# 표 S2 — 반응 유형·서브셋별 방법 오차(τ) 실측

> **표 S2. 서브셋별 방법 오차 실측 (kcal/mol).** GMTKN55 참조값 대비 각 계산 수준의 오차 통계다. **이 값들은 보정 단계의 기술적 결과이며 실행 중 밴드 경계로 쓰이지 않았다 — 실행 시의 판단은 위의 반응 유형별 임계값을 썼다.** 마지막 열은 서브셋 값을 그대로 썼다면 참조값 자체의 추정 오차 0.2 kcal/mol 하한에 걸렸을지를 표시한다.

**(가) 실행에 실제로 쓴 임계값 — 반응 유형별**

| 반응 유형 | τ(L1) | τ(L3) | 반응 수 |
|---|---:|---:|---:|
| conformer | 1.213 | 0.405 | 167 |
| isomer | 9.036 | 3.407 | 57 |

**(나) 서브셋별 오차 통계 (기술적 · 실행에 쓰이지 않음)**

| 서브셋 | 유형 | n | L1 MAE | L1 중앙 | L1 최대 | L3 MAE | L3 중앙 | L3 최대 | 0.2 floor |
|---|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| ACONF | conformer | 15 | 0.193 | 0.243 | 0.493 | 0.065 | 0.050 | 0.180 | 예 (L1·L3) |
| Amino20x4 | conformer | 80 | 0.954 | 0.716 | 4.409 | 0.235 | 0.174 | 1.243 | 아니오 |
| CDIE20 | conformer | 20 | 1.802 | 1.569 | 4.405 | 1.079 | 1.042 | 2.124 | 아니오 |
| ICONF | conformer | 17 | 1.629 | 1.661 | 4.277 | 0.328 | 0.249 | 0.793 | 아니오 |
| ISO34 | isomer | 34 | 6.902 | 7.089 | 21.635 | 1.949 | 1.448 | 10.309 | 아니오 |
| ISOL24 | isomer | 23 | 12.190 | 8.011 | 29.432 | 5.562 | 3.485 | 19.252 | 아니오 |
| PCONF21 | conformer | 18 | 1.757 | 1.772 | 4.244 | 0.537 | 0.514 | 1.035 | 아니오 |
| SCONF | conformer | 17 | 1.643 | 1.121 | 7.240 | 0.651 | 0.530 | 2.752 | 아니오 |

**각주**

a. 이 서브셋별 값은 보정 단계에서 얻은 기술적(descriptive) 결과이며 실행 중 밴드 경계로 쓰이지 않았다. 실행 시의 판단은 반응 유형별 임계값을 썼다.

   *These per-subset values are descriptive calibration results and were not used as runtime band boundaries. Runtime decisions used reaction-type thresholds.*

b. 반응 유형별로 둔 이유 — τ 는 반응 유형별이다. 서브셋별로 두지 않는다 — 에이전트가 런타임에 조회해야 하는데 오염 방어가 서브셋 정체를 숨기도록 요구하기 때문(기획안 §3.2). 반응 유형은 결합 그래프 비교로 판정 가능하다.

c. 하한 0.2 kcal/mol 의 근거 — GMTKN55 참조값 자체의 추정 오차 ±0.2 kcal/mol (ISOL24 .res 주석, DLPNO-CCSD(T)/CBS). 어떤 수준의 τ 도 이보다 작아질 수 없다.

d. 실행에 쓴 반응 유형별 임계값은 네 값 모두 하한보다 크므로 하한이 걸리지 않았다. 서브셋별 값을 썼다면 걸렸을 경우만 (나)의 마지막 열에 표시했다.

e. L2 는 과제 정의에 쓰이지 않아 표에서 뺐다. 원본 `per_subset_detail` 에는 남아 있다.

---

## 수치 출처 (source mapping)

| 항목 | 출처 |
|---|---|
| (가) 반응 유형별 임계값 | `data/tasks/frozen_rules_v1.json` → `tau.values` |
| (나) 서브셋별 통계 | 같은 파일 → `tau.per_subset_detail[subset].levels` |
| 반응 수 | 같은 파일 → `tau.n_reactions` |
| 하한 0.2 | 같은 파일 → `tau.floor` · `tau.floor_reason` |

`build_s2()` 가 실행 τ 네 값을 현재 고정값과 **대조 assertion** 한 뒤 파일을 쓴다. `Tau.get()` 이 돌려주는 실행 시점 값과도 일치를 확인한다.

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
