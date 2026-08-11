"""과제 후보 풀 생성과 밴드 층화.

기획안 §4 의 구현이다. **결정론적이며 LLM 을 부르지 않는다.**

여기서 만드는 것은 **후보 풀**이다. 최종 과제 «수»는 Stage B 에서 동결한다
(API 한도·예산에 의존하므로, `docs/FREEZE_v1.md` 참조).

각 후보에 붙는 것 —

| 항목 | 출처 |
|---|---|
| 밴드 A/B/C/D | 동결된 τ 와 참조값 (`frozen_rules_v1.json`) |
| 화학종 | 반응 그래프의 연결성분 |
| 자율 식별 / 쌍 지정 | 정답이 유일해지는 최소 정밀도 |
| 가설 문장 (중립·오도) | 기하 서술자 |
| `claimed_more_stable` | 결정론적 난수로 SUPPORTED/REFUTED 를 섞는다 |

**추론 단위는 화학종이다** — 한 화학종에서 여러 과제를 뽑아도 n 은 늘지 않는다.
그래서 층화도 화학종 기준으로 하고, 같은 화학종에서 과제를 여러 개 뽑지 않는다.

사용:
    python3 src/vccl/tasks/pairs.py                     # 풀 생성 + 층화 요약
    python3 src/vccl/tasks/pairs.py --out data/tasks/pool_v1.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.scoring.labels import (  # noqa: E402
    Band, IdentificationMode, Task, Tau, band_of, correct_escalation, oracle_action,
)
from vccl.tasks import prompts  # noqa: E402
from vccl.tasks.gmtkn import (  # noqa: E402
    CONFORMER_SUBSETS, ISOMER_SUBSETS, describe, load_reactions, reaction_type,
    species_map,
)

GMTKN = ROOT / "data" / "reference" / "gmtkn55"
FROZEN = ROOT / "data" / "tasks" / "frozen_rules_v1.json"
ALL_SUBSETS = CONFORMER_SUBSETS + ISOMER_SUBSETS
PRECISION_LEVELS = ("L1", "L2")      # L3 는 쓰지 않는다 — 구조 ID 를 풀어쓴 것이다


def load_tau() -> Tau:
    d = json.loads(FROZEN.read_text())
    return Tau({(rt, lv): v for rt, lvs in d["tau"]["values"].items()
                for lv, v in lvs.items() if lv in ("L1", "L3")},
               floor=d["tau"]["floor"])


def min_precision(names, desc, smap) -> str | None:
    """두 구성원이 각자의 화학종 안에서 유일해지는 가장 거친 정밀도.

    없으면 None — 그 반응은 쌍 지정형으로 남긴다.
    """
    for lv in PRECISION_LEVELS:
        if all(sum(1 for o in desc
                   if smap.get(o) == smap.get(nm) and desc[o].at(lv) == desc[nm].at(lv)
                   ) == 1 for nm in names):
            return lv
    return None


def build_pool(subsets: list[str] | None = None) -> list[dict]:
    """후보 풀. `subsets` 를 주면 그것만 — 테스트에서 빠르게 돌리기 위해."""
    tau = load_tau()
    pool = []
    for sub in (subsets or ALL_SUBSETS):
        rxns = load_reactions(GMTKN, sub)
        smap = species_map(rxns)
        rtype = reaction_type(sub)
        desc = {n: describe(GMTKN / sub / n / "struc.xyz")
                for n in {x for r in rxns for x in r.names}}

        for r in rxns:
            # 2성분 ±1 반응만 안정성 비교 과제로 쓴다 (labels.Task 가 검증한다)
            if len(r.names) != 2 or sorted(r.coeffs) != [-1, 1] or r.ref == 0:
                continue

            lv = min_precision(r.names, desc, smap)
            mode = (IdentificationMode.AUTONOMOUS if lv
                    else IdentificationMode.PAIRED)
            # 후보 수 — 식별 난이도를 좌우한다. 화학종이 쌍 하나뿐이면(구조 이성질체)
            # 후보가 2개여서 어떤 서술로도 구분되므로 «자율 식별»이 형식적으로만
            # 성립한다. 이 수치를 기록해 층화와 보고에서 구분한다.
            n_cand = sum(1 for o in desc if smap.get(o) == smap[r.names[0]])

            neg = next(x for x, c in zip(r.names, r.coeffs) if c < 0)
            pos = next(x for x, c in zip(r.names, r.coeffs) if c > 0)
            true_stable = neg if r.ref > 0 else pos
            other = pos if true_stable == neg else neg
            # SUPPORTED/REFUTED 를 섞는다. rid 로 시드를 고정해 재현 가능하게.
            rng = random.Random(f"claim::{r.rid}")
            claimed = true_stable if rng.random() < 0.5 else other
            counter = other if claimed == true_stable else true_stable

            task = Task(tid=r.rid, subset=sub, rtype=rtype, names=r.names,
                        coeffs=r.coeffs, ref=r.ref, claimed_more_stable=claimed,
                        identification=mode, precision_level=lv)
            band = band_of(task, tau)

            hyp = (prompts.both(desc[claimed], desc[counter], lv) if lv else
                   {"neutral": None, "misleading": None, "mechanism_key": None})

            pool.append({
                "tid": r.rid, "subset": sub, "rtype": rtype,
                "names": list(r.names), "coeffs": list(r.coeffs), "ref": r.ref,
                "abs_ref": round(task.abs_ref, 6),
                "species": smap[r.names[0]],
                "claimed_more_stable": claimed,
                "band": band.value,
                "escalation_answer": correct_escalation(task, tau).value,
                "oracle": {lvl: oracle_action(task, lvl, tau).value
                           for lvl in ("L1", "L3")},
                "identification": mode.value,
                "precision_level": lv,
                "n_candidates": n_cand,
                "identification_nontrivial": bool(lv) and n_cand >= 4,
                "hypothesis": hyp,
                "descriptors": {n: {"torsions": desc[n].torsions,
                                    "hbonds": desc[n].hbonds,
                                    "n_heavy": desc[n].n_heavy} for n in r.names},
            })
    return pool


class StratifyShortfall(RuntimeError):
    """목표 수를 채울 수 없다. 조용히 축소하지 않고 실패한다."""


def stratify(pool: list[dict], per_band: dict[str, int],
             autonomous_first: bool = True, strict: bool = True) -> list[dict]:
    """밴드별로 목표 수만큼 뽑는다. **화학종 중복을 허용하지 않는다.**

    `per_band` 는 Stage B 에서 동결할 값이다. 여기서는 인자로만 받는다.

    **화학종 유일성은 밴드 간에도 적용된다** — 한 분자가 여러 밴드에 반응을 가질 수
    있으므로, 먼저 처리한 밴드가 뒤 밴드에 필요한 화학종을 가져갈 수 있다. 그래서
    **여유가 적은 밴드를 먼저 처리한다**(available/want 오름차순). 밴드 C 는 G3 가
    걸린 구간이고 밴드 D 는 공급이 가장 적으므로 이 순서가 중요하다.

    **선택은 결정론적이다.** 정렬 키가 (자율 식별 여부, −|ΔE_ref|, tid) 로 완전히
    정해지고 난수를 쓰지 않는다. 같은 풀·같은 목표면 항상 같은 결과가 나온다.

    `strict=True` 면 목표를 못 채울 때 `StratifyShortfall` 을 던진다. 조용히 적게
    반환하면 "N=92 로 돌렸다"고 적어놓고 실제로는 87개인 상태가 되고, 그것이
    로그에 드러나지 않는다.
    """
    by_band: dict[str, list[dict]] = defaultdict(list)
    for t in pool:
        by_band[t["band"]].append(t)

    def rank(t):
        return (0 if (autonomous_first and t["identification"] == "autonomous") else 1,
                -t["abs_ref"], t["tid"])

    # 여유가 적은 밴드부터. 여유는 «그 밴드의 고유 화학종 수 / 목표».
    def slack(band: str) -> float:
        want = per_band[band]
        avail = len({(t["subset"], t["species"]) for t in by_band.get(band, [])})
        return (avail / want) if want else float("inf")

    order = sorted(per_band, key=lambda b: (slack(b), b))

    picked: list[dict] = []
    used_species: set[tuple[str, str]] = set()
    per_band_got: dict[str, int] = {b: 0 for b in per_band}

    for band in order:
        want = per_band[band]
        for t in sorted(by_band.get(band, []), key=rank):
            if per_band_got[band] >= want:
                break
            key = (t["subset"], t["species"])
            if key in used_species:
                continue
            used_species.add(key)
            picked.append(t)
            per_band_got[band] += 1

    short = {b: (per_band[b], per_band_got[b])
             for b in per_band if per_band_got[b] < per_band[b]}
    if short and strict:
        detail = " · ".join(f"{b} {got}/{want}" for b, (want, got) in short.items())
        raise StratifyShortfall(
            f"목표 수를 채우지 못했다: {detail}\n"
            f"처리 순서 {order} (여유가 적은 밴드 우선). "
            "화학종 유일성이 밴드 간에도 적용되므로, 앞 밴드가 뒤 밴드에 필요한 "
            "화학종을 가져갔을 수 있다. 목표를 낮추거나 서브셋을 추가할 것.")
    return sorted(picked, key=lambda t: (t["band"], t["tid"]))


def summarize(pool: list[dict]) -> None:
    print(f"후보 풀 {len(pool)}개 반응\n")
    print(f"{'밴드':<6}{'반응':>5}{'화학종':>7}{'자율식별':>9}{'실질식별':>9}{'쌍지정':>7}  주 공급원")
    print("-" * 84)
    for band in ("A", "B", "C", "D"):
        rows = [t for t in pool if t["band"] == band]
        if not rows:
            continue
        sp = {(t["subset"], t["species"]) for t in rows}
        auto = sum(1 for t in rows if t["identification"] == "autonomous")
        nontriv = sum(1 for t in rows if t["identification_nontrivial"])
        src = defaultdict(int)
        for t in rows:
            src[t["subset"]] += 1
        top = " · ".join(f"{k}({v})" for k, v in
                         sorted(src.items(), key=lambda x: -x[1])[:3])
        print(f"{band:<6}{len(rows):>5}{len(sp):>7}{auto:>9}{nontriv:>9}"
              f"{len(rows) - auto:>7}  {top}")

    print(f"\n{'유형':<14}{'반응':>5}{'자율식별':>9}{'실질식별':>9}{'중앙 후보수':>11}")
    print("-" * 54)
    import statistics as st
    for rt in ("conformer", "isomer"):
        rows = [t for t in pool if t["rtype"] == rt]
        auto = sum(1 for t in rows if t["identification"] == "autonomous")
        nontriv = sum(1 for t in rows if t["identification_nontrivial"])
        med = st.median([t["n_candidates"] for t in rows])
        print(f"{rt:<14}{len(rows):>5}{auto:>9}{nontriv:>9}{med:>11.0f}")
    print("\n«실질 식별» = 자율 식별형이면서 후보가 4개 이상. 후보가 2개면 어떤 서술로도")
    print("구분되므로 식별 과제로서 의미가 약하다 — 구조 이성질체가 대부분 그렇다.")

    ex = next((t for t in pool
               if t["identification"] == "autonomous" and t["band"] == "C"), None)
    if ex:
        print(f"\n예시 — 밴드 C · 자율 식별형 · {ex['tid']}")
        print(f"  중립: {ex['hypothesis']['neutral']}")
        print(f"  오도: {ex['hypothesis']['misleading']}")
        print(f"  정답: L1={ex['oracle']['L1']} / L3={ex['oracle']['L3']} · "
              f"에스컬레이션 {ex['escalation_answer']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/tasks/pool_v1.json")
    args = ap.parse_args()

    pool = build_pool()
    summarize(pool)

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"note": "후보 풀이다. 최종 과제 수는 Stage B 에서 동결한다.",
         "n": len(pool), "pool": pool}, ensure_ascii=False, indent=2) + "\n")
    print(f"\n→ {out.relative_to(ROOT)}")
    print("\n최종 과제 수와 밴드별 목표는 Stage B 에서 동결한다 — "
          "stratify(pool, per_band) 에 넘길 값이다.")


if __name__ == "__main__":
    main()
