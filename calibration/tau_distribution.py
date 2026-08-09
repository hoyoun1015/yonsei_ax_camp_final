#!/usr/bin/env python3
"""τ 를 문턱으로 쓰는 것이 타당한가 — 오차 분포와 민감도 분석.

**동기.** τ 는 MAE(평균)인데 우리는 그것을 개별 과제의 결정론적 문턱으로 쓴다.
`|ΔE_ref| ≤ τ → ABSTAIN` 이라는 라벨이 여기 걸려 있다. 그런데 오차 분포가
치우쳐 있으면(ISO34 는 MAE 1.949 인데 최대 10.31) 평균은 대표값이 아니다.

이 스크립트가 답하려는 것 셋.

1. 오차 분포가 실제로 어떻게 생겼는가 — 평균·중앙·백분위수·꼬리
2. 문턱을 평균 대신 중앙값이나 75백분위로 바꾸면 밴드가 얼마나 달라지는가
3. 그 선택이 G3(밴드 C 화학종 ≥ 25) 판정을 뒤집는가

추가 계산은 없다. 이미 끝난 331구조의 캐시만 다시 읽는다.

사용: python3 tau_distribution.py <gmtkn55_root> <tau_work> <dft_work>
"""
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.argv = sys.argv  # band_analysis 의 헬퍼를 재사용한다
_src = Path(__file__).with_name("band_analysis.py").read_text()
exec(_src.split("def main()")[0])

TYPES = {
    "conformer": ["ACONF", "Amino20x4", "ICONF", "SCONF", "PCONF21", "CDIE20"],
    "구조이성질체": ["ISO34", "ISOL24"],
}


def pct(v, q):
    """q 백분위수 (0~100). 선형보간."""
    s = sorted(v)
    if not s:
        return float("nan")
    k = (len(s) - 1) * q / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def collect(root, tau_work, dft_work):
    """반응유형 → 수준 → [|오차|], 그리고 반응 목록."""
    errs = defaultdict(lambda: defaultdict(list))
    rows = []  # (유형, 서브셋, 화학종, |ΔE_ref|)
    for t, subs in TYPES.items():
        for sub in subs:
            rxns = reactions(root / sub / ".res")
            smap = species_map(rxns)
            for names, coeffs, ref in rxns:
                rows.append((t, sub, smap[names[0]], abs(ref)))
                for lvl, fn in (
                    ("L1", lambda n: xtb_energy(tau_work / sub / "sp" / n / "sp.log")),
                    ("L3", lambda n: dft_energy(dft_work / sub / DFT_TAG / n / "sp.out")),
                ):
                    es = [fn(n) for n in names]
                    if all(e is not None for e in es):
                        calc = sum(c * e for c, e in zip(coeffs, es)) * HARTREE
                        errs[t][lvl].append(abs(calc - ref))
    return errs, rows


def band_c_species(rows, thr):
    """thr[(유형, 수준)] → 문턱. 밴드 C 화학종 수를 센다."""
    out = set()
    for t, sub, sp, d in rows:
        if thr[(t, "L3")] < d <= thr[(t, "L1")]:
            out.add((sub, sp))
    return out


