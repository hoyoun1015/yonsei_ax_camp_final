#!/usr/bin/env python3
"""3단 사다리의 단조성 검정 — L1 > L2 > L3 인가.

**동기.** 기획안의 사다리는 L1(xTB) → L2(def2-SVP) → L3(def2-TZVP) 3단이고,
에스컬레이션 밴드가 `τ₃ < |ΔE_ref| ≤ τ₂` 로 정의된다. 이 정의는 **τ₂ > τ₃**,
즉 수준을 올리면 오차가 준다는 것을 전제한다.

L2 실측(2026-08-10) 결과 그 전제가 서브셋마다 깨진다. ISOL24 는 L2 가 L3 보다
**좋다**(3.345 대 5.562). 작은 기저에서 오차가 우연히 상쇄되는 알려진 현상이다.
전제가 깨지면 밴드 C 가 비거나 음수 폭이 되어 에스컬레이션 정답을 정의할 수 없다.

이 스크립트는 반응 유형별로 세 수준의 τ 를 내고, 단조성이 성립하는지와
그 결과 밴드가 어떻게 되는지를 판정한다. 추가 계산은 없다.

사용: python3 ladder_check.py <gmtkn55_root> <tau_work> <dft_work>
"""
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

_src = Path(__file__).with_name("band_analysis.py").read_text()
exec(_src.split("def main()")[0])

TYPES = {
    "conformer": ["ACONF", "Amino20x4", "ICONF", "SCONF", "PCONF21", "CDIE20"],
    "구조이성질체": ["ISO34", "ISOL24"],
}
TAG_L2 = "b3lyp-d3bj_def2-SVP"
TAG_L3 = "b3lyp-d3bj_def2-TZVP"
FLOOR = 0.2  # GMTKN55 참조값 자체의 오차. τ 는 이보다 작을 수 없다.


def main():
    root, tw, dw = (Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(),
                    Path(sys.argv[3]).resolve())

    levels = {
        "L1": lambda sub, n: xtb_energy(tw / sub / "sp" / n / "sp.log"),
        "L2": lambda sub, n: dft_energy(dw / sub / TAG_L2 / n / "sp.out"),
        "L3": lambda sub, n: dft_energy(dw / sub / TAG_L3 / n / "sp.out"),
    }

    # ── 서브셋별 ────────────────────────────────────────────────────────
    print("=" * 72)
    print("1. 서브셋별 τ — 단조성이 성립하는가")
    print("=" * 72)
    print(f"{'서브셋':<11} {'τ_L1':>7} {'τ_L2':>7} {'τ_L3':>7}   단조성")
    print("-" * 72)
    subset_rows = []
    for t, subs in TYPES.items():
        for sub in subs:
            rxns = reactions(root / sub / ".res")
            taus = {}
            for lvl, fn in levels.items():
                errs = []
                for names, coeffs, ref in rxns:
                    es = [fn(sub, n) for n in names]
                    if all(e is not None for e in es):
                        errs.append(abs(sum(c * e for c, e in zip(coeffs, es))
                                        * HARTREE - ref))
                taus[lvl] = st.mean(errs) if errs else None
            ok = taus["L1"] > taus["L2"] > taus["L3"]
            if ok:
                v = "🟢 L1>L2>L3"
            elif taus["L2"] > taus["L1"]:
                v = "🔴 L2가 L1보다 나쁘다"
            else:
                v = "🔴 L2가 L3보다 좋다"
            print(f"{sub:<11} {taus['L1']:>7.3f} {taus['L2']:>7.3f} "
                  f"{taus['L3']:>7.3f}   {v}")
            subset_rows.append((t, sub, taus, ok))

    n_ok = sum(1 for *_, ok in subset_rows if ok)
    print(f"\n단조성 성립: {n_ok}/8 서브셋")

    # ── 반응 유형별 ──────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("2. 반응 유형별 τ — 시스템이 실제로 쓰는 값")
    print("=" * 72)
    print(f"{'유형':<12} {'반응':>4} {'τ_L1':>7} {'τ_L2':>7} {'τ_L3':>7}   단조성")
    print("-" * 72)
    type_taus = {}
    rows = []  # (유형, 서브셋, 화학종, |ΔE_ref|)
    for t, subs in TYPES.items():
        errs = defaultdict(list)
        for sub in subs:
            rxns = reactions(root / sub / ".res")
            smap = species_map(rxns)
            for names, coeffs, ref in rxns:
                rows.append((t, sub, smap[names[0]], abs(ref)))
                for lvl, fn in levels.items():
                    es = [fn(sub, n) for n in names]
                    if all(e is not None for e in es):
                        errs[lvl].append(abs(sum(c * e for c, e in zip(coeffs, es))
                                            * HARTREE - ref))
        taus = {lvl: max(st.mean(v), FLOOR) for lvl, v in errs.items()}
        type_taus[t] = taus
        ok = taus["L1"] > taus["L2"] > taus["L3"]
        print(f"{t:<12} {len(errs['L3']):>4} {taus['L1']:>7.3f} {taus['L2']:>7.3f} "
              f"{taus['L3']:>7.3f}   {'🟢 성립' if ok else '🔴 깨짐'}")

    # ── 밴드 ────────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("3. 밴드 C 를 어느 경계로 정의할 것인가")
    print("=" * 72)
    print("설계대로면 밴드 C = τ₃ < |ΔE_ref| ≤ τ₂ (τ₂ = L2). L2 를 건너뛰고")
    print("2단 사다리로 가면 밴드 C = τ_L3 < |ΔE_ref| ≤ τ_L1 이다.\n")

    for label, hi_lvl in (("3단 — 상한 τ_L2", "L2"), ("2단 — 상한 τ_L1", "L1")):
        band_c, band_ab, band_d = set(), set(), set()
        rxn_c = 0
        widths = []
        for t in TYPES:
            lo, hi = type_taus[t]["L3"], type_taus[t][hi_lvl]
            widths.append(f"{t} {lo:.2f}~{hi:.2f}" + ("" if hi > lo else " ⚠음수폭"))
        for t, sub, sp, d in rows:
            lo, hi = type_taus[t]["L3"], type_taus[t][hi_lvl]
            if d > hi:
                band_ab.add((sub, sp))
            elif d > lo:
                band_c.add((sub, sp))
                rxn_c += 1
            else:
                band_d.add((sub, sp))
        g3 = "🟢 통과" if len(band_c) >= 25 else (
            "🟡 경고" if len(band_c) >= 15 else "🔴 폐기")
        print(f"{label}")
        print(f"  구간: {' · '.join(widths)}")
        print(f"  밴드 C {len(band_c):>3}종 ({rxn_c}반응) · A+B {len(band_ab):>3}종 · "
              f"D {len(band_d):>3}종   G3 {g3}")

    print("\n" + "=" * 72)
    print("판정")
    print("=" * 72)
    ci = type_taus["구조이성질체"]
    if ci["L2"] <= ci["L3"]:
        print("🔴 구조 이성질체에서 τ_L2 ≤ τ_L3 이다. L2 에서 L3 로 올리는 것이")
        print("   오차를 줄이지 않으므로, 3단 정의로는 이 유형의 밴드 C 가 성립하지 않는다.")
        print("   → 사다리를 L1 → L3 2단으로 확정하는 것이 근거 있는 선택이다.")
    else:
        print("🟢 3단 단조성이 유형 수준에서는 성립한다. 다만 서브셋 수준에서 깨지는 곳이")
        print("   있으므로, 유형 평균으로 뭉개는 것이 정당한지 별도 논의가 필요하다.")


if __name__ == "__main__":
    main()
