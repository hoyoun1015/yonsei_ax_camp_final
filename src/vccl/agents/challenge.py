"""Identification challenge — primary 24 · condition V 단독.

사전등록 `docs/DECISION_LOG.md` 2026-08-14 (4) **pre-execution analysis amendment**.
과제 집합·추론 단위는 `frozen_stage_b_v1.json` 동결본, 조건·통계는 위 amendment.

**동결본을 그대로 쓴다.** 프롬프트·채점·τ·라벨을 새로 만들지 않고 `main_run` 의 것을
import 한다. 사본을 만들면 갈라진다 (2026-08-12 에 smoke 사본 때문에 결함을 놓쳤다).

**왜 V 단독인가.** identification 단계의 프롬프트·모델 설정이 V 와 V−τ 에서 동일하고
(`_tau_block` 은 choose_level·review·conclude 에만 들어간다) **τ manipulation 이
identification 이후에만 개입하므로 V−τ 는 identification ablation 정보를 추가하지 않는다.**

🔒 **역할 한정.** RQ1 전체를 증명하는 실험이 아니다. main benchmark 의 식별 76/76 을
**더 어려운 후보 선택 환경에서 보조 검증**한다.

🔒 **smoke 모드는 성능을 출력하지 않는다.** 실행 경로·task ID·채점 필드·출력 형식만 본다.

사용:
    python3 src/vccl/agents/challenge.py --selftest        # LLM 0회 — 가정·통계 검증
    python3 src/vccl/agents/challenge.py --smoke 2         # 경로 확인 (성능 비출력)
    python3 src/vccl/agents/challenge.py --run             # primary 24 본실행
    python3 src/vccl/agents/challenge.py --report          # 24 완료 후에만
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
    ABORT_PCT, score_run, to_spec, verify_frozen,
)
from vccl.tasks.pairs import build_pool, load_tau  # noqa: E402

STAGE_A = ROOT / "data" / "tasks" / "frozen_rules_v1.json"
STAGE_B = ROOT / "data" / "tasks" / "frozen_stage_b_v1.json"
ORDER = ROOT / "data" / "tasks" / "execution_order_v1.json"
SET = "primary"                  # secondary 94 는 이번 범위가 아니다
CONDITION = "V"
ALPHA = 0.05


# ── 과제 · 가정 ──────────────────────────────────────────────────────
def task_ids() -> list[str]:
    sb = json.loads(STAGE_B.read_text())
    ids = sb["identification_challenge"][SET]["task_ids"]
    n = sb["identification_challenge"][SET]["n"]
    if len(ids) != n:
        raise SystemExit(f"🔴 동결본 불일치: n={n} 인데 task_ids {len(ids)}개")
    return ids


def chance_probs(ids: list[str], pool: dict) -> list[float]:
    """과제별 «무작위 쌍 선택» 정답확률 1/C(후보수, 2).

    가정 — 채점이 후보 n개 중 **순서 없는** 정확한 쌍 하나를 고르는 문제이고
    gold pair 가 유일하다. `--selftest` 가 이를 24과제 전량에서 검증한다.
    """
    out = []
    for t in ids:
        c = len(to_spec(pool[t]).candidates)
        if c < 2:
            raise SystemExit(f"🔴 {t}: 후보가 {c}개 — 쌍을 만들 수 없다")
        out.append(1.0 / comb(c, 2))
    return out


def poisson_binomial_pmf(ps: list[float]) -> list[float]:
    """서로 다른 확률의 베르누이 합의 정확 분포. 동적계획법 — 근사하지 않는다."""
    dist = [1.0]
    for p in ps:
        nxt = [0.0] * (len(dist) + 1)
        for k, v in enumerate(dist):
            nxt[k] += v * (1.0 - p)
            nxt[k + 1] += v * p
        dist = nxt
    return dist


def pb_upper_tail(k: int, ps: list[float]) -> float:
    """단측 p = P(K ≥ k) — «우연보다 높다» 를 검정한다."""
    d = poisson_binomial_pmf(ps)
    return sum(d[k:])


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """정확 신뢰구간. scipy 없이 베타 분위수를 이분법으로 구한다."""
    def beta_cdf(x: float, a: float, b: float) -> float:
        # 정규화 불완전베타 — 연분수 없이 급수로 (a,b 가 작은 정수라 충분하다)
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        # I_x(a,b) = sum_{j=a}^{a+b-1} C(a+b-1, j) x^j (1-x)^{a+b-1-j}   (정수 a,b)
        n_ = int(a + b - 1)
        return sum(comb(n_, j) * x ** j * (1 - x) ** (n_ - j)
                   for j in range(int(a), n_ + 1))

    def solve(target: float, a: float, b: float) -> float:
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if beta_cdf(mid, a, b) > target:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    # Clopper–Pearson: 하한 = Beta(k, n−k+1) 의 α/2 분위수 ·
    #                  상한 = Beta(k+1, n−k) 의 1−α/2 분위수
    lower = 0.0 if k == 0 else solve(alpha / 2, k, n - k + 1)
    upper = 1.0 if k == n else solve(1 - alpha / 2, k + 1, n - k)
    return lower, upper


# ── 산출물 ───────────────────────────────────────────────────────────
def out_dir_existing() -> Path | None:
    ds = sorted(d for d in (ROOT / "experiments").glob(f"chal_{SET}_*")
                if (d / "challenge_result.json").exists())
    return ds[-1] if ds else None


def frozen_hashes() -> dict[str, str]:
    return {"stage_a": json.loads(STAGE_A.read_text())["sha256"],
            "stage_b": json.loads(STAGE_B.read_text())["sha256"],
            "execution_order": json.loads(ORDER.read_text())["sha256"]}


# ── selftest — LLM 0회 ───────────────────────────────────────────────
def selftest():
    pool = {t["tid"]: t for t in build_pool()}
    ids = task_ids()
    sb = json.loads(STAGE_B.read_text())
    ic = sb["identification_challenge"]
    print("=" * 78)
    print(f"challenge selftest — {SET} · LLM 호출 0회")
    print("=" * 78)
    v = verify_frozen()
    for name, good, h in v["checks"]:
        print(f"  {'🟢' if good else '🔴'} {name:<40} {h}")
    ok = v["ok"]

    print(f"\n동결본 규정 (그대로 인용)")
    print(f"  추론 단위   {ic[SET].get('inference_unit', '—')}")
    print(f"  limitation  {ic['limitation'][:70]}…")
    print(f"  R0 제외     {ic['r0_exclusion'][:70]}…")

    print(f"\n통계 가정 검증 (24과제 전량)")
    a = b = c = 0
    for t in ids:
        e = pool[t]
        s = to_spec(e)
        gold = set(e["names"])
        if gold <= {s.real_names[l] for l in s.candidates}:
            a += 1
        if len(gold) == 2 and len(e["names"]) == 2:
            b += 1
        if len(set(s.real_names.values())) == len(s.real_names):
            c += 1
    n = len(ids)
    for label, got in (("gold 2구조가 후보에 포함", a), ("gold pair 유일", b),
                       ("라벨↔실구조 전단사", c)):
        good = got == n
        ok &= good
        print(f"  {'🟢' if good else '🔴'} {label:<28} {got}/{n}")
    # 자율식별형인가
    modes = Counter(pool[t]["identification"] for t in ids)
    good = set(modes) == {"autonomous"}
    ok &= good
    print(f"  {'🟢' if good else '🔴'} {'전량 autonomous':<28} {dict(modes)}")
    nt = sum(1 for t in ids if pool[t]["identification_nontrivial"])
    print(f"  {'🟢' if nt == n else '🟡'} {'identification_nontrivial':<28} {nt}/{n}")

    ps = chance_probs(ids, pool)
    print(f"\n무작위 귀무가설")
    print(f"  과제별 1/C(n,2)  범위 {min(ps):.4f} ~ {max(ps):.4f}")
    print(f"  기대 정답 수      {sum(ps):.3f}/{n}  (평균 {sum(ps)/n:.1%})")
    d = poisson_binomial_pmf(ps)
    print(f"  분포 합 = {sum(d):.10f} (1.0 이어야 한다)")
    print(f"  P(K≥k) 예시:  k=5 → {pb_upper_tail(5,ps):.4g} · "
          f"k=8 → {pb_upper_tail(8,ps):.4g} · k=12 → {pb_upper_tail(12,ps):.4g}")
    lo, hi = clopper_pearson(20, n)
    print(f"  Clopper–Pearson 예시  20/24 → [{lo:.3f}, {hi:.3f}]")

    print(f"\n중복 확인")
    main = set(json.loads(STAGE_B.read_text())["primary_experiment"]
               ["main_benchmark"]["task_ids"])
    ov = [t for t in ids if t in main]
    print(f"  main N=92 와 중복 {len(ov)}과제 — challenge 안에서는 포함하되")
    print(f"  🔒 **main 과 합쳐 표본 수를 늘려 해석하지 않는다**")

    print(f"\n예상 호출  {n} 과제 × 4.95 ≈ {n*4.95:.0f}회 (5시간 창 566 기준 "
          f"{n*4.95/566*100:.0f}%)")
    print(f"\n  {'🟢 selftest 통과' if ok else '🔴 selftest 실패 — 실행하지 않는다'}")
    return ok


# ── 실행 ─────────────────────────────────────────────────────────────
def execute(ids: list[str], smoke: int | None, model: str):
    v = verify_frozen()
    mode = f"smoke {smoke}과제" if smoke else f"{SET} 본실행 {len(ids)}과제"
    print("=" * 78)
    print(f"identification challenge — {SET} · condition {CONDITION} · {mode}")
    print("=" * 78)
    print("사전등록 docs/DECISION_LOG.md 2026-08-14 (4) · 동결 과제집합은 stage B")
    for name, good, h in v["checks"]:
        print(f"  {'🟢' if good else '🔴'} {name:<40} {h}")
    if not v["ok"]:
        raise SystemExit("\n🔴 동결이 어긋났다. 실행하지 않는다.")

    if smoke is None and out_dir_existing() is not None:
        raise SystemExit(
            f"🔴 {SET} 결과가 이미 있다 ({out_dir_existing().name}). 덮어쓰지 않는다.")

    pool = {t["tid"]: t for t in build_pool()}
    part = ids[:smoke] if smoke else ids
    tau = load_tau()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = "smoke" if smoke else SET
    out_dir = ROOT / "experiments" / f"chal_{tag}_{stamp}_{model}"
    ledger = Ledger(out_dir / "calls.jsonl")
    be = Backend(model=model, ledger=ledger, condition=CONDITION)

    print(f"\n  과제 {len(part)}개 · 조건 {CONDITION} 단독 "
          f"(τ manipulation 은 identification 이후에만 개입 → V−τ 불필요)")
    print(f"  사전등록 실패 규칙  FAILED > {ABORT_PCT}% (24과제 기준 2과제 이상)")
    if smoke:
        print("\n  🔒 smoke — **성능 결과를 출력하지 않는다.** 실행 경로·task ID·"
              "채점 필드·출력 형식만 확인한다.")

    q0 = read_quota()
    g = q0.get("Gemini Models", {})
    print(f"\n  quota(시작)  5시간 {g.get('Five Hour Limit Remaining')} · "
          f"주간 {g.get('Weekly Limit Remaining')}")

    rows, t0 = [], time.time()
    for i, t in enumerate(part):
        e = pool[t]
        print(f"\n[{i+1}/{len(part)}] {t}  밴드 {e['band']} · 후보 {len(to_spec(e).candidates)}개",
              flush=True)
        res = run_task(be, to_spec(e), tau)
        row = score_run(e, res, tau)
        rows.append(row)
        if smoke:
            # 🔒 성능 비출력 — 실행 사실과 필드 존재만
            print(f"    {'🔴 FAILED' if row['failed'] else '완료'} · 라운드 {row['rounds']}"
                  + (f" · ⚠️ {row['error']}" if row["error"] else ""))
        else:
            print(f"    {'🔴 FAILED' if row['failed'] else '완료'} · 라운드 {row['rounds']}"
                  f" · 식별 {'○' if row['identification_correct'] else '×'}")
        (out_dir / "rows_partial.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2, default=str) + "\n")

    elapsed = time.time() - t0
    q1 = read_quota()
    quota_ledger.record(model=model, n_calls=len(ledger.calls),
                        tokens=ledger.summary()["usage"], before=q0, after=q1,
                        seconds=elapsed, context=f"challenge/{tag}")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "preregistration": "docs/DECISION_LOG.md 2026-08-14 (4)",
        "set": SET, "smoke": bool(smoke), "condition": CONDITION, "model": model,
        "task_ids": part, "frozen": frozen_hashes(),
        "chance_probs": chance_probs(part, pool),
        "elapsed_s": round(elapsed, 1), "rows": rows,
        "ledger_summary": ledger.summary(),
        "quota_before": q0, "quota_after": q1,
        "scope_note": ("RQ1 전체를 증명하는 실험이 아니다. main benchmark 의 식별 "
                       "76/76 을 더 어려운 후보 선택 환경에서 보조 검증한다."),
        "no_pooling_note": ("main N=92 와 중복되는 과제를 main 과 합쳐 표본 수를 "
                            "늘려 해석하지 않는다."),
    }
    name = "smoke_result.json" if smoke else "challenge_result.json"
    (out_dir / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")
    (out_dir / "rows_partial.json").unlink(missing_ok=True)

    # ── 무결성 ────────────────────────────────────────────────────────
    ls = ledger.summary()
    lines = (out_dir / "calls.jsonl").read_text().splitlines()
    bad = sum(1 for l in lines if not _parses(l))
    failed = sum(r["failed"] for r in rows)
    denom = len(ids)                      # 사전등록 단위 = 24
    pct = 100.0 * failed / denom
    print(f"\n{'=' * 78}\n실행 무결성\n{'=' * 78}")
    print(f"  🟢 과제 커버리지    계획 {len(part)} · 실행 {len(rows)} · "
          f"중복 {len(rows)-len({r['tid'] for r in rows})}")
    print(f"  {'🟢' if not bad else '🔴'} 원장 무결      {len(lines)}줄 · "
          f"요약 {ls['n_calls']} · 파싱실패 {bad}")
    print(f"  {'🟢' if pct <= ABORT_PCT else '🔴'} FAILED         {failed}건 "
          f"({SET} {denom}과제 기준 {pct:.1f}% · 무효 기준 {ABORT_PCT}%)")
    for r in rows:
        if r["failed"]:
            print(f"       {r['tid']:<32} {r['error']}")
    # 채점 필드 존재 검사 (smoke 의 목적)
    need = ["identification_correct", "identification_accuracy", "selected_pair",
            "gold_pair", "identification_mode", "band"]
    miss = {k for r in rows for k in need if k not in r}
    print(f"  {'🟢' if not miss else '🔴'} 채점 필드      {'전부 존재' if not miss else miss}")
    print(f"  호출 {ls['n_calls']} · 실패 {ls['failures']} · "
          f"토큰 {ls['usage']['total_tokens']:,} · 경과 {elapsed/60:.1f}분")
    g1 = q1.get("Gemini Models", {})
    print(f"  quota  5시간 {g.get('Five Hour Limit Remaining')} → "
          f"{g1.get('Five Hour Limit Remaining')} · 주간 "
          f"{g.get('Weekly Limit Remaining')} → {g1.get('Weekly Limit Remaining')}")
    print(f"\n→ {out_dir.relative_to(ROOT)}")
    if smoke:
        print("\n  🔒 성능 결과는 출력하지 않았다. 본실행은 `--run` 으로.")
    else:
        print("\n  다음 — `--report` 로 사전등록된 통계를 본다.")


def _parses(line: str) -> bool:
    try:
        json.loads(line)
        return True
    except Exception:  # noqa: BLE001
        return False


# ── 보고 ─────────────────────────────────────────────────────────────
def report():
    d = out_dir_existing()
    if d is None:
        raise SystemExit(f"🔴 {SET} 본실행 결과가 없다. `--run` 을 먼저 돌린다.")
    p = json.loads((d / "challenge_result.json").read_text())
    rows = p["rows"]
    ps = p["chance_probs"]
    ok = [r for r in rows if not r["failed"]]
    n = len(rows)
    failed = n - len(ok)

    print("=" * 78)
    print(f"identification challenge — {SET} (n={n}) · condition V 단독")
    print("=" * 78)
    print("사전등록 docs/DECISION_LOG.md 2026-08-14 (4)")
    print(f"\n  FAILED {failed}/{n} ({100*failed/n:.1f}%) · "
          f"무효 기준 {ABORT_PCT}% "
          f"{'🟢' if 100*failed/n <= ABORT_PCT else '🔴 초과'}")

    # 식별 정확도 — FAILED 는 식별을 수행하지 못한 것이므로 분모에서 뺀다
    k = sum(1 for r in ok if r["identification_correct"])
    m = len(ok)
    lo, hi = clopper_pearson(k, m)
    ps_ok = [q for r, q in zip(rows, ps) if not r["failed"]]
    pval = pb_upper_tail(k, ps_ok)
    exp = sum(ps_ok)

    print(f"\n  identification accuracy  **{k}/{m}** ({k/m:.1%})")
    print(f"  95% CI (Clopper–Pearson) [{lo:.3f}, {hi:.3f}]")
    print(f"  무작위 기대 정답수        {exp:.3f}/{m} (평균 {exp/m:.1%})")
    print(f"  단측 정확 Poisson-binomial  **p = {pval:.4g}**  "
          f"{'*' if pval < ALPHA else ''}  (α = {ALPHA})")

    print(f"\n  📌 사전 고정된 해석 문구")
    if pval < ALPHA:
        print("     «사전 지정된 nontrivial candidate set 에서 식별 성능이")
        print("       무작위 쌍 선택보다 유의하게 높았다.»")
    else:
        print("     «이 challenge 에서는 무작위 선택을 넘는 식별 성능에 대한")
        print("       충분한 증거를 얻지 못했다.»")

    print(f"\n  🔒 이 실험은 RQ1 전체를 증명하지 않는다 — main 의 76/76 을 더 어려운")
    print(f"     후보 선택 환경에서 보조 검증한 것이다.")
    print(f"  🔒 main N=92 와 중복 과제를 합쳐 표본 수를 늘려 해석하지 않는다.")
    print(f"  🔒 Amino20x4 편중·밴드 불균형으로 **밴드별·계열별 일반화 주장을 하지 않는다.**")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--smoke", type=int, metavar="N")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--model", default=None)
    a = ap.parse_args()
    model = a.model or json.loads(STAGE_B.read_text())["primary_experiment"]["primary_model"]
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.smoke:
        execute(task_ids(), a.smoke, model)
    elif a.run:
        execute(task_ids(), None, model)
    elif a.report:
        report()
    else:
        ap.error("--selftest · --smoke N · --run · --report 중 하나")


if __name__ == "__main__":
    main()
