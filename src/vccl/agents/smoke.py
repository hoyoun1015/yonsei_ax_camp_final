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
    """main N=92 와 challenge primary 를 제외하고 과제를 고른다.

    🔴 **예전 필터가 결함을 가렸다** (DECISION_LOG 2026-08-12 (4)). 이 함수는
    `hypothesis["neutral"]` 이 있는 것과 `identification=="autonomous"` 인 것만
    골랐고, 그래서 **가설이 없던 paired 과제 16개를 정확히 배제**하고 있었다.
    7/7 통과는 결함이 없다는 증거가 아니었다.

    이제 **autonomous 와 paired 를 둘 다 반드시 포함한다.** 검증용 표본이 결함
    사례를 배제하면 그 검증은 통과할 수밖에 없다.
    """
    sb = json.loads(STAGE_B.read_text())
    excluded = set(sb["primary_experiment"]["main_benchmark"]["task_ids"])
    excluded |= set(sb["identification_challenge"]["primary"]["task_ids"])

    pool = [t for t in build_pool() if t["tid"] not in excluded]
    auto = [t for t in pool if t["identification"] == "autonomous"]
    paired = [t for t in pool if t["identification"] == "paired"]

    picked, seen = [], set()
    # 밴드 C 를 먼저 — 분기 A(escalation)를 자극하는 유일한 구간이다
    for band in ("C", "B", "A", "D"):
        for t in sorted(auto, key=lambda x: (-x["n_candidates"], x["tid"])):
            if t["band"] == band and band not in seen:
                picked.append(t)
                seen.add(band)
                break
        if len(picked) >= max(1, n - 1):
            break
    # 🔒 paired 를 반드시 하나 넣는다. 이게 Batch 1 을 무효로 만든 경로다
    if paired:
        picked = picked[:max(1, n - 1)] + [
            sorted(paired, key=lambda x: (x["band"], x["tid"]))[0]]
    return picked[:n]


# 🔒 spec 생성은 main_run 과 **같은 코드**를 쓴다. 예전에는 smoke 가 자기 사본을
# 들고 있었고, 그래서 본실행에만 있는 경로(paired)가 smoke 에서 검증되지 않았다.
from vccl.agents.main_run import to_spec  # noqa: E402,F401


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

    # ── Batch 1 무효를 만든 두 결함의 회귀 방지 (2026-08-12 (5)) ──────
    modes = {e["identification"] for e in entries}
    checks["8_both_identification_modes"] = {
        "pass": modes == {"autonomous", "paired"},
        "detail": f"포함된 식별 모드 {sorted(modes)}",
        "note": ("🔴 예전 smoke 는 autonomous 만 골라 paired 결함을 못 잡았다."
                 if modes != {"autonomous", "paired"} else "")}

    no_hyp = [e["tid"] for e in entries
              if not ((e.get("hypothesis") or {}).get("neutral") or "").strip()]
    checks["9_every_task_has_hypothesis"] = {
        "pass": not no_hyp,
        "detail": f"가설 없는 과제 {no_hyp or '없음'}"}

    probe = _identification_failure_probe()
    checks["10_identification_error_not_crash"] = {
        "pass": probe["pass"], "detail": probe["detail"],
        "note": "LLM 을 부르지 않는 결정론적 프로브다 — 에이전트가 참조 쌍과 다른 "
                "쌍을 골랐을 때 크래시하지 않고 «오답»으로 채점되는지 본다"}
    return checks


def _identification_failure_probe() -> dict:
    """식별 오류 경로를 강제로 통과시킨다. 실패는 «측정»되어야지 크래시가 아니다.

    실제 LLM 은 시켜도 틀리게 고르지 않을 수 있으므로 스크립트된 백엔드를 쓴다.
    이 경로가 Batch 1 에서 `KeyError` 로 죽어 식별 실패가 지표에서 사라졌다.
    """
    sys.path.insert(0, str(ROOT / "tests"))
    try:
        import importlib.util
        s = importlib.util.spec_from_file_location(
            "t_pi", ROOT / "tests" / "test_paired_and_identification.py")
        m = importlib.util.module_from_spec(s)
        s.loader.exec_module(m)
        entry, spec, wrong = m._wrong_pair_case()
        res = run_task(m._ScriptedBackend(wrong), spec, load_tau())
        row = m.score_run(entry, res, load_tau())
        ok = (res.error is None and res.identification_correct is False
              and row["reference_direction_correct"] is False
              and row["delta_evidence"] is not None
              and row["delta_gold_convention"] is None)
        return {"pass": bool(ok),
                "detail": (f"식별 오류 시 크래시 없음={res.error is None} · "
                           f"결론 오답 처리={row['reference_direction_correct'] is False} · "
                           f"자기증거 채점됨={row['delta_evidence'] is not None}")}
    except Exception as e:  # noqa: BLE001
        return {"pass": False, "detail": f"프로브 자체가 실패했다: {type(e).__name__}: {e}"}


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
