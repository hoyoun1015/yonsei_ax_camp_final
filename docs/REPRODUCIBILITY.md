# 재현 안내

이 문서는 [README](../README.md)에서 분리한 실행·재현 정보다. 연구 내용 설명은 README에
있고, 여기에는 **환경 · 명령 · 코드 구조**만 둔다.

재현은 세 층위로 나뉘며, 아래로 갈수록 비용이 크다.

| 층위 | 무엇 | 비용 | LLM/API |
|---|---|---|---|
| **1. 검증** | 동결·LOCK 무결성 확인, 그림·표 재생성 | 초 단위 | 0회 |
| **2. 계산 재현** | GMTKN55 구조로 xTB·DFT를 다시 돌린다 | 수 시간 | 0회 |
| **3. 에이전트 재실행** | 3-에이전트 루프를 다시 돌린다 | 수 일 (quota) | 수백 회 |

---

## 1. 검증 — LLM/API 0회

가장 먼저 이것부터 돌리면 된다. 저장소에 들어 있는 동결 산출물만 읽는다.

```bash
# 동결 해시·과제 커버리지·원장 무결성 23항목
python3 src/vccl/scoring/aggregate.py --check

# LOCK 된 표·그림 산출물 sha256 대조
python3 tables/lock_manifest.py --verify
```

`--check` 가 대조하는 것: 동결본 3종의 해시가 실행 시점과 같은지, 92과제가 조건별로
빠짐없이 한 번씩 실행됐는지, 원장(`calls.jsonl`) 줄 수가 요약 수와 맞는지, τ 블록이
의도한 단계에만 들어갔는지, 과대해석 정의가 일관되는지.

### 테스트

`pytest` 없이 표준 라이브러리만으로 돌린다 (테스트 49건).

```bash
python3 - <<'PY'
import sys, traceback, importlib.util; from pathlib import Path
sys.path.insert(0, "src"); ok = fail = 0
for f in sorted(Path("tests").glob("test_*.py")):
    s = importlib.util.spec_from_file_location(f.stem, f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    for n in [n for n in dir(m) if n.startswith("test_")]:
        try: getattr(m, n)(); ok += 1
        except Exception: fail += 1; print(f"🔴 {f.name}::{n}"); traceback.print_exc()
print(f"{'🟢' if not fail else '🔴'} 통과 {ok} · 실패 {fail}")
PY
```

### 그림과 표 재생성

논문 Figure·Table 은 **동결 산출물에서 스크립트로만** 만든다. 수치를 손으로 옮겨
적지 않는다.

```bash
# 1) 동결본 → plot-ready 데이터 (assertion 30건 포함)
python3 src/vccl/scoring/plot_data.py

# 2) plot-ready 데이터 → figures/draft/ F0~F4
python3 figures/make_figures.py

# 표도 같은 방식
python3 src/vccl/scoring/table_data.py
python3 tables/make_tables.py          # Main Table 1
python3 tables/make_supp_tables.py     # Supplementary S1~S8
```

| | |
|---|---|
| 그림 데이터 | `src/vccl/scoring/plot_data.py` → `results/plot_data/` |
| 그림 | `figures/make_figures.py` → `figures/draft/` |
| 그림 설명문 | `figures/captions.md` |
| 표 데이터 | `src/vccl/scoring/table_data.py` → `results/table_data/` |
| 표 | `tables/make_tables.py` · `tables/make_supp_tables.py` |
| 설계 근거 | `paper_logic/figure_design.md` · `paper_logic/table_design.md` |

**`make_figures.py` 는 `results/plot_data/` 외의 어떤 것도 읽지 않는다.** 수치를
바꾸려면 `plot_data.py` 를 고쳐야 하고, 그때 assertion 이 정정값 재현을 검증한다.
비용 축은 psi4 실측 wall time 전용이다 (`DECISION_LOG` 2026-08-14 (1) 정정 ②).

> ⚠️ **재생성해도 PDF 해시는 달라진다.** matplotlib 이 `/CreationDate` 를 파일에
> 박기 때문이다. **내용 동일성은 PNG 로 확인한다.**

> 🔒 Figure F0~F4 · Main Table 1 · Supplementary S1~S8 은 LOCK 상태다. 재생성은
> 동일성 확인용이며, 수치·문구 변경은 amendment 절차를 거친다.

---

## 2. 계산 재현 — LLM/API 0회, 수 시간

### 참조 데이터

GMTKN55 는 저장소에 넣지 않는다 (공개 저장소이므로). 받아서 쓴다.

```bash
bash scripts/fetch_reference.sh     # → data/reference/gmtkn55/
```

### 필요한 것

