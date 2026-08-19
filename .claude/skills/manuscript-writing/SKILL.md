---
name: manuscript-writing
description: 이 저장소의 한국어 논문 원고(paper/manuscript.md)를 쓰거나 고칠 때 사용한다. 초록·서론·방법·결과·논의·한계·결론 중 어느 절이든 작성·수정·검토 요청이 오면 먼저 이 스킬을 부른다. 규칙을 새로 만들지 않고 paper/ 의 정본 문서들을 정해진 순서로 읽어 집행하는 실행기다.
---

# 원고 집필 실행기

**이 스킬은 정본이 아니다.** 규칙·수치·주장 경계는 전부 저장소 문서에 있다.
여기서는 **무엇을 어떤 순서로 읽고, 무엇을 검사하는가**만 정한다.

⛔ **이 스킬 안에서 규칙을 재정의하지 않는다.** 아래 문서와 어긋나는 지침이 이 파일에
있다면 **문서가 이긴다.**

---

## 1. Source of truth — 이 순서를 지킨다

```
1  paper_logic/paper_fol_10.md            논리·주장 경계의 최상위 정본
2  canonical 실험 산출물                   results/*.json · results/plot_data/ · results/table_data/
3  LOCK 그림·표·caption                    figures/captions.md · figures/draft/ · tables/draft/ · tables/supplementary/
4  paper/source_errata_for_manuscript.md   문헌 서지·claim boundary·stale 표현에 한함
5  paper/writing_rules.md                  집필 규칙 정본
6  paper/manuscript_blueprint.md           절·문단 설계
7  paper/claim_language_matrix.md          증거 등급별 허용 표현
8  paper/terminology_glossary.md           용어 표기
9  paper/citation_plan.md                  인용 서지·두 축 검증 상태
10 paper/figure_table_narrative.md         그림·표 호출 위치
11 paper/limitations_map.md                한계 배치
12 paper/korean_scientific_prose_calibration.md  한국어 문체
13 paper/manuscript_acceptance_criteria.md 합격 기준
```

**충돌 처리** — **논리 자체가 걸리면 Paper-FOL 이 우선한다.** 다만 **문헌 제목·서지·문헌
claim boundary, 그리고 «사전등록» 관련 manuscript-facing 표현**에서는 `citation_plan.md` 와
`source_errata_for_manuscript.md` 를 따른다.

---

## 2. 절대 지켜야 할 서사

원고의 주인공은 **실제 계산화학 도구로 화학 가설을 자율 검증하는 연구 에이전트 A** 다.

```
A → 연구 수행 흐름 → «지금 계산 증거로 결론을 내려도 되는가»라는 판단 문제
  → 방법 오차 기준 τ → 비교 실험 → 결과
```

**τ · Band · 통계가 주인공이 되면 실패다.** 시스템에 별도 이름을 만들지 않고
「연구 에이전트 A(이하 A)」로 부른다.

---

## 3. 집필 순서 — 최종 배치와 다르다

**작성 순서**

```
3 시스템·방법 → 4 실험 설계 → 5 결과 → 1 서론 → 2 관련 연구
→ 6 논의 → 7 한계 → 8 결론 → 초록
```

방법과 결과를 먼저 고정해야 **서론·초록의 주장 강도가 본문보다 세지는 것을 막을 수 있다.**
**최종 파일에서는 정상적인 논문 순서로 배치한다.**

---

## 4. 문단 하나를 쓸 때의 절차

1. **blueprint ID 를 확인한다** (`manuscript_blueprint.md` — I-3, M-4, R-2 …)
2. 그 문단의 **Paper-FOL 번호를 찾아 해당 단계의 Boundary 블록을 읽는다**
3. 필요한 **canonical 산출물을 실제로 연다.** 기억으로 수치를 쓰지 않는다
4. 인용이 필요하면 `citation_plan.md` 에서 **BIB_STATUS 와 CLAIM_STATUS 를 각각 확인**한다
   - **둘 다 VERIFIED 가 아니면 그 문헌을 쓰지 않는다**
5. 그림·표를 부를 자리인지 `figure_table_narrative.md` 로 확인한다
6. `terminology_glossary.md` 의 표기를 적용한다 (첫 등장/이후/피할 표현)
7. **한국어로 쓴다** — `writing_rules.md` §3·§4 와 `korean_scientific_prose_calibration.md`
8. 문단을 쓴 직후 **`claim_language_matrix.md` 로 주장 강도를 점검**한다
9. 절을 마치면 **human-prose audit**(§6)
10. 원고 전체를 마치면 **`manuscript_acceptance_criteria.md` A1~H4 를 실행**한다

---

## 5. 매번 확인하는 다섯 가지

- **관측과 해석** — 주요 결과·null·사후 검정·인과 해석에서는 문장을 분리한다
- **provenance** — N=92 의 정확 McNemar 8개 검정은 **결과를 본 뒤 추가**됐고 다중비교
  보정이 없다. 표 S1 의 행별 지위를 그대로 따른다
- **null 은 앞쪽에** — 실행 전에 정한 주 지표(과대해석)가 갈리지 않았다는 사실(p = 0.25)을
  결과 절 앞쪽에 한 문장으로 쓰고 변명하지 않는다
- **고정 문구** — 비용·Band C·경로 B·보조 검증은 `writing_rules.md` §5-3 문구 그대로
- **수치 출처** — `writing_rules.md` §5-4 의 대조표에서만 인용한다

---

## 6. Human-prose audit (절 단위)

`writing_rules.md` §4 와 `korean_scientific_prose_calibration.md` 를 **열어서** 확인한다.
**이 스킬에 금지어 목록을 복사해 두지 않는다.**

검사 대상 — 번역투 · 추상명사 연쇄 · 같은 문장 구조의 반복 · 불필요한 지시어 ·
한국 연구자가 잘 쓰지 않는 어휘 결합 · **문단 끝마다 붙는 자평·교훈 문장**.

🔒 **동의어로 바꿔 넘어가지 않는다. 걸리면 문장을 다시 설계한다.**

---

## 7. 절대 금지

- 새 실험을 제안하거나 실행하지 않는다
- 새 통계를 만들지 않는다. 없는 수치를 쓰지 않는다
- `paper_logic/paper_fol_10.md` 를 수정하지 않는다
- LOCK 산출물(F0~F4 · Main Table 1 · S1~S9)과 caption 을 수정하지 않는다
- citation metadata 를 추정하지 않는다 (저자·DOI·연도·제목)
- acceptance criterion 을 완화하거나 스스로 바꾸지 않는다
- preflight 문서의 규칙을 이 스킬 안에서 다시 정의하지 않는다

---

## 8. 요청별 진입점

| 요청 | 먼저 읽을 것 |
|---|---|
| 결과 절의 한 문단 | blueprint R-* → Paper-FOL 8·9 Boundary → canonical 산출물 → claim matrix |
| 관련 연구·선행 대비 | citation_plan §2-B·§3·§4 → errata E-1~E-4 → blueprint RW-* |
| 논의·조건화 | Paper-FOL 10 → gap_analysis 후보 B 표현 규칙 → limitations_map |
| 한계 | limitations_map → 배치표대로 |
| 그림·표 호출 | figure_table_narrative → captions.md(LOCK) |
| 초록 | **본문을 다 쓴 뒤에만.** blueprint A-1 → 강도가 본문보다 세지 않게 |
| 용어가 헷갈릴 때 | terminology_glossary |
| 마무리 검사 | manuscript_acceptance_criteria A1~H4 |
