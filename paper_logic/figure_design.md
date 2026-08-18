# Figure 설계 — venue-neutral (승인 전 제작 금지)

> 🗄️ **이 문서는 Figure 확정 «전» 의 설계 기록이다. 현재 정본이 아니다.**
> 현재 Figure 는 **F0~F4 로 LOCK** 돼 있고 내용·caption·이미지는
> `figures/captions.md` 와 `figures/draft/` 가 정본이다. 표는 **Main Table 1 (LOCK)** ·
> **Supplementary S1~S8 (기존 LOCK)** · **Supplementary S9 (별도 LOCK)** 이 정본이며
> `paper_logic/table_design.md` §4 · `tables/supplementary/LOCK_MANIFEST.md` (S1~S8) ·
> `tables/supplementary/S9_LOCK.md` (S9) 를 본다.
>
> 아래에 남아 있는 **옛 Supplementary 번호(«신규 S1» 등) · 옛 T1~T9 후보 번호 ·
> 폐기된 Main Table 후보 · 옛 F1 오염 프로브 figure 후보 · «후보 67건»** 은
> **설계 이력이며 현재 설계가 아니다.** 본문을 쓸 때 이 번호를 옮기지 않는다.


**작성 2026-08-15 · 아직 그리지 않는다.** 목표 venue 미정 → 1-column / 2-column 모두로
변환 가능하도록 설계한다. **패널은 세로로 쌓아도 가로로 붙여도 성립하게** 만들고,
색 하나 없이 흑백으로도 읽히게 한다(패턴·위치로 구분, 색은 보조).

---

## 0. 먼저 — 각 Figure 가 «무엇을 증명하는가»

| Fig | 증명하는 NEW-FOL | 성격 | 판정 |
|---|---|---|---|
| **F0** | NEW-FOL-9 (시스템 동작) · **NEW-FOL-11 (재조작화 미검증)** | **설명적** — 그 자체로는 증거가 아니다 | **유지** (독자가 구조를 모르면 나머지를 못 읽는다) |
| **F1** | NEW-FOL-5 (τ) · 6 (채점 정의) · 7 (N=92) | 정의 + 실측 | **유지** — 밴드 정의가 전체 결과의 전제다 |
| **F2** | NEW-FOL-12 (V>R0) · 14 (V−τ≡R0) · **13 (주 지표 널)** | 확증 결과 | **유지 · 패널 b 추가 권고** |
| **F3** | NEW-FOL-15 (**검출된 이득의 집중**) · 16 (비용) | 확증 결과 | **유지** — 두 패널이 «선택적 상승»이라는 한 주장을 이룬다 |
| **F4** | NEW-FOL-9 · 6 (τ 점검 → 적응적 상승) | 사례 | **유지** — 앵커 대비는 Discussion 으로 |

**추가 Figure 를 만들지 않는다.** 남은 명제는 표로 충분하다 —
NEW-FOL-8(오염 프로브)·10(challenge)·17(오류 분해)은 Supplementary 표로 내린다.

### 🔴 설계 단계에서 잡은 함정 2개

1. **F0 를 «설계도»로만 그리면 OVERCLAIM 이 된다.** 분기 B 를 다른 경로와 같은 굵기로
   그리면 독자는 그것이 실제로 쓰였다고 읽는다. **실측 사용 횟수를 경로 위에 숫자로
   적는다** (분기 A 45 · 분기 B 1). 설명적 그림을 정직한 그림으로 만드는 유일한 방법이다.
2. **비용을 표시할 때 trace 의 `cost_s` 를 쓰면 안 된다.** 그것은 «표시용 근사»
   (L3 = 구조당 40초)다. **psi4 실측 wall time** 을 써야 한다
   (DECISION_LOG 2026-08-14 (1) 정정 ②). F3b·F4 에 해당.
   → **`src/vccl/scoring/plot_data.py` 로 `results/plot_data/cost_by_task.csv` 를
   생성했고, 정정 합계 재현을 assertion 으로 걸었다** — ALL_L3 19,926.1 (차 −0.0) ·
   V 6,106.6 (차 −0.4) · V−τ 27,766.5 (차 +0.5). 92/92 과제 전부 실측이며
   근사 대체가 없다. **그림은 이 CSV 만 읽는다.**

