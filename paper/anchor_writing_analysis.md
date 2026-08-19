# 앵커 논문의 «집필법» 분석 — 논문 본문 아님 · 설계 근거 전용

**작성 2026-08-20 · 원문 직접 확인 · 새 실험·분석 없음**

**대상** arXiv **2604.18805** — *AI scientists produce results without reasoning scientifically* (Corral)
**확보 방법** arXiv 초록 페이지와 전문 HTML(`arxiv.org/html/2604.18805v1`)을 직접 읽었다.
저장소에는 원문 사본이 없다(`docs/` 의 PDF 는 전부 우리 산출물이다).

> ⚠️ **한계 표시.** 전문 접근은 했지만 절 단위 질의로 읽었기 때문에 **모든 문단을 한 줄도
> 빠짐없이 본 것은 아니다.** 아래 «없다» 로 적은 항목(특히 §6 의 «예상이 빗나간 결과»
> 처리)은 **확보한 범위에서 확인되지 않았다**는 뜻이며, 부재의 증명이 아니다.

> 🔒 **우리가 가져오는 것은 문장이 아니라 구조다.** 앵커의 표현·어구·문장을 옮기지
> 않는다. 논리의 정본은 `paper_logic/paper_fol_10.md` 이고, 이 문서는 그 논리를
> **어떤 순서와 강도로 배치할 것인가**에만 관여한다.

---

## 1. 전체 narrative architecture

**절 순서 (원문 그대로)**

```
1 Introduction → 2 Results → 3 Discussion → 4 Methods
  → Acknowledgements · Data availability · Code availability · Competing interests
  → Declaration of AI-assisted technologies · Author contributions
  → Instructions for reporting errors
```

**핵심 관찰 — Methods 가 맨 뒤다.** Nature 계열 본문 형식이다. 독자는 «무엇을
알아냈는가»를 먼저 다 읽고, 재현 정보는 마지막에 본다. 절 이름도 «실험» 이 아니라
**Results / Discussion / Methods** 셋뿐이고 Limitations·Conclusion 이라는 별도 절이 없다.

**메타 절이 이례적으로 두껍다** — 데이터·코드 공개, 이해충돌, **AI 사용 선언**,
저자 기여, 그리고 «오류 신고 방법»까지 둔다. 인식적 정직성을 다루는 논문이 스스로
그 규범을 이행해 보이는 배치다.

---

## 2. Title / Abstract

### 2-1. 제목

> *AI scientists produce results without reasoning scientifically*

- **완전한 서술문이고 주어가 연구 대상(AI scientists)이다.** 시스템 이름도, 방법 이름도,
  «벤치마크»· «프레임워크» 같은 단어도 없다.
- **대비 구조 하나로 전체 논지를 압축**한다 — «결과는 낸다 / 그러나 과학적으로 추론하지는
  않는다». 독자는 제목만으로 이 논문이 무엇을 반증하려는지 안다.
- 7 단어. 부제 없음.

### 2-2. 초록의 정보 공개 순서

원문 초록은 다음 순서로만 움직인다.

| 순 | 기능 | 원문 신호어 |
|---|---|---|
| 1 | **긴장(tension) 한 문장** — 널리 쓰이고 있다, 그러나 검증되지 않았다 | *"…increasingly deployed…, yet whether … is poorly understood."* |
| 2 | **«Here, we» — 무엇을 했는가** (규모·도메인·두 렌즈) | *"Here, we evaluate … across eight domains … through more than 25,000 agent runs and two complementary lenses"* |
| 3 | **관측 결과** (숫자) | *"We observe that … 41.4% of explained variance versus 1.5% for the scaffold."* |
| 4 | **결과의 확장** — 어디까지 같은 패턴이 나오는가 | *"The same reasoning pattern appears whether …"* · *"They persist even when …"* |
| 5 | **«Thus» — 종합 판정** | *"Thus, current LLM-based agents execute scientific workflows but do not exhibit the epistemic patterns…"* |
| 6 | **규범적 마무리** (사실이 아니라 함의) | *"Until reasoning itself becomes a training target, … cannot be justified by the process that generated it."* |

