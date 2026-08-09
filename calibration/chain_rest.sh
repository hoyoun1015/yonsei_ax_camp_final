#!/bin/zsh
# ISOL24 다음에 남은 서브셋들의 τ_L3 를 순차로 잰다.
#
# 이 넷이 밴드 C·D 의 공급원이고, G3 게이트(밴드 C 화학종 25종 이상, 15종
# 미만이면 폐기)를 판정하려면 반드시 필요하다. 전부 작은 분자라 ISOL24 와
# 달리 빠르고 디스크도 거의 안 쓴다.
#
# 서브셋 사이에도 직렬을 지킨다 — 동시에 돌리는 것이 2026-08-09 새벽에
# 머신이 죽은 이유다.

set -u
cd "${0:A:h}"

WAIT_PID="${1:?앞 잡의 PID 를 인자로 준다}"
SUBSETS=(ICONF PCONF21 SCONF CDIE20)

echo "[$(date '+%H:%M:%S')] ISOL24 (pid $WAIT_PID) 종료 대기"
while kill -0 "$WAIT_PID" 2>/dev/null; do
  sleep 30
done
echo "[$(date '+%H:%M:%S')] ISOL24 종료 확인"

for sub in $SUBSETS; do
  echo "[$(date '+%H:%M:%S')] $sub 시작"
  env SAFE_MEM_GB=3 KILL_RSS_GB=5 PSI4_THREADS=8 MIN_DISK_GB=12 DISK_DF_ATOMS=40 \
    python3 safe_dft.py ../data/reference/gmtkn55 dft_work "$sub" \
    > "logs/${sub}_L3.log" 2>&1
  if grep -q "MAE" "logs/${sub}_L3.log" 2>/dev/null; then
    echo "[$(date '+%H:%M:%S')] $sub 완료 — $(grep 'MAE' logs/${sub}_L3.log | head -1)"
  else
    echo "[$(date '+%H:%M:%S')] $sub 이 MAE 까지 가지 못했다. 로그를 확인할 것."
  fi
done

echo "[$(date '+%H:%M:%S')] 전 서브셋 종료"
