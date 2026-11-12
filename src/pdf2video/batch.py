"""Batch processing module with multiprocessing support and error containment."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Optional
from tqdm import tqdm

from .audio import auto_detect_music_file, probe_media_duration
from .config import AppConfig
from .encoder import encode_video
from .ffmpeg_check import find_ffmpeg
from .renderer import (
    CorruptedPDFError,
    EmptyPDFError,
    PasswordProtectedPDFError,
    render_pdf_to_images,
)

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Outcome of processing a single PDF file."""

    input_path: Path
    output_path: Path
    status: str  # 'succeeded' | 'skipped' | 'failed'
    reason: Optional[str] = None
    page_count: int = 0
    duration: float = 0.0
    file_size_bytes: int = 0


def discover_pdf_files(target: Path, recursive: bool = False) -> list[Path]:
    """Discover PDF files from a file or directory path.

    Args:
        target: Target file or directory.
        recursive: Whether to search subdirectories recursively.

    Returns:
        List of resolved PDF Path objects.
    """
    target = target.resolve()
    if target.is_file():
        if target.suffix.lower() == ".pdf":
            return [target]
        return []

    if not target.is_dir():
        return []

    found: list[Path] = []
    if recursive:
        for root, _, files in os.walk(target):
            for f in sorted(files):
                if f.lower().endswith(".pdf"):
                    found.append(Path(root) / f)
    else:
        for entry in sorted(target.iterdir()):
            if entry.is_file() and entry.suffix.lower() == ".pdf":
                found.append(entry)

    return found


def _worker_process_file(job_payload: dict[str, Any]) -> TaskResult:
    """Isolated worker function executed in child processes.

    Ensures each task uses its own independent temporary directory that is
    guaranteed to be removed upon completion or failure.
    """
    pdf_path = Path(job_payload["pdf_path"])
    output_path = Path(job_payload["output_path"])
    ffmpeg_exe = Path(job_payload["ffmpeg_exe"])
    music_file = Path(job_payload["music_file"]) if job_payload.get("music_file") else None

    seconds_per_page = float(job_payload["seconds_per_page"])
    render_width = int(job_payload["render_width"])
    background_color = str(job_payload["background_color"])
    fps = int(job_payload["fps"])
    crf = int(job_payload["crf"])
    preset = str(job_payload["preset"])
    audio_bitrate = str(job_payload["audio_bitrate"])
    audio_channels = str(job_payload["audio_channels"])
    music_volume = float(job_payload["music_volume"])
    music_fade_out_seconds = float(job_payload["music_fade_out_seconds"])

    # Dedicated temporary directory for this specific PDF's frames
    temp_dir = tempfile.TemporaryDirectory(prefix="pdf2vid_frames_")
    try:
        frames_dir = Path(temp_dir.name)

        num_pages, _ = render_pdf_to_images(
            pdf_path=pdf_path,
            output_dir=frames_dir,
            target_width=render_width,
            background_color=background_color,
        )

        encode_video(
            ffmpeg_exe=ffmpeg_exe,
            frames_dir=frames_dir,
            num_pages=num_pages,
            seconds_per_page=seconds_per_page,
            output_file=output_path,
            fps=fps,
            crf=crf,
            preset=preset,
            audio_file=music_file,
            audio_volume=music_volume,
            audio_fade_out_seconds=music_fade_out_seconds,
            audio_bitrate=audio_bitrate,
            audio_channels=audio_channels,
        )

        file_size = output_path.stat().st_size if output_path.exists() else 0
        total_duration = num_pages * seconds_per_page

        return TaskResult(
            input_path=pdf_path,
            output_path=output_path,
            status="succeeded",
            page_count=num_pages,
            duration=total_duration,
            file_size_bytes=file_size,
        )

    except (EmptyPDFError, PasswordProtectedPDFError, CorruptedPDFError) as err:
        logger.warning("Rendering failure on '%s': %s", pdf_path.name, err)
        return TaskResult(
            input_path=pdf_path,
            output_path=output_path,
            status="failed",
            reason=str(err),
        )
    except Exception as err:
        logger.error("Unexpected error processing '%s': %s", pdf_path.name, err, exc_info=True)
        return TaskResult(
            input_path=pdf_path,
            output_path=output_path,
            status="failed",
            reason=f"{type(err).__name__}: {err}",
        )
    finally:
        try:
            temp_dir.cleanup()
        except Exception:
            pass


