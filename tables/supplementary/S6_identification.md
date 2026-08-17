# 표 S6 — 구조 식별 보조 검증 (identification challenge)

> **표 S6. 구조 식별 보조 검증.** 후보 구조가 4~15개인 과제에서 가설 문장만 보고 비교할 두 구조를 스스로 특정하게 한 실험이다. 조건은 V 단독이며, τ 는 식별 이후 단계에만 개입하므로 V−τ 를 따로 돌리지 않았다. **이 사전 지정 nontrivial candidate set 환경에서 본 벤치마크의 식별 76/76 을 보조 검증한 것이며, RQ1 전체를 입증하지 않는다. 난이도(hardness) 자체를 측정한 실험이 아니다.**

## (가) primary 24 — 완료 · 실행 전 분석계획 추가에 따른 보조 검증

*분석계획 `docs/DECISION_LOG.md 2026-08-14 (4) — pre-execution analysis amendment` · 모델 `gemini-3.6-flash-high` · 조건 V*

> ⚠️ 원 기획안에 들어 있던 사전등록이 아니라 **실행 직전에 추가한 분석계획**이다. 동결본이 과제 집합만 규정했고 조건·성공 기준·통계 계획은 비어 있었기 때문이다. 결과를 보기 전에 후보 집합·조건(V 단독)·귀무가설·검정·양방향 해석 문구를 고정했으므로 결과를 보고 고른 분석은 아니다. 다만 «처음부터 preregistered 였다» 고 쓰지 않는다.

| 항목 | 값 |
|---|---:|
| 과제 수 | 24 |
| 완료하지 못한 과제 | 0 / 24 |
| 식별 정확도 | 24 / 24 |
| 95% 신뢰구간 (Clopper–Pearson) | [0.858, 1.000] |
| 무작위 쌍 선택의 기대 정답 수 | 2.410 / 24 |
| 단측 정확 Poisson-binomial | 2.02×10⁻²⁶ |

**고정 해석 (결과를 보기 전에 정한 문구)**

> 사전 지정된 nontrivial candidate set 에서 식별 성능이 무작위 쌍 선택보다 유의하게 높았다.

**후보 구조 수 분포**

| 후보 구조 수 | 과제 수 |
|---|---:|
| 후보 4개 | 4 |
| 후보 5개 | 17 |
| 후보 11개 | 1 |
| 후보 12개 | 1 |
| 후보 15개 | 1 |
| 합계 | 24 |

후보 수는 4~15개, 중앙값 5개다.

**구간·계열 분포**

| 구간 | 과제 |
|---|---:|
| Band A | 13 |
| Band B | 9 |
| Band C | 1 |
| Band D | 1 |
| 합계 | 24 |

| 계열 | 과제 |
|---|---:|
| ACONF | 2 |
| Amino20x4 | 15 |
| ICONF | 1 |
| ISO34 | 1 |
| PCONF21 | 3 |
| SCONF | 2 |
| 합계 | 24 |

**이 실험이 주장하지 않는 것**

1. RQ1 전체를 입증하지 않는다 — 후보가 4~15개인 사전 지정 nontrivial candidate set 환경에서 main 의 식별 76/76 을 보조 검증한 것이다.
2. 난이도(hardness) 자체를 측정한 실험이 아니다.
3. primary 24개 중 15개가 Amino20x4 다. 식별 성능이 아미노산 배좌 판정에 좌우되며 다른 화학 계열로 일반화된다고 주장하지 않는다. 밴드 분포도 불균형(A13 B9 C1 D1)이라 이 세트로 밴드 의존적 주장을 하지 않는다.
4. R0 는 구조 쌍을 오라클로 받으므로 식별을 수행하지 않는다. 이 세트에서 R0 와 V 의 식별 정확도를 비교하지 않는다.
5. main N=92 와 중복되는 9과제를 합쳐 표본 수를 늘려 해석하지 않는다.

추론 단위 — 화학종 24종 — **유의성 검정은 이것으로 한다**

