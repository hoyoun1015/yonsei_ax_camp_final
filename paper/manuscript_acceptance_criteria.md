# 원고 합격 기준 (Manuscript Acceptance Criteria) — 본문 아님

**작성 2026-08-20 · 이후 `/goal` 의 종료 조건으로 사용한다**

**원칙** — 「좋은 논문이 되었다」 같은 주관적 조건을 쓰지 않는다. **모든 항목은 파일을
열어 세거나 grep 으로 확인할 수 있어야 한다.** 판정은 PASS/FAIL 둘 중 하나다.

**대상 파일** — 원고는 `paper/manuscript.md`(가칭) 하나로 쓴다고 가정한다.
아래 명령의 `$M` 은 그 경로다. 명령은 **저장소 루트에서** 실행한다.

⚠️ **schema 주의** — canonical JSON 의 조건 키는 `"V"` 와 **`"V-tau"`**(ASCII 하이픈)다.
본문 표기 `V−τ`(U+2212)와 다르므로 스크립트에서 본문 표기를 키로 쓰지 않는다.
아래 스니펫은 2026-08-20 에 실제 저장소 schema 로 dry-run 해 동작을 확인했다.

---

## A. 구조 (7항목)

| # | 기준 | 확인 방법 |
|---|---|---|
| A1 | 제목이 있고 가제와 일치한다 | 첫 줄 `#` 확인 |
| A2 | 초록이 있다 | `## 초록` 존재 |
| A3 | 8개 본문 절이 모두 있다 (서론 / 관련 연구 / 시스템·방법 / 실험 설계 / 결과 / 논의 / 한계 / 결론) | `grep -c "^## "` ≥ 9 (초록 포함) |
| A4 | 참고문헌 절이 있다 | `grep "^## 참고문헌"` |
| A5 | 보충자료 안내가 있다 | `grep "보충자료"` ≥ 1 |
| A6 | `manuscript_blueprint.md` 의 **38개 문단 기능이 모두 원고에서 구현**됐다 | 문단 ID 별로 대응 서술을 찾아 대조한다. **자연스러운 글을 위해 인접 기능을 한 문단으로 합칠 수 있으며, 문단 수 자체는 합격 기준이 아니다** |
| A7 | 결론이 초록·본문보다 강한 주장을 하지 않는다 | 결론 절에 §C 금지 표현 0건 |

## B. 논리 coverage (4항목)

| # | 기준 | 확인 방법 |
|---|---|---|
| B1 | **Paper-FOL 1~10 이 모두 본문에 배치**돼 있다 | blueprint 의 Paper-FOL 열을 원고 절과 대조 — 10/10 |
| B2 | **연구 에이전트 A 가 서사의 주인공**이다 | 서론에서 A 의 정의가 τ 정의보다 먼저 나온다 |
| B3 | **τ 가 A 보다 먼저 주인공으로 등장하지 않는다** | 원고에서 「τ」 첫 등장 위치 > 「연구 에이전트 A」 첫 등장 위치 |
| B4 | τ 가 절 제목·초록 첫 문장의 주어가 아니다 | **script 는 절 제목만** 검사한다(아래). **초록 첫 문장은 수동 확인** — 자동·수동 범위를 구분해 둔다 |

```bash
python3 - <<'PY'
import re; t=open("$M").read()
a=t.find("연구 에이전트 A"); u=t.find("τ")
print("B3", "PASS" if 0<=a<u else "FAIL", a, u)
print("B4", "PASS" if not re.search(r"^## .*τ", t, re.M) else "FAIL")
PY
```

## C. 주장 강도 (8항목)

| # | 기준 | 확인 방법 (0건이어야 PASS) |
|---|---|---|
| C1 | **금지 overclaim 0건** | 아래 grep-1 |
| C2 | **ALL_L3 를 상한이라 부른 곳 0건** | `grep -nE "상한\|upper bound"` → ALL_L3 문맥 0 |
| C3 | **τ 의 모델 간 일반화 주장 0건** | `grep -nE "모델 간.*(일반화\|재현)\|cross-model.*generaliz"` |
| C4 | **완전한 closed-loop 주장 0건** | `grep -nE "완전한 closed\|full closed"` |
| C5 | **「차이가 없다/동등하다」 0건** (p > α 를 동등성으로) | `grep -nE "차이가 없\|동등하\|대등하"` |
| C6 | **주 지표 널이 명시**돼 있다 | `grep -c "0.25"` ≥ 1 **그리고** 결과 절 앞쪽에 위치 |
| C7 | **사후 provenance 누락 0건** (**manual + script hybrid**) | ① **E-3 문단**에 N=92 McNemar 8개 검정의 사후 provenance 와 다중비교 미보정이 명시됐는가(수동) ② **Results 에서 p 를 해석하는 문단을 하나씩 읽어** E-3 의 disclosure 와 모순되지 않는지 확인(수동·문단별) ③ 금지 표현 grep(아래 grep-2). **grep 만으로 PASS 하지 않는다** |
| C8 | **cross-model 이 한 문단을 넘지 않는다** | S9 언급 문단 수 = 1 |

