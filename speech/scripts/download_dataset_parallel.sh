#!/usr/bin/env bash
# Speech Commands v0.01 官方数据多连接分段下载。
# 单连接到 download.tensorflow.org 仅 ~66 KB/s，多路 Range 并发可显著提速。
# 支持断点续跑：已完成的分段用 .done 标记跳过。
set -uo pipefail

URL="http://download.tensorflow.org/data/speech_commands_v0.01.tar.gz"
SIZE=1489096277
MD5_EXPECT="3cd23799cb2bbdec517f1cc028f8d43c"
N=32
CONCURRENCY=16
OUT_DIR="E:/MultimediaCourseAssets/speech/data"
PART_DIR="$OUT_DIR/parts"
FINAL="$OUT_DIR/speech_commands_v0.01.tar.gz"

mkdir -p "$PART_DIR"
CHUNK=$(( (SIZE + N - 1) / N ))

for i in $(seq 0 $((N - 1))); do
  idx=$(printf "%02d" "$i")
  [ -f "$PART_DIR/part_$idx.done" ] && continue
  start=$(( i * CHUNK ))
  end=$(( start + CHUNK - 1 ))
  [ "$end" -ge "$SIZE" ] && end=$(( SIZE - 1 ))
  (
    if curl -s --retry 5 --retry-delay 3 --max-time 3600 \
         -r "$start-$end" -o "$PART_DIR/part_$idx" "$URL"; then
      touch "$PART_DIR/part_$idx.done"
      echo "[done] part $idx $(stat -c%s "$PART_DIR/part_$idx") bytes"
    else
      echo "[fail] part $idx"
    fi
  ) &
  while [ "$(jobs -rp | wc -l)" -ge "$CONCURRENCY" ]; do sleep 2; done
done
wait

cat $(for i in $(seq 0 $((N - 1))); do printf "%s/part_%02d " "$PART_DIR" "$i"; done) > "$FINAL"
ACTUAL=$(stat -c%s "$FINAL")
echo "expected=$SIZE actual=$ACTUAL"
if [ "$ACTUAL" -ne "$SIZE" ]; then
  echo "[error] 文件大小不符，分段保留在 $PART_DIR 以便续跑"
  exit 1
fi
rm -rf "$PART_DIR"
echo "[校验] md5 期望 $MD5_EXPECT"
md5sum "$FINAL"
