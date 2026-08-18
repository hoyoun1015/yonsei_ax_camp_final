"""보충자료 표 S9 제작 — **`results/cross_model_replication_final.json` 만 읽는다.**

S9 는 **보조 검증**이다. 이 연구의 주인공은 화학 가설을 실제 계산 도구로 자율 검증하는
에이전트 전체이고, 다른 베이스 모델에서의 재현은 그것을 옆에서 받치는 실험이다.
**제목·caption·각주를 그 톤으로 유지한다.**

🔒 **기존 LOCK 을 건드리지 않는다.**

  - `tables/make_supp_tables.py` 를 수정하지 않는다 — 그 파일은 S1~S8 LOCK manifest 의
    `code` 항목이라 한 글자만 바뀌어도 `lock_manifest.py --verify` 가 깨진다.
    그래서 표를 그리는 헬퍼만 **읽기 전용으로 import** 한다.
  - `results/table_data/` 에 아무것도 쓰지 않는다 — `lock_manifest.py` 가 그 디렉터리를
    glob 해서 S1~S8 의 `source_data` 로 넣기 때문에, 새 파일을 두면 다음 manifest
    재생성 때 S1~S8 범위로 조용히 빨려 들어간다.
  - Figure F0~F4 · Main Table 1 · S1~S8 · 기존 manifest 를 읽지도 쓰지도 않는다.

🔒 **표에 들어가는 숫자를 이 파일에 적지 않는다.** 전부 정본 artifact 에서 읽어 배치만
한다. 수치를 바꾸려면 `src/vccl/scoring/replication_final.py` 를 고쳐야 하고, 그쪽은
raw chunk 결과에서 재현되지 않으면 파일을 쓰지 않는다.

사용 (프로젝트 루트에서):

    python3 src/vccl/scoring/replication_final.py --save   # 1) 정본 artifact (assertion)
    python3 tables/make_replication_table.py               # 2) → S9 md/pdf/png
    python3 tables/make_replication_table.py --lock        # 2) + S9 전용 lock 기록
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tables"))
sys.path.insert(0, str(ROOT / "src"))

from make_supp_tables import md_table, render  # noqa: E402  (읽기 전용 import)
from vccl.scoring.replication_final import OUT as SRC, build  # noqa: E402

SUP = ROOT / "tables" / "supplementary"
STEM = "S9_replication"
LOCK_DATE = str(date.today())
TITLE = "표 S9. 다른 베이스 모델에서의 보조 검증 (cross-model replication)"


def load() -> dict:
    """정본을 읽고 **raw chunk 에서 다시 만들어 대조한다.** 어긋나면 그리지 않는다."""
    if not SRC.exists():
        raise SystemExit(f"🔴 정본이 없다: {SRC.relative_to(ROOT)}\n"
                         "   먼저 python3 src/vccl/scoring/replication_final.py --save")
    saved = json.loads(SRC.read_text())
    fresh, fails = build()
    if fails:
        raise SystemExit("🔴 정본이 raw chunk 에서 재현되지 않는다:\n  " + "\n  ".join(fails))
    a = {k: v for k, v in saved.items() if k != "generated_at"}
    b = {k: v for k, v in fresh.items() if k != "generated_at"}
    if a != b:
        raise SystemExit("🔴 저장된 정본과 재생성 결과가 다르다. S9 를 그리지 않는다.")

    it = saved["integrity"]
    bad = []
    if it["n_rows"] != it["expected"]:
        bad.append(f"과제 수 {it['n_rows']} != {it['expected']}")
    for k in ("failed", "duplicate", "missing", "unexpected"):
        if it[k] != 0:
            bad.append(f"{k} = {it[k]}")
    if not it["frozen_task_identity"]:
        bad.append("frozen task identity 불일치")
    c = saved["preregistered_results"]["counts_over_30_tasks"]["justified_resolution"]
    if saved["success_criterion"]["met"] != (c["sonnet_V"] > c["R0"]):
        bad.append("성공 기준 플래그가 관측값과 어긋난다")
    if len(saved["preregistered_tests"]["tests"]) != saved["preregistered_tests"]["n_tests"]:
        bad.append("사전 지정 검정 개수가 선언과 다르다")
    if bad:
        raise SystemExit("🔴 무결성 assertion 실패:\n  " + "\n  ".join(bad))
    print(f"  🟢 정본 대조·무결성 assertion 통과 ({SRC.relative_to(ROOT)})")
    return saved


def tables(d: dict):
    c = d["preregistered_results"]["counts_over_30_tasks"]
    n = d["integrity"]["expected"]
    row = lambda k, lab: [lab, f"{c[k]['sonnet_V']} / {n}",     # noqa: E731
                          f"{c[k]['gemini_V']} / {n}", f"{c[k]['R0']} / {n}"]
    hdr = ["지표 (동일 30과제)", "sonnet V", "gemini V", "R0"]
    rows = [row("justified_resolution", "근거가 충분한 결론"),
            row("reference_direction_correct", "참조값과 방향이 맞음"),
            row("overinterpretation", "과대해석"),
            row("over_cautious", "과도한 신중"),
            row("used_l3", "최종 판단 수준이 L3인 과제")]

    t = d["preregistered_tests"]["tests"]
    thdr = ["사전 지정 비교", "값", "불일치 (b : c)", "p"]
    trows = [["sonnet V 대 R0",
              f"{c['justified_resolution']['sonnet_V']} 대 {c['justified_resolution']['R0']}",
              f"{t['sonnet_vs_r0']['discordant_b']} : {t['sonnet_vs_r0']['discordant_c']}",
              f"{t['sonnet_vs_r0']['p_exact_two_sided']}"],
             ["sonnet V 대 gemini V",
              f"{c['justified_resolution']['sonnet_V']} 대 {c['justified_resolution']['gemini_V']}",
              f"{t['sonnet_vs_gemini']['discordant_b']} : {t['sonnet_vs_gemini']['discordant_c']}",
              f"{t['sonnet_vs_gemini']['p_exact_two_sided']}"]]

    b = d["preregistered_results"]["band_c"]
    bhdr = ["Band C 기술 통계", f"sonnet V", "gemini V", "R0"]
    brows = [["근거가 충분한 결론", f"{b['sonnet_V_justified']} / {b['n']}",
              f"{b['gemini_V_justified']} / {b['n']}", f"{b['R0_justified']} / {b['n']}"],
             ["최종 판단 수준이 L3인 과제", f"{b['sonnet_V_used_l3']} / {b['n']}", "—", "—"]]
    return (hdr, rows), (thdr, trows), (bhdr, brows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lock", action="store_true", help="S9 전용 lock 기록도 쓴다")
    a = ap.parse_args()
    d = load()
    (hdr, rows), (thdr, trows), (bhdr, brows) = tables(d)
    it, pv = d["integrity"], d["provenance"]
    ib = d["interpretation_boundaries"]
    ec = d["preregistered_results"]["sonnet_error_decomposition"]["values"]
    idn = d["preregistered_results"]["sonnet_autonomous_identification"]
    n = it["expected"]

    cap = ("**표 S9. 다른 베이스 모델에서의 보조 검증.** 주 실험(92과제)과 같은 시스템 V 를 "
           "베이스 모델만 바꿔 30과제에서 다시 돌렸다. **이 표는 주 결과를 대체하지도 "
           "확증하지도 않는다** — 실행 전에 정해 둔 기준은 «규칙 기준선 R0 보다 근거가 "
           "충분한 결론이 많은가» 하는 **방향 하나**였고, 그 기준은 충족됐다. **그러나 그 "
           "차이는 통계적으로 유의하지 않았다.** 방법 오차 정보를 뺀 조건(V−τ)은 이 모델에서 "
           "돌리지 않았으므로 **τ 의 효과가 모델을 넘어 일반화된다는 주장은 하지 않는다.**")

    L = [f"# 표 S9 — 다른 베이스 모델에서의 보조 검증 (cross-model replication)", "",
         f"> {cap}", "",
         f"**{pv['model']} · 조건 {pv['condition']} 단독 · {pv['n_tasks']}과제 · "
         f"실패 {it['failed']}건**", "",
         "**(가) 같은 30과제에서의 결과**", ""]
    L += md_table(hdr, rows, ["l", "r", "r", "r"])
    L += ["", "**(나) 사전에 지정한 검정 2개** (짝지은 정확 McNemar · 양측 · α = 0.05)", ""]
    L += md_table(thdr, trows, ["l", "r", "c", "r"])
    L += ["", "**(다) Band C — 기술 통계만** (n = "
          f"{d['preregistered_results']['band_c']['n']}, 검정하지 않았다)", ""]
    L += md_table(bhdr, brows, ["l", "r", "r", "r"])
    L += ["", "**각주**", "",
          f"a. **실행 전에 정한 성공 기준은 방향 하나뿐이었다** — sonnet V 의 근거가 충분한 "
          f"결론이 R0 보다 많은가. **통계적 유의성을 조건으로 요구하지 않았다.** 관측은 "
          f"{d['success_criterion']['observed']['sonnet_V']} 대 "
          f"{d['success_criterion']['observed']['R0']} 이므로 **기준은 충족됐다.** "
          f"결과를 본 뒤 기준을 바꾸지 않았다.",
          "",
          f"b. **그 차이는 통계적으로 유의하지 않다** (p = "
          f"{d['preregistered_tests']['tests']['sonnet_vs_r0']['p_exact_two_sided']}). "
          f"«sonnet 에서도 V 가 R0 보다 유의하게 우수했다» 로 쓰지 않는다. 유의하지 않다는 "
          f"것은 «차이가 없다» 가 아니라 이 표본에서 **검출되지 않았다**는 뜻이다 — "
          f"불일치 쌍이 {sum(d['preregistered_tests']['tests']['sonnet_vs_r0'][k] for k in ('discordant_b','discordant_c'))}개뿐이라 "
          f"검정력이 없다.",
          "",
          "c. **방법 오차 정보를 뺀 조건(V−τ)을 이 모델에서 돌리지 않았다.** 복제 계획에 "
          "처음부터 없었다. 따라서 **τ 제거의 효과가 다른 모델에서도 같다거나, τ 를 쓰는 "
          "방식이 모델을 넘어 일반화된다는 주장을 하지 않는다.** 이 표가 확인한 것은 "
          "**시스템 V 전체의 제한적인 방향 일관성**이다.",
          "",
          "d. **두 모델의 비교는 모델 우열 연구가 아니다.** sonnet 대 gemini 는 p = "
          f"{d['preregistered_tests']['tests']['sonnet_vs_gemini']['p_exact_two_sided']} 로, "
          "sonnet 이 못하다는 증명도 두 모델이 같다는 증명도 아니다. 30과제 · 조건 하나 · "
          "한 번의 실행이다.",
          "",
          f"e. **Band C 는 기술 통계뿐이다** (n = {d['preregistered_results']['band_c']['n']}). "
          "검정하지 않았고 p 값을 만들지 않았다. 말할 수 있는 것은 «주 실험에서 관측된 "
          "Band C 중심 패턴과 정성적으로 어긋나지 않는다» 까지이며, «Band C 효과가 "
          "복제됐다» 로 쓰지 않는다.",
          "",
          f"f. **탐색적·기술 통계 전용** — 오류 분해(맞음 {ec['correct']} · 도구 한계 "
          f"{ec['tool-limited']} · 판단 한계 {ec['agent-limited']} · 둘 다 {ec['compound']}) · "
          f"과도한 신중 {d['preregistered_results']['counts_over_30_tasks']['over_cautious']['sonnet_V']}건 · "
          f"자율 식별 {idn['correct']}/{idn['n']}(천장에 닿아 분산이 없다). "
          "**이 값들에 새 검정을 붙이지 않는다.**",
          "",
          "g. «최종 판단 수준이 L3인 과제» 는 결론을 낼 때 쓴 계산 수준이 L3 였던 과제 "
          "수다. **계산 수준을 올린 횟수가 아니다.**",
          "",
          "h. R0 는 비교할 구조 쌍·관측량·계산 수준을 미리 받는 기준선이다. **비교가 "
          "성립하는 축은 «결론 판단» 하나뿐이며** 전체 작업 대비로 읽지 않는다.",
          "", "---", "", "## 실행과 무결성", ""]
    L += md_table(["항목", "값"],
                  [["모델", f"`{pv['model']}`"],
                   ["실행 경로", pv["execution_route"]],
                   ["조건", f"{pv['condition']} 단독 (V−τ 없음)"],
                   ["과제", f"{pv['subset']} · subset 해시 `{pv['subset_sha16']}`"],
                   ["분할", " + ".join(str(x) for x in pv["chunk_partition"])
                    + f" = {n} (`{'` · `'.join(c['run_id'] for c in pv['chunks'])}`)"],
                   ["완료", f"{it['valid_chunks']} chunk · {it['n_rows']}/{it['expected']} · "
                            f"실패 {it['failed']}"],
                   ["중복 · 누락 · 예상 밖", f"{it['duplicate']} · {it['missing']} · {it['unexpected']}"],
                   ["과제 동일성", "동결 목록과 순서까지 일치" if it["frozen_task_identity"] else "🔴 불일치"],
                   ["구간 분포", " · ".join(f"{k} {v}" for k, v in it["bands"].items())],
                   ["무효 기준", it["abort_rule"]],
                   ["1차 시도", pv["invalid_first_attempt"]["status"] + " (최종 집계 제외)"],
                   ["가림(blinding)", pv["blinding"]]],
                  ["l", "l"])
    L += ["", "## 수치 출처 (source mapping)", ""]
    L += md_table(["항목", "출처"],
                  [["전부", f"`{SRC.relative_to(ROOT)}`"],
                   ["정본 생성", "`src/vccl/scoring/replication_final.py` (읽기 전용 · LLM 0회)"],
                   ["원자료", "`experiments/repl_c1~c4_*_" + pv["model"] + "/replication_result.json`"],
                   ["비교 gemini V", d["comparators"]["gemini_V"]],
                   ["비교 R0", d["comparators"]["R0"]]],
                  ["l", "l"])
    L += ["", "**동결 해시**", "", "```"]
    L += [f"{k:<16}{v[:16]}…" for k, v in pv["frozen"].items()]
    L += ["```", "",
          "이 표를 다시 만드는 법 (LLM 호출 0회)", "", "```bash",
          "python3 src/vccl/scoring/replication_final.py --save",
          "python3 tables/make_replication_table.py",
          "```", "",
          "🔒 **S9 는 별도 artifact 다.** 파일 해시와 상류 산출물은 "
          "`tables/supplementary/S9_LOCK.md` 에 있다. **Figure F0~F4 · Main Table 1 · "
          "보충자료 표 S1~S8 의 기존 LOCK 은 이 표 때문에 바뀌지 않는다** — S1~S8 의 "
          "`LOCK_MANIFEST.md` · `lock_manifest.json` · 생성기도 수정하지 않았다.",
          "",
          f"**정본 요약 문구.** {ib['canonical_summary_ko']}"]
    (SUP / f"{STEM}.md").write_text("\n".join(L) + "\n")
    print(f"  → tables/supplementary/{STEM}.md")

    render(STEM, TITLE, [
        ("h", "(가) 같은 30과제에서의 결과"),
        ("t", hdr, rows, [1.5, 0.62, 0.62, 0.62], ["l", "r", "r", "r"]),
        ("h", "(나) 사전에 지정한 검정 2개 (짝지은 정확 McNemar · 양측 · α = 0.05)"),
        ("t", thdr, trows, [1.2, 0.55, 0.7, 0.55], ["l", "r", "c", "r"]),
        ("h", f"(다) Band C — 기술 통계만 (n = {d['preregistered_results']['band_c']['n']}, 검정하지 않았다)"),
        ("t", bhdr, brows, [1.5, 0.62, 0.62, 0.62], ["l", "r", "r", "r"]),
        ("p", "실행 전에 정한 성공 기준은 방향 하나였고 충족됐다 — sonnet V 가 R0 보다 "
              "근거가 충분한 결론이 많다. 유의성을 조건으로 요구하지 않았다.\n"
              "그 차이는 통계적으로 유의하지 않다 (p = "
              f"{d['preregistered_tests']['tests']['sonnet_vs_r0']['p_exact_two_sided']}). "
              "«유의하게 우수했다» 로 쓰지 않는다.\n"
              "방법 오차 정보를 뺀 조건(V−τ)을 이 모델에서 돌리지 않았다 — τ 효과가 모델을 "
              "넘어 일반화된다는 주장을 하지 않는다.\n"
              "두 모델 비교는 우열 연구가 아니다 (p = "
              f"{d['preregistered_tests']['tests']['sonnet_vs_gemini']['p_exact_two_sided']}).\n"
              "Band C 는 검정하지 않았다. 오류 분해·과도한 신중·자율 식별은 탐색적 기술 "
              "통계다."),
    ])

    if a.lock:
        write_lock(d)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_lock(d: dict) -> None:
    """S9 전용 lock 기록. **기존 S1~S8 manifest 를 읽지도 쓰지도 않는다.**"""
    files = {f"tables/supplementary/{STEM}.{e}": SUP / f"{STEM}.{e}"
             for e in ("md", "pdf", "png")}
    code = {"tables/make_replication_table.py": Path(__file__),
            "src/vccl/scoring/replication_final.py":
                ROOT / "src/vccl/scoring/replication_final.py"}
    upstream = {str(SRC.relative_to(ROOT)): SRC}
    for c in d["provenance"]["chunks"]:
        upstream[c["path"] + "/replication_result.json"] = \
            ROOT / c["path"] / "replication_result.json"

    m = {"lock_date": LOCK_DATE, "generated_on": LOCK_DATE,
         "generated_at": datetime.now(timezone.utc).isoformat(),
         "scope": "Supplementary Table S9 (cross-model replication · 보조 검증)",
         "separate_from": ("tables/supplementary/lock_manifest.json (S1~S8) — "
                           "이 기록은 그 manifest 를 수정하지 않는 별도 artifact 다"),
         "unaffected_locks": ["Figure F0~F4 (figures/captions.md · figures/draft/)",
                              "Main Table 1 (tables/draft/T1_system.*)",
                              "Supplementary S1~S8 (tables/supplementary/LOCK_MANIFEST.md)"],
         "note_pdf": ("PDF 는 matplotlib 이 /CreationDate 를 박아 재생성 시 해시가 "
                      "달라진다. 내용 동일성은 PNG 로 확인한다."),
         "table": {k: {"bytes": v.stat().st_size, "sha256": sha(v)} for k, v in files.items()},
         "code": {k: sha(v) for k, v in code.items()},
         "upstream": {k: sha(v) for k, v in upstream.items()},
         "frozen": d["provenance"]["frozen"]}
    (SUP / "S9_lock.json").write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n")

    L = ["# 보충자료 표 S9 — LOCK 기록 (cross-model replication)", "",
         f"**LOCK {m['lock_date']}** · 생성 {m['generated_on']}", "",
         "이 표의 **수치·통계·문구·행·열·각주는 확정**됐다. 이후 변경은 제출 형식에 따른 "
         "레이아웃 조정만 허용하며, 그 밖의 변경은 **먼저 amendment 로 보고**한다.", "",
         "> ⚠️ " + m["note_pdf"], "",
         "🔒 **이것은 S1~S8 과 별도의 기록이다.** "
         "`tables/supplementary/LOCK_MANIFEST.md` · `lock_manifest.json` · "
         "`lock_manifest.py` · `make_supp_tables.py` 를 **수정하지 않았다.**", "",
         "**영향받지 않는 기존 LOCK**", ""]
    L += [f"- {x}" for x in m["unaffected_locks"]]
    L += ["", "---", "", "## 1. 표 산출물", "",
          "| 파일 | 크기 | sha256 |", "|---|---:|---|"]
    L += [f"| `{k}` | {v['bytes']:,} | `{v['sha256']}` |" for k, v in m["table"].items()]
    L += ["", "## 2. 생성 코드", "", "| 파일 | sha256 |", "|---|---|"]
    L += [f"| `{k}` | `{v}` |" for k, v in m["code"].items()]
    L += ["", "## 3. 상류 산출물", "", "| 파일 | sha256 |", "|---|---|"]
    L += [f"| `{k}` | `{v}` |" for k, v in m["upstream"].items()]
    L += ["", "## 4. 동결 해시", "", "```"]
    L += [f"{k:<16}{v}" for k, v in m["frozen"].items()]
    L += ["```", "", "## 5. 검증", "", "```bash",
          "python3 tables/make_replication_table.py --verify", "```", "",
          "기계가 읽는 기록은 `tables/supplementary/S9_lock.json` 이다."]
    (SUP / "S9_LOCK.md").write_text("\n".join(L) + "\n")
    print("  → tables/supplementary/S9_lock.json | S9_LOCK.md")


def verify() -> bool:
    m = json.loads((SUP / "S9_lock.json").read_text())
    ok = True
    for section in ("table", "code", "upstream"):
        for k, v in m[section].items():
            want = v["sha256"] if isinstance(v, dict) else v
            p = ROOT / k
            got = sha(p) if p.exists() else "🔴 없음"
            good = got == want
            ok &= good
            if not good and k.endswith(".pdf"):
                print(f"  🟡 {k}  (PDF 는 /CreationDate 때문에 달라질 수 있다 — PNG 로 확인)")
                ok = True if all(sha(ROOT / x) == m["table"][x]["sha256"]
                                 for x in m["table"] if x.endswith(".png")) and ok else ok
            else:
                print(f"  {'🟢' if good else '🔴'} {k}")
    print(f"\n{'🟢 S9 LOCK 상태 그대로' if ok else '🔴 S9 LOCK 이 깨졌다'}")
    return ok


if __name__ == "__main__":
    if "--verify" in sys.argv:
        sys.exit(0 if verify() else 1)
    main()
