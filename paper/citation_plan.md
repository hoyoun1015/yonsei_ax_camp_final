# 인용 계획 (Citation Plan) — 본문 아님

**작성 2026-08-20 · 검증 2026-08-20 (arXiv API · Crossref API 직접 조회)**
**없는 저자·DOI·연도·제목을 만들어내지 않는다**

**검증은 두 축이다** (§2) — **BIB_STATUS**(서지 metadata)와 **CLAIM_STATUS**(우리가 쓰려는
주장을 원문에서 확인했는가). 두 축을 하나의 «VERIFIED» 로 뭉치지 않는다.

🔒 **본문·참고문헌에 쓰는 인용은 BIB_STATUS=VERIFIED 이면서 CLAIM_STATUS=VERIFIED 인 것만
허용한다.** 최종 원고에 `NEEDS_VERIFICATION`·`CLAIM_UNVERIFIED`·placeholder 가 남으면 안 된다.
이 문서에 미사용 후보로 남는 것은 무방하다.

---

## 1. 문헌의 역할

| 역할 | 무엇을 위해 | 해당 |
|---|---|---|
| **Anchor** | 계승하고 한 고리를 조건화하는 대상 | C-06 |
| **직접적 방법 선행** | 증거 정당성을 실제로 평가한 사례 | C-07 |
| **과학 에이전트 일반** | 인식적 실패·자율성 한계 | C-08 · C-13 |
| **화학·도구 사용 에이전트** | 파이프라인이 이미 있다는 근거 | C-01 · C-02 · C-03 · C-14 |
| **에이전트 평가 벤치마크** | 채점이 결과 중심이라는 근거 | C-04 · C-05 |
| **판단보류·에스컬레이션** | 판단 기준을 만드는 여러 방식 | C-09 · C-10 · C-12 |
| **계산화학 배경** | τ·참조값·계산 수준 | C-15 · C-16 · C-17 |
| **다중 에이전트 구조** | 랩미팅형 선행 | C-19 |

---

## 2-A. 확인된 서지 (참고문헌 작성용)

