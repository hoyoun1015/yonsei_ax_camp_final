"""L0 — 오염 프로브 (G5). LLM 단독, 도구 없음. 과제당 1호출.

**무엇을 검정하는가.** GMTKN55 는 공개 벤치마크다. 모델이 참조값을 외웠다면 계산
없이도 방향을 맞힐 수 있고, 그러면 **"도구를 썼기 때문에 맞혔다"는 주장이 무너진다.**

게이트 G5 (기획안 §10) — **L0 정확도가 R0 보다 유의하게 낮아야 한다.**
비슷하면 오염이므로 좌표 난독화·서브셋 교체를 검토하고, 그래도 남으면 정직하게
보고하고 밴드 C·D 중심으로 분석을 재배치한다.

**L0 는 V 에서 «도구만» 뺀 ablation 이다.** 가설·후보 구조 서술·τ 정보는 V 와 동일하게
주고 계산 능력만 없앤다. τ 를 빼면 "보류할 근거를 못 줘서 못 보류했다"가 되어 오염
측정이 아니라 프롬프트 결핍 측정이 된다.

**구조 이름은 익명화한다** — `H_ttt` 같은 이름에 회전각 패턴이 인코딩돼 있어 그대로
주면 그것 자체가 힌트다(오염 방어).

사용:
    python3 src/vccl/agents/l0.py                    # main N=92 전량
    python3 src/vccl/agents/l0.py --limit 5          # 일부만 (점검용)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents import quota_ledger, schemas  # noqa: E402
from vccl.agents.backend import Backend, Ledger, read_quota  # noqa: E402
from vccl.agents.loop import anonymize  # noqa: E402
from vccl.agents.pilot import phrase  # noqa: E402
from vccl.agents.r0 import to_task  # noqa: E402
from vccl.scoring.labels import Conclusion, Tau, band_of  # noqa: E402
from vccl.tasks.gmtkn import describe, load_reactions, species_map  # noqa: E402
from vccl.tasks.pairs import build_pool, load_tau  # noqa: E402

GMTKN = ROOT / "data" / "reference" / "gmtkn55"
STAGE_B = ROOT / "data" / "tasks" / "frozen_stage_b_v1.json"
R0_RESULT = ROOT / "results" / "r0_baseline.json"


def build_prompt(entry: dict, tau: Tau) -> tuple[str, dict]:
    task = to_task(entry)
    rxns = load_reactions(GMTKN, task.subset)
    smap = species_map(rxns)
    desc = {x: describe(GMTKN / task.subset / x / "struc.xyz")
            for x in {y for r in rxns for y in r.names}}
    members = sorted(x for x in desc if smap[x] == smap[task.names[0]])
    to_label, from_label = anonymize(members, task.tid)
    cand = "\n".join(f"- **{to_label[m]}**: {phrase(desc[m], 'L2')}" for m in members)

    prompt = f"""당신은 계산화학자다. 아래 가설을 판정하라.

## 가설

> {entry["hypothesis"]["neutral"]}

## 사용 가능한 구조

{cand}

## 이 문제의 조건 — **계산 도구를 쓸 수 없다**

양자화학 계산을 실행할 수 없다. 좌표도 주어지지 않았다. 위 기하 서술과 당신의
화학 지식만으로 판정해야 한다.

참고로 이 계열의 계산 방법오차는 다음과 같다.

- 저비용 방법(GFN2-xTB): **{tau.get(task.rtype, 'L1'):.2f} kcal/mol**
- 고비용 방법(B3LYP-D3(BJ)/def2-TZVP): **{tau.get(task.rtype, 'L3'):.2f} kcal/mol**

두 구조의 에너지 차이가 이보다 작다면 계산으로도 판정할 수 없는 크기다.

## 할 일

- **SUPPORTED** — 가설이 맞다고 판단한다
- **REFUTED** — 가설이 틀렸다고 판단한다
- **ABSTAIN** — 계산 없이는 판단할 수 없다

