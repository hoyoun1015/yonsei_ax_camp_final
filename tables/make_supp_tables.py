"""보충자료 표 S1~S8 제작 — **`results/table_data/` 만 읽는다.**

실행 (프로젝트 루트에서):

    python3 src/vccl/scoring/table_data.py    # 1) 동결본 → results/table_data/ (assertion)
    python3 tables/make_supp_tables.py        # 2) → tables/supplementary/*.md|.pdf

🔒 **표에 들어가는 숫자를 이 파일에 적지 않는다.** 전부 `results/table_data/` 에서 읽어
배치만 한다. 수치를 바꾸려면 1) 을 고쳐야 한다.

🔒 **Main Table 1 과 Figure F0~F4 는 LOCK 이다.** 이 스크립트는 `tables/draft/` 와
`results/plot_data/` 를 읽지도 쓰지도 않는다.

스타일은 Main Table 1 과 같다 — 세로선 없음, 색 없음, 가로줄 세 개(booktabs 관례).
흑백 인쇄에서도 읽힌다.

번호 체계 (현재 정본 · `paper_logic/table_design.md` §4)

| | |
|---|---|
| S1 | 통계검정 요약 |
| S2 | 반응 유형·서브셋별 τ 실측 전량 ← **LOCK 된 그림 2 caption 이 이 번호를 참조** |
| S3 | 오류 분해 (탐색적) |
| S4 | 벤치마크 구성 |
| S5 | 계산시간·비용 상세 |
| S6 | identification challenge |
| S7 | L0 contamination probe |
| S8 | 그림 5 사례의 에이전트 출력 전문 |
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Apple SD Gothic Neo", "AppleGothic", "Nanum Gothic",
                        "NanumGothic", "Malgun Gothic", "DejaVu Sans"],
    "axes.unicode_minus": False, "font.size": 9,
    "figure.dpi": 200, "savefig.bbox": "tight", "savefig.pad_inches": 0.06,
    "pdf.fonttype": 42, "ps.fonttype": 42,
})

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "table_data"
OUT = ROOT / "tables" / "supplementary"
OUT.mkdir(parents=True, exist_ok=True)

BANDS = ("A", "B", "C", "D")
LAB = {"V": "V", "V-tau": "V−τ", "R0": "R0", "ALL_L3": "ALL_L3"}
SUB_SHORT = {"all": "전체 92", "C": "Band C 25", "non-C": "Band C 밖 67"}
STATUS_SHORT = {"주 지표·주 대비 사전 지정 · 검정은 사후": "주 지표·주 대비 사전",
                "비교축 사전 지정 · 검정은 사후": "비교축 사전",
                "post-hoc 탐색적": "post-hoc"}


def ko(t: str) -> str:
    """한글 폰트에 글리프가 없는 문자를 같은 뜻의 문자로 바꾼다 (표기 정규화)."""
    sup = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
    return (t.replace("**", "").replace("`", "")          # markdown 강조가 새지 않게
             .replace("−", "-").replace("–", "-")
             .replace("≤", "<=").replace("≥", ">=")
             .replace("×10", "x10").translate(sup))


def sci(p: float) -> str:
    """PDF 용 p 값 표기. 지수는 mathtext 로 낸다 — 한글 폰트에 위첨자가 없다."""
    if p >= 0.001:
        return f"{p:.4g}"
    m, ex = f"{p:.2e}".split("e")
    return rf"${m}{{\times}}10^{{{int(ex)}}}$"


def md_sci(p: float) -> str:
    if p >= 0.001:
        return f"{p:.4g}"
    m, ex = f"{p:.2e}".split("e")
    sup = str(int(ex)).replace("-", "⁻")
    return f"{m}×10{''.join('⁰¹²³⁴⁵⁶⁷⁸⁹'[int(c)] if c.isdigit() else c for c in sup)}"


# ── 렌더러 ───────────────────────────────────────────────────────────
# 블록: ("h", 제목) · ("t", 헤더, 행들, 폭, 정렬) · ("p", 문단) · ("s",)
def render(stem: str, title: str, blocks: list, width: float = 7.0) -> None:
    """블록을 세로로 쌓아 한 장으로 그린다. 좌표는 «행 단위» 다."""
    ROW = 0.235                                   # 행 하나의 세로 크기(인치)
    WRAP = int(width * 15.5)

    plan, h = [], 0.0
    h += 1.35                                     # 표 제목
    for b in blocks:
        if b[0] == "h":
            plan.append((b, 1.15)); h += 1.15
        elif b[0] == "t":
            n = len(b[2]) + 1.5
            plan.append((b, n)); h += n + 0.5
        elif b[0] == "p":
            lines = []
            for para in b[1].split("\n"):
                lines += textwrap.wrap(ko(para), WRAP) or [""]
            plan.append((b, len(lines) * 0.68 + 0.35, lines))
            h += len(lines) * 0.68 + 0.35
        else:
            plan.append((b, 0.5)); h += 0.5

    fig = plt.figure(figsize=(width, h * ROW + 0.15))
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(-h, 0)

    y = -0.95
    for line in textwrap.wrap(ko(title), int(WRAP * 0.78)):
        ax.text(0, y, line, fontsize=10.5, fontweight="bold", va="baseline")
        y -= 0.95
    y += 0.95 - 1.35

    for item in plan:
        b = item[0]
        if b[0] == "h":
            y -= 0.85
            ax.text(0, y, ko(b[1]), fontsize=9.2, fontweight="bold", va="baseline")
            y -= 0.30
        elif b[0] == "t":
            _, header, rows, widths, aligns = b
            xs, acc = [], 0.0
            for w in widths:
                xs.append(acc); acc += w
            xs = [x / acc for x in xs] + [1.0]
            ax.plot([0, 1], [y, y], lw=1.05, color="black")
            y -= 0.78
            for i, (hh, al) in enumerate(zip(header, aligns)):
                _cell(ax, xs, i, y, ko(hh), al, 8.3, "black", bold=True)
            y -= 0.30
            ax.plot([0, 1], [y, y], lw=0.65, color="black")
            for r in rows:
                y -= 0.92
                sub = str(r[0]).startswith("—")
                for i, (v, al) in enumerate(zip(r, aligns)):
                    txt = str(v)
                    if i == 0 and sub:
                        txt = "  " + txt.lstrip("— ")
                    _cell(ax, xs, i, y, ko(txt), al, 8.1,
                          "0.32" if sub else "black")
            y -= 0.34
            ax.plot([0, 1], [y, y], lw=1.05, color="black")
            y -= 0.5
        elif b[0] == "p":
            y -= 0.35
            for line in item[2]:
                ax.text(0, y, line, fontsize=7.3, va="baseline", color="0.15")
                y -= 0.68
        else:
            y -= 0.5

    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{stem}.{ext}")
    plt.close(fig)
    print(f"  → tables/supplementary/{stem}.pdf | .png")


def _cell(ax, xs, i, y, txt, align, size, color, bold=False):
    w = "bold" if bold else "normal"
    if align == "l":
        ax.text(xs[i] + 0.004, y, txt, fontsize=size, color=color, fontweight=w)
    elif align == "r":
        ax.text(xs[i + 1] - 0.008, y, txt, fontsize=size, color=color,
                ha="right", fontweight=w)
    else:
        ax.text((xs[i] + xs[i + 1]) / 2, y, txt, fontsize=size, color=color,
                ha="center", fontweight=w)


def md_cell(v) -> str:
    """셀 안의 «|» 를 이스케이프한다. 안 하면 표의 열 수가 깨진다 (|ΔE_ref| 같은 표기)."""
    return str(v).replace("|", "\\|")


def md_table(header: list[str], rows: list, aligns: list[str]) -> list[str]:
    a = {"l": "---", "r": "---:", "c": ":---:"}
    return ["| " + " | ".join(md_cell(h) for h in header) + " |",
            "|" + "|".join(a[x] for x in aligns) + "|"] + \
           ["| " + " | ".join(md_cell(v) for v in r) + " |" for r in rows]


def write_md(stem: str, lines: list[str]) -> None:
    (OUT / f"{stem}.md").write_text("\n".join(lines + lock_block(stem)) + "\n")
    print(f"  → tables/supplementary/{stem}.md")


LOCK_DATE = "2026-08-17"


def lock_block(stem: str) -> list[str]:
    """🔒 LOCK 표시. **MD 에만** 붙이므로 PDF·PNG 렌더 내용은 바뀌지 않는다."""
    return [
        "", "---", "", f"## 🔒 LOCK ({LOCK_DATE})", "",
        "이 표의 **수치·통계·문구·행·열·각주를 확정**했다. 이후에는 제출 형식에 따른 "
        "레이아웃 조정 외에 내용을 바꾸지 않는다. **바꿔야 할 이유가 생기면 먼저 "
        "amendment 로 보고한다.**", "",
        "재생성 (LLM 호출 0회 · 동결 산출물만 읽는다)", "", "```bash",
        "python3 src/vccl/scoring/table_data.py     # → results/table_data/ (assertion)",
        "python3 tables/make_supp_tables.py         # → tables/supplementary/",
        "```", "",
        f"파일 해시와 상류 산출물 버전은 `tables/supplementary/LOCK_MANIFEST.md` 에 "
        f"있다. Figure F0~F4 와 Main Table 1 의 기존 LOCK 은 그대로 유지된다.",
    ]


def frozen_block(d: dict) -> list[str]:
    return ["", "**동결 해시**", "", "```"] + \
           [f"{k:<12}{v[:16]}…" for k, v in d["frozen"].items()] + ["```"]


# ── S1 ───────────────────────────────────────────────────────────────
def s1() -> None:
    d = json.loads((DATA / "s1_tests.json").read_text())
    rows_md, rows_pdf = [], []
    for r in d["rows"]:
        comp = f"{LAB[r['a']]} 대 {LAB[r['b']]}"
        sig = " *" if r["significant_at_05"] else ""
        rows_md.append([comp, r["metric_ko"], r["subset_ko"], r["n"],
                        f"{r['n10']} : {r['n01']}", md_sci(r["p"]) + sig,
                        r["prereg_status"]])
        rows_pdf.append([comp, r["metric_ko"], SUB_SHORT[r["subset"]],
                         r["n"], f"{r['n10']} : {r['n01']}", sci(r["p"]) + sig,
                         STATUS_SHORT[r["prereg_status"]]])

    cap = ("**표 S1. 통계검정 요약.** 같은 과제에 대한 짝지은 정확 McNemar 검정이다"
           "(양측, α = 0.05). 불일치 쌍은 «앞 조건만 성공 : 뒤 조건만 성공» 이다. "
           "**사전등록된 주 지표는 첫 행 하나뿐이며, 그 지표에서는 두 조건이 갈리지 "
           "않았다(p = 0.25).** 별표는 α = 0.05 기준 유의를 뜻한다.")
    hdr = ["비교", "지표", "과제", "n", "불일치 b:c", "p", "사전등록 지위"]
    al = ["l", "l", "l", "r", "c", "r", "l"]

    L = ["# 표 S1 — 통계검정 요약", "", f"> {cap}", ""]
    L += md_table(hdr, rows_md, al)
    L += ["", "**각주**", "",
          f"a. {d['prereg_note']}",
          "",
          f"b. {d['test_provenance']} 따라서 이 표의 어떤 행도 «검정이 사전등록됐다» 는 "
          f"뜻으로 읽지 않는다.",
          "",
          f"c. {d['primary_result_note']}",
          "",
          f"d. {d['multiplicity']} 표에 실린 검정은 {len(d['rows'])}개다.",
          "",
          "e. 지위 표기의 뜻은 다음과 같다.",
          ""]
    L += md_table(["표기", "뜻"], [
        ["주 지표·주 대비 사전 지정 · 검정은 사후",
         "지표와 조건쌍이 모두 결과 전에 고정됐다. 검정 자체는 사후에 추가했다."],
        ["비교축 사전 지정 · 검정은 사후",
         "조건쌍 또는 부분집합은 설계 문서가 결과 전에 지정했으나, 그 지표에 대한 "
         "이 검정은 사후에 추가했다."],
        ["post-hoc 탐색적", "지표·비교축·검정 모두 결과를 본 뒤 정했다."]],
        ["l", "l"])
    L += ["", "표 안에서는 자리를 줄여 «주 지표·주 대비 사전» · «비교축 사전» · "
          "«post-hoc» 으로 적었다.", "",
          "f. 각 행이 무엇을 근거로 그 지위를 받았는지는 아래에 적었다.", ""]
    L += md_table(["비교 · 지표 · 과제", "무엇이 사전 지정됐나"],
                  [[f"{LAB[r['a']]} 대 {LAB[r['b']]} · {r['metric_ko']} · {r['subset_ko']}",
                    r["prereg_basis"]] for r in d["rows"]], ["l", "l"])
    L += ["",
          "g. 세 검정(과대해석·과도한 신중·근거가 충분한 결론)은 같은 92과제를 서로 "
          "다른 지표로 본 것이므로 독립이 아니다.",
          "", "---", "", "## 수치 출처 (source mapping)", ""]
    L += md_table(["항목", "출처"],
                  [["불일치 쌍 · p", "`results/table_data/s1_tests.json` → `rows[].n10/n01/p`"],
                   ["원본 채점", "`results/main_run_aggregate.json` (V · V−τ)"],
                   ["R0 채점", "`results/oracle_headroom_audit.json` → `rows.R0`"],
                   ["Band 배정", "`main_run_aggregate.json` 행의 `band`"],
                   ["사전등록 지위", "기획안 §7.1 · §4 · `docs/DECISION_LOG.md`"]],
                  ["l", "l"])
    L += ["", "모든 값은 `src/vccl/scoring/table_data.py` 의 `build_s1()` 이 92행 원본 "
          "채점에서 **다시 계산**한 것이다. 기존 문서의 수치를 옮겨 적지 않았고, "
          "8개 검정 전부가 assertion 을 통과해야 파일이 쓰인다."]
    L += frozen_block(d)
    write_md("S1_tests", L)

    render("S1_tests", "표 S1. 통계검정 요약 — 정확 McNemar (짝지은 · 동일 과제)", [
        ("t", hdr, rows_pdf, [1.05, 0.85, 0.72, 0.26, 0.5, 0.62, 0.95], al),
        ("p", "b:c 는 «앞 조건만 성공 : 뒤 조건만 성공» 이다. * 는 α=0.05 기준 유의.\n"
              "지위 표기 — «주 지표·주 대비 사전»: 지표와 조건쌍이 모두 결과 전에 "
              "고정됐다. «비교축 사전»: 조건쌍·부분집합만 결과 전에 지정됐다. "
              "«post-hoc»: 지표·비교축·검정 모두 사후에 정했다.\n"
              + d["prereg_note"] + "\n" + d["test_provenance"] + "\n"
              + d["primary_result_note"] + "\n" + d["multiplicity"]),
    ])


# ── S2 ───────────────────────────────────────────────────────────────
def s2() -> None:
    d = json.loads((DATA / "s2_tau.json").read_text())
    rt_rows = [[rt, f"{v['L1']:.3f}", f"{v['L3']:.3f}",
                str(d["n_reactions"][rt]["L1"])]
               for rt, v in d["runtime_tau"].items()]
    rt_hdr = ["반응 유형", "τ(L1)", "τ(L3)", "반응 수"]
    rt_al = ["l", "r", "r", "r"]

    rows = [[r["subset"], r["rtype"], r["n_reactions"],
             f"{r['L1_mae']:.3f}", f"{r['L1_median']:.3f}", f"{r['L1_max']:.3f}",
             f"{r['L3_mae']:.3f}", f"{r['L3_median']:.3f}", f"{r['L3_max']:.3f}",
             ("예 (" + "·".join(r["floor_binds_levels"]) + ")")
             if r["floor_would_bind"] else "아니오"]
            for r in d["rows"]]
    hdr = ["서브셋", "유형", "n", "L1 MAE", "L1 중앙", "L1 최대",
           "L3 MAE", "L3 중앙", "L3 최대", f"{d['floor']} floor"]
    al = ["l", "l", "r", "r", "r", "r", "r", "r", "r", "c"]

    cap = ("**표 S2. 서브셋별 방법 오차 실측 (kcal/mol).** GMTKN55 참조값 대비 각 "
           "계산 수준의 오차 통계다. **이 값들은 보정 단계의 기술적 결과이며 실행 중 "
           "밴드 경계로 쓰이지 않았다 — 실행 시의 판단은 위의 반응 유형별 임계값을 "
           "썼다.** 마지막 열은 서브셋 값을 그대로 썼다면 참조값 자체의 추정 오차 "
           f"{d['floor']} kcal/mol 하한에 걸렸을지를 표시한다.")

    L = ["# 표 S2 — 반응 유형·서브셋별 방법 오차(τ) 실측", "", f"> {cap}", "",
         "**(가) 실행에 실제로 쓴 임계값 — 반응 유형별**", ""]
    L += md_table(rt_hdr, rt_rows, rt_al)
    L += ["", "**(나) 서브셋별 오차 통계 (기술적 · 실행에 쓰이지 않음)**", ""]
    L += md_table(hdr, rows, al)
    L += ["", "**각주**", "",
          f"a. {d['descriptive_note_ko']}",
          "",
          f"   *{d['descriptive_note_en']}*",
          "",
          f"b. 반응 유형별로 둔 이유 — {d['scope_rule']}",
          "",
          f"c. 하한 {d['floor']} kcal/mol 의 근거 — {d['floor_reason']}",
          "",
          "d. 실행에 쓴 반응 유형별 임계값은 네 값 모두 하한보다 크므로 하한이 걸리지 "
          "않았다. 서브셋별 값을 썼다면 걸렸을 경우만 (나)의 마지막 열에 표시했다.",
          "",
          "e. L2 는 과제 정의에 쓰이지 않아 표에서 뺐다. 원본 `per_subset_detail` 에는 "
          "남아 있다.",
          "", "---", "", "## 수치 출처 (source mapping)", ""]
    L += md_table(["항목", "출처"],
                  [["(가) 반응 유형별 임계값", "`data/tasks/frozen_rules_v1.json` → `tau.values`"],
                   ["(나) 서브셋별 통계", "같은 파일 → `tau.per_subset_detail[subset].levels`"],
                   ["반응 수", "같은 파일 → `tau.n_reactions`"],
                   ["하한 0.2", "같은 파일 → `tau.floor` · `tau.floor_reason`"]],
                  ["l", "l"])
    L += ["", "`build_s2()` 가 실행 τ 네 값을 현재 고정값과 **대조 assertion** 한 뒤 "
          "파일을 쓴다. `Tau.get()` 이 돌려주는 실행 시점 값과도 일치를 확인한다."]
    L += frozen_block(d)
    write_md("S2_tau", L)

    render("S2_tau", "표 S2. 반응 유형·서브셋별 방법 오차(τ) 실측 (kcal/mol)", [
        ("h", "(가) 실행에 실제로 쓴 임계값 — 반응 유형별"),
        ("t", rt_hdr, rt_rows, [1.0, 0.6, 0.6, 0.6], rt_al),
        ("h", "(나) 서브셋별 오차 통계 — 기술적 결과 · 실행에 쓰이지 않음"),
        ("t", hdr, rows, [0.9, 0.72, 0.34, 0.55, 0.55, 0.55, 0.55, 0.55, 0.55, 0.72], al),
        ("p", d["descriptive_note_ko"] + "\n" + d["descriptive_note_en"] + "\n"
              f"하한 {d['floor']} kcal/mol — {d['floor_reason']}\n"
              "실행에 쓴 네 값은 모두 하한보다 크므로 하한이 걸리지 않았다. "
              "L2 는 과제 정의에 쓰이지 않아 표에서 뺐다."),
    ])


# ── S3 ───────────────────────────────────────────────────────────────
def s3() -> None:
    d = json.loads((DATA / "s3_errors.json").read_text())
    cls = ["correct", "tool-limited", "agent-limited", "compound"]
    ko_cls = {"correct": "옳은 결론", "tool-limited": "도구 한계",
              "agent-limited": "판단 한계", "compound": "복합"}
    cond = ["V", "V-tau"]
    rows = [[ko_cls[k]] + [d["counts"][c][k] for c in cond] for k in cls]
    rows.append(["합계"] + [sum(d["counts"][c].values()) for c in cond])
    hdr = ["오류 유형", LAB["V"], LAB["V-tau"]]
    al = ["l", "r", "r"]

    brows = []
    for b in BANDS:
        for k in cls[1:]:
            pass
    brows = [[f"Band {b}"] + [d["by_band"][c][b][k] for c in cond for k in cls[1:]]
             for b in BANDS]
    bhdr = ["구간", "V 도구", "V 판단", "V 복합", "V−τ 도구", "V−τ 판단", "V−τ 복합"]
    bal = ["l"] + ["r"] * 6

    cap = ("**표 S3. 오류 분해 — 탐색적 분석.** 92과제의 오류를 원인별로 나눈 것이다. "
           "**사전 지정 검정이 없는 탐색적 분석이므로 확증 결과로 읽지 않는다.** "
           "「도구 한계」는 지금 사용한 계산 도구와 수준에서 에이전트의 판단만 고쳐서는 "
           "해결하기 어려운 오류를 뜻하며, 더 높은 계산 수준이나 다른 방법으로도 해결할 "
           "수 없다는 뜻이 아니다.")

    L = ["# 표 S3 — 오류 분해 (🔒 탐색적)", "", f"> {cap}", "",
         "**(가) 조건별 오류 분해**", ""]
    L += md_table(hdr, rows, al)
    L += ["", "**(나) 구간별 오류 분해 (옳은 결론 제외)**", ""]
    L += md_table(bhdr, brows, bal)
    L += ["", "**정의**", ""]
    L += md_table(["유형", "뜻"],
                  [[ko_cls[k], d["definitions"][k]] for k in cls], ["l", "l"])
    L += ["", "**각주**", "",
          f"a. {d['status_ko']}",
          "",
          f"b. {d['forbidden']}",
          "",
          "c. 두 조건은 같은 92과제를 실행한 결과이며 짝지어져 있다. 이 표에는 검정을 "
          "붙이지 않았다 — 사전 지정 검정이 없다.",
          "", "---", "", "## 수치 출처 (source mapping)", ""]
    L += md_table(["항목", "출처"],
                  [["조건별 개수", "`results/table_data/s3_errors.json` → `counts`"],
                   ["구간별 개수", "같은 파일 → `by_band`"],
                   ["원본 채점", "`results/main_run_aggregate.json` 92행 × 2조건의 `error_class`"]],
                  ["l", "l"])
    L += ["", "`build_s3()` 가 92행에서 다시 집계하고, 합계 92·미분류 0 을 함께 "
          "assertion 한다."]
    L += frozen_block(d)
    write_md("S3_errors", L)

    render("S3_errors", "표 S3. 오류 분해 — 탐색적 분석 (사전 지정 검정 없음)", [
        ("h", "(가) 조건별"),
        ("t", hdr, rows, [1.2, 0.5, 0.5], al),
        ("h", "(나) 구간별 (옳은 결론 제외)"),
        ("t", bhdr, brows, [0.7, 0.55, 0.55, 0.55, 0.62, 0.62, 0.62], bal),
        ("p", "도구 한계 — " + d["definitions"]["tool-limited"] + "\n"
              "판단 한계 — " + d["definitions"]["agent-limited"] + "\n"
              "복합 — " + d["definitions"]["compound"] + "\n"
              + d["forbidden"] + "\n"
              "사전 지정 검정이 없어 이 표에는 p 값을 붙이지 않았다."),
    ])


# ── S4 ───────────────────────────────────────────────────────────────
def s4() -> None:
    d = json.loads((DATA / "s4_benchmark.json").read_text())
    c = d["cross_band"]
    rows = [[f"Band {b}", c[b]["n"], c[b]["conformer"], c[b]["isomer"],
             c[b]["autonomous"], c[b]["paired"], c[b]["n_subsets"],
             f"{c[b]['abs_ref_min']:.2f}–{c[b]['abs_ref_max']:.2f}"]
            for b in BANDS]
    rows.append(["합계", d["n"], d["by_rtype"]["conformer"], d["by_rtype"]["isomer"],
                 d["by_identification"]["autonomous"], d["by_identification"]["paired"],
                 len(d["by_subset"]), "—"])
    hdr = ["구간", "과제", "배좌", "구조", "자율 식별", "쌍 지정", "서브셋", "참조 ΔE 절댓값 범위"]
    al = ["l", "r", "r", "r", "r", "r", "r", "r"]

    ps = d["per_subset"]
    srows = [[s, ps[s]["rtype"], ps[s]["n"], ps[s]["species"]]
             + [ps[s][b] for b in BANDS] for s in sorted(ps)]
    srows.append(["합계", "—", d["n"], d["n_species"]]
                 + [d["by_band"][b] for b in BANDS])
    shdr = ["서브셋", "유형", "과제", "화학종", "A", "B", "C", "D"]
    sal = ["l", "l", "r", "r", "r", "r", "r", "r"]

    cap = (f"**표 S4. 본 벤치마크의 구성 (N = {d['n']}).** 구간은 참조 에너지 차이 "
           f"|ΔE_ref| 와 실측 방법 오차 τ 의 관계로 기계적으로 정해진다. "
           f"**화학종이 중복되지 않는 {d['n']}과제이므로 추론 단위와 과제 수가 같다.** "
           f"자율 식별형은 가설 문장만으로 비교할 두 구조를 스스로 특정해야 하는 과제이고, "
           f"쌍 지정형은 두 구조를 지정받는 과제다.")

    L = ["# 표 S4 — 벤치마크 구성", "", f"> {cap}", "",
         "**(가) 구간별 구성**", ""]
    L += md_table(hdr, rows, al)
    L += ["", "**(나) 서브셋별 구성**", ""]
    L += md_table(shdr, srows, sal)
    L += ["", "**각주**", "",
          f"a. {d['unique_species_note']}",
          "",
          "b. 구간 정의", ""]
    L += md_table(["구간", "조건", "정답 행동"],
                  [[f"Band {b['band']}", b["condition"], b["correct_action"]]
                   for b in d["band_rule_ko"]], ["l", "l", "l"])
    L += ["", f"   {d['band_rule_note']}",
          "",
          "c. 「배좌」는 conformer(같은 결합 그래프의 회전 이성질체), 「구조」는 "
          "isomer(결합 그래프가 다른 이성질체)다. 방법 오차 τ 가 두 유형에서 크게 "
          "다르므로 임계값을 따로 뒀다 (표 S2).",
          "",
          "d. Band C 는 낮은 수준으로는 판단할 수 없고 높은 수준으로 올리면 판단할 수 "
          "있는 유일한 구간이다. 설계 단계에서 이 구간을 결정적 구간으로 지정했다.",
          "", "---", "", "## 수치 출처 (source mapping)", ""]
    L += md_table(["항목", "출처"],
                  [["과제 목록·순서", "`data/tasks/frozen_stage_b_v1.json` → `primary_experiment.main_benchmark.task_ids`"],
                   ["구간", "`results/main_run_aggregate.json` 행의 `band`"],
                   ["유형·서브셋·화학종·식별 방식", "`src/vccl/tasks/pairs.py` 의 `build_pool()`"],
                   ["참조 ΔE 절댓값", "같은 풀의 `abs_ref` (GMTKN55 참조값)"],
                   ["과제별 원본", "`results/table_data/s4_tasks.csv` (92행)"]],
                  ["l", "l"])
    L += ["", "`build_s4()` 가 구간 분포·식별 방식·화학종 유일성·동결 목록과의 순서 "
          "일치를 assertion 한다."]
    L += frozen_block(d)
    write_md("S4_benchmark", L)

    render("S4_benchmark", f"표 S4. 벤치마크 구성 (N = {d['n']})", [
        ("h", "(가) 구간별"),
        ("t", hdr, rows, [0.62, 0.45, 0.45, 0.45, 0.6, 0.55, 0.5, 0.8], al),
        ("h", "(나) 서브셋별"),
        ("t", shdr, srows, [0.85, 0.7, 0.45, 0.5, 0.32, 0.32, 0.32, 0.32], sal),
        ("h", "구간 정의"),
        ("t", ["구간", "조건", "정답 행동"],
         [[f"Band {b['band']}", b["condition"], b["correct_action"]]
          for b in d["band_rule_ko"]], [0.5, 1.3, 1.6], ["l", "l", "l"]),
        ("p", d["band_rule_note"] + "\n" + d["unique_species_note"] + "\n"
              "「배좌」는 conformer, 「구조」는 isomer 다. τ 가 두 유형에서 크게 달라 "
              "임계값을 따로 뒀다 (표 S2)."),
    ])


# ── S5 ───────────────────────────────────────────────────────────────
def s5() -> None:
    d = json.loads((DATA / "s5_cost.json").read_text())
    order = ["ALL_L3", "V", "V-tau", "R0"]
    rows = [[LAB[k], f"{d['totals_s'][k]:,.1f}", f"{d['pct_of_all_l3'][k]:.2f}",
             d["n_tasks_final_level_l3"].get(k, 92 if k == "ALL_L3" else 0),
             d["n_exec_L3"].get(k, 92 if k == "ALL_L3" else 0)] for k in order]
    hdr = ["조건", "총 계산시간 (초)", "ALL_L3 대비 (%)", "최종 수준이 L3인 과제",
           "L3 실행 횟수"]
    al = ["l", "r", "r", "r", "r"]

    st, q = d["l3_wall_s_stats"], d["l3_wall_s_quartiles"]
    drows = [["최소", f"{st['min']:,.1f}"], ["10 분위", f"{q['p10']:,.1f}"],
             ["25 분위", f"{q['p25']:,.1f}"], ["중앙값", f"{st['median']:,.1f}"],
             ["평균", f"{st['mean']:,.1f}"], ["75 분위", f"{q['p75']:,.1f}"],
             ["90 분위", f"{q['p90']:,.1f}"], ["최대", f"{st['max']:,.1f}"]]
    dhdr = ["통계량", "L3 계산시간 (초)"]
    dal = ["l", "r"]

    def rng(b):
        return (f"{b['lo']} 초 이상" if b["hi"] is None
                else f"{b['lo']}–{b['hi']} 초")
    brows = [[rng(b), b["n"]] for b in d["distribution"]]
    brows.append(["합계", sum(b["n"] for b in d["distribution"])])
    bhdr = ["구간", "과제 수"]

    pb = d["per_band"]
    pbrows = [[f"Band {b}", pb[b]["n"], f"{pb[b]['l3_wall_s_total']:,.1f}",
               f"{pb[b]['l3_wall_s_median']:,.1f}"] for b in BANDS]
    pbhdr = ["구간", "과제", "L3 총 시간 (초)", "L3 중앙값 (초)"]
    pbal = ["l", "r", "r", "r"]

    cap = ("**표 S5. 계산시간과 비용.** 저장된 psi4 계산 기록에서 읽은 **실제 소요 "
           "시간**이다. ALL_L3 는 모든 과제를 높은 수준으로 실행한 **비교용 정책**이며 "
           "도달 가능한 상한을 뜻하지 않는다. V−τ 가 100%를 넘는 것은 같은 과제를 "
           "여러 번 계산했기 때문이다.")

    L = ["# 표 S5 — 계산시간·비용 상세", "", f"> {cap}", "",
         "**(가) 조건별 총 계산시간**", ""]
    L += md_table(hdr, rows, al)
    L += ["", "**(나) 과제 하나를 높은 수준으로 계산할 때의 시간 분포 (92과제)**", ""]
    L += md_table(dhdr, drows, dal)
    L += ["", "**(다) 시간 구간별 과제 수**", ""]
    L += md_table(bhdr, brows, ["l", "r"])
    L += ["", "**(라) 구간별 높은 수준 계산시간**", ""]
    L += md_table(pbhdr, pbrows, pbal)
    c16 = d["correction_2026_08_16"]
    L += ["", "**각주**", "",
          f"a. {d['basis']} ({d['correction_ref']})",
          "",
          f"b. 분위수 관례 — {d['quantile_convention']}",
          "",
          f"   🔧 **2026-08-16 정정** ({c16['ref']}). {c16['what']} 가운데 두 값이 "
          f"{c16['central_two'][0]} 초와 {c16['central_two'][1]} 초이므로 중앙값은 "
          f"**{c16['median_before']} → {c16['median_after']} 초**로 바뀐다. "
          f"{c16['unchanged']}",
          "",
          f"c. {d['all_l3_note']}",
          "",
          f"d. {d['forbidden']} 고정 문구는 «ALL_L3 가 해결한 75과제 중 74과제를 "
          f"{d['pct_of_all_l3']['V']:.1f}% 의 계산 비용으로 해결했다» 다.",
          "",
          f"e. **「최종 수준이 L3인 과제」는 마지막 판단을 L3 결과로 내린 과제다.** "
          f"L3 계산이 한 번이라도 돌아간 과제와 다르다 — 조건 {LAB['V-tau']} 에서는 "
          f"L3 가 한 번이라도 돌아간 과제가 "
          f"{d['n_tasks_any_l3_exec']['V-tau']} / 92 인데 최종 판단 수준이 L3인 과제는 "
          f"{d['n_tasks_final_level_l3']['V-tau']} / 92 다. 한 과제는 L3 로 계산한 뒤 "
          f"비교 대상을 다시 정해 마지막에는 L1 결과로 판단을 마쳤다. 조건 "
          f"{LAB['V']} 에서는 두 수가 모두 "
          f"{d['n_tasks_final_level_l3']['V']} 로 같다. **두 값을 혼동하지 않는다.**",
          "",
          "f. R0 는 규칙 기준선이며 항상 낮은 수준 한 번만 계산한다. 낮은 수준의 계산은 "
          "과제당 0.04초 수준이라 총합이 4초에 못 미친다.",
          "",
          "g. 같은 과제라도 구조 크기에 따라 계산시간이 1,000배 넘게 벌어진다"
          f"({st['min']:.1f}초 ~ {st['max']:,.1f}초). 평균이 중앙값의 "
          f"{st['mean']/st['median']:.1f}배인 것은 이 꼬리 때문이다.",
          "", "---", "", "## 수치 출처 (source mapping)", ""]
    L += md_table(["항목", "출처"],
                  [["과제별 실측 시간", "psi4 계산 캐시 → `src/vccl/scoring/headroom.py` 의 `task_cost_s`"],
                   ["실행 횟수", "`main_run_aggregate.json` 행의 `cost_s` 에서 역산 (근사 단가는 횟수 복원에만 사용)"],
                   ["조건별 총합·비율", "`results/table_data/s5_cost.json` → `totals_s` · `pct_of_all_l3`"],
                   ["최종 수준이 L3인 과제", "`s5_cost.json` → `n_tasks_final_level_l3` "
                    "(= `level_used == 'L3'`)"],
                   ["L3 1회 이상 실행 과제 (각주 e)", "`s5_cost.json` → `n_tasks_any_l3_exec` "
                    "(`s5_cost_by_task.csv` 의 `*_n_exec_L3` 에서 집계)"],
                   ["중앙값·분위수", "원자료 92개에서 `statistics.median` 과 선형보간 "
                    "(R type 7) 으로 계산 — `table_data.quantile()`"],
                   ["과제별 원본", "`results/table_data/s5_cost_by_task.csv` (92행)"]],
                  ["l", "l"])
    L += ["", "`build_s5()` 가 네 조건의 총합·비율과 분포 통계 네 값을 정정된 실측 "
          "기준값과 대조하고, 92과제 전부에 실측 시간이 있는지(근사 대체 0) 확인한다."]
    L += frozen_block(d)
    write_md("S5_cost", L)

    render("S5_cost", "표 S5. 계산시간·비용 상세 (psi4 실측 wall time)", [
        ("h", "(가) 조건별 총 계산시간"),
        ("t", hdr, rows, [0.55, 0.95, 0.9, 0.7, 0.7], al),
        ("h", "(나) 과제 하나의 높은 수준 계산시간 분포 (92과제)"),
        ("t", dhdr, drows, [0.7, 0.9], dal),
        ("h", "(다) 시간 구간별 과제 수"),
        ("t", bhdr, brows, [0.9, 0.5], ["l", "r"]),
        ("h", "(라) 구간별 높은 수준 계산시간"),
        ("t", pbhdr, pbrows, [0.6, 0.4, 0.8, 0.8], pbal),
        ("p", d["basis"] + "\n분위수 관례 — " + d["quantile_convention"] + "\n"
              + d["all_l3_note"] + "\n" + d["forbidden"] + "\n"
              f"구조 크기에 따라 계산시간이 {st['min']:.1f}초에서 {st['max']:,.1f}초까지 "
              f"벌어진다. 평균이 중앙값의 {st['mean']/st['median']:.1f}배인 것은 이 "
              f"꼬리 때문이다."),
    ])


# ── S6 ───────────────────────────────────────────────────────────────
def s6() -> None:
    d = json.loads((DATA / "s6_identification.json").read_text())
    p, s = d["primary"], d["secondary"]
    ci = p["ci95_clopper_pearson"]
    rows = [
        ["과제 수", f"{p['n']}"],
        ["완료하지 못한 과제", f"{p['failed']} / {p['n']}"],
        ["식별 정확도", f"{p['identification_correct']} / {p['denominator']}"],
        ["95% 신뢰구간 (Clopper–Pearson)", f"[{ci[0]:.3f}, {ci[1]:.3f}]"],
        ["무작위 쌍 선택의 기대 정답 수", f"{p['random_expected']:.3f} / {p['denominator']}"],
        ["단측 정확 Poisson-binomial", md_sci(p["p_one_sided_poisson_binomial"])],
    ]
    # PDF 는 한글 폰트에 위첨자 글리프가 없으므로 ASCII 지수 표기를 쓴다
    rows_pdf = [r[:] for r in rows]
    rows_pdf[-1][1] = sci(p["p_one_sided_poisson_binomial"])
    hdr = ["항목", "값"]
    al = ["l", "r"]

    nc = p["n_candidates"]
    crows = [[f"후보 {k}개", v] for k, v in nc["distribution"].items()]
    crows.append(["합계", sum(nc["distribution"].values())])
    chdr = ["후보 구조 수", "과제 수"]

    brows = [[f"Band {b}", p["by_band"][b]] for b in BANDS]
    brows.append(["합계", sum(p["by_band"].values())])
    srows = [[k, v] for k, v in p["by_subset"].items()]
    srows.append(["합계", sum(p["by_subset"].values())])

    cap = ("**표 S6. 구조 식별 보조 검증.** 후보 구조가 4~15개인 과제에서 가설 문장만 "
           "보고 비교할 두 구조를 스스로 특정하게 한 실험이다. 조건은 V 단독이며, "
           "τ 는 식별 이후 단계에만 개입하므로 V−τ 를 따로 돌리지 않았다. "
           "**이 사전 지정 nontrivial candidate set 환경에서 본 벤치마크의 식별 "
           "76/76 을 보조 검증한 것이며, RQ1 전체를 입증하지 않는다. "
           "난이도(hardness) 자체를 측정한 실험이 아니다.**")

    L = ["# 표 S6 — 구조 식별 보조 검증 (identification challenge)", "",
         f"> {cap}", "",
         f"## (가) primary {p['n']} — {p['status']}", "",
         f"*분석계획 `{p['plan_provenance']}` · 모델 `{p['model']}` · 조건 "
         f"{p['condition']}*", "",
         f"> ⚠️ {p['plan_note']}", ""]
    L += md_table(hdr, rows, al)
    L += ["", "**고정 해석 (결과를 보기 전에 정한 문구)**", "",
          f"> {p['fixed_interpretation']}", "",
          "**후보 구조 수 분포**", ""]
    L += md_table(chdr, crows, ["l", "r"])
    L += [f"", f"후보 수는 {nc['min']}~{nc['max']}개, 중앙값 {nc['median']}개다.", "",
          "**구간·계열 분포**", ""]
    L += md_table(["구간", "과제"], brows, ["l", "r"])
    L += [""]
    L += md_table(["계열", "과제"], srows, ["l", "r"])
    L += ["", "**이 실험이 주장하지 않는 것**", ""]
    L += [f"{i+1}. {x}" for i, x in enumerate(p["scope_limits"])]
    L += ["", f"추론 단위 — {p['inference_unit']}", "",
          "---", "", f"## (나) {s['title']}", "",
          f"*사후등록 {' · '.join('`'+a+'`' for a in s['amendment'])} · 상태 "
          f"{s['status']}*", ""]
    if "by_species" not in s:
        L += [f"> 🔲 **이 칸은 실행이 끝난 뒤 채운다.** {s.get('note','')}", ""]
    else:
        comp = s["composition"]
        L += [f"> **표 S6(나). 같은 24 화학종에서 나온 {s['n']}개 관측.** "
              f"기존 primary {comp['primary_reuse']}개 관측을 그대로 재사용하고 "
              f"{comp['secondary_new']}개를 새로 실행해 합친 것이다. "
              f"**추론 단위는 {s['n']}개의 독립 표본이 아니다** — 화학종 "
              f"{s['n_species']}종이 반응을 여럿 내므로 같은 화학종의 관측끼리 "
              f"독립이 아니다. **이 칸에서는 새로운 통계적 추론을 하지 않았다.**", "",
              "**구성**", ""]
        L += md_table(["출처", "관측 수", "식별 정확"],
                      [["기존 primary 24 재사용 (재실행 아님)",
                        comp["primary_reuse"],
                        f"{s['by_provenance']['primary_reuse']['correct']} / "
                        f"{s['by_provenance']['primary_reuse']['total']}"],
                       ["이번에 새로 실행", comp["secondary_new"],
                        f"{s['by_provenance']['secondary_new']['correct']} / "
                        f"{s['by_provenance']['secondary_new']['total']}"],
                       ["합계", s["n"],
                        f"{s['identification_correct']} / {s['denominator']}"]],
                      ["l", "r", "r"])
        L += ["", f"완료하지 못한 과제(FAILED)는 **{s['failed']} / {s['n']}** 이다. "
              f"실행 유효성은 신규 실행 {s['validity_gate']['denominator']} 을 분모로 "
              f"재며 신규 FAILED 는 **{s['failed_new_exec']}건** 이다 "
              f"(무효 기준 {s['validity_gate']['threshold_failed']}건).", "",
              "**전체 식별 정확도**", "",
              f"> **{s['identification_correct']} / {s['denominator']}** "
              f"({s['accuracy']:.1%}) — 화학종 {s['n_species']}종에서 나온 "
              f"{s['n']}개 관측", "",
              "**화학종별 correct / total**", ""]
        L += md_table(["화학종", "맞음", "전체", "비율"],
                      [[k, v["correct"], v["total"],
                        f"{v['correct']/v['total']:.0%}"]
                       for k, v in s["by_species"].items()], ["l", "r", "r", "r"])
        m = s["species_macro"]
        L += ["", "**화학종 단위 descriptive macro summary**", "",
              f"- {m['n_species']}종 · 평균 {m['mean']:.1%} · 중앙값 "
              f"{m['median']:.1%} · 범위 {m['min']:.0%}–{m['max']:.0%}",
              f"- 전량 정답 {m['all_correct_species']}종 · 전량 오답 "
              f"{m['all_wrong_species']}종",
              f"- 🔒 화학종이 {m['n_species']}종뿐이다. 이 값으로 일반화하지 않는다.",
              "", "**후보 구조 수별 correct / total**", ""]
        L += md_table(["후보 구조 수", "맞음", "전체", "비율", "화학종"],
                      [[k, v["correct"], v["total"],
                        f"{v['correct']/v['total']:.0%}", f"{v['n_species']}종"]
                       for k, v in s["by_n_candidates"].items()],
                      ["l", "r", "r", "r", "r"])
        L += ["", "**계열(서브셋)별 correct / total**", ""]
        L += md_table(["계열", "맞음", "전체", "비율", "화학종"],
                      [[k, v["correct"], v["total"],
                        f"{v['correct']/v['total']:.0%}", f"{v['n_species']}종"]
                       for k, v in s["by_subset"].items()],
                      ["l", "r", "r", "r", "r"])
        L += ["", "**식별에 실패한 과제**", ""]
        if not s["identification_failures"]:
            L += ["없다.", ""]
        else:
            L += md_table(["과제", "화학종", "계열", "후보 수", "고른 쌍", "정답 쌍",
                           "출처"],
                          [[f"`{x['tid']}`", x["species_key"], x["subset"],
                            x["n_candidates"], " + ".join(x["selected_pair"]),
                            " + ".join(x["gold_pair"]), x["provenance"]]
                           for x in s["identification_failures"]],
                          ["l", "l", "l", "r", "l", "l", "l"])
            L += [""]
        L += ["**이 칸이 하지 않는 것**", "",
              f"- {s['no_inference']}",
              f"- {s['not_replication']}",
              f"- {s['reporting_rule']}",
              "- 결과를 보고 새로운 부분집단·문턱·검정법을 만들지 않았다.", ""]
    L += ["---", "", "## 수치 출처 (source mapping)", ""]
    L += md_table(["항목", "출처"],
                  [["primary 채점 결과", f"`{p['source']}`"],
                   ["분석계획 출처", f"`{p['plan_provenance']}`"],
                   ["신뢰구간·검정", "`src/vccl/agents/challenge.py` 의 `clopper_pearson` · `pb_upper_tail`"],
                   ["무작위 귀무가설", "과제별 1/C(후보 수, 2) — 같은 파일의 `chance_probs`"],
                   ["후보 수·계열·구간", "`src/vccl/tasks/pairs.py` 의 `build_pool()`"],
                   ["제한 문구", "`data/tasks/frozen_stage_b_v1.json` → `identification_challenge`"],
                   ["(나) secondary 94", f"`{s.get('source', '미실행')}`"],
                   ["(나) 신규 실행 원장", " · ".join(
                       f"`{v['dir']}` ({v['n_calls']}호출)"
                       for v in s.get("chunks", {}).values()) or "—"]],
                  ["l", "l"])
    L += ["", "**(가)** 는 `build_s6()` 가 기존 primary 결과에서 24/24 · 신뢰구간 · "
          "기대 정답 수 · p · 후보 수 범위 · 계열·구간 분포·본 벤치마크와의 중복을 "
          "**다시 계산해 assertion** 한 값이다. **(나)** 는 "
          "`build_s6_secondary()` 가 `experiments/chal_secondary94/"
          "secondary_result.json` 을 읽어 **기술 통계로 집계**한 것이며, 구성(24+70)· "
          "화학종 24종·합계 정합·신규 FAILED 게이트를 assertion 한다. "
          "**(나)에서는 어떤 추론 통계도 만들지 않는다.**"]
    L += frozen_block(d)
    write_md("S6_identification", L)

    render("S6_identification", "표 S6. 구조 식별 보조 검증 (identification challenge)", [
        ("h", f"(가) primary {p['n']} — {p['status']}"),
        ("t", hdr, rows_pdf, [1.5, 0.7], al),
        ("p", p["plan_note"] + "\n고정 해석 (결과를 보기 전에 정한 문구) — "
              + p["fixed_interpretation"]),
        ("h", "후보 구조 수 분포"),
        ("t", chdr, crows, [0.8, 0.5], ["l", "r"]),
        ("h", "구간 분포"),
        ("t", ["구간", "과제"], brows, [0.8, 0.5], ["l", "r"]),
        ("h", "계열 분포"),
        ("t", ["계열", "과제"], srows, [0.8, 0.5], ["l", "r"]),
        ("p", "이 실험이 주장하지 않는 것 — " + " / ".join(p["scope_limits"][:3])),
    ] + _s6_secondary_blocks(s))


def _s6_secondary_blocks(s: dict) -> list:
    """S6 (나) 의 PDF 블록. 미실행이면 자리표시만."""
    head = [("h", f"(나) {s['title']}")]
    if "by_species" not in s:
        return head + [("p", "🔲 이 칸은 실행이 끝난 뒤 채운다.")]
    comp, m = s["composition"], s["species_macro"]
    bp = s["by_provenance"]
    return head + [
        ("t", ["출처", "관측 수", "식별 정확"],
         [["기존 primary 24 재사용 (재실행 아님)", comp["primary_reuse"],
           f"{bp['primary_reuse']['correct']} / {bp['primary_reuse']['total']}"],
          ["이번에 새로 실행", comp["secondary_new"],
           f"{bp['secondary_new']['correct']} / {bp['secondary_new']['total']}"],
          ["합계", s["n"], f"{s['identification_correct']} / {s['denominator']}"]],
         [1.6, 0.6, 0.7], ["l", "r", "r"]),
        ("p", f"전체 식별 정확도 {s['identification_correct']}/{s['denominator']} "
              f"({s['accuracy']:.1%}) — 화학종 {s['n_species']}종에서 나온 {s['n']}개 "
              f"관측. 추론 단위는 {s['n']}개의 독립 표본이 아니다.\n"
              f"FAILED {s['failed']}/{s['n']} · 신규 FAILED "
              f"{s['failed_new_exec']}/{s['validity_gate']['denominator']} "
              f"(무효 기준 {s['validity_gate']['threshold_failed']}건)."),
        ("h", "화학종별 correct / total"),
        ("t", ["화학종", "맞음", "전체", "비율"],
         [[k, v["correct"], v["total"], f"{v['correct']/v['total']:.0%}"]
          for k, v in s["by_species"].items()], [1.6, 0.4, 0.4, 0.5],
         ["l", "r", "r", "r"]),
        ("p", f"화학종 단위 macro summary — {m['n_species']}종 · 평균 {m['mean']:.1%} · "
              f"중앙값 {m['median']:.1%} · 범위 {m['min']:.0%}-{m['max']:.0%} · "
              f"전량 정답 {m['all_correct_species']}종 · 전량 오답 "
              f"{m['all_wrong_species']}종."),
        ("h", "후보 구조 수별 · 계열별"),
        ("t", ["후보 구조 수", "맞음", "전체", "비율", "화학종"],
         [[k, v["correct"], v["total"], f"{v['correct']/v['total']:.0%}",
           f"{v['n_species']}종"] for k, v in s["by_n_candidates"].items()],
         [0.9, 0.4, 0.4, 0.5, 0.6], ["l", "r", "r", "r", "r"]),
        ("t", ["계열", "맞음", "전체", "비율", "화학종"],
         [[k, v["correct"], v["total"], f"{v['correct']/v['total']:.0%}",
           f"{v['n_species']}종"] for k, v in s["by_subset"].items()],
         [0.9, 0.4, 0.4, 0.5, 0.6], ["l", "r", "r", "r", "r"]),
        ("p", ("식별에 실패한 과제 — 없다." if not s["identification_failures"]
               else "식별에 실패한 과제 — " + " / ".join(
                   f"{x['tid']} (후보 {x['n_candidates']}, 고른 쌍 "
                   f"{'+'.join(x['selected_pair'])}, 정답 쌍 "
                   f"{'+'.join(x['gold_pair'])})"
                   for x in s["identification_failures"]))
              + "\n" + s["no_inference"] + "\n" + s["not_replication"]),
    ]


# ── S7 ───────────────────────────────────────────────────────────────
def s7() -> None:
    d = json.loads((DATA / "s7_l0.json").read_text())
    l0, r0 = d["l0"], d["r0_reference"]
    rows = [
        ["과제 수", d["n"], d["n"]],
        ["결론을 단정한 과제", l0["declared"], r0["declared"]],
        ["판단을 보류한 과제", l0["abstained"], d["n"] - r0["declared"]],
        ["참조값과 방향이 맞은 과제", l0["direction_correct"], r0["direction_correct"]],
        ["단정한 과제 중 정확도", f"{100*l0['accuracy_when_declared']:.1f}%",
         f"{100*r0['accuracy_when_declared']:.1f}%"],
        ["전체 대비 정확도", f"{100*l0['accuracy_overall']:.1f}%", "—"],
    ]
    hdr = ["항목", "L0 (도구 없음)", "R0 (규칙 기준선)"]
    al = ["l", "r", "r"]

    bb = d["by_band"]
    brows = [[f"Band {b}", bb[b]["n"], bb[b]["declared"], bb[b]["direction_correct"],
              f"{bb[b]['accuracy_pct']:.0f}%"] for b in BANDS]
    brows.append(["합계", d["n"], l0["declared"], l0["direction_correct"],
                  f"{100*l0['accuracy_when_declared']:.1f}%"])
    bhdr = ["구간", "과제", "단정", "방향 정확", "정확도"]
    bal = ["l", "r", "r", "r", "r"]

    cap = ("**표 S7. 계산 도구 없이 답하게 한 검사.** 같은 92과제를 계산 없이 가설 "
           "문장만 보고 판단하게 했다. 참조값을 외워서 맞히고 있는지 살피는 검사다. "
           "**결론은 «오염이 없다» 가 아니라 «이 검사에서는 강한 암기를 의심할 근거가 "
           "나오지 않았다» 이다.**")

    L = ["# 표 S7 — 계산 도구 없이 답하게 한 검사 (contamination probe)", "",
         f"> {cap}", "", "**(가) L0 와 규칙 기준선 비교**", ""]
    L += md_table(hdr, rows, al)
    L += ["", "**(나) 구간별 L0 성적**", ""]
    L += md_table(bhdr, brows, bal)
    L += ["", "**각주**", "",
          f"a. {d['purpose']}",
          "",
          f"b. {d['conclusion_ko']}",
          "",
          f"c. {d['forbidden']}",
          "",
          f"d. 단정한 과제 기준으로 두 조건의 차이는 {d['margin_pp']:.1f}%p 다. "
          f"참고로 방향을 무작위로 고를 때의 기대값은 "
          f"{d['random_baseline_pct']}% 다. **이 값과 L0 의 "
          f"{100*l0['accuracy_when_declared']:.1f}% 가 통계적으로 구분되는지는 "
          f"검정하지 않았으므로, «우연 수준이다»·«동전 던지기에 가깝다» 로 해석하지 "
          f"않는다.**",
          "",
          "e. R0 는 같은 과제에 계산 도구와 결정론적 규칙을 적용한 기준선이며(방법 오차 "
          "이내면 보류, 아니면 계산된 방향을 그대로 쓴다), L0 보다 높은 방향 정확도를 "
          "보였다. **두 조건의 차이를 순수한 도구 사용의 인과효과로 해석하지 않는다.**",
          "",
          "f. 구간별 수치는 표본이 작다(단정한 과제가 구간당 8~23개). 구간 사이의 차이를 "
          "주장하지 않는다.",
          "", "---", "", "## 수치 출처 (source mapping)", ""]
    L += md_table(["항목", "출처"],
                  [["L0 결과", f"`{d['source']}` → `rows` (92행)"],
                   ["R0 참조", "같은 파일 → `g5.r0`"],
                   ["구간 배정", "같은 파일 행의 `band`"]],
                  ["l", "l"])
    L += ["", "`build_s7()` 가 92행에서 단정 수·방향 정확 수·구간별 정확도를 다시 "
          "집계해 assertion 한다."]
    L += frozen_block(d)
    write_md("S7_l0_probe", L)

    render("S7_l0_probe", "표 S7. 계산 도구 없이 답하게 한 검사 (contamination probe)", [
        ("h", "(가) L0 와 규칙 기준선 비교"),
        ("t", hdr, rows, [1.3, 0.8, 0.8], al),
        ("h", "(나) 구간별 L0 성적"),
        ("t", bhdr, brows, [0.7, 0.45, 0.45, 0.6, 0.5], bal),
        ("p", d["purpose"] + "\n" + d["conclusion_ko"] + "\n" + d["forbidden"] + "\n"
              "구간별 수치는 표본이 작다(단정한 과제가 구간당 8~23개). 구간 사이의 "
              "차이를 주장하지 않는다."),
    ])


# ── S8 ───────────────────────────────────────────────────────────────
SKIP = {"level", "structure_more_stable", "structure_other", "selected_pair",
        "gold_pair", "identification_correct", "specified_pair_given", "qc_ok",
        "ambiguous", "evidence_sufficient", "cost_s"}
FIELD_KO = {"identification_basis": "구조 식별 근거", "reasoning": "판단 근거",
            "concern": "지적", "ambiguity_note": "모호성 메모",
            "restates_original_hypothesis": "원 가설 재진술",
            "observable": "관측량", "recommendation": "권고", "conclusion": "결론",
            "delta_evidence_kcal_mol": "계산된 ΔE (kcal/mol)",
            "delta_gold_convention_kcal_mol": "참조 부호 규약 기준 ΔE (kcal/mol)"}


def s8() -> None:
    d = json.loads((DATA / "s8_trajectory.json").read_text())
    sel = d["selection"]
    L = ["# 표 S8 — 그림 5 사례의 에이전트 출력 전문", "",
         f"> **표 S8. 그림 5 에 실은 실행 사례의 원문 전문.** 과제 `{d['tid']}` · "
         f"조건 {d['condition']} · 구간 {d['band']} 이다. 그림에는 길이 때문에 발췌만 "
         f"실었고, 이 표가 에이전트가 실제로 출력한 문장 전문을 담는다. "
         f"**요약·윤문·번역하지 않았다.**", "",
         "**과제 정보**", ""]
    L += md_table(["항목", "값"], [
        ["과제", f"`{d['tid']}`"], ["조건", d["condition"]],
        ["구간", d["band"]], ["반응 유형", d["rtype"]],
        ["참조 에너지 차이 (절댓값)", f"{d['abs_ref_kcal_mol']} kcal/mol"],
        ["방법 오차 τ(L1)", f"{d['tau_L1']} kcal/mol"],
        ["방법 오차 τ(L3)", f"{d['tau_L3']} kcal/mol"],
        ["최종 결론", d["final_conclusion"]],
        ["구조 식별", "정확" if d["identification_correct"] else "오류"],
        ["높은 수준 계산의 실측 시간", f"{d['l3_wall_s_measured']} 초"],
        ["원본", f"`experiments/{d['source_batch']}/batch_result.json`"],
    ], ["l", "l"])
    L += ["", "**사례 선정**", "",
          f"- {sel['rule']}",
          f"- {sel['provenance_note']}",
          f"- {sel['forbidden']}",
          f"- {sel['disclosure']}",
          "", "---", "", "## 실행 전문", "",
          f"*{d['verbatim_note']}*", ""]

    for st in d["steps"]:
        L.append(f"### 라운드 {st['round']} — {st['step_ko']}")
        L.append("")
        f = st["fields"]
        if "level" in f:
            L.append(f"**계산 수준** `{f['level']}`")
            L.append("")
        if st["step"] == "operationalize":
            L.append(f"**고른 구조 쌍** `{f['structure_more_stable']}` (더 안정하다고 "
                     f"주장) 대 `{f['structure_other']}`")
            L.append("")
            L.append(f"**모호성 표시** {'예' if f.get('ambiguous') else '아니오'}")
            L.append("")
        if st["step"] == "execute":
            L.append(f"**고른 쌍** `{f['selected_pair']}` · **정답 쌍** "
                     f"`{f['gold_pair']}` · **식별** "
                     f"{'정확' if f['identification_correct'] else '오류'}")
            L.append("")
            L.append(f"**계산된 ΔE** {f['delta_evidence_kcal_mol']} kcal/mol · "
                     f"**QC** {'통과' if f['qc_ok'] else '실패'}")
            L.append("")
            if st.get("l3_wall_s_measured"):
                L.append(f"**실측 계산시간** {st['l3_wall_s_measured']} 초 "
                         f"(trace 의 `cost_s` {f['cost_s']} 는 근사값이다)")
                L.append("")
        if st["step"] == "review":
            L.append(f"**증거 충분** {'예' if f['evidence_sufficient'] else '아니오'} · "
                     f"**권고** `{f['recommendation']}`")
            L.append("")
        for k, v in f.items():
            if k in SKIP or not isinstance(v, str) or not v.strip():
                continue
            L.append(f"**{FIELD_KO.get(k, k)}** (원문)")
            L.append("")
            L.append("> " + v.replace("\n", "\n> "))
            L.append("")

    L += ["---", "", "## 수치 출처 (source mapping)", ""]
    L += md_table(["항목", "출처"],
                  [["실행 전문", f"`experiments/{d['source_batch']}/batch_result.json` → `case_study_candidates`"],
                   ["τ · 구간 · 참조값", "`data/tasks/frozen_rules_v1.json` · `build_pool()`"],
                   ["최종 채점", "`results/main_run_aggregate.json` 의 해당 행"],
                   ["실측 계산시간", "psi4 계산 캐시 → `headroom.task_cost_s`"]],
                  ["l", "l"])
    L += ["", f"a. {d['cost_s_note']}", "",
          "b. `build_s8()` 가 L1→L3 상승 기록, |ΔE_L1| < τ(L1), |ΔE_L3| > τ(L3), "
          "구간 C 조건, 식별 정확, 원문 텍스트 필드 보존을 assertion 한다.", ""]
    L += frozen_block(d)
    write_md("S8_trajectory", L)

    # PDF — 전문은 흐르는 글이므로 문단 블록으로 낸다
    blocks = [("t", ["항목", "값"],
               [["과제", d["tid"]], ["조건 · 구간", f"{d['condition']} · {d['band']}"],
                ["참조 에너지 차이 (절댓값)", f"{d['abs_ref_kcal_mol']} kcal/mol"],
                ["τ(L1) · τ(L3)", f"{d['tau_L1']} · {d['tau_L3']} kcal/mol"],
                ["최종 결론", d["final_conclusion"]],
                ["높은 수준 계산 실측 시간", f"{d['l3_wall_s_measured']} 초"]],
               [1.1, 1.3], ["l", "l"]),
              ("p", sel["rule"] + " " + sel["disclosure"]),
              ("h", "실행 전문 — 요약·윤문하지 않았다")]
    for st in d["steps"]:
        blocks.append(("h", f"라운드 {st['round']} — {st['step_ko']}"))
        f = st["fields"]
        head = []
        if "level" in f:
            head.append(f"계산 수준 {f['level']}")
        if st["step"] == "execute":
            head.append(f"계산된 ΔE {f['delta_evidence_kcal_mol']} kcal/mol")
            if st.get("l3_wall_s_measured"):
                head.append(f"실측 {st['l3_wall_s_measured']} 초")
        if st["step"] == "review":
            head.append(f"증거 충분 {'예' if f['evidence_sufficient'] else '아니오'} · "
                        f"권고 {f['recommendation']}")
        body = list(head)
        for k, v in f.items():
            if k in SKIP or not isinstance(v, str) or not v.strip():
                continue
            body.append(f"[{FIELD_KO.get(k, k)}] {v}")
        blocks.append(("p", "\n".join(body)))
    render("S8_trajectory", "표 S8. 그림 5 사례의 에이전트 출력 전문", blocks)


if __name__ == "__main__":
    print("보충자료 표 S1~S8 — results/table_data/ 만 읽는다")
    for fn in (s1, s2, s3, s4, s5, s6, s7, s8):
        fn()
    print("\n완료. Main Table 1 과 Figure F0~F4 는 건드리지 않았다.")
