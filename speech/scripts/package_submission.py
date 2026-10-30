"""生成课程提交包 zip（指导文档 10.4 节格式）。

zip 内容：
    code/            教师代码 + demo_long.wav（本仓库 speech/kws_hw 下的代码文件）
    runs/            best.pt + 结果图 + metrics.json 等小型证据
    report.pdf       实验报告 PDF
    report.docx      实验报告 Word 版

不包含 data/、conda 环境与任何大文件。用法（在仓库根目录）:
    conda run -p D:/Anaconda3/envs/pytorch python -s speech/scripts/package_submission.py
"""

import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CODE_FILES = [
    "README.md", "requirements.txt", "features.py", "prepare_data.py",
    "model.py", "train.py", "evaluate.py", "infer.py", "detect.py",
    "demo_long.wav",
]
RUNS_FILES = [
    "best.pt", "confusion_matrix.png", "det_curve.png", "training_curves.png",
    "score_hist.png", "metrics.json", "classification_report.txt",
    "misclassified.txt", "history.json",
]


def sha256_of(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs_dir", type=str, default=str(ROOT / "kws_hw" / "runs"))
    parser.add_argument("--report_pdf", type=str,
                        default=str(ROOT / "reports" / "delivery-20261031" / "kws_report.pdf"))
    parser.add_argument("--report_docx", type=str,
                        default=str(ROOT / "reports" / "delivery-20261031" / "kws_report.docx"))
    parser.add_argument("--out", type=str,
                        default=str(ROOT / "submission" / "2023302610_肖怀瑾_kws.zip"))
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    report_pdf = Path(args.report_pdf)
    report_docx = Path(args.report_docx)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    entries = [("code/" + name, ROOT / "kws_hw" / name) for name in CODE_FILES]
    entries += [("runs/" + name, runs_dir / name) for name in RUNS_FILES]
    entries.append(("report.pdf", report_pdf))
    entries.append(("report.docx", report_docx))

    missing = [arc for arc, path in entries if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少待打包文件: " + ", ".join(missing))

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for arc, path in entries:
            zf.write(path, arc)

    with zipfile.ZipFile(out, "r") as zf:
        names = zf.namelist()
        bad = zf.testzip()
    print(f"[完成] {out}")
    print(f"  文件数 {len(names)}，损坏检测: {'无' if bad is None else bad}")
    print(f"  大小 {out.stat().st_size / 1e6:.2f} MB，SHA256 {sha256_of(out)}")


if __name__ == "__main__":
    main()
