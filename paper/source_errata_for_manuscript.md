# 집필용 source errata — 본문 아님

**작성 2026-08-20 · 인용 검증(arXiv API · Crossref API) 결과 발견한 내부 기록 오류를 모았다**

## 이 문서의 지위

> 🔒 **문헌의 제목·서지·claim boundary 에 한해서는 `paper/citation_plan.md` 와 이 errata 가
> stale 한 내부 문서보다 우선한다. Paper-FOL 의 논리 구조 자체는 변경하지 않는다.**

`paper_logic/new_fol.md` · `paper_logic/anchor_fol.md` · `docs/선행연구.md` ·
`paper_logic/paper_fol_10.md` 는 **이번에 수정하지 않았다.** 번호 체계와 역사 기록을
소급해서 다시 쓰지 않기 위해서다. 대신 **집필할 때 무엇을 따라야 하는지**를 여기 적는다.

---

## 1. 문헌 서지 오류

### E-1 · arXiv 2606.02965 의 제목

| | |
|---|---|
| **stale 위치** | `docs/선행연구.md` (갈래 C 표) |
| **기존 표현** | 「**What Benchmarks Don't Measure**」 |
| **검증된 표현** | ***Designing for Doubt: The Case for Informed Abstention in Autonomous Agents***, Victor Ojewale, Suresh Venkatasubramanian, arXiv:2606.02965 (2026-06-01) |
| **manuscript 에서** | 검증된 제목·저자를 쓴다. 「What Benchmarks Don't Measure」를 쓰지 않는다 |
| **근거** | `citation_plan.md` **C-11** (arXiv API 조회) |

### E-2 · arXiv 2505.02484 의 제목

| | |
|---|---|
| **stale 위치** | `docs/선행연구.md` · `paper_logic/anchor_fol.md`(reference 표) |
| **기존 표현** | 「**El Agente Q**」 |
| **검증된 표현** | ***El Agente: An Autonomous Agent for Quantum Chemistry***, Yunheng Zou 외 16인, arXiv:2505.02484 (2025-05-05), DOI 10.1016/j.matt.2025.102263 |
| **manuscript 에서** | **「El Agente」** 로 쓴다. 「El Agente Q」는 쓰지 않는다 |
| **근거** | `citation_plan.md` **C-02** |

---

## 2. 문헌 claim boundary 오류

### E-3 · 판단보류 선행연구의 «임계값 출처»

| | |
|---|---|
| **stale 위치** | `paper_logic/new_fol.md` **NEW-FOL-4** |
| **기존 표현** | *"판단보류/에스컬레이션 선행연구는 임계값을 전부 «모델 내부»에서 가져온다(confidence · entropy · conformal · 비용비)"* |
| **검증 결과** | 원문 초록 확인 결과 **포괄 주장이 지지되지 않는다.** ① **C-09 AgentAbstain** 은 «언제 행동하지 않아야 하는지 인식하는 능력»을 측정하며 **임계값 출처를 초록에서 다루지 않는다** ② **C-11 Designing for Doubt** 는 판단보류를 **설계 속성**으로 논하는 글이라 임계값 출처의 근거가 아니다 ③ 임계값 출처가 실제로 확인된 것은 **C-10**(모델이 산출한 정답 확률 추정 + 기대 비용 비교)과 **C-12**(응답별 불확실성 점수 + 보정 집합의 오류율 추정) 둘이다 |
| **manuscript 에서 쓸 최종 표현** | *"기존 판단보류·에스컬레이션 연구는 판단 기준을 여러 방식으로 만든다 — 모델이 산출한 정답 확률 추정과 행동·에스컬레이션의 기대 비용 비교(C-10), 응답별 불확실성 점수와 별도 보정 집합에서 추정한 오류율(C-12). 에이전트가 언제 멈춰야 하는지를 평가한 벤치마크도 있다(C-09). 이 연구의 차이는 계산 방법 자체의 실측 오차를 외부 판단 기준으로 직접 쓴다는 점이다."* |
| **금지** | ⛔ 「임계값이 전부 모델 내부에서 온다」 · ⛔ C-09·C-11 을 임계값 출처의 근거로 인용 |
| **근거** | `citation_plan.md` **C-09 · C-10 · C-11 · C-12** · `manuscript_blueprint.md` **RW-4** |

