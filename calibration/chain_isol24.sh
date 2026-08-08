#!/bin/zsh
# Amino20x4 가 끝나면 ISOL24 를 이어서 돌린다.
#
# 두 서브셋을 동시에 돌리지 않는 것이 핵심이다 — 그게 2026-08-09 새벽에
# 머신이 죽은 이유다. 앞 잡의 PID 가 사라질 때까지 기다렸다가 시작한다.
#
# ISOL24 는 40~81 원자라 safe_dft.py 가 전부 scf_type disk_df 로 돌린다.
# D1 추정으로 47구조 ~8시간. nohup 으로 띄우므로 터미널이나 세션이 죽어도
# 계속되고, 중간에 죽어도 같은 명령을 다시 치면 완료분은 건너뛴다.

set -u
cd "${0:A:h}"

WAIT_PID="${1:?앞 잡의 PID 를 인자로 준다}"

echo "[$(date '+%H:%M:%S')] Amino20x4 (pid $WAIT_PID) 종료 대기"
while kill -0 "$WAIT_PID" 2>/dev/null; do
  sleep 30
done
echo "[$(date '+%H:%M:%S')] Amino20x4 종료 확인"

# 앞 잡이 정말 끝까지 갔는지 로그로 확인한다. 중간에 죽었으면 ISOL24 로
# 넘어가기 전에 사람이 봐야 하므로 여기서 멈춘다.
if ! grep -q "MAE" logs/Amino20x4_L3.log 2>/dev/null; then
  echo "[$(date '+%H:%M:%S')] 중단: Amino20x4 가 MAE 까지 가지 못했다. ISOL24 를 시작하지 않는다."
  echo "  logs/Amino20x4_L3.log 를 확인하고, 같은 명령으로 재개한 뒤 다시 체인을 걸 것."
  exit 1
fi

echo "[$(date '+%H:%M:%S')] ISOL24 시작 (47구조, 40~81원자, disk_df, ~8시간 예상)"
env SAFE_MEM_GB=3 KILL_RSS_GB=5 PSI4_THREADS=8 MIN_DISK_GB=15 DISK_DF_ATOMS=40 \
  python3 safe_dft.py ../data/reference/gmtkn55 dft_work ISOL24 \
  > logs/ISOL24_L3.log 2>&1
echo "[$(date '+%H:%M:%S')] ISOL24 종료 (exit $?)"
