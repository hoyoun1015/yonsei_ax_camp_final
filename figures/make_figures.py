"""Figure 제작 (한글 논문용) — **`results/plot_data/` 만 읽는다.**

실행 (프로젝트 루트에서):

    python3 src/vccl/scoring/plot_data.py     # 1) 동결본 → results/plot_data/ (assertion 포함)
    python3 figures/make_figures.py           # 2) results/plot_data/ → figures/draft/*.pdf|png

🔒 **그림에 들어가는 실험 결과 숫자를 이 파일에 문자열로 적지 않는다.**
전부 `results/plot_data/` 에서 읽어 포맷만 한다. 수치를 바꾸려면 1) 을 고쳐야 한다.
비용은 psi4 실측 wall time 전용 (DECISION_LOG 2026-08-14 (1) 정정 ②).

고유 기술명·기호는 번역하지 않는다 —
GFN2-xTB · B3LYP-D3(BJ)/def2-TZVP · τ · ΔE · p · R0 · V−τ · ALL_L3 · Band A–D.

Caption 은 `figures/captions.md`.
"""
from __future__ import annotations

import csv
import json
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "plot_data"
OUT = ROOT / "figures" / "draft"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Apple SD Gothic Neo", "AppleGothic", "Nanum Gothic",
                        "NanumGothic", "Malgun Gothic", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 8, "axes.linewidth": 0.8, "axes.labelsize": 8,
    "axes.titlesize": 9, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "figure.dpi": 150, "savefig.bbox": "tight", "savefig.pad_inches": 0.04,
    "pdf.fonttype": 42, "ps.fonttype": 42,
})

STYLE = {
    "R0":     dict(facecolor="0.88", hatch="///", edgecolor="black"),
    "V-tau":  dict(facecolor="0.62", hatch="...", edgecolor="black"),
    "V":      dict(facecolor="0.20", hatch="",    edgecolor="black"),
    "ALL_L3": dict(facecolor="white", hatch="xx", edgecolor="black"),
}
LABEL = {"R0": "R0 (규칙 기준선)", "V-tau": "V-τ (τ 제거)",
         "V": "V (전체 시스템)", "ALL_L3": "ALL_L3 (비교 기준)"}
SHORT = {"R0": "R0", "V-tau": "V-τ", "V": "V", "ALL_L3": "ALL_L3"}
ORDER = ["R0", "V-tau", "V", "ALL_L3"]
BANDS = ["A", "B", "C", "D"]
ACTION_KO = {"ABSTAIN": "판단 보류", "resolve": "판단 가능"}

def ko(text: str) -> str:
    """한글 폰트에 글리프가 없는 문자를 같은 뜻의 문자로 바꾼다.

    **내용을 고치는 것이 아니라 표기만 정규화한다** — U+2212(−)는 ASCII 하이픈과
    같은 «빼기»이고, 에이전트 원문 인용에서도 의미가 달라지지 않는다.
    """
    return text.replace("\u2212", "-").replace("\u2013", "-")


def J(n):
    return json.loads((DATA / n).read_text())


def C(n):
    with (DATA / n).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(fig, stem):
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{stem}.{ext}")
    plt.close(fig)
    print(f"  → figures/draft/{stem}.pdf | .png")


def pfmt(p):
    """p 값 표기. 유의하지 않은 경우 «차이 없음» 으로 읽히지 않게 적는다."""
    if p >= 0.01:
        return f"p = {p:.2f}" + (" (유의하지 않음)" if p >= 0.05 else "")
    m, e = f"{p:.1e}".split("e")
    return f"p = {float(m):.1f}" + r"$\times$10$^{" + str(int(e)) + r"}$"