```bash
# grep-1 · 금지 overclaim
grep -nE "유의하게 (줄|감소|억제|향상|우수)|과대해석을 (줄|억제|감소)|최초로|Band C에만|\
confined|반례|앵커가 틀렸|판단의 질을 본 사례가 없|전부 outcome-only|추론 평가.*최초|\
fidelity router|% 성능|LLM 을 쓰지 않" "$M"

# grep-2 · C7 보조 — 금지 표현만 잡는다. 이것이 PASS 근거가 되지는 않는다
grep -nE "사전등록된 검정|사전에 검정하였다|사전등록 주 지표|비교축만 사전" "$M"
# (0건이어야 하며, 그 뒤 ①②의 수동 확인을 마쳐야 C7 PASS)
```

**⚠️ 약한 자동검사를 강한 검증으로 두지 않는다.** C7 은 script 로 «금지 표현 부재»만
확인하고, «모든 해석 문단이 provenance 와 정합하는가»는 **문단별 수동 audit** 으로 판정한다.

## D. 수치 정합 (4항목)

| # | 기준 | 확인 방법 |
|---|---|---|
| D1 | **본문의 모든 주요 수치가 canonical 산출물과 일치** | 아래 스크립트 |
| D2 | 고정 문구가 변형 없이 쓰였다 (비용 · Band C · 경로 B · replication) | `writing_rules.md` §5-3 문자열 포함 확인 |
| D3 | 새로 만들어낸 수치·통계가 0건 | 본문 숫자 목록 − canonical 목록 = ∅ |
| D4 | L3 관련 세 수치(45 / 91 / 101)를 혼동한 곳 0건 | 수동 확인 + 문맥 grep |

```bash
python3 - <<'PY'
import json,re
t=open("$M").read()
agg=json.load(open("results/main_run_aggregate.json"))
rep=json.load(open("results/cross_model_replication_final.json"))
n=lambda c,k: sum(bool(r[k]) for r in agg["rows"][c])
want={"74":n("V","justified_resolution"),"54":n("V-tau","justified_resolution")}
checks=[("74/92",n("V","justified_resolution")==74),("54/92",n("V-tau","justified_resolution")==54),
        ("0.25","p = 0.25" in t or "p=0.25" in t),("30.6%","30.6%" in t),
        ("21/30",rep["preregistered_results"]["counts_over_30_tasks"]["justified_resolution"]["sonnet_V"]==21)]
for lab,ok in checks: print("D1",lab,"PASS" if ok else "FAIL")
PY
```

## E. 한계 (3항목)

| # | 기준 | 확인 방법 |
|---|---|---|
| E1 | **`limitations_map.md` 의 🔴 세 개가 논의 본문에 있다** | L-01 · L-02 · L-03 각각 grep |
| E2 | **한계 절에 🟠 항목이 모두 있다** (L-04~L-15 중 해당분) | 항목별 대조 — 누락 0 |
| E3 | 같은 한계를 세 곳 이상에서 반복하지 않았다 | 항목별 등장 횟수 ≤ 2 |

## F. 인용 (3항목)

| # | 기준 | 확인 방법 |
|---|---|---|
| F1 | **인용 hallucination 0건** — 저자·DOI·연도·제목을 생성한 곳 없음 | 참고문헌 전 항목을 `citation_plan.md` **§2-A 서지**와 1:1 대조 |
| F2 | **본문·참고문헌의 모든 인용이 `BIB_STATUS = VERIFIED` 이면서 `CLAIM_STATUS = VERIFIED`** | `citation_plan.md` §2-B 상태표와 1:1 대조. **🟢 표시만으로 통과시키지 않고 두 축을 각각 확인한다.** CLAIM_STATUS 가 PARTIAL·UNVERIFIED 인 문헌(C-07 · C-17 · C-20)은 **원문 재확인 전까지 쓰지 않는다.** 원고에 `NEEDS_VERIFICATION` · `CLAIM_UNVERIFIED` · placeholder 인용이 **모두 0건** |
| F3 | 「전부 outcome-only」류 문헌 과잉 주장 0건 | grep-1 에 포함 |

## G. 그림·표 (3항목)

| # | 기준 | 확인 방법 |
|---|---|---|
| G1 | F0~F4 와 Main Table 1 이 **각각 최소 1회** 호출된다 | `grep -c "그림 1\|F0"` 등 |
| G2 | 호출 순서가 **F0 → F1 → Main Table 1 → F2 → F3 → F4** 다 | 첫 등장 위치 오름차순 |
| G3 | 본문 서술이 caption(LOCK)보다 강하지 않다 | caption 문장과 대응 본문 문단 대조 |

