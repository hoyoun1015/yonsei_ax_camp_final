#!/usr/bin/env python3
"""GMTKN55 서브셋 실측 조사 — 반응 수, |ΔE_ref| 분포, 원자수, 고유 화학종 수.

v1/v2 어느 브랜치에서 실행하든 현재 체크아웃 상태를 그대로 읽는다.
사용: python3 subset_survey.py <gmtkn55_root> [출력.csv]
"""
import re
import sys
import statistics as st
from pathlib import Path
from collections import Counter, defaultdict

SUBSETS = ["Amino20x4", "ISO34", "ISOL24", "ICONF", "ACONF", "PCONF21",
           "CDIE20", "SCONF", "MCONF", "BUT14DIOL", "UPU23"]

TMER = re.compile(r"^\s*\$tmer\s+(.*?)\s+x\s+(.*?)\s+\$w\s+(-?[\d.]+)\s*$")


def expand_braces(token):
    """'i1{e,p}/$f' -> ['i1e', 'i1p'];  'B_{T,G}/$f' -> ['B_T', 'B_G']"""
    token = token.replace("/$f", "")
    m = re.search(r"\{([^}]*)\}", token)
    if not m:
        return [token]
    pre, post = token[:m.start()], token[m.end():]
    return [pre + part + post for part in m.group(1).split(",")]


def parse_res(res_path):
    """반응 목록 반환: [(구조명들, 계수들, 참조값), ...]"""
    out = []
    for line in res_path.read_text(errors="ignore").splitlines():
        m = TMER.match(line)
        if not m:
            continue
        specs, coeffs, ref = m.group(1), m.group(2), float(m.group(3))
        names = []
        for tok in specs.split():
            names.extend(expand_braces(tok))
        out.append((names, coeffs.split(), ref))
    return out


def formula(xyz_path):
    """struc.xyz에서 분자식 문자열(원소 카운트 정규형)과 원자 수."""
    lines = xyz_path.read_text(errors="ignore").splitlines()
    n = int(lines[0].split()[0])
    elems = Counter()
    for ln in lines[2:2 + n]:
        parts = ln.split()
        if parts:
            elems[parts[0].capitalize()] += 1
    return "".join(f"{e}{elems[e]}" for e in sorted(elems)), n


def main():
    root = Path(sys.argv[1])
    rows = []
    for sub in SUBSETS:
        d = root / sub
        res = d / ".res"
        if not res.exists():
            rows.append((sub, "결측", "", "", "", "", ""))
            continue
        rxns = parse_res(res)
        refs = [abs(r) for _, _, r in rxns]

        struc_dirs = sorted(p.parent for p in d.glob("*/struc.xyz"))
        formulas, atoms = {}, []
        for sd in struc_dirs:
            try:
                f, n = formula(sd / "struc.xyz")
            except Exception:
                continue
            formulas[sd.name] = f
            atoms.append(n)

        species = len(set(formulas.values()))
        rows.append((
            sub, len(struc_dirs), species, len(rxns),
            round(st.median(refs), 2) if refs else "",
            f"{min(refs):.2f}–{max(refs):.2f}" if refs else "",
            f"{int(st.median(atoms))}/{max(atoms)}" if atoms else "",
        ))

    hdr = ["서브셋", "구조", "고유화학종", "반응", "중앙|ΔEref|", "범위", "원자수 중앙/최대"]
    w = [max(len(str(r[i])) for r in rows + [hdr]) for i in range(len(hdr))]
    print(" | ".join(h.ljust(w[i]) for i, h in enumerate(hdr)))
    print("-+-".join("-" * x for x in w))
    for r in rows:
        print(" | ".join(str(c).ljust(w[i]) for i, c in enumerate(r)))

    tot_rxn = sum(r[3] for r in rows if isinstance(r[3], int))
    tot_str = sum(r[1] for r in rows if isinstance(r[1], int))
    print(f"\n합계: 구조 {tot_str} · 반응 {tot_rxn}")

    if len(sys.argv) > 2:
        import csv
        with open(sys.argv[2], "w", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(hdr)
            wr.writerows(rows)
        print(f"저장: {sys.argv[2]}")


if __name__ == "__main__":
    main()