- Python 3 · [xTB](https://github.com/grimme-lab/xtb) (GFN2) · [psi4](https://psicode.org/)
- RAM 16 GB 이상 권장
- 331 구조 전량 DFT 재계산은 **약 11시간**이 걸린다.
  `calibration/dft_work/` 의 에너지 캐시를 보존하는 이유다.

### 실행

```bash
cd calibration

# τ_L3 — 서브셋 하나. 중단돼도 같은 명령으로 재개하면 완료분을 건너뛴다
nohup env SAFE_MEM_GB=3 KILL_RSS_GB=5 PSI4_THREADS=8 \
  python3 safe_dft.py ../data/reference/gmtkn55 dft_work ISO34 \
  > logs/ISO34_L3.log 2>&1 &

# τ_L1 (xTB) 실측
python3 tau_probe.py ../data/reference/gmtkn55 tau_work

# 밴드 층화 + 화학종 클러스터링 + 게이트 판정
python3 band_analysis.py ../data/reference/gmtkn55 tau_work dft_work
```

> ⚠️ **두 서브셋을 동시에 돌리지 않는다.** RAM 16 GB에서 동시 실행이 머신을 죽였다
> (2026-08-09 · `DECISION_LOG` 참조). `safe_dft.py` 가 직렬·저메모리·재개 가능으로
> 설계된 이유이며, `chain_*.sh` 가 순차 실행을 강제한다.
> **DFT 를 다시 돌릴 일이 생기면 반드시 `safe_dft.py` 를 쓴다.**

---

## 3. 에이전트 재실행 — LLM/API 수백 회

본실행은 92과제 × 2조건에 **LLM 911호출**이 들어갔고, 주간 quota 때문에 3배치로
나눠 실행했다. 재실행에는 백엔드 자격증명이 필요하다 (`env_local.json`, 저장소 제외).

```bash
python3 src/vccl/agents/smoke.py                  # 소규모 연결 확인
python3 src/vccl/agents/main_run.py --help        # 본실행 (chunk 분할·재개)
python3 src/vccl/agents/challenge.py --help       # 식별 챌린지
python3 src/vccl/agents/replication.py --help     # cross-model replication
python3 src/vccl/agents/batch_status.py           # 실행 중 감시 (로컬 파일만 읽는다)
```

> 🔒 **동결 후 불변.** 재실행하더라도 τ·라벨·과제 정의·프롬프트는 수정하지 않는다.
> 러너는 매 배치마다 동결 해시를 대조하고, 어긋나면 실행을 중단한다.
> 변경이 필요하면 구현 **전에** `DECISION_LOG` 에 기록한다.

---

## 코드 구조

```
src/vccl/
  tasks/       과제 생성·층화·프롬프트·동결
    gmtkn.py            GMTKN55 파싱
    pairs.py            구조 쌍 구성과 반응 유형 판정
    prompts.py          에이전트 프롬프트 (τ 블록 포함/제외)
    freeze.py           Stage A 동결 (τ·라벨·밴드)
    freeze_stage_b.py   Stage B 동결 (실험 규모·실행 규약)
    execution_order.py  실행 순서 동결
  executor/    계산 실행층 — 넘겨받은 명세만 수행한다
    cached.py           xTB·psi4 실행과 에너지 캐시
  agents/      3-에이전트 루프와 실행 러너
    loop.py             PI · Computational Chemist · Skeptical Reviewer 루프
    schemas.py          응답 스키마
    backend.py          LLM 백엔드
    r0.py               규칙 기준선 (LLM 0회)
    l0.py               L0 프로브 (계산 없이 사전지식만)
    main_run.py         본실행 배치
    challenge.py challenge_secondary.py   식별 챌린지
    replication.py      cross-model replication
  scoring/     채점·집계·검증
    labels.py           라벨 유도 (기계적)
    aggregate.py        집계 + 무결성 점검 (--check)
    headroom.py         고정 비교 정책 대비 분석
    plot_data.py table_data.py   그림·표용 데이터 생성

calibration/   τ 실측과 밴드 층화 (설계 단계)
  safe_dft.py         DFT 단일점 러너 — 직렬·메모리 가드·재개 가능
  tau_probe.py        xTB 방법오차 실측 (L1)
  band_analysis.py    밴드 층화 + 화학종 클러스터링 + 게이트 판정
  tau_distribution.py 오차 분포와 문턱 민감도
  chain_*.sh          서브셋 순차 실행 (동시 실행 금지를 강제)
  dft_work/           에너지 캐시 — 재계산 11시간이므로 보존한다

data/tasks/    동결본 (frozen_rules_v1 · frozen_stage_b_v1 · execution_order_v1)
experiments/   실행 산출물과 원장 (calls.jsonl)
results/       집계 결과와 그림·표용 데이터
figures/ tables/   LOCK 된 논문 그림·표와 생성 스크립트
paper_logic/   주장 사슬 · 주장–증거 대응표 · 그림/표 설계
docs/          설계 문서 · 실측 결과 · DECISION_LOG · 사고 기록
tests/         라벨·쌍 구성·짝지은 검정·식별 채점 테스트 (49건)
```

---

## 저장소에 없는 것

| | 이유 |
|---|---|
| `data/reference/gmtkn55/` | 참조 데이터. `scripts/fetch_reference.sh` 로 받는다 |
| `env_local.json` · `.env` | 백엔드 자격증명 |
| `calibration/tau_work/` · 타이밍 프로브 스크래치 | 재현 가능하고 용량만 크다 (65 MB) |
| 일부 pilot·smoke·L0 `calls.jsonl` | 프롬프트 전문이라 용량이 크다. 요약만 커밋한다 |

본실행·식별 챌린지·replication 의 원장(`calls.jsonl`)은 provenance 이므로 **전량
커밋되어 있다.**
