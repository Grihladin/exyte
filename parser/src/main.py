"""CLI entry point for parsing utilities."""

from __future__ import annotations

import sys
from pathlib import Path

from src.config import (
    DEFAULT_PDF_PATH,
    DEFAULT_START_PAGE_INDEX,
    DEFAULT_PAGE_COUNT,
)
from src import pipeline


def _parse_args(argv: list[str]) -> tuple[Path, int, int, bool]:
    pdf_path: Path | None = None
    num_pages = DEFAULT_PAGE_COUNT
    start_page = DEFAULT_START_PAGE_INDEX
    phase1_only = False

    args = list(argv)
    if args and not args[0].startswith("-") and not args[0].isdigit():
        pdf_path = Path(args.pop(0))
    elif not args and not DEFAULT_PDF_PATH.exists():
        raise FileNotFoundError(
            f"Default PDF not found at {DEFAULT_PDF_PATH} and no path argument was provided."
        )

    for arg in args:
        if arg == "--phase1":
            phase1_only = True
        elif arg.startswith("--start="):
            value = arg.split("=", 1)[1]
            page_number = int(value)
            if page_number < 1:
                raise ValueError("--start must be >= 1")
            start_page = page_number - 1
        elif arg.isdigit():
            num_pages = int(arg)
        else:
            raise ValueError(
                "Usage: python -m src.main [pdf_path] [num_pages] [--start=<page>] [--phase1]"
            )

    pdf = pdf_path or DEFAULT_PDF_PATH
    if not pdf.exists():
        raise FileNotFoundError(f"PDF not found: {pdf}")

    return pdf, num_pages, start_page, phase1_only


def main() -> None:
    try:
        pdf_path, num_pages, start_page, phase1_only = _parse_args(sys.argv[1:])
    except (ValueError, FileNotFoundError) as exc:
        sys.exit(str(exc))

    if phase1_only:
        pipeline.run_pdf_phase(pdf_path, num_pages, start_page)
    else:
        pipeline.run_structure_phase(pdf_path, num_pages, start_page)


if __name__ == "__main__":
    main()
