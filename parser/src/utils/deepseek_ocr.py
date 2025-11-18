"""Wrapper around the DeepSeek OCR model for table extraction."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


@dataclass
class OCRTable:
    """Structured OCR response."""

    headers: list[str]
    rows: list[list[str]]
    raw_text: str


class DeepSeekOCR:
    """Thin wrapper around transformers' DeepSeek OCR checkpoint."""

    def __init__(
        self,
        model_name: str,
        device: str | None = None,
        max_new_tokens: int = 512,
    ) -> None:
        try:
            from transformers import AutoModelForCausalLM, AutoProcessor
            import torch
        except ImportError as exc:  # pragma: no cover - environment specific
            raise RuntimeError(
                "transformers and torch are required for DeepSeek OCR integration."
            ) from exc

        self._torch = torch
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.max_new_tokens = max_new_tokens

        logger.info("Loading DeepSeek OCR model %s on %s", model_name, self.device)
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

        self._pad_token_id = self._resolve_pad_token_id()

    def extract_table(self, image_path: str | Path) -> OCRTable:
        """Run OCR over the provided table image and parse it into rows."""
        raw_text = self._generate_text(Path(image_path))
        headers, rows = self._parse_table_text(raw_text)
        return OCRTable(headers=headers, rows=rows, raw_text=raw_text)

    def _generate_text(self, image_path: Path) -> str:
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover - environment specific
            raise RuntimeError("Pillow is required for DeepSeek OCR.") from exc

        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {
            key: value.to(self.device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }

        generation_kwargs = {
            "max_new_tokens": self.max_new_tokens,
        }
        if self._pad_token_id is not None:
            generation_kwargs["pad_token_id"] = self._pad_token_id

        with self._torch.inference_mode():
            output_ids = self.model.generate(**inputs, **generation_kwargs)

        decoded = self.processor.batch_decode(output_ids, skip_special_tokens=True)
        if not decoded:
            return ""
        return decoded[0].strip()

    def _parse_table_text(self, text: str) -> tuple[list[str], list[list[str]]]:
        """Convert OCR text into headers + rows with simple heuristics."""
        if not text:
            return [], []

        cleaned_lines = [
            line.strip().strip("|")
            for line in text.splitlines()
            if line.strip() and not set(line.strip()) <= {"-", "|", "+"}
        ]
        if not cleaned_lines:
            return [], []

        delimiter = self._infer_delimiter(cleaned_lines)

        parsed_rows: list[list[str]] = []
        for line in cleaned_lines:
            if delimiter:
                cells = [cell.strip() for cell in line.split(delimiter)]
            else:
                cells = [cell.strip() for cell in re.split(r"\s{2,}", line)]
            cells = [cell for cell in cells if cell]
            if cells:
                parsed_rows.append(cells)

        if not parsed_rows:
            return [], []

        headers = parsed_rows[0]
        rows = parsed_rows[1:] if len(parsed_rows) > 1 else []
        return headers, rows

    @staticmethod
    def _infer_delimiter(lines: Iterable[str]) -> str | None:
        for delimiter in ("|", "\t", ",", ";"):
            if any(delimiter in line for line in lines):
                return delimiter
        return None

    def _resolve_pad_token_id(self) -> int | None:
        tokenizer = getattr(self.processor, "tokenizer", None)
        if tokenizer and tokenizer.pad_token_id is not None:
            return tokenizer.pad_token_id
        if tokenizer and tokenizer.eos_token_id is not None:
            return tokenizer.eos_token_id
        return getattr(self.model.config, "pad_token_id", None)
