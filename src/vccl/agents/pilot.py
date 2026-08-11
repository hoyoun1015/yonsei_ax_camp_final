"""3-에이전트 full-loop 파일럿 — 실제 quota 소비량 측정.

**목적은 성능 측정이 아니다.** Stage B(최종 과제 수·반복·ablation 범위)를 동결하기
전에 **호출 하나가 실제로 얼마를 먹는지** 재는 것이다. 대표 과제 3개만 돌린다.

과제는 밴드가 서로 다른 것으로 고른다 — 값싼 수준으로 충분한 것, 상위 계산이
필요한 것, 어떤 수준으로도 판정 불가한 것.

사용:
    python3 src/vccl/agents/pilot.py [--model gemini-3.6-flash-high] [--condition V]
    python3 src/vccl/agents/pilot.py --dry-run     # LLM 호출 없이 과제 구성만 확인
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents.backend import Backend, Ledger  # noqa: E402
from vccl.agents.loop import TaskSpec, anonymize, run_task  # noqa: E402
from vccl.scoring.labels import (  # noqa: E402
    Band, IdentificationMode, Run, Task, Tau, band_of, error_class, is_correct,
    is_overinterpretation, oracle_action,
)
from vccl.tasks.gmtkn import describe, load_reactions, reaction_type, species_map  # noqa: E402

GMTKN = ROOT / "data" / "reference" / "gmtkn55"
FROZEN = ROOT / "data" / "tasks" / "frozen_rules_v1.json"
PILOT_SUBSET = "ACONF"          # 자율 식별 가능률이 가장 높고(87%) 계산이 전량 캐시돼 있다

TORSION_KO = {"anti": "anti", "gauche": "gauche", "skew": "skew(anticlinal)",
              "syn": "syn(겹침)"}


def load_tau() -> Tau:
    d = json.loads(FROZEN.read_text())
    vals = {(rt, lv): v for rt, lvs in d["tau"]["values"].items()
            for lv, v in lvs.items() if lv in ("L1", "L3")}
    return Tau(vals, floor=d["tau"]["floor"])


def phrase(desc, level: str) -> str:
    """서술자를 자연어 구절로. 최소 정밀도만 쓴다(§4.4)."""
    if level == "L1":
        parts = [f"{TORSION_KO.get(k, k)} {n}개" for k, n in desc.composition]
        s = "회전각이 " + " · ".join(parts) + "인 배좌"
    else:
        s = "회전각이 " + "-".join(TORSION_KO.get(t, t) for t in desc.unsigned) + " 순서인 배좌"
    if desc.hbonds:
        s += f" (분자 내 수소결합 {desc.hbonds}개)"
    return s


def build_specs(tau: Tau, n: int = 3):
    """밴드가 서로 다른 대표 과제를 고른다."""
    rxns = load_reactions(GMTKN, PILOT_SUBSET)
    smap = species_map(rxns)
    rtype = reaction_type(PILOT_SUBSET)
    desc = {n_: describe(GMTKN / PILOT_SUBSET / n_ / "struc.xyz")
            for n_ in {x for r in rxns for x in r.names}}

    # 화학종 안에서 유일해지는 최소 정밀도
    def min_level(names):
        for lv in ("L1", "L2"):
            ok = True
            for nm in names:
                sp = smap[nm]
                same = [o for o in desc if smap[o] == sp
                        and desc[o].at(lv) == desc[nm].at(lv)]
                if len(same) != 1:
                    ok = False
                    break
            if ok:
                return lv
        return None

    pool = []
    for r in rxns:
        if len(r.names) != 2 or sorted(r.coeffs) != [-1, 1] or r.ref == 0:
            continue
        lv = min_level(r.names)
        if lv is None:
            continue
        rng = random.Random(f"claim::{r.rid}")
        neg = next(x for x, c in zip(r.names, r.coeffs) if c < 0)
        pos = next(x for x, c in zip(r.names, r.coeffs) if c > 0)
        true_stable = neg if r.ref > 0 else pos
        other = pos if true_stable == neg else neg
        # 절반은 참인 방향, 절반은 거짓 방향으로 주장해 SUPPORTED/REFUTED 를 섞는다
        claimed = true_stable if rng.random() < 0.5 else other
        task = Task(tid=r.rid, subset=PILOT_SUBSET, rtype=rtype, names=r.names,
                    coeffs=r.coeffs, ref=r.ref, claimed_more_stable=claimed,
                    identification=IdentificationMode.AUTONOMOUS, precision_level=lv)
        pool.append((task, lv))

    # 밴드별로 하나씩
    picked, seen = [], set()
    for want in (Band.D, Band.C, Band.B, Band.A):
        for task, lv in pool:
            if band_of(task, tau) is want and task.tid not in seen:
                picked.append((task, lv))
                seen.add(task.tid)
                break
        if len(picked) >= n:
            break

    specs = []
    for task, lv in picked:
        species = smap[task.names[0]]
        members = sorted(x for x in desc if smap[x] == species)
        to_label, from_label = anonymize(members, task.tid)
        claimed_lab = to_label[task.claimed_more_stable]
        other = next(x for x in task.names if x != task.claimed_more_stable)
        hyp = (f"{phrase(desc[task.claimed_more_stable], lv)}가 "
               f"{phrase(desc[other], lv)}보다 전자에너지가 낮아 더 안정할 것이다.")
        specs.append((task, TaskSpec(
            task_id=task.tid, subset=PILOT_SUBSET, rtype=task.rtype, hypothesis=hyp,
            candidates={to_label[m]: phrase(desc[m], "L2") for m in members},
            real_names=from_label, reference_pair=tuple(task.names),
            ref_names=task.names, ref_coeffs=task.coeffs), claimed_lab, lv))
    return specs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-3.6-flash-high")
    ap.add_argument("--condition", default="V", choices=["V", "V-tau"])
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tau = load_tau()
    specs = build_specs(tau, args.n)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "experiments" / f"pilot_{stamp}_{args.model}_{args.condition}"
    ledger = Ledger(out_dir / "calls.jsonl")

    print(f"파일럿 — 모델 {args.model} · condition {args.condition} · 과제 {len(specs)}개")
    print(f"원장 {ledger.path.relative_to(ROOT)}\n")

    for task, spec, claimed_lab, lv in specs:
        b = band_of(task, tau)
        print(f"[{task.tid}] 밴드 {b.value} · |ΔE_ref| {task.abs_ref:.3f} · "
              f"최소정밀도 {lv} · 후보 {len(spec.candidates)}개")
        print(f"  가설: {spec.hypothesis}")
        print(f"  (정답: 오라클 L1={oracle_action(task, 'L1', tau).value} / "
              f"L3={oracle_action(task, 'L3', tau).value})")
    if args.dry_run:
        print("\n--dry-run — LLM 을 호출하지 않고 종료한다.")
        (out_dir / "specs.json").write_text(json.dumps(
            [{"task": t.tid, "band": band_of(t, tau).value, "hypothesis": s.hypothesis,
              "candidates": s.candidates, "min_level": lv}
             for t, s, _, lv in specs], ensure_ascii=False, indent=2))
        return

    be = Backend(model=args.model, ledger=ledger, condition=args.condition)
    tau_for_agent = None if args.condition == "V-tau" else tau

    results = []
    for task, spec, _, lv in specs:
        print(f"\n{'=' * 70}\n실행 [{task.tid}]")
        r = run_task(be, spec, tau_for_agent)
        ok = None if r.conclusion is None else is_correct(
            task, Run(r.level_used, r.delta_calc, r.conclusion), tau)
        over = None if r.conclusion is None else is_overinterpretation(
            task, Run(r.level_used, r.delta_calc, r.conclusion), tau)
        ecls = None if r.conclusion is None else error_class(
            task, Run(r.level_used, r.delta_calc, r.conclusion), tau).value
        print(f"  결론 {r.conclusion.value if r.conclusion else '실패'} · "
              f"수준 {r.level_used} · ΔE_calc {r.delta_calc} · 라운드 {r.rounds} · "
              f"분기A {r.branch_a} 분기B {r.branch_b}")
        print(f"  식별 {'정확' if r.identification_correct else '오류'} · "
              f"오라클 대비 {'정답' if ok else '오답'} · 과대해석 {over} · {ecls}")
        if r.error:
            print(f"  ⚠️ {r.error}")
        results.append({"task": task.tid, "band": band_of(task, tau).value,
                        "abs_ref": task.abs_ref, "result": asdict(r),
                        "is_correct": ok, "overinterpretation": over,
                        "error_class": ecls})

    summ = ledger.summary()
    (out_dir / "results.json").write_text(json.dumps(
        {"model": args.model, "condition": args.condition,
         "results": results, "ledger_summary": summ},
        ensure_ascii=False, indent=2, default=str))

    print(f"\n{'=' * 70}\nquota 소비 실측")
    print(f"{'=' * 70}")
    u = summ["usage"]
    n = summ["n_calls"]
    print(f"호출 {n}회 (실패 {summ['failures']}) · 역할별 {summ['by_role']}")
    print(f"토큰 입력 {u['input_tokens']:,} · 출력 {u['output_tokens']:,} · "
          f"사고 {u['thinking_tokens']:,} · 합계 {u['total_tokens']:,}")
    if n:
        print(f"호출당 평균 — 입력 {u['input_tokens'] // n:,} · "
              f"합계 {u['total_tokens'] // n:,}")
        per_task = n / len(specs)
        print(f"과제당 호출 {per_task:.1f}회 · 토큰 {u['total_tokens'] // len(specs):,}")
        print(f"\n120과제 1조건 추정 — 호출 {int(per_task * 120):,}회 · "
              f"토큰 {u['total_tokens'] // len(specs) * 120:,}")
    print(f"\n→ {out_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
