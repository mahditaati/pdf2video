# pdf2video

A clean, production-quality command-line tool that converts multi-page PDF documents into crystal-clear, lightweight MP4 videos with background music. Designed specifically for presentations, slide decks, technical reports, and document showcases, `pdf2video` ensures that text remains sharp and perfectly legible while keeping file sizes small.

### Key Features

- **Crystal-Clear Text**: Renders pages at 1920 px resolution using anti-aliased subpixel rendering with H.264 `yuv420p` encoding and `tune stillimage`.
- **Intelligent Canvas Padding**: Automatically handles mixed page aspect ratios (e.g. landscape slides mixed with portrait documents) with configurable background color padding without stretching or distortion.
- **Background Music Integration**: Automatically loops shorter music tracks or trims longer audio to precisely match the video length, with a smooth ending fade-out.
- **Fault-Tolerant Parallel Batch Processing**: Uses multi-core process pools to convert entire folders of PDFs concurrently. Corrupted, empty, or password-protected files are cleanly reported without aborting the batch.
- **Atomic File Writing**: Videos are encoded to an isolated temporary file first and atomically renamed upon success, eliminating corrupt half-written files.
- **Fast Web Playback**: Embeds `-movflags +faststart` metadata for instant browser streaming.
- **Zero-Code Configuration**: Control all behaviors through `config.yaml` or direct CLI flags.

---

## Quick Start

1. Put your PDF files inside the `input/` folder.
2. Put a background music file (e.g. `.mp3`, `.wav`) inside the `music/` folder (or project root).
3. Run the conversion command:
   ```bash
   python -m pdf2video.cli
   ```
   *(or `pdf2video` if installed in your environment)*
4. Find your rendered MP4 videos in the `output/` folder!

---

## Command Examples

### Convert a Single PDF File
```bash
python -m pdf2video.cli -i document.pdf -o output/
```

### Convert an Entire Folder
```bash
python -m pdf2video.cli -i input/ -o output/
```

### Recursive Folder Scanning
Convert all PDFs in subfolders and preserve directory structure:
```bash
python -m pdf2video.cli -i input/ -o output/ --recursive
```

### Custom Page Duration (e.g. 2.5 seconds per page)
```bash
python -m pdf2video.cli -s 2.5
```

### Custom Music Volume & Fade-Out Duration
Set background music volume to 10% with a 3-second fade-out:
```bash
python -m pdf2video.cli --volume 0.10 --fade-out 3.0
```

### Overwrite Existing Videos
By default, existing output files are skipped. Force re-encoding:
```bash
python -m pdf2video.cli --overwrite
```

### Dry Run (Preview Actions Without Encoding)
```bash
python -m pdf2video.cli --dry-run
```

### High Sharpness Mode (CRF 20, Preset Slower)
```bash
python -m pdf2video.cli --crf 20 --preset slower
```

---

## Configuration & CLI Reference

All options can be set globally in `config.yaml` or overridden on the command line:

| Option (`config.yaml`) | CLI Flag | Default | Description |
|:---|:---|:---:|:---|
| `input_folder` | `-i`, `--input` | `"input"` | Path to an input PDF file or folder containing PDFs. |
| `output_folder` | `-o`, `--output` | `"output"` | Directory where generated MP4 videos will be saved. |
| `seconds_per_page` | `-s`, `--seconds-per-page` | `1.0` | Number of seconds each PDF page frame is displayed. |
| `music_file` | `-m`, `--music` | `null` | Path to background audio file. If null, auto-detects from `music/` or root. |
| `music_volume` | `--volume` | `0.15` | Background audio volume multiplier (`0.0` = mute, `0.15` = 15%, `1.0` = full). |
| `music_fade_out_seconds` | `--fade-out` | `2.0` | Duration of audio fade-out at the end of the video (capped at video length). |
| `render_width` | `-w`, `--width` | `1920` | Target horizontal resolution in pixels. Height adjusts to preserve aspect ratio. |
| `background_color` | `--bg-color` | `"#FFFFFF"` | Canvas color used for padding mixed page dimensions (e.g. `"#FFFFFF"`, `"black"`). |
| `fps` | `--fps` | `2` | Video frame rate. 2 fps keeps static slide files tiny while universally playable. |
| `crf` | `--crf` | `23` | H.264 Constant Rate Factor (0-51). Lower = sharper/larger, higher = smaller/blurrier. |
| `preset` | `--preset` | `"slow"` | x264 compression efficiency preset (`ultrafast` to `veryslow`). |
| `audio_bitrate` | `--bitrate` | `"64k"` | AAC audio stream bitrate. |
| `audio_channels` | `--channels` | `"stereo"` | Audio channels (`"stereo"` or `"mono"`). |
| `workers` | `--workers` | `null` | Number of parallel worker processes. Defaults to half of CPU cores (min 1). |
| `recursive` | `-r`, `--recursive` | `false` | Scan input directories recursively. |
| `overwrite` | `--overwrite` | `false` | Overwrite existing output videos instead of skipping them. |
| `log_file` | `--log-file` | `null` | Path to optional log file for execution details. |
| `ffmpeg_path` | `--ffmpeg-path` | `null` | Custom path to the `ffmpeg` executable binary. |
| N/A | `--dry-run` | `false` | List files that would be converted without producing videos. |
| N/A | `--verbose` | `false` | Enable detailed debug logs in console. |

