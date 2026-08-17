# Anchor paper — 주장 구조의 연역 사슬 (FOL-1 ~ FOL-9)

**작성 2026-08-14 · 논문 본문 아님 · 논리 구조 분석 전용**

## 앵커 확정 상태

| | |
|---|---|
| 논문 | **arXiv 2604.18805 (2026-04)** — *AI scientists produce results without reasoning scientifically* |
| 벤치마크 이름 | **Corral** |
| 확정 근거 | `docs/선행연구.md` §4 — **본문 109p 직접 확인 (2026-08-08)**, 네 가지 사유 명시 |
| 보조 앵커 | arXiv 2606.23175 *Correct Answer, Wrong Mechanism* (position paper, 28 에피소드) |
| 최근접 경쟁 | arXiv 2606.11851 **StatefulDiscovery** — overinterpretation 을 사실상 같은 뜻으로 정의. **내부 L2 판정 = LLM skill · 최종 평가 = ES/DV rubric LLM judge (Gemini-3.1-pro)** |

🔒 **임의로 정하지 않았다.** 프로젝트 자료에 이미 확정·기록돼 있어 그대로 사용한다.

> 🟢 **2026-08-14 확인 완료.** StatefulDiscovery 본문(§3.2–3.3 · §4.2 · Appendix D)을
> 직접 읽었다 — L2 내부 판정은 LLM skill `evidence-strength-judge`, 최종 평가는
> **ES/DV 1–5 rubric LLM judging (Gemini-3.1-pro)** + 인간 120건 spot-check.
> **결론: 우리 차별점은 «채점 축»에서만 성립한다** — 내부 판정은 우리도 LLM(Reviewer)이다.
> 상세 대조는 `gap_analysis.md` §6.

---

## 연역 사슬

각 명제는 앞 명제에 의존한다. 중간 논리를 생략하지 않았다.

### FOL-1 · 전제 (분야 관찰)
**과학 에이전트 벤치마크는 주로 «결과»를 채점한다.**
앵커 관련연구 첫 문장 — *"Existing benchmarks for scientific agents primarily score
outcomes."* 우리 쪽 독립 조사도 같은 결론(`선행연구.md` §2: ChemCrow·El Agente Q·
ChemGraph·MDGym·ScienceAgentBench·ASTABench 전부 outcome-only).

### FOL-2 · FOL-1로부터
**결과 점수는 «맞는 답에 도달했는가»와 «옳게 추론했는가»를 구분하지 못한다.**
두 사건은 독립적으로 발생할 수 있다 — 틀린 추론으로 맞는 답에 도달하는 것이 가능하다.

### FOL-3 · FOL-2로부터
**따라서 결과 채점으로는 탐지되지 않는 인식적 실패(epistemic failure)가 존재할 수 있다.**
이 시점에서는 «존재할 수 있다»(가능성)까지만 따라온다. 실재는 아직 보이지 않았다.

### FOL-4 · FOL-3으로부터 (방법론적 요구)
**그것을 탐지하려면 결과가 아니라 «트레이스» — 인식적 조작의 순서 — 를 검사해야 한다.**
무엇을 가설로 세웠고, 무엇을 시험했고, 어떤 증거를 얻었고, 그 증거에 비추어 판단을
바꿨는가.

### FOL-5 · FOL-4의 조작화 ⚠️ **사슬에서 가장 약한 고리**
**앵커는 트레이스 검사를 «2단계 LLM 주석»으로 구현한다.**
Stage 1 — Claude Sonnet 4.5 가 메시지 단위로 인식적 조작을 라벨링
(hypothesis / test / evidence / judgment / commitment).
Stage 2 — 같은 모델이 엣지를 만든다. (본문 §4.8 · H.1)

> 🔴 **여기서 «판정자» 가 평가 대상과 같은 종류의 시스템이 된다.**
> FOL-4 는 "트레이스를 검사해야 한다"까지만 요구하며, **«LLM 으로 검사해야 한다»를
> 함의하지 않는다.** FOL-5 는 논리적 필연이 아니라 **구현 선택**이다.
> — 이 틈이 우리 논문의 자리다.