---

## F0 · 시스템 workflow

| | |
|---|---|
| **단 하나의 주장** | *"에이전트는 가설을 스스로 조작화하고, 계산 수준을 고르고, 증거 충분성을 검토하고, 필요하면 상위 계산으로 올린다 — 그리고 그 각 경로가 실제로 몇 번 쓰였는지 여기 적혀 있다."* |
| **데이터** | 구조: `src/vccl/agents/loop.py` · 실측 주석: `main_run_aggregate.json` (V 조건) — 분기 A **45** · 분기 B **1** · 라운드 {1:46, 2:46} · L3 도달 **45/92** |
| **패널** | 단일 패널. 좌→우 흐름: **원 가설(고정)** → PI 조작화 → Comp. Chemist 수준 선택 → **실행층(결정론적, 캐시)** → Skeptical Reviewer → {분기 A ↑수준 · 분기 B ↺조작화 · 종료} → PI 최종 결론 |
| **표시 수치** | 각 되돌아가는 화살표 위에 **실제 사용 횟수** (A: 45회 · B: **1회**). 실행층 박스에 «판단하지 않음» 명시. τ 블록이 들어가는 지점 3곳(수준 선택·검토·결론)을 작은 표지로 표시 — **조작화 단계에는 τ 가 없다는 것이 보여야 한다** |
| **caption 초안** | *"System architecture. Three LLM roles operate over a deterministic execution layer that only runs submitted calculation specifications and never decides what to compare or what to conclude. Two feedback paths return control to earlier stages: branch A escalates the level of theory, branch B re-operationalizes the comparison while the original hypothesis stays fixed. Numbers on the return arrows are the observed usage counts in condition V over N=92 tasks. The τ marker indicates the three prompts that receive the method-error block; the operationalization prompt does not."* |
| **오해 위험** | ⚠️ 분기 B 를 대칭적으로 그리면 «두 경로가 대등하게 쓰인다»로 읽힌다 → **1회를 명시**하고 화살표를 점선으로 둔다. ⚠️ «자율 시스템»으로 읽혀 R0 와의 비교 범위가 넓어 보일 수 있다 → 실행층이 받는 입력이 무엇인지 명확히 |
| **연결** | NEW-FOL-9 (설명적) · **NEW-FOL-11 (수치로 정직하게)** · claim map #9, #11 |

---

## F1 · 벤치마크와 밴드 — 실제 runtime rule 은 «반응유형별» τ 다

