"""GMTKN55 파싱 · 화학종 클러스터링 · 기하 서술자.

`calibration/` 의 탐색 스크립트들이 검증한 로직을 정본으로 옮긴 것이다.
calibration 쪽은 측정 이력(provenance)으로 남기고, 앞으로는 이 모듈을 쓴다.

여기 있는 것은 전부 **결정론적이고 LLM 을 부르지 않는다.**
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

HARTREE = 627.5094740631
TMER = re.compile(r"^\s*\$tmer\s+(.*?)\s+x\s+(.*?)\s+\$w\s+(-?[\d.]+)\s*$")

# 반응 유형 — 결합 그래프로 판정 가능하므로 에이전트가 런타임에 조회할 수 있다
# (기획안 §3.2). 서브셋 정체를 노출하지 않는다.
CONFORMER_SUBSETS = ["ACONF", "Amino20x4", "ICONF", "SCONF", "PCONF21", "CDIE20"]
ISOMER_SUBSETS = ["ISO34", "ISOL24"]


def reaction_type(subset: str) -> str:
    if subset in CONFORMER_SUBSETS:
        return "conformer"
    if subset in ISOMER_SUBSETS:
        return "isomer"
    raise ValueError(f"알 수 없는 서브셋: {subset}")


# ── 반응 파싱 ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Reaction:
    subset: str
    names: tuple[str, ...]
    coeffs: tuple[int, ...]
    ref: float                      # 참조 ΔE (kcal/mol)

    @property
    def rid(self) -> str:
        return f"{self.subset}:{'+'.join(self.names)}"

    @property
    def abs_ref(self) -> float:
        return abs(self.ref)

    @property
    def rtype(self) -> str:
        return reaction_type(self.subset)


def _expand(token: str) -> list[str]:
    token = token.replace("/$f", "")
    m = re.search(r"\{([^}]*)\}", token)
    if not m:
        return [token]
    pre, post = token[: m.start()], token[m.end():]
    return [pre + p + post for p in m.group(1).split(",")]


def load_reactions(root: Path, subset: str) -> list[Reaction]:
    out = []
    for line in (root / subset / ".res").read_text(errors="ignore").splitlines():
        m = TMER.match(line)
        if not m:
            continue
        names: list[str] = []
        for tok in m.group(1).split():
            names.extend(_expand(tok))
        coeffs = [int(c) for c in m.group(2).split()]
        if len(names) == len(coeffs):
            out.append(Reaction(subset, tuple(names), tuple(coeffs), float(m.group(3))))
    return out


# ── 화학종 = 반응 그래프의 연결성분 ───────────────────────────────────
def species_map(rxns: list[Reaction]) -> dict[str, str]:
    """구조 이름 → 화학종 대표 이름.

    한 반응에 함께 등장하는 구조를 같은 화학종으로 묶고 이행적으로 닫는다.
    이름 규칙(접두사·번호)으로 뽑으면 CDIE20 의 `R21 → P20` 처럼 번호를 넘나드는
    반응에서 한 반응이 두 화학종으로 쪼개져, pseudo-replication 을 막으려던
    기획안 §4.2 의 취지가 깨진다.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for r in rxns:
        for n in r.names[1:]:
            a, b = find(r.names[0]), find(n)
            if a != b:
                parent[a] = b
    return {n: find(n) for n in parent}


# ── 기하 서술자 ───────────────────────────────────────────────────────
# 회전각 구간은 IUPAC 관례다. 임의로 정한 값이 아니다 —
#   syn 0–30 · gauche(synclinal) 30–90 · skew(anticlinal) 90–150 · anti 150–180
ANGLE_BINS = {"syn": (0.0, 30.0), "gauche": (30.0, 90.0),
              "skew": (90.0, 150.0), "anti": (150.0, 180.0)}
COV = {"H": 0.31, "C": 0.76, "N": 0.71, "O": 0.66, "F": 0.57,
       "P": 1.07, "S": 1.05, "SI": 1.11, "CL": 1.02}
BOND_TOL = 1.30
HBOND_DH = 1.25
HBOND_MAX = 2.60
HBOND_ANGLE_MIN = 100.0
DONORS = {"N", "O", "F", "S"}
MAX_BACKBONE = 12          # 사슬 탐색 폭주 방지


