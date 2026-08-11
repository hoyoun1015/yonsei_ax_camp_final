"""quota 소비 통제 측정.

**왜 다시 재는가.** 파일럿 측정이 일관되지 않았다 — Flash 가 한 번은 21호출에 약 9%,
다른 때는 16호출에 3% 를 썼다. 원인 후보가 셋이다.

1. **5시간 창이 회전하며 회복된다.** 실제로 Claude 실행 중 Gemini 가 72% → 73% 로
   오르는 것을 관측했다. 전후 차이는 «소비 − 회복»이지 소비가 아니다.
2. **백분율이 정수**라 16호출 규모에서 해상도가 1% 뿐이다.
3. 루프 실행은 호출마다 프롬프트 길이가 달라 토큰이 들쭉날쭉하다.

**설계.** 세 가지를 통제한다.

- **동일 호출 반복** — 같은 프롬프트·같은 스키마로 N회. 루프 변동성을 제거한다.
- **idle 대조군** — 호출 없이 같은 시간을 대기해 «회복만»을 따로 잰다.
  소비 추정 = (실행 구간 감소분) + (대조군 회복분)
- **cache_read 포함 전 항목 기록** — 모델 간 차이의 원인을 남긴다.

사용:
    python3 src/vccl/agents/quota_probe.py --model gemini-3.1-pro-high --n 20
    python3 src/vccl/agents/quota_probe.py --model ... --n 20 --skip-idle
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents.backend import QUOTA_GROUP, read_quota  # noqa: E402
from vccl.agents import quota_ledger  # noqa: E402

AGY = str(Path.home() / ".local" / "bin" / "agy")

# 파일럿의 choose_level 프롬프트를 고정해 쓴다. 호출마다 동일해야 한다.
PROMPT = """당신은 계산화학 연구팀의 Computational Chemist다. 어느 계산 수준으로 실행할지 정하라.

## 검증할 비교

**S2** 대 **S1** — 상대 전자에너지

## 선택지

- **L1** — GFN2-xTB 단일점. 반응당 약 0.02초.
- **L3** — B3LYP-D3(BJ)/def2-TZVP 단일점. 반응당 25초~53분.

## 이 방법들의 알려진 오차 (방법오차 τ)

- L1: **1.21 kcal/mol**
- L3: **0.41 kcal/mol**

## 할 일

이번 라운드에 실행할 수준 하나를 고르고 이유를 적는다.

## 출력 형식

**아래 형태의 JSON 객체 하나만 출력한다.** 설명문·코드펜스를 붙이지 않는다.
`|` 는 택일을 뜻한다 — 배열이 아니라 값 하나를 고른다.