> 🔒 **NEW-FOL-4 의 번호와 논리 위치는 그대로 둔다.** 바뀌는 것은 **manuscript 에서 그
> 명제를 서술하는 범위**뿐이다. NEW-FOL-4 에 이미 붙어 있는 *"«없다»는 부재 증명이다 —
> 논문에서는 «우리가 찾은 범위에서는 없었다»로 쓴다"* 라는 단서와 방향이 같다.

### E-4 · StatefulDiscovery 의 판정 방식을 인용할 때

| | |
|---|---|
| **위치** | `paper_logic/gap_analysis.md` §6 · `paper_logic/anchor_fol.md` |
| **기존 기록** | ES/DV 를 **LLM judge(Gemini-3.1-pro) 1–5 rubric** 으로 평가 (2026-08-14 본문 직접 확인 기록) |
| **이번 검증** | **초록에는 그 내용이 없다**(NOT ADDRESSED). 초록이 지지하는 것은 **overinterpretation 의 정의**까지다 |
| **manuscript 에서** | LLM judge 세부를 본문에 쓰려면 **원문(§3.2–3.3 · §4.2) 을 다시 확인한 뒤** 쓴다. 재확인 전에는 **초록이 지지하는 범위(정의)까지만** 인용한다 |
| **근거** | `citation_plan.md` **C-07** (CLAIM_STATUS = PARTIAL) |

---

## 3. 용어 표현 정정 (논리 무변경)

### E-5 · 「사전등록 주 지표」 → 「실행 전에 정한 주 지표」

| | |
|---|---|
| **stale 위치** | `paper_logic/paper_fol_10.md` (Paper-FOL 8·10 및 §6 금지 표현 표에 「사전등록 주 지표」 표현이 남아 있다) |
| **왜 문제인가** | 「사전등록」이 **검정까지 사전에 고정된 것처럼** 읽힌다. 실제로는 지표·비교축·부분집합 일부만 실행 전에 고정됐고 **검정 목록과 분석법은 결과를 본 뒤 추가**됐다 |
| **manuscript 에서 쓸 최종 표현** | **「실행 전에 정한 주 지표」** (과대해석). 그리고 검정을 언급할 때는 반드시 — *"N=92 에서 보고한 정확 McNemar 8개 검정의 목록과 분석법 자체는 결과를 본 뒤 추가되었다. 다중비교 보정은 하지 않았다."* |
| **provenance 의 정본** | **표 S1 의 행별 지위 표기** — ① 주 지표·주 대비 모두 실행 전 고정 **1건** ② 비교축 또는 부분집합만 실행 전 고정 **3건** ③ post-hoc 탐색적 **4건** |
| **근거** | `tables/supplementary/S1_tests.md` · `DECISION_LOG` 2026-08-16 (6) · `writing_rules.md` §6-3 |

> 🔒 **Paper-FOL 의 번호·논리·주장·수치는 이번 패치에서 수정하지 않았다.**
> 바뀌는 것은 **manuscript 에서 쓰는 용어 표현**뿐이다.

---

## 4. 집필 중 확인 (grep)

```bash
# 이 errata 가 금지한 표현이 원고에 들어갔는지
grep -nE "What Benchmarks Don't Measure|El Agente Q|임계값(을|이) 전부|모델 내부에서 (온다|가져온다)|사전등록 주 지표|사전등록된 검정" paper/manuscript*.md
```

- [ ] E-1 「What Benchmarks Don't Measure」 0건
- [ ] E-2 「El Agente Q」 0건
- [ ] E-3 「임계값이 전부 모델 내부에서」 0건 · C-09/C-11 을 임계값 출처로 인용 0건
- [ ] E-4 StatefulDiscovery 의 LLM judge 세부를 원문 재확인 없이 쓴 곳 0건
- [ ] E-5 「사전등록 주 지표」 0건 · McNemar 언급부에 사후 provenance 표시
