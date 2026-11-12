# ==============================================================================
# Makefile for pdf2video
# ==============================================================================

.PHONY: help run dry test overwrite

help:
	@echo "pdf2video - Quick Command Reference"
	@echo "-----------------------------------"
	@echo "  make run        : Convert all PDFs in input/ to output/"
	@echo "  make dry        : Preview files to be converted (dry-run)"
	@echo "  make overwrite  : Convert all PDFs and overwrite existing videos"
	@echo "  make test       : Run the 37 automated test suite"
	@echo ""

run:
	@./run.sh

dry:
	@./run.sh dry

overwrite:
	@./run.sh overwrite

test:
	@./run.sh test
