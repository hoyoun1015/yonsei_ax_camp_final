#!/usr/bin/env python3
"""밴드 분포 실측 — G3·G4 게이트 판정.

기획안 §밴드 정의를 서브셋별 τ 로 적용한다. τ₂→τ_L1, τ₃→τ_L3 대응이다
(L2 = xTB 국소최적화는 전 서브셋에서 L1 보다 나빠 사다리 단에서 탈락했다).

    A 명백     |ΔE_ref| > 3·τ_L1
    B 경계     τ_L1 < |ΔE_ref| ≤ 3·τ_L1
    C 상승필요 τ_L3 < |ΔE_ref| ≤ τ_L1     ← 연구의 심장
    D 판정불가 |ΔE_ref| ≤ τ_L3

**밴드를 절대 구간이 아니라 서브셋별 τ 로 정의하는 것이 핵심이다.**
τ_L3 가 서브셋마다 8~30배 다르므로(docs/D1_실측결과.md §8) 단일 구간을 쓰면
L1 으로도 판정 가능한 과제가 밴드 C 로 잘못 분류된다.

게이트 (기획안 §게이트):
    G3  밴드 C 에 고유 **화학종** 25종 이상. **15종 미만이면 폐기.**
    G4  밴드 A+B ≥ 50종, 밴드 D ≥ 10종.

**n 은 과제 수가 아니라 화학종 수다.** 한 화학종에서 여러 과제를 뽑아도
n 은 늘지 않는다. 그래서 반응 수와 화학종 수를 둘 다 낸다.

사용: python3 band_analysis.py <gmtkn55_root> <tau_work> <dft_work>
"""
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

HARTREE = 627.5094740631
TMER = re.compile(r"^\s*\$tmer\s+(.*?)\s+x\s+(.*?)\s+\$w\s+(-?[\d.]+)\s*$")
DFT_TAG = "b3lyp-d3bj_def2-TZVP"

# 기획안이 상정한 서브셋별 화학종 수. 매핑 규칙이 이것과 어긋나면 경고한다 —
# 규칙이 틀렸거나 기획안 수치가 틀렸거나 둘 중 하나이고, 조용히 넘어가면 안 된다.
EXPECTED_SPECIES = {"ISO34": 28, "ISOL24": 24, "Amino20x4": 19, "ICONF": 10,
                    "ACONF": 3, "PCONF21": 3, "SCONF": 2, "CDIE20": 3}

SUBSETS = ["ISO34", "ISOL24", "Amino20x4", "ICONF", "ACONF", "PCONF21",
           "SCONF", "CDIE20"]


def species_of(sub, name):
    """구조 이름에서 화학종을 뽑는다. 서브셋마다 명명 규칙이 다르다.

    같은 화학종의 서로 다른 배좌/이성질체는 같은 키로 묶여야 한다.
    """
    if sub in ("ACONF", "Amino20x4", "ICONF"):
        # B_G / ALA_xab / H2S2O7_1 — 마지막 밑줄 앞이 분자다.
        return name.rsplit("_", 1)[0]
    if sub == "ISOL24":
        # i12e / i12p — e(반응물)와 p(생성물)가 같은 이성질화 쌍이다.
        m = re.match(r"(i\d+)[ep]$", name)
        return m.group(1) if m else name
    if sub == "PCONF21":
        # GLY_ab / SER_pII 는 분자별, 숫자 이름들은 한 트리펩타이드의 배좌다.
        if "_" in name:
            return name.split("_", 1)[0]
        return "PCONF21_peptide"
    if sub == "SCONF":
        # C1..C15 / G1..G4 — 앞의 알파벳이 당 분자다.
        m = re.match(r"([A-Za-z]+)", name)
        return m.group(1) if m else name
    if sub in ("ISO34", "CDIE20"):
        # E26/P26, R20/P20 — 앞 글자를 떼면 같은 골격의 짝이 묶인다.
        m = re.match(r"[A-Za-z]+(\d+)$", name)
        return m.group(1) if m else name
    return name


def expand(token):
    token = token.replace("/$f", "")
    m = re.search(r"\{([^}]*)\}", token)
    if not m:
        return [token]
    pre, post = token[:m.start()], token[m.end():]
    return [pre + p + post for p in m.group(1).split(",")]


def reactions(res_path):
    out = []
    for line in res_path.read_text(errors="ignore").splitlines():
        m = TMER.match(line)
        if not m:
            continue
        names = []
        for tok in m.group(1).split():
            names.extend(expand(tok))
        coeffs = [int(c) for c in m.group(2).split()]
        if len(names) == len(coeffs):
            out.append((names, coeffs, float(m.group(3))))
    return out


def xtb_energy(log_path):
    if not log_path.exists():
        return None
    txt = log_path.read_text(errors="ignore")
    if "normal termination of xtb" not in txt:
        return None
    m = re.findall(r"TOTAL ENERGY\s+(-?\d+\.\d+)", txt)
    return float(m[-1]) if m else None


def dft_energy(out_path):
    if not out_path.exists():
        return None
    txt = out_path.read_text(errors="ignore")
    if "Psi4 exiting successfully" not in txt:
        return None
    m = re.findall(r"Total Energy\s*=\s*(-?\d+\.\d+)", txt)
    return float(m[-1]) if m else None


