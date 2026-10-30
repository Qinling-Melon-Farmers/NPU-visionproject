"""Verify the extracted vision submission package.

Run from the extracted package root:
    python verify_package.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest" / "submission_manifest.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    if not MANIFEST.is_file():
        print("missing manifest/submission_manifest.json")
        return 1
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    report = ROOT / "report" / "vision_report.docx"
    pdf = ROOT / "report" / "vision_report.pdf"
    if not report.is_file():
        print("missing report/vision_report.docx")
        return 1
    if not pdf.is_file():
        print("missing report/vision_report.pdf")
        return 1
    if sha256(report) != data.get("report_sha256"):
        print("report hash does not match manifest")
        return 1
    bad = []
    for item in data.get("files", []):
        path = ROOT / item["path"]
        if not path.is_file():
            bad.append((item["path"], "missing"))
        elif sha256(path) != item["sha256"]:
            bad.append((item["path"], "hash"))
    if bad:
        for name, why in bad:
            print(f"{why}: {name}")
        return 1
    required = ["README_FIRST.md", "code/vision/__main__.py",
                "docs/REPRODUCE.md", "docs/EVIDENCE.md", "docs/LICENSES.md"]
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        print("missing required entries: " + ", ".join(missing))
        return 1
    print(f"OK: {len(data['files'])} files, report {data['report_sha256'][:12]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
