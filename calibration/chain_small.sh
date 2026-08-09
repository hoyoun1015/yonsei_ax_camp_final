#!/bin/zsh
# 남은 소형 서브셋 3종. 최대 43원자라 ISOL24(81원자)와 달리 스크래치가 작다.
# 그래서 디스크 하한을 12 GB 에서 5 GB 로 낮춘다 — 12 GB 는 ISOL24 기준이라
# 이 크기에는 과보수적이고, 실제로 그 하한 때문에 셋 다 시작조차 못 했다.
set -u
cd "${0:A:h}"
for sub in PCONF21 SCONF CDIE20; do
  echo "[$(date '+%H:%M:%S')] $sub 시작 (여유 $(df -g / | tail -1 | awk '{print $4}') GB)"
  env SAFE_MEM_GB=3 KILL_RSS_GB=5 PSI4_THREADS=8 MIN_DISK_GB=5 DISK_DF_ATOMS=40 \
    python3 safe_dft.py ../data/reference/gmtkn55 dft_work "$sub" \
    > "logs/${sub}_L3.log" 2>&1
  echo "[$(date '+%H:%M:%S')] $sub — $(grep -E 'MAE|누락' logs/${sub}_L3.log | tr '\n' ' ')"
done
echo "[$(date '+%H:%M:%S')] 종료"
