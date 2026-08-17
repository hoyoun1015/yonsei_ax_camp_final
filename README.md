# Virtual Computational Chemistry Lab

**자율 계산화학 연구 에이전트** — 자연어 화학 가설을 해석하고, 계산 실험을 설계·실행하고,
결과가 불충분하면 후속 계산까지 결정하여 가설을 지지·기각·**판단보류**한다.

> **한 문장으로.** "A가 B보다 안정하다"는 화학 가설을 AI가 직접 계산해서 검증하게 만들되,
> **AI가 자기 계산의 오차보다 작은 차이를 놓고 단정하는지**를 잡아내는 것이 이 연구의 핵심이다.
> 그 오차를 실제 계산 331건으로 측정했고, 오차가 문제 종류에 따라 8배까지 다르다는 것을 확인했다.

마감 2026-09-02 · 시작 2026-08-08 · 단독 · Apple M4, GPU 없음, 웻랩 없음

---

## 이 연구가 다른 지점

자연어에서 양자화학 계산으로 가는 파이프라인은 이미 여러 시스템이 한다.
**이 연구가 구별되는 것은 그 판단을 무엇으로 채점하느냐다.**

에이전트가 "A가 B보다 안정하다"고 결론 내렸을 때, 그 판단이 옳은지를 사람이나 LLM이
평가하지 않는다. **자기가 쓴 계산 방법의 오차(τ)보다 작은 차이를 놓고 단정했는가**로
기계적으로 판정한다. τ는 GMTKN55 참조값 대비 실측한다.

연구 질문은 RQ1(가설 해석) · RQ2(실험 설계) · RQ3(적응적 추론) · RQ4(과대해석 억제)이고,
**RQ3·RQ4에 채점 기준을 다는 것**이 방법론적 핵심이다.

---

## 진행 상황

**실험은 끝났다. 남은 것은 본문 집필과 replication 잔여 2 chunk다.**
자세한 현재 상태는 [RESUME_HERE.md](RESUME_HERE.md), 모든 결정·정정 이력은
[docs/DECISION_LOG.md](docs/DECISION_LOG.md)를 본다.

| 단계 | 상태 |
|---|---|
| 평가 인프라 (τ 사다리 · 밴드 · 규칙 기준선) | 🟢 완료 (2026-08-09) |
| 본실행 N=92 (V · V−τ) | 🟢 완료 · FAILED 0/92 · LLM 911호출 |
| 식별 챌린지 primary 24 / secondary 94 | 🟢 24/24 · 94/94 (secondary는 post-hoc) |
| Figure F0~F4 · Main Table 1 · Supplementary S1~S8 | 🔒 **LOCK** |
| cross-model replication (sonnet · V 단독 · N=30) | 🟡 16/30 · chunk 3·4 남음 |
| 본문 집필 | 🔲 미시작 |

### 본실행 결과 (N=92 · 동일 과제 짝지음)

| 지표 | R0 | V | V−τ |
|---|---:|---:|---:|
| 근거가 충분한 결론 | 56/92 | **74/92** | 54/92 |
| 과대해석 (사전등록 주 지표) | 0 | **0/92** | 3/92 |
| 과도한 신중 | — | **0/92** | 20/92 |
| 계산 비용 (ALL_L3 대비 · psi4 실측) | 0.02% | **30.6%** | 139.3% |

정확 McNemar (paired) — **V 대 V−τ p = 1.1×10⁻⁵** · V 대 R0 p = 9.1×10⁻⁴.

⚠️ **사전등록 주 지표(과대해석)는 유의하지 않았다** (0:3 · p = 0.25).
τ가 과대해석을 줄였다고 쓰지 않는다. 실제 차이는 근거가 충분한 결론 ·
과도한 신중 · Band C에서 나왔다. 해석 시 지킬 규칙 전문은 RESUME_HERE.md에 있다.

### τ 사다리 — 8개 서브셋 331구조 전량 실측, 누락 0