- **첫 문장의 역할은 배경 설명이 아니라 «긴장 만들기»** 다. *«많이 쓰인다, 그런데 …인지는
  잘 모른다»* 라는 한 문장으로 공백을 즉시 만든다.
- **핵심 숫자는 여섯 개** — 8 도메인 · 25,000+ 실행 · 41.4% · 1.5% · 68% · 26%.
  초록에 숫자를 더 넣지 않는다.
- **마지막 문장은 «우리가 무엇을 보였다»가 아니라 «따라서 이 분야는 무엇을 해야 한다»** 로
  끝난다. 일반화의 방향이 데이터가 아니라 규범 쪽으로 열려 있어 과장으로 읽히지 않는다.

---

## 3. Introduction — 다섯 문단뿐이다

문단마다 **첫 문장이 그 문단의 임무를 선언**하고, 마지막 문장이 다음 문단의 전제를 만든다.

| 문단 | 첫 문장 (원문) | 마지막 문장 (원문) | 임무 |
|---|---|---|---|
| 1 | *"DENDRAL …, one of the first artificial intelligence (AI) systems to produce a scientific result, showed its reasoning at every step."* | *"Expert systems built on this template remain in use in laboratories today."* | **역사적 대비항 세우기** — 예전에는 추론이 보였다 |
| 2 | *"Large language models (LLMs) have renewed this ambition."* | *"The epistemic process by which they arrive at scientific conclusions is largely inaccessible to scrutiny."* | 현재 시스템으로 이동, **잃어버린 것(가시성)을 명명** |
| 3 | *"This opacity matters for science itself."* | *"It bears on whether AI systems can produce scientific understanding beyond correct predictions."* | **왜 문제인가** — 이해관계 설정 |
| 4 | *"Current evaluations do not address this."* | *"The epistemic process underlying a result determines whether the knowledge produced is justified …"* | **공백 지목** |
| 5 | *"Here, we study LLM-based scientific agents … through two complementary lenses."* | *"These findings suggest that evaluating LLM-based agents requires direct assessment of their reasoning process, and that progress will require changes at the base-model level rather than further scaffold engineering."* | **연구 소개 + 결과 요지 + 함의** |

**왜 이 정보를 여기서 말했는가 — 세 가지 설계**

1. **1문단을 «현재»가 아니라 «1965년»으로 연다.** 지금의 결핍을 비판으로 시작하지 않고,
   과거에 있었던 것을 먼저 보여준 뒤 «그것이 사라졌다»로 넘어간다. 공격이 아니라
   상실의 서사가 되어 반발을 덜 산다.
2. **3·4문단의 첫 문장이 각각 6단어·5단어다.** 긴 문단들 사이에 짧은 선언을 박아
   논지의 관절을 만든다. 이 두 문장이 사실상 서론의 접속사다.
3. **5문단에서 결과의 «요지»까지 말해버린다.** 결과를 숨기지 않는다. 대신 숫자는
   초록·Results 로 미루고 방향만 말한다.

---

## 4. Results — 소제목이 «행위»가 아니라 «발견·주제»를 앞세운다

**소제목의 형태는 하나가 아니다 — 서술문도 있고 명사구도 있다.**

```
The base model determines performance
Epistemological structure of agent reasoning
Reasoning breaks down predominately
Reasoning does not adapt to epistemic demand
```

넷 중 셋은 완결된 서술문이고, 「Epistemological structure of agent reasoning」은
**명사구**다. **공통점은 문법 형태가 아니라 기능이다** — 어느 것도 «…에 대한 분석»,
«…의 결과» 처럼 **연구 행위만** 적지 않고, 그 절에서 독자가 알아야 할 **발견·주제·판정을
앞세운다.** 목차만 읽어도 논문이 무엇을 말하는지 순서대로 읽힌다.

🔒 **따라서 «소제목은 완결된 서술문이어야 한다»는 규칙을 세우지 않는다.** 가져올 것은
기능(무엇을 앞세우는가)이지 문법 형태가 아니다.