@dataclass
class Descriptor:
    n_heavy: int
    torsions: list[str] = field(default_factory=list)   # 부호 포함 라벨
    hbonds: int = 0

    @property
    def unsigned(self) -> tuple[str, ...]:
        return tuple(t.rstrip("+-") for t in self.torsions)

    @property
    def composition(self) -> tuple[tuple[str, int], ...]:
        u = self.unsigned
        return tuple(sorted((k, u.count(k)) for k in set(u)))

    def at(self, level: str):
        """서술 정밀도 3단. L1 조성 · L2 패턴 · L3 부호."""
        if level == "L1":
            return (self.composition, self.hbonds)
        if level == "L2":
            return (self.unsigned, self.hbonds)
        if level == "L3":
            return (tuple(self.torsions), self.hbonds)
        raise ValueError(level)


def read_xyz(path: Path) -> list[tuple[str, tuple[float, float, float]]]:
    lines = path.read_text().splitlines()
    n = int(lines[0].split()[0])
    out = []
    for l in lines[2:2 + n]:
        f = l.split()
        if len(f) >= 4:
            out.append((f[0].upper(), tuple(float(x) for x in f[1:4])))
    return out


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _bonded(atoms, i, j):
    r = COV.get(atoms[i][0], 0.8) + COV.get(atoms[j][0], 0.8)
    return _dist(atoms[i][1], atoms[j][1]) < r * BOND_TOL


def _angle(center, p1, p2):
    v1 = [p1[i] - center[i] for i in range(3)]
    v2 = [p2[i] - center[i] for i in range(3)]
    n1 = math.sqrt(sum(x * x for x in v1)) or 1e-9
    n2 = math.sqrt(sum(x * x for x in v2)) or 1e-9
    c = max(-1.0, min(1.0, sum(v1[i] * v2[i] for i in range(3)) / (n1 * n2)))
    return math.degrees(math.acos(c))


def dihedral(p0, p1, p2, p3) -> float:
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
    return math.degrees(math.atan2(sum(cr[i] * w[i] for i in range(3)), x))


def classify_torsion(angle: float) -> str:
    m = abs(angle)
    for name, (lo, hi) in ANGLE_BINS.items():
        if lo <= m < hi or (name == "anti" and m >= lo):
            if name == "syn":
                return "syn"
            return name + ("+" if angle > 0 else "-") if name != "anti" else "anti"
    return "anti"


def heavy_backbone(atoms) -> list[int]:
    """중원자 사슬의 가장 긴 경로.

    탄소만 보면 ICONF 의 H2S2O7·H4P2O7 처럼 탄소가 없는 분자를 다룰 수 없다.
    """
    heavy = [i for i, (el, _) in enumerate(atoms) if el != "H"]
    adj = defaultdict(list)
    for a in range(len(heavy)):
        for b in range(a + 1, len(heavy)):
            i, j = heavy[a], heavy[b]
            if _bonded(atoms, i, j):
                adj[i].append(j)
                adj[j].append(i)
    best: list[int] = []

    def walk(node, seen):
        nonlocal best
        if len(seen) > len(best):
            best = list(seen)
        if len(seen) > MAX_BACKBONE:
            return
        for nb in adj[node]:
            if nb not in seen:
                walk(nb, seen + [nb])

    for s in heavy:
        walk(s, [s])
    return best


def count_hbonds(atoms) -> int:
    """분자 내 수소결합 개수. D–H···A 기하로 판정한다.

    SCONF(당)·PCONF21(펩타이드)에서는 수소결합이 배좌 안정성을 지배하므로
    회전각만으로는 구조가 구분되지 않는다.
    """
    hs = [i for i, (el, _) in enumerate(atoms) if el == "H"]
    acc = [i for i, (el, _) in enumerate(atoms) if el in DONORS]
    n = 0
    for h in hs:
        donor = None
        for a in acc:
            r = (COV.get(atoms[a][0], 0.8) + COV["H"]) * HBOND_DH
            if _dist(atoms[h][1], atoms[a][1]) < r:
                donor = a
                break
        if donor is None:
            continue
        for a in acc:
            if a == donor or _bonded(atoms, donor, a):
                continue
            if (_dist(atoms[h][1], atoms[a][1]) <= HBOND_MAX
                    and _angle(atoms[h][1], atoms[donor][1], atoms[a][1]) >= HBOND_ANGLE_MIN):
                n += 1
                break
    return n


def describe(xyz_path: Path) -> Descriptor:
    atoms = read_xyz(xyz_path)
    bb = heavy_backbone(atoms)
    tors = [classify_torsion(dihedral(*[atoms[bb[i + k]][1] for k in range(4)]))
            for i in range(max(0, len(bb) - 3))]
    return Descriptor(n_heavy=sum(1 for a in atoms if a[0] != "H"),
                      torsions=tors, hbonds=count_hbonds(atoms))