| 반응 유형 | 판정 방법 | 반응 | τ_L1 (xTB) | τ_L3 (B3LYP/TZVP) | 사다리 |
|---|---|---:|---:|---:|---:|
| conformer | 결합 그래프 동일 | 167 | 1.213 | 0.405 | 3.0× |
| 구조 이성질체 | 분자식 같고 그래프 다름 | 57 | 9.036 | 3.407 | 2.7× |

단위 kcal/mol. **계산 수준을 올리면 방법오차가 줄어든다** — RQ3(에스컬레이션)의 전제가
8개 서브셋 전부에서 성립한다. 그리고 **τ는 반응 유형에 따라 8배 다르다.**

### 게이트 판정

| 게이트 | 기준 | 실측 | |
|---|---|---:|---|
| **G3** | 밴드 C 화학종 ≥ 25 (**15 미만이면 폐기**) | **33종** | 🟢 |
| G4 | 밴드 A+B ≥ 50종 · D ≥ 10종 | 85 · 17종 | 🟢 |
| G2 | DFT가 τ를 줄이는가 | 1.7~5.0× | 🟢 |
| G6 | ZPVE·ΔE 일치 | — | 🟢 |

G3가 이 연구의 생사를 갈랐다. 밴드 C(`τ_L3 < |ΔE_ref| ≤ τ_L1`)가 비면
에이전트가 규칙 기준선을 이길 구조적 경로가 없다.

### 남은 일

- 🔲 **cross-model replication chunk 3·4** (14과제) — Claude 주간 quota 회복 후.
  **30과제 전량 완료 전에는 성능을 열람하지 않는다** (사전등록).
- 🔲 **본문 집필**
- 🔲 선행연구 재확인 · 시스템 이름 확정 (VirtualLab_CC와 충돌 회피)

---

## 문서

| 문서 | 내용 |
|---|---|
| [**작업보고서_2026-08-09.pdf**](docs/작업보고서_2026-08-09.pdf) | **전체 현황 보고서 (10쪽)** — 한 것·결과·정정·필요한 것·구조 추천 |
| [D1_실측결과.md](docs/D1_실측결과.md) | τ 사다리 실측 전문, 게이트 판정, 정정 사항 |
| [기획안_v3.md](docs/기획안_v3.md) | 연구 설계 |
| [구현_설계.md](docs/구현_설계.md) | 3층 구조, 스택, 구현 순서, LLM 예산 |
| [검증된_사실.md](docs/검증된_사실.md) | 직접 확인한 수치와 미확인 항목 |
| [DECISION_LOG.md](docs/DECISION_LOG.md) | **모든 결정·정정 이력. 과거 상태는 여기서 본다** |
| [RESUME_HERE.md](RESUME_HERE.md) | **현재 상태 · 재현 명령 · 해석 시 지킬 규칙** |
| [paper_logic/new_fol.md](paper_logic/new_fol.md) | 주장 사슬 NEW-FOL-1~18 + 근거·금지 표현 |
| [paper_logic/claim_evidence_map.md](paper_logic/claim_evidence_map.md) | 주장–증거 대응표 + 한계 L1~L8 |
| [tables/supplementary/LOCK_MANIFEST.md](tables/supplementary/LOCK_MANIFEST.md) | S1~S8 LOCK 해시 대장 |

## 그림

| | |
|---|---|
| [tau_distribution.png](figures/tau_distribution.png) | 방법오차 분포 — τ(평균)가 꼬리에 끌리는 모양 |
| [계보도_v1.pdf](docs/계보도_v1.pdf) | 연구 계보 |

---

## 코드

```
calibration/
  safe_dft.py         DFT 단일점 러너 — 직렬 실행, 메모리·디스크 가드, 재개 가능
  tau_probe.py        xTB 방법오차 실측 (L1)
  band_analysis.py    밴드 층화 + 화학종 클러스터링 + 게이트 판정
  tau_distribution.py 오차 분포와 문턱 민감도 분석
  chain_*.sh          서브셋 순차 실행 (동시 실행 금지를 강제)
  dft_work/           에너지 캐시 — 331구조 재계산은 11시간이므로 보존한다
docs/                 설계 문서, 실측 결과, 보고서, DECISION_LOG
data/reference/       GMTKN55 (scripts/fetch_reference.sh 로 받는다)
src/vccl/
  tasks/              과제 생성·층화·프롬프트·실행 순서 동결
  executor/           계산 실행층 (xTB · psi4)
  agents/             3-에이전트 루프 · 본실행 · 식별 챌린지 · replication
  scoring/            집계·무결성 점검·headroom·plot/table 데이터 생성
experiments/          실행 산출물과 원장 (calls.jsonl)
paper_logic/          주장 사슬(FOL) · 주장–증거 대응표 · Figure/Table 설계
figures/  tables/     LOCK 된 논문 그림·표와 생성 스크립트
```