| ID | 서지 |
|---|---|
| **C-01** | Andres M Bran, Sam Cox, Oliver Schilter, Carlo Baldassari, Andrew D White, Philippe Schwaller. *ChemCrow: Augmenting large-language models with chemistry tools.* **arXiv:2304.05376** (2023-04-11) — 학술지판 미확인이므로 **arXiv 판으로 인용** |
| **C-02** | Yunheng Zou, Austin H. Cheng, Abdulrahman Aldossary, Jiaru Bai, Shi Xuan Leong, Jorge Arturo Campos-Gonzalez-Angulo, Changhyeok Choi, Cher Tian Ser, Gary Tom, Andrew Wang, Zijian Zhang, Ilya Yakavets, Han Hao, Chris Crebolder, Varinia Bernales, Alán Aspuru-Guzik. *El Agente: An Autonomous Agent for Quantum Chemistry.* **arXiv:2505.02484** (2025-05-05) · **DOI 10.1016/j.matt.2025.102263** |
| **C-03** | Thang D. Pham, Aditya Tanikanti, Murat Keçeli. *ChemGraph: An Agentic Framework for Computational Chemistry Workflows.* **arXiv:2506.06363** (2025-06-03) — 학술지판 미확인 |
| **C-04** | Vinay Kumar, Satyendra Rajput, Mausam, N. M. Anoop Krishnan. *MDGYM: Benchmarking AI Agents on Molecular Simulations.* **arXiv:2605.08941** (2026-05-09) |
| **C-05** | Ziru Chen, Shijie Chen, Yuting Ning, Qianheng Zhang, Boshi Wang, Botao Yu, Yifei Li, Zeyi Liao, Chen Wei, Zitong Lu, Vishal Dey, Mingyi Xue, Frazier N. Baker, Benjamin Burns, Daniel Adu-Ampratwum, Xuhui Huang, Xia Ning, Song Gao, Yu Su, Huan Sun. *ScienceAgentBench: Toward Rigorous Assessment of Language Agents for Data-Driven Scientific Discovery.* **arXiv:2410.05080** (2024-10-07) · **ICLR 2025** |
| **C-06** | Martiño Ríos-García, Nawaf Alampara, Chandan Gupta, Indrajeet Mandal, Sajid Mannan, Ali Asghar Aghajani, N. M. Anoop Krishnan, Kevin Maik Jablonka. *AI scientists produce results without reasoning scientifically.* **arXiv:2604.18805** (2026-04-20) |
| **C-07** | Jiayao Chen, Shi Liu, Linyi Yang. *StatefulDiscovery: Evidence-Calibrated Claim Formation in Open-Ended Scientific Discovery.* **arXiv:2606.11851** (2026-06-10) |
| **C-08** | Steven Young Eulig. *Position: Correct Answer, Wrong Mechanism — When AI Scientists Defend General Claims Their Own Data Contradicts.* **arXiv:2606.23175** (2026-06-22) |
| **C-09** | Xun Liu, Yi Evie Zhang, Vira Kasprova, Parisa Rabbani, Pardis Sadat Zahraei, Tianyu Zhang, Ali Ebrahimpour-Boroojeny, Varun Chandrasekaran. *AgentAbstain: Do LLM Agents Know When Not to Act?* **arXiv:2607.10059** (2026-07-11) |
| **C-10** | Matthew DosSantos DiSorbo, Harang Ju. *Act or Escalate? Evaluating Escalation Behavior in Automation with Language Models.* **arXiv:2604.08588** (2026-03-31) |
| **C-11** | Victor Ojewale, Suresh Venkatasubramanian. *Designing for Doubt: The Case for Informed Abstention in Autonomous Agents.* **arXiv:2606.02965** (2026-06-01) |
| **C-12** | Sijin Dong, Hiroyuki Shinnou. *Uncertainty-Aware Abstention in Large Language Models with Provable Alignment Guarantees.* **arXiv:2607.04430** (2026-07-05) |
| **C-13** | Shuai Wang, Xinyuan Tian, Pangpang Liu, Yize Zhao. *Workflow Closure Is Not Scientific Closure in Auto-Research Systems.* **arXiv:2605.26200** (2026-05-25) |
| **C-14** | Daniil A. Boiko, Robert MacKnight, Ben Kline, Gabe Gomes. *Autonomous chemical research with large language models.* **Nature 624**(7992), 570–578 (2023) · **DOI 10.1038/s41586-023-06792-0** |
| **C-15** | Lars Goerigk, Andreas Hansen, Christoph Bauer, Stephan Ehrlich, Asim Najibi, Stefan Grimme. *A look at the density functional theory zoo with the advanced GMTKN55 database for general main group thermochemistry, kinetics and noncovalent interactions.* **Phys. Chem. Chem. Phys. 19**, 32184–32215 (2017) · **DOI 10.1039/c7cp04913g** |
| **C-16** | Christoph Bannwarth, Sebastian Ehlert, Stefan Grimme. *GFN2-xTB — An Accurate and Broadly Parametrized Self-Consistent Tight-Binding Quantum Chemical Method with Multipole Electrostatics and Density-Dependent Dispersion Contributions.* **J. Chem. Theory Comput. 15**(3), 1652–1671 (2019) · **DOI 10.1021/acs.jctc.8b01176** |
| **C-17** | Tom Frömbgen, Elizaveta Surzhikova, Jürgen Dölz, Jonny Proppe, Barbara Kirchner, Christoph R. Jacob. *Uncertainty Quantification for In Silico Chemistry.* **Chem. Rev. 126**(7), 4189–4236 (2026) · **DOI 10.1021/acs.chemrev.5c00931** |
| **C-18** | g-xTB — ChemRxiv **DOI 10.26434/chemrxiv-2025-bjxvt** (저장소 기록) · **서지 미확인** |
| **C-19** | Kyle Swanson, Wesley Wu, Nash L. Bulaong, John E. Pak, James Zou. *The Virtual Lab of AI agents designs new SARS-CoV-2 nanobodies.* **Nature 646**, 716–723 (2025) · **DOI 10.1038/s41586-025-09442-9** |
| **C-20** | Linghan Kong, Richard A. Bryce. *Discriminating High from Low Energy Conformers of Druglike Molecules: An Assessment of Machine Learning Potentials and Quantum Chemical Methods.* **ChemPhysChem 26**(8) (2025) · **DOI 10.1002/cphc.202400992** · 쪽수 ABSENT |

---

## 2-B. 검증 상태 — **두 축으로 분리한다**

**BIB_STATUS** — 서지 metadata(제목·저자·연도·학술지·DOI)를 공식 source 에서 확인했는가
**CLAIM_STATUS** — **우리가 쓰려는 주장**을 원문(초록·본문)에서 실제로 확인했는가
  · `VERIFIED` 원문에서 해당 주장을 확인 · `PARTIAL` 일부만 확인 · `UNVERIFIED` 서지만 확인
