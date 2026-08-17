"""plot-ready 데이터 생성 — **읽기 전용 · LLM 0회 · 그림을 그리지 않는다.**

그림(`figures/make_figures.py`)은 이 스크립트가 만든 파일만 읽는다.
손으로 수치를 옮겨 적지 않기 위해서다.

🔴 **비용은 psi4 실측 wall time 만 쓴다.** `rows["cost_s"]` 는 `cached.LEVEL_COST_S`
의 «표시용 근사»(L3 = 구조당 40초)이며 ALL_L3·R0 의 실측 기준과 섞으면 무효 비교가
된다 (DECISION_LOG 2026-08-14 (1) 정정 ②). 근사값에서는 **실행 횟수만** 역산하고
단가는 실측으로 다시 곱한다.

**모든 산출물에 assertion 을 건다** — 동결 원본에서 재현되지 않으면 파일을 쓰지 않는다.

사용: python3 src/vccl/scoring/plot_data.py
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents.r0 import to_task  # noqa: E402
from vccl.executor import cached  # noqa: E402
from vccl.scoring.headroom import _l3_seconds, task_cost_s  # noqa: E402
from vccl.scoring.labels import band_of  # noqa: E402
from vccl.tasks.pairs import build_pool, load_tau  # noqa: E402

AGG = ROOT / "results" / "main_run_aggregate.json"
HEADROOM = ROOT / "results" / "oracle_headroom_audit.json"
STAGE_B = ROOT / "data" / "tasks" / "frozen_stage_b_v1.json"
CONDITIONS = ("V", "V-tau")
BANDS = ("A", "B", "C", "D")

EXPECT_COST = {"ALL_L3": 19926.1, "V": 6107.0, "V-tau": 27766.0}
COST_TOL = 1.0

# 앞선 분석에서 보고한 값 — 재현되지 않으면 중단한다
EXPECT_JR = {"R0": 56, "V-tau": 54, "V": 74, "ALL_L3": 75}
EXPECT_CALIB = {"V": (79, 0, 0, 13), "V-tau": (55, 20, 3, 14)}   # aC aA iC iA
EXPECT_BANDC = {"R0": 8, "V-tau": 11, "V": 22}
EXPECT_P = {"V_vs_R0": 9.122e-4, "V_vs_Vtau": 1.097e-5, "Vtau_vs_R0": 0.8601,
            "bandC_V_vs_Vtau": 9.766e-4, "bandC_V_vs_R0": 5.188e-4,
            "nonC_V_vs_R0": 0.3877, "overinterp": 0.25, "overcaution": 1.907e-6}
P_RTOL = 0.02

_fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'🟢' if ok else '🔴'} {name:<46} {detail}")
    if not ok:
        _fails.append(name)
    return ok


def close(a: float, b: float, rtol: float = P_RTOL) -> bool:
    return abs(a - b) <= rtol * max(abs(a), abs(b), 1e-30)


# ── 공통 로더 ────────────────────────────────────────────────────────
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


def mcnemar(a: dict, b: dict, ids, key="justified_resolution"):
    """정확 McNemar. a 기준 (n10 = a 성공·b 실패)."""
    n01 = sum(1 for t in ids if not a[t][key] and b[t][key])
    n10 = sum(1 for t in ids if a[t][key] and not b[t][key])
    n = n01 + n10
    p = 1.0 if n == 0 else min(
        1.0, 2 * sum(comb(n, k) for k in range(min(n01, n10) + 1)) / 2 ** n)
    return n10, n01, p


# ── 비용 ─────────────────────────────────────────────────────────────
def exec_counts(cost_s: float) -> tuple[int, int]:
    c1 = cached.LEVEL_COST_S["L1"] * 2
    c3 = cached.LEVEL_COST_S["L3"] * 2
    n3 = int(round(cost_s / c3)) if cost_s >= c3 / 2 else 0
    n1 = int(round((cost_s - n3 * c3) / c1))
    if abs(n3 * c3 + n1 * c1 - cost_s) > 0.005:
        raise SystemExit(f"🔴 실행 횟수 역산 실패 (cost_s={cost_s})")
    return n1, n3


def build_cost(pool, tau, ids, rows, out: Path):
    print("\n[cost] psi4 실측 wall time")
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
            cost = n1 * c1 + n3 * l3
            r |= {f"{c}_n_exec_L1": n1, f"{c}_n_exec_L3": n3,
                  f"{c}_cost_s_measured": round(cost, 3),
                  f"{c}_used_l3": bool(rows[c][tid]["used_l3"])}
            totals[c] += cost
        recs.append(r)

    for k, want in EXPECT_COST.items():
        check(f"cost {k} 재현", abs(totals[k] - want) <= COST_TOL,
              f"{totals[k]:.1f}초 vs 정정값 {want:.1f} (차 {totals[k]-want:+.1f})")
    check("실측 wall time 결측 0", n_approx == 0, f"근사 대체 {n_approx}/92")

    summary = {
        "basis": "psi4 measured wall time; the 40 s/structure approximation was used "
                 "only to recover execution counts.",
        "correction_ref": "DECISION_LOG 2026-08-14 (1) correction 2",
        "totals_s": {k: round(v, 1) for k, v in totals.items()},
        "pct_of_all_l3": {k: round(100 * v / totals["ALL_L3"], 2) for k, v in totals.items()},
        "n_exec_L3": {c: sum(r[f"{c}_n_exec_L3"] for r in recs) for c in CONDITIONS},
        "n_tasks_used_l3": {c: sum(r[f"{c}_used_l3"] for r in recs) for c in CONDITIONS},
        "l3_wall_s_stats": {
            "min": round(min(r["l3_wall_s_measured"] for r in recs), 1),
            # 짝수 표본(n=92)에서는 가운데 두 값의 평균이다. 예전 구현은 한 값을
            # 그냥 집어 78.2 를 냈다 (DECISION_LOG 2026-08-16 (6) 정정).
            # 이 값은 어떤 Figure 에도 들어가지 않는다 — cost_summary 의 기술 통계다.
            "median": round(statistics.median(
                [r["l3_wall_s_measured"] for r in recs]), 1),
            "mean": round(totals["ALL_L3"] / len(recs), 1),
            "max": round(max(r["l3_wall_s_measured"] for r in recs), 1)},
        "forbidden": "Do not write '…% performance'. ALL_L3 is a reference policy, "
                     "not a proven upper bound.",
    }
    write_csv(out / "cost_by_task.csv", recs)
    write_json(out / "cost_summary.json", summary)
    return summary


# ── F0 · workflow 실측 주석 ──────────────────────────────────────────
def build_f0(ids, rows, out: Path):
    """F0 그림에 들어가는 «실측 수치»를 파일로 뺀다.

    그림 코드에 결과 숫자를 문자열로 박아두면 재현성 사슬이 끊긴다
    (동결본 → plot_data → results/plot_data → make_figures → Figure).
    """
    print("\n[F0] workflow 실측 주석")
    from collections import Counter
    V = rows["V"]
    branch_a = sum(V[t]["branch_a"] for t in ids)
    branch_b = sum(V[t]["branch_b"] for t in ids)
    rounds = Counter(V[t]["rounds"] for t in ids)
    used_l3 = sum(bool(V[t]["used_l3"]) for t in ids)

    check("F0 분기 A = 45", branch_a == 45, f"실측 {branch_a}")
    check("F0 분기 B = 1", branch_b == 1, f"실측 {branch_b}")
    check("F0 라운드 분포 {1:46, 2:46}", dict(rounds) == {1: 46, 2: 46}, str(dict(rounds)))
    check("F0 라운드 합 = 92", sum(rounds.values()) == 92, str(sum(rounds.values())))

    payload = {
        "condition": "V", "n_tasks": len(ids),
        "branch_a_escalate": branch_a, "branch_b_reoperationalize": branch_b,
        "rounds": {str(k): v for k, v in sorted(rounds.items())},
        "used_l3_tasks": used_l3,
        "tau_prompt_stages": ["choose_level", "review", "conclude"],
        "tau_absent_stages": ["operationalize"],
        "note": "τ 블록은 수준 선택·검토·결론 프롬프트에만 들어간다. "
                "비교 문제를 구체화하는 프롬프트에는 들어가지 않는다.",
    }
    write_json(out / "f0_workflow.json", payload)
    return payload


# ── F1 · 밴드 · τ 사다리 ─────────────────────────────────────────────
def build_f1(pool, tau, ids, rows, out: Path):
    print("\n[F1] 반응유형별 τ 사다리 + |ΔE_ref| 분포")
    ladders = {}
    for rt in ("conformer", "isomer"):
        l3, l1 = tau.get(rt, "L3"), tau.get(rt, "L1")
        ladders[rt] = {"tau_L3": round(l3, 4), "tau_L1": round(l1, 4),
                       "three_tau_L1": round(3 * l1, 4),
                       "correct_action": {
                           "D": {"at_L1": "ABSTAIN", "at_L3": "ABSTAIN"},
                           "C": {"at_L1": "ABSTAIN", "at_L3": "resolve"},
                           "B": {"at_L1": "resolve", "at_L3": "resolve"},
                           "A": {"at_L1": "resolve", "at_L3": "resolve"}}}
    recs = []
    for tid in ids:
        t = to_task(pool[tid])
        recs.append({"tid": tid, "rtype": t.rtype, "subset": t.subset,
                     "abs_ref": round(t.abs_ref, 6),
                     "band": band_of(t, tau).value})
    # assertion — 밴드가 τ 규칙에서 재현되는가 · 기록된 밴드와 일치하는가
    mismatch = [r["tid"] for r in recs if r["band"] != rows["V"][r["tid"]]["band"]]
    check("밴드가 실행 기록과 일치", not mismatch, f"불일치 {len(mismatch)}")
    from collections import Counter
    tot = Counter(r["band"] for r in recs)
    check("전체 밴드 분포 A30 B22 C25 D15",
          [tot[b] for b in BANDS] == [30, 22, 25, 15], str(dict(sorted(tot.items()))))
    per = {}
    for rt in ("conformer", "isomer"):
        sub = [r for r in recs if r["rtype"] == rt]
        cc = Counter(r["band"] for r in sub)
        per[rt] = {"n": len(sub), **{b: cc.get(b, 0) for b in BANDS}}
        # 경계가 실제로 밴드를 가르는지 직접 검증
        L = ladders[rt]
        bad = [r["tid"] for r in sub
               if (r["band"] == "D") != (r["abs_ref"] <= L["tau_L3"])
               or (r["band"] == "C") != (L["tau_L3"] < r["abs_ref"] <= L["tau_L1"])
               or (r["band"] == "B") != (L["tau_L1"] < r["abs_ref"] <= L["three_tau_L1"])
               or (r["band"] == "A") != (r["abs_ref"] > L["three_tau_L1"])]
        check(f"{rt} 경계가 밴드를 정확히 가름", not bad, f"위반 {len(bad)}/{len(sub)}")
    check("반응유형 합 = 92", per["conformer"]["n"] + per["isomer"]["n"] == 92,
          f"conformer {per['conformer']['n']} + isomer {per['isomer']['n']}")

    write_csv(out / "f1_tasks.csv", recs)
    write_json(out / "f1_ladders.json",
               {"note": "Band boundaries are the frozen reaction-type τ actually used "
                        "at runtime (frozen_rules_v1.json). Per-subset MAE values were "
                        "NOT used as boundaries (see Supplementary T2).",
                "ladders": ladders, "band_counts_by_rtype": per,
                "band_counts_total": {b: tot[b] for b in BANDS}})
    return ladders, per


# ── F2 · 주 결과 + calibration ───────────────────────────────────────
def build_f2(ids, rows, out: Path):
    print("\n[F2] justified resolution + 2×2 calibration")
    jr = {k: sum(1 for t in ids if rows[k][t]["justified_resolution"])
          for k in ("R0", "V-tau", "V", "ALL_L3")}
    for k, want in EXPECT_JR.items():
        check(f"justified {k} = {want}", jr[k] == want, f"실측 {jr[k]}")

    tests = {}
    for name, a, b in (("V_vs_R0", "V", "R0"), ("V_vs_Vtau", "V", "V-tau"),
                       ("Vtau_vs_R0", "V-tau", "R0")):
        n10, n01, p = mcnemar(rows[a], rows[b], ids)
        tests[name] = {"a": a, "b": b, "n10": n10, "n01": n01, "p": p}
        check(f"McNemar {name}", close(p, EXPECT_P[name]),
              f"p={p:.4g} (기대 {EXPECT_P[name]:.4g}) 불일치 {n10}:{n01}")

    calib = {}
    for c in CONDITIONS:
        m = {"adequate_commit": 0, "adequate_abstain": 0,
             "inadequate_commit": 0, "inadequate_abstain": 0}
        for t in ids:
            r = rows[c][t]
            k = ("adequate" if r["evidence_adequate"] else "inadequate") + \
                ("_commit" if r["stated"] != "ABSTAIN" else "_abstain")
            m[k] += 1
        calib[c] = m
        want = EXPECT_CALIB[c]
        got = (m["adequate_commit"], m["adequate_abstain"],
               m["inadequate_commit"], m["inadequate_abstain"])
        check(f"calibration {c}", got == want and sum(got) == 92,
              f"{got} (기대 {want}) 합 {sum(got)}")
        # off-diagonal 이 기존 지표와 같은지 교차 검증
        oc = sum(1 for t in ids if rows[c][t]["over_cautious"])
        oi = sum(1 for t in ids if rows[c][t]["overinterpretation"])
        check(f"  {c} off-diagonal = 기존 지표",
              m["adequate_abstain"] == oc and m["inadequate_commit"] == oi,
              f"over-caution {oc} · overinterpretation {oi}")

    for key, metric in (("overcaution", "over_cautious"),
                        ("overinterp", "overinterpretation")):
        n10, n01, p = mcnemar(rows["V"], rows["V-tau"], ids, metric)
        tests[key] = {"metric": metric, "n10": n10, "n01": n01, "p": p}
        check(f"McNemar {key}", close(p, EXPECT_P[key]),
              f"p={p:.4g} (기대 {EXPECT_P[key]:.4g}) 불일치 {n10}:{n01}")

    write_json(out / "f2_main.json", {
        "metric": "justified resolution = committed AND own evidence adequate "
                  "AND direction matches reference",
        "n_tasks": len(ids), "counts": jr, "tests": tests, "calibration": calib,
        "note_R0": "R0 receives the structure pair, observable and level as oracle "
                   "input; only the conclusion axis is comparable.",
        "note_ALL_L3": "ALL_L3 is a reference policy that runs every task at the "
                       "higher level. It is NOT a proven upper bound.",
        "note_calibration": "This matrix is consistency against the agent's own "
                            "evidence, not correctness against the reference."})
    return jr, tests, calib


# ── F3 · 밴드별 + 비용·품질 ──────────────────────────────────────────
def build_f3(ids, rows, cost_summary, out: Path):
    print("\n[F3] 밴드별 justified + 비용·품질")
    per_band, tests = {}, {}
    for b in BANDS:
        sub = [t for t in ids if rows["V"][t]["band"] == b]
        per_band[b] = {"n": len(sub),
                       **{k: sum(1 for t in sub if rows[k][t]["justified_resolution"])
                          for k in ("R0", "V-tau", "V", "ALL_L3")}}
    check("밴드별 n 합 = 92", sum(v["n"] for v in per_band.values()) == 92,
          str({b: per_band[b]["n"] for b in BANDS}))
    for k, want in EXPECT_BANDC.items():
        check(f"밴드 C {k} = {want}", per_band["C"][k] == want, f"실측 {per_band['C'][k]}")

    cids = [t for t in ids if rows["V"][t]["band"] == "C"]
    nids = [t for t in ids if rows["V"][t]["band"] != "C"]
    for name, a, b, sel in (("bandC_V_vs_Vtau", "V", "V-tau", cids),
                            ("bandC_V_vs_R0", "V", "R0", cids),
                            ("nonC_V_vs_R0", "V", "R0", nids)):
        n10, n01, p = mcnemar(rows[a], rows[b], sel)
        tests[name] = {"a": a, "b": b, "n": len(sel), "n10": n10, "n01": n01, "p": p}
        check(f"McNemar {name}", close(p, EXPECT_P[name]),
              f"p={p:.4g} (기대 {EXPECT_P[name]:.4g}) n={len(sel)} 불일치 {n10}:{n01}")

    quality_cost = {k: {"cost_s": cost_summary["totals_s"][k],
                        "pct_of_all_l3": cost_summary["pct_of_all_l3"][k],
                        "justified": sum(1 for t in ids if rows[k][t]["justified_resolution"])}
                    for k in ("R0", "V", "V-tau", "ALL_L3")}
    write_json(out / "f3_bands.json", {
        "per_band": per_band, "tests": tests, "quality_cost": quality_cost,
        "primary_contrast": "bandC_V_vs_Vtau",
        "wording": "Report as: the statistically detected performance gain is "
                   "concentrated in band C. Do NOT write 'confined to band C'. "
                   "p=0.39 outside band C is an absence of detected difference, "
                   "not evidence of no difference."})
    return per_band, tests, quality_cost


# ── F4 · 대표 trajectory ─────────────────────────────────────────────
CASE_TID = "ACONF:B_T+B_G"
# 그림에 실을 «원문 발췌» 를 고를 때 쓰는 필드와 길이 상한.
# 논문이 한국어이고 에이전트 출력도 한국어이므로 **번역하지 않는다** — 원문을 그대로
# 인용하고, 길이를 줄인 경우 발췌임을 표시한다.
EXCERPT = {
    ("operationalize", 1): ("identification_basis", 90),
    ("review", 1): ("concern", 95),
    ("conclude", 2): ("reasoning", 115),
}


def _excerpt(text: str, limit: int) -> tuple[str, bool]:
    """문장 경계에서 자른다. 자른 경우 True 를 함께 돌려준다."""
    t = " ".join(text.split())
    if len(t) <= limit:
        return t, False
    cut = t[:limit]
    for sep in ("。", ". ", "다. ", "다 ", ", "):
        i = cut.rfind(sep)
        if i > limit * 0.55:
            return cut[:i + len(sep)].strip().rstrip(",") + " …", True
    return cut.rstrip() + " …", True


def build_f4(pool, tau, ids, rows, out: Path):
    print(f"\n[F4] 대표 trajectory — {CASE_TID}")
    sb_hash = json.loads(STAGE_B.read_text())["sha256"]
    cand = None
    for d in sorted((ROOT / "experiments").glob("main_b*")):
        f = d / "batch_result.json"
        if not f.exists():
            continue
        p = json.loads(f.read_text())
        if p["frozen"]["stage_b"] != sb_hash:
            continue
        for c in p["case_study_candidates"]:
            if c["tid"] == CASE_TID and c["condition"] == "V":
                cand = c
    if cand is None:
        raise SystemExit(f"🔴 {CASE_TID} 후보를 찾지 못했다")

    task = to_task(pool[CASE_TID])
    row = rows["V"][CASE_TID]
    l3_wall = task_cost_s(task, "L3")
    steps = []
    for t in cand["trace"]:
        s_ = {"round": t["round"], "step": t["step"]}
        key = EXCERPT.get((t["step"], t["round"]))
        if key:
            field, lim = key
            txt, trimmed = _excerpt(t[field], lim)
            s_ |= {"text_ko": txt, "text_ko_field": field,
                   "text_ko_is_excerpt": trimmed,
                   "text_ko_full_len": len(t[field])}
        if t["step"] == "operationalize":
            s_ |= {"pair": [t["structure_more_stable"], t["structure_other"]]}
        elif t["step"] == "choose_level":
            s_ |= {"level": t["level"]}
        elif t["step"] == "execute":
            s_ |= {"level": t["level"],
                   "delta_evidence": t["delta_evidence_kcal_mol"],
                   "wall_s_measured": round(l3_wall, 1) if t["level"] == "L3"
                   else round(cached.LEVEL_COST_S["L1"] * 2, 3)}
        elif t["step"] == "review":
            s_ |= {"sufficient": t["evidence_sufficient"],
                   "recommendation": t["recommendation"]}
        elif t["step"].startswith("conclude"):
            s_ |= {"conclusion": t["conclusion"]}
        steps.append(s_)

    payload = {
        "tid": CASE_TID, "condition": "V", "band": row["band"], "rtype": task.rtype,
        "tau_L1": round(tau.get(task.rtype, "L1"), 4),
        "tau_L3": round(tau.get(task.rtype, "L3"), 4),
        "abs_ref": round(task.abs_ref, 4),
        "final_conclusion": row["stated"],
        "identification_correct": row["identification_correct"],
        "l3_wall_s_measured": round(l3_wall, 1),
        "steps": steps,
        "selection": {"pool": "case-study candidates with score >= 8 across the three "
                              "valid main-run batches", "n_candidates": 67,
                      "n_top_score": 20, "rule": "highest score; all top-score "
                      "candidates are band C, condition V",
                      "disclosure": "Selection is not random; report the rule."},
        "quote_note": "그림에 실은 문장은 에이전트가 실제로 출력한 한국어 원문의 "
                      "발췌다. 번역하지 않았고 표현을 다듬지도 않았다. 길이를 줄인 "
                      "경우 text_ko_is_excerpt 로 표시했으며 전문은 Supplementary "
                      "Material 에 싣는다.",
        "scope": "과제 하나의 실행 사례다. 전체 결과로 일반화하지 않는다 — Band C "
                 "전체는 F3(a) 다. 앵커 논문과의 관계는 Discussion 에서 다룬다.",
    }
    # assertion
    d1 = [s for s in steps if s["step"] == "execute" and s["level"] == "L1"]
    d3 = [s for s in steps if s["step"] == "execute" and s["level"] == "L3"]
    check("L1→L3 상승이 기록됨", bool(d1) and bool(d3),
          f"L1 {len(d1)}회 · L3 {len(d3)}회")
    check("라운드1 Reviewer 가 escalate 요구",
          any(s["step"] == "review" and s["round"] == 1
              and s["recommendation"] == "escalate" for s in steps))
    check("L1 증거 < τ_L1", abs(d1[0]["delta_evidence"]) < payload["tau_L1"],
          f"|ΔE_L1| {abs(d1[0]['delta_evidence'])} < τ_L1 {payload['tau_L1']}")
    check("L3 증거 > τ_L3", abs(d3[0]["delta_evidence"]) > payload["tau_L3"],
          f"|ΔE_L3| {abs(d3[0]['delta_evidence'])} > τ_L3 {payload['tau_L3']}")
    check("밴드 C 이고 τ_L3 < |ΔE_ref| ≤ τ_L1",
          row["band"] == "C"
          and payload["tau_L3"] < payload["abs_ref"] <= payload["tau_L1"],
          f"|ΔE_ref| {payload['abs_ref']}")
    check("식별 정확", row["identification_correct"] is True)
    write_json(out / "f4_trajectory.json", payload)
    return payload



# ── T1 · Main Table (시스템 동작) ────────────────────────────────────
EXPECT_T1 = {
    "V":     dict(failed=0, ident=(76, 76), auto_jr=63, paired_jr=11,
                  l3_tasks=45, l3_exec=45, l3_any=45,
                  br_a=45, br_b=1, rounds={1: 46, 2: 46}),
    "V-tau": dict(failed=0, ident=(76, 76), auto_jr=46, paired_jr=8,
                  l3_tasks=91, l3_exec=101, l3_any=92,
                  br_a=22, br_b=11, rounds={1: 66, 2: 19, 3: 7}),
}
EXPECT_EXEC = dict(n_calls=911, n_batches=3, unparsed=5, status_err=1,
                   jsonl_bad=0, task_failed=0)


def build_t1(ids, rows, out: Path):
    """Main Table 1 의 table-ready 데이터.

    **표 렌더러는 이 파일만 읽는다.** 논문 표에 들어가는 숫자를 렌더러 코드에 적지
    않기 위해서다 (Figure 와 같은 규칙).

    Hypothesis Fidelity·Protocol Validity 는 **넣지 않는다**
    (DECISION_LOG 2026-08-16 (1), `paper_logic/table_design.md` §5).
    """
    from collections import Counter
    print("\n[T1] Main Table — 시스템 동작")
    n = len(ids)
    per = {}
    for c in CONDITIONS:
        R = rows[c]
        auto = [t for t in ids if R[t]["identification_mode"] == "autonomous"]
        pair = [t for t in ids if R[t]["identification_mode"] == "paired"]
        n1n3 = [exec_counts(R[t]["cost_s"]) for t in ids]
        per[c] = {
            "failed": sum(R[t]["failed"] for t in ids),
            "ident_ok": sum(1 for t in auto if R[t]["identification_correct"]),
            "ident_n": len(auto),
            "auto_jr": sum(1 for t in auto if R[t]["justified_resolution"]),
            "auto_n": len(auto),
            "paired_jr": sum(1 for t in pair if R[t]["justified_resolution"]),
            "paired_n": len(pair),
            "l3_tasks": sum(1 for t in ids if R[t]["used_l3"]),
            "l3_exec": sum(x[1] for x in n1n3),
            # 표에는 넣지 않고 각주 c 가 쓴다 — 「최종 판단 수준이 L3」와
            # 「L3 가 한 번이라도 돌았다」는 다르다 (V−τ 에서 91 대 92).
            "l3_any_exec_tasks": sum(1 for x in n1n3 if x[1] >= 1),
            "branch_a": sum(R[t]["branch_a"] for t in ids),
            "branch_b": sum(R[t]["branch_b"] for t in ids),
            "rounds": {str(k): v for k, v in
                       sorted(Counter(R[t]["rounds"] for t in ids).items())},
        }
        e = EXPECT_T1[c]
        check(f"T1 {c} FAILED", per[c]["failed"] == e["failed"], str(per[c]["failed"]))
        check(f"T1 {c} 자율식별",
              (per[c]["ident_ok"], per[c]["ident_n"]) == e["ident"],
              f"{per[c]['ident_ok']}/{per[c]['ident_n']}")
        check(f"T1 {c} 자율식별형 근거충분결론", per[c]["auto_jr"] == e["auto_jr"],
              str(per[c]["auto_jr"]))
        check(f"T1 {c} 쌍지정형 근거충분결론", per[c]["paired_jr"] == e["paired_jr"],
              str(per[c]["paired_jr"]))
        check(f"T1 {c} 최종수준 L3 과제", per[c]["l3_tasks"] == e["l3_tasks"],
              str(per[c]["l3_tasks"]))
        check(f"T1 {c} L3 실행 횟수", per[c]["l3_exec"] == e["l3_exec"],
              str(per[c]["l3_exec"]))
        # 라벨 정정의 근거 — 두 정의가 실제로 갈리는지 확인한다
        check(f"T1 {c} L3 1회이상 실행 과제", per[c]["l3_any_exec_tasks"] == e["l3_any"],
              f"{per[c]['l3_any_exec_tasks']} (최종수준 L3 는 {per[c]['l3_tasks']})")
        check(f"T1 {c} 경로 A", per[c]["branch_a"] == e["br_a"], str(per[c]["branch_a"]))
        check(f"T1 {c} 경로 B", per[c]["branch_b"] == e["br_b"], str(per[c]["branch_b"]))
        check(f"T1 {c} 라운드 분포",
              {int(k): v for k, v in per[c]["rounds"].items()} == e["rounds"],
              str(per[c]["rounds"]))
        # 하위 합이 전체 근거충분결론과 맞는가 (그림 3과의 정합성)
        tot = sum(1 for t in ids if rows[c][t]["justified_resolution"])
        check(f"T1 {c} 하위 합 = 전체",
              per[c]["auto_jr"] + per[c]["paired_jr"] == tot,
              f"{per[c]['auto_jr']}+{per[c]['paired_jr']}={tot}")

    # ── 실행 규모 (원장 직접 집계) ────────────────────────────────
    sb = json.loads(STAGE_B.read_text())["sha256"]
    ex = dict(n_calls=0, n_batches=0, unparsed=0, status_err=0, jsonl_bad=0,
              elapsed_s=0.0, err_also_unparsed=0)
    for d in sorted((ROOT / "experiments").glob("main_b*")):
        f = d / "batch_result.json"
        if not f.exists():
            continue
        p_ = json.loads(f.read_text())
        if p_["frozen"]["stage_b"] != sb:
            continue
        ex["n_batches"] += 1
        ex["elapsed_s"] += p_["elapsed_s"]
        calls = []
        for line in (d / "calls.jsonl").read_text().splitlines():
            try:
                calls.append(json.loads(line))
            except Exception:  # noqa: BLE001
                ex["jsonl_bad"] += 1
        ex["n_calls"] += len(calls)
        unp = [c for c in calls if c["parsed"] is None]
        err = [c for c in calls if c["status"] != "SUCCESS"]
        ex["unparsed"] += len(unp)
        ex["status_err"] += len(err)
        ex["err_also_unparsed"] += sum(1 for c in err if c["parsed"] is None)
    ex["task_failed"] = sum(per[c]["failed"] for c in CONDITIONS)
    ex["elapsed_min"] = round(ex["elapsed_s"] / 60, 1)

    for k, want in EXPECT_EXEC.items():
        check(f"T1 실행 {k}", ex[k] == want, f"{ex[k]}")
    check("T1 status ERROR ⊂ 구조화 출력 실패",
          ex["err_also_unparsed"] == ex["status_err"],
          f"{ex['err_also_unparsed']}/{ex['status_err']}")

    ROW = [
        ("failed", "완료하지 못한 과제 (FAILED)",
         lambda v: f"{v['failed']} / {n}",
         "main_run_aggregate.json → rows[조건][*].failed"),
        ("ident", "자율 식별 정확도",
         lambda v: f"{v['ident_ok']} / {v['ident_n']}",
         "rows[조건][*] 중 identification_mode=='autonomous' 의 identification_correct"),
        ("auto_jr", "— 자율 식별형의 근거가 충분한 결론",
         lambda v: f"{v['auto_jr']} / {v['auto_n']}",
         "같은 부분집합의 justified_resolution"),
        ("paired_jr", "— 쌍 지정형의 근거가 충분한 결론",
         lambda v: f"{v['paired_jr']} / {v['paired_n']}",
         "identification_mode=='paired' 부분집합의 justified_resolution"),
        # 🔧 라벨 정정 (2026-08-16) — `used_l3` 는 «L3 가 한 번이라도 돌았는가» 가
        #    아니라 `level_used == "L3"`, 즉 **최종 판단 수준**이다. 수치는 그대로다.
        ("l3_tasks", "최종 판단 수준이 L3인 과제",
         lambda v: f"{v['l3_tasks']} / {n}",
         "rows[조건][*].used_l3  (= level_used == 'L3' · 최종 판단 수준)"),
        ("l3_exec", "L3 실행 횟수",
         lambda v: f"{v['l3_exec']}",
         "rows[조건][*].cost_s 에서 역산한 L3 실행 수 (cost_by_task.csv 와 동일 계산)"),
        ("branch_a", "경로 A (계산 수준 상향) 사용 횟수",
         lambda v: f"{v['branch_a']}",
         "rows[조건][*].branch_a"),
        ("branch_b", "경로 B (비교 대상 재설정) 사용 횟수",
         lambda v: f"{v['branch_b']}",
         "rows[조건][*].branch_b"),
        ("rounds", "라운드 분포 (1 / 2 / 3)",
         lambda v: " / ".join(str(v["rounds"].get(str(k), 0)) for k in (1, 2, 3)),
         "rows[조건][*].rounds"),
    ]
    payload = {
        "table_id": "T1",
        "title": "두 조건의 실행 동작",
        "n_tasks": n,
        "conditions": list(CONDITIONS),
        "condition_label": {"V": "V", "V-tau": "V−τ"},
        "rows": [{"key": k, "label": lab,
                  "display": {c: fmt(per[c]) for c in CONDITIONS},
                  "source": src} for k, lab, fmt, src in ROW],
        "raw": per,
        "execution": ex,
        "excluded_metrics": {
            "hypothesis_fidelity":
                "§7.2가 규정한 «원 가설 유지의 결정론적 검사»가 구현되지 않았다. "
                "구현은 필드가 비었는지만 보므로 보고하지 않는다 "
                "(DECISION_LOG 2026-08-16 (1)).",
            "protocol_validity":
                "실행 명세가 미리 계산된 registry 안(계산 수준 2택 × 후보 구조 쌍)에서만 "
                "만들어지므로 100%가 구성상 보장된다. 성과 지표로 쓰지 않고 Methods "
                "각주로만 밝힌다.",
        },
        "frozen": {
            "frozen_rules_v1.json": json.loads(
                (ROOT / "data/tasks/frozen_rules_v1.json").read_text())["sha256"],
            "frozen_stage_b_v1.json": json.loads(STAGE_B.read_text())["sha256"],
            "execution_order_v1.json": json.loads(
                (ROOT / "data/tasks/execution_order_v1.json").read_text())["sha256"],
        },
        "not_repeated_from_figures":
            "전체 근거가 충분한 결론·p값·계산 비용 %는 그림 3·4에 있으므로 이 표에서 "
            "반복하지 않는다.",
    }
    write_json(out / "t1_system.json", payload)
    return payload


# ── io ───────────────────────────────────────────────────────────────
def write_csv(path: Path, recs: list[dict]):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0]))
        w.writeheader()
        w.writerows(recs)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/plot_data")
    a = ap.parse_args()
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("plot-ready 데이터 생성 — 동결 원본에서 추출 · LLM 0회")
    print("=" * 78)
    agg, hr, pool, tau, ids, rows = load()
    check("과제 92개", len(ids) == 92, f"{len(ids)}")
    check("V·V−τ FAILED 0", all(not rows[c][t]["failed"] for c in CONDITIONS for t in ids))

    cost = build_cost(pool, tau, ids, rows, out)
    build_f0(ids, rows, out)
    build_f1(pool, tau, ids, rows, out)
    build_f2(ids, rows, out)
    build_f3(ids, rows, cost, out)
    build_f4(pool, tau, ids, rows, out)
    build_t1(ids, rows, out)

    print(f"\n{'=' * 78}")
    if _fails:
        raise SystemExit(f"🔴 assertion {len(_fails)}건 실패: {_fails}\n"
                         "산출물을 신뢰할 수 없다.")
    print("🟢 assertion 전부 통과")
    for f in sorted(out.iterdir()):
        print(f"  → {f.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
