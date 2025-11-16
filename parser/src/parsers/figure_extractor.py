"""Figure and image extraction from PDF documents."""

import logging
import re
from pathlib import Path
from typing import Optional, Sequence

from src.utils.figures import FigureLabel

from .pdf_extractor import PDFExtractor

logger = logging.getLogger(__name__)


class FigureExtractor:
    """Extract figures and images from PDF documents."""
    
    def __init__(self, pdf_extractor: PDFExtractor, images_dir: Path):
        """Initialize figure extractor.
        
        Args:
            pdf_extractor: PDFExtractor instance for accessing PDF
            images_dir: Directory to save extracted images
        """
        self.pdf_extractor = pdf_extractor
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        
        # Track extracted images and IDs to avoid duplicates
        self.extracted_xrefs: set[int] = set()
        self.generated_ids: set[str] = set()
        self.figure_counter = 0

    def _slugify_label(self, label_source: str | None) -> str:
        """Convert a figure number or label into a filesystem-friendly slug."""
        if not label_source:
            return ""
        slug = label_source.strip()
        slug = slug.replace(" ", "_")
        slug = re.sub(r'[^0-9A-Za-z_.-]+', "_", slug)
        slug = re.sub(r'_+', "_", slug).strip("_")
        return slug

    def _build_figure_id(self, page_label: str, label: FigureLabel | None) -> str:
        """Create a readable figure identifier."""
        if label:
            slug = self._slugify_label(label.number or label.raw_label)
            base_id = f"figure_{slug}" if slug else None
        else:
            base_id = None

        if not base_id:
            base_id = f"fig_p{page_label}_{self.figure_counter}"

        candidate = base_id
        suffix = 1
        while candidate in self.generated_ids:
            candidate = f"{base_id}_{suffix}"
            suffix += 1

        self.generated_ids.add(candidate)
        return candidate
    
    def extract_figures_from_page(
        self,
        page_num: int,
        page_label: Optional[str] = None,
        figure_labels: Optional[Sequence[FigureLabel]] = None,
    ) -> list[dict]:
        """Extract all figures from a page.
        
        Args:
            page_num: Page number (0-indexed)
            page_label: Optional page label (e.g., "27", "ii") for figure ID
            figure_labels: Optional ordered labels detected within the page text
            
        Returns:
            List of figure metadata dictionaries
        """
        try:
            images = self.pdf_extractor.get_images_on_page(page_num)
            
            if not images:
                return []
            
            figures = []
            page_label_str = page_label or str(page_num + 1)
            figure_labels = list(figure_labels or [])
            
            for img_data in images:
                xref = img_data["xref"]
                
                # Skip if already extracted (same image referenced multiple times)
                if xref in self.extracted_xrefs:
                    logger.debug(f"Skipping duplicate image xref={xref} on page {page_num + 1}")
                    continue
                
                try:
                    # Extract image data
                    image_info = self.pdf_extractor.extract_image(xref)
                    
                    # Generate figure ID
                    self.figure_counter += 1
                    label_info = (
                        figure_labels[len(figures)]
                        if len(figures) < len(figure_labels)
                        else None
                    )
                    figure_id = self._build_figure_id(page_label_str, label_info)
                    
                    # Save image to disk
                    image_filename = f"{figure_id}.{image_info['extension']}"
                    image_path = self.images_dir / image_filename
                    
                    with open(image_path, "wb") as f:
                        f.write(image_info["data"])
                    
                    logger.debug(
                        f"Saved figure {figure_id} from page {page_num + 1}: "
                        f"{image_info['width']}x{image_info['height']} "
                        f"{image_info['extension'].upper()}"
                    )
                    
                    # Create figure metadata
                    figure_metadata: dict[str, object] = {
                        "figure_id": figure_id,
                        "page": page_num + 1,  # 1-indexed for user display
                        "page_label": page_label_str,
                        "image_path": str(image_path.relative_to(image_path.parent.parent)),
                        "width": image_info["width"],
                        "height": image_info["height"],
                        "format": image_info["extension"].upper(),
                        "colorspace": image_info.get("colorspace", "unknown"),
                        "xref": xref,
                    }
                    
                    if label_info:
                        figure_metadata["label"] = label_info.display_label
                        figure_metadata["figure_number"] = label_info.number
                        if label_info.caption:
                            figure_metadata["caption"] = label_info.caption
                    
                    figures.append(figure_metadata)
                    self.extracted_xrefs.add(xref)
                    
                except Exception as e:
                    logger.warning(f"Failed to extract image xref={xref} on page {page_num + 1}: {e}")
                    continue
            
            if figures:
                logger.info(f"Extracted {len(figures)} figures from page {page_num + 1}")
            
            return figures
            
        except Exception as e:
            logger.error(f"Failed to extract figures from page {page_num + 1}: {e}")
            return []
    
    def extract_all_figures(
        self,
        start_page: int = 0,
        end_page: Optional[int] = None,
        page_labels: Optional[dict[int, str]] = None,
        figure_labels_map: Optional[dict[int, Sequence[FigureLabel]]] = None,
    ) -> dict[str, dict]:
        """Extract all figures from document.
        
        Args:
            start_page: Starting page number (0-indexed)
            end_page: Ending page number (0-indexed, exclusive). None means all pages.
            page_labels: Optional mapping of page_num -> page_label
            figure_labels_map: Optional mapping of page_num -> ordered figure labels
            
        Returns:
            Dictionary mapping figure_id -> figure_metadata
        """
        if end_page is None:
            end_page = self.pdf_extractor.get_page_count()
        
        all_figures: dict[str, dict] = {}
        page_labels = page_labels or {}
        figure_labels_map = figure_labels_map or {}
        
        logger.info(f"Extracting figures from pages {start_page + 1} to {end_page}...")
        
        for page_num in range(start_page, end_page):
            page_label = page_labels.get(page_num)
            labels_for_page = figure_labels_map.get(page_num)
            figures = self.extract_figures_from_page(
                page_num,
                page_label,
                figure_labels=labels_for_page,
            )
            
            for figure in figures:
                figure_id = figure["figure_id"]
                all_figures[figure_id] = figure
            
            # Log progress every 100 pages
            if (page_num + 1) % 100 == 0:
                logger.info(
                    f"Processed {page_num + 1}/{end_page} pages "
                    f"({len(all_figures)} figures extracted so far)..."
                )
        
        logger.info(
            f"Figure extraction complete: {len(all_figures)} figures "
            f"from {end_page - start_page} pages"
        )
        
        return all_figures
