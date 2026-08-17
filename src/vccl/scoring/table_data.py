"""보충자료 표 S1~S8 의 source data 를 동결 산출물에서 생성한다.

**LLM 호출 0회 · 읽기 전용.** 계산·채점·동결 파일을 수정하지 않는다.
`results/plot_data/` (Figure 입력) 도 건드리지 않는다 — 여기서는
`results/table_data/` 에만 쓴다.

**수치를 손으로 옮기지 않는다.** 모든 값은 아래 원본에서 다시 집계하며, 앞선 분석이
보고한 값과 대조하는 assertion 을 통과해야 파일이 쓰인다.

| 표 | 원본 |
|---|---|
| S1 검정 요약 | `results/main_run_aggregate.json` · `results/oracle_headroom_audit.json` |
| S2 τ 실측 | `data/tasks/frozen_rules_v1.json` → `tau.per_subset_detail` · `tau.values` |
| S3 오류 분해 | `main_run_aggregate.json` 92행 × 2조건의 `error_class` |
| S4 벤치마크 구성 | `frozen_stage_b_v1.json` 과제 목록 × `build_pool()` |
| S5 계산시간 | psi4 캐시 실측 wall time (`scoring/headroom.task_cost_s`) |
| S6 식별 챌린지 | `experiments/chal_primary_…/challenge_result.json` |
| S7 L0 probe | `experiments/L0_…/l0_result.json` |
| S8 사례 전문 | `experiments/main_b1_…/batch_result.json` → `case_study_candidates` |

🔒 **지키는 표현 규칙**

- 비용은 **실측 wall time 만** 쓴다. 40초/구조 근사는 실행 횟수 역산에만 쓰였다.
- `ALL_L3` 를 theoretical upper bound 라고 부르지 않는다 — **비교용 정책** 이다.
- tool-limited 를 «줄일 수 없는 오류» 로 쓰지 않는다.
- Hypothesis Fidelity · Protocol Validity 를 성과 지표로 되살리지 않는다.
- post-hoc 검정은 반드시 post-hoc 이라고 표시한다.

사용:
    python3 src/vccl/scoring/table_data.py          # → results/table_data/
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents.r0 import to_task  # noqa: E402
from vccl.executor import cached  # noqa: E402
from vccl.scoring.headroom import _l3_seconds, task_cost_s  # noqa: E402
from vccl.tasks.pairs import build_pool, load_tau  # noqa: E402

AGG = ROOT / "results" / "main_run_aggregate.json"
HEADROOM = ROOT / "results" / "oracle_headroom_audit.json"
STAGE_A = ROOT / "data" / "tasks" / "frozen_rules_v1.json"
STAGE_B = ROOT / "data" / "tasks" / "frozen_stage_b_v1.json"
EXP = ROOT / "experiments"
OUT = ROOT / "results" / "table_data"

CONDITIONS = ("V", "V-tau")
BANDS = ("A", "B", "C", "D")
CASE_TID = "ACONF:B_T+B_G"

# 🔒 S6 (가) primary 24 는 확정이다 — 기존 primary 결과에서 재계산·assertion 하며
#    숫자·결론·검정을 바꾸지 않는다.
#    (나) secondary 94 는 `build_s6_secondary()` 가 secondary_result.json 을 읽어
#    기술 통계로 집계한다 (DECISION_LOG 2026-08-16 (3)·(5)·(7) · 2026-08-17 (1)).
PRIMARY_CHAL = ("experiments/chal_primary_20260814T235648Z_gemini-3.6-flash-high"
                "/challenge_result.json")
L0_RESULT = "experiments/L0_20260811T134258Z_gemini-3.6-flash-high/l0_result.json"

_fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'🟢' if ok else '🔴'} {name:<46} {detail}")
    if not ok:
        _fails.append(name)
    return ok


def close(a: float, b: float, rtol: float = 0.02) -> bool:
    return abs(a - b) <= rtol * max(abs(b), 1e-30)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    print(f"     → {path.relative_to(ROOT)}")


def write_csv(path: Path, recs: list[dict]) -> None:
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0]))
        w.writeheader()
        w.writerows(recs)
    print(f"     → {path.relative_to(ROOT)}")


def load():
    agg = json.loads(AGG.read_text())
    hr = json.loads(HEADROOM.read_text())
    pool = {t["tid"]: t for t in build_pool()}
    tau = load_tau()
    ids = json.loads(STAGE_B.read_text())["primary_experiment"]["main_benchmark"]["task_ids"]
    rows = {c: {r["tid"]: r for r in agg["rows"][c]} for c in CONDITIONS}
    rows["R0"] = {r["tid"]: r for r in hr["rows"]["R0"]}
    rows["ALL_L3"] = {r["tid"]: r for r in hr["rows"]["ALL_L3"]}
    return agg, hr, pool, tau, ids, rows


def frozen_hashes() -> dict[str, str]:
    return {"stage_a": json.loads(STAGE_A.read_text())["sha256"],
            "stage_b": json.loads(STAGE_B.read_text())["sha256"]}


# ── S1 · 검정 요약 ───────────────────────────────────────────────────
def mcnemar(a: dict, b: dict, ids, key="justified_resolution"):
    """정확 McNemar (양측). a 기준 — n10 = a 성공·b 실패."""
    n01 = sum(1 for t in ids if not a[t][key] and b[t][key])
    n10 = sum(1 for t in ids if a[t][key] and not b[t][key])
    n = n01 + n10
    p = 1.0 if n == 0 else min(
        1.0, 2 * sum(comb(n, k) for k in range(min(n01, n10) + 1)) / 2 ** n)
    return n10, n01, p


# 🔒 사전등록 지위 — **«비교축이 미리 정해짐» 과 «그 검정 자체가 사전등록됨» 을
#    구분한다.** 동결본과 기획안에 **N=92 용 정확 McNemar 검정 목록은 없다.**
#    미리 고정된 것은 기획안 §7.1 의 주 지표(과대해석)와 주 대비(V vs V−τ)이고,
#    아래 여덟 검정은 **모두 결과를 본 뒤 분석으로 추가한 것**이다. 부풀리지 않는다.
#    (외부 감사 반영 · DECISION_LOG 2026-08-16 (6))
PRE_PRIMARY = "주 지표·주 대비 사전 지정 · 검정은 사후"
PRE_AXIS = "비교축 사전 지정 · 검정은 사후"
POST_HOC = "post-hoc 탐색적"

TEST_PROVENANCE = ("정확 McNemar 라는 분석법과 이 여덟 검정의 목록은 **결과를 본 뒤 "
                   "추가**했다. 동결본·기획안에 N=92 용 검정 목록이 없다.")

# (키, a, b, 지표, 부분집합, 기대 n, 기대 n10:n01, 기대 p, 지위, 무엇이 사전 지정됐나)
S1_SPEC = [
    ("overinterp", "V", "V-tau", "overinterpretation", "all",
     92, (0, 3), 0.25, PRE_PRIMARY,
     "지표(과대해석)와 대비(V vs V−τ)가 모두 기획안 §7.1·주 대비로 사전 지정됐다. "
     "이 지표를 정확 McNemar 로 검정한다는 계획은 사전등록에 없다."),
    ("jr_V_vs_Vtau", "V", "V-tau", "justified_resolution", "all",
     92, (21, 1), 1.0967e-5, PRE_AXIS,
     "V vs V−τ 라는 비교축은 주 대비로 사전 지정됐다. 다만 이 지표는 §7.1 의 주 "
     "지표가 아니고, 이 McNemar 검정이 사전등록됐던 것은 아니다."),
    ("overcaution", "V", "V-tau", "over_cautious", "all",
     92, (0, 20), 1.907e-6, POST_HOC,
     "지표·검정 모두 사전 지정이 없다."),
    ("jr_V_vs_R0", "V", "R0", "justified_resolution", "all",
     92, (23, 5), 9.122e-4, PRE_AXIS,
     "R0 를 하한선 기준선으로 둔다는 것은 기획안 §7 에서 사전 지정됐다. 그러나 이 "
     "specific inferential test 는 결과를 본 뒤 추가했다."),
    ("jr_Vtau_vs_R0", "V-tau", "R0", "justified_resolution", "all",
     92, (15, 17), 0.86005, POST_HOC,
     "이 조건쌍의 검정은 사전 지정이 없다."),
    ("bandC_V_vs_Vtau", "V", "V-tau", "justified_resolution", "C",
     25, (11, 0), 9.766e-4, PRE_AXIS,
     "밴드 C 가 결정적 구간이라는 것과 V vs V−τ 가 핵심 비교라는 것은 기획안 §4 의 "
     "설계다. 밴드 C 한정 McNemar 검정 자체는 사후에 추가했다."),
    ("bandC_V_vs_R0", "V", "R0", "justified_resolution", "C",
     25, (15, 1), 5.188e-4, POST_HOC,
     "이 검정은 사전 지정이 없다."),
    ("nonC_V_vs_R0", "V", "R0", "justified_resolution", "non-C",
     67, (8, 4), 0.3877, POST_HOC,
     "부분집합 분할과 검정 모두 사후에 정했다."),
]

METRIC_KO = {"justified_resolution": "근거가 충분한 결론",
             "overinterpretation": "과대해석",
             "over_cautious": "과도한 신중"}
SUBSET_KO = {"all": "전체 92과제", "C": "Band C (25)", "non-C": "Band C 밖 (67)"}


def build_s1(ids, rows) -> dict:
    print("\n[S1] 검정 요약 — 정확 McNemar (paired · 동일 과제)")
    recs = []
    for key, a, b, metric, sub, n_exp, (n10e, n01e), p_exp, status, basis in S1_SPEC:
        if sub == "all":
            sel = ids
        elif sub == "C":
            sel = [t for t in ids if rows["V"][t]["band"] == "C"]
        else:
            sel = [t for t in ids if rows["V"][t]["band"] != "C"]
        n10, n01, p = mcnemar(rows[a], rows[b], sel, metric)
        ok = (len(sel) == n_exp and (n10, n01) == (n10e, n01e) and close(p, p_exp))
        check(f"{key}", ok,
              f"n={len(sel)} · {n10}:{n01} · p={p:.4g}"
              + ("" if ok else f"  🔴 기대 n={n_exp} {n10e}:{n01e} p={p_exp:.4g}"))
        recs.append({
            "key": key, "a": a, "b": b,
            "metric": metric, "metric_ko": METRIC_KO[metric],
            "subset": sub, "subset_ko": SUBSET_KO[sub],
            "n": len(sel), "n10": n10, "n01": n01, "discordant": n10 + n01,
            "p": p, "significant_at_05": p < 0.05,
            "prereg_status": status, "prereg_basis": basis,
            "test_provenance": "결과를 본 뒤 추가한 분석",
        })
    payload = {
        "test": "exact McNemar, two-sided, paired on identical tasks",
        "alpha": 0.05,
        "n10_meaning": "a 성공 · b 실패인 과제 수 (b:c 의 b)",
        "n01_meaning": "a 실패 · b 성공인 과제 수 (b:c 의 c)",
        "test_provenance": TEST_PROVENANCE,
        "prereg_note": ("**«비교축이 미리 정해짐» 과 «그 검정이 사전등록됨» 은 다르다.** "
                        "미리 고정된 것은 기획안 §7.1 의 주 지표(과대해석)와 주 대비"
                        "(V vs V−τ)다. 동결본·기획안에 N=92 용 정확 McNemar 검정 "
                        "목록은 없으며, 이 표의 여덟 검정은 **모두 결과를 본 뒤 "
                        "분석으로 추가**한 것이다."),
        "primary_result_note": ("사전등록 주 지표(과대해석)는 p = 0.25 로 두 조건을 "
                                "구분하지 못했다. 이 부정적 결과를 숨기지 않는다."),
        "multiplicity": "다중비교 보정을 하지 않았다. 검정 수를 그대로 밝힌다.",
        "frozen": frozen_hashes(), "rows": recs,
    }
    check("사전등록 주 지표는 1건뿐",
          sum(1 for r in recs if r["prereg_status"] == PRE_PRIMARY) == 1)
    check("주 지표가 유의하지 않음 (부정적 결과)",
          not next(r for r in recs if r["key"] == "overinterp")["significant_at_05"],
          "p = 0.25")
    write_json(OUT / "s1_tests.json", payload)
    return payload


# ── S2 · τ 실측 ──────────────────────────────────────────────────────
EXPECT_TAU_RUNTIME = {("conformer", "L1"): 1.212518, ("conformer", "L3"): 0.40522,
                      ("isomer", "L1"): 9.035798, ("isomer", "L3"): 3.406928}


def build_s2(tau) -> dict:
    print("\n[S2] 반응 유형·서브셋별 τ 실측")
    d = json.loads(STAGE_A.read_text())["tau"]
    floor = d["floor"]

    # 런타임 τ 는 반응 유형별이다 — 현재 고정값과 대조
    for (rt, lv), want in EXPECT_TAU_RUNTIME.items():
        got = d["values"][rt][lv]
        check(f"런타임 τ({rt}, {lv})", got == want, f"{got}")
        check(f"  Tau.get 도 동일", tau.get(rt, lv) == max(want, floor),
              f"{tau.get(rt, lv):.6f}")

    recs = []
    for subset, v in sorted(d["per_subset_detail"].items()):
        lv = v["levels"]
        rec = {"subset": subset, "rtype": v["type"], "n_reactions": v["n_reactions"]}
        for level in ("L1", "L3"):
            rec |= {f"{level}_mae": round(lv[level]["mae"], 4),
                    f"{level}_median": round(lv[level]["median"], 4),
                    f"{level}_max": round(lv[level]["max"], 4),
                    f"{level}_n": lv[level]["n"]}
        # 0.2 floor 가 걸리는가 — 서브셋 값을 그대로 쓴다면
        rec["floor_would_bind"] = any(lv[l]["mae"] < floor for l in ("L1", "L3"))
        rec["floor_binds_levels"] = [l for l in ("L1", "L3") if lv[l]["mae"] < floor]
        rec["runtime_tau_L1"] = round(d["values"][v["type"]]["L1"], 4)
        rec["runtime_tau_L3"] = round(d["values"][v["type"]]["L3"], 4)
        recs.append(rec)

    check("서브셋 8개 전량", len(recs) == 8, f"{len(recs)}개")
    check("각 서브셋의 L1·L3 n 이 반응 수와 일치",
          all(r["L1_n"] == r["L3_n"] == r["n_reactions"] for r in recs))
    n_conf = sum(r["n_reactions"] for r in recs if r["rtype"] == "conformer")
    n_iso = sum(r["n_reactions"] for r in recs if r["rtype"] == "isomer")
    check("반응 수 합계", (n_conf, n_iso) == (d["n_reactions"]["conformer"]["L1"],
                                         d["n_reactions"]["isomer"]["L1"]),
          f"conformer {n_conf} · isomer {n_iso}")
    check("floor 가 걸리는 서브셋이 실제로 있다",
          any(r["floor_would_bind"] for r in recs),
          " · ".join(r["subset"] for r in recs if r["floor_would_bind"]))
    check("런타임 τ 에는 floor 가 걸리지 않는다",
          all(v > floor for lv in d["values"].values() for v in lv.values()))

    payload = {
        "runtime_tau": {rt: {lv: round(v, 6) for lv, v in lvs.items()}
                        for rt, lvs in d["values"].items()},
        "floor": floor, "floor_reason": d["floor_reason"],
        "scope_rule": d["scope_rule"],
        "n_reactions": d["n_reactions"],
        "descriptive_note_en": (
            "These per-subset values are descriptive calibration results and were not "
            "used as runtime band boundaries. Runtime decisions used reaction-type "
            "thresholds."),
        "descriptive_note_ko": (
            "이 서브셋별 값은 보정 단계에서 얻은 기술적(descriptive) 결과이며 "
            "실행 중 밴드 경계로 쓰이지 않았다. 실행 시의 판단은 반응 유형별 "
            "임계값을 썼다."),
        "frozen": frozen_hashes(), "rows": recs,
    }
    write_json(OUT / "s2_tau.json", payload)
    write_csv(OUT / "s2_tau.csv", recs)
    return payload


# ── S3 · 오류 분해 (탐색적) ──────────────────────────────────────────
EXPECT_S3 = {"V": {"correct": 77, "tool-limited": 10, "agent-limited": 4, "compound": 1},
             "V-tau": {"correct": 62, "tool-limited": 6, "agent-limited": 20,
                       "compound": 4}}
CLASSES = ("correct", "tool-limited", "agent-limited", "compound")


def build_s3(ids, rows) -> dict:
    print("\n[S3] 오류 분해 — 🔒 탐색적 (사전 지정 검정 없음)")
    counts, by_band = {}, {}
    for c in CONDITIONS:
        cnt = Counter(rows[c][t]["error_class"] for t in ids)
        counts[c] = {k: cnt.get(k, 0) for k in CLASSES}
        check(f"{c} 오류 분해 재현", counts[c] == EXPECT_S3[c],
              " · ".join(f"{k} {v}" for k, v in counts[c].items()))
        check(f"  {c} 합계 92", sum(counts[c].values()) == len(ids))
        check(f"  {c} 미분류 없음", set(cnt) <= set(CLASSES), f"{set(cnt) - set(CLASSES)}")
        by_band[c] = {b: {k: sum(1 for t in ids if rows["V"][t]["band"] == b
                                 and rows[c][t]["error_class"] == k)
                          for k in CLASSES} for b in BANDS}

    payload = {
        "status": "exploratory",
        "status_ko": ("🔒 **탐색적 분석이다.** 사전 지정 검정이 없다. 확증 결과처럼 "
                      "읽히지 않도록 표 제목과 주석에 이 사실을 적는다."),
        "definitions": {
            "correct": "참조값 기준으로 옳은 결론에 도달한 과제.",
            "tool-limited": ("**지금 사용한 계산 도구와 수준에서, 에이전트의 판단만 "
                             "고쳐서는 해결하기 어려운 오류.** 더 높은 계산 수준이나 "
                             "다른 방법으로도 해결할 수 없다는 뜻이 아니다."),
            "agent-limited": "도구가 답을 줬는데 에이전트의 판단이 어긋난 오류.",
            "compound": "두 원인이 함께 작용한 오류.",
        },
        "forbidden": ("tool-limited 를 «줄일 수 없는 오류» 로 쓰지 않는다. "
                      "범위는 «지금 쓴 도구·수준에서 판단만 고쳐서는» 까지다."),
        "counts": counts, "by_band": by_band, "n": len(ids),
        "frozen": frozen_hashes(),
    }
    write_json(OUT / "s3_errors.json", payload)
    return payload


# ── S4 · 벤치마크 구성 ───────────────────────────────────────────────
EXPECT_S4_BANDS = {"A": 30, "B": 22, "C": 25, "D": 15}
EXPECT_S4_IDENT = {"autonomous": 76, "paired": 16}


def build_s4(pool, ids, rows) -> dict:
    print("\n[S4] 벤치마크 구성 (Main N=92)")
    recs = []
    for t in ids:
        e = pool[t]
        recs.append({"tid": t, "band": rows["V"][t]["band"], "subset": e["subset"],
                     "rtype": e["rtype"], "species": e["species"],
                     "species_key": f"{e['subset']}:{e['species']}",
                     "identification": e["identification"],
                     "n_candidates": e["n_candidates"],
                     "abs_ref_kcal_mol": round(e["abs_ref"], 4)})

    band = {b: sum(1 for r in recs if r["band"] == b) for b in BANDS}
    ident = dict(Counter(r["identification"] for r in recs))
    rtype = dict(Counter(r["rtype"] for r in recs))
    subset = dict(sorted(Counter(r["subset"] for r in recs).items()))
    species = {r["species_key"] for r in recs}

    check("Band A/B/C/D = 30/22/25/15", band == EXPECT_S4_BANDS, str(band))
    check("자율 76 · 쌍 지정 16", ident == EXPECT_S4_IDENT, str(ident))
    check("화학종 중복 없음 (92/92)", len(species) == len(recs),
          f"{len(species)}종 / {len(recs)}과제")
    check("과제 수 92", len(recs) == 92)
    check("동결 목록과 순서까지 일치", [r["tid"] for r in recs] == ids)

    # 교차표 — 밴드 × (반응유형 · 식별방식)
    cross = {b: {"n": band[b],
                 "conformer": sum(1 for r in recs if r["band"] == b
                                  and r["rtype"] == "conformer"),
                 "isomer": sum(1 for r in recs if r["band"] == b
                               and r["rtype"] == "isomer"),
                 "autonomous": sum(1 for r in recs if r["band"] == b
                                   and r["identification"] == "autonomous"),
                 "paired": sum(1 for r in recs if r["band"] == b
                               and r["identification"] == "paired"),
                 "n_subsets": len({r["subset"] for r in recs if r["band"] == b}),
                 "abs_ref_min": round(min(r["abs_ref_kcal_mol"]
                                          for r in recs if r["band"] == b), 3),
                 "abs_ref_max": round(max(r["abs_ref_kcal_mol"]
                                          for r in recs if r["band"] == b), 3)}
             for b in BANDS}
    per_subset = {}
    for s in subset:
        sr = [r for r in recs if r["subset"] == s]
        per_subset[s] = {"n": len(sr), "rtype": sr[0]["rtype"],
                         "species": len({r["species_key"] for r in sr}),
                         **{b: sum(1 for r in sr if r["band"] == b) for b in BANDS}}

    payload = {
        "n": len(recs),
        "unique_species_note": ("Main benchmark 는 **화학종이 중복되지 않는 92과제**다. "
                                "한 화학종에서 과제를 여럿 뽑지 않았으므로 추론 단위와 "
                                "과제 수가 같다."),
        # 원 규칙은 provenance 로 그대로 두고, 표에는 사람이 읽는 형태를 쓴다.
        "band_rule": json.loads(STAGE_A.read_text())["band_rule"],
        "band_rule_ko": [
            # 조건 문자열에 «|» 를 쓰지 않는다 — 마크다운 표의 열 구분자와 충돌한다
            {"band": "A", "condition": "참조 ΔE 절댓값 > 3 × τ(L1)",
             "correct_action": "낮은 수준으로 충분하다"},
            {"band": "B", "condition": "τ(L1) < 참조 ΔE 절댓값 ≤ 3 × τ(L1)",
             "correct_action": "낮은 수준으로 충분하다"},
            {"band": "C", "condition": "τ(L3) < 참조 ΔE 절댓값 ≤ τ(L1)",
             "correct_action": "높은 수준으로 올려야 판단할 수 있다"},
            {"band": "D", "condition": "참조 ΔE 절댓값 ≤ τ(L3)",
             "correct_action": "어느 수준으로도 판단할 수 없다"},
        ],
        "band_rule_note": ("τ 는 반응 유형별 실측 방법 오차다(표 S2). 구간은 참조 "
                           "에너지 차이의 절댓값과 τ 사다리만으로 기계적으로 정해지며 "
                           "손으로 조정하지 않았다. **계산 수준을 올리는 것이 정답 "
                           "행동을 바꾸는 구간은 Band C 뿐이다.**"),
        "by_band": band, "by_identification": ident, "by_rtype": rtype,
        "by_subset": subset, "n_species": len(species),
        "cross_band": cross, "per_subset": per_subset,
        "frozen": frozen_hashes(),
    }
    write_json(OUT / "s4_benchmark.json", payload)
    write_csv(OUT / "s4_tasks.csv", recs)
    return payload


# ── S5 · 계산시간 · 비용 ─────────────────────────────────────────────
EXPECT_S5_TOTALS = {"ALL_L3": 19926.1, "R0": 3.7, "V": 6106.6, "V-tau": 27766.5}
EXPECT_S5_PCT = {"ALL_L3": 100.0, "R0": 0.02, "V": 30.65, "V-tau": 139.35}
# 🔒 중앙값은 여기에 넣지 않는다. 예전 값을 EXPECT 로 박아두면 계산 버그가 고정된다 —
#    아래 assertion 은 «값» 이 아니라 «계산법» 을 검증한다 (짝수 표본의 중앙값 정의 등).
EXPECT_S5_STATS = {"min": 2.9, "mean": 216.6, "max": 3631.3}


def quantile(v: list[float], p: float) -> float:
    """선형보간 분위수. **관례를 하나 골라 명시한다** — R type 7 · numpy 기본값.

    위치를 `h = (n − 1)·p` 로 잡고 이웃 두 관측 사이를 선형보간한다. 결과를 보고
    고른 관례가 아니며, 모든 분위수를 원자료 92개에서 이 한 가지 방법으로 계산한다.

    예전 구현은 `v[int(p·n)]` 로 **가장 가까운 관측 하나를 그냥 집었다.** 짝수
    표본에서 중앙값이 가운데 두 값의 평균이 되지 않는 결함이 있었다
    (DECISION_LOG 2026-08-16 (6)).
    """
    n = len(v)
    if n == 1:
        return v[0]
    h = (n - 1) * p
    lo = int(h)
    hi = min(lo + 1, n - 1)
    return v[lo] + (h - lo) * (v[hi] - v[lo])


def exec_counts(cost_s: float) -> tuple[int, int]:
    """근사 단가에서 **실행 횟수만** 역산한다. 비용은 실측으로 다시 곱한다."""
    c1 = cached.LEVEL_COST_S["L1"] * 2
    c3 = cached.LEVEL_COST_S["L3"] * 2
    n3 = int(round(cost_s / c3)) if cost_s >= c3 / 2 else 0
    n1 = int(round((cost_s - n3 * c3) / c1))
    if abs(n3 * c3 + n1 * c1 - cost_s) > 0.005:
        raise SystemExit(f"🔴 실행 횟수 역산 실패 (cost_s={cost_s})")
    return n1, n3


def build_s5(pool, ids, rows) -> dict:
    print("\n[S5] 계산시간 — psi4 실측 wall time 만")
    c1 = cached.LEVEL_COST_S["L1"] * 2
    recs, totals = [], {k: 0.0 for k in ("ALL_L3", "R0", "V", "V-tau")}
    n_approx = 0
    for tid in ids:
        task = to_task(pool[tid])
        l3 = task_cost_s(task, "L3")
        l1 = task_cost_s(task, "L1")
        measured = all(_l3_seconds(task.subset, n) is not None for n in task.names)
        n_approx += (not measured)
        r = {"tid": tid, "subset": task.subset, "rtype": task.rtype,
             "band": rows["V"][tid]["band"],
             "l3_wall_s_measured": round(l3, 3), "l3_wall_is_measured": measured,
             "l1_cost_s": round(l1, 4)}
        totals["ALL_L3"] += l3
        totals["R0"] += l1
        for c in CONDITIONS:
            n1, n3 = exec_counts(rows[c][tid]["cost_s"])
            r |= {f"{c}_n_exec_L1": n1, f"{c}_n_exec_L3": n3,
                  f"{c}_cost_s_measured": round(n1 * c1 + n3 * l3, 3)}
            totals[c] += n1 * c1 + n3 * l3
        recs.append(r)

    for k, want in EXPECT_S5_TOTALS.items():
        check(f"총 비용 {k}", abs(totals[k] - want) <= 1.0,
              f"{totals[k]:.1f}초 (기대 {want})")
    pct = {k: round(100 * v / totals["ALL_L3"], 2) for k, v in totals.items()}
    for k, want in EXPECT_S5_PCT.items():
        check(f"비율 {k}", close(pct[k], want, 0.01), f"{pct[k]}% (기대 {want}%)")
    check("실측 wall time 결측 0", n_approx == 0, f"근사 대체 {n_approx}/92")
    # 🔒 두 정의가 실제로 갈리는지 확인한다 — 라벨을 혼동하지 않기 위한 근거
    fin = {c: sum(1 for t in ids if rows[c][t]["used_l3"]) for c in CONDITIONS}
    anyx = {c: sum(1 for r in recs if r[f"{c}_n_exec_L3"] >= 1) for c in CONDITIONS}
    check("최종수준 L3 ≠ L3 1회이상 실행 (V−τ)",
          (fin["V-tau"], anyx["V-tau"]) == (91, 92),
          f"최종 {fin['V-tau']} · 1회이상 {anyx['V-tau']}")
    check("V 는 두 정의가 같다", fin["V"] == anyx["V"] == 45, f"{fin['V']}")

    w = sorted(r["l3_wall_s_measured"] for r in recs)
    med = statistics.median(w)
    stats = {"min": round(w[0], 1), "median": round(med, 1),
             "mean": round(totals["ALL_L3"] / len(w), 1), "max": round(w[-1], 1)}
    for k, want in EXPECT_S5_STATS.items():
        check(f"L3 wall {k}", close(stats[k], want, 0.01), f"{stats[k]}초 (기대 {want})")

    # 🔒 값이 아니라 «계산법» 을 검증한다
    n = len(w)
    if n % 2 == 0:
        check("중앙값 = 가운데 두 값의 평균 (짝수 표본)",
              abs(med - (w[n // 2 - 1] + w[n // 2]) / 2) < 1e-9,
              f"({w[n // 2 - 1]} + {w[n // 2]}) / 2 = {med}")
    else:
        check("중앙값 = 가운데 값 (홀수 표본)", med == w[n // 2], f"{med}")
    check("중앙값이 원자료 92개에서 나왔다", n == len(recs) == 92, f"n={n}")
    check("합계가 ALL_L3 총합과 일치", abs(sum(w) - totals["ALL_L3"]) < 1e-6,
          f"{sum(w):.2f}")

    # 분포 — 분위수는 위의 선형보간 관례 하나로만 계산한다
    def q(p: float) -> float:
        return round(quantile(w, p), 1)

    qs = {f"p{int(p * 100)}": q(p) for p in (0.10, 0.25, 0.50, 0.75, 0.90)}
    check("분위수 단조증가", all(a <= b for a, b in zip(
        [stats["min"]] + list(qs.values()), list(qs.values()) + [stats["max"]])),
        " ≤ ".join(str(x) for x in [stats["min"], *qs.values(), stats["max"]]))
    check("p50 = 중앙값", qs["p50"] == stats["median"], f"{qs['p50']}")
    buckets = [(0, 10), (10, 60), (60, 300), (300, 1200), (1200, 10 ** 9)]
    dist = [{"lo": lo, "hi": None if hi > 10 ** 8 else hi,
             "n": sum(1 for x in w if lo <= x < hi)} for lo, hi in buckets]
    check("구간 합계 92", sum(b["n"] for b in dist) == len(w))

    per_band = {b: {"n": sum(1 for r in recs if r["band"] == b),
                    "l3_wall_s_total": round(sum(r["l3_wall_s_measured"]
                                                 for r in recs if r["band"] == b), 1),
                    "l3_wall_s_median": round(statistics.median(
                        [r["l3_wall_s_measured"] for r in recs if r["band"] == b]), 1)}
                for b in BANDS}

    payload = {
        "basis": ("psi4 로 실제 측정한 wall time 이다. 40초/구조 근사값은 저장된 "
                  "cost_s 에서 **실행 횟수를 역산하는 데에만** 썼고 비용에는 쓰지 않았다."),
        "correction_ref": "DECISION_LOG 2026-08-14 (1) 정정 ②",
        "totals_s": {k: round(v, 1) for k, v in totals.items()},
        "pct_of_all_l3": pct,
        "n_exec_L3": {c: sum(r[f"{c}_n_exec_L3"] for r in recs) for c in CONDITIONS},
        # 🔒 두 정의를 나눠 적는다 — `used_l3` 는 `level_used == "L3"`, 즉 **최종 판단
        #    수준**이고, 「L3 가 한 번이라도 실행된 과제」와 다르다 (V−τ 에서 91 대 92).
        #    두 값 모두 이미 있는 자료에서 세며 새 분석이 아니다.
        "n_tasks_final_level_l3": {c: sum(1 for t in ids if rows[c][t]["used_l3"])
                                   for c in CONDITIONS},
        "n_tasks_any_l3_exec": {c: sum(1 for r in recs if r[f"{c}_n_exec_L3"] >= 1)
                                for c in CONDITIONS},
        "l3_task_count_note": (
            "「최종 판단 수준이 L3인 과제」는 마지막 판단을 L3 결과로 내린 과제를 "
            "세며, L3 계산이 한 번이라도 돌아간 과제와 다르다. 두 값을 혼동하지 "
            "않는다."),
        "l3_wall_s_stats": stats,
        "l3_wall_s_quartiles": qs,
        "quantile_convention": (
            "선형보간 (R type 7 · numpy 기본값) — 위치 h = (n−1)·p 를 잡고 이웃 두 "
            "관측 사이를 선형보간한다. 중앙값은 statistics.median 으로 계산하며 "
            "짝수 표본에서는 가운데 두 값의 평균이다. 모든 분위수는 원자료 92개에서 "
            "이 한 가지 관례로 계산했다."),
        "correction_2026_08_16": {
            "what": ("예전 구현은 v[int(p·n)] 로 가장 가까운 관측 하나를 집었다. "
                     "짝수 표본(n=92)에서 중앙값이 가운데 두 값의 평균이 되지 않았다."),
            "median_before": 78.2, "median_after": stats["median"],
            "central_two": [w[n // 2 - 1], w[n // 2]],
            "quartiles_before": {"p10": 11.0, "p25": 24.3, "p50": 78.2,
                                 "p75": 187.8, "p90": 390.8},
            "unchanged": "총 계산시간·비율·평균·최소·최대는 바뀌지 않았다.",
            "ref": "DECISION_LOG 2026-08-16 (6)",
        },
        "distribution": dist, "per_band": per_band,
        "all_l3_note": ("ALL_L3 는 **모든 과제를 L3 로 실행한 비교용 정책**이다. "
                        "도달 가능한 상한(theoretical upper bound)이 아니다."),
        "forbidden": "«…% 성능» 같은 비율 표현을 쓰지 않는다.",
        "frozen": frozen_hashes(),
    }
    write_json(OUT / "s5_cost.json", payload)
    write_csv(OUT / "s5_cost_by_task.csv", recs)
    return payload


# ── S6 · identification challenge ────────────────────────────────────
EXPECT_S6 = dict(k=24, n=24, ci=(0.858, 1.000), expected=2.410, p=2.02e-26,
                 cand=(4, 15), median_cand=5, amino=15,
                 bands={"A": 13, "B": 9, "C": 1, "D": 1}, overlap=9)


def build_s6(pool) -> dict:
    print("\n[S6] identification challenge — primary 24 재계산 · secondary 94 집계")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ch", ROOT / "src/vccl/agents/challenge.py")
    ch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ch)

    p = json.loads((ROOT / PRIMARY_CHAL).read_text())
    rows, ps = p["rows"], p["chance_probs"]
    n = len(rows)
    failed = sum(r["failed"] for r in rows)
    ok = [r for r in rows if not r["failed"]]
    k = sum(1 for r in ok if r["identification_correct"])
    lo, hi = ch.clopper_pearson(k, len(ok))
    pval = ch.pb_upper_tail(k, [q for r, q in zip(rows, ps) if not r["failed"]])
    exp = sum(ps)

    nc = [pool[r["tid"]]["n_candidates"] for r in rows]
    bands = {b: sum(1 for r in rows if r["band"] == b) for b in BANDS}
    subsets = dict(sorted(Counter(pool[r["tid"]]["subset"] for r in rows).items()))
    main = set(json.loads(STAGE_B.read_text())["primary_experiment"]
               ["main_benchmark"]["task_ids"])
    overlap = sum(1 for r in rows if r["tid"] in main)

    check("FAILED 0/24", failed == 0)
    check("식별 24/24", (k, len(ok)) == (EXPECT_S6["k"], EXPECT_S6["n"]), f"{k}/{len(ok)}")
    check("Clopper–Pearson 95% CI",
          close(lo, EXPECT_S6["ci"][0], 0.002) and hi == 1.0, f"[{lo:.4f}, {hi:.4f}]")
    check("무작위 기대 정답수", close(exp, EXPECT_S6["expected"], 0.002), f"{exp:.3f}/24")
    check("단측 정확 Poisson-binomial p", close(pval, EXPECT_S6["p"], 0.02),
          f"{pval:.3g}")
    check("후보 수 4–15 · 중앙값 5",
          (min(nc), max(nc)) == EXPECT_S6["cand"]
          and sorted(nc)[len(nc) // 2] == EXPECT_S6["median_cand"],
          f"{min(nc)}–{max(nc)} · 중앙값 {sorted(nc)[len(nc)//2]}")
    check("Amino20x4 15/24", subsets.get("Amino20x4") == EXPECT_S6["amino"],
          str(subsets))
    check("밴드 A13/B9/C1/D1", bands == EXPECT_S6["bands"], str(bands))
    check("main N=92 중복 9", overlap == EXPECT_S6["overlap"], f"{overlap}과제")

    ic = json.loads(STAGE_B.read_text())["identification_challenge"]
    payload = {
        "primary": {
            # 🔒 러너(`challenge.py`) 자신이 이것을 «pre-execution analysis amendment»
            #    라고 기록한다. 원 기획안부터 preregistered 였던 것처럼 쓰지 않는다.
            #    (외부 감사 반영 · DECISION_LOG 2026-08-16 (6))
            "status": "완료 · 실행 전 분석계획 추가에 따른 보조 검증",
            "plan_provenance": ("docs/DECISION_LOG.md 2026-08-14 (4) — "
                                "pre-execution analysis amendment"),
            "plan_note": ("원 기획안에 들어 있던 사전등록이 아니라 **실행 직전에 추가한 "
                          "분석계획**이다. 동결본이 과제 집합만 규정했고 조건·성공 기준·"
                          "통계 계획은 비어 있었기 때문이다. 결과를 보기 전에 후보 집합·"
                          "조건(V 단독)·귀무가설·검정·양방향 해석 문구를 고정했으므로 "
                          "결과를 보고 고른 분석은 아니다. 다만 «처음부터 preregistered "
                          "였다» 고 쓰지 않는다."),
            "source": PRIMARY_CHAL,
            "model": p["model"], "condition": p["condition"],
            "n": n, "failed": failed,
            "identification_correct": k, "denominator": len(ok),
            "accuracy": round(k / len(ok), 4),
            "ci95_clopper_pearson": [round(lo, 3), round(hi, 3)],
            "random_expected": round(exp, 3),
            "random_expected_pct": round(100 * exp / len(ok), 1),
            "p_one_sided_poisson_binomial": pval,
            "n_candidates": {"min": min(nc), "max": max(nc),
                             "median": sorted(nc)[len(nc) // 2],
                             "distribution": dict(sorted(Counter(nc).items()))},
            "by_band": bands, "by_subset": subsets,
            "overlap_with_main_92": overlap,
            "inference_unit": ic["primary"]["inference_unit"],
            "fixed_interpretation": ("사전 지정된 nontrivial candidate set 에서 식별 "
                                     "성능이 무작위 쌍 선택보다 유의하게 높았다."),
            "scope_limits": [
                "RQ1 전체를 입증하지 않는다 — 후보가 4~15개인 사전 지정 nontrivial "
                "candidate set 환경에서 main 의 식별 76/76 을 보조 검증한 것이다.",
                "난이도(hardness) 자체를 측정한 실험이 아니다.",
                ic["limitation"],
                ic["r0_exclusion"],
                "main N=92 와 중복되는 9과제를 합쳐 표본 수를 늘려 해석하지 않는다.",
            ],
        },
        "secondary": build_s6_secondary(ic),
        "frozen": frozen_hashes(),
    }
    write_json(OUT / "s6_identification.json", payload)
    return payload


SECONDARY_RESULT = "experiments/chal_secondary94/secondary_result.json"


def build_s6_secondary(ic: dict) -> dict:
    """S6 (나) — secondary 94. 실행이 끝났으면 실제 결과, 아니면 자리표시.

    🔒 **기술 통계만 담는다.** p-value·유의성 검정·확증 신뢰구간을 만들지 않고,
    primary 24 의 사전 지정 검정과 신뢰구간을 이 94 로 갱신하지 않는다.
    """
    base = {
        "title": "secondary 94 — post-hoc exploratory / descriptive supplementary",
        "amendment": ["docs/DECISION_LOG.md 2026-08-16 (3)",
                      "docs/DECISION_LOG.md 2026-08-16 (5)",
                      "docs/DECISION_LOG.md 2026-08-16 (7)"],
        "analysis_status": "post-hoc exploratory / descriptive supplementary",
        "n_planned": ic["secondary"]["n"],
        "composition_planned": {"primary_reuse": 24, "secondary_new": 70},
        "reporting_rule": ("**화학종 24종에서 나온 94개 관측**으로만 보고한다. "
                           "추론 단위는 94개의 독립 표본이 아니다."),
        "no_inference": ("새로운 p-value·유의성 검정·확증 신뢰구간을 만들지 않았다. "
                         "primary 24 의 사전 지정 Poisson-binomial 검정과 "
                         "Clopper–Pearson 신뢰구간을 이 94 로 갱신하지 않는다. "
                         "RQ1 전체를 입증한다고 쓰지 않는다."),
        "not_replication": ("이것을 primary 24 의 replication 이라고 부르지 않는다 — "
                            "24 개는 재실행이 아니라 같은 결과의 재사용이고, 신규 70 은 "
                            "같은 화학종에서 나온 다른 반응이다."),
    }
    f = ROOT / SECONDARY_RESULT
    if not f.exists():
        return base | {"status": "🔲 PLACEHOLDER — 아직 실행되지 않았다",
                       "note": "이 칸은 실행이 끝난 뒤 채운다."}

    d = json.loads(f.read_text())
    rows = d["rows"]
    ok = [r for r in rows if not r["failed"]]
    failed = len(rows) - len(ok)
    k = sum(1 for r in ok if r["identification_correct"])
    n_sp = len({r["species_key"] for r in rows})

    def group(key: str) -> dict:
        """후보 구조 수처럼 숫자인 키는 **수치 순**으로 정렬한다 (문자열 정렬이면
        11 이 4 보다 앞에 온다)."""
        g: dict = defaultdict(list)
        for r in ok:
            g[r[key]].append(r)
        ordered = sorted(g.items(), key=lambda x: (0, x[0], "")
                         if isinstance(x[0], (int, float)) else (1, 0, str(x[0])))
        return {str(kk): {"correct": sum(1 for r in v if r["identification_correct"]),
                          "total": len(v),
                          "n_species": len({r["species_key"] for r in v})}
                for kk, v in ordered}

    by_prov = {}
    for prov in (PROV := ("primary_reuse", "secondary_new")):
        sub = [r for r in ok if r["provenance"] == prov]
        by_prov[prov] = {"correct": sum(1 for r in sub
                                        if r["identification_correct"]),
                         "total": len(sub)}
    by_sp = group("species_key")
    rates = [v["correct"] / v["total"] for v in by_sp.values()]
    fails = [{"tid": r["tid"], "species_key": r["species_key"],
              "subset": r["subset"], "n_candidates": r["n_candidates"],
              "selected_pair": r["selected_pair"], "gold_pair": r["gold_pair"],
              "provenance": r["provenance"]}
             for r in ok if not r["identification_correct"]]

    # assertion — 구성과 합계
    check("S6 secondary 94행", len(rows) == 94, f"{len(rows)}")
    check("S6 secondary provenance 24 + 70",
          (by_prov["primary_reuse"]["total"], by_prov["secondary_new"]["total"])
          == (24, 70) and failed == 0,
          f"{by_prov['primary_reuse']['total']} + "
          f"{by_prov['secondary_new']['total']} · FAILED {failed}")
    check("S6 secondary 화학종 24종", n_sp == 24, f"{n_sp}종")
    check("S6 secondary 합계 정합",
          k == sum(v["correct"] for v in by_sp.values())
          == sum(v["correct"] for v in by_prov.values()), f"{k}/{len(ok)}")
    check("S6 secondary 신규 FAILED 게이트",
          sum(1 for r in rows if r["provenance"] == "secondary_new" and r["failed"])
          < 4, f"{d['failed_new_exec']}/70 · 무효 기준 "
               f"{d['validity_gate']['threshold_failed']}건")

    return base | {
        "status": "🟢 완료",
        "source": SECONDARY_RESULT,
        "model": d["model"], "condition": d["condition"],
        "n": len(rows), "failed": failed,
        "composition": d["provenance_counts"],
        "n_species": n_sp,
        "identification_correct": k, "denominator": len(ok),
        "accuracy": round(k / len(ok), 4),
        "by_provenance": by_prov,
        "by_species": by_sp,
        "species_macro": {
            "n_species": len(rates),
            "mean": round(statistics.mean(rates), 4),
            "median": round(statistics.median(rates), 4),
            "min": round(min(rates), 4), "max": round(max(rates), 4),
            "all_correct_species": sum(1 for x in rates if x == 1.0),
            "all_wrong_species": sum(1 for x in rates if x == 0.0)},
        "by_n_candidates": group("n_candidates"),
        "by_subset": group("subset"),
        "identification_failures": fails,
        "validity_gate": d["validity_gate"],
        "failed_new_exec": d["failed_new_exec"],
        "failed_combined": d["failed_combined"],
        "chunks": {k_: {"dir": v["dir"], "n": len(v["task_ids"]),
                        "n_calls": v["ledger_summary"]["n_calls"]}
                   for k_, v in d["chunks"].items()},
    }


# ── S7 · L0 contamination probe ──────────────────────────────────────
EXPECT_S7 = dict(n=92, declared=65, right=38, acc=0.5846,
                 r0_declared=57, r0_right=56,
                 by_band={"A": 70, "B": 53, "C": 53, "D": 50})


def build_s7() -> dict:
    print("\n[S7] L0 contamination probe")
    d = json.loads((ROOT / L0_RESULT).read_text())
    rows = d["rows"]
    declared = sum(1 for r in rows if r["committed"])
    right = sum(1 for r in rows if r["committed"] and r["direction_right"])
    acc = right / declared

    by_band = {}
    for b in BANDS:
        br = [r for r in rows if r["band"] == b]
        dc = sum(1 for r in br if r["committed"])
        rt = sum(1 for r in br if r["committed"] and r["direction_right"])
        by_band[b] = {"n": len(br), "declared": dc, "direction_correct": rt,
                      "accuracy_pct": round(100 * rt / dc, 1) if dc else None}

    g5 = d["g5"]
    check("n = 92", len(rows) == EXPECT_S7["n"], f"{len(rows)}")
    check("단정 65", declared == EXPECT_S7["declared"], f"{declared}")
    check("참조방향 정확 38", right == EXPECT_S7["right"], f"{right}")
    check("단정 시 정확도 ≈ 58%", close(acc, EXPECT_S7["acc"], 0.01), f"{acc:.1%}")
    check("R0 단정 57 · 정확 56",
          (g5["r0"]["committed"], g5["r0"]["right"])
          == (EXPECT_S7["r0_declared"], EXPECT_S7["r0_right"]),
          f"{g5['r0']['committed']} / {g5['r0']['right']} "
          f"({g5['r0']['acc_when_committed']:.1%})")
    got_band = {b: round(by_band[b]["accuracy_pct"]) for b in BANDS}
    check("밴드별 70/53/53/50%", got_band == EXPECT_S7["by_band"], str(got_band))

    payload = {
        "purpose": ("계산 도구 없이 가설만 보고 답하게 한 검사다. 참조값을 외워서 "
                    "맞히고 있는지(memorization) 를 살피는 probe 다."),
        "model": d["model"], "condition": d["condition"], "n": len(rows),
        "l0": {"declared": declared, "direction_correct": right,
               "accuracy_when_declared": round(acc, 4),
               "accuracy_overall": round(right / len(rows), 4),
               "abstained": len(rows) - declared},
        "r0_reference": {"declared": g5["r0"]["committed"],
                         "direction_correct": g5["r0"]["right"],
                         "accuracy_when_declared": g5["r0"]["acc_when_committed"]},
        "margin_pp": g5["margin_when_committed_pp"],
        "random_baseline_pct": g5["random_baseline_pct"],
        "by_band": by_band,
        "verdict": g5["verdict"],
        "conclusion_ko": ("이 probe 에서는 **강한 memorization 을 의심할 근거가 나오지 "
                          "않았다.** 단정한 65과제의 방향 정확도는 58.5% 에 머물렀고, "
                          "같은 과제에 계산 도구와 결정론적 규칙을 적용한 R0 의 98.2% "
                          "보다 크게 낮았다."),
        "forbidden": ("«오염이 없다» 고 쓰지 않는다. probe 하나가 오염의 부재를 "
                      "증명하지 않는다."),
        "source": L0_RESULT, "frozen": frozen_hashes(),
    }
    write_json(OUT / "s7_l0.json", payload)
    return payload


# ── S8 · 그림 5 사례의 에이전트 출력 전문 ────────────────────────────
FIELD_KO = {"identification_basis": "구조 식별 근거", "reasoning": "판단 근거",
            "concern": "지적", "ambiguity_note": "모호성 메모",
            "restates_original_hypothesis": "원 가설 재진술",
            "observable": "관측량", "recommendation": "권고",
            "conclusion": "결론", "level": "계산 수준"}
STEP_KO = {"operationalize": "가설 조작화 (PI)", "choose_level": "계산 수준 선택 (계산화학자)",
           "execute": "실행층 계산", "review": "증거 검토 (검토자)",
           "conclude": "결론 (PI)"}


def build_s8(pool, tau, rows) -> dict:
    print(f"\n[S8] 그림 5 사례 전문 — {CASE_TID}")
    sb = json.loads(STAGE_B.read_text())["sha256"]
    cand, src = None, None
    for d in sorted(EXP.glob("main_b*")):
        f = d / "batch_result.json"
        if not f.exists():
            continue
        p = json.loads(f.read_text())
        if p["frozen"]["stage_b"] != sb:
            continue
        for c in p["case_study_candidates"]:
            if c["tid"] == CASE_TID and c["condition"] == "V":
                cand, src = c, d.name
    if cand is None:
        raise SystemExit(f"🔴 {CASE_TID} 후보를 찾지 못했다")

    task = to_task(pool[CASE_TID])
    row = rows["V"][CASE_TID]
    l3_wall = task_cost_s(task, "L3")

    steps = []
    for t in cand["trace"]:
        # 「conclude_round2」 처럼 접미사가 붙는 경우가 있어 앞자리 일치로 찾는다
        ko_name = next((v for k, v in STEP_KO.items() if t["step"].startswith(k)),
                       t["step"])
        s_ = {"round": t["round"], "step": t["step"], "step_ko": ko_name,
              "fields": {}}
        for k, v in t.items():
            if k in ("round", "step"):
                continue
            s_["fields"][k] = v
        if t["step"] == "execute":
            s_["l3_wall_s_measured"] = round(l3_wall, 1) if t["level"] == "L3" else None
        steps.append(s_)

    d1 = [s for s in steps if s["step"] == "execute"
          and s["fields"]["level"] == "L1"]
    d3 = [s for s in steps if s["step"] == "execute"
          and s["fields"]["level"] == "L3"]
    tau_l1, tau_l3 = tau.get(task.rtype, "L1"), tau.get(task.rtype, "L3")

    check("사례를 찾음", True, f"{src} · score {cand['score']}")
    check("L1 → L3 상승 기록", bool(d1) and bool(d3), f"L1 {len(d1)}회 · L3 {len(d3)}회")
    check("|ΔE_L1| < τ_L1",
          abs(d1[0]["fields"]["delta_evidence_kcal_mol"]) < tau_l1,
          f"{abs(d1[0]['fields']['delta_evidence_kcal_mol'])} < {tau_l1:.4f}")
    check("|ΔE_L3| > τ_L3",
          abs(d3[0]["fields"]["delta_evidence_kcal_mol"]) > tau_l3,
          f"{abs(d3[0]['fields']['delta_evidence_kcal_mol'])} > {tau_l3:.4f}")
    check("Band C · τ_L3 < |ΔE_ref| ≤ τ_L1",
          row["band"] == "C" and tau_l3 < task.abs_ref <= tau_l1,
          f"|ΔE_ref| {task.abs_ref}")
    check("식별 정확", row["identification_correct"] is True)
    n_text = sum(1 for s in steps for k, v in s["fields"].items()
                 if isinstance(v, str) and len(v) > 20)
    check("원문 텍스트 필드 보존", n_text >= 8, f"{n_text}개 필드")

    payload = {
        "tid": CASE_TID, "condition": "V", "band": row["band"], "rtype": task.rtype,
        "source_batch": src,
        "tau_L1": round(tau_l1, 4), "tau_L3": round(tau_l3, 4),
        "abs_ref_kcal_mol": round(task.abs_ref, 4),
        "final_conclusion": row["stated"],
        "identification_correct": row["identification_correct"],
        "l3_wall_s_measured": round(l3_wall, 1),
        "cost_s_note": ("trace 의 `cost_s` 는 40초/구조 근사값이다. 실제 계산 시간은 "
                        f"psi4 실측 {l3_wall:.1f}초다 — 표에는 실측값을 쓴다."),
        "selection": {
            "rule": ("대표 사례 선정 점수에서 **최고점에 해당한 20개 사례 중 하나**를 "
                     "선택했다. 점수 규칙은 `main_run.case_study_score` 다."),
            "n_top_score": 20,
            "provenance_note": ("Hypothesis Fidelity 를 성과 지표에서 제거한 최신 "
                                "기준이다. 두 조건 모두 92/92 가 True 였으므로 모든 "
                                "과제에 같은 값이 더해졌고 최고점 그룹과 선택된 사례는 "
                                "바뀌지 않았다 (DECISION_LOG 2026-08-16 (2))."),
            "forbidden": "«후보 67개 가운데 선택» 이라는 옛 문구를 쓰지 않는다.",
            "disclosure": ("통계적으로 대표성을 갖는 표본이 아니라 규칙에 따라 골라낸 "
                           "사례다. «대표 사례» 로 일반화하지 않는다."),
        },
        "verbatim_note": ("아래는 에이전트가 실제로 출력한 한국어 원문 **전문**이다. "
                          "요약·윤문·번역하지 않았다. 그림 5 에는 발췌만 실었고 이 표가 "
                          "전문을 담는다."),
        "steps": steps, "frozen": frozen_hashes(),
    }
    write_json(OUT / "s8_trajectory.json", payload)
    return payload


# ── main ─────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 78)
    print("보충자료 표 S1~S8 source data — LLM 호출 0회 · 읽기 전용")
    print("=" * 78)
    agg, hr, pool, tau, ids, rows = load()
    check("동결 stage B 일치", agg["frozen"]["stage_b"] == frozen_hashes()["stage_b"])
    check("잠정 결과가 아님", agg["provisional"] is False)
    check("과제 92", len(ids) == 92 and agg["n_tasks"] == 92)

    build_s1(ids, rows)
    build_s2(tau)
    build_s3(ids, rows)
    build_s4(pool, ids, rows)
    build_s5(pool, ids, rows)
    build_s6(pool)
    build_s7()
    build_s8(pool, tau, rows)

    print("\n" + "=" * 78)
    if _fails:
        print(f"🔴 assertion 실패 {len(_fails)}건 — 파일을 쓰지 않아야 한다")
        for f in _fails:
            print(f"   · {f}")
        sys.exit(1)
    print("🟢 assertion 전부 통과")
    print("=" * 78)


if __name__ == "__main__":
    main()