# ── F0 · 시스템 실행 흐름 ────────────────────────────────────────────
def fig0():
    w = J("f0_workflow.json")
    n, a, b = w["n_tasks"], w["branch_a_escalate"], w["branch_b_reoperationalize"]
    r1, r2 = w["rounds"]["1"], w["rounds"]["2"]

    fig, ax = plt.subplots(figsize=(7.4, 3.7))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
    BY, BH = 46, 15
    boxes = {}

    def box(key, x, wd, text, *, fc="white", fs=7.2, y=BY, h=BH, bold=False):
        ax.add_patch(FancyBboxPatch((x, y), wd, h, boxstyle="round,pad=0.7",
                                    facecolor=fc, edgecolor="black", lw=1.0, zorder=3))
        ax.text(x + wd / 2, y + h / 2, text, ha="center", va="center", zorder=4,
                fontsize=fs, fontweight="bold" if bold else "normal")
        boxes[key] = (x, y, wd, h)

    box("hyp", 1, 13.5, "가설\n(고정)", fc="0.92", bold=True)
    box("pi", 18, 16, "PI\n비교 대상 구체화")
    box("chem", 37.5, 16, "계산화학자\n계산 수준 선택\n[τ]", fs=7.0)
    box("exe", 57, 15.5, "계산 실행층\n(정해진 계산만 수행)", fs=6.7)
    box("rev", 76, 17, "비판적 검토자\n[τ]", fs=7.0)
    box("con", 57, 15.5, "PI\n최종 판단  [τ]", y=14, h=13, fs=7.0)

    def arr(x1, y1, x2, y2, **kw):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), zorder=2,
                    arrowprops=dict(arrowstyle="-|>", mutation_scale=9,
                                    color="black", shrinkA=0, shrinkB=0, **kw))

    for p, q in (("hyp", "pi"), ("pi", "chem"), ("chem", "exe"), ("exe", "rev")):
        xa, _, wa, _ = boxes[p]; xb, *_ = boxes[q]
        arr(xa + wa, BY + BH / 2, xb, BY + BH / 2, lw=1.0)

    ya = BY + BH + 9
    ax.plot([84.5, 84.5, 45.5, 45.5], [BY + BH, ya, ya, BY + BH + 0.2],
            lw=1.7, color="black", zorder=2)
    arr(45.5, BY + BH + 3.0, 45.5, BY + BH, lw=1.7)
    ax.text(65, ya + 2.2, "경로 A   계산 수준 상향", ha="center", fontsize=7.2,
            fontweight="bold")
    ax.text(65, ya - 4.2, f"{n}과제 중 {a}회", ha="center", fontsize=6.8)

    yb = BY - 8
    ax.plot([80, 80, 26, 26], [BY, yb, yb, BY - 0.2], lw=0.9, color="black",
            ls=(0, (2.5, 2.5)), zorder=2)
    arr(26, BY - 3.0, 26, BY, lw=0.9, ls=(0, (2.5, 2.5)))
    ax.text(53, yb - 4.6, f"경로 B   비교 대상 재설정   {n}과제 중 {b}회",
            ha="center", fontsize=6.9)

    arr(84.5, BY, 72.5, 27, lw=1.0)
    arr(57, 20.5, 43, 20.5, lw=1.0)
    ax.text(42, 20.5, "원래 가설에 대한\n최종 판단", ha="right", va="center",
            fontsize=6.8, style="italic")

    lx, ly = 1.5, 17.0
    ax.add_patch(FancyBboxPatch((lx - 1.2, ly - 8.8), 34, 12.6,
                                boxstyle="round,pad=0.3", facecolor="white",
                                edgecolor="0.6", lw=0.6, zorder=0))
    ax.plot([lx, lx + 6.5], [ly, ly], lw=1.7, color="black")
    ax.text(lx + 8, ly, "경로 A (계산 수준 상향)", fontsize=6.5, va="center")
    ax.plot([lx, lx + 6.5], [ly - 5.2, ly - 5.2], lw=0.9, color="black",
            ls=(0, (2.5, 2.5)))
    ax.text(lx + 8, ly - 5.2, "경로 B (비교 대상 재설정)", fontsize=6.5, va="center")

    ax.text(1, 5.2,
            "[τ] 표시가 있는 단계에만 실측 방법 오차를 알려준다. 비교 대상을 "
            "구체화하는 단계에는 알려주지 않는다.\n"
            f"되돌아가는 화살표의 숫자는 조건 V에서 실제로 사용된 횟수다"
            f" (전체 {n}과제 중 {r1}과제는 한 라운드, {r2}과제는 두 라운드로 끝났다).",
            fontsize=6.5, va="top")
    save(fig, "F0_workflow")