def tau_of(rxns, energy_fn):
    """이 서브셋의 방법오차 MAE. 에너지가 하나라도 없는 반응은 뺀다."""
    errs, missing = [], 0
    for names, coeffs, ref in rxns:
        es = [energy_fn(n) for n in names]
        if any(e is None for e in es):
            missing += 1
            continue
        errs.append(abs(sum(c * e for c, e in zip(coeffs, es)) * HARTREE - ref))
    return (st.mean(errs) if errs else None), len(errs), missing


def band_of(dref, tau1, tau3):
    a = abs(dref)
    if a > 3 * tau1:
        return "A"
    if a > tau1:
        return "B"
    if a > tau3:
        return "C"
    return "D"


def main():
    root, tau_work, dft_work = (Path(sys.argv[1]).resolve(),
                                Path(sys.argv[2]).resolve(),
                                Path(sys.argv[3]).resolve())

    print("서브셋별 τ 와 밴드 분포 (단위 kcal/mol)\n")
    print(f"{'서브셋':<11} {'τ_L1':>7} {'τ_L3':>7} {'반응':>5} "
          f"{'A':>4} {'B':>4} {'C':>4} {'D':>4}   화학종 A/B/C/D")
    print("-" * 78)

    species_band = defaultdict(set)   # 밴드 → {(서브셋, 화학종)}
    rxn_total = defaultdict(int)
    skipped = []

    for sub in SUBSETS:
        res = root / sub / ".res"
        if not res.exists():
            skipped.append((sub, ".res 없음"))
            continue
        rxns = reactions(res)

        tau1, n1, _ = tau_of(rxns, lambda n: xtb_energy(tau_work / sub / "sp" / n / "sp.log"))
        tau3, n3, miss3 = tau_of(
            rxns, lambda n: dft_energy(dft_work / sub / DFT_TAG / n / "sp.out"))

        if tau1 is None or tau3 is None:
            skipped.append((sub, f"τ_L1={'없음' if tau1 is None else '있음'} "
                                 f"τ_L3={'없음' if tau3 is None else '없음/미완'}"))
            continue
        if miss3:
            # τ_L3 가 일부 반응만으로 나온 값이면 밴드 경계가 흔들린다.
            skipped.append((sub, f"τ_L3 누락 {miss3}개 — 미완결"))
            continue

        counts = defaultdict(int)
        sp_counts = defaultdict(set)
        for names, coeffs, ref in rxns:
            b = band_of(ref, tau1, tau3)
            counts[b] += 1
            rxn_total[b] += 1
            for n in names:
                key = (sub, species_of(sub, n))
                species_band[b].add(key)
                sp_counts[b].add(key)

        sp = "/".join(str(len(sp_counts[b])) for b in "ABCD")
        print(f"{sub:<11} {tau1:>7.3f} {tau3:>7.3f} {len(rxns):>5} "
              f"{counts['A']:>4} {counts['B']:>4} {counts['C']:>4} {counts['D']:>4}   {sp}")

        uniq = {species_of(sub, n) for names, _, _ in rxns for n in names}
        exp = EXPECTED_SPECIES.get(sub)
        if exp is not None and len(uniq) != exp:
            print(f"{'':<11} ⚠ 화학종 {len(uniq)}종 — 기획안 상정 {exp}종과 다르다. "
                  f"매핑 규칙이나 기획안 수치를 재검토할 것.")

    if skipped:
        print("\n제외된 서브셋 (τ 미완결 — 밴드를 매길 수 없다):")
        for sub, why in skipped:
            print(f"  {sub}: {why}")

    print("\n" + "=" * 78)
    print("게이트 판정 — **화학종 기준**\n")
    nc = len(species_band["C"])
    nab = len(species_band["A"] | species_band["B"])
    nd = len(species_band["D"])

    def verdict(ok, warn=None):
        return "🟢 통과" if ok else ("🟡 " + warn if warn else "🔴 미달")

    print(f"  G3  밴드 C 화학종 {nc:>3}종  (목표 25 · 15 미만이면 폐기)   "
          f"{verdict(nc >= 25, '경고 — 서브셋 추가 필요' if nc >= 15 else None)}")
    if nc < 15:
        print("      🔴 **15종 미만이다. 기획안대로면 이 설계는 폐기 대상이다.**")
    print(f"  G4  밴드 A+B 화학종 {nab:>3}종 (목표 50)                    {verdict(nab >= 50)}")
    print(f"  G4  밴드 D  화학종 {nd:>3}종  (목표 10)                    {verdict(nd >= 10)}")
    print(f"\n  참고 — 반응 수: A {rxn_total['A']} · B {rxn_total['B']} · "
          f"C {rxn_total['C']} · D {rxn_total['D']}")

    if skipped:
        print("\n⚠ 위 판정은 완결된 서브셋만 센 것이다. 제외된 서브셋의 τ_L3 가 나오면"
              "\n  다시 돌려야 확정된다. 특히 밴드 C·D 의 주 공급원이 빠져 있으면"
              "\n  G3 를 과소평가한다.")


if __name__ == "__main__":
    main()