**하위 절의 시작 방식 — 확인한 범위에서 반복된 두 가지**

| 방식 | 예 | 언제 쓰나 |
|---|---|---|
| **결과 선언으로 시작** | *"Agents do not adapt their reasoning to the task, as a human practitioner would."* | 그 절이 하나의 판정을 담을 때 |
| **무엇을 했는지 한 문장으로 시작** | *"To examine how agents reason, we analyzed the full agent traces."* | 새 측정 방식이 처음 나올 때 |

**숫자와 정의를 한 문장에서 처리한다 — 다만 이것은 영어 문장의 장치다**

> *"Untested claims, hypotheses stated without experiments designed to test them, appear in 53% of traces overall and 63% in hypothesis-driven domains."*

지표 이름 → 쉼표로 정의 → 동사 → 숫자. 지표를 먼저 정의하는 별도 문단이 없다.
🔒 **가져올 기능은 «독자가 정의를 찾아 앞뒤로 왕복하지 않게 한다» 하나다.**
appositive(쉼표 동격)와 «숫자는 문장 끝»은 영어 어순의 산물이므로 **한국어 규칙으로
옮기지 않는다.** 한국어에서는 수치를 그것이 뒷받침하는 주장 가까이 두면 된다.

**관측과 해석을 «인접한 두 문장»으로 분리한다**

> 관측 — *"Reasoning ability accounts for 41.4% of the explained variance, environment scope for 30.1%, scaffold for 1.5%."*
> 해석 — *"The base model determines the performance of the agent, and the scaffold modulates the interaction only marginally."*

한 문장 안에서 숫자와 의미를 섞지 않는다. **먼저 잰 것, 다음 문장에서 뜻.**
`§7` 의 ADOPT 1순위다.

**부정적 수치를 나열로 압축한다**

> *"Evidence non-uptake … occurs in 68% of traces. In 71% of traces, beliefs are never updated. Only 26% of traces exhibit refutation-driven belief revision."*

세 문장 모두 짧고, 완충어가 없다. 나쁜 결과를 길게 설명하지 않는 것이 오히려 강하다.

---

## 5. Methods — 형식 정의 → 구현 → 도메인 → 측정 → 통계

```
4.1 Formalism            4.2 Task and tool formalism      4.3 Agent implementations
4.4 Domains and environments                              4.5 Manual trace annotation
4.6 Diagnostic question-answer pairs                      4.7 IRT and phenomenological model
4.8 Epistemological graphs                                4.9 Trace intervention experiment
4.10 Token-level log-probability analysis
```

- **추상에서 구체로, 그리고 측정 도구는 뒤로.** 무엇을 «에이전트»라 부르는지부터 정의하고
  (4.1–4.3), 그 위에 도메인을 얹고(4.4), 그다음에야 트레이스를 어떻게 라벨링했는지
  말한다(4.5·4.8).
- **본문과 보충자료의 분할 기준이 명시적이다** — *"Full tool lists, scoring rubrics, and
  task specifications … appear in [reference]; details for every environment are at [URL]."*
  즉 **재현에 필요한 «목록»은 보충자료로, «규칙»은 본문으로.**
- **방법 선택의 정당화는 짧다.** *"Tools are part of the environment, not the agent."*
  처럼 한 줄로 선을 긋고 넘어간다. 대안을 검토한 서술을 길게 두지 않는다.
- **판정자 신뢰성 수치를 Methods 안에 둔다** —
  *"Inter-annotator agreement analysis on a representative sample of 25 traces showed
  substantial human–human agreement (overall 92.6%, mean PABAK 0.853) and even higher
  human–LLM agreement (95.7%)."* Results 로 올리지 않는다. **측정 도구의 품질은 결과가
  아니라 방법이라는 태도**다.

---

## 6. 부정적 결과 · null 결과의 처리 — **여기서 앵커는 우리 모델이 되지 못한다**

