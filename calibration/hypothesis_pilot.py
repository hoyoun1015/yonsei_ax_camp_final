#!/usr/bin/env python3
"""구조 자율 식별 파일럿 — 화학적 서술만으로 비교 대상을 특정할 수 있는가.

**동기.** 기획안 §4.4는 과제 프롬프트에서 구조 쌍 지정을 제거한다. "구조 A가 구조 B보다
안정할 것이다"가 아니라 화학적 서술을 주고, 어느 구조가 그에 해당하는지는 에이전트가
좌표에서 판정하게 한다. 그래야 RQ1(가설 해석)이 실제 과제가 된다.

**이 스크립트가 답하는 것 — 그것이 가능한가, 그리고 얼마나 정밀해야 하는가.**

정밀도에는 상충이 있다. 거칠게 쓰면(*"gauche 배좌가 더 안정하다"*) 해당 구조가 여럿이라
정답이 하나로 정해지지 않는다. 너무 정밀하게 쓰면(*"첫째 +gauche, 둘째 anti, 셋째 −gauche"*)
사실상 구조 ID를 풀어쓴 것이어서 자율 식별이라 부를 수 없다.

**그래서 «정답이 유일해지는 최소 정밀도»를 반응마다 찾는다.** 서술 정밀도를 3단으로 두고,
쌍의 두 구성원이 각자의 분자 안에서 유일해지는 가장 거친 단계를 고른다.

| 단계 | 서술 | 예 |
|---|---|---|
| 1 조성 | 회전각 유형의 «개수»만 | "anti 3개" · "gauche 2개 + skew 1개" |
| 2 패턴 | 순서는 주되 부호는 버림 | "anti-gauche-anti" |
| 3 부호 | 부호까지 | "gauche+ · anti · gauche−" |

3단이 필요하면 그 반응은 **자율 식별 부적합**으로 표시한다 — 그 정밀도는 구조 ID와 다름없다.

**모호한 가설은 버리지 않는다.** 대표 사례 트랙에서 쓴다 — 에이전트가 모호성을 인식하고
조작화를 다시 세우는(§5.3 분기 B) 능력 자체를 보여주는 재료가 된다.

사용: python3 hypothesis_pilot.py <gmtkn55_root> [서브셋 ...]
"""
import math
import sys
from collections import defaultdict
from pathlib import Path

# band_analysis 의 헬퍼를 재사용한다 — reactions / expand / species_map.
# 화학종 정의(연결성분)를 한 곳에만 두기 위해 복제하지 않고 가져온다.
_src = Path(__file__).with_name("band_analysis.py").read_text()
exec(_src.split("def main()")[0])

# ── 기하 판정 임계 ────────────────────────────────────────────────────
COV = {"H": 0.31, "C": 0.76, "N": 0.71, "O": 0.66, "F": 0.57, "P": 1.07,
       "S": 1.05, "SI": 1.11, "CL": 1.02}
BOND_TOL = 1.30          # 공유결합 반지름 합의 이 배수 안이면 결합
# IUPAC 관례에 맞춘 구간이다. 임의로 정한 값이 아니다 —
#   syn/synperiplanar 0–30 · gauche/synclinal 30–90 · anticlinal(skew) 90–150 ·
#   anti/antiperiplanar 150–180
# 초안에서 경계를 105°로 뒀더니 90~98° 구조가 gauche 로 뭉개져 skew 가 한 번도
# 발동하지 않았다(ACONF 의 `x` 계열). 관례값으로 되돌린다.
ANTI_MIN = 150.0
SKEW_LO = 90.0
GAUCHE_LO = 30.0
HBOND_DH = 1.25          # 이 거리 안의 H는 그 원자에 결합된 것으로 본다 (×COV 합)
HBOND_MAX = 2.60         # H···acceptor 최대 (Å)
HBOND_ANGLE_MIN = 100.0  # D–H···A 최소 각 (도)
DONORS = {"N", "O", "F", "S"}


def read_xyz(path):
    lines = path.read_text().splitlines()
    n = int(lines[0].split()[0])
    out = []
    for l in lines[2:2 + n]:
        f = l.split()
        if len(f) >= 4:
            out.append((f[0].upper(), tuple(float(x) for x in f[1:4])))
    return out


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def bonded(atoms, i, j):
    ei, ej = atoms[i][0], atoms[j][0]
    r = COV.get(ei, 0.8) + COV.get(ej, 0.8)
    return dist(atoms[i][1], atoms[j][1]) < r * BOND_TOL