---

## (나) secondary 94 — post-hoc exploratory / descriptive supplementary

*사후등록 `docs/DECISION_LOG.md 2026-08-16 (3)` · `docs/DECISION_LOG.md 2026-08-16 (5)` · `docs/DECISION_LOG.md 2026-08-16 (7)` · 상태 🟢 완료*

> **표 S6(나). 같은 24 화학종에서 나온 94개 관측.** 기존 primary 24개 관측을 그대로 재사용하고 70개를 새로 실행해 합친 것이다. **추론 단위는 94개의 독립 표본이 아니다** — 화학종 24종이 반응을 여럿 내므로 같은 화학종의 관측끼리 독립이 아니다. **이 칸에서는 새로운 통계적 추론을 하지 않았다.**

**구성**

| 출처 | 관측 수 | 식별 정확 |
|---|---:|---:|
| 기존 primary 24 재사용 (재실행 아님) | 24 | 24 / 24 |
| 이번에 새로 실행 | 70 | 70 / 70 |
| 합계 | 94 | 94 / 94 |

완료하지 못한 과제(FAILED)는 **0 / 94** 이다. 실행 유효성은 신규 실행 70 을 분모로 재며 신규 FAILED 는 **0건** 이다 (무효 기준 4건).

**전체 식별 정확도**

> **94 / 94** (100.0%) — 화학종 24종에서 나온 94개 관측

**화학종별 correct / total**

| 화학종 | 맞음 | 전체 | 비율 |
|---|---:|---:|---:|
| ACONF:H_x+g-x+ | 9 | 9 | 100% |
| ACONF:P_GX | 3 | 3 | 100% |
| Amino20x4:ALA_xab | 4 | 4 | 100% |
| Amino20x4:ARG_xby | 1 | 1 | 100% |
| Amino20x4:ASN_xah | 2 | 2 | 100% |
| Amino20x4:ASP_xbc | 4 | 4 | 100% |
| Amino20x4:CYS_xal | 4 | 4 | 100% |
| Amino20x4:GLN_xal | 4 | 4 | 100% |
| Amino20x4:GLU_xad | 4 | 4 | 100% |
| Amino20x4:GLY_xag | 4 | 4 | 100% |
| Amino20x4:HIS_xav | 4 | 4 | 100% |
| Amino20x4:ILE_xak | 2 | 2 | 100% |
| Amino20x4:MET_xbo | 4 | 4 | 100% |
| Amino20x4:PHE_xal | 4 | 4 | 100% |
| Amino20x4:PRO_xab | 4 | 4 | 100% |
| Amino20x4:THR_xal | 4 | 4 | 100% |
| Amino20x4:TRP_xac | 4 | 4 | 100% |
| ICONF:SI5H12_4 | 3 | 3 | 100% |
| ISO34:P6 | 3 | 3 | 100% |
| PCONF21:224 | 6 | 6 | 100% |
| PCONF21:GLY_b | 2 | 2 | 100% |
| PCONF21:SER_b | 2 | 2 | 100% |
| SCONF:C15 | 10 | 10 | 100% |
| SCONF:G4 | 3 | 3 | 100% |

**화학종 단위 descriptive macro summary**

- 24종 · 평균 100.0% · 중앙값 100.0% · 범위 100%–100%
- 전량 정답 24종 · 전량 오답 0종
- 🔒 화학종이 24종뿐이다. 이 값으로 일반화하지 않는다.

**후보 구조 수별 correct / total**

| 후보 구조 수 | 맞음 | 전체 | 비율 | 화학종 |
|---|---:|---:|---:|---:|
| 4 | 12 | 12 | 100% | 4종 |
| 5 | 57 | 57 | 100% | 17종 |
| 11 | 6 | 6 | 100% | 1종 |
| 12 | 9 | 9 | 100% | 1종 |
| 15 | 10 | 10 | 100% | 1종 |

**계열(서브셋)별 correct / total**