## H. 문체 (4항목)

| # | 기준 | 확인 방법 |
|---|---|---|
| H1 | **한국어 문체 calibration audit 완료** | `korean_scientific_prose_calibration.md` §5 체크리스트 전 항목 확인 기록 |
| H2 | **AI 반복 문장 audit 완료** | 아래 grep-3 결과를 검토하고, 남긴 것은 이유가 있어야 한다 |
| H3 | 「우리는」·「본 연구에서는」이 template 처럼 반복되지 않는다 | **모든 사용처를 human-prose audit 에서 확인하고, 행위자 명시가 실제로 필요한 자리에만 남긴다. 반복적 template 사용은 FAIL** (수치 임계값을 두지 않는다) |
| H4 | 용어 불일치 0건 | `terminology_glossary.md` §6 grep |

```bash
# grep-3 · AI 선호 표현 (0건이 목표가 아니라, 남은 것마다 이유가 있어야 한다)
grep -nE "이를 통해|이러한|해당 |가능하게 한다|제공한다|시사한다|관점에서|맥락에서|주목할 만" "$M" | wc -l
```

**H2 주의** — 이 grep 은 **금지 목록이 아니다.** 걸린 문장은 «단어를 바꾸지 말고 문장을
다시 설계할지» 판단하는 후보다(`writing_rules.md` §4-1).

---

## 총 항목 수 — **36개** (A 7 · B 4 · C 8 · D 4 · E 3 · F 3 · G 3 · H 4)

---

## 🎯 `/goal` completion spec (그대로 복사해 쓴다)

```
목표: paper/manuscript.md 를 완성한다. 아래 36개 기준이 전부 PASS 여야 종료한다.
      하나라도 FAIL 이면 종료하지 않는다. 기준을 스스로 바꾸거나 완화하지 않는다.

[정본]
  문헌 정정      paper/source_errata_for_manuscript.md
  논리·주장 경계   paper_logic/paper_fol_10.md (commit da096e6)
  집필 규칙        paper/writing_rules.md
  문단 설계        paper/manuscript_blueprint.md
  용어             paper/terminology_glossary.md
  주장 강도        paper/claim_language_matrix.md
  인용             paper/citation_plan.md
  그림·표 호출     paper/figure_table_narrative.md
  한계 배치        paper/limitations_map.md
  한국어 문체      paper/korean_scientific_prose_calibration.md
  합격 기준        paper/manuscript_acceptance_criteria.md  ← 이 파일

[절대 조건 — 하나라도 어기면 즉시 FAIL]
  1  새 실험·새 통계·새 수치를 만들지 않는다. 모든 수치는 canonical 산출물에서만 인용한다
  2  LOCK 산출물(F0~F4 · Main Table 1 · S1~S9)과 그 caption 을 수정하지 않는다
  3  Paper-FOL 을 수정하지 않는다
  4  존재하지 않는 저자·DOI·연도·제목을 쓰지 않는다. **본문·참고문헌에 쓰는 인용은
     citation_plan.md 에서 BIB_STATUS=VERIFIED 이고 CLAIM_STATUS=VERIFIED 인 것만 쓴다**
     (두 축을 각각 확인한다). CLAIM_STATUS 가 PARTIAL·UNVERIFIED 인 문헌은 원문 재확인
     전까지 쓰지 않는다. 최종 원고에 NEEDS_VERIFICATION·CLAIM_UNVERIFIED·placeholder
     인용이 남으면 FAIL
 12  paper/source_errata_for_manuscript.md 의 E-1~E-5 를 따른다 — 문헌 제목·서지·claim
     boundary 에서는 citation_plan.md 와 errata 가 내부 문서보다 우선한다
  5  사전에 정한 주 지표가 널이었다는 사실(p = 0.25)을 결과 절 앞쪽에 명시한다
  6  N=92 의 McNemar 검정이 결과를 본 뒤 추가된 것임을 밝힌다
  7  p > 0.05 를 「차이가 없다 / 동등하다」로 쓰지 않는다
  8  ALL_L3 를 상한이라 부르지 않는다
  9  τ 효과의 모델 간 일반화를 주장하지 않는다 (V−τ 미복제)
 10  「완전한 closed-loop」·「최초」·「전부 outcome-only」를 쓰지 않는다
 11  τ 를 논문의 주제로 올리지 않는다. 주인공은 연구 에이전트 A 다

[종료 판정]
  paper/manuscript_acceptance_criteria.md 의 A1~H4 각 항목에 대해
  PASS/FAIL 과 그 근거(파일 위치 또는 명령 출력)를 표로 보고한 뒤,
  36/36 PASS 일 때만 완료로 선언한다.
  자체 판단으로 «충분히 좋다»고 종료하지 않는다.
```
