"""후보 풀 진단 — «실질 식별»(nontrivial autonomous) 재고 조사.

**동기.** N=92 층화에서 자율 식별형은 76/92 였으나 후보가 4개 이상인 «실질 식별»은
22개뿐이었다. 후보가 2개면 어떤 서술로도 구분되므로 식별 과제로서 의미가 약하다 —
Target Identification Rate 가 대부분 "둘 중 하나 고르기"를 재게 된다.

Stage B 동결 전에 재고를 정확히 파악한다. 이 스크립트는 **아무것도 바꾸지 않는다.**

출력 —
  ① 224개 전체의 실질 식별 수
  ② 밴드별 분포
  ③ 화학종 중복 없이 실제 선택 가능한 최대 수 (밴드 간 경합 포함)
  ④ 반응 유형·서브셋별 분포
  ⑤ 밴드 분포를 유지하면서 실질 식별을 우선하면 몇 개까지 확보되는가

사용: python3 src/vccl/tasks/inventory.py
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.tasks.pairs import build_pool, stratify  # noqa: E402

TARGET_92 = {"A": 30, "B": 22, "C": 25, "D": 15}
BANDS = ("A", "B", "C", "D")


def species_key(t):
    return (t["subset"], t["species"])


def max_matching(by_band_species: dict[str, set], caps: dict[str, int] | None = None):
    """밴드↔화학종 최대 매칭. 한 화학종은 한 밴드에만 배정된다.

    밴드별 상한을 두면 «그 분포로 채울 수 있는 최대»가 나온다. 상한이 없으면
    전체 최대다. 헝가리안까지 갈 필요 없이 증가 경로(augmenting path)로 충분하다.
    """
    bands = list(by_band_species)
    cap = {b: (caps.get(b, 0) if caps else 10 ** 9) for b in bands}
    assigned: dict[str, list] = {b: [] for b in bands}
    owner: dict[tuple, str] = {}

    def try_assign(band, seen):
        if len(assigned[band]) >= cap[band]:
            return False
        for sp in sorted(by_band_species[band]):
            if sp in seen:
                continue
            seen.add(sp)
            if sp not in owner:
                owner[sp] = band
                assigned[band].append(sp)
                return True
            # 이미 쓰인 화학종 — 그 소유 밴드가 다른 화학종으로 옮겨갈 수 있는가
            cur = owner[sp]
            if try_assign(cur, seen):
                assigned[cur].remove(sp)
                owner[sp] = band
                assigned[band].append(sp)
                return True
        return False

    for band in bands:
        while len(assigned[band]) < cap[band] and try_assign(band, set()):
            pass
    return {b: len(v) for b, v in assigned.items()}


def main():
    pool = build_pool()
    nt = [t for t in pool if t["identification_nontrivial"]]
    auto = [t for t in pool if t["identification"] == "autonomous"]

    print("=" * 78)
    print("① 전체 재고")
    print("=" * 78)
    print(f"  반응 총계                     {len(pool):>4}")
    print(f"  자율 식별형 (autonomous)      {len(auto):>4}  ({len(auto)/len(pool):.0%})")
    print(f"  **실질 식별 (후보 ≥4)**       {len(nt):>4}  ({len(nt)/len(pool):.0%})")
    print(f"  고유 화학종 (전체)            {len({species_key(t) for t in pool}):>4}")
    print(f"  고유 화학종 (실질 식별)       {len({species_key(t) for t in nt}):>4}")

    print("\n" + "=" * 78)
    print("② 밴드별 분포")
    print("=" * 78)
    print(f"{'밴드':<6}{'반응':>5}{'자율':>6}{'실질':>6}{'실질 화학종':>12}{'실질 비율':>10}")
    print("-" * 78)
    for b in BANDS:
        rows = [t for t in pool if t["band"] == b]
        a = [t for t in rows if t["identification"] == "autonomous"]
        n = [t for t in rows if t["identification_nontrivial"]]
        sp = len({species_key(t) for t in n})
        print(f"{b:<6}{len(rows):>5}{len(a):>6}{len(n):>6}{sp:>12}"
              f"{(len(n)/len(rows) if rows else 0):>9.0%}")

    print("\n" + "=" * 78)
    print("③ 화학종 중복 없이 선택 가능한 최대 (밴드 간 경합 반영)")
    print("=" * 78)
    nt_by_band = {b: {species_key(t) for t in nt if t["band"] == b} for b in BANDS}
    naive = {b: len(v) for b, v in nt_by_band.items()}
    unlimited = max_matching(nt_by_band)
    print(f"{'밴드':<6}{'단순 화학종 수':>14}{'경합 반영 최대':>15}")
    print("-" * 78)
    for b in BANDS:
        print(f"{b:<6}{naive[b]:>14}{unlimited[b]:>15}")
    print(f"{'합':<6}{sum(naive.values()):>14}{sum(unlimited.values()):>15}")
    print("\n  «단순»은 각 밴드에서 독립적으로 셌을 때. «경합 반영»은 한 화학종이 한 밴드에만")
    print("  배정된다는 제약을 넣어 계산한 최대 매칭이다. 둘이 같으면 경합이 없다는 뜻이다.")

    capped = max_matching(nt_by_band, TARGET_92)
    print(f"\n  N=92 분포(A30/B22/C25/D15)를 «실질 식별만»으로 채우려 하면:")
    for b in BANDS:
        want, got = TARGET_92[b], capped[b]
        mark = "🟢" if got >= want else "🔴"
        print(f"    {b}  {got:>3} / {want:<3} {mark}")
    print(f"    합 {sum(capped.values())} / 92")

    print("\n" + "=" * 78)
    print("④ 반응 유형·서브셋별 분포")
    print("=" * 78)
    print(f"{'유형':<14}{'반응':>5}{'자율':>6}{'실질':>6}{'중앙 후보수':>12}")
    print("-" * 78)
    import statistics as st
    for rt in ("conformer", "isomer"):
        rows = [t for t in pool if t["rtype"] == rt]
        print(f"{rt:<14}{len(rows):>5}"
              f"{sum(1 for t in rows if t['identification'] == 'autonomous'):>6}"
              f"{sum(1 for t in rows if t['identification_nontrivial']):>6}"
              f"{st.median([t['n_candidates'] for t in rows]):>12.0f}")

    print(f"\n{'서브셋':<12}{'반응':>5}{'자율':>6}{'실질':>6}{'후보수 범위':>13}"
          f"{'실질 화학종':>12}")
    print("-" * 78)
    for sub in sorted({t["subset"] for t in pool}):
        rows = [t for t in pool if t["subset"] == sub]
        n = [t for t in rows if t["identification_nontrivial"]]
        cands = [t["n_candidates"] for t in rows]
        print(f"{sub:<12}{len(rows):>5}"
              f"{sum(1 for t in rows if t['identification'] == 'autonomous'):>6}"
              f"{len(n):>6}{f'{min(cands)}–{max(cands)}':>13}"
              f"{len({species_key(t) for t in n}):>12}")

    print("\n" + "=" * 78)
    print("⑤ 밴드 분포를 유지하면서 실질 식별을 우선하면?")
    print("=" * 78)
    base = stratify(pool, TARGET_92)
    opt = stratify(pool, TARGET_92, nontrivial_first=True)
    for label, sel in (("현행 (자율 우선)", base), ("2차 기준 추가 (실질 우선)", opt)):
        got = Counter(t["band"] for t in sel)
        a = sum(1 for t in sel if t["identification"] == "autonomous")
        n = sum(1 for t in sel if t["identification_nontrivial"])
        dist = " ".join(f"{b}{got[b]}" for b in BANDS)
        print(f"  {label:<26} {dist}  자율 {a}/92  **실질 {n}/92**")
    print("\n  밴드별 목표 수는 그대로이므로 분포가 깨지지 않는다 — 2차 기준은 같은 밴드")
    print("  «안에서만» 순서를 바꾼다.")

    # 왜 개선이 없는가 — 손실이 밴드 «간»에서 나는지 «안»에서 나는지 가른다
    changed = [t["tid"] for t in base] != [t["tid"] for t in opt]
    nt_sp = defaultdict(set)
    for x in nt:
        nt_sp[species_key(x)].add(x["band"])
    sel = {species_key(x): (x["band"], x["identification_nontrivial"]) for x in opt}
    wasted = [(k, sel[k][0], sorted(nt_sp[k])) for k in nt_sp
              if k in sel and not sel[k][1]]
    unused = [k for k in nt_sp if k not in sel]
    print(f"\n  선택이 달라졌는가: {changed}")
    print(f"  실질 식별 화학종 {len(nt_sp)}종의 사용 내역")
    print(f"    실질 과제로 선택       {sum(1 for k in nt_sp if k in sel and sel[k][1])}")
    print(f"    같은 화학종의 자명 과제로 선택  {len(wasted)}  ← 낭비")
    for k, got, avail in wasted:
        print(f"       {k[0]}/{k[1]}: 밴드 {got} 에서 자명 과제로 소비 "
              f"(실질은 밴드 {avail} 에 있었다)")
    print(f"    미선택                 {len(unused)}")
    print("\n  **손실은 밴드 «간» 경합이다.** 위 사례들은 실질 과제가 다른 밴드에 있는데")
    print("  화학종이 먼저 다른 밴드에서 소비됐다. 밴드 «안» 순서를 바꾸는 2차 기준으로는")
    print("  고칠 수 없다 — 그래서 개선이 0 이다. 밴드 간 배정을 최적화하면 +2 를 얻지만")
    print("  (22 → 24) 복잡도에 비해 이득이 작다.")

    print("\n" + "=" * 78)
    print("판단 재료")
    print("=" * 78)
    print(f"  실질 식별 과제는 전체 {len(nt)}개, 화학종 "
          f"{len({species_key(t) for t in nt})}종이다.")
    print(f"  이것만으로 N=92 분포를 채우는 것은 "
          f"{'가능' if sum(capped.values()) >= 92 else '불가'}하다"
          f" (최대 {sum(capped.values())}개).")
    print("  → Main benchmark 는 기존 분포를 유지하고, Identification challenge 는")
    print("     실질 식별 과제만 따로 묶어 별도 평가하는 2층 구조가 재고와 맞는다.")


if __name__ == "__main__":
    main()
