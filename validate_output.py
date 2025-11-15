"""Validate generated parsed_document.json for table coverage."""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.append(str(REPO_ROOT / "parser"))

from src.config import JSON_OUTPUT_FILE


def find_table_issues(document: dict) -> list[dict]:
    tables_with_data = set()
    missing_instances = []
    def norm(name: str) -> str:
        cleaned = (name or "").strip().lower()
        return re.sub(r'^tables\b', 'table', cleaned)

    for chapter in document.get("chapters", []):
        chapter_num = chapter.get("chapter_number")
        for section in chapter.get("sections", []):
            section_num = section.get("section_number")
            for table_ref in section.get("references", {}).get("tables", []):
                ref_name_raw = table_ref.get("reference") or "<unnamed table>"
                ref_name = norm(ref_name_raw)
                if table_ref.get("table_data"):
                    tables_with_data.add(ref_name)
                else:
                    missing_instances.append({
                        "chapter": chapter_num,
                        "section": section_num,
                        "reference": ref_name,
                    })
    unresolved = [issue for issue in missing_instances if norm(issue["reference"]) not in tables_with_data]
    return unresolved


def main() -> int:
    output_path = JSON_OUTPUT_FILE
    if not output_path.exists():
        print(f"Output file not found: {output_path}", file=sys.stderr)
        return 1
    data = json.loads(output_path.read_text())
    issues = find_table_issues(data)
    if not issues:
        print("✅ All table references include extracted data.")
        return 0
    print(f"⚠️ {len(issues)} table reference(s) missing structured data:")
    for issue in issues[:20]:
        print(
            f"  Chapter {issue['chapter']} Section {issue['section']} -> {issue['reference']}"
        )
    if len(issues) > 20:
        print(f"  ... and {len(issues) - 20} more")
    return 1


if __name__ == "__main__":
    sys.exit(main())