| | |
|---|---|
| **단 하나의 주장** | *"정답 행동은 참조 에너지차의 크기와 **반응유형별** 실측 방법오차만으로 기계적으로 정해진다. 그 규칙 아래에서 밴드 C 는 «싼 계산으로는 판정 불가, 비싼 계산으로는 판정 가능»한 유일한 구간이다."* |
| **데이터** | 🔒 **밴드 경계는 `frozen_rules_v1.json` 의 반응유형별 τ — 실행 시 실제로 쓰인 규칙이다.** 서브셋별 MAE 를 경계로 쓰지 않는다 |
| **τ (경계 그 자체)** | **conformer** τ_L3 **0.405** · τ_L1 **1.213** · 3τ_L1 **3.638** <br> **isomer** τ_L3 **3.407** · τ_L1 **9.036** · 3τ_L1 **27.107** (kcal/mol) |
| **패널** | **(a) 사다리 2개를 분리해 그린다.** 위: conformer, 아래: isomer. 각각 로그 x축에 τ_L3 · τ_L1 · 3τ_L1 경계를 세우고 구간을 D/C/B/A 로 칠한다. 각 밴드 아래 «L1 정답행동 / L3 정답행동» 두 줄 — **C 에서만 두 값이 다르다**(ABSTAIN → 판정) <br> **(b)** 92과제 \|ΔE_ref\| 스트립 플롯을 **같은 두 축에 나눠** 얹는다 (conformer n=44 · isomer n=48). 각 점 = 한 과제 |
| **x/y축** | 두 패널 모두 x = \|ΔE_ref\| (kcal/mol, **로그**). y = 반응유형(2행). 밴드별 n 을 각 구간 위에 표기 |
| **표시 수치** | 경계 τ 6개(위 표) · 반응유형별 밴드 n — **conformer A20 B3 C12 D9** · **isomer A10 B19 C13 D6** · 전체 A30 B22 **C25** D15 |
| **caption 초안** | *"Task banding is derived, not chosen. For each of the two reaction types we measured the mean absolute error of each level of theory against GMTKN55 reference values (τ), and a task's correct action follows from \|ΔE_ref\| and τ alone: at or below τ_L3 no available level resolves it (D); between τ_L3 and τ_L1 only the higher level does (C); above τ_L1 the cheap level suffices (B, A). Band C is thus the only region where escalation changes the correct action. The two ladders are shown separately because the thresholds differ by roughly an order of magnitude between conformer and isomer reactions; these reaction-type values are the rule applied at runtime. Per-subset error values are reported in Supplementary Table T2 and were not used as band boundaries."* |
| **오해 위험** | 🔴 **단일 사다리로 그리면 실제 규칙을 잘못 표현한다** — conformer 와 isomer 의 τ 가 약 7~8배 다르다. 반드시 2행 분리. 🔴 **«우리가 밴드를 발견했다»로 읽히면 안 된다** — 정의다. 🔴 서브셋 수치(ISO34 6.902→1.949 등)를 이 그림에 쓰면 **경계가 실행 규칙과 달라진다** → **T2(Supplementary)로 내렸다** |
| **연결** | NEW-FOL-5 · 6 · 7 · claim map #5, #6, #7 |

---

## F2 · 주 결과 — justified resolution, 그리고 널이었던 주 지표