앵커의 «나쁜 수치»는 전부 **연구 대상의 실패**(에이전트가 증거를 무시한다)이고,
그것이 곧 논문의 주장이다. 그래서 앵커는 부정 결과를 **완충 없이 앞세우는** 전략을 쓴다 —
문장을 짧게, 숫자를 그대로, 변명 없이.

**반면 우리 논문의 주 지표 결과(과대해석 p = 0.25)는 «우리 예상이 빗나간 것»** 이다.
성격이 다르다. 확보한 범위에서 **앵커에는 «저자의 사전 예상이 빗나갔다»를 다루는 문단이
확인되지 않았다.** 따라서 이 항목만은 앵커에서 배울 수 없고, 우리가 규칙을 만들어야 한다.

**우리가 쓸 규칙 (앵커 파생 아님 · 이 문서의 제안)**

1. **주 지표 결과를 Results 의 «그 축을 다루는 첫 문단»에 둔다.** 뒤로 미루지 않는다.
2. **한 문장으로 사실만 말하고 변명하지 않는다** — 앵커가 부정 수치를 다루는 리듬을 그대로
   가져온다. 길게 해명할수록 숨기는 것처럼 읽힌다.
3. **바로 다음 문단에서 «실제로 차이가 난 축»으로 넘어간다.** 순서가 «예상 → 빗나감 →
   그러나 다른 곳에서 갈렸다» 여야 하고, 반대로 배치하면 사후 프레이밍이 된다.
4. **예상이 왜 빗나갔는지에 대한 설명은 Discussion 으로 미룬다.** Results 에서 해석하지
   않는다(§4 의 관측/해석 분리 원칙과 같다).

---

## 7. Discussion — 수미상관으로 열고, 규범으로 닫는다

- **첫 문단이 서론 1문단의 DENDRAL 로 되돌아간다** —
  *"The question of whether machines can conduct scientific inquiry has accompanied AI since
  DENDRAL … in 1965. Our data provide a specific answer for current LLM-based agents."*
  **두 문장뿐이다.** 결과 요약으로 시작하지 않는다.