---

## How to Trade Quality Against File Size

Video encoding balances visual sharpness against resulting file size. Because PDF documents consist primarily of high-contrast text and vector graphics, three settings control this trade-off:

1. **CRF (Constant Rate Factor, `--crf`)**:
   - **CRF 20**: Maximum sharpness for intricate diagrams and fine serif fonts. File size is ~8% larger.
   - **CRF 23 (Default)**: Sweet spot. High visual fidelity (PSNR ~41.4 dB) with compact file sizes (~15-20 KB per page).
   - **CRF 26-28**: Maximum bandwidth savings for presentations with large bold headings. Reduces file size by ~12-15%, with slight edge compression artifacts on small fonts.

2. **Render Width (`--width`)**:
   - `1920` (Default Full HD): Ideal for desktop presentations, YouTube, and browser viewing.
   - `1280` (720p HD): Cuts file size by ~35% for mobile-first distribution.
   - `2560` (1440p 2K): Ultra-sharp for 4K displays or fine CAD/architectural schematics.

3. **Frame Rate (`--fps`)**:
   - `2` (Default): Static slides do not change during a page duration. A low frame rate of 2 fps dramatically lowers video bitrate without affecting perceived quality or player compatibility.

---

## Background Music Guidelines

Place your audio track (`.mp3`, `.wav`, `.m4a`, `.aac`, `.flac`, `.ogg`) inside the `music/` folder.
- If multiple audio files are present, specify the exact one in `config.yaml` or with `--music path/to/track.mp3`.
- **Copyright Notice**: Always ensure that you possess the necessary distribution rights, commercial licensing, or royalty-free permissions for any background music you include in videos published online.

---

## Troubleshooting

- **`FFmpeg is not installed or could not be found`**:
  Make sure FFmpeg is installed and added to your system `PATH`, or specify its binary path directly via `ffmpeg_path: "/path/to/ffmpeg"` in `config.yaml` or `--ffmpeg-path /path/to/ffmpeg`.
- **`Configured music file does not exist`**:
  Verify the audio path in `config.yaml` or place your music file directly into `music/` so auto-detection can locate it.
- **`PDF is password-protected`**:
  Encrypted PDFs that require an opening password cannot be rendered automatically. Remove the password encryption from the PDF before converting.
- **`Corrupted or invalid PDF`**:
  Damaged PDFs are logged as `[FAIL]` in the batch summary while other files in the folder continue processing unaffected.
- **`Output video looks blurry`**:
  Decrease the CRF value (`--crf 20`) or increase the horizontal render width (`--width 2560`).
- **`File size is too large`**:
  Increase the CRF value (`--crf 26`), ensure `--fps 2` is used, and check that `--bitrate` is set to `64k`.

---

## Project Structure

```text
├── config.yaml             # Central configuration file with commented options
├── input/                  # Default folder for input PDF files (.gitkeep)
├── music/                  # Default folder for background music files (.gitkeep)
├── output/                 # Default destination for generated MP4 videos (.gitkeep)
├── pyproject.toml          # Package metadata and console entry point
├── requirements.txt        # Python dependency declarations
├── src/
│   └── pdf2video/
│       ├── __init__.py     # Package initialization and version info
│       ├── audio.py        # Music auto-detection, duration probe, filter graph
│       ├── batch.py        # Multi-process batch runner, skip logic, summary table
│       ├── cli.py          # Command-line interface and argument parsing
│       ├── config.py       # YAML loader, dataclass schema, validation
│       ├── encoder.py      # FFmpeg command builder, atomic video output
│       ├── ffmpeg_check.py # FFmpeg executable locator and diagnosis
│       └── renderer.py     # PyMuPDF page rasterization, aspect ratio padding
└── tests/
    ├── __init__.py
    ├── test_batch_and_encoder.py
    ├── test_config.py
    ├── test_duration_and_audio.py
    ├── test_e2e.py
    └── test_renderer.py
```
