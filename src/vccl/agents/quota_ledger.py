"""quota 누적 원장 — 주간 용량을 별도 측정 없이 추정한다.

**왜 필요한가.** `gemini-3.6-flash-high` 의 주간 용량이 미확인이다. N=20 통제 측정에서
주간 감소가 1%p 해상도 아래였다. 확인하려면 N=100 규모 측정이 필요한데 그것만으로
5시간 창의 15% 를 쓴다.

**대신 누적한다.** 앞으로의 모든 실행(파일럿·본실행·디버깅)에서 `/usage` 전후값과
호출 수·토큰을 이 원장에 append 한다. 표본이 쌓이면 주간 소비를 회귀로 추정할 수 있고,
추가 quota 를 쓰지 않는다.

**회복을 다루는 방식.** 주간 창도 회전하지만 5시간 창보다 훨씬 느리다. 구간마다
경과 시간을 기록해 두고, 추정 시 «호출당 소비» 회귀에서 시간 항을 함께 본다.
관측이 적을 때는 회복을 무시한 하한 추정만 보고한다 — 과대추정보다 안전하다.

사용:
    from vccl.agents.quota_ledger import record, estimate
    record(model="...", n_calls=14, tokens={...}, before=q0, after=q1, seconds=210,
           context="pilot")

    python3 src/vccl/agents/quota_ledger.py        # 누적 추정 보고
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / "experiments" / "quota_ledger.jsonl"
W5, WW = "Five Hour Limit Remaining", "Weekly Limit Remaining"
GROUP_OF = {"gemini": "Gemini Models", "claude-gpt": "Claude and GPT models"}


def _pct(q: dict, group: str, window: str) -> float | None:
    v = (q or {}).get(group, {}).get(window)
    if not v:
        return None
    try:
        return float(str(v).rstrip("%"))
    except ValueError:
        return None


def record(*, model: str, n_calls: int, tokens: dict, before: dict, after: dict,
           seconds: float, context: str, quota_group: str | None = None) -> None:
    """한 실행 구간을 원장에 남긴다. 실패해도 실험을 막지 않는다."""
    from vccl.agents.backend import QUOTA_GROUP
    qg = quota_group or QUOTA_GROUP.get(model, "gemini")
    grp = GROUP_OF.get(qg, "Gemini Models")
    rec = {
        "at": datetime.now(timezone.utc).isoformat(),
        "context": context, "model": model, "quota_group": qg, "group_label": grp,
        "n_calls": n_calls, "seconds": round(seconds, 1),
        "tokens": {k: int(v) for k, v in (tokens or {}).items()},
        "before": {"five_hour": _pct(before, grp, W5),
                   "weekly": _pct(before, grp, WW)},
        "after": {"five_hour": _pct(after, grp, W5),
                  "weekly": _pct(after, grp, WW)},
    }
    for w in ("five_hour", "weekly"):
        b, a = rec["before"][w], rec["after"][w]
        rec.setdefault("drop_pp", {})[w] = (
            round(b - a, 2) if b is not None and a is not None else None)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]


def estimate(model: str | None = None) -> dict:
    """누적 관측으로 창 용량을 추정한다.

    **회복을 무시한 하한 추정이다.** 관측 감소는 «소비 − 회복»이므로 실제 소비는
    이보다 크거나 같다. 즉 여기서 나오는 용량은 **과대추정**일 수 있다 —
    그 방향을 문서에 명시하고, 표본이 쌓이면 다시 본다.
    """
    rows = [r for r in load() if model is None or r["model"] == model]
    out: dict[str, dict] = {}
    for w in ("five_hour", "weekly"):
        used = [r for r in rows
                if r.get("drop_pp", {}).get(w) is not None
                and r["drop_pp"][w] > 0 and r["n_calls"] > 0]
        n_calls = sum(r["n_calls"] for r in used)
        drop = sum(r["drop_pp"][w] for r in used)
        out[w] = {
            "n_segments": len(used), "n_calls": n_calls,
            "total_drop_pp": round(drop, 2),
            "pp_per_call": round(drop / n_calls, 4) if n_calls else None,
            "capacity_calls": int(n_calls / drop * 100) if drop > 0 else None,
            "note": "회복 미보정 — 실제 용량은 이 값 이하일 수 있다",
        }
    # 감소가 0%p 로 관측된 구간에서 **용량 하한**을 얻는다.
    # 백분율 해상도가 1%p 이므로 "0%p 관측" 은 실제 감소가 1%p 미만임을 뜻한다.
    # 따라서 호출당 소비 < 1/N %p 이고 용량 > 100·N 회다.
    for w in ("five_hour", "weekly"):
        zero = [r for r in rows if r.get("drop_pp", {}).get(w) == 0]
        n0 = sum(r["n_calls"] for r in zero)
        out[w]["segments_with_zero_drop"] = len(zero)
        out[w]["calls_in_zero_drop_segments"] = n0
        out[w]["capacity_lower_bound_calls"] = int(n0 * 100) if n0 else None
        if n0:
            out[w]["lower_bound_note"] = (
                f"0%p 로 관측된 구간의 누적 {n0}호출에서 감소가 1%p 미만이었으므로 "
                f"호출당 소비 < {1 / n0:.4f}%p, 용량 > {n0 * 100:,}회")
    return out


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else None
    rows = load()
    if not rows:
        print(f"원장이 비어 있다: {LEDGER.relative_to(ROOT)}")
        print("파일럿·본실행이 돌면 자동으로 쌓인다.")
        return

    print(f"quota 누적 원장 — 구간 {len(rows)}개\n")
    print(f"{'시각':<18}{'맥락':<16}{'모델':<24}{'호출':>5}{'5h감소':>8}{'주간감소':>9}")
    print("-" * 82)
    for r in rows:
        if model and r["model"] != model:
            continue
        d = r.get("drop_pp", {})
        print(f"{r['at'][:16]:<18}{r['context']:<16}{r['model']:<24}"
              f"{r['n_calls']:>5}{str(d.get('five_hour')):>8}{str(d.get('weekly')):>9}")

    for m in sorted({r["model"] for r in rows} if not model else {model}):
        e = estimate(m)
        print(f"\n{m}")
        for w, label in (("five_hour", "5시간"), ("weekly", "주간")):
            x = e[w]
            if x["capacity_calls"]:
                print(f"  {label:<5} 구간 {x['n_segments']} · 호출 {x['n_calls']} · "
                      f"감소 {x['total_drop_pp']}%p → 용량 ≈ {x['capacity_calls']:,}회 "
                      f"(호출당 {x['pp_per_call']}%p)")
            else:
                lb = x.get("capacity_lower_bound_calls")
                print(f"  {label:<5} 감소 미관측 — 0%p 구간 "
                      f"{x.get('segments_with_zero_drop', 0)}개, 누적 "
                      f"{x.get('calls_in_zero_drop_segments', 0)}호출")
                if lb:
                    print(f"        → **용량 하한 > {lb:,}회** "
                          f"(해상도 1%p 이므로 호출당 소비 < "
                          f"{100 / lb:.4f}%p)")
        print("  ⚠️ 회복 미보정 하한 추정 — 실제 용량은 이 값 이하일 수 있다")


if __name__ == "__main__":
    main()
