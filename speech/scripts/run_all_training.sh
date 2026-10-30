#!/usr/bin/env bash
# 一次跑完基线 + 三组消融的训练与评估（单 GPU 顺序执行）。
set -uo pipefail
KWS="C:/Users/ASUS/Desktop/多媒体技术/speech/kws_hw"
LOGS="C:/Users/ASUS/Desktop/多媒体技术/speech/logs"
DATA="E:/MultimediaCourseAssets/speech/data/processed"
PY="conda run -p D:/Anaconda3/envs/pytorch python -s"
cd "$KWS"

echo "=== [1/4] 基线：40 epoch + 增强（runs/） ==="
$PY train.py --data_dir "$DATA" --save_dir runs > "$LOGS/train-runs.log" 2>&1
tail -8 "$LOGS/train-runs.log"
$PY evaluate.py --data_dir "$DATA" --save_dir runs > "$LOGS/evaluate-runs.log" 2>&1
grep -E "测试集准确率|EER|FAR=" "$LOGS/evaluate-runs.log"

echo "=== [2/4] 消融：20 epoch + 增强（runs_20/） ==="
$PY train.py --data_dir "$DATA" --epochs 20 --save_dir runs_20 > "$LOGS/train-runs_20.log" 2>&1
tail -4 "$LOGS/train-runs_20.log"
$PY evaluate.py --data_dir "$DATA" --checkpoint runs_20/best.pt --save_dir runs_20 > "$LOGS/evaluate-runs_20.log" 2>&1
grep -E "测试集准确率|EER|FAR=" "$LOGS/evaluate-runs_20.log"

echo "=== [3/4] 消融：40 epoch 无增强（runs_noaug/） ==="
$PY train.py --data_dir "$DATA" --no_augment --save_dir runs_noaug > "$LOGS/train-runs_noaug.log" 2>&1
tail -4 "$LOGS/train-runs_noaug.log"
$PY evaluate.py --data_dir "$DATA" --checkpoint runs_noaug/best.pt --save_dir runs_noaug > "$LOGS/evaluate-runs_noaug.log" 2>&1
grep -E "测试集准确率|EER|FAR=" "$LOGS/evaluate-runs_noaug.log"

echo "=== [4/4] 消融：40 epoch + width 48（runs_w48/） ==="
$PY train.py --data_dir "$DATA" --width 48 --save_dir runs_w48 > "$LOGS/train-runs_w48.log" 2>&1
tail -4 "$LOGS/train-runs_w48.log"
$PY evaluate.py --data_dir "$DATA" --checkpoint runs_w48/best.pt --save_dir runs_w48 > "$LOGS/evaluate-runs_w48.log" 2>&1
grep -E "测试集准确率|EER|FAR=" "$LOGS/evaluate-runs_w48.log"

echo "=== 全部训练与评估完成 ==="