# ── F1 · Band 정의 ───────────────────────────────────────────────────
def fig1():
    lad = J("f1_ladders.json"); tasks = C("f1_tasks.csv")
    rt_ko = {"conformer": "배좌 이성질체(conformer)", "isomer": "구조 이성질체"}
    fig, axes = plt.subplots(2, 1, figsize=(7.4, 4.4), sharex=True)
    fig.subplots_adjust(hspace=0.45)
    shade = {"D": "0.97", "C": "0.70", "B": "0.88", "A": "0.97"}

    for ax, rt in zip(axes, ("conformer", "isomer")):
        L = lad["ladders"][rt]; cnt = lad["band_counts_by_rtype"][rt]
        t3, t1, t3x = L["tau_L3"], L["tau_L1"], L["three_tau_L1"]
        lo, hi = 0.02, 300
        segs = [(lo, t3, "D"), (t3, t1, "C"), (t1, t3x, "B"), (t3x, hi, "A")]
        for p, q, nm in segs:
            ax.axvspan(p, q, color=shade[nm], zorder=0)
        for v in (t3, t1, t3x):
            ax.axvline(v, color="black", lw=0.8, zorder=1)
        for p, q, nm in segs:
            xm = (p * q) ** 0.5
            act = L["correct_action"][nm]
            em = nm == "C"
            ax.text(xm, 0.90, f"Band {nm}   n={cnt[nm]}", ha="center", va="center",
                    fontsize=8 if em else 7.3, fontweight="bold" if em else "normal")
            ax.text(xm, 0.67,
                    f"L1  {ACTION_KO[act['at_L1']]}\nL3  {ACTION_KO[act['at_L3']]}",
                    ha="center", va="center", fontsize=6.3,
                    fontweight="bold" if em else "normal")
        for v, lab in ((t3, "τ(L3)"), (t1, "τ(L1)"), (t3x, "3τ(L1)")):
            ax.text(v, 1.06, f"{lab} = {v:.2f}", ha="center", va="bottom", fontsize=6.4)
        xs = [float(r["abs_ref"]) for r in tasks if r["rtype"] == rt]
        ys = [0.24 + 0.09 * ((i * 3) % 4) / 3 for i in range(len(xs))]
        ax.plot(xs, ys, "o", ms=3.0, mfc="black", mec="white", mew=0.4, zorder=4,
                alpha=0.85)
        ax.set_xscale("log"); ax.set_xlim(lo, hi); ax.set_ylim(0.14, 1.02)
        ax.set_yticks([])
        ax.text(0.0, 1.14, f"{rt_ko[rt]}  (n = {cnt['n']})", transform=ax.transAxes,
                ha="left", va="bottom", fontsize=8, fontweight="bold")
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
    # 로그 눈금 라벨을 평문으로 — 한글 폰트에 위첨자 마이너스 글리프가 없다
    from matplotlib.ticker import FixedLocator, FixedFormatter
    ticks = [0.1, 1, 10, 100]
    for ax in axes:
        ax.xaxis.set_major_locator(FixedLocator(ticks))
        ax.xaxis.set_major_formatter(FixedFormatter(["0.1", "1", "10", "100"]))
        ax.xaxis.set_minor_locator(FixedLocator([]))
    axes[1].set_xlabel("|ΔE| (참조값 기준, kcal/mol · 로그 눈금)")
    axes[0].set_title("Band C에서는 L1과 L3의 판단이 달라진다\n"
                      "(경계는 반응 유형별 실측 방법 오차 τ · 점 하나가 과제 하나)",
                      fontsize=8.2, pad=32)
    save(fig, "F1_bands")