| | |
|---|---|
| **단 하나의 주장** | *"τ 를 가진 에이전트만 규칙 기준선을 넘는다. τ 를 빼면 규칙 한 줄과 구분되지 않는다 — 그리고 그 차이는 사전등록한 주 지표에서는 나타나지 않았다."* |
| **데이터** | `main_run_aggregate.json` + `oracle_headroom_audit.json`(R0·ALL_L3) + McNemar |
| **패널** | **(a)** justified resolution — 가로 막대 4개: **R0 56/92 · V−τ 54/92 · V 74/92 · ALL_L3 75/92**. V vs R0, V vs V−τ, V−τ vs R0 위에 유의성 브래킷 <br> **(b) 🔄 2×2 calibration matrix** (독립 막대 4개 대신) — 축: **자기 증거 충분성(adequate / inadequate) × 결론(commit / abstain)**. V 와 V−τ 를 나란히 두 개의 2×2 로 그린다 |
| **x/y축** | (a) x = 과제 수 (0–92), y = 조건. 막대 끝에 `k/92 (%)` <br> (b) 축 없음(행렬). 행 = 자기 증거 (adequate / inadequate), 열 = 결론 (commit / abstain). 셀에 과제 수, 셀 음영은 수에 비례. 두 행렬 공통 스케일 |
| **표시 수치** | (a) 브래킷에 **p = 9.1×10⁻⁴** (V vs R0) · **p = 1.1×10⁻⁵** (V vs V−τ) · **p = 0.86 n.s.** (V−τ vs R0) <br> (b) 셀 값 — **검증 완료, 합계 92** <br><br> **V** — adequate+commit **79** · adequate+abstain **0** · inadequate+commit **0** · inadequate+abstain **13** <br> **V−τ** — adequate+commit **55** · adequate+abstain **20** · inadequate+commit **3** · inadequate+abstain **14** <br><br> 두 «실패» 셀에 이름을 직접 적는다 — adequate+abstain = **over-caution**, inadequate+commit = **overinterpretation**. 각각 **p = 1.9×10⁻⁶** · **p = 0.25 n.s.** |
| **caption 초안** | *"Justified resolution (committed + own evidence adequate + direction correct) over the same N=92 tasks; exact McNemar tests, paired. (a) Only the condition with method-error information exceeds the one-line rule baseline; removing it (V−τ) leaves performance statistically indistinguishable from R0. ALL_L3 is a reference policy that runs every task at the higher level — not a proven upper bound. (b) Calibration of commitment against the agent's own evidence. Off-diagonal cells are the two failure modes: committing when the observed difference is within the method error of the level used (overinterpretation, the pre-registered primary metric) and abstaining when it is not (over-caution). V occupies neither off-diagonal cell. Removing the method-error block moves 20 tasks into over-caution (p = 1.9×10⁻⁶) and 3 into overinterpretation (p = 0.25, not significant). The pre-registered primary metric therefore did not separate the conditions; the separation is on the opposite axis."* |
| **오해 위험** | 🔴 **ALL_L3 를 «상한»으로 읽히게 배치하면 안 된다** — reference policy 로 못박는다. 🔴 **패널 b 를 빼면 체리피킹이 된다.** 🔴 R0 막대를 «전체 워크플로 기준선»으로 읽으면 안 됨 (구조 쌍·수준을 오라클로 받는다). 🔴 **2×2 의 대각선을 «정답»으로 읽히게 하면 안 된다** — 이 행렬은 «자기 증거에 대한 일관성»이지 «정답 여부»가 아니다. 참조값 대비 정확성은 (a) 의 justified resolution 이다. caption 에서 구분한다 |
| **연결** | NEW-FOL-12 · 13a · 13b · 14 · claim map #12, #13a, #13b, #14 |

---

## F3 · 성능 이득이 집중된 구간과 그 비용

| | |
|---|---|
| **단 하나의 주장** | *"**통계적으로 검출된 성능 이득은 밴드 C 에 집중되었다**, 그리고 그 이득은 «필요한 곳에서만 올리는 것»에서 온다 — 무차별 상승은 더 비싸고 이득이 없다."* |
| **데이터** | 밴드별 justified (R0/V−τ/V) · **`results/plot_data/cost_by_task.csv`** (실측 wall time, assertion 통과) |
| **패널** | **(a)** 밴드(A/B/C/D) × 조건(R0·V−τ·V) justified resolution 그룹 막대 <br> **(b)** 비용–품질 산점: x = 계산비용(ALL_L3 대비 %, **실측**), y = justified resolution. 점 4개(R0 · V · V−τ · ALL_L3) |
| **x/y축** | (a) x = 밴드, y = justified 과제 수 (밴드별 n 표기: A30 B22 **C25** D15). (b) x = 비용 % (0–150, 100 에 ALL_L3 세로 기준선), y = justified /92 |
| **표시 수치** | (a) 밴드 C: **R0 8 · V−τ 11 · V 22** / 25 <br> ⚠️ **핵심 ablation 을 먼저 표시한다** — 밴드 C **V vs V−τ p = 9.8×10⁻⁴** (주) · **V vs R0 p = 5.2×10⁻⁴** (보조) <br> 비-C 통합 V vs R0 **p = 0.39** 는 «검출되지 않음»으로만 표기 <br> (b) R0 (0.02%, 56) · **V (30.65%, 74)** · **V−τ (139.35%, 54)** · ALL_L3 (100%, 75) |
| **caption 초안** | *"(a) The statistically detected performance gain is concentrated in band C, the region where escalation changes the correct action. Within band C the ablation contrast is V vs V−τ (p = 9.8×10⁻⁴); the comparison against the rule baseline is shown as well (p = 5.2×10⁻⁴). Outside band C the V–R0 difference was not detected at this sample size (p = 0.39); this is an absence of detected difference, not evidence of no difference. (b) Cost is psi4 wall time measured from the cached calculations, relative to running every task at the higher level. V reaches 74 of the 75 justified resolutions of that reference policy at 30.65% of its cost. V−τ escalates on 91 of 92 tasks (101 executions, some tasks run more than once) and therefore costs more than the reference policy itself, without a corresponding gain."* |
| **오해 위험** | 🔴 **«효과는 밴드 C 에만 있다 / confined to band C» 로 쓰지 않는다.** p = 0.39 는 **효과가 0 이라는 증명이 아니다** — 비-C 는 검정력이 낮고(불일치 8:4) 애초에 이득 여지가 작은 구간이다. **«검출된 이득이 집중되었다»** 로만 쓴다 <br> 🔴 비용에 `LEVEL_COST_S` 근사(L3 = 40초)를 쓰면 무효 수치가 된다 — **CSV 만 읽는다** <br> 🔴 «V 가 ALL_L3 보다 낫다»로 읽히면 안 된다 (74 < 75) <br> 🔴 (b) 의 R0 점이 원점에 붙어 «공짜로 56»으로 보인다 — R0 가 구조 쌍·수준을 오라클로 받는다는 점을 caption 또는 본문에 |
| **연결** | NEW-FOL-15 · 16 · claim map #15, #16 |

