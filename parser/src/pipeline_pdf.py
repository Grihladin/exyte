from __future__ import annotations

from pathlib import Path

from tqdm.auto import tqdm

from src.parsers import PDFExtractor


def run_pdf_phase(pdf_path: str | Path, num_pages: int, start_page: int) -> None:
    """Phase 1 sampling with a simple progress bar (no logging)."""
    with PDFExtractor(pdf_path) as extractor:
        total_pages = extractor.get_page_count()
        if start_page >= total_pages:
            raise ValueError(
                f"Start page ({start_page + 1}) is beyond total pages ({total_pages})."
            )

        pages_to_extract = min(num_pages, total_pages - start_page)

        with tqdm(total=pages_to_extract, desc="Extracting pages", unit="page") as progress:
            for page_offset in range(pages_to_extract):
                page_num = start_page + page_offset
                extractor.extract_page_text(page_num)
                extractor.extract_page_text_with_blocks(page_num)
                extractor.get_images_on_page(page_num)
                progress.update(1)
