"""Build the vision-course submission package with an explicit layout.

The package is intentionally small and readable:
    README_FIRST.md
    code/vision/            course code + author code + runs scripts
    report/vision_report.docx
    docs/                    reproduce / evidence / licenses / audit / coverage
    manifest/                file list and SHA256
    verify_package.py

Usage (from workspace root, multimedia-vision env):
    python -s vision/scripts/package_vision_submission.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # vision/
STAGE = ROOT / "submission" / "package-20261031"
ZIP = ROOT / "submission" / "2023302610_肖怀瑾_vision.zip"
REPORT = ROOT / "reports" / "delivery-20261028" / "vision_report.docx"

CODE_SCRIPTS = {
    "audit_interactions.py", "build_tvsum_mapping.py", "check_summary_playback.py",
    "environment_check.py", "export_interactions.py", "prepare_resources.ps1",
    "replay_image.py", "replay_models.py", "run.ps1", "verify_report.py",
    "verify_submission.py",
}
CODE_REPORTS = {
    "__init__.py", "add_references.py", "build_report_v2.py", "docx_helpers.py",
    "make_figures_v2.py", "report_appendices.py", "report_sections.py",
}
VENDOR_SKIP_DIRS = {".git", "__pycache__", "custom_data", "tests", "examples", "docs", ".github"}
VENDOR_SKIP_NAMES = {"requirements.txt", "setup.py", "test_groundtruth", "unlabeled-data-id"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def copy(src: Path, rel: str) -> dict:
    dst = STAGE / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {"path": rel, "size": dst.stat().st_size, "sha256": digest(dst)}


def keep_vendor(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & VENDOR_SKIP_DIRS:
        return False
    if rel.suffix.lower() == ".pickle" or rel.name in VENDOR_SKIP_NAMES:
        return False
    if "splits" in parts and rel.name != "tvsum.yml":
        return False
    if "anchor_based" in parts:
        return False
    return True


def collect_code() -> list[dict]:
    entries = []
    # top-level package files
    for name in ("__init__.py", "__main__.py", "README.md", "environment.yml",
                 "environment-lock-win-64.yml", "conda-explicit-win-64.txt"):
        src = ROOT / name
        if src.is_file():
            entries.append(copy(src, f"code/vision/{name}"))

    for dirname in ("common", "experiments", "configs", "manifests", "tests"):
        base = ROOT / dirname
        for src in sorted(base.rglob("*")):
            if not src.is_file() or "__pycache__" in src.parts:
                continue
            rel = src.relative_to(ROOT)
            entries.append(copy(src, f"code/vision/{rel.as_posix()}"))

    for src in sorted((ROOT / "scripts").glob("*")):
        if src.is_file() and src.name in CODE_SCRIPTS:
            entries.append(copy(src, f"code/vision/scripts/{src.name}"))

    for src in sorted((ROOT / "reports").glob("*.py")):
        if src.name in CODE_REPORTS:
            entries.append(copy(src, f"code/vision/reports/{src.name}"))

    vendor_base = ROOT / "vendor"
    for src in sorted(vendor_base.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(vendor_base)
        if not keep_vendor(rel):
            continue
        entries.append(copy(src, f"code/vision/vendor/{rel.as_posix()}"))
    return entries


def collect_docs() -> list[dict]:
    entries = []
    for src in sorted((ROOT / "package_docs").glob("*.md")):
        if src.name == "README_FIRST.md":
            continue
        entries.append(copy(src, f"docs/{src.name}"))
    audit = ROOT / "reports" / "INTERACTION_AUDIT.md"
    entries.append(copy(audit, "docs/INTERACTION_AUDIT.md"))
    entries.append(copy(ROOT / "package_docs" / "README_FIRST.md", "README_FIRST.md"))
    entries.append(copy(ROOT / "package_docs" / "verify_package.py", "verify_package.py"))
    return entries


def main() -> None:
    if not REPORT.is_file():
        raise FileNotFoundError(f"missing final report: {REPORT}")
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    files = collect_code()
    files += collect_docs()
    files.append(copy(REPORT, "report/vision_report.docx"))
    report_pdf = REPORT.with_suffix(".pdf")
    if report_pdf.is_file():
        files.append(copy(report_pdf, "report/vision_report.pdf"))
    else:
        raise FileNotFoundError(f"missing final PDF report: {report_pdf}")

    try:
        git_head = subprocess.run(
            ["git", "-C", str(ROOT.parent), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        git_head = "unknown"

    manifest = {
        "package": "2023302610_肖怀瑾_vision",
        "student": "肖怀瑾",
        "student_id": "2023302610",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "layout": "README_FIRST.md + code/vision + report + docs + manifest",
        "source_git_head": git_head,
        "report_sha256": digest(REPORT),
        "report_pdf_sha256": digest(report_pdf) if report_pdf.is_file() else None,
        "files": sorted(files, key=lambda x: x["path"]),
        "excluded": [
            "datasets", "weights", "features", "videos", "logs", "outputs",
            "submission zips", "conda environment", "drafts and preview images",
        ],
        "notes": [
            "Author code keeps LICENSE/README and provenance files.",
            "The final report is embedded; data are not included.",
            "Interaction appendix follows the saved visible records only.",
        ],
    }
    manifest_path = STAGE / "manifest" / "submission_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    checksum_lines = []
    for item in sorted(files, key=lambda x: x["path"]):
        checksum_lines.append(f'{item["sha256"]}  {item["path"]}')
    checksum_lines.append(f'{digest(manifest_path)}  manifest/submission_manifest.json')
    (STAGE / "manifest" / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n",
                                                         encoding="utf-8")

    ZIP.parent.mkdir(parents=True, exist_ok=True)
    tmp = ZIP.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(STAGE).as_posix())
    tmp.replace(ZIP)
    print(f"[done] {ZIP}")
    print(f"  files={len(files) + 2} size={ZIP.stat().st_size / 1e6:.2f} MB")
    print(f"  report_sha256={manifest['report_sha256']}")


if __name__ == "__main__":
    main()
