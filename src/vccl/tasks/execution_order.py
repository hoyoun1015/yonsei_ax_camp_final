"""본실행 배치 배정 — 층화 순서. **동결본을 수정하지 않는다.**

DECISION_LOG 2026-08-12 (3) protocol amendment 의 구현이다.

동결본(`frozen_stage_b_v1.json`)의 `task_ids` 와 `task_ordering` 은 **그대로 보존한다.**
이 모듈은 그것을 «정본»으로 읽어 실행 순서만 따로 만들고 별도 파일에 기록한다.

**왜 동결 순서를 그대로 쓰지 않는가.** 동결 정렬키가 `(자율식별, −|ΔE_ref|, tid)` 라
순서가 밴드 블록으로 뭉친다. 30/30/32 로 자르면 Batch 1 이 전부 밴드 A 가 되고
밴드 C·D 가 마지막 배치에 몰린다. 배치는 quota window 로 나뉘므로 **밴드와 실행 시점이
교락된다** — 밴드별 차이와 시점별 차이를 분리할 수 없게 된다.

**결정론적이다. RNG 를 쓰지 않는다.** 재현성은 출력 순서의 SHA-256 으로 보증한다.

사용: python3 src/vccl/tasks/execution_order.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents.r0 import to_task  # noqa: E402
from vccl.scoring.labels import band_of  # noqa: E402
from vccl.tasks.pairs import build_pool, load_tau  # noqa: E402

STAGE_B = ROOT / "data" / "tasks" / "frozen_stage_b_v1.json"
OUT = ROOT / "data" / "tasks" / "execution_order_v1.json"
BATCH_SIZES = (30, 30, 32)
BANDS = ("A", "B", "C", "D")


def largest_remainder(total: int, weights: list[int]) -> list[int]:
    """정원을 비례 배분한다. 최대잉여법 — 결정론적이고 합이 정확히 맞는다."""
    w = sum(weights)
    exact = [total * x / w for x in weights]
    base = [int(x) for x in exact]
    rest = total - sum(base)
    # 잉여가 큰 순, 동률이면 인덱스가 작은 쪽 — 완전히 정해진다
    order = sorted(range(len(weights)), key=lambda i: (-(exact[i] - base[i]), i))
    for i in order[:rest]:
        base[i] += 1
    return base


def build() -> dict:
    tau = load_tau()
    pool = {t["tid"]: t for t in build_pool()}
    sb = json.loads(STAGE_B.read_text())
    frozen_ids = sb["primary_experiment"]["main_benchmark"]["task_ids"]

    # 동결본을 정본으로 삼는다. 밴드 내 상대 순서를 보존한다
    queues: dict[str, list[str]] = {b: [] for b in BANDS}
    for tid in frozen_ids:
        queues[band_of(to_task(pool[tid]), tau).value].append(tid)

    # ① 밴드별 배치 정원 — 배치 크기에 비례
    quota = {b: largest_remainder(len(queues[b]), list(BATCH_SIZES)) for b in BANDS}

    # ② 배치 안에서는 A→B→C→D 라운드로빈 — 배치 «안»에서도 밴드를 시간에 퍼뜨린다
    batches: list[list[str]] = []
    cursor = {b: 0 for b in BANDS}
    for bi in range(len(BATCH_SIZES)):
        take = {b: queues[b][cursor[b]:cursor[b] + quota[b][bi]] for b in BANDS}
        for b in BANDS:
            cursor[b] += quota[b][bi]
        seq, i = [], 0
        while any(i < len(take[b]) for b in BANDS):
            for b in BANDS:
                if i < len(take[b]):
                    seq.append(take[b][i])
            i += 1
        batches.append(seq)

    flat = [t for b in batches for t in b]
    assert sorted(flat) == sorted(frozen_ids), "과제 집합이 동결본과 다르다"
    assert [len(b) for b in batches] == list(BATCH_SIZES), "배치 크기가 맞지 않는다"

    payload = {
        "purpose": "본실행 V·V−τ 배치 배정. 동결본을 대체하지 않는다",
        "amendment": "DECISION_LOG 2026-08-12 (3)",
        "derived_from": {
            "file": "frozen_stage_b_v1.json",
            "sha256": sb["sha256"],
            "frozen_task_ordering_preserved": True,
            "note": "동결본의 task_ids·task_ordering 은 수정하지 않았다. "
                    "여기서 만드는 것은 실행 순서뿐이다",
        },
        "rule": [
            "1) 동결 task_ids 순서를 정본으로 밴드별 큐 구성 (밴드 내 상대 순서 보존)",
            "2) 밴드별 배치 정원 = 배치 크기 비례 + 최대잉여법",
            "3) 배치 안에서는 A→B→C→D 라운드로빈",
            "4) 같은 과제의 V·V−τ 는 연속 실행. 짝수 인덱스는 V 먼저, 홀수는 V−τ 먼저",
        ],
        "seed": None,
        "seed_note": "무작위 요소가 없다. RNG 를 쓰지 않으므로 seed 가 존재하지 않는다",
        "batch_sizes": list(BATCH_SIZES),
        "band_quota_per_batch": {b: quota[b] for b in BANDS},
        "batches": [
            {"batch": i + 1, "n": len(seq),
             "band_counts": dict(Counter(
                 band_of(to_task(pool[t]), tau).value for t in seq)),
             "task_ids": seq}
            for i, seq in enumerate(batches)
        ],
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    payload["sha256"] = hashlib.sha256(body.encode()).hexdigest()
    return payload


def main():
    payload = build()
    if OUT.exists():
        prev = json.loads(OUT.read_text())
        if prev.get("sha256") == payload["sha256"]:
            print(f"이미 생성돼 있고 내용이 동일하다 (SHA-256 {payload['sha256'][:16]}…).")
            return
        raise SystemExit(
            f"중단 — {OUT.name} 이 이미 있고 내용이 다르다.\n"
            f"  기존 {prev.get('sha256','?')[:16]}…\n  신규 {payload['sha256'][:16]}…\n\n"
            "실행 순서는 amendment 이후 다시 바꾸지 않기로 했다(사용자 지시). "
            "정당한 사유가 있으면 DECISION_LOG 에 남기고 이 파일을 지운 뒤 재생성할 것.")

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                              sort_keys=True) + "\n")
    print("실행 순서 생성 완료 — 동결본은 수정하지 않았다\n")
    for b in payload["batches"]:
        bc = b["band_counts"]
        print(f"  Batch {b['batch']}  n={b['n']:>2}  " +
              " ".join(f"{k}={bc.get(k, 0)}" for k in BANDS))
    print(f"\n→ {OUT.relative_to(ROOT)}")
    print(f"   SHA-256 {payload['sha256']}")


if __name__ == "__main__":
    main()