def main():
    root, tau_work, dft_work = (Path(sys.argv[1]).resolve(),
                                Path(sys.argv[2]).resolve(),
                                Path(sys.argv[3]).resolve())
    errs, rows = collect(root, tau_work, dft_work)

    print("=" * 74)
    print("1. 오차 분포 — τ(평균)는 대표값인가")
    print("=" * 74)
    print(f"{'유형':<12} {'수준':<4} {'n':>4} {'평균(τ)':>8} {'중앙':>7} "
          f"{'p75':>7} {'p90':>7} {'최대':>7} {'평균초과':>7}")
    print("-" * 74)
    stats = {}
    for t in TYPES:
        for lvl in ("L1", "L3"):
            v = errs[t][lvl]
            m = st.mean(v)
            over = sum(1 for x in v if x > m) / len(v) * 100
            stats[(t, lvl)] = dict(mean=m, median=st.median(v),
                                   p75=pct(v, 75), p90=pct(v, 90), max=max(v))
            print(f"{t:<12} {lvl:<4} {len(v):>4} {m:>8.3f} {st.median(v):>7.3f} "
                  f"{pct(v,75):>7.3f} {pct(v,90):>7.3f} {max(v):>7.2f} {over:>6.0f}%")

    print("\n분포가 오른쪽으로 치우쳐 있으면 평균 > 중앙값이고, 평균 초과 비율이")
    print("50%보다 작다. 그 경우 평균은 '전형적인 오차'가 아니라 꼬리에 끌린 값이다.")

    print("\n" + "=" * 74)
    print("2. 문턱 선택이 밴드 C 를 얼마나 흔드는가 — G3 민감도")
    print("=" * 74)
    print(f"{'문턱 정의':<22} {'conformer τ_L1/τ_L3':>22} {'밴드 C 화학종':>14}  G3")
    print("-" * 74)
    for label, key in (("평균 (현행 τ)", "mean"), ("중앙값", "median"),
                       ("75백분위", "p75"), ("90백분위", "p90")):
        thr = {(t, l): max(stats[(t, l)][key], 0.2)   # 참조값 바닥 0.2
               for t in TYPES for l in ("L1", "L3")}
        n = len(band_c_species(rows, thr))
        c1, c3 = thr[("conformer", "L1")], thr[("conformer", "L3")]
        mark = "🟢 통과" if n >= 25 else ("🟡 경고" if n >= 15 else "🔴 폐기")
        print(f"{label:<22} {c1:>10.3f} / {c3:<10.3f} {n:>13}  {mark}")

    print("\n(τ := max(실측, 0.2) — GMTKN55 참조값 자체의 오차가 ±0.2 이므로 바닥을 깐다)")

    print("\n" + "=" * 74)
    print("3. 경계 근처 과제는 얼마나 되는가")
    print("=" * 74)
    print("문턱을 ±25% 흔들었을 때 밴드가 바뀌는 반응의 비율이다.")
    print("이 값이 크면 라벨이 문턱 선택에 민감하다는 뜻이다.\n")
    base = {(t, l): max(stats[(t, l)]["mean"], 0.2) for t in TYPES for l in ("L1", "L3")}
    for f in (0.75, 1.25):
        alt = {k: v * f for k, v in base.items()}
        moved = sum(1 for t, sub, sp, d in rows
                    if (base[(t, "L3")] < d <= base[(t, "L1")]) !=
                       (alt[(t, "L3")] < d <= alt[(t, "L1")]))
        print(f"  문턱 ×{f:.2f} → 밴드 C 진입·이탈 {moved:>3}개 / {len(rows)}반응 "
              f"({moved/len(rows)*100:.0f}%)")

    # ── 그림 ────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        for cand in ("AppleGothic", "Apple SD Gothic Neo", "NanumGothic"):
            if any(f.name == cand for f in font_manager.fontManager.ttflist):
                plt.rcParams["font.family"] = cand
                break
        plt.rcParams["axes.unicode_minus"] = False

        fig, axes = plt.subplots(2, 2, figsize=(11, 7))
        for i, t in enumerate(TYPES):
            for j, lvl in enumerate(("L1", "L3")):
                ax = axes[i][j]
                v = errs[t][lvl]
                s = stats[(t, lvl)]
                ax.hist(v, bins=30, color="#5b8def", edgecolor="white", linewidth=0.5)
                ax.axvline(s["mean"], color="#d1495b", lw=2,
                           label=f"평균 τ = {s['mean']:.2f}")
                ax.axvline(s["median"], color="#2a9d8f", lw=2, ls="--",
                           label=f"중앙값 = {s['median']:.2f}")
                ax.axvline(s["p75"], color="#e9c46a", lw=2, ls=":",
                           label=f"p75 = {s['p75']:.2f}")
                ax.set_title(f"{t} · {lvl}  (n={len(v)}, 최대 {s['max']:.1f})",
                             fontsize=10)
                ax.set_xlabel("|오차| (kcal/mol)", fontsize=8)
                ax.set_ylabel("반응 수", fontsize=8)
                ax.legend(fontsize=7.5)
                ax.tick_params(labelsize=8)
        fig.suptitle("방법오차 분포 — τ(평균)는 꼬리에 끌린다", fontsize=12)
        fig.tight_layout()
        out = Path(__file__).parent.parent / "figures" / "tau_distribution.png"
        out.parent.mkdir(exist_ok=True)
        fig.savefig(out, dpi=150)
        print(f"\n그림 저장: {out}")
    except Exception as e:
        print(f"\n(그림 생략: {e})")


if __name__ == "__main__":
    main()