### 계산 재현

```bash
cd calibration
# τ_L3 — 서브셋 하나. 중단돼도 같은 명령으로 재개하면 완료분을 건너뛴다
nohup env SAFE_MEM_GB=3 KILL_RSS_GB=5 PSI4_THREADS=8 \
  python3 safe_dft.py ../data/reference/gmtkn55 dft_work ISO34 \
  > logs/ISO34_L3.log 2>&1 &

# 밴드 분포와 게이트 판정
python3 band_analysis.py ../data/reference/gmtkn55 tau_work dft_work
```

**두 서브셋을 동시에 돌리지 않는다.** RAM 16 GB에서 동시 실행이 머신을 죽였다
(2026-08-09). `safe_dft.py`가 직렬·저메모리·재개 가능으로 설계된 이유다.

---

## 원칙

이 프로젝트를 이전 세 시도와 다르게 만드는 것들이다. 전문은 [CLAUDE.md](CLAUDE.md).

1. **정답은 LLM 판정이 아니다.** 어떤 주 지표도 LLM이 점수를 매기지 않는다.
2. **자명한 기준선을 설계 전에 먼저 측정한다.** 이전 세 시도가 모두 가설에 유리한
   비교 대상을 골라서 죽었다.
3. **τ는 방법오차에서 유도한다.** 파이프라인 재현성이 아니다.
4. **ABSTAIN 라벨은 기계적으로 유도한다.** 손으로 "작게 설정"하지 않는다.
5. **τ와 라벨은 동결 후 불변.** 결과를 본 뒤에는 어떤 이유로도 수정하지 않는다.
6. **가장 유력한 결과는 규칙 기반 기준선이 에이전트를 이기는 것이다.**
   그래도 논문은 성립한다 — 성능을 과장하지 않는 것이 이 설계의 전제다.

---

## 무결성 점검

```bash
python3 src/vccl/scoring/aggregate.py --check   # 동결·커버리지·원장 23항목 (API 0)
python3 tables/lock_manifest.py --verify        # S1~S8 LOCK 해시 대조
```

## Figure · Table 재생성

논문 Figure 는 **동결 산출물에서 스크립트로만** 만든다. 수치를 손으로 옮겨 적지 않는다.

```bash
# 1) 동결본 → plot-ready 데이터 (assertion 30건 포함, LLM 0회)
python3 src/vccl/scoring/plot_data.py

# 2) plot-ready 데이터 → figures/draft/F0~F4 .pdf|.png
python3 figures/make_figures.py
```

| | |
|---|---|
| 데이터 생성 | `src/vccl/scoring/plot_data.py` → `results/plot_data/` |
| 그림 생성 | `figures/make_figures.py` → `figures/draft/` |
| Caption | `figures/captions.md` |
| 설계 근거 | `paper_logic/figure_design.md` |

표도 같은 방식이다 — `src/vccl/scoring/table_data.py` → `results/table_data/` →
`tables/make_tables.py` · `tables/make_supp_tables.py` → `tables/draft/` ·
`tables/supplementary/`. **LOCK 이후에는 수치·문구를 바꾸지 않는다** (레이아웃 조정만).

**`make_figures.py` 는 `results/plot_data/` 외의 어떤 것도 읽지 않는다.** 수치를 바꾸려면
반드시 1) 을 고쳐야 하며, 그때 assertion 이 정정값 재현을 검증한다
(비용은 psi4 실측 wall time 전용 — DECISION_LOG 2026-08-14 (1) 정정 ②).