### FOL-6 · FOL-5의 신뢰성 확보
**그 주석은 인간 전문가와 대조해 검증됐다.**
전문가 2인 · 626 트레이스 · 인간–인간 일치 92.6% · 인간–LLM 일치 95.7%.
따라서 주석을 신뢰할 수 있는 측정으로 취급한다.

> ⚠️ **일치도는 «신뢰성»의 증거이지 «판정자 독립성»의 증거가 아니다.**
> 인간과 LLM 이 같은 편향을 공유하는 경우를 배제하지 못한다.

### FOL-7 · FOL-5·6을 대규모 적용
**증거가 68% 의 트레이스에서 채택되지 않고(evidence non-uptake),
반증에 따른 신념 수정은 26% 에서만 일어난다.**
8개 도메인 · 25,000+ 에이전트 실행.
주석 대상 부분집합에서는 더 나쁘다 — Claude Sonnet 4.5 · GPT-4o 모두 non-uptake **88%**,
belief revision 각각 **4% · 1%**. 워크플로 성격 도메인이 **82%** 로 가장 높다.

### FOL-8 · 분산 분해 (독립 관찰)
**베이스 모델이 성능·행동 분산의 41.4% 를 설명하고, 스캐폴드는 1.5% 를 설명한다.**

### FOL-9 · 결론 (FOL-7 + FOL-8)
**(a) 결과 기반 평가로는 이 실패를 탐지할 수 없고,
(b) 스캐폴드 공학만으로는 고칠 수 없다.**
> *"Outcome-based evaluation cannot detect these failures, and scaffold engineering
> alone cannot repair them."*

---

## 사슬의 구조적 특징 — 공격 가능한 지점

| 고리 | 성격 | 공격 가능성 |
|---|---|---|
| FOL-1 → FOL-3 | 논리적으로 견고 | 낮음 |
| **FOL-4 → FOL-5** | **구현 선택이 필연처럼 제시됨** | **높음 — 우리 자리** |
| FOL-6 | 일치도 ≠ 독립성 | 중간 |
| FOL-7 | 대규모 실측 | 낮음 (수치 자체는 반박 어려움) |
| **FOL-8 → FOL-9(b)** | **분산 분해에서 «스캐폴드 무용»으로 도약** | **중간 — 우리 ablation 이 «조건화» 후보.** ⚠️ 반례라고 쓰지 않는다. 앵커는 분산 설명력(관측), 우리는 단일 구성요소 개입 — **동종 비교 불가** |

**FOL-9(b) 의 논리적 간격.** 분산 분해는 «여러 스캐폴드를 뭉뚱그린 평균 효과»를
말한다. **특정 스캐폴드 «구성요소» 하나의 인과 효과가 크다는 것을 배제하지 않는다.**
"scaffold engineering alone cannot repair them" 은 분산 분해가 직접 지지하는 것보다
**강한 진술**이다.

---

## 앵커가 우리 도메인을 비워두었다

Corral 8개 도메인 — AFM 실험 실행 · 흡착 표면 구성 · **분자 시뮬레이션(LAMMPS)** ·
ML 물성 예측 · 회로 추론 · 역합성 계획 · 분광 구조 규명 · 무기 정성분석.

**양자화학 상대에너지(conformer / isomer)는 없다.** 인접하지만 비어 있다.

## 필요한 reference (본문 작성 시)

| 용도 | 문헌 |
|---|---|
| 앵커 | arXiv 2604.18805 (Corral) |
| 보조 앵커 | arXiv 2606.23175 |
| 최근접 경쟁 | arXiv 2606.11851 (StatefulDiscovery) |
| outcome-only 계보 | ChemCrow 2304.05376 · El Agente Q 2505.02484 · ChemGraph 2506.06363 · MDGym 2605.08941 |
| abstention 계보 (임계값이 모델 내부) | AgentAbstain 2607.10059 · Act or Escalate 2604.08588 · What Benchmarks Don't Measure 2606.02965 |
| 방법오차 · UQ | GMTKN55 (PCCP 19, 32184, 2017) · GFN2-xTB (JCTC 15, 1652, 2019) · UQ for In Silico Chemistry (Chem Rev 126, 4189, 2026) · g-xTB (ChemRxiv 2025) |
| ⚠️ 이름 충돌 회피 | VirtualLab_CC (S2949747726000230) — 시스템 이름을 다르게 지어야 한다 |