**USE** — 최종 원고에서 쓸 것인가

🔒 **본문·참고문헌에는 BIB_STATUS=VERIFIED **이면서** CLAIM_STATUS=VERIFIED 인 것만 쓴다.**

| ID | BIB | CLAIM | USE | 확인 근거 (2026-08-20) |
|---|---|---|---|---|
| **C-01** ChemCrow | ✅ VERIFIED | ✅ VERIFIED | YES | arXiv 초록 — *"By integrating 18 expert-designed tools, ChemCrow augments the LLM performance in chemistry"* · *"Our evaluation, including both LLM and expert assessments…"* |
| **C-02** El Agente | ✅ VERIFIED | ✅ VERIFIED | YES | arXiv 초록 — *"an LLM-based multi-agent system that dynamically generates and executes quantum chemistry workflows from natural language user prompts."* |
| **C-03** ChemGraph | ✅ VERIFIED | ✅ VERIFIED | YES | arXiv 초록 — 구조 생성·단일점 에너지·구조 최적화·진동 해석·열화학을 tight-binding·MLIP·DFT·파동함수 방법으로 수행 |
| **C-04** MDGYM | ✅ VERIFIED | ✅ VERIFIED | YES | arXiv 초록 — *"even the strongest agent solves only 21% of easy-level tasks, with less than 10% at higher difficulties"* → **과제 성공률로 채점** |
| **C-05** ScienceAgentBench | ✅ VERIFIED | ✅ VERIFIED | YES | arXiv 초록 — *"unify the target output … to a self-contained Python program file and employ an array of evaluation metrics to examine the generated programs, execution results, and costs."* |
| **C-06** Corral (앵커) | ✅ VERIFIED | ✅ VERIFIED | YES | 초록 전문 + Introduction·Results·Discussion·Methods 절 구성 직접 확인 (68% · 26% · 41.4%/1.5% · 2단계 LLM 주석 · 인간 대조 92.6%/95.7%) |
| **C-07** StatefulDiscovery | ✅ VERIFIED | 🟡 **PARTIAL** | **조건부** | 초록에서 **overinterpretation 정의는 확인**. 그러나 *"claim adjudication 이 LLM judge/rubric 인가"* 는 **초록에 없다**(NOT ADDRESSED). ES/DV LLM judge 세부는 `gap_analysis.md` §6 의 2026-08-14 본문 확인 기록에 근거 → **본문에서 그 세부를 쓰려면 원문 재확인 필요** |
| **C-08** Correct Answer, Wrong Mechanism | ✅ VERIFIED | ✅ VERIFIED | YES | 초록 — *"we evaluate them as if only the final answer matters"* · *"task outcome, mechanism fidelity, and epistemic honesty must be measured separately."* |
| **C-09** AgentAbstain | ✅ VERIFIED | ✅ VERIFIED | YES | 초록 — *"the calibrated ability of tool-using LLM agents to recognize when not to act"* · 최고 모델 **59.5% paired accuracy**. ⚠️ **임계값 출처는 초록에 없다** |
| **C-10** Act or Escalate? | ✅ VERIFIED | ✅ VERIFIED | YES | 초록 — *"an LLM forms a prediction, estimates its probability of being correct, and compares the expected costs of acting and escalating."* |
| **C-11** Designing for Doubt | ✅ VERIFIED | ✅ VERIFIED | 선택 | 초록 — *"runtime enforcement, calibrated guard mechanisms, and auditable trace generation should become standard properties"* · **144 시나리오·7 모델군 평가**. ⚠️ 임계값 출처 논의 아님 |
| **C-12** Uncertainty-Aware Abstention | ✅ VERIFIED | ✅ VERIFIED | YES | 초록 — 응답별 *"uncertainty score"* + *"Hoeffding-style or Clopper-Pearson confidence intervals"* 로 보정 |
| **C-13** Workflow Closure | ✅ VERIFIED | ✅ VERIFIED | 선택 | 초록 — *"autonomous execution under non-autonomous epistemic control."* |
| **C-14** Coscientist | ✅ VERIFIED | ✅ VERIFIED | YES | Crossref 서지 + 제목이 «자율 화학 연구 수행»을 직접 진술 |
| **C-15** GMTKN55 | ✅ VERIFIED | ✅ VERIFIED | YES | Crossref 서지 + 제목이 데이터베이스 정체를 진술 |
| **C-16** GFN2-xTB | ✅ VERIFIED | ✅ VERIFIED | YES | Crossref 서지 + 제목이 방법 정체를 진술 |
| **C-17** UQ for In Silico Chemistry | ✅ VERIFIED | 🟡 **PARTIAL** | **조건부** | Crossref 서지 확인. 제목은 «계산화학 불확실성 정량화 리뷰»까지 지지한다. **«에너지차가 방법 오차 안이면 순위를 주장할 수 없다»는 문장은 `선행연구.md` 인용이며 이번에 원문 확인 못 함** → 그 문장을 쓰려면 원문 확인 필요. **약한 형태(리뷰 존재)로는 지금도 인용 가능** |
| **C-18** g-xTB | ❌ UNVERIFIED | — | **NO** | ChemRxiv DOI 가 저장소에 기록돼 있으나 이번에 확인하지 못했다. 배경 주장은 C-17 로 대체 |
| **C-19** Virtual Lab | ✅ VERIFIED | ✅ VERIFIED | 선택 | Crossref 서지 + 제목이 «AI 에이전트 팀이 연구를 수행»을 진술 |
| **C-20** Kong & Bryce | ✅ VERIFIED | ❌ **UNVERIFIED** | **NO** | Crossref 서지만 확인. **본문 페이월로 내용 미확인** → 인용하지 않는다 |

