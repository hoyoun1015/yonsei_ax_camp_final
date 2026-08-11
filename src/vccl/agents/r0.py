"""R0 — **oracle-pair / decision-rule baseline**. LLM 호출 0회.

🔒 **이름을 정확히 쓴다. R0 는 «자율 시스템 기준선»이 아니다.**

R0 는 다음을 **입력으로 받는다** — 즉 스스로 하지 않는다.

| R0 가 받는 것 (오라클) | R0 가 하는 것 |
|---|---|
| 비교할 구조 쌍 | `\\|ΔE_calc\\| ≤ τ_L1` → ABSTAIN, 아니면 부호 판정 |
| 관측량 (ΔE) | |
| 계산 수준 (L1 고정) | |

따라서 R0 와 V 를 비교할 때 **«전체 워크플로 대비»로 읽으면 안 된다.** R0 는
가설 해석(RQ1)·조작화·계산 선택(RQ2)·에스컬레이션(RQ3)을 **수행하지 않는다.**
비교가 성립하는 축은 **결론 판단 하나뿐**이다.

**Identification challenge 에서는 R0 와 V 의 식별 정확도를 비교하지 않는다.**
R0 는 구조 쌍을 오라클로 받으므로 식별을 아예 수행하지 않는다. 그 축에서 R0 는
정의상 100% 이며 그 숫자는 아무 의미가 없다.

**과대해석률 0 은 성능 주장이 아니다.** 규칙이 τ_L1 을 그대로 임계값으로 쓰므로
`\\|ΔE_calc\\| ≤ τ_L1` 이면 반드시 ABSTAIN 한다 — **구성상 0 이 나와야 한다.**
0 이 아니면 채점 파이프라인에 버그가 있다는 뜻이다. 그래서 이 값은
**scoring pipeline sanity check** 로 기록한다.

**R0 가 구조적으로 못 하는 것.** 절대 에스컬레이션하지 않으므로 밴드 C
(`τ_L3 < \\|ΔE_ref\\| ≤ τ_L1`)를 **하나도 해결하지 못한다.** V 가 R0 를 이길 수 있는
유일한 경로가 여기다(기획안 §6).

사용: python3 src/vccl/agents/r0.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.executor import cached  # noqa: E402
from vccl.scoring.labels import (  # noqa: E402
    Band, Conclusion, ErrorClass, IdentificationMode, Run, Task, Tau,
    band_of, correct_escalation, error_class, evidence_adequate, is_correct,
    is_over_cautious, is_overinterpretation, oracle_action,
)
from vccl.tasks.pairs import (  # noqa: E402
    build_pool, identification_challenge, load_tau, stratify,
)

TARGET_92 = {"A": 30, "B": 22, "C": 25, "D": 15}
LEVEL = "L1"          # R0 는 값싼 수준에 고정된다. 절대 올리지 않는다


def to_task(t: dict) -> Task:
    return Task(tid=t["tid"], subset=t["subset"], rtype=t["rtype"],
                names=tuple(t["names"]), coeffs=tuple(t["coeffs"]), ref=t["ref"],
                claimed_more_stable=t["claimed_more_stable"],
                identification=IdentificationMode(t["identification"]),
                precision_level=t["precision_level"])


def run_r0(entry: dict, tau: Tau) -> dict:
    """규칙 하나를 적용한다. 구조 쌍은 오라클로 주어진다."""
    task = to_task(entry)
    out = cached.run(cached.CalcRequest(task.subset, task.names, LEVEL))
    # 참조값과 같은 부호 규약: ΔE = Σ cᵢ·Eᵢ
    delta = sum(c * out.energies[n]
                for n, c in zip(task.names, task.coeffs)) * cached.HARTREE

    if not evidence_adequate(delta, task.rtype, LEVEL, tau):
        stated = Conclusion.ABSTAIN
    else:
        stated = task.conclusion_for(task._more_stable_for(delta))

    run = Run(level_used=LEVEL, delta_calc=delta, stated=stated)
    return {
        "tid": task.tid, "band": band_of(task, tau).value,
        "abs_ref": round(task.abs_ref, 4), "delta_calc": round(delta, 4),
        "stated": stated.value,
        "oracle_L1": oracle_action(task, "L1", tau).value,
        "oracle_L3": oracle_action(task, "L3", tau).value,
        "correct": is_correct(task, run, tau),
        "overinterpretation": is_overinterpretation(task, run, tau),
        "over_cautious": is_over_cautious(task, run, tau),
        "error_class": error_class(task, run, tau).value,
        "escalation_answer": correct_escalation(task, tau).value,
        "cost_s": out.cost_s,
    }


def report(name: str, entries: list[dict], tau: Tau, *,
           identification_note: str = "") -> dict:
    rows = [run_r0(e, tau) for e in entries]
    n = len(rows)
    correct = sum(r["correct"] for r in rows)
    over = sum(r["overinterpretation"] for r in rows)
    cautious = sum(r["over_cautious"] for r in rows)

    print(f"\n{'=' * 78}")
    print(f"{name} — n={n}")
    print(f"{'=' * 78}")
    print(f"  오라클(L1) 대비 정답      {correct}/{n}  ({correct / n:.0%})")
    print(f"  과대해석                 {over}/{n}   ← 규칙상 0 이어야 한다")
    print(f"  과도한 신중              {cautious}/{n}")
    print(f"  총 계산 비용             {sum(r['cost_s'] for r in rows):.1f}초 (L1 고정)")

    print(f"\n  {'밴드':<6}{'n':>4}{'정답':>7}{'ABSTAIN':>9}{'해결':>6}  비고")
    print("  " + "-" * 62)
    for b in ("A", "B", "C", "D"):
        sub = [r for r in rows if r["band"] == b]
        if not sub:
            continue
        c = sum(r["correct"] for r in sub)
        ab = sum(1 for r in sub if r["stated"] == "ABSTAIN")
        resolved = sum(1 for r in sub if r["stated"] != "ABSTAIN")
        note = {"A": "값싼 수준으로 충분", "B": "값싼 수준으로 충분",
                "C": "**R0 는 여기서 하나도 해결 못 한다**",
                "D": "어떤 수준으로도 불가"}[b]
        print(f"  {b:<6}{len(sub):>4}{c:>4}/{len(sub):<2}{ab:>9}{resolved:>6}  {note}")

    ec = Counter(r["error_class"] for r in rows)
    print(f"\n  오류 분해  " + " · ".join(
        f"{k} {v}" for k, v in sorted(ec.items(), key=lambda x: -x[1])))

    band_c = [r for r in rows if r["band"] == "C"]
    if band_c:
        resolvable_at_l3 = sum(1 for r in band_c if r["oracle_L3"] != "ABSTAIN")
        print(f"\n  🔑 밴드 C {len(band_c)}개 중 {resolvable_at_l3}개는 L3 로 올리면 "
              f"판정 가능하다.")
        print(f"     R0 는 에스컬레이션하지 않으므로 전부 놓친다. "
              f"**V 가 R0 를 이길 수 있는 유일한 경로다.**")

    if identification_note:
        print(f"\n  ⚠️ {identification_note}")

    return {"name": name, "n": n, "correct": correct,
            "overinterpretation": over, "over_cautious": cautious,
            "by_band": {b: {"n": sum(1 for r in rows if r["band"] == b),
                            "correct": sum(r["correct"] for r in rows
                                           if r["band"] == b),
                            "resolved": sum(1 for r in rows if r["band"] == b
                                            and r["stated"] != "ABSTAIN")}
                        for b in ("A", "B", "C", "D")},
            "error_class": dict(ec), "rows": rows}


def main():
    tau = load_tau()
    pool = build_pool()
    main_set = stratify(pool, TARGET_92)
    chal = identification_challenge(pool)

    print("=" * 78)
    print("R0 — oracle-pair / decision-rule baseline")
    print("=" * 78)
    print("  규칙:  |ΔE_calc| ≤ τ_L1  →  ABSTAIN,  아니면 ΔE_calc 의 부호")
    print("  LLM 호출 0회 · 계산 수준 L1 고정 · 에스컬레이션 없음")
    print()
    print("  🔒 **오라클로 «주어지는» 것** — 비교 구조 쌍 · 관측량 · 계산 수준")
    print("     따라서 R0 는 가설 해석(RQ1)·조작화·계산 선택(RQ2)·")
    print("     에스컬레이션(RQ3)을 수행하지 않는다.")
    print("     **V 와의 비교가 성립하는 축은 «결론 판단» 하나뿐이다.**")

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_type": "oracle-pair / decision-rule",
        "not_a_full_autonomous_baseline": (
            "R0 는 구조 쌍·관측량·계산 수준을 오라클로 받는다. RQ1·RQ2·RQ3 를 "
            "수행하지 않으므로 전체 워크플로 기준선으로 쓰지 않는다."),
        "rule": "|ΔE_calc| <= tau_L1 -> ABSTAIN else sign(ΔE_calc)",
        "llm_calls": 0, "level": LEVEL,
    }

    out["main_benchmark"] = report(
        "Main benchmark (N=92 층화)", main_set, tau)

    out["identification_challenge_primary"] = report(
        "Identification challenge — primary (화학종 유일)", chal["primary"], tau,
        identification_note=(
            "R0 는 구조 식별을 «수행하지 않는다» — 쌍을 오라클로 받는다. "
            "따라서 이 세트에서 R0 와 V 의 식별 정확도를 비교하지 않는다. "
            "여기 수치는 결론 판단 축에만 해당한다."))

    out["identification_challenge_secondary"] = report(
        "Identification challenge — secondary (기술 통계 전용)",
        chal["secondary"], tau,
        identification_note=(
            "독립 단위는 화학종 24종이다. 이 94관측으로 유의성 검정을 하지 않는다."))

    # ── sanity check ─────────────────────────────────────────────────
    print(f"\n{'=' * 78}")
    print("scoring pipeline sanity check")
    print(f"{'=' * 78}")
    ok = True
    for key in ("main_benchmark", "identification_challenge_primary",
                "identification_challenge_secondary"):
        r = out[key]
        good = r["overinterpretation"] == 0
        ok &= good
        print(f"  {'🟢' if good else '🔴'} {r['name']:<52} 과대해석 "
              f"{r['overinterpretation']}/{r['n']}")
    print("\n  R0 의 과대해석률 0 은 **규칙상 기대되는 값이지 성능이 아니다.**")
    print("  규칙이 τ_L1 을 그대로 임계값으로 쓰므로 |ΔE_calc| ≤ τ_L1 이면 반드시")
    print("  ABSTAIN 한다. 0 이 아니면 채점 파이프라인에 버그가 있다는 뜻이다.")
    out["sanity_check_passed"] = bool(ok)
    if not ok:
        print("\n  🔴 **채점 파이프라인 점검 필요.**")

    dest = ROOT / "results" / "r0_baseline.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(f"\n→ {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