그리고 지금 답하고 있는 원 가설을 그대로 다시 적는다."""
    return prompt, from_label


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-3.6-flash-high")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    tau = load_tau()
    sb = json.loads(STAGE_B.read_text())
    want = set(sb["primary_experiment"]["main_benchmark"]["task_ids"])
    entries = [t for t in build_pool() if t["tid"] in want]
    entries.sort(key=lambda t: (t["band"], t["tid"]))     # 동결된 결정론적 순서
    if args.limit:
        entries = entries[:args.limit]
    if not args.limit and len(entries) != len(want):
        raise SystemExit(f"과제 수 불일치: {len(entries)} / {len(want)}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "experiments" / f"L0_{stamp}_{args.model}"
    ledger = Ledger(out_dir / "calls.jsonl")

    print("=" * 78)
    print("L0 — 오염 프로브 (G5) · LLM 단독, 도구 없음")
    print("=" * 78)
    print(f"  모델 {args.model} · 과제 {len(entries)}개 · 과제당 1호출")
    print("  V 에서 «도구만» 뺀 ablation — 가설·후보·τ 는 동일하게 준다\n")

    q0 = read_quota()
    be = Backend(model=args.model, ledger=ledger, condition="L0")

    rows, failed = [], []
    for i, e in enumerate(entries, 1):
        task = to_task(e)
        prompt, _ = build_prompt(e, tau)
        try:
            got = be.ask(task_id=task.tid, agent_role="L0", round=1, prompt=prompt,
                         schema=schemas.CONCLUDE,
                         prompt_version=f"{schemas.PROMPT_VERSION}/L0")
            stated = Conclusion(got["conclusion"])
        except Exception as ex:  # noqa: BLE001
            failed.append({"tid": task.tid, "error": f"{type(ex).__name__}: {ex}"})
            print(f"  [{i:>3}/{len(entries)}] {task.tid:<28} FAILED", flush=True)
            continue

        ref_stable = task.reference_more_stable
        direction_right = (stated is not Conclusion.ABSTAIN
                           and stated is task.conclusion_for(ref_stable))
        rows.append({
            "tid": task.tid, "band": band_of(task, tau).value,
            "abs_ref": round(task.abs_ref, 4), "stated": stated.value,
            "committed": stated is not Conclusion.ABSTAIN,
            "direction_right": direction_right,
            "restated": got.get("restates_original_hypothesis", "")[:200],
        })
        print(f"  [{i:>3}/{len(entries)}] {task.tid:<28} {stated.value:<10}"
              f"{'✓' if direction_right else ('·' if stated is Conclusion.ABSTAIN else '✗')}",
              flush=True)

    q1 = read_quota()
    quota_ledger.record(model=args.model, n_calls=len(ledger.calls),
                        tokens=ledger.summary()["usage"], before=q0, after=q1,
                        seconds=0.0, context="L0/G5")

    n = len(rows)
    committed = [r for r in rows if r["committed"]]
    right = [r for r in committed if r["direction_right"]]

    print(f"\n{'=' * 78}")
    print(f"L0 결과 — n={n} (FAILED {len(failed)})")
    print(f"{'=' * 78}")
    print(f"  단정(commit) 비율        {len(committed)}/{n}  ({len(committed)/n:.0%})")
    print(f"  보류(ABSTAIN)           {n - len(committed)}/{n}")
    print(f"  단정 중 방향 정답        {len(right)}/{len(committed)}"
          f"  ({len(right)/len(committed):.0%})" if committed else "")
    print(f"  전체 대비 방향 정답      {len(right)}/{n}  ({len(right)/n:.0%})")

    print(f"\n  {'밴드':<6}{'n':>4}{'단정':>6}{'방향정답':>9}{'보류':>6}")
    print("  " + "-" * 40)
    for b in ("A", "B", "C", "D"):
        sub = [r for r in rows if r["band"] == b]
        if not sub:
            continue
        c = sum(r["committed"] for r in sub)
        rr = sum(r["direction_right"] for r in sub)
        print(f"  {b:<6}{len(sub):>4}{c:>6}{rr:>9}{len(sub) - c:>6}")

    # ── G5 판정 — R0 와 대조 ─────────────────────────────────────────
    #
    # 🔒 **두 조건을 «같은 지표»로 비교해야 한다.** 초안은 L0 를 순수 방향 정확도로,
    # R0 를 오라클(τ 기준) 정답으로 재서 비교했다 — R0 는 밴드 C·D 에서 단정하면
    # 오라클이 ABSTAIN 이라 오답 처리되므로 부당하게 낮게 나온다(47 대 실제 56).
    # 오염 프로브가 물어야 하는 것은 «계산 없이 방향을 맞힐 수 있는가»이므로
    # 양쪽 모두 **참조 방향 대비 정확도**로 잰다.
    verdict = None
    if R0_RESULT.exists() and not args.limit:
        r0 = json.loads(R0_RESULT.read_text())["main_benchmark"]
        by_tid = {t["tid"]: t for t in entries}
        r0_committed = r0_right = 0
        for x in r0["rows"]:
            if x["stated"] == "ABSTAIN":
                continue
            r0_committed += 1
            tk = to_task(by_tid[x["tid"]])
            if tk._more_stable_for(x["delta_calc"]) == tk.reference_more_stable:
                r0_right += 1

        print(f"\n{'=' * 78}")
        print("G5 판정 — L0 대 R0 (동일 지표: 참조 방향 대비 정확도)")
        print(f"{'=' * 78}")
        print(f"{'':<24}{'단정':>7}{'방향정답':>10}{'단정중':>9}{'전체중':>9}")
        print("-" * 78)
        print(f"{'L0 (도구 없음)':<24}{len(committed):>7}{len(right):>10}"
              f"{len(right)/len(committed):>8.0%}{len(right)/n:>9.0%}")
        print(f"{'R0 (도구 + 규칙)':<24}{r0_committed:>7}{r0_right:>10}"
              f"{r0_right/r0_committed:>8.0%}{r0_right/r0['n']:>9.0%}")

        l0_acc = len(right) / len(committed) if committed else 0
        r0_acc = r0_right / r0_committed if r0_committed else 0
        print(f"\n  단정 중 정확도 차이  {r0_acc - l0_acc:+.0%}p (R0 − L0)")
        print(f"  전체 중 정확도 차이  {r0_right/r0['n'] - len(right)/n:+.0%}p")
        print(f"\n  참고 — 이진 방향이므로 무작위 기대값은 50% 다. "
              f"L0 는 {l0_acc:.0%}.")

        if l0_acc >= r0_acc - 0.05:
            verdict = "FAIL"
            print("\n  🔴 **G5 실패 위험** — L0 가 R0 에 근접하거나 넘어섰다.")
            print("     참조값 기억(오염)을 의심해야 한다. 좌표 난독화·서브셋 교체를")
            print("     검토하고, 그래도 남으면 정직하게 보고하고 밴드 C·D 중심으로")
            print("     분석을 재배치한다(기획안 §10).")
        else:
            verdict = "PASS"
            print("\n  🟢 **G5 통과** — 도구 없는 L0 가 R0 보다 뚜렷하게 낮다.")
            print("     «도구를 썼기 때문에 맞혔다»는 주장이 유지된다.")
        g5 = {"metric": "참조 방향 대비 정확도 (양 조건 동일)",
              "l0": {"committed": len(committed), "right": len(right),
                     "acc_when_committed": round(l0_acc, 4),
                     "acc_overall": round(len(right) / n, 4)},
              "r0": {"committed": r0_committed, "right": r0_right,
                     "acc_when_committed": round(r0_acc, 4),
                     "acc_overall": round(r0_right / r0["n"], 4)},
              "margin_when_committed_pp": round((r0_acc - l0_acc) * 100, 1),
              "random_baseline_pct": 50, "verdict": verdict}
    else:
        g5 = None

    summ = ledger.summary()
    (out_dir / "l0_result.json").write_text(json.dumps(
        {"model": args.model, "condition": "L0", "n": n, "failed": failed,
         "committed": len(committed), "direction_right": len(right),
         "g5_verdict": verdict, "g5": g5, "rows": rows, "ledger_summary": summ,
         "quota_before": q0, "quota_after": q1},
        ensure_ascii=False, indent=2) + "\n")

    fail_pct = len(failed) / len(entries) * 100 if entries else 0
    print(f"\n  호출 {summ['n_calls']} · 토큰 {summ['usage']['total_tokens']:,}")
    print(f"  FAILED {len(failed)}/{len(entries)} ({fail_pct:.1f}%)"
          + ("  🔴 5% 초과 — 이 실행을 무효로 보고 재실행할 것" if fail_pct > 5 else ""))
    print(f"  quota 5시간 "
          f"{q0.get('Gemini Models', {}).get('Five Hour Limit Remaining')} → "
          f"{q1.get('Gemini Models', {}).get('Five Hour Limit Remaining')}")
    print(f"\n→ {out_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