| 계열 | 맞음 | 전체 | 비율 | 화학종 |
|---|---:|---:|---:|---:|
| ACONF | 12 | 12 | 100% | 2종 |
| Amino20x4 | 53 | 53 | 100% | 15종 |
| ICONF | 3 | 3 | 100% | 1종 |
| ISO34 | 3 | 3 | 100% | 1종 |
| PCONF21 | 10 | 10 | 100% | 3종 |
| SCONF | 13 | 13 | 100% | 2종 |

**식별에 실패한 과제**

없다.

**이 칸이 하지 않는 것**

- 새로운 p-value·유의성 검정·확증 신뢰구간을 만들지 않았다. primary 24 의 사전 지정 Poisson-binomial 검정과 Clopper–Pearson 신뢰구간을 이 94 로 갱신하지 않는다. RQ1 전체를 입증한다고 쓰지 않는다.
- 이것을 primary 24 의 replication 이라고 부르지 않는다 — 24 개는 재실행이 아니라 같은 결과의 재사용이고, 신규 70 은 같은 화학종에서 나온 다른 반응이다.
- **화학종 24종에서 나온 94개 관측**으로만 보고한다. 추론 단위는 94개의 독립 표본이 아니다.
- 결과를 보고 새로운 부분집단·문턱·검정법을 만들지 않았다.

---

## 수치 출처 (source mapping)

| 항목 | 출처 |
|---|---|
| primary 채점 결과 | `experiments/chal_primary_20260814T235648Z_gemini-3.6-flash-high/challenge_result.json` |
| 분석계획 출처 | `docs/DECISION_LOG.md 2026-08-14 (4) — pre-execution analysis amendment` |
| 신뢰구간·검정 | `src/vccl/agents/challenge.py` 의 `clopper_pearson` · `pb_upper_tail` |
| 무작위 귀무가설 | 과제별 1/C(후보 수, 2) — 같은 파일의 `chance_probs` |
| 후보 수·계열·구간 | `src/vccl/tasks/pairs.py` 의 `build_pool()` |
| 제한 문구 | `data/tasks/frozen_stage_b_v1.json` → `identification_challenge` |
| (나) secondary 94 | `experiments/chal_secondary94/secondary_result.json` |
| (나) 신규 실행 원장 | `experiments/chal_sec_c1_20260816T070415Z_gemini-3.6-flash-high` (158호출) · `experiments/chal_sec_c2_20260816T112752Z_gemini-3.6-flash-high` (194호출) |

**(가)** 는 `build_s6()` 가 기존 primary 결과에서 24/24 · 신뢰구간 · 기대 정답 수 · p · 후보 수 범위 · 계열·구간 분포·본 벤치마크와의 중복을 **다시 계산해 assertion** 한 값이다. **(나)** 는 `build_s6_secondary()` 가 `experiments/chal_secondary94/secondary_result.json` 을 읽어 **기술 통계로 집계**한 것이며, 구성(24+70)· 화학종 24종·합계 정합·신규 FAILED 게이트를 assertion 한다. **(나)에서는 어떤 추론 통계도 만들지 않는다.**

**동결 해시**

```
stage_a     0bfc4cee6a6cf0e0…
stage_b     2e80a29588b91baf…
```

---

## 🔒 LOCK (2026-08-17)

이 표의 **수치·통계·문구·행·열·각주를 확정**했다. 이후에는 제출 형식에 따른 레이아웃 조정 외에 내용을 바꾸지 않는다. **바꿔야 할 이유가 생기면 먼저 amendment 로 보고한다.**

재생성 (LLM 호출 0회 · 동결 산출물만 읽는다)

```bash
python3 src/vccl/scoring/table_data.py     # → results/table_data/ (assertion)
python3 tables/make_supp_tables.py         # → tables/supplementary/
```

파일 해시와 상류 산출물 버전은 `tables/supplementary/LOCK_MANIFEST.md` 에 있다. Figure F0~F4 와 Main Table 1 의 기존 LOCK 은 그대로 유지된다.