### 집계 (서로 다른 축이므로 합산하지 않는다)

| 축 | 수 |
|---|---:|
| **BIB_STATUS = VERIFIED** | **19 / 20** (C-18 제외) |
| **CLAIM_STATUS = VERIFIED** | **16** |
| CLAIM_STATUS = PARTIAL | 2 (C-07 · C-17) |
| CLAIM_STATUS = UNVERIFIED | 1 (C-20) |
| **USE = NO (미사용)** | **2** (C-18 · C-20) |
| USE = 선택 (필요할 때만) | 3 (C-11 · C-13 · C-19) |
| **두 축 모두 VERIFIED — 지금 바로 인용 가능** | **16** |

**집필 전에 해결해야 할 것 — 2건**
1. **C-07** — StatefulDiscovery 의 ES/DV LLM judge 세부를 본문에 쓰려면 **원문(§3.2–3.3·§4.2) 재확인**.
   재확인 전에는 **초록이 지지하는 범위(overinterpretation 정의)까지만** 쓴다.
2. **C-17** — «방법 오차 안이면 순위 주장 불가» 문장을 쓰려면 **원문 확인**.
   재확인 전에는 «계산화학의 불확실성 정량화를 다룬 리뷰» 수준으로만 인용한다.

---

## 3. 각 문헌이 실제로 지지하는 범위

| ID | 우리가 쓰려는 주장 | source 가 실제로 지지하는 범위 |
|---|---|---|
| C-01·C-02·C-03·C-14 | 자연어에서 화학 계산까지 가는 에이전트가 이미 있다 | 각 시스템의 구현과 시연. **채점 방식에 대한 일반 주장은 지지하지 않는다** |
| C-04·C-05 | 에이전트 평가가 과제 성공률·산출물 대조 중심이다 | **그 두 벤치마크의 채점 방식**까지. 「모든 선행이 그렇다」는 지지하지 않는다 |
| **C-06** | 인식적 실패가 대규모로 실재하고 결과 기반 평가로 탐지되지 않는다 · 분산 분해에서 스캐폴드 1.5% | 8도메인·25,000+ 실행. **판정은 2단계 LLM 주석**(인간 대조 92.6%/95.7%) |
| **C-07** | 증거 정당성 자체를 평가하는 최근 사례가 있다 | **초록 범위** — overinterpretation 을 «주장이 그것을 뒷받침하는 분석의 증거 범위를 초과하는 것»으로 정의. **LLM judge 세부는 초록이 지지하지 않는다** |
| C-08 | 결과가 맞아도 기전이 틀릴 수 있고, 결과만 보는 평가로는 부족하다 | position paper · 세 축(과제 결과·기전 충실도·인식적 정직성) 분리 주장 |
| **C-09** | 에이전트가 «언제 행동하지 않아야 하는지»를 평가한 벤치마크가 있고 성능이 낮다 | 최고 모델 59.5% paired accuracy. ⚠️ **임계값 출처의 근거로 쓰지 않는다** |
| **C-10** | 판단 기준을 **모델이 산출한 정답 확률 추정과 기대 비용 비교**로 만든다 | 초록이 직접 진술 |
| **C-11** | 판단보류를 시스템 **설계 속성**으로 다루자는 논의가 있다 | runtime enforcement · calibrated guard · auditable trace. ⚠️ **임계값 출처 논의 아님** |
| **C-12** | 판단 기준을 **불확실성 점수 + 보정 집합의 오류율 추정**으로 만든다 | 초록이 직접 진술 |
| C-13 | 자율 실행과 인식적 통제는 분리돼야 한다 | 초록이 직접 진술 |
| C-15 | τ 의 분모가 되는 참조값 집합 | GMTKN55 데이터베이스 자체 |
| C-16 | L1 계산 수준의 정의 | GFN2-xTB 방법 |
| **C-17** | (강) 에너지차가 방법 오차 안이면 순위를 주장할 수 없다 / (약) 계산화학 불확실성 정량화 리뷰 | **약한 형태만 현재 지지됨** |
| C-19 | 다중 에이전트가 연구를 수행한 선행 사례 | 나노바디 설계. **우리 도메인과 다르다** |

