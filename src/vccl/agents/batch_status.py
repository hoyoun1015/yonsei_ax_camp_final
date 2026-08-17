"""실행 중인 배치의 진행 상황. **로컬 파일만 읽는다 · API 호출 0회.**

`main_run.py` 는 과제마다 `rows_partial.json` 을 갱신하고 끝나면 지운다. 그래서
이 스크립트로 **돌고 있는 배치를 방해하지 않고** 상태를 볼 수 있다.

quota 는 조회하지 않는다 — `/usage` 조회 자체가 호출 1회를 소비하므로, 실행 중에
반복해서 찍으면 예산을 갉아먹는다. quota 는 실행 직전·직후에만 본다(main_run 이 한다).

**조기 경보가 목적이다.** 사전등록 규칙은 «한 condition 에서 FAILED > 5% 면 그 실행을
무효로 본다» 이므로, 이미 그 선을 넘었다면 남은 호출을 태울 이유가 없다.

사용:
    python3 src/vccl/agents/batch_status.py
    python3 src/vccl/agents/batch_status.py --watch 60      # 60초마다 다시 출력
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ORDER = ROOT / "data" / "tasks" / "execution_order_v1.json"
CONDITIONS = ("V", "V-tau")
ABORT_PCT = 5.0


def newest_batch_dir() -> Path | None:
    ds = sorted((ROOT / "experiments").glob("main_b*"),
                key=lambda p: p.stat().st_mtime)
    return ds[-1] if ds else None


def show(d: Path) -> bool:
    """진행 중이면 True 를 돌려준다."""
    partial, final = d / "rows_partial.json", d / "batch_result.json"
    running = partial.exists()
    src = partial if running else final
    if not src.exists():
        print(f"  {d.name} — 아직 결과 파일이 없다 (기동 중이거나 첫 과제 진행 중)")
        return True

    payload = json.loads(src.read_text())
    rows = payload if running else payload["rows"]
    batch_no = None if running else payload.get("batch")

    # 계획 대비 진행률
    planned = None
    if batch_no is None:
        # 실행 중이면 배치 번호를 디렉터리명에서 뽑는다 (main_b1_…)
        try:
            batch_no = int(d.name.split("_")[0].removeprefix("main_b"))
        except ValueError:
            batch_no = None
    if batch_no and ORDER.exists():
        o = json.loads(ORDER.read_text())
        if 1 <= batch_no <= len(o["batches"]):
            planned = o["batches"][batch_no - 1]

    print(f"  {d.name}")
    print(f"  상태  {'🟡 진행 중' if running else '🟢 완료'}"
          + (f" · Batch {batch_no}" if batch_no else ""))

    done = len(rows.get("V", [])) + len(rows.get("V-tau", []))
    total = 2 * planned["n"] if planned else None
    if total:
        print(f"  진행  {done}/{total} 실행 "
              f"({100 * done / total:.0f}%) · 과제 "
              f"{max(len(rows.get(c, [])) for c in CONDITIONS)}/{planned['n']}")

    abort = False
    for c in CONDITIONS:
        rs = rows.get(c, [])
        if not rs:
            continue
        f = sum(r["failed"] for r in rs)
        pct = 100.0 * f / len(rs)
        # 사전등록 기준은 «배치 전체» 에 대한 것이다. 진행 중에는 이미 확정된 실패
        # 개수만으로 판정할 수 있다 — 계획 n 을 분모로 하면 하한이 된다
        floor_pct = 100.0 * f / planned["n"] if planned else pct
        bad = floor_pct > ABORT_PCT
        abort |= bad
        print(f"  {c:<7} n={len(rs):<3} FAILED {f} "
              f"(현재 {pct:.1f}% · 배치 전체 기준 최소 {floor_pct:.1f}%)"
              + ("  🔴 무효 기준 초과 확정" if bad else ""))
        for r in rs:
            if r["failed"]:
                print(f"        {r['tid']:<32} {r['error']}")

    if abort:
        print(f"\n  🔴 **이미 사전등록 무효 기준({ABORT_PCT}%)을 넘겼다.**")
        print("     남은 호출을 태울 이유가 없다 — 중단하고 원인을 고친 뒤 재실행한다.")
        print("     (부분 결과를 확증 결과로 쓰지 않는다는 사전등록 항목)")

    # 밴드별 · 조건별 요약
    for c in CONDITIONS:
        rs = [r for r in rows.get(c, []) if not r["failed"]]
        if not rs:
            continue
        bands = Counter(r["band"] for r in rs)
        l3 = sum(bool(r["used_l3"]) for r in rs)
        jr = sum(1 for r in rs if r.get("justified_resolution"))
        cC = [r for r in rs if r["band"] == "C"]
        print(f"  {c:<7} 밴드 " + " ".join(f"{b}={bands.get(b, 0)}" for b in "ABCD")
              + f" · L3 {l3} · justified {jr}/{len(rs)}"
              + (f" · 밴드C L3상승 {sum(bool(r['used_l3']) for r in cC)}/{len(cC)}"
                 if cC else ""))
        if any(r["identification_correct"] is False for r in rs):
            mm = [r["tid"] for r in rs if r["identification_correct"] is False]
            print(f"          식별 오류 {len(mm)}건 {mm[:3]} "
                  "(크래시 아님 — 오답으로 채점된다)")
    return running


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", type=int, default=0,
                    help="N초마다 다시 출력. 로컬 파일만 읽으므로 API 를 쓰지 않는다")
    args = ap.parse_args()

    while True:
        d = newest_batch_dir()
        print("=" * 78)
        print("본실행 진행 상황 — 로컬 파일만 읽는다 (API 호출 0회)")
        print("=" * 78)
        if d is None:
            print("  experiments/main_b* 디렉터리가 없다 — 아직 시작하지 않았다")
            running = False
        else:
            running = show(d)
        if not args.watch or not running:
            break
        print(f"\n  {args.watch}초 후 다시 확인한다 (Ctrl-C 로 중단)")
        time.sleep(args.watch)


if __name__ == "__main__":
    main()