# ── F2 · 근거가 충분한 결론과 계산 결과에 따른 판단 ──────────────────
def fig2():
    d = J("f2_main.json"); cnt, tests, cal = d["counts"], d["tests"], d["calibration"]
    n = d["n_tasks"]
    fig = plt.figure(figsize=(7.4, 3.5))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.50, 0.60, 0.60], wspace=0.24)

    ax = fig.add_subplot(gs[0, 0])
    for i, k in enumerate(ORDER):
        ax.barh(i, cnt[k], height=0.60, **STYLE[k])
        ax.text(cnt[k] + 1.5, i, f"{cnt[k]}/{n}", va="center", fontsize=7.4)
    ax.set_yticks(range(4)); ax.set_yticklabels([LABEL[k] for k in ORDER])
    ax.invert_yaxis(); ax.set_xlim(0, 176)
    ax.set_xticks([0, 20, 40, 60, 80, n])
    ax.set_xlabel(f"근거가 충분한 결론 (전체 {n}과제)")
    ax.set_title("(가) 근거가 충분한 결론", loc="left", fontweight="bold")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for name, i1, i2, x in (("Vtau_vs_R0", 1, 0, 92), ("V_vs_R0", 2, 0, 100),
                            ("V_vs_Vtau", 2, 1, 108)):
        ax.plot([x, x + 2.4, x + 2.4, x], [i1, i1, i2, i2], lw=0.7, color="black",
                clip_on=False)
        ax.text(x + 4.5, (i1 + i2) / 2, pfmt(tests[name]["p"]), va="center",
                fontsize=6.3, ha="left")

    keys = [("adequate_commit", "inadequate_commit"),
            ("adequate_abstain", "inadequate_abstain")]
    for j, cond in enumerate(("V", "V-tau")):
        axm = fig.add_subplot(gs[0, 1 + j])
        m = cal[cond]
        for r in range(2):
            for c in range(2):
                v = m[keys[r][c]]
                sh = 1 - min(v / n * 1.45, 0.80)
                axm.add_patch(Rectangle((c, 1 - r), 1, 1, facecolor=str(round(sh, 2)),
                                        edgecolor="black", lw=0.9))
                off = (r == 0 and c == 1) or (r == 1 and c == 0)
                axm.text(c + .5, 1 - r + .60, str(v), ha="center", va="center",
                         fontsize=12, fontweight="bold" if off else "normal",
                         color="white" if sh < 0.45 else "black")
                if off:
                    axm.text(c + .5, 1 - r + .22,
                             "과대해석" if r == 0 else "과도한 신중",
                             ha="center", va="center", fontsize=5.9,
                             color="white" if sh < 0.45 else "black")
        axm.set_xlim(0, 2); axm.set_ylim(0, 2)
        axm.set_xticks([.5, 1.5])
        axm.set_xticklabels(["증거 충분", "증거 불충분"], fontsize=6.4)
        axm.set_yticks([1.5, .5])
        axm.set_yticklabels(["단정", "판단 보류"] if j == 0 else ["", ""], fontsize=6.8)
        axm.tick_params(length=0)
        axm.set_xlabel("직접 계산한 결과", fontsize=6.6)
        axm.set_title(("(나) " if j == 0 else "") + SHORT[cond], loc="left",
                      fontweight="bold", fontsize=8.5)
        for s in axm.spines.values():
            s.set_visible(False)
    fig.text(0.545, -0.07,
             f"과도한 신중  {pfmt(tests['overcaution']['p'])}"
             f"        과대해석  {pfmt(tests['overinterp']['p'])}"
             "  — 과대해석이 사전에 정한 주 지표였다", fontsize=6.6)
    save(fig, "F2_main_result")