def determine_worker_count(requested: Optional[int]) -> int:
    """Compute default or sanitized worker count."""
    if requested is not None and requested >= 1:
        return requested
    cpu_count = os.cpu_count() or 2
    return max(1, cpu_count // 2)


def print_batch_summary(results: list[TaskResult]) -> None:
    """Print a clean, aligned summary table of batch execution results."""
    succeeded = [r for r in results if r.status == "succeeded"]
    skipped = [r for r in results if r.status == "skipped"]
    failed = [r for r in results if r.status == "failed"]

    print("\n" + "=" * 65)
    print("                      BATCH PROCESSING SUMMARY")
    print("=" * 65)
    print(f" Total files processed: {len(results)}")
    print(f"   [SUCCESS] Succeeded: {len(succeeded)}")
    print(f"   [SKIP]    Skipped:   {len(skipped)}")
    print(f"   [FAIL]    Failed:    {len(failed)}")
    print("-" * 65)

    if succeeded:
        print("\nSucceeded files:")
        for r in succeeded:
            size_kb = r.file_size_bytes / 1024.0
            print(
                f"  - {r.input_path.name} -> {r.output_path.name} "
                f"({r.page_count} pages, {r.duration:.1f}s, {size_kb:.1f} KB)"
            )

    if skipped:
        print("\nSkipped files (already exist; use --overwrite to replace):")
        for r in skipped:
            print(f"  - {r.input_path.name} (destination: {r.output_path.name})")

    if failed:
        print("\nFailed files:")
        for r in failed:
            print(f"  - {r.input_path.name}: {r.reason}")

    print("=" * 65 + "\n")


def process_batch(
    config: AppConfig,
    dry_run: bool = False,
) -> tuple[int, list[TaskResult]]:
    """Execute batch conversion of PDFs according to configuration.

    Args:
        config: Validated AppConfig settings.
        dry_run: If True, only lists actions without rendering or encoding.

    Returns:
        Tuple of (exit_code, list_of_TaskResults).
    """
    # Verify FFmpeg before starting
    ffmpeg_exe = find_ffmpeg(config.ffmpeg_path)

    # Ensure default folders exist
    if not config.input_folder.is_file() and config.input_folder.suffix.lower() != ".pdf":
        config.input_folder.mkdir(parents=True, exist_ok=True)
    if config.output_folder.suffix.lower() != ".mp4":
        config.output_folder.mkdir(parents=True, exist_ok=True)
    Path("music").mkdir(parents=True, exist_ok=True)

    # Resolve music file
    resolved_music = auto_detect_music_file(
        explicit_path=config.music_file,
        search_dirs=[Path("music"), Path(".")],
    )

    if resolved_music:
        music_dur = probe_media_duration(ffmpeg_exe, resolved_music)
        if music_dur:
            logger.info("Using background music: %s (duration: %.1fs)", resolved_music, music_dur)
        else:
            logger.info("Using background music: %s", resolved_music)
    else:
        logger.info("No background music file detected; videos will have no audio track.")

    # Discover PDFs
    pdf_files = discover_pdf_files(config.input_folder, recursive=config.recursive)
    if not pdf_files:
        logger.warning("No PDF files found at: %s", config.input_folder)
        return 0, []

    results: list[TaskResult] = []
    pending_payloads: list[dict[str, Any]] = []

    for pdf_path in pdf_files:
        # Determine output file path
        if config.output_folder.suffix.lower() == ".mp4" and len(pdf_files) == 1:
            out_path = config.output_folder
        elif config.input_folder.is_dir() and config.recursive:
            try:
                rel_path = pdf_path.relative_to(config.input_folder)
                out_path = (config.output_folder / rel_path).with_suffix(".mp4")
            except ValueError:
                out_path = config.output_folder / f"{pdf_path.stem}.mp4"
        else:
            out_path = config.output_folder / f"{pdf_path.stem}.mp4"

        # Check skip condition
        if out_path.exists() and not config.overwrite:
            results.append(
                TaskResult(
                    input_path=pdf_path,
                    output_path=out_path,
                    status="skipped",
                    reason="Output file already exists",
                )
            )
            continue

        if dry_run:
            results.append(
                TaskResult(
                    input_path=pdf_path,
                    output_path=out_path,
                    status="skipped",
                    reason="[Dry-run] Would convert",
                )
            )
            continue

        payload = {
            "pdf_path": str(pdf_path),
            "output_path": str(out_path),
            "ffmpeg_exe": str(ffmpeg_exe),
            "music_file": str(resolved_music) if resolved_music else None,
            "seconds_per_page": config.seconds_per_page,
            "render_width": config.render_width,
            "background_color": config.background_color,
            "fps": config.fps,
            "crf": config.crf,
            "preset": config.preset,
            "audio_bitrate": config.audio_bitrate,
            "audio_channels": config.audio_channels,
            "music_volume": config.music_volume,
            "music_fade_out_seconds": config.music_fade_out_seconds,
        }
        pending_payloads.append(payload)

    if dry_run:
        print("\n--- DRY RUN PREVIEW ---")
        for r in results:
            print(f"Would convert: {r.input_path} -> {r.output_path}")
        print(f"Total PDFs found: {len(pdf_files)}")
        print("-----------------------\n")
        return 0, results

    # Execute conversion tasks
    num_workers = determine_worker_count(config.workers)
    total_tasks = len(pdf_files)

    with tqdm(total=total_tasks, desc="Converting PDFs", unit="video") as pbar:
        # Update progress bar for already skipped files
        pbar.update(len(results))

        if pending_payloads:
            if num_workers == 1 or len(pending_payloads) == 1:
                # Run sequentially without multiprocessing overhead
                for payload in pending_payloads:
                    res = _worker_process_file(payload)
                    results.append(res)
                    pbar.update(1)
            else:
                with ProcessPoolExecutor(max_workers=num_workers) as executor:
                    future_to_pdf = {
                        executor.submit(_worker_process_file, p): p["pdf_path"]
                        for p in pending_payloads
                    }
                    for future in as_completed(future_to_pdf):
                        try:
                            res = future.result()
                            results.append(res)
                        except Exception as e:
                            pdf_name = future_to_pdf[future]
                            results.append(
                                TaskResult(
                                    input_path=Path(pdf_name),
                                    output_path=Path("unknown"),
                                    status="failed",
                                    reason=f"Worker crashed: {e}",
                                )
                            )
                        finally:
                            pbar.update(1)

    print_batch_summary(results)

    has_failures = any(r.status == "failed" for r in results)
    exit_code = 1 if has_failures else 0
    return exit_code, results
