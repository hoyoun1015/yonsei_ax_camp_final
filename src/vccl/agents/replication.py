"""부차 실험 — cross-model replication (`claude-sonnet-4-6` · condition V 만).

사전등록: `docs/DECISION_LOG.md` 2026-08-14 (2). **결과를 보기 전에 확정했다.**

**동결본을 그대로 쓴다.** 프롬프트·채점·τ·라벨·과제를 새로 만들지 않고
`main_run` 의 것을 그대로 import 한다. 사본을 만들면 갈라진다.

🔒 **사전등록 규칙을 코드로 강제한다.**

  실행 모드(`--chunk 1..4`)는 **성능 지표를 출력하지 않는다.** quota · FAILED ·
  실행 무결성만 찍는다. 중간 결과를 본 뒤 설계를 흔드는 일을 막기 위해서다.

  성능은 `--report` 로만 볼 수 있고, **30과제 전량이 끝나야** 동작한다.

사용:
    python3 src/vccl/agents/replication.py --chunk 1    # 8과제 (1~8)
    python3 src/vccl/agents/replication.py --chunk 2    # 8과제 (9~16)
    python3 src/vccl/agents/replication.py --chunk 3    # 7과제 (17~23)
    python3 src/vccl/agents/replication.py --chunk 4    # 7과제 (24~30)
    python3 src/vccl/agents/replication.py --report     # 30과제 완료 후에만
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents import quota_ledger  # noqa: E402
from vccl.agents.backend import Backend, Ledger, read_quota  # noqa: E402
from vccl.agents.loop import run_task  # noqa: E402
from vccl.agents.main_run import (  # noqa: E402
    ABORT_PCT, case_study_score, score_run, to_spec, verify_frozen,
)
from vccl.tasks.pairs import build_pool, load_tau  # noqa: E402

STAGE_A = ROOT / "data" / "tasks" / "frozen_rules_v1.json"
STAGE_B = ROOT / "data" / "tasks" / "frozen_stage_b_v1.json"
ORDER = ROOT / "data" / "tasks" / "execution_order_v1.json"
HEADROOM = ROOT / "results" / "oracle_headroom_audit.json"
MAIN_AGG = ROOT / "results" / "main_run_aggregate.json"
MODEL = "claude-sonnet-4-6"
CONDITION = "V"
N_TOTAL = 30
# 실행 분할 — DECISION_LOG 2026-08-14 (3) schedule-only amendment.
# Claude 5시간 창은 **약 60~70호출**이고(Gemini 566 과 다르다) sonnet 은 과제당
# 6.1호출을 쓴다. 8과제 ≈ 49호출로 25% 여유를 둔다. 15+15·10×3 은 창을 넘거나
# 한도에 너무 가깝다. **N·subset·순서·모델·프롬프트·채점은 바뀌지 않았다.**
CHUNKS = (8, 8, 7, 7)
CLAUDE_CALLS_PER_WINDOW = 65      # 5시간 100% 를 호출 수로 환산한 관측값
# 사전등록된 subset 해시 — Batch 1 의 30과제·동일 순서
SUBSET_SHA = "e5fafe10c47cdb6b"


def chunk_slice(n: int) -> slice:
    """chunk 번호(1-based) → subset 의 구간. 경계는 CHUNKS 로 완전히 정해진다."""
    start = sum(CHUNKS[:n - 1])
    return slice(start, start + CHUNKS[n - 1])


def frozen_hashes() -> dict[str, str]:
    """실행 시점의 동결 해시. 나중에 «어느 setup 으로 얻었나» 를 되짚기 위해 남긴다."""
    return {"stage_a": json.loads(STAGE_A.read_text())["sha256"],
            "stage_b": json.loads(STAGE_B.read_text())["sha256"],
            "execution_order": json.loads(ORDER.read_text())["sha256"]}


def subset() -> list[str]:
    """사전등록 subset. `execution_order_v1.json` Batch 1 을 그대로 쓴다."""
    import hashlib
    ids = json.loads(ORDER.read_text())["batches"][0]["task_ids"]
    got = hashlib.sha256(json.dumps(ids).encode()).hexdigest()[:16]
    if got != SUBSET_SHA or len(ids) != N_TOTAL:
        raise SystemExit(
            f"🔴 subset 이 사전등록과 다르다 (해시 {got} != {SUBSET_SHA}, n={len(ids)}).\n"
            "DECISION_LOG 2026-08-14 (2) 에 동결된 30과제여야 한다. 중단한다.")
    return ids


def out_dir_for(chunk: int) -> Path | None:
    ds = sorted((ROOT / "experiments").glob(f"repl_c{chunk}_*"))
    return ds[-1] if ds else None


def load_chunk(chunk: int) -> dict | None:
    d = out_dir_for(chunk)
    if d is None:
        return None
    f = d / "replication_result.json"
    return json.loads(f.read_text()) if f.exists() else None


# ── 실행 ─────────────────────────────────────────────────────────────
def run_chunk(chunk: int, model: str):
    v = verify_frozen()
    print("=" * 78)
    print(f"cross-model replication — {model} · condition {CONDITION} · "
          f"chunk {chunk}/{len(CHUNKS)} ({CHUNKS[chunk - 1]}과제)")
    print("=" * 78)
    print("사전등록 docs/DECISION_LOG.md 2026-08-14 (2) · 분할 (3) amendment")
    for name, good, h in v["checks"]:
        print(f"  {'🟢' if good else '🔴'} {name:<40} {h}")
    if not v["ok"]:
        raise SystemExit("\n🔴 동결이 어긋났다. 실행하지 않는다.")

    ids = subset()
    part = ids[chunk_slice(chunk)]
    missing = [c for c in range(1, chunk) if load_chunk(c) is None]
    if missing:
        raise SystemExit(f"🔴 앞선 chunk {missing} 결과가 없다. 순서대로 돌린다.")
    if load_chunk(chunk) is not None:
        raise SystemExit(
            f"🔴 chunk {chunk} 결과가 이미 있다 ({out_dir_for(chunk).name}). "
            "덮어쓰지 않는다 — 재실행이 필요하면 DECISION_LOG 에 근거를 남기고 "
            "기존 디렉터리를 옮길 것.")

    tau = load_tau()
    pool = {t["tid"]: t for t in build_pool()}
    entries = [pool[t] for t in part]
    print(f"\n  과제 {len(entries)}개 · 밴드 "
          + " ".join(f"{k}={v_}" for k, v_ in
                     sorted(Counter(e["band"] for e in entries).items())))
    print(f"  예상 호출 약 {len(entries) * 5}~{len(entries) * 6}회")
    print(f"  사전등록 실패 규칙  FAILED > {ABORT_PCT}% (30과제 기준 2과제 이상)")
    print("\n  🔒 이 모드는 **성능 지표를 출력하지 않는다.** 30과제 전량 완료 후")
    print("     `--report` 로만 본다 (사전등록 2026-08-14 (2)).")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "experiments" / f"repl_c{chunk}_{stamp}_{model}"
    ledger = Ledger(out_dir / "calls.jsonl")
    be = Backend(model=model, ledger=ledger, condition=CONDITION)

    q0 = read_quota()
    cg = q0.get("Claude and GPT models", {})
    print(f"\n  quota(시작)  주간 {cg.get('Weekly Limit Remaining')} · "
          f"5시간 {cg.get('Five Hour Limit Remaining')}")

    rows, cases, t0 = [], [], time.time()
    for i, e in enumerate(entries):
        print(f"\n[{i + 1}/{len(entries)}] {e['tid']}  밴드 {e['band']}", flush=True)
        res = run_task(be, to_spec(e), tau)
        row = score_run(e, res, tau)
        rows.append(row)
        # 🔒 성능을 찍지 않는다 — 실행 사실과 실패 여부만
        print(f"    {'🔴 FAILED' if row['failed'] else '완료'} · 라운드 {row['rounds']}"
              + (f" · ⚠️ {row['error']}" if row["error"] else ""))
        if not row["failed"]:
            s, marks = case_study_score(row, res)
            if s >= 8:
                cases.append({"tid": e["tid"], "condition": CONDITION,
                              "band": row["band"], "score": s, "marks": marks,
                              "trace": res.trace})
        (out_dir / "rows_partial.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2, default=str) + "\n")

    elapsed = time.time() - t0
    q1 = read_quota()
    quota_ledger.record(model=model, n_calls=len(ledger.calls),
                        tokens=ledger.summary()["usage"], before=q0, after=q1,
                        seconds=elapsed, context=f"replication/chunk{chunk}")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "preregistration": "docs/DECISION_LOG.md 2026-08-14 (2)",
        "chunk": chunk, "n_chunks": len(CHUNKS), "model": model,
        "condition": CONDITION,
        "subset_sha16": SUBSET_SHA, "task_ids": part,
        "frozen": frozen_hashes(),
        "elapsed_s": round(elapsed, 1), "rows": rows,
        "case_study_candidates": cases,
        "ledger_summary": ledger.summary(),
        "quota_before": q0, "quota_after": q1,
    }
    (out_dir / "replication_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")
    (out_dir / "rows_partial.json").unlink(missing_ok=True)

    # ── 무결성만 보고한다 ────────────────────────────────────────────
    failed = sum(r["failed"] for r in rows)
    pct = 100.0 * failed / N_TOTAL          # 분모는 사전등록 단위(30과제)
    ls = ledger.summary()
    lines = (out_dir / "calls.jsonl").read_text().splitlines()
    bad = 0
    for ln in lines:
        try:
            json.loads(ln)
        except Exception:  # noqa: BLE001
            bad += 1
    cg1 = q1.get("Claude and GPT models", {})
    print(f"\n{'=' * 78}\n실행 무결성 (성능 지표는 출력하지 않는다)\n{'=' * 78}")
    print(f"  🟢 과제 커버리지        계획 {len(part)} · 실행 {len(rows)} · "
          f"중복 {len(rows) - len({r['tid'] for r in rows})}")
    print(f"  {'🟢' if not bad else '🔴'} 원장 무결          "
          f"{len(lines)}줄 · 요약 {ls['n_calls']} · 파싱실패 {bad}")
    print(f"  {'🟢' if pct <= ABORT_PCT else '🔴'} FAILED             "
          f"{failed}건 (30과제 기준 {pct:.1f}% · 무효 기준 {ABORT_PCT}%)")
    for r in rows:
        if r["failed"]:
            print(f"       {r['tid']:<32} {r['error']}")
    print(f"  호출 {ls['n_calls']} · 실패 {ls['failures']} · "
          f"토큰 {ls['usage']['total_tokens']:,} · 경과 {elapsed / 60:.1f}분")
    print(f"  quota  주간 {cg.get('Weekly Limit Remaining')} → "
          f"{cg1.get('Weekly Limit Remaining')} · 5시간 "
          f"{cg.get('Five Hour Limit Remaining')} → "
          f"{cg1.get('Five Hour Limit Remaining')}")
    print(f"\n→ {out_dir.relative_to(ROOT)}")
    if chunk < len(CHUNKS):
        print(f"\n  다음 — Claude 5시간 quota 가 회복되면 `--chunk {chunk + 1}`.")
        print(f"     (5시간 100% ≈ {CLAUDE_CALLS_PER_WINDOW}호출 · 다음 chunk 약 "
              f"{CHUNKS[chunk]* 6.1:.0f}호출)")
    print("  🔒 성능은 30과제 전량 완료 후 `--report` 로만 본다.")


# ── 보고 (30과제 전량 완료 후에만) ───────────────────────────────────
def mcnemar(a: dict, b: dict, ids: list[str], key: str) -> tuple[int, int, float]:
    n01 = sum(1 for t in ids if not a[t][key] and b[t][key])
    n10 = sum(1 for t in ids if a[t][key] and not b[t][key])
    n = n01 + n10
    p = 1.0 if n == 0 else min(
        1.0, 2 * sum(comb(n, k) for k in range(min(n01, n10) + 1)) / 2 ** n)
    return n10, n01, p


def report():
    got = [load_chunk(c) for c in range(1, len(CHUNKS) + 1)]
    if any(g is None for g in got):
        state = ' · '.join(f"c{i + 1} {'완료' if g else '미완'}"
                           for i, g in enumerate(got))
        raise SystemExit(
            "🔴 30과제가 아직 끝나지 않았다 — 부분 결과를 해석하지 않는다.\n"
            f"   {state}\n"
            "   (사전등록 docs/DECISION_LOG.md 2026-08-14 (2)·(3))")
    rows = {r["tid"]: r for g in got for r in g["rows"]}
    ids = subset()
    assert set(rows) == set(ids), "subset 이 사전등록과 다르다"

    failed = sum(r["failed"] for r in rows.values())
    pct = 100.0 * failed / N_TOTAL
    P = print
    P("=" * 78)
    P(f"cross-model replication 결과 — {MODEL} · V · N={N_TOTAL}")
    P("=" * 78)
    P("사전등록 docs/DECISION_LOG.md 2026-08-14 (2) · 부차 실험 (primary claim 을 바꾸지 않는다)")
    P(f"\n  {'🟢' if pct <= ABORT_PCT else '🔴'} FAILED {failed}/{N_TOTAL} ({pct:.1f}%)"
      + ("" if pct <= ABORT_PCT else "  ← 사전등록 무효 기준 초과"))

    # 비교 대상 — 같은 30과제
    h = json.loads(HEADROOM.read_text())
    r0 = {r["tid"]: r for r in h["rows"]["R0"] if r["tid"] in rows}
    gem = {r["tid"]: r for r in json.loads(MAIN_AGG.read_text())["rows"]["V"]
           if r["tid"] in rows}
    ok = [t for t in ids if not rows[t]["failed"]]

    P(f"\n{'-' * 78}\n기술 통계 (동일 30과제)")
    P(f"  {'':<26}{'sonnet V':>10}{'gemini V':>10}{'R0':>10}")
    for key, label in (("justified_resolution", "justified resolution"),
                       ("reference_direction_correct", "참조방향 정확도"),
                       ("overinterpretation", "과대해석 (§7.1)"),
                       ("over_cautious", "과도한 신중")):
        P(f"  {label:<26}{sum(bool(rows[t][key]) for t in ok):>10}"
          f"{sum(bool(gem[t][key]) for t in ok):>10}"
          f"{sum(bool(r0[t][key]) for t in ok):>10}")
    P(f"  {'L3 사용':<26}{sum(bool(rows[t]['used_l3']) for t in ok):>10}"
      f"{sum(bool(gem[t]['used_l3']) for t in ok):>10}{0:>10}")
    ec = Counter(rows[t]["error_class"] for t in ok)
    P(f"\n  오류 분해 (sonnet)  " + " · ".join(f"{k} {v_}" for k, v_ in ec.most_common()))
    P(f"  식별 정확도 (자율식별형 한정)  "
      f"{sum(1 for t in ok if rows[t]['identification_accuracy'])}/"
      f"{sum(1 for t in ok if rows[t]['identification_accuracy'] is not None)}")

    P(f"\n{'-' * 78}\n사전 지정 검정 2개 (정확 McNemar · 양측 · α=0.05 · paired)")
    for a, b, name in ((rows, r0, "V_sonnet vs R0"),
                       (rows, gem, "V_sonnet vs V_gemini")):
        n10, n01, p = mcnemar(a, b, ok, "justified_resolution")
        P(f"  {name:<26} {sum(bool(a[t]['justified_resolution']) for t in ok)} vs "
          f"{sum(bool(b[t]['justified_resolution']) for t in ok)}  "
          f"불일치 {n10}:{n01}  p={p:.4g}  {'*' if p < 0.05 else ''}")

    s_jr = sum(bool(rows[t]["justified_resolution"]) for t in ok)
    r_jr = sum(bool(r0[t]["justified_resolution"]) for t in ok)
    P(f"\n  📌 사전 정의된 판정 — R0 대비 justified resolution 이 «같은 방향(우위)»인가")
    P(f"     sonnet {s_jr} vs R0 {r_jr} → "
      f"**{'패턴이 복제됐다' if s_jr > r_jr else '복제되지 않았다'}**")

    bc = [t for t in ok if rows[t]["band"] == "C"]
    P(f"\n{'-' * 78}\n밴드 C (n={len(bc)}) — **기술 통계만. 검정력이 없어 유의성을 주장하지 않는다**")
    P(f"  sonnet justified {sum(bool(rows[t]['justified_resolution']) for t in bc)}/{len(bc)}"
      f" · L3 상승 {sum(bool(rows[t]['used_l3']) for t in bc)}/{len(bc)}")
    P(f"  gemini justified {sum(bool(gem[t]['justified_resolution']) for t in bc)}/{len(bc)}"
      f" · R0 justified {sum(bool(r0[t]['justified_resolution']) for t in bc)}/{len(bc)}")

    P(f"\n  🔒 모델 우열을 주장하지 않는다 (30과제·V 단독·단일 실행).")
    P("  🔒 V−τ 를 복제하지 않았으므로 τ 효과의 모델 간 일반화를 주장하지 않는다.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk", type=int, choices=tuple(range(1, len(CHUNKS) + 1)))
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--model", default=MODEL)
    a = ap.parse_args()
    if a.report:
        report()
    elif a.chunk:
        run_chunk(a.chunk, a.model)
    else:
        ap.error("--chunk 1..4 또는 --report 중 하나를 준다")


if __name__ == "__main__":
    main()