---

## F4 · 대표 trajectory — τ 기반 증거 점검이 적응적 상승을 유발한 사례

| | |
|---|---|
| **단 하나의 주장** | *"Reviewer 의 τ 기반 증거 점검이 **실제로 escalation 을 유발했고**, 상승 후 결론에 도달했다 — 한 과제의 실제 트레이스."* |
| **🔒 범위** | **앵커의 evidence non-uptake 와 동일 현상으로 연결하지 않는다.** 이 그림은 **우리 메커니즘이 작동한 기록**이며, 앵커와의 관계는 **Discussion 에서** 다룬다 (construct 가 다르다 — NEW-FOL-13b) |
| **데이터** | **`ACONF:B_T+B_G` · 조건 V · 밴드 C · trace 8단계 전량 보존** (대안 19건, 전부 밴드 C·V). 비용은 **`cost_by_task.csv` 의 실측값** |
| **패널** | 단일 세로 타임라인 (라운드 1 → 2). 각 단계 박스에 **실제 출력 발췌**(번역 명시): ① 원 가설 ② PI 식별 `S2 vs S1` + 기하 근거 ③ 수준 선택 **L1** ④ 실행 **ΔE = 0.605** ⑤ Reviewer **불충분 → escalate** ⑥ 수준 선택 **L3** ⑦ 실행 **ΔE = 0.570** ⑧ Reviewer 충분 → PI **REFUTED** |
| **표시 수치** | **τ_L1 = 1.213 · τ_L3 = 0.405** (conformer) · ΔE_L1 **0.605** · ΔE_L3 **0.570** · \|ΔE_ref\| = **0.598** · **L3 실측 wall time**(근사 80초 아님) · 정답 행동 L1 ABSTAIN → L3 판정 |
| **caption 초안** | *"One task, condition V, band C. The agent identified the comparison from the hypothesis text alone, ran the cheap level, and observed a difference of 0.605 kcal/mol. The reviewer rejected that as insufficient because it lies within the measured method error of the level used (τ_L1 = 1.213 for conformer reactions), and requested escalation. At the higher level the difference of 0.570 kcal/mol exceeded that level's error (τ_L3 = 0.405) and the conclusion was issued. The reference value is 0.598 kcal/mol, i.e. the task is resolvable only above the cheap level. Quotes are excerpts of the agent's own outputs, translated but not summarized; full text in Supplementary."* |
| **오해 위험** | 🔴 **한 사례를 일반화로 읽히게 하면 안 된다** — caption 에 «one task» 명시, 밴드 C 25과제 전체는 F3(a) <br> 🔴 **선택 편향** — 67 후보 중 최고점을 골랐다는 사실과 선택 기준을 Supplementary 에 공개 <br> 🔴 발췌를 윤문하면 «에이전트가 이렇게 말했다»가 왜곡된다 → **번역만 하고 요약하지 않는다** <br> 🔴 **앵커 대비를 이 caption 에 넣지 않는다** (Discussion 으로) |
| **연결** | NEW-FOL-9 · 6 · claim map #9. **NEW-FOL-11 과 무관** (이 사례는 분기 A 다) |

