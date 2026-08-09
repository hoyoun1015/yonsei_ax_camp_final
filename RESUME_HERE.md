# RESUME_HERE — 세션이 죽으면 이 파일부터 읽는다

최종 갱신: 2026-08-09 02:05

## 지금 상태 한 줄

D1(τ 사다리 실측) 진행 중. **G2·G6 통과**, ISO34 L3 완료.
남은 것은 **conformer 계열 τ_L3**와 **L2 측정** — 둘 다 밴드 C·D 확정에 필수.

## 2026-08-09 새벽에 컴퓨터가 죽은 이유와 대응 (중요)

**원인은 메모리다.** 구 러너 `dft_tau_probe.py`가 워커 4개 × `memory 6 GB`를
**16 GB 머신**에 요구했고, `timing_ladder`의 ISOL24 잡은 `memory 10 GB`였다.
스왑이 터지면서 머신 전체가 죽었다.

**부수 버그.** 구 러너는 완료 판정을 `sp.out` **파일 존재 여부**로 했다.
죽다 만 잡이 영구히 "완료"로 건너뛰어져 조용히 누락된다. ACONF 3개가 이 상태였다.

**대응 — `calibration/safe_dft.py`가 구 러너를 대체한다. 과제 범위는 그대로다.**

| | 구 러너 | safe_dft.py |
|---|---|---|
| 동시 잡 | 4 | **1 (직렬)** |
| 선언 메모리 | 6~10 GB | **3 GB** (`SAFE_MEM_GB`) |
| 완료 판정 | 파일 존재 | **`Psi4 exiting successfully` 마커** |
| 대형 분자 | in-core DF | **`scf_type disk_df`** (40원자↑ 자동) |
| 폭주 시 | 머신 사망 | **RSS 6 GB 초과 시 그 잡만 kill → 저메모리 재시도** |
| 디스크 | 무방비 | 여유 15 GB 밑이면 새 잡 시작 안 함 |
| 스크래치 | 방치 | 잡별 격리 + 종료 시 삭제 |

**실측 결과: 잡당 피크 RSS 2.2 GB, ACONF 20원자 기준 10초.** 안전하다.

### 두 개의 실측으로 확인한 함정

1. **`scf_subtype disk_df`는 없는 옵션이다.** psi4 1.11에서 out-of-core DF는
   `set scf_type disk_df` (subtype이 아니라 scf_type의 값).
2. **경로는 반드시 절대경로.** psi4는 잡 디렉터리를 cwd로 실행되므로
   `PSI_SCRATCH`에 상대경로를 넘기면 sp.out조차 만들지 않고 즉사한다.

## 재개 명령 — 언제 죽어도 그대로 다시 치면 이어서 돈다

완료된 잡은 건너뛰고 미완료분만 돈다. 중복 계산 없다.

```bash
cd "(진짜_이게_최종)/calibration"

# 서브셋 하나 (ACONF 자리에 서브셋명)
nohup env SAFE_MEM_GB=3 KILL_RSS_GB=6 PSI4_THREADS=8 \
  python3 safe_dft.py ../data/reference/gmtkn55 dft_work ACONF \
  > logs/ACONF_L3.log 2>&1 &

# 진행 확인
tail -f logs/ACONF_L3.log
```

`nohup`으로 띄우므로 **터미널이나 Claude 세션이 죽어도 계산은 계속된다.**

### ISOL24 (40~81원자) — 여기가 위험구간

`DISK_DF_ATOMS=40`이라 자동으로 out-of-core로 간다. 단독으로, 다른 잡 없이 돌린다.
D1 추정으로 47구조 ~8시간. 디스크 여유(현재 39 GB)를 먼저 확인할 것.

```bash
nohup env SAFE_MEM_GB=3 KILL_RSS_GB=5 PSI4_THREADS=8 MIN_DISK_GB=15 \
  python3 safe_dft.py ../data/reference/gmtkn55 dft_work ISOL24 \
  > logs/ISOL24_L3.log 2>&1 &
```

**절대 두 서브셋을 동시에 돌리지 않는다.** 그게 이번에 죽은 이유다.
직렬을 강제하려면 `chain_isol24.sh` 를 쓴다 — 앞 잡의 PID 가 사라질 때까지
기다렸다가 시작하고, 앞 잡이 MAE 까지 가지 못했으면 시작하지 않고 멈춘다.

```bash
nohup ./chain_isol24.sh <앞_잡_PID> > logs/chain.log 2>&1 &
```

## 서브셋 진행표

**D1 계산은 끝났다. 8개 서브셋 전량 L3 완료, 누락 0.**

| 서브셋 | τ_L1 | τ_L3 |
|---|---:|---:|
| ISOL24 | 12.190 | 5.562 |
| ISO34 | 6.902 | 1.949 |
| CDIE20 | 1.802 | 1.079 |
| PCONF21 | 1.757 | 0.537 |
| SCONF | 1.643 | 0.651 |
| ICONF | 1.629 | 0.328 |
| Amino20x4 | 0.954 | 0.235 |
| ACONF | 0.193 | 0.065 |

**G3·G4 전부 통과** — 밴드 C 36종(목표 25) · A+B 90종(50) · D 18종(10).
재계산: `python3 band_analysis.py ../data/reference/gmtkn55 tau_work dft_work`

**τ_L3가 서브셋마다 8~30배 다르다.** conformer 계열이 이성질화보다 훨씬 정확하다.
밴드를 절대 구간이 아니라 `τ_L3,subset < |ΔE_ref| ≤ τ_L1,subset`으로 정의해야 한다.
상세는 `docs/D1_실측결과.md` §8. 그 결과 **서브셋별 τ_L1**을 따로 내는 일이 새로 생겼다.

## 디스크 (2026-08-09 04:30에 겪은 것)

ISOL24가 14/46에서 **디스크 부족으로 가드에 걸려 멈췄다.** 머신은 죽지 않았고
데이터도 잃지 않았다 — 설계대로 동작한 것이다.

범인은 `/private/tmp`였다. 크래시한 psi4가 남긴 12 GB 스크래치와, 폐기한
단백질 안정성 후보의 다운로드 데이터가 든 이전 세션 스크래치패드 22 GB.
지워서 34 GB를 회수했다. **계산이 멈추면 먼저 `/private/tmp`를 본다.**

```bash
du -sh /private/tmp/* | sort -rh | head
```

## D1 게이트 현황 (`docs/D1_실측결과.md` §8)

| | 항목 | 상태 |
|---|---|---|
| G2 | DFT가 τ를 줄이는가 | 🟢 통과 — L1 6.902 → L3 1.949 (3.5배) |
| G6 | ZPVE·ΔE 일치 | 🟢 통과 |
| — | L2(def2-SVP)가 L1과 L3 사이인가 | 🔴 미측정 |
| — | conformer 계열 τ_L3 | 🔴 미측정 |
| G3·G4 | 밴드별 화학종 수 | 🔴 위 둘 대기 |
| — | API RPD 확인 | 🙋 **사용자만 가능** |

## git

문서 수정분과 `calibration/`·`figures/`가 **아직 커밋 안 됨**. 최근 커밋 `8f4fe36`.
계산이 한 서브셋 끝날 때마다 커밋해 두면 다음에 죽어도 손실이 없다.

## 잊지 말 것

- 주제·RQ 구성·불변조건은 `CLAUDE.md`. 임의로 바꾸지 않는다.
- τ와 라벨은 **동결 후 불변**. 결과를 본 뒤 고치지 않는다.
- 계산 규모를 줄여서 문제를 피하지 않는다. 실행 방식으로 푼다.