def angle_at(p_center, p1, p2):
    v1 = [p1[i] - p_center[i] for i in range(3)]
    v2 = [p2[i] - p_center[i] for i in range(3)]
    n1 = math.sqrt(sum(x * x for x in v1)) or 1e-9
    n2 = math.sqrt(sum(x * x for x in v2)) or 1e-9
    c = max(-1.0, min(1.0, sum(v1[i] * v2[i] for i in range(3)) / (n1 * n2)))
    return math.degrees(math.acos(c))


def dihedral(p0, p1, p2, p3):
    b0 = [p0[i] - p1[i] for i in range(3)]
    b1 = [p2[i] - p1[i] for i in range(3)]
    b2 = [p3[i] - p2[i] for i in range(3)]
    n1 = math.sqrt(sum(x * x for x in b1)) or 1e-9
    b1 = [x / n1 for x in b1]

    def proj(v):
        d = sum(v[i] * b1[i] for i in range(3))
        return [v[i] - d * b1[i] for i in range(3)]

    v, w = proj(b0), proj(b2)
    x = sum(v[i] * w[i] for i in range(3))
    cr = [b1[1] * v[2] - b1[2] * v[1], b1[2] * v[0] - b1[0] * v[2],
          b1[0] * v[1] - b1[1] * v[0]]
    y = sum(cr[i] * w[i] for i in range(3))
    return math.degrees(math.atan2(y, x))


def heavy_backbone(atoms):
    """중원자(비수소) 사슬의 가장 긴 경로.

    탄소만 보면 ICONF 의 H2S2O7·H4P2O7 처럼 탄소가 없는 분자를 다룰 수 없다.
    """
    heavy = [i for i, (el, _) in enumerate(atoms) if el != "H"]
    adj = defaultdict(list)
    for a in range(len(heavy)):
        for b in range(a + 1, len(heavy)):
            i, j = heavy[a], heavy[b]
            if bonded(atoms, i, j):
                adj[i].append(j)
                adj[j].append(i)
    best = []

    def walk(node, seen):
        nonlocal best
        if len(seen) > len(best):
            best = list(seen)
        if len(seen) > 12:      # 폭주 방지 — 사슬이 길면 앞부분으로 충분하다
            return
        for nb in adj[node]:
            if nb not in seen:
                walk(nb, seen + [nb])

    for s in heavy:
        walk(s, [s])
    return best


def classify(a):
    m = abs(a)
    if m >= ANTI_MIN:
        return "anti"
    if SKEW_LO <= m < ANTI_MIN:
        return "skew+" if a > 0 else "skew-"
    if GAUCHE_LO <= m < SKEW_LO:
        return "gauche+" if a > 0 else "gauche-"
    return "syn"          # ±30° 미만 — 겹침(synperiplanar)


def h_bonds(atoms):
    """분자 내 수소결합 개수. D–H···A 로 판정한다."""
    hs = [i for i, (el, _) in enumerate(atoms) if el == "H"]
    acc = [i for i, (el, _) in enumerate(atoms) if el in DONORS]
    n = 0
    for h in hs:
        # 이 H 가 붙어 있는 도너를 찾는다
        d = None
        for a in acc:
            r = (COV.get(atoms[a][0], 0.8) + COV["H"]) * HBOND_DH
            if dist(atoms[h][1], atoms[a][1]) < r:
                d = a
                break
        if d is None:
            continue
        for a in acc:
            if a == d or bonded(atoms, d, a):
                continue
            if dist(atoms[h][1], atoms[a][1]) <= HBOND_MAX:
                if angle_at(atoms[h][1], atoms[d][1], atoms[a][1]) >= HBOND_ANGLE_MIN:
                    n += 1
                    break
    return n


def describe(path):
    """구조 하나의 서술자 3단."""
    atoms = read_xyz(path)
    bb = heavy_backbone(atoms)
    labels = []
    for i in range(max(0, len(bb) - 3)):
        labels.append(classify(dihedral(*[atoms[bb[i + k]][1] for k in range(4)])))
    hb = h_bonds(atoms)
    unsigned = tuple(l.rstrip("+-") for l in labels)
    comp = tuple(sorted((k, unsigned.count(k)) for k in set(unsigned)))
    return {
        "n_heavy": len([a for a in atoms if a[0] != "H"]),
        "hbond": hb,
        "L1": (comp, hb),                    # 조성
        "L2": (unsigned, hb),                # 패턴
        "L3": (tuple(labels), hb),           # 부호
        "raw": labels,
    }