---

## 4. 인용할 때의 claim boundary

| 주장 | 반드시 이렇게 |
|---|---|
| 선행 채점 방식 | **「다수가 결과 중심으로 채점해 왔다」** + C-07 로 «증거 정당성을 평가한 사례도 있다». ⛔ 「전부 outcome-only」·「판단의 질을 본 사례가 없다」·「추론 평가 최초」 |
| **판단보류 계보 (RW-4)** | **「여러 방식이 있다」** — 모델의 정답 확률 추정과 비용 비교(C-10), 불확실성 점수와 보정 집합(C-12). 차이는 «계산 방법 자체의 실측 오차를 외부 기준으로 직접 쓴다»는 점. ⛔ **「임계값이 전부 모델 내부에서 온다」 포괄 주장 금지** · ⛔ C-09·C-11 을 임계값 출처의 근거로 쓰지 않는다 |
| 앵커(C-06) | 계승 7고리 · 방법적 대체 1(FOL-5, 범위 한정) · 조건화 1(FOL-9(b)). ⛔ 반례·틀렸다 · 1.5% 병치 |
| StatefulDiscovery(C-07) | 차별점은 **채점 축**뿐. ⛔ 성능 우열 · 「더 엄밀하다」 · 「우리는 LLM 을 쓰지 않는다」 |
| 파이프라인 선행(C-01~C-03·C-14) | 「파이프라인 구현은 이 논문의 기여가 아니다」. ⛔ 「최초」 |
| C-19 | 구조적 선행으로만. 성능·도메인을 비교하지 않는다 |

---

## 5. ⚠️ 후속 정정이 필요한 저장소 기록

이번 검증에서 **저장소 기록과 원문이 어긋나는 곳** 셋을 발견했다. 해당 파일들은 수정하지
않았고, **집필 시 따라야 할 최종 표현은 `paper/source_errata_for_manuscript.md` 에 정리했다.**

| 위치 | 현재 기록 | 원문 |
|---|---|---|
| `docs/선행연구.md` | 「What Benchmarks Don't Measure」(arXiv 2606.02965) | 실제 제목은 ***Designing for Doubt: The Case for Informed Abstention in Autonomous Agents*** |
| `docs/선행연구.md` · `paper_logic/anchor_fol.md` | 「El Agente Q」 | 실제 제목은 ***El Agente: An Autonomous Agent for Quantum Chemistry*** |
| `paper_logic/new_fol.md` **NEW-FOL-4** | *"판단보류/에스컬레이션 선행연구는 임계값을 전부 «모델 내부»에서 가져온다"* | C-09 는 임계값 출처를 다루지 않고 C-11 은 설계 속성 논의다. **포괄 주장을 지지하지 않는다** → RW-4 의 새 framing 과 맞추려면 정정이 필요하다 |

---

## 6. 참고문헌 표기 방식

- 국문 논문이지만 **참고문헌은 원어 그대로** 적는다.
- 학술지 게재분은 학술지 서지를 기준으로 하고 arXiv 번호를 병기한다(C-02·C-05·C-14 등).
- arXiv 판만 확인된 것은 **arXiv 판으로 인용**한다(C-01·C-03). 확인하지 못한 학술지
  서지를 적지 않는다.
- **인용 스타일은 제출처가 정해지면 확정한다.**
