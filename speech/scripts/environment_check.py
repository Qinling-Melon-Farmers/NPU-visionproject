"""语音部分环境核验脚本。

检查 D:\\Anaconda3\\envs\\pytorch 环境内:
    - Python / 依赖包版本（numpy、scipy、soundfile、scikit-learn、matplotlib、tqdm、torch）
    - CUDA 可用性与实际 GPU 张量运算
    - soundfile 真实 wav 读写（NumPy ABI 冒烟测试）
    - matplotlib Agg 出图

用法:
    conda run -p D:/Anaconda3/envs/pytorch python -s speech/scripts/environment_check.py

缺少依赖时以退出码 2 结束，并在输出末尾列出缺失项。
"""

import importlib
import json
import sys
import tempfile
from pathlib import Path

results = {}
missing = []


def try_import(name):
    try:
        return importlib.import_module(name), None
    except Exception as exc:  # noqa: BLE001 - 记录所有导入失败
        return None, f"{type(exc).__name__}: {exc}"


results["python"] = sys.version.split()[0]
results["executable"] = sys.executable

for name in ["numpy", "scipy", "soundfile", "sklearn", "matplotlib", "tqdm", "torch"]:
    mod, err = try_import(name)
    if mod is None:
        results[name] = f"MISSING ({err})"
        missing.append(name)
    else:
        results[name] = getattr(mod, "__version__", "unknown")

# torch / GPU：import 成功不代表 GPU 能算，这里做一次真实矩阵乘
if "torch" not in missing:
    try:
        import torch

        results["torch.version.cuda"] = str(torch.version.cuda)
        results["cuda.is_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            results["gpu"] = torch.cuda.get_device_name(0)
            x = torch.randn(1024, 1024, device="cuda")
            _ = float((x @ x).sum().item())
            results["gpu_matmul_ok"] = True
    except Exception as exc:  # noqa: BLE001
        results["gpu_check_error"] = f"{type(exc).__name__}: {exc}"

# soundfile 真实写 + 读一条 wav（ABI / libsndfile 冒烟）
if "soundfile" not in missing and "numpy" not in missing:
    try:
        import numpy as np
        import soundfile as sf

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "probe.wav"
            t = np.sin(2.0 * np.pi * 440.0 * np.arange(16000) / 16000.0)
            sf.write(str(p), t.astype("float32"), 16000)
            wav, sr = sf.read(str(p), dtype="float32")
            results["soundfile_io"] = f"ok sr={sr} n={len(wav)}"
    except Exception as exc:  # noqa: BLE001
        results["soundfile_io"] = f"FAIL {type(exc).__name__}: {exc}"

# matplotlib Agg 出图冒烟
if "matplotlib" not in missing:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "probe.png"
            fig, ax = plt.subplots()
            ax.plot([0, 1], [0, 1])
            fig.savefig(p)
            plt.close(fig)
        results["matplotlib_png"] = "ok"
    except Exception as exc:  # noqa: BLE001
        results["matplotlib_png"] = f"FAIL {type(exc).__name__}: {exc}"

print(json.dumps(results, ensure_ascii=False, indent=2))
if missing:
    print("\n[缺少依赖] " + ", ".join(missing))
    sys.exit(2)
print("\n[OK] 环境核验通过")
