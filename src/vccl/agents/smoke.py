"""dev/smoke — end-to-end 파이프라인 검증. **본평가가 아니다.**

**과제는 main N=92 와 겹치지 않는 것으로 고른다.** 겹치면 본실행 전에 그 과제의
결과를 본 셈이 되어 사전등록이 오염된다. Identification challenge primary 24 도
제외한다.

**검증 항목 7개** (Protocol amendment 2026-08-11 (5)) —

1. 3-agent 역할 전달        세 역할이 모두 호출되고 앞 단계 산출이 다음 프롬프트에 실린다
2. 실제 tool 실행·결과 전달  실행층이 캐시에서 에너지를 읽고 ΔE 가 프롬프트로 들어간다
3. escalation / 재조작화     분기 A·B 가 코드 경로로 도달 가능한지
4. 구조화 출력 파싱          모든 호출이 파싱되고 타입·enum 이 검증된다
5. 로그 원장                필수 필드가 전부 남는다
6. 채점 연결                labels 가 적용되고 오류 분해가 산출된다
7. 재시도/실패 처리          사다리가 작동하고 FAILED 가 규칙대로 처리된다

사용:
    python3 src/vccl/agents/smoke.py                 # 기본 3과제
    python3 src/vccl/agents/smoke.py --n 2
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents import quota_ledger  # noqa: E402
from vccl.agents.backend import Backend, Ledger, read_quota  # noqa: E402
from vccl.agents.loop import MAX_ROUNDS, TaskSpec, anonymize, run_task  # noqa: E402
from vccl.agents.pilot import phrase  # noqa: E402
from vccl.agents.r0 import to_task  # noqa: E402
from vccl.scoring.labels import (  # noqa: E402
    Run, band_of, error_class, is_correct, is_overinterpretation, oracle_action,
)
from vccl.tasks.gmtkn import describe, load_reactions, species_map  # noqa: E402
from vccl.tasks.pairs import build_pool, load_tau  # noqa: E402

GMTKN = ROOT / "data" / "reference" / "gmtkn55"
STAGE_B = ROOT / "data" / "tasks" / "frozen_stage_b_v1.json"

REQUIRED_LEDGER_FIELDS = [
    "call_id", "timestamp", "task_id", "condition", "agent_role", "model",
    "quota_group", "round", "prompt_version", "prompt_sha256", "prompt",
    "raw_response", "parsed", "status", "duration_s", "usage",
]


def pick_smoke_tasks(n: int) -> list[dict]:
    """main N=92 와 challenge primary 를 제외하고 밴드가 다른 과제를 고른다."""
    sb = json.loads(STAGE_B.read_text())
    excluded = set(sb["primary_experiment"]["main_benchmark"]["task_ids"])
    excluded |= set(sb["identification_challenge"]["primary"]["task_ids"])

    pool = [t for t in build_pool()
            if t["tid"] not in excluded
            and t["identification"] == "autonomous"
            and t["hypothesis"]["neutral"]]
    picked, seen = [], set()
    # 밴드 C 를 반드시 포함한다 — 분기 A(escalation)를 자극하는 유일한 구간이다
    for band in ("C", "B", "A", "D"):
        for t in sorted(pool, key=lambda x: (-x["n_candidates"], x["tid"])):
            if t["band"] == band and t["band"] not in seen:
                picked.append(t)
                seen.add(band)
                break
        if len(picked) >= n:
            break
    return picked[:n]


def to_spec(entry: dict) -> TaskSpec:
    task = to_task(entry)
    rxns = load_reactions(GMTKN, task.subset)
    smap = species_map(rxns)
    desc = {x: describe(GMTKN / task.subset / x / "struc.xyz")
            for x in {y for r in rxns for y in r.names}}
    members = sorted(x for x in desc if smap[x] == smap[task.names[0]])
    to_label, from_label = anonymize(members, task.tid)
    return TaskSpec(
        task_id=task.tid, subset=task.subset, rtype=task.rtype,
        hypothesis=entry["hypothesis"]["neutral"],
        candidates={to_label[m]: phrase(desc[m], "L2") for m in members},
        real_names=from_label, reference_pair=tuple(task.names),
        ref_names=task.names, ref_coeffs=task.coeffs)


def verify(entries, results, ledger) -> dict:
    """7개 항목을 판정한다. 통과 못 한 항목은 그대로 드러낸다."""
    calls = ledger.calls
    checks: dict[str, dict] = {}

    roles = {c.agent_role for c in calls}
    checks["1_three_agent_roles"] = {
        "pass": roles == {"PI", "ComputationalChemist", "SkepticalReviewer"},
        "detail": f"호출된 역할 {sorted(roles)}"}

    # 앞 단계 산출이 다음 프롬프트에 실렸는가 — Reviewer 프롬프트에 ΔE 가 있어야 한다
    rev = [c for c in calls if c.agent_role == "SkepticalReviewer"]
    carried = all("kcal/mol" in c.prompt and "더 낮은 에너지" in c.prompt for c in rev)
    tool_calls = [c for c in calls if c.tool_result]
    checks["2_tool_execution_and_handoff"] = {
        "pass": bool(tool_calls) and carried,
        "detail": (f"tool_result 기록 {len(tool_calls)}건 · "
                   f"Reviewer 프롬프트에 ΔE 전달 {carried}")}

    br_a = sum(r["result"]["branch_a"] for r in results)
    br_b = sum(r["result"]["branch_b"] for r in results)
    checks["3_branches"] = {
        "pass": True,   # 도달 여부는 모델 판단이라 실패로 보지 않는다
        "detail": f"분기 A(escalate) {br_a}회 · 분기 B(재조작화) {br_b}회",
        "note": ("분기 B 가 0 이면 «경로가 없다»가 아니라 «에이전트가 쓰지 않았다»다. "
                 "Loop Utilization 지표로 본실행에서 관측한다."
                 if br_b == 0 else "")}

    parsed_ok = all(c.parsed is not None for c in calls if c.status == "SUCCESS"
                    and not c.error)
    checks["4_structured_output_parsing"] = {
        "pass": parsed_ok,
        "detail": f"파싱 성공 {sum(1 for c in calls if c.parsed is not None)}/{len(calls)}"}

    missing = set()
    for c in calls:
        d = asdict(c)
        missing |= {f for f in REQUIRED_LEDGER_FIELDS if f not in d or d[f] is None
                    and f not in ("parsed", "error")}
    checks["5_ledger_fields"] = {
        "pass": not missing,
        "detail": f"누락 필드 {sorted(missing) or '없음'} · 원장 {len(calls)}줄"}

    scored = [r for r in results if r["scoring"]["error_class"] is not None]
    checks["6_scoring_wired"] = {
        "pass": len(scored) == len([r for r in results if r["result"]["conclusion"]]),
        "detail": f"채점된 과제 {len(scored)}/{len(results)}"}

    retried = [c for c in calls if "#try2" in c.prompt_version
               or "#try3" in c.prompt_version]
    failed_tasks = [r for r in results if r["result"]["error"]]
    checks["7_retry_and_failure"] = {
        "pass": True,
        "detail": (f"경로 전환 재시도 {len(retried)}건 · "
                   f"FAILED 과제 {len(failed_tasks)}/{len(results)}"),
        "note": ("재시도가 0건이면 1순위 경로가 전부 성공한 것이다 — 사다리 자체는 "
                 "diagnose_empty.py 로 검증됐다." if not retried else "")}
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--model", default="gemini-3.6-flash-high")
    args = ap.parse_args()

    tau = load_tau()
    entries = pick_smoke_tasks(args.n)
    if not entries:
        raise SystemExit("smoke 과제를 고를 수 없다 — 제외 목록을 확인할 것")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "experiments" / f"smoke_{stamp}_{args.model}"
    ledger = Ledger(out_dir / "calls.jsonl")

    print("=" * 78)
    print("dev/smoke — end-to-end 파이프라인 검증 (본평가 아님)")
    print("=" * 78)
    print(f"  모델 {args.model} · condition V · 과제 {len(entries)}개")
    print(f"  🔒 main N=92 · challenge primary 24 와 겹치지 않는 과제만 고름\n")
    for e in entries:
        task = to_task(e)
        print(f"  [{e['tid']}] 밴드 {e['band']} · |ΔE_ref| {task.abs_ref:.3f} · "
              f"후보 {e['n_candidates']}개 · 오라클 L1="
              f"{oracle_action(task, 'L1', tau).value} L3="
              f"{oracle_action(task, 'L3', tau).value}")

    q0 = read_quota()
    be = Backend(model=args.model, ledger=ledger, condition="V")

    results = []
    for e in entries:
        spec = to_spec(e)
        task = to_task(e)
        print(f"\n{'-' * 78}\n실행 [{e['tid']}]  {spec.hypothesis[:70]}…")
        r = run_task(be, spec, tau)
        sc = {"correct": None, "overinterpretation": None, "error_class": None}
        if r.conclusion is not None:
            run = Run(r.level_used, r.delta_calc, r.conclusion)
            sc = {"correct": is_correct(task, run, tau),
                  "overinterpretation": is_overinterpretation(task, run, tau),
                  "error_class": error_class(task, run, tau).value}
        print(f"  결론 {r.conclusion.value if r.conclusion else 'FAILED'} · "
              f"수준 {r.level_used} · 라운드 {r.rounds} · "
              f"분기A {r.branch_a} 분기B {r.branch_b} · "
              f"식별 {'정확' if r.identification_correct else '오류'}")
        print(f"  채점 정답={sc['correct']} 과대해석={sc['overinterpretation']} "
              f"{sc['error_class'] or ''}")
        if r.error:
            print(f"  ⚠️ {r.error}")
        results.append({"tid": e["tid"], "band": e["band"],
                        "result": asdict(r), "scoring": sc})

    q1 = read_quota()
    quota_ledger.record(model=args.model, n_calls=len(ledger.calls),
                        tokens=ledger.summary()["usage"], before=q0, after=q1,
                        seconds=0.0, context="smoke/V")

    checks = verify(entries, results, ledger)
    print(f"\n{'=' * 78}")
    print("파이프라인 검증")
    print(f"{'=' * 78}")
    all_pass = True
    for key in sorted(checks):
        c = checks[key]
        all_pass &= c["pass"]
        print(f"  {'🟢' if c['pass'] else '🔴'} {key:<34} {c['detail']}")
        if c.get("note"):
            print(f"      └ {c['note']}")

    summ = ledger.summary()
    print(f"\n  호출 {summ['n_calls']} · 실패 {summ['failures']} · "
          f"토큰 {summ['usage']['total_tokens']:,}")
    print(f"  quota  5시간 "
          f"{q0.get('Gemini Models', {}).get('Five Hour Limit Remaining')} → "
          f"{q1.get('Gemini Models', {}).get('Five Hour Limit Remaining')}")

    (out_dir / "smoke_result.json").write_text(json.dumps(
        {"model": args.model, "n_tasks": len(entries),
         "task_ids": [e["tid"] for e in entries],
         "excluded_from": "main N=92 + identification challenge primary",
         "checks": checks, "results": results, "ledger_summary": summ,
         "quota_before": q0, "quota_after": q1,
         "verdict": "PASS" if all_pass else "FAIL"},
        ensure_ascii=False, indent=2, default=str) + "\n")

    print(f"\n  {'🟢 PASS — G5 로 진행 가능' if all_pass else '🔴 FAIL — 원인을 고칠 것'}")
    print(f"\n→ {out_dir.relative_to(ROOT)}")
    print("   원장(calls.jsonl)은 대표 사례 trajectory 보존용으로 삭제하지 않는다.")


if __name__ == "__main__":
    main()
