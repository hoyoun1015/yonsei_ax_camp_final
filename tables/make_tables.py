"""논문 표 제작 — **`results/plot_data/` 만 읽는다.**

실행 (프로젝트 루트에서):

    python3 src/vccl/scoring/plot_data.py     # 1) 동결본 → results/plot_data/ (assertion)
    python3 tables/make_tables.py             # 2) table-ready 데이터 → tables/draft/*.md

🔒 **표에 들어가는 숫자를 이 파일에 적지 않는다.** 전부 `t1_system.json` 에서 읽어
배치만 한다. 수치를 바꾸려면 1) 을 고쳐야 한다.

현재 본문 표는 **하나**다 (`paper_logic/table_design.md` §3·§4).
Supplementary S1~S8 은 아직 만들지 않는다.

🔒 **LOCK (2026-08-16)** — 표 1의 수치·행·열·각주·caption을 확정했다. 이후에는 제출
형식에 따른 레이아웃 조정 외에 내용을 바꾸지 않는다.
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
    "figure.dpi": 200, "savefig.bbox": "tight", "savefig.pad_inches": 0.05,
    "pdf.fonttype": 42, "ps.fonttype": 42,
})

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "plot_data"
OUT = ROOT / "tables" / "draft"
OUT.mkdir(parents=True, exist_ok=True)


def CAPTION(n, lab, ident) -> str:
    """표 1 caption. 수치는 인자로 받는다 — 이 파일에 결과값을 적지 않는다."""
    return (
        f"> **표 1. 두 조건의 실행 동작.** 같은 {n}과제를 조건 {lab['V']} 와 "
        f"{lab['V-tau']} 로 각각 실행한 결과다. 두 조건 모두 모든 과제를 끝까지 "
        f"수행했고, 자율 식별 정확도도 {ident.replace(' ', '')}으로 같았다. 실행 "
        f"과정에서는 계산 수준 선택과 반복 계산 패턴이 크게 달랐다. 근거가 충분한 "
        f"결론은 식별 방식별로 나누어 함께 제시했으며, 전체 결과와 통계 검정은 "
        f"그림 3에 제시한다.")


def build_t1() -> str:
    d = json.loads((DATA / "t1_system.json").read_text())
    n = d["n_tasks"]
    cs = d["conditions"]
    lab = d["condition_label"]
    ex = d["execution"]
    L = []

    L.append(f"# 표 1 — {d['title']}\n")
    L.append("**caption 초안**\n")
    ident = next(r for r in d["rows"] if r["key"] == "ident")["display"]["V"]
    L.append(CAPTION(n, lab, ident) + "\n")

    L.append("\n**표**\n")
    L.append("| 지표 | " + " | ".join(lab[c] for c in cs) + " |")
    L.append("|---|" + "---:|" * len(cs))
    for r in d["rows"]:
        L.append(f"| {r['label']} | " + " | ".join(r["display"][c] for c in cs) + " |")

    L.append("\n**각주**\n")
    L.append(
        f"a. 유효 본실행은 {ex['n_batches']}개 묶음, 총 **{ex['n_calls']}회 호출**"
        f"(약 {ex['elapsed_min']:.0f}분)이다. 첫 시도에서 구조화된 출력을 얻지 못한 "
        f"호출이 **{ex['unparsed']}회** 있었고 모두 재시도 경로에서 복구됐다. "
        f"그중 **{ex['status_err']}회**는 실행 도구가 오류 상태를 반환한 경우"
        f"(일시적 네트워크 오류)이고, 나머지 "
        f"**{ex['unparsed'] - ex['status_err']}회**는 정상 상태로 응답했으나 본문이 "
        f"비어 있던 경우다 — 즉 오류 상태 {ex['status_err']}회는 구조화 출력 실패 "
        f"{ex['unparsed']}회에 **포함된다**. 원장 파일(JSONL)의 줄 파싱 실패는 "
        f"**{ex['jsonl_bad']}**, 과제 단위로 실패한 과제는 **{ex['task_failed']}** 이다.")
    L.append(
        "\nb. 자율 식별 정확도의 분모에서 쌍 지정형 과제는 제외했다. 그 과제들은 비교할 "
        "두 구조를 지정받으므로 식별을 수행하지 않는다. 두 조건 모두 분모와 분자가 같아 "
        "이 지표에는 조건 간 차이가 남아 있지 않다.")
    per = d["raw"]
    L.append(
        "\nc. 경로 A는 계산 수준을 올린 횟수, 경로 B는 원래 가설을 그대로 둔 채 비교 "
        "대상만 다시 정한 횟수다. **「최종 판단 수준이 L3인 과제」는 마지막 판단을 "
        "L3 결과로 내린 과제를 세며, L3 계산이 한 번이라도 돌아간 과제와 다르다.** "
        f"조건 {lab['V-tau']}에서는 L3가 한 번이라도 돌아간 과제가 "
        f"{per['V-tau']['l3_any_exec_tasks']}개인데 최종 판단 수준이 L3인 과제는 "
        f"{per['V-tau']['l3_tasks']}개다 — 한 과제는 L3로 계산한 뒤 비교 대상을 다시 "
        f"정해(경로 B) 마지막에는 L1 결과로 판단을 마쳤다. 조건 {lab['V']}에서는 두 "
        f"수가 모두 {per['V']['l3_tasks']}개로 같다. L3 실행 횟수가 과제 수보다 큰 "
        "것은 같은 과제를 두 번 이상 계산한 경우가 있기 때문이다.")
    L.append(f"\nd. {d['not_repeated_from_figures']}")

    L.append("\n**표에 넣지 않은 계획 지표**\n")
    for k, v in d["excluded_metrics"].items():
        L.append(f"- `{k}` — {v}")

    L.append("\n---\n\n## 수치 출처 (source mapping)\n")
    L.append("| 행 | 출처 |")
    L.append("|---|---|")
    for r in d["rows"]:
        L.append(f"| {r['label']} | `{r['source']}` |")
    L.append(f"| 각주 a (실행 규모) | `experiments/main_b*/batch_result.json` 의 "
             f"`ledger_summary` · `elapsed_s` 와 각 `calls.jsonl` 원본 집계 |")
    L.append(
        "\n모든 값은 `src/vccl/scoring/plot_data.py` 의 `build_t1()` 이 동결 산출물에서 "
        "뽑아 `results/plot_data/t1_system.json` 에 기록한 것이며, 이 표는 그 파일만 "
        "읽는다. 생성 시 assertion 27건이 통과해야 파일이 쓰인다.\n")
    L.append("**동결 해시** — 표의 근거가 된 실행은 다음 동결본으로 수행됐다.\n")
    L.append("```")
    for k, v in d["frozen"].items():
        L.append(f"{k:<26}{v[:16]}…")
    L.append("```")

    # 🔒 LOCK 은 **생성기가 만든다** — 손으로 붙이면 재생성 때 지워진다.
    #    (2026-08-17 에 실제로 한 번 지워졌다. DECISION_LOG 2026-08-17 (2))
    L.append("\n---\n\n## 🔒 LOCK (2026-08-16)\n")
    L.append("표 1의 **수치·행·열·각주·caption을 확정**했다. 이후에는 제출 형식에 따른 "
             "레이아웃 조정 외에 내용을 바꾸지 않는다.\n")
    L.append("```bash\npython3 src/vccl/scoring/plot_data.py\n"
             "python3 tables/make_tables.py\n```\n")
    L.append("> **LOCK 이후 1회 수정** (2026-08-17, 외부 감사 · 사용자 승인) — 행 라벨을 "
             "«L3를 사용한 과제 수» 에서 **«최종 판단 수준이 L3인 과제»** 로 고치고 "
             "각주 c 를 보완했다. `used_l3` 는 `level_used == 'L3'`, 즉 최종 판단 "
             "수준이며 «L3 가 한 번이라도 실행된 과제»(V−τ 92/92)와 다르기 때문이다. "
             "**수치·행·열 구성은 바뀌지 않았다** — semantic/provenance correction 이다 "
             "(`DECISION_LOG` 2026-08-16 (6) §③).")
    return "\n".join(L) + "\n"


def ko(t: str) -> str:
    """한글 폰트에 글리프가 없는 문자를 같은 뜻의 문자로 바꾼다 (표기 정규화)."""
    return t.replace("\u2212", "-").replace("\u2013", "-")


def render_t1():
    """논문용 렌더링본. 장식 없이 가로줄 세 개(booktabs 관례)만 쓴다.

    좌표는 «행 단위»로 잡고 ylim 을 내용에 맞춰 여백을 남기지 않는다.
    """
    d = json.loads((DATA / "t1_system.json").read_text())
    lab, cs = d["condition_label"], d["conditions"]
    rows = [(r["label"], [r["display"][c] for c in cs]) for r in d["rows"]]
    ident = next(r for r in d["rows"] if r["key"] == "ident")["display"]["V"]
    cap = CAPTION(d["n_tasks"], lab, ident).lstrip("> ").replace("**", "")
    cap_lines = textwrap.wrap(ko(cap), 74)

    W = 6.9
    nr = len(rows)
    head, gap_cap = 1.0, 0.9
    total_rows = head + nr + gap_cap + len(cap_lines) * 0.72
    row_in = 0.245                                   # 행 하나의 세로 크기(인치)
    fig = plt.figure(figsize=(W, total_rows * row_in + 0.12))
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(-(total_rows - head), head)

    x_lab, x_col = 0.015, (0.655, 0.865)
    ax.plot([0, 1], [head, head], lw=1.1, color="black")
    ax.text(x_lab, head - 0.72, "지표", fontsize=9.5, fontweight="bold")
    for x, c in zip(x_col, cs):
        ax.text(x, head - 0.72, ko(lab[c]), fontsize=9.5, fontweight="bold",
                ha="center")
    ax.plot([0, 1], [0, 0], lw=0.7, color="black")

    y = 0.0
    for label, vals in rows:
        y -= 1.0
        sub = label.startswith("—")
        ax.text(x_lab + (0.022 if sub else 0), y + 0.28,
                label.lstrip("— ") if sub else label,
                fontsize=9, color="0.30" if sub else "black")
        if sub:
            ax.text(x_lab + 0.008, y + 0.28, "·", fontsize=9, color="0.45")
        for x, v in zip(x_col, vals):
            ax.text(x, y + 0.28, v, fontsize=9, ha="center")
    ax.plot([0, 1], [y - 0.02, y - 0.02], lw=1.1, color="black")

    y -= gap_cap
    for line in cap_lines:
        ax.text(0, y, line, fontsize=7.4, va="top")
        y -= 0.72
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"T1_system.{ext}")
    plt.close(fig)
    print("  → tables/draft/T1_system.pdf | .png")


if __name__ == "__main__":
    print("표 제작 — results/plot_data/ 만 읽는다")
    (OUT / "T1_system.md").write_text(build_t1())
    print("  → tables/draft/T1_system.md")
    render_t1()
    print("\n완료. Supplementary S1~S8 은 만들지 않았다.")