# ── F3 · Band별 결과와 계산 비용 ─────────────────────────────────────
def fig3():
    d = J("f3_bands.json"); pb, tests, qc = d["per_band"], d["tests"], d["quality_cost"]
    n = sum(pb[b]["n"] for b in BANDS)
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.4),
                                  gridspec_kw=dict(width_ratios=[1.2, 1.0],
                                                   wspace=0.30))
    conds = ["R0", "V-tau", "V"]; w = 0.26
    for i, k in enumerate(conds):
        xs = [b + (i - 1) * w for b in range(4)]
        ax.bar(xs, [pb[b][k] for b in BANDS], width=w, label=LABEL[k], **STYLE[k])
        for x, b in zip(xs, BANDS):
            ax.text(x, pb[b][k] + 0.6, str(pb[b][k]), ha="center", fontsize=6.3)
    ax.set_xticks(range(4))
    ax.set_xticklabels([f"Band {b}\n(n={pb[b]['n']})" for b in BANDS])
    ax.set_ylabel("근거가 충분한 결론 (과제 수)"); ax.set_ylim(0, 43)
    ax.set_yticks([0, 10, 20, 30])
    ax.set_title("(가) Band별 결과", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(-0.02, 1.00),
              fontsize=6.5, handlelength=1.4, borderpad=0.2, labelspacing=0.25)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.plot([2 - w, 2 + w], [25.0, 25.0], lw=0.9, color="black")
    ax.text(2, 25.9, f"V 대 V-τ   {pfmt(tests['bandC_V_vs_Vtau']['p'])}",
            ha="center", fontsize=6.6, fontweight="bold")
    ax.text(2, 29.6, f"V 대 R0   {pfmt(tests['bandC_V_vs_R0']['p'])}",
            ha="center", fontsize=6.3)
    ax.text(3.52, 41.0,
            f"Band C 밖에서는\nV 대 R0  {pfmt(tests['nonC_V_vs_R0']['p'])}",
            ha="right", va="top", fontsize=6.3, style="italic")

    for k in ORDER:
        q = qc[k]
        ax2.plot(q["pct_of_all_l3"], q["justified"], "o", ms=9, zorder=3,
                 mfc=STYLE[k]["facecolor"], mec="black", mew=1.0)
    ax2.axvline(100, color="black", lw=0.7, ls=":", zorder=1)
    ax2.text(102, 37.5, "ALL_L3 = 100%", fontsize=6.0, rotation=90, va="bottom")
    for k, dx, dy, ha, va in (("R0", 9, 0, "left", "center"),
                              ("V", 0, -11, "center", "top"),
                              ("ALL_L3", 0, 11, "center", "bottom"),
                              ("V-tau", 10, 0, "left", "center")):
        q = qc[k]; pct = q["pct_of_all_l3"]
        txt = f"{pct:.1f}%" if pct >= 0.1 else f"{pct:.2f}%"
        ax2.annotate(f"{SHORT[k]}\n{txt} · {q['justified']}/{n}",
                     (pct, q["justified"]), textcoords="offset points",
                     xytext=(dx, dy), ha=ha, va=va, fontsize=6.5)
    ax2.set_xlim(-25, 215); ax2.set_ylim(36, 88)
    ax2.set_xlabel("계산 비용 (ALL_L3 대비 %)")
    ax2.set_ylabel("근거가 충분한 결론 (과제 수)")
    ax2.set_title("(나) 계산 비용과 해결 성능", loc="left", fontweight="bold")
    for s in ("top", "right"):
        ax2.spines[s].set_visible(False)
    save(fig, "F3_band_and_cost")