---

## T1~T9 분류 — **본문 Figure 에는 넣지 않는다**

> ⚠️ **이 절의 Table 분류는 `paper_logic/table_design.md` (2026-08-16)로 대체됐다.**
> 최신 결론은 **Main Table 1개**이며, 아래 T4 항목의 «프로토콜 유효율»과
> Hypothesis Fidelity 는 **성과 지표에서 제거**됐다. 아래는 당시 초안으로 남긴다.

| ID | 내용 | 분류 | 사유 |
|---|---|---|---|
| **T4** | 시스템 동작 지표 (RQ1·RQ2) — FAILED 0/92 · 식별 76/76 · 프로토콜 유효율 | **Main Table** | 기획안 §7.2 «결과 절 첫 표». 이게 낮으면 나머지를 해석할 수 없다 |
| **T5** | Loop Utilization — 분기 A 45 / **분기 B 1** · 라운드 분포 | **Main Table** | **사전등록된 지표이자 부정적 결과.** 본문에 보여야 한다 |
| **T6** | 주 결과 수치 전량 + McNemar (F2 의 수치 근거) | **Main Table** | Figure 가 그림이면 표는 정확한 수치 |
| **T1** | 선행 채점 방식 비교 (outcome-only) | Main **또는** Supp | Related Work 분량에 따라. 없어도 산문으로 대체 가능 |
| **T2** | 반응유형 × 수준별 τ 실측 전량 | **Supplementary** | F1 이 요약을 담는다 |
| **T3** | 벤치마크 구성 상세 (밴드·화학종·서브셋) | **Supplementary** | F1(b) 가 요약을 담는다 |
| **T7** | 비용 상세 (과제별 wall time 분포) | **Supplementary** | F3(b) 가 요약. **과제별 2.9~3,631초 편차**는 부록에 |
| **T8** | 오류 분해 2×2 | **Supplementary** | **탐색적** (사전 지정 검정 없음) — 본문 표로 올리면 confirmatory 로 읽힌다 |
| **T9** | identification challenge (24/24 · CI · Poisson-binomial) | **Supplementary** | 보조 검증이고 **천장 효과**로 정보량이 낮다 |
| **S7** (초안의 «신규 S1») | L0 오염 프로브 (단정 시 58.5% · Band별 70/53/53/50%) | **Supplementary** | 이전 F1 후보였으나 본문 5개에서 제외. **현재 정본 번호는 S7 이다** |

---

## 공통 제작 규약 (승인 후 적용)

- **venue-neutral** — 패널을 세로/가로 어느 쪽으로 재배치해도 성립. 폰트 크기는 최종 폭에
  맞춰 조정하되 **축 라벨·수치는 흑백 인쇄에서도 읽히게**
- **색에 의존하지 않는다** — 조건은 위치·해칭·기호로 구분하고 색은 보조
- **모든 수치는 `results/` 의 동결 산출물에서 스크립트로 생성** — 손으로 옮겨 적지 않는다
- **plot-ready data 를 먼저 CSV/JSON 으로 뽑고 그림은 그 파일만 읽는다** (재현성)
- **비용은 실측 wall time 만** (근사 금지)
- n.s. 는 «차이 없음»이 아니라 «충분한 증거 없음»으로 caption 에 표기