def fmt(level_key, d):
    if level_key == "L1":
        comp, hb = d["L1"]
        s = " + ".join(f"{k} {v}" for k, v in comp) or "회전각 없음"
    elif level_key == "L2":
        pat, hb = d["L2"]
        s = "-".join(pat) or "회전각 없음"
    else:
        pat, hb = d["L3"]
        s = "-".join(pat) or "회전각 없음"
    return f"{s}" + (f" · H결합 {hb}" if hb else "")


def analyse(root, sub):
    d = root / sub
    rxns = reactions(d / ".res")
    smap = species_map(rxns)
    names = sorted({n for names_, _, _ in rxns for n in names_})

    desc = {}
    for n in names:
        xyz = d / n / "struc.xyz"
        if xyz.exists():
            desc[n] = describe(xyz)

    # 분자(연결성분)별로 각 정밀도에서 서술자가 유일한지
    by_species = defaultdict(list)
    for n in desc:
        by_species[smap.get(n, n)].append(n)

    unique = {}
    for lvl in ("L1", "L2", "L3"):
        u = set()
        for sp, members in by_species.items():
            counts = defaultdict(list)
            for n in members:
                counts[desc[n][lvl]].append(n)
            for k, v in counts.items():
                if len(v) == 1:
                    u.add(v[0])
        unique[lvl] = u

    # 반응마다 최소 정밀도
    verdict = []
    for names_, _, ref in rxns:
        if not all(n in desc for n in names_):
            verdict.append((names_, None))
            continue
        need = None
        for lvl in ("L1", "L2", "L3"):
            if all(n in unique[lvl] for n in names_):
                need = lvl
                break
        verdict.append((names_, need))
    return desc, verdict, unique


def main():
    root = Path(sys.argv[1]).resolve()
    subs = sys.argv[2:] or ["ACONF", "ICONF", "SCONF", "PCONF21"]

    summary = []
    for sub in subs:
        print("=" * 90)
        print(f"{sub}")
        print("=" * 90)
        desc, verdict, unique = analyse(root, sub)

        print(f"{'구조':<14} {'중원자':>4}  {'조성(L1)':<26} {'패턴(L2)':<26} 부호(L3)")
        print("-" * 90)
        for n in sorted(desc):
            d = desc[n]
            print(f"{n:<14} {d['n_heavy']:>4}  {fmt('L1', d):<26} "
                  f"{fmt('L2', d):<26} {fmt('L3', d)}")

        cnt = defaultdict(int)
        for _, need in verdict:
            cnt[need] += 1
        tot = len(verdict)
        print(f"\n반응 {tot}개의 최소 정밀도")
        for lvl, label in (("L1", "1 조성 — 가장 자연스럽다"),
                           ("L2", "2 패턴 — 자연스러운 서술 가능"),
                           ("L3", "3 부호 — 구조 ID 수준. 자율 식별 부적합"),
                           (None, "불가 — 어느 정밀도로도 유일하지 않음")):
            n = cnt.get(lvl, 0)
            if n:
                print(f"  {label:<42} {n:>3}개 ({n/tot*100:.0f}%)")
        usable = cnt.get("L1", 0) + cnt.get("L2", 0)
        print(f"  → **자율 식별 가능(L1·L2): {usable}/{tot} ({usable/tot*100:.0f}%)**")
        summary.append((sub, tot, cnt.get("L1", 0), cnt.get("L2", 0),
                        cnt.get("L3", 0), cnt.get(None, 0)))
        print()

    print("=" * 90)
    print("종합 — 서브셋별 자율 식별 가능성")
    print("=" * 90)
    print(f"{'서브셋':<10} {'반응':>4} {'L1 조성':>7} {'L2 패턴':>7} "
          f"{'L3 부호':>7} {'불가':>5} {'가능률':>7}")
    print("-" * 90)
    for sub, tot, a, b, c, x in summary:
        print(f"{sub:<10} {tot:>4} {a:>7} {b:>7} {c:>7} {x:>5} "
              f"{(a+b)/tot*100:>6.0f}%")
    print("\nL1·L2 가 자율 식별형으로 쓸 수 있는 반응이다. L3·불가는 쌍 지정형으로 남기거나")
    print("대표 사례 트랙에서 «모호성 인식 → 재조작화» 시연 재료로 쓴다(§4.4·§5.3).")


if __name__ == "__main__":
    main()