{
  "level": "L1" | "L3",
  "reasoning": "<문자열>"
}"""

FIELDS = ("input_tokens", "output_tokens", "thinking_tokens",
          "cache_read_tokens", "total_tokens")


def pct(q: dict, group: str, window: str) -> float | None:
    v = q.get(group, {}).get(window)
    if not v:
        return None
    try:
        return float(v.rstrip("%"))
    except ValueError:
        return None


def one_call(model: str, timeout: int = 300) -> dict:
    t0 = time.time()
    try:
        out = subprocess.run(
            [AGY, "-p", PROMPT, "--model", model, "--output-format", "json",
             "--disable-slash-commands"],
            capture_output=True, text=True, timeout=timeout).stdout.strip()
        p = json.loads(out.splitlines()[-1]) if out else {}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "why": type(e).__name__, "dt": time.time() - t0,
                **{f: 0 for f in FIELDS}}
    u = p.get("usage", {}) or {}
    resp = (p.get("response") or "").strip()
    ok = bool(resp) or p.get("structured_output") is not None
    return {"ok": ok, "why": "" if ok else "empty", "dt": time.time() - t0,
            **{f: u.get(f, 0) for f in FIELDS}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--skip-idle", action="store_true",
                    help="idle 대조군을 건너뛴다 (회복 보정 없이 측정)")
    args = ap.parse_args()

    grp = ("Claude and GPT models" if QUOTA_GROUP[args.model] == "claude-gpt"
           else "Gemini Models")
    W5, WW = "Five Hour Limit Remaining", "Weekly Limit Remaining"

    print(f"모델 {args.model} · 동일 호출 {args.n}회 · 그룹 «{grp}»\n")

    # ── 1) 실행 구간 ──────────────────────────────────────────────────
    q0 = read_quota()
    t_run0 = time.time()
    calls = []
    for i in range(args.n):
        r = one_call(args.model)
        calls.append(r)
        print(f"  [{i+1:>2}/{args.n}] {'OK ' if r['ok'] else 'FAIL'} "
              f"{r['dt']:>5.1f}s  in {r['input_tokens']:>6,} "
              f"cache {r['cache_read_tokens']:>6,} total {r['total_tokens']:>6,}",
              flush=True)
    run_s = time.time() - t_run0
    q1 = read_quota()

    # ── 2) idle 대조군 — 같은 시간 대기, 호출 없음 ────────────────────
    recover5 = recoverw = 0.0
    if not args.skip_idle:
        print(f"\n  idle 대조군 — {run_s:.0f}초 대기 (호출 없음)", flush=True)
        time.sleep(run_s)
        q2 = read_quota()
        a, b = pct(q1, grp, W5), pct(q2, grp, W5)
        if a is not None and b is not None:
            recover5 = b - a
        a, b = pct(q1, grp, WW), pct(q2, grp, WW)
        if a is not None and b is not None:
            recoverw = b - a

    ok = sum(c["ok"] for c in calls)
    tot = {f: sum(c[f] for c in calls) for f in FIELDS}
    d5 = (pct(q0, grp, W5) or 0) - (pct(q1, grp, W5) or 0)
    dw = (pct(q0, grp, WW) or 0) - (pct(q1, grp, WW) or 0)

    print(f"\n{'=' * 74}")
    print(f"{args.model} — 동일 호출 {args.n}회 (성공 {ok})")
    print(f"{'=' * 74}")
    print(f"실행 시간 {run_s:.0f}초 · 호출당 {run_s / args.n:.1f}초")
    for f in FIELDS:
        print(f"  {f:<20} 합계 {tot[f]:>9,}  호출당 {tot[f] // args.n:>8,}")
    cr = tot["cache_read_tokens"] / tot["input_tokens"] * 100 if tot["input_tokens"] else 0
    print(f"  캐시 적중률           {cr:.0f}%")

    print(f"\nquota — 그룹 «{grp}»")
    print(f"  5시간   {pct(q0, grp, W5)}% → {pct(q1, grp, W5)}%   "
          f"관측 감소 {d5:.0f}%p" + (f" · idle 회복 {recover5:+.0f}%p" if not args.skip_idle else ""))
    print(f"  주간    {pct(q0, grp, WW)}% → {pct(q1, grp, WW)}%   "
          f"관측 감소 {dw:.0f}%p" + (f" · idle 회복 {recoverw:+.0f}%p" if not args.skip_idle else ""))

    # 회복 보정 — 관측 감소는 «소비 − 회복»이므로 회복분을 되돌려 더한다
    cons5, consw = d5 + max(recover5, 0), dw + max(recoverw, 0)
    print(f"\n  보정 소비   5시간 {cons5:.0f}%p · 주간 {consw:.0f}%p")
    if cons5 > 0:
        print(f"  → 5시간 창 용량 ≈ {int(args.n / cons5 * 100):,}회 "
              f"(호출당 {cons5 / args.n:.3f}%p)")
    if consw > 0:
        print(f"  → 주간 용량     ≈ {int(args.n / consw * 100):,}회 "
              f"(호출당 {consw / args.n:.3f}%p)")
    if cons5 <= 0 and consw <= 0:
        print("  ⚠️ 감소가 관측되지 않았다. N 을 늘려야 백분율 해상도(1%)를 넘는다.")

    quota_ledger.record(model=args.model, n_calls=args.n, tokens=tot,
                        before=q0, after=q1, seconds=run_s,
                        context=f"probe/n{args.n}")

    out = ROOT / "experiments" / f"quota_probe_{args.model}.json"
    out.write_text(json.dumps({
        "model": args.model, "n": args.n, "n_ok": ok, "group": grp,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "run_seconds": round(run_s, 1), "idle_control": not args.skip_idle,
        "tokens_total": tot, "tokens_per_call": {f: tot[f] // args.n for f in FIELDS},
        "cache_hit_rate_pct": round(cr, 1),
        "quota_before": q0, "quota_after_run": q1,
        "observed_drop_pp": {"five_hour": d5, "weekly": dw},
        "idle_recovery_pp": {"five_hour": recover5, "weekly": recoverw},
        "corrected_consumption_pp": {"five_hour": cons5, "weekly": consw},
        "estimated_capacity_calls": {
            "five_hour": int(args.n / cons5 * 100) if cons5 > 0 else None,
            "weekly": int(args.n / consw * 100) if consw > 0 else None},
    }, ensure_ascii=False, indent=2))
    print(f"\n→ {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