# ── F4 · 실행 사례 (통계적 대표 표본이 아니라 골라낸 사례다) ─────────
def fig4():
    d = J("f4_trajectory.json")
    st = {(s["step"], s["round"]): s for s in d["steps"]}
    ex1 = next(s for s in d["steps"] if s["step"] == "execute" and s["level"] == "L1")
    ex3 = next(s for s in d["steps"] if s["step"] == "execute" and s["level"] == "L3")

    fig, ax = plt.subplots(figsize=(7.4, 6.6))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
    X, W = 15, 74

    def blk(y, title, body=None, *, fc="white", lw=1.0):
        wrapped = textwrap.fill(body, 46) if body else None
        nl = wrapped.count("\n") + 1 if wrapped else 0
        h = 4.4 + 2.8 * nl
        ax.add_patch(FancyBboxPatch((X, y - h), W, h, boxstyle="round,pad=0.55",
                                    facecolor=fc, edgecolor="black", lw=lw, zorder=2))
        ax.text(X + 2, y - 2.4, title, fontsize=7.2, fontweight="bold", va="top",
                zorder=3)
        if wrapped:
            ax.text(X + 2, y - 5.8, wrapped, fontsize=6.4, va="top", zorder=3)
        return y - h

    def gap(y, dd=3.0):
        ax.annotate("", xy=(X + W / 2, y - dd), xytext=(X + W / 2, y),
                    arrowprops=dict(arrowstyle="-|>", mutation_scale=8, lw=0.9,
                                    color="black"))
        return y - dd

    def rnd(y0, y1, label):
        ax.add_patch(Rectangle((5, y1), 6.2, y0 - y1, facecolor="0.93",
                               edgecolor="black", lw=0.7, zorder=1))
        ax.text(8.1, (y0 + y1) / 2, label, rotation=90, ha="center", va="center",
                fontsize=7.2, fontweight="bold")

    y = 99
    y = blk(y, "가설 (고정)",
            "회전각이 gauche인 배좌가 anti인 배좌보다 전자에너지가 낮아 더 안정할 "
            "것이다.", fc="0.93")
    y = gap(y)
    top1 = y
    op = st[("operationalize", 1)]
    y = blk(y, f"PI · 비교 대상 구체화   →   {op['pair'][0]} 대 {op['pair'][1]}",
            ko(op["text_ko"]))
    y = gap(y)
    y = blk(y, f"계산화학자 · 계산 수준 선택   →   {ex1['level']} (GFN2-xTB)")
    y = gap(y)
    y = blk(y, f"계산 실행   ΔE = {ex1['delta_evidence']:+.3f} kcal/mol"
            f"     (계산 시간 {ex1['wall_s_measured']:.2f}초)", fc="0.93")
    y = gap(y)
    rv = st[("review", 1)]
    y = blk(y, "비판적 검토자 · 증거 불충분   →   계산 수준 상향", ko(rv["text_ko"]),
            fc="0.88", lw=1.6)
    rnd(top1, y, "1라운드")
    y = gap(y, 3.6)
    top2 = y
    y = blk(y, f"계산화학자 · 계산 수준 상향   →   {ex3['level']} "
            "(B3LYP-D3(BJ)/def2-TZVP)")
    y = gap(y)
    y = blk(y, f"계산 실행   ΔE = {ex3['delta_evidence']:+.3f} kcal/mol"
            f"     (계산 시간 {ex3['wall_s_measured']:.0f}초, 실측)", fc="0.93")
    y = gap(y)
    y = blk(y, "비판적 검토자 · 증거 충분   →   결론")
    y = gap(y)
    cc = st[("conclude", 2)]
    y = blk(y, f"PI · 원래 가설에 대한 최종 판단   →   {d['final_conclusion']}",
            ko(cc["text_ko"]), fc="0.88", lw=1.6)
    rnd(top2, y, "2라운드")

    ax.text(50, y - 4.8,
            f"τ(L1) = {d['tau_L1']:.2f},   τ(L3) = {d['tau_L3']:.2f},   "
            f"참조값 |ΔE| = {d['abs_ref']:.2f} kcal/mol"
            "   (Band C: L1으로는 판단할 수 없는 구간)", ha="center", fontsize=7.0)
    ax.text(50, y - 9.0,
            f"과제 하나의 실행 사례다 ({d['tid']}, 조건 V). 상자 안의 문장은 "
            "에이전트가 실제로 출력한 원문이며 표현을 다듬지 않았다.\n"
            "길이를 줄인 부분이 있으며 전문은 보충자료에 싣는다.",
            ha="center", va="top", fontsize=6.3, style="italic")
    save(fig, "F4_trajectory")


if __name__ == "__main__":
    print("Figure 제작 (한글) — results/plot_data/ 만 읽는다")
    for fn in (fig0, fig1, fig2, fig3, fig4):
        fn()
    print("\n완료.")
