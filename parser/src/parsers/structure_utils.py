"""Utility helpers for structure parsing."""

from __future__ import annotations

import re
import statistics
from typing import Optional

from ..utils.patterns import PATTERNS
from ..utils.formatters import clean_text


def extract_chapter_title(lines: list[str], current_idx: int) -> str:
    title_parts: list[str] = []
    found_start = False

    for i in range(current_idx + 1, min(current_idx + 10, len(lines))):
        line = lines[i].strip()
        if not line:
            if found_start:
                break
            continue

        if (
            PATTERNS["chapter"].match(line)
            or PATTERNS["user_notes"].match(line)
            or PATTERNS["part"].match(line)
            or PATTERNS["section_header"].match(line)
        ):
            break

        if line.isupper() or (len(line.split()) <= 6 and not line.endswith(".")):
            title_parts.append(line)
            found_start = True
            if ". . ." in line or re.search(r"\.\s+\.\s+\.", line):
                continue
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if (
                    PATTERNS["part"].match(next_line)
                    or PATTERNS["section_header"].match(next_line)
                ):
                    break
                if next_line and (next_line.isupper() or ". . ." in next_line):
                    continue
            break
        elif found_start:
            break

    if title_parts:
        return clean_text(" ".join(title_parts))
    return "Untitled Chapter"


def looks_like_section(line: str) -> bool:
    parts = line.split(None, 1)
    if len(parts) < 2:
        return False
    section_num, title = parts
    if not re.match(r"^\d+(?:\.\d+)*$", section_num):
        return False
    if len(title) > 200:
        return False
    first_token = title.split()[0] if title.split() else ""
    first_token = first_token.lstrip('(["')
    if not first_token or not first_token[0].isupper():
        return False
    uppercase_words = sum(
        1 for word in title.split() if word.isupper() or word[0].isupper()
    )
    if uppercase_words < len(title.split()) * 0.3:
        return False
    return True


def extract_title_and_inline_text(text: str) -> tuple[str, str]:
    normalized = text.strip()
    if not normalized:
        return "", ""
    split_match = re.search(r"\.\s+(?=[A-Z\[])", normalized)
    if split_match:
        title = normalized[: split_match.start()].strip()
        inline_text = normalized[split_match.end():].strip()
        return clean_text(title.rstrip(".")), inline_text
    return clean_text(normalized.rstrip(".")), ""


def normalize_line_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def align_line_features(lines: list[str], features: list[dict]) -> dict[int, dict]:
    lookup: dict[int, dict] = {}
    feature_idx = 0
    total_features = len(features)
    for line_idx, line in enumerate(lines):
        normalized_line = normalize_line_text(line)
        if not normalized_line:
            continue
        while feature_idx < total_features:
            feature = features[feature_idx]
            feature_idx += 1
            normalized_feature = normalize_line_text(feature.get("text", ""))
            if not normalized_feature:
                continue
            if normalized_feature == normalized_line:
                lookup[line_idx] = feature
                break
    return lookup


def compute_font_stats(features: list[dict]) -> dict[str, float]:
    sizes = [feature.get("max_size") for feature in features if feature.get("max_size")]
    if not sizes:
        return {}
    median_size = statistics.median(sizes)
    avg_size = sum(sizes) / len(sizes)
    max_size = max(sizes)
    return {
        "median": float(median_size),
        "average": float(avg_size),
        "max": float(max_size),
    }


def is_confident_part_heading(
    line_idx: int,
    line_features: Optional[dict[int, dict]],
    font_stats: Optional[dict[str, float]],
) -> bool:
    if not line_features or line_idx not in line_features:
        return True
    info = line_features[line_idx]
    font_size = info.get("max_size") or info.get("size")
    if font_size is None:
        return True
    median_size = (font_stats or {}).get("median", 0.0)
    max_size = (font_stats or {}).get("max", 0.0)
    if font_size >= max(12.0, median_size + 1.0):
        return True
    if max_size and font_size >= max_size * 0.9:
        return True
    if info.get("is_bold") and font_size >= median_size:
        return True
    return False