- **한계는 별도 제목 없이 본문에 녹아 있다.** 조건을 붙이는 문장(*"In workflow-construction
  domains, agents approach ceiling performance."*)이 주장 문장 옆에 바로 붙는다.
- **일반화의 강도가 마지막에서 오히려 낮아진다.** 마지막 문장은 새로운 사실 주장 대신
  조건문으로 끝난다 — *"As long as they are evaluated only by the answers they produce,
  this difference will remain invisible, and it will shape the knowledge they help produce."*
- **처방은 «likely» 로 완충한다** — *"Addressing them will likely require changes to how base
  models are trained."* 관측은 단정하고, **다음에 무엇을 해야 하는지는 완충한다.**

---

## 8. 반복되는 문단 구조 — 실제로 확인된 것만

전 문단을 하나의 틀에 맞추지 않는다. **확인한 범위에서 실제로 반복이 관찰된 것은 셋이다**(문서 첫머리의 한계 표시 참조).

| 패턴 | 형태 | 어디서 |
|---|---|---|
| **P1 · 선언 → 근거 → 확장** | 첫 문장이 판정, 이어서 수치, 마지막에 «어디까지 그런가» | Results 각 절 |
| **P2 · 관측 문장 / 해석 문장 인접쌍** | 숫자 문장 다음 문장이 곧 의미 | Results·Discussion |
| **P3 · 짧은 전환 문장** | 6~10 단어 완결문 하나로 논지를 꺾음 (*"This opacity matters for science itself."*) | Introduction 문단 머리 |

---

## 9. 문장 수준에서 관찰된 것

| 항목 | 관찰 |
|---|---|
| 길이·리듬 | 대부분 20~35 단어. 문단 머리·논지 전환에만 6~10 단어 단문 |
| 태 | **능동 우세**. 측정 절차 서술에서만 부분적 수동 |
| 주어 | 연구자 행위는 *we*, 판정·결과는 **연구 대상을 주어로**(*agents…*, *the base model…*) |
| 동사 구분 | 관측 *observe / occurs / appear*, 해석 *determines / suggest*, 처방 *will likely require* |
| hedge 강도 | **관측에는 hedge 없음.** 처방·원인에만 *likely* 급 완충 |
| 인과 표현 | 분산 분해 결과에는 인과어를 쓰지 않고 *accounts for* 로 묶음. 인과 주장은 개입 실험(4.9)이 있을 때만 |
| 숫자 위치 | (영어) 문장 끝, 정의는 앞에 동격으로. **한국어로 옮기지 않는 형식** |
| 용어 첫 등장 | 그 자리에서 쉼표 동격으로 정의하고 다시 정의하지 않음 |
| 반복 | 핵심 수치(68% · 41.4% · 1.5%)가 초록·Results·Discussion 에 다시 나온다. **횟수가 규칙이라기보다, 다시 쓸 때마다 그 자리에서 새 서술 기능을 한다** |

---

## 10. ADOPT — 우리 논문에 가져올 원칙

| # | 원칙 | 우리 쪽 적용 지점 |
|---|---|---|
| **A1** | **관측 문장과 해석 문장을 분리하고 인접시킨다** | Paper-FOL 8·9 전체. 우리 금지 표현 대부분이 «숫자와 해석을 한 문장에 섞을 때» 생긴다 |
| **A2** | **Results 소제목이 연구 행위가 아니라 발견·주제를 앞세우게 한다** | 서술문·명사구 중 **한국어로 자연스러운 쪽**을 쓴다. 형태를 통일하지 않는다 |
| **A3** | **독자가 정의를 찾아 앞뒤로 왕복하지 않게 한다** | 지표를 처음 쓸 때 그 자리에서 짧게 정의한다. **쉼표 동격은 자연스러울 때만** — 영어 appositive 를 한국어에 기계적으로 옮기지 않는다 |
| **A4** | **부정 수치는 짧게, 완충 없이** | 주 지표 널(p = 0.25) 보고에 적용 (단 §6 의 우리 규칙과 함께) |
| **A5** | **각 문단 첫 문장이 그 문단의 임무를 선언한다** | 다섯 문단은 **좋은 초기 blueprint 이지 규칙이 아니다.** Paper-FOL 흐름이 자연스러운 쪽이 우선이며 4~6문단으로 조정할 수 있다 |
| **A6** | **논지를 꺾어야 할 때 짧은 완결문 하나를 둔다** | 글자 수·단어 수를 규칙으로 만들지 않는다. 필요할 때만 쓴다 |
| **A7** | **Discussion 을 서론의 대비항으로 되돌려 연다** | 우리 대비항은 «계산은 하지만 그 계산을 믿어도 되는지는 모르는 시스템» |
| **A8** | **직접 측정한 값은 불필요하게 완충하지 않고, 의미·일반화·인과는 증거 수준에 맞게 제한한다** | 경로 B 1/92 의 원인을 «알 수 없다»로 두기로 한 결정과 맞는다 |
| **A9** | **판정 도구의 신뢰성은 Methods 로** | τ 실측·동결·assertion 은 Results 가 아니라 Methods |
| **A10** | **마지막 문장은 새 사실이 아니라 조건·규범으로** | Paper-FOL 10 의 조건화가 그대로 이 자리에 들어간다 |

---

## 11. DO NOT ADOPT — 가져오지 않을 것

| # | 앵커의 특징 | 왜 우리는 안 되는가 |
|---|---|---|
| **X1** | **단정의 강도** (*"scaffold engineering alone cannot repair them"*) | 앵커는 8도메인·25,000 실행이다. **우리는 1도메인·N=92·단일 모델**이고 **주 지표가 널**이다. 같은 강도로 쓰면 즉시 overclaim |
| **X2** | **한계를 별도 제목 없이 전부 산문에 녹이기** | 우리 한계는 L1~L8 + 식별 제한 5개 + 범위 한정 3문장으로 **양이 다르다.** 전부 녹이면 묻힌다 → **핵심 3개만 Discussion 본문, 나머지는 별도 한계 절**(의도적 이탈) |
| **X3** | **Methods 를 맨 뒤로** | Nature 형식이다. 국문 제출본 관례와 충돌할 수 있으므로 **투고처 확정 전에는 채택 보류** |
| **X4** | **제목·문장 표현 자체** | 우리 제목은 이미 별도로 정한다. 앵커 어구를 옮기지 않는다 |
| **X5** | **부정 결과 = 곧 주장** 이라는 서사 | 앵커의 부정 결과는 «대상의 실패», 우리 주 지표 널은 «우리 예상의 실패». **성격이 달라 같은 배치를 쓸 수 없다** (§6) |
| **X6** | **인과어 없이도 강하게 읽히는 영어 구문**(*accounts for*, *modulates*) | 한국어로 직역하면 «설명분산을 차지한다» 류의 번역투가 된다. 기능만 가져오고 표현은 새로 쓴다 |
| **X7** | **초록에서 방법을 «두 렌즈»로 은유** | 우리는 조건 4종을 그대로 이름으로 부르는 편이 정확하다 |

---

## 12. 한국어로 옮길 때 주의할 점

**목표는 «쉬운 글»이 아니라 «한국인 연구자가 직접 쓴 것 같은 정확한 학술문»이다.**
영어 구조를 한국어 단어로 갈아 끼우는 방식은 금지한다. AI 티가 나면 **단어를 바꾸는 것이
아니라 문장을 다시 쓴다.**

### 12-1. 기계적으로 반복되면 안 되는 표현

> 이를 통해 · 이러한 · 가능하게 한다 · 제공한다 · 시사한다 · 관점에서 · 맥락에서 ·
> 주목할 만하다 · 중요한 시사점을 제공한다 · 살펴보고자 한다 · 라고 할 수 있다

이 표현들이 나쁜 이유는 «어렵다»가 아니라 **아무 문장에나 붙어 정보를 늘리지 않기**
때문이다. 지우면 문장이 짧아지고 뜻이 그대로면 원래 필요 없던 말이다.

### 12-2. 구조 차원의 규칙

| 증상 | 대신 |
|---|---|
| 영어 어순 직역 («…하는 것은 …을 의미한다») | 주어를 앞에 두고 술어로 끝낸다 |
| 추상명사 과다 («개선의 가능성을 제시한다») | 동사로 쓴다 («개선할 수 있다») |
| 피동 남용 («…이 관측되었다») | 관측 주체가 우리면 «…을 관측했다» |
| 한 문장에 절 세 개 이상 | 두 문장으로 자른다 |
| 지시어 연쇄 («이러한 결과는 이를 통해») | 지시어를 명사로 되돌린다 |
| 영어 용어를 음차만 («에스컬레이션을 수행한다») | 우리말로 풀되 원어가 필요한 것만 남긴다 |

### 12-3. 이미 정해져 있는 우리 문체 규약 — **새로 만들지 말고 따른다**

`figures/captions.md` 는 **LOCK 된 한글 논문용 문서**이고 표기 규칙을 이미 확정해 두었다.

- **원어로 남기는 것** — GFN2-xTB · B3LYP-D3(BJ)/def2-TZVP · τ · ΔE · p · R0 · V−τ ·
  ALL_L3 · Band A–D · PI. **그 밖에는 한국어로 적는다.**
- **바꿔 쓰는 것** — branch A/B → **경로 A/B**, Supplementary Material → **보충자료**,
  justified resolution → **근거가 충분한 결론**.
- 보충자료 표 S1~S9 의 각주 문장들이 **이미 우리 학술 문체의 표본**이다. 본문은 그 톤과
  이어져야 한다(LOCK 이라 고칠 수 없으므로 본문이 맞춰야 한다).

### 12-4. 문체 자가 점검 세 가지

1. **문장에서 숫자를 지웠을 때 뜻이 남는가?** 남지 않으면 그 문장은 해석이 아니라 나열이다.
2. **«이», «이러한», «해당»을 전부 지워도 읽히는가?** 읽히면 원래 없어야 할 말이다.
3. **소리 내어 읽었을 때 숨이 차는가?** 차면 절을 잘라야 한다.
