#!/bin/zsh
# L2 = B3LYP-D3(BJ)/def2-SVP 단일점. 8개 서브셋 전량.
#
# **왜 이것이 필요한가.** 에스컬레이션 밴드가 τ₃ < |ΔE_ref| ≤ τ₂ 로 정의되고
# τ₂ 는 L2 기준이다. 지금까지는 τ₂ 자리에 τ_L1(xTB)을 대입한 잠정값을 썼다.
# L2 가 나오면 밴드 C 가 확정되고, 그 위에서 완충대와 과제셋을 정할 수 있다.
#
# def2-SVP 는 def2-TZVP 보다 기저가 작아 훨씬 싸다 (TZVP 전량이 ~11시간이었다).
# 작은 서브셋부터 돌려서 결과를 일찍 보고, 가장 무거운 ISOL24 를 마지막에 둔다.
#
# 결과는 dft_work/<서브셋>/b3lyp-d3bj_def2-SVP/ 에 들어가므로 TZVP 캐시와
# 충돌하지 않는다. 중단돼도 같은 명령으로 재개하면 완료분을 건너뛴다.

set -u
cd "${0:A:h}"

# 구조 수가 적은 것부터. ISOL24(40~81원자)가 전체 비용을 지배하므로 맨 뒤.
SUBSETS=(ACONF SCONF PCONF21 ICONF CDIE20 ISO34 Amino20x4 ISOL24)

echo "[$(date '+%H:%M:%S')] L2 (def2-SVP) 시작 — 8개 서브셋, 디스크 여유 $(df -g / | tail -1 | awk '{print $4}') GB"

for sub in $SUBSETS; do
  echo "[$(date '+%H:%M:%S')] $sub 시작"
  env SAFE_MEM_GB=3 KILL_RSS_GB=5 PSI4_THREADS=8 MIN_DISK_GB=10 DISK_DF_ATOMS=40 \
    python3 safe_dft.py ../data/reference/gmtkn55 dft_work "$sub" def2-SVP \
    > "logs/${sub}_L2.log" 2>&1
  line=$(grep -E 'MAE' "logs/${sub}_L2.log" | head -1)
  miss=$(grep -E '반응 .*누락' "logs/${sub}_L2.log" | head -1)
  echo "[$(date '+%H:%M:%S')] $sub — ${line:-실패} · ${miss:-}"
done

echo "[$(date '+%H:%M:%S')] L2 전량 종료"
