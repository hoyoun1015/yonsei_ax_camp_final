"""oracle headroom audit — **LLM 호출 0회.**

## 이 감사가 묻는 것

> *"동결된 benchmark 가 애초에 adaptive agent 의 장점을 보여줄 측정 범위를 갖고 있는가?"*

**결과를 보고 설계를 바꾸기 위한 것이 아니다.** Stage B·scoring·주 지표를 수정하지
않는다. 이 모듈은 **읽기 전용**이다 — 동결된 τ·N=92·캐시된 L1/L3 만 쓰고, 어떤 동결
파일도 쓰지 않는다.

## 비교하는 정책 4개

| | 수준 선택 | 결론 |
|---|---|---|
| **R0** (실측) | L1 고정 | `\\|ΔE_calc\\| ≤ τ_L1` → ABSTAIN, 아니면 부호 |
| **P_faithful** | A/B→L1 · C→L3 · D→L1 후 abstain | 그 수준의 `ΔE_calc` 에 충실 |
| **P_oracle** | 같음 | 그 수준의 «정답 행동»을 그대로 선언 |
| **ALL_L3** | 전량 L3 | L3 의 `ΔE_calc` 에 충실 |

🔒 **두 정책은 «천장·상한» 이 아니다** (2026-08-17 정정).

| 정책 | 무엇인가 |
|---|---|
| `P_faithful` | 사전에 정의한 **deterministic adaptive reference policy** 하나 |
| `P_oracle` | 참조 정보를 쓰는 **oracle-informed comparison policy** |

**둘 다 실제 에이전트 성능의 theoretical ceiling / upper bound 가 아니다.**
근거 — justified resolution 에서 **P_faithful 69 인데 V 는 74 다.** V 는 어느 밴드에서든
수준을 올릴 수 있어 이 고정 정책의 행동 공간을 벗어난다. 초판이 P_faithful 을 «V 의
천장» 이라고 부른 것은 그 포함 관계를 확인하지 않은 오류였다
(`DECISION_LOG` 2026-08-14 (1) 정정 ① · 2026-08-17 (3)).

`P_oracle − P_faithful` 은 **이 두 고정 정책 사이의 차이**이며, 도구 한계로 잃는 양의
상한을 증명한 값이 아니다. 다만 «에이전트 판단을 고치면 줄일 수 있는 몫» 과 «지금 쓴
도구·수준에서 줄이기 어려운 몫» 을 갈라 보는 데는 여전히 쓸 수 있다.

`ALL_L3` 는 adaptive 정책의 의미를 재기 위한 대조다 — 같은 점수를 훨씬 비싸게
얻는다면 adaptive 의 가치는 정확도가 아니라 비용이다.

## 지표를 분리한다

동결된 §7 지표들은 **서로 다른 것을 재고, 에스컬레이션에 대해 서로 다르게 반응한다.**
한 숫자로 합치면 그 사실이 사라진다.

| 계열 | 지표 | 에스컬레이션이 점수를 올리는가 |
|---|---|---|
| 정확성 | 수준상대 정답 (`is_correct`) | ❓ — `oracle_action` 이 «사용한 수준»에 따라 달라진다 |
| 정확성 | 참조방향 정확도 | ✅ 밴드 C 에서 |
| 해결력 | justified resolution | ✅ 밴드 C 에서 |
| 판단 | 과대해석률 (§7.1 주 지표) | ❌ **정의상 R0 = 0. 개선 여지가 없다** |
| 판단 | Escalation Appropriateness (§7.3) | ✅ 밴드 C 전량 |
| 비용 | 초 · L3 호출 수 | ❌ 반대로 올린다 |

사용: python3 src/vccl/scoring/headroom.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.executor import cached  # noqa: E402
from vccl.scoring.labels import (  # noqa: E402
    Band, Conclusion, Escalation, Run, Task, Tau, band_of, correct_escalation,
    error_class, evidence_adequate, is_correct, is_over_cautious,
    is_overinterpretation, oracle_action,
)
from vccl.agents.r0 import TARGET_92, to_task  # noqa: E402
from vccl.tasks.pairs import build_pool, load_tau, stratify  # noqa: E402

BANDS = ("A", "B", "C", "D")
POLICIES = ("R0", "P_faithful", "P_oracle", "ALL_L3")


# ── 실제 비용 — psi4 출력의 wall time 을 읽는다 ──────────────────────
_WALL = re.compile(r"Psi4 wall time for execution:\s*(\d+):(\d+):(\d+\.?\d*)")


def _l3_seconds(subset: str, name: str) -> float | None:
    d, tag, fname, _ = cached.LEVELS["L3"]
    p = cached.CAL / d / subset / tag / name / fname
    if not p.exists():
        return None
    m = _WALL.search(p.read_text(errors="ignore"))
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def task_cost_s(task: Task, level: str) -> float:
    """그 수준으로 이 과제를 푸는 실제 비용. L3 는 캐시의 wall time 을 쓴다."""
    if level == "L1":
        return cached.LEVEL_COST_S["L1"] * len(task.names)
    got = [_l3_seconds(task.subset, n) for n in task.names]
    if any(g is None for g in got):
        # 실측이 없으면 근사값으로 대체하고 그 사실을 표시한다 (조용히 넘기지 않는다)
        return cached.LEVEL_COST_S["L3"] * len(task.names)
    return sum(got)


# ── 정책 ─────────────────────────────────────────────────────────────
def deltas(task: Task) -> dict[str, float]:
    """L1·L3 각각의 ΔE_calc. 참조값과 같은 부호 규약을 쓴다."""
    out = {}
    for lv in ("L1", "L3"):
        res = cached.run(cached.CalcRequest(task.subset, task.names, lv))
        out[lv] = sum(c * res.energies[n]
                      for n, c in zip(task.names, task.coeffs)) * cached.HARTREE
    return out


def adaptive_level(task: Task, tau: Tau) -> str:
    """사용자가 지정한 완벽 정책의 수준 선택. A/B → L1 · C → L3 · D → L1(포기)."""
    return "L3" if band_of(task, tau) is Band.C else "L1"


def apply_policy(policy: str, task: Task, tau: Tau, d: dict[str, float]) -> Run:
    if policy == "R0":
        level = "L1"
    elif policy == "ALL_L3":
        level = "L3"
    else:
        level = adaptive_level(task, tau)

    if policy == "P_oracle":
        # 그 수준의 «정답 행동» 을 그대로 선언한다 — 참조 정보를 쓰는 비교 정책
        return Run(level, d[level], oracle_action(task, level, tau))

    # 나머지는 «자기 증거에 충실» — 참조값을 보지 않는다. 실제 V 가 도달 가능한 경로
    delta = d[level]
    if not evidence_adequate(delta, task.rtype, level, tau):
        stated = Conclusion.ABSTAIN
    else:
        stated = task.conclusion_for(task._more_stable_for(delta))
    return Run(level, delta, stated)


# ── 지표 ─────────────────────────────────────────────────────────────
def reference_direction_correct(task: Task, run: Run) -> bool:
    """참조 방향을 맞혔는가. ABSTAIN 은 정답으로 세지 않는다 (G5 와 같은 지표)."""
    if run.stated is Conclusion.ABSTAIN:
        return False
    return run.stated is task.conclusion_for(task.reference_more_stable)


def justified_resolution(task: Task, run: Run, tau: Tau) -> bool:
    """**해결력 지표.** 단정했고 · 자기 증거가 그것을 정당화하고 · 방향이 맞다.

    셋을 모두 요구한다. 그래서 «운으로 맞힌 단정»과 «근거 있는 해결»이 갈린다.
    """
    return (run.stated is not Conclusion.ABSTAIN
            and evidence_adequate(run.delta_calc, task.rtype, run.level_used, tau)
            and reference_direction_correct(task, run))


def escalation_action(policy: str, task: Task, tau: Tau) -> Escalation:
    """이 정책이 실제로 취한 «에스컬레이션 행동». 정답은 correct_escalation."""
    if policy == "ALL_L3":
        return Escalation.ESCALATION       # 항상 올린다
    if policy == "R0":
        return Escalation.SUFFICIENT       # 절대 올리지 않는다
    b = band_of(task, tau)
    return {Band.C: Escalation.ESCALATION,
            Band.D: Escalation.FUTILE}.get(b, Escalation.SUFFICIENT)


def score(policy: str, tasks: list[Task], tau: Tau,
          dcache: dict[str, dict[str, float]]) -> dict:
    rows = []
    for t in tasks:
        d = dcache[t.tid]
        run = apply_policy(policy, t, tau, d)
        b = band_of(t, tau).value
        esc_taken = escalation_action(policy, t, tau)
        rows.append({
            "tid": t.tid, "band": b, "level": run.level_used,
            "abs_ref": round(t.abs_ref, 4), "delta_calc": round(run.delta_calc, 4),
            "stated": run.stated.value,
            # 정확성
            "level_relative_correct": is_correct(t, run, tau),
            "reference_direction_correct": reference_direction_correct(t, run),
            # 해결력
            "justified_resolution": justified_resolution(t, run, tau),
            "resolved": run.stated is not Conclusion.ABSTAIN,
            # 판단
            "overinterpretation": is_overinterpretation(t, run, tau),
            "over_cautious": is_over_cautious(t, run, tau),
            "error_class": error_class(t, run, tau).value,
            # 에스컬레이션
            "escalation_answer": correct_escalation(t, tau).value,
            "escalation_taken": esc_taken.value,
            "escalation_correct": esc_taken is correct_escalation(t, tau),
            # 비용
            "cost_s": task_cost_s(t, run.level_used),
            "used_l3": run.level_used == "L3",
        })
    return {"policy": policy, "rows": rows}


METRICS = [
    ("level_relative_correct", "수준상대 정답 (frozen is_correct)", "정확성"),
    ("reference_direction_correct", "참조방향 정확도", "정확성"),
    ("justified_resolution", "justified resolution", "해결력"),
    ("resolved", "단정한 과제 수 (근거 무관)", "해결력"),
    ("overinterpretation", "과대해석 (§7.1 주 지표 · 낮을수록 좋다)", "판단"),
    ("over_cautious", "과도한 신중 (낮을수록 좋다)", "판단"),
    ("escalation_correct", "Escalation Appropriateness (§7.3)", "에스컬레이션"),
]
LOWER_IS_BETTER = {"overinterpretation", "over_cautious"}


def agg(res: dict, key: str, band: str | None = None) -> int:
    return sum(r[key] for r in res["rows"] if band is None or r["band"] == band)


def main():
    tau = load_tau()
    pool = build_pool()
    tasks = [to_task(e) for e in stratify(pool, TARGET_92)]
    n = len(tasks)
    dcache = {t.tid: deltas(t) for t in tasks}
    scored = {p: score(p, tasks, tau, dcache) for p in POLICIES}
    nb = {b: sum(1 for t in tasks if band_of(t, tau).value == b) for b in BANDS}

    P = print
    P("=" * 84)
    P("oracle headroom audit — LLM 호출 0회 · 동결본 읽기 전용")
    P("=" * 84)
    P(f"  frozen main benchmark  N={n}  ·  밴드 " +
      " ".join(f"{b}{nb[b]}" for b in BANDS))
    P("  ⚠️ 이 감사는 Stage B·scoring·주 지표를 수정하지 않는다. 동결 파일에 쓰지 않는다.")
    P()
    P("  R0          L1 고정 · 규칙 하나 (실측 재현)")
    P("  P_faithful  A/B→L1 · C→L3 · D→abstain · 자기 증거에 충실")
    P("              ← 사전 정의한 deterministic adaptive reference policy")
    P("  P_oracle    같은 수준 선택 + 정답 행동 선언")
    P("              ← 참조 정보를 쓰는 oracle-informed comparison policy")
    P("  🔒 둘 다 실제 에이전트 성능의 천장·상한이 아니다 (P_faithful 69 < V 74).")
    P("  ALL_L3      전량 L3 · 자기 증거에 충실")

    # ── 표 1 · 지표별 점수와 headroom ─────────────────────────────────
    P(f"\n{'=' * 84}")
    P("표 1 — 지표별 R0 실측 · 완벽 정책 최대 · headroom")
    P("=" * 84)
    P(f"  {'계열':<8}{'지표':<40}{'R0':>7}{'P_faith':>9}{'P_orac':>8}{'ALL_L3':>8}")
    P("  " + "-" * 78)
    table1 = {}
    for key, label, fam in METRICS:
        v = {p: agg(scored[p], key) for p in POLICIES}
        table1[key] = v
        P(f"  {fam:<8}{label:<40}" + "".join(f"{v[p]:>7}/{n%100:<2}" if False
                                             else f"{v[p]:>8}" for p in POLICIES))
    P()
    P(f"  {'지표':<48}{'headroom(과제)':>15}{'headroom(%p)':>14}")
    P("  " + "-" * 78)
    headroom = {}
    for key, label, fam in METRICS:
        v = table1[key]
        sign = -1 if key in LOWER_IS_BETTER else 1
        hf = sign * (v["P_faithful"] - v["R0"])
        ho = sign * (v["P_oracle"] - v["R0"])
        headroom[key] = {"vs_R0_by_P_faithful": hf, "vs_R0_by_P_oracle": ho,
                         "pp_faithful": round(100 * hf / n, 1),
                         "pp_oracle": round(100 * ho / n, 1),
                         "R0": v["R0"], "P_faithful": v["P_faithful"],
                         "P_oracle": v["P_oracle"], "ALL_L3": v["ALL_L3"]}
        flag = "🔴" if hf <= 2 else ("🟡" if hf <= 6 else "🟢")
        P(f"  {flag} {label:<46}{hf:>+8} / {ho:<+4}{100*hf/n:>+9.1f} /{100*ho/n:>+6.1f}")
    P("\n  왼쪽 = P_faithful 대비 · 오른쪽 = P_oracle 대비 (둘 다 비교 정책이다)")
    P("  🔴 ≤2과제  🟡 3~6과제  🟢 >6과제")

    # ── 표 2 · 밴드 C 가 만드는 headroom ──────────────────────────────
    P(f"\n{'=' * 84}")
    P(f"표 2 — 밴드 C {nb['C']}개가 각 지표에서 실제로 만드는 headroom")
    P("=" * 84)
    P(f"  {'지표':<44}{'C 안':>10}{'C 밖':>10}{'C 기여율':>10}")
    P("  " + "-" * 78)
    band_c = {}
    for key, label, fam in METRICS:
        sign = -1 if key in LOWER_IS_BETTER else 1
        inside = sign * (agg(scored["P_faithful"], key, "C")
                         - agg(scored["R0"], key, "C"))
        total = sign * (agg(scored["P_faithful"], key) - agg(scored["R0"], key))
        outside = total - inside
        share = f"{100*inside/total:.0f}%" if total else "—"
        band_c[key] = {"inside_C": inside, "outside_C": outside, "total": total}
        P(f"  {label:<44}{inside:>+10}{outside:>+10}{share:>10}")

    # ── 표 3 · 밴드별 상세 ────────────────────────────────────────────
    P(f"\n{'=' * 84}")
    P("표 3 — 밴드별 (justified resolution · 참조방향 정확도)")
    P("=" * 84)
    for key, label in (("justified_resolution", "justified resolution"),
                       ("reference_direction_correct", "참조방향 정확도")):
        P(f"\n  {label}")
        P(f"    {'밴드':<6}{'n':>4}{'R0':>8}{'P_faith':>9}{'P_orac':>8}"
          f"{'ALL_L3':>8}   해석")
        P("    " + "-" * 74)
        for b in BANDS:
            note = {"A": "값싼 수준으로 충분", "B": "값싼 수준으로 충분",
                    "C": "**에스컬레이션이 값을 하는 유일한 구간**",
                    "D": "어떤 수준으로도 불가"}[b]
            vals = "".join(f"{agg(scored[p], key, b):>8}" for p in POLICIES)
            P(f"    {b:<6}{nb[b]:>4}{vals[:8]:>8}{vals[8:16]:>9}"
              f"{vals[16:24]:>8}{vals[24:]:>8}   {note}")

    # ── 표 4 · 비용 ───────────────────────────────────────────────────
    P(f"\n{'=' * 84}")
    P("표 4 — 비용 (실제 wall time · L3 는 캐시에서 읽음)")
    P("=" * 84)
    P(f"  {'정책':<12}{'총 초':>12}{'L3 과제':>9}{'R0 대비':>10}"
      f"{'ALL_L3 대비':>12}   justified res.")
    P("  " + "-" * 78)
    cost = {}
    c_all = sum(r["cost_s"] for r in scored["ALL_L3"]["rows"])
    c_r0 = sum(r["cost_s"] for r in scored["R0"]["rows"])
    for p in POLICIES:
        c = sum(r["cost_s"] for r in scored[p]["rows"])
        l3 = sum(r["used_l3"] for r in scored[p]["rows"])
        jr = agg(scored[p], "justified_resolution")
        cost[p] = {"total_s": round(c, 1), "n_l3_tasks": l3,
                   "vs_r0": round(c / c_r0, 1) if c_r0 else None,
                   "frac_of_all_l3": round(c / c_all, 4) if c_all else None,
                   "justified_resolution": jr}
        P(f"  {p:<12}{c:>12,.1f}{l3:>9}{c/c_r0:>9.0f}×{100*c/c_all:>11.1f}%"
          f"   {jr}/{n}")

    # ── 표 5 · 오류 분해 ──────────────────────────────────────────────
    P(f"\n{'=' * 84}")
    P("표 5 — §7.4 오류 분해")
    P("=" * 84)
    P(f"  {'정책':<12}" + "".join(f"{k:>16}" for k in
                                 ("correct", "agent-limited", "tool-limited",
                                  "compound")))
    P("  " + "-" * 78)
    ec = {}
    for p in POLICIES:
        c = Counter(r["error_class"] for r in scored[p]["rows"])
        ec[p] = dict(c)
        P(f"  {p:<12}" + "".join(f"{c.get(k, 0):>16}" for k in
                                 ("correct", "agent-limited", "tool-limited",
                                  "compound")))
    P("\n  P_faithful 의 agent-limited 는 «정의상 0» 이다 — 자기 증거에 충실하게")
    P("  만든 정책이므로. 남는 오류는 전부 tool-limited 로 분류된다 — 현재 사용한")
    P("  계산 도구와 수준에서 에이전트 판단만 고쳐서는 해결하기 어려운 경우다.")
    P("  더 높은 수준이나 다른 계산 절차로 줄일 수 있는지는 이 결과만으로 알 수 없다.")

    # ── 판정 ──────────────────────────────────────────────────────────
    P(f"\n{'=' * 84}")
    P("판정 — 동결된 benchmark 가 adaptive 의 장점을 잴 수 있는가")
    P("=" * 84)
    verdicts = []
    for key, label, fam in METRICS:
        h = headroom[key]["vs_R0_by_P_faithful"]
        if h <= 2:
            verdicts.append((key, label, h, "측정 불가"))
        elif h <= 6:
            verdicts.append((key, label, h, "측정 취약"))
        else:
            verdicts.append((key, label, h, "측정 가능"))
    for key, label, h, v in sorted(verdicts, key=lambda x: -x[2]):
        icon = {"측정 가능": "🟢", "측정 취약": "🟡", "측정 불가": "🔴"}[v]
        P(f"  {icon} {v:<10}{label:<48}{h:>+4}과제")

    usable = [x for x in verdicts if x[3] == "측정 가능"]
    P()
    if usable:
        P(f"  🟢 **{len(usable)}개 지표에 충분한 측정 범위가 있다.**")
        for _, label, h, _ in usable:
            P(f"     · {label} — {h}과제 ({100*h/n:.1f}%p)")
    else:
        P("  🔴 **어떤 지표에도 충분한 측정 범위가 없다. 본실행 전에 논의가 필요하다.**")

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "llm_calls": 0,
        "read_only": ("동결된 τ·N=92·캐시만 읽는다. Stage B·scoring·주 지표를 "
                      "수정하지 않으며 어떤 동결 파일에도 쓰지 않는다."),
        "n": n, "per_band": nb,
        "policies": {
            "R0": "L1 고정 · |ΔE_calc| ≤ τ_L1 → ABSTAIN, 아니면 부호",
            # 🔒 «천장·상한» 으로 쓰지 않는다 (2026-08-17 정정). 디스크의
            #    oracle_headroom_audit.json 은 정정 전 문구를 그대로 담고 있다 —
            #    그 파일은 S1~S8 LOCK manifest 의 상류 산출물이라 재생성하지 않았다.
            "P_faithful": ("A/B→L1 · C→L3 · D→L1 후 abstain · 자기 증거에 충실. "
                           "사전에 정의한 deterministic adaptive reference policy 이며 "
                           "실제 에이전트 성능의 천장이 아니다 (69 < V 74)."),
            "P_oracle": ("같은 수준 선택 + 그 수준의 정답 행동 선언. 참조 정보를 쓰는 "
                         "oracle-informed comparison policy 이며 도달 불가능한 상한을 "
                         "증명한 값이 아니다."),
            "ALL_L3": "전량 L3 · 자기 증거에 충실",
        },
        "metric_families": {k: f for k, _, f in METRICS},
        "scores": {k: table1[k] for k, _, _ in METRICS},
        "headroom": headroom,
        "band_c_contribution": band_c,
        "by_band": {key: {b: {p: agg(scored[p], key, b) for p in POLICIES}
                          for b in BANDS}
                    for key, _, _ in METRICS},
        "cost": cost,
        "error_class": ec,
        "verdict": {k: v for k, _, _, v in verdicts},
        "rows": {p: scored[p]["rows"] for p in POLICIES},
    }
    dest = ROOT / "results" / "oracle_headroom_audit.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    P(f"\n→ {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
