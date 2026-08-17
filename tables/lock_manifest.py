"""보충자료 표 S1~S8 의 LOCK manifest 생성·검증. **LLM 호출 0회 · 읽기 전용.**

    python3 tables/lock_manifest.py            # manifest 생성
    python3 tables/lock_manifest.py --verify   # 현재 파일이 manifest 와 일치하는지

기록하는 것 —

| 층 | 무엇 |
|---|---|
| 산출물 | `tables/supplementary/` 의 MD · PDF · PNG |
| source data | `results/table_data/` 의 JSON · CSV |
| 생성 코드 | `table_data.py` · `make_supp_tables.py` · `lock_manifest.py` |
| 상류 산출물 | 동결본, 본실행 집계, primary 24, L0 probe, secondary 94, S8 원본 배치 |

⚠️ **PDF 는 재현 대상에서 뺀다.** matplotlib 이 `/CreationDate` 를 파일에 박기 때문에
같은 내용을 다시 그려도 해시가 달라진다. **내용 동일성은 PNG 로 확인한다** — 같은
figure 를 같은 데이터로 그리면 PNG 는 바이트까지 같다. PDF 해시는 «이 시점의 파일»
기록으로만 남긴다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUP = ROOT / "tables" / "supplementary"
DATA = ROOT / "results" / "table_data"
MANIFEST_MD = SUP / "LOCK_MANIFEST.md"
MANIFEST_JSON = SUP / "lock_manifest.json"

LOCK_DATE = "2026-08-17"
TABLES = [
    ("S1", "S1_tests", "통계검정 요약 (정확 McNemar 8건)"),
    ("S2", "S2_tau", "반응 유형·서브셋별 방법 오차 τ 실측"),
    ("S3", "S3_errors", "오류 분해 (탐색적)"),
    ("S4", "S4_benchmark", "벤치마크 구성 (N=92)"),
    ("S5", "S5_cost", "계산시간·비용 상세 (psi4 실측)"),
    ("S6", "S6_identification", "구조 식별 보조 검증 (primary 24 · secondary 94)"),
    ("S7", "S7_l0_probe", "계산 도구 없이 답하게 한 검사 (L0 probe)"),
    ("S8", "S8_trajectory", "그림 5 사례의 에이전트 출력 전문"),
]
CODE = ["src/vccl/scoring/table_data.py", "tables/make_supp_tables.py",
        "tables/lock_manifest.py"]
UPSTREAM = [
    "data/tasks/frozen_rules_v1.json",
    "data/tasks/frozen_stage_b_v1.json",
    "data/tasks/execution_order_v1.json",
    "results/main_run_aggregate.json",
    "results/oracle_headroom_audit.json",
    "experiments/chal_primary_20260814T235648Z_gemini-3.6-flash-high"
    "/challenge_result.json",
    "experiments/L0_20260811T134258Z_gemini-3.6-flash-high/l0_result.json",
    "experiments/chal_secondary94/secondary_result.json",
    "experiments/main_b1_20260813T003426Z_gemini-3.6-flash-high/batch_result.json",
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def collect() -> dict:
    out = {"lock_date": LOCK_DATE, "generated_on": str(date.today()),
           "scope": "Supplementary Tables S1~S8",
           "note_pdf": ("PDF 는 matplotlib 이 /CreationDate 를 박아 재생성 시 해시가 "
                        "달라진다. 내용 동일성은 PNG 로 확인한다."),
           "unaffected_locks": ["Figure F0~F4 (figures/captions.md · figures/draft/)",
                                "Main Table 1 (tables/draft/T1_system.*)"],
           "tables": {}, "source_data": {}, "code": {}, "upstream": {}}
    for sid, stem, title in TABLES:
        e = {"title": title, "files": {}}
        for ext in ("md", "pdf", "png"):
            f = SUP / f"{stem}.{ext}"
            e["files"][ext] = {"path": str(f.relative_to(ROOT)),
                               "bytes": f.stat().st_size, "sha256": sha(f)}
        out["tables"][sid] = e
    for f in sorted(DATA.iterdir()):
        if f.suffix in (".json", ".csv"):
            out["source_data"][f.name] = {"bytes": f.stat().st_size, "sha256": sha(f)}
    for rel in CODE:
        out["code"][rel] = sha(ROOT / rel)
    for rel in UPSTREAM:
        f = ROOT / rel
        out["upstream"][rel] = sha(f) if f.exists() else "🔴 없음"
    return out


def render(m: dict) -> str:
    L = ["# 보충자료 표 S1~S8 — LOCK MANIFEST", "",
         f"**LOCK {m['lock_date']}** · 생성 {m['generated_on']}", "",
         "이 표들의 **수치·통계·문구·행·열·각주는 확정**됐다. 이후 변경은 제출 형식에 "
         "따른 레이아웃 조정만 허용하며, 그 밖의 변경은 **먼저 amendment 로 보고**한다.",
         "", f"> ⚠️ {m['note_pdf']}", "",
         "**영향받지 않는 기존 LOCK**", ""]
    L += [f"- {x}" for x in m["unaffected_locks"]]
    L += ["", "---", "", "## 1. 표 산출물", ""]
    for sid, e in m["tables"].items():
        L += [f"### {sid} — {e['title']}", "",
              "| 형식 | 크기 | sha256 |", "|---|---:|---|"]
        for ext in ("md", "pdf", "png"):
            f = e["files"][ext]
            L.append(f"| `.{ext}` | {f['bytes']:,} | `{f['sha256']}` |")
        L.append("")
    L += ["---", "", "## 2. source data (`results/table_data/`)", "",
          "표는 이 파일들만 읽는다. 값을 바꾸려면 생성기를 고쳐야 한다.", "",
          "| 파일 | 크기 | sha256 |", "|---|---:|---|"]
    for n, v in m["source_data"].items():
        L.append(f"| `{n}` | {v['bytes']:,} | `{v['sha256']}` |")
    L += ["", "---", "", "## 3. 생성 코드", "", "| 파일 | sha256 |", "|---|---|"]
    for n, v in m["code"].items():
        L.append(f"| `{n}` | `{v}` |")
    L += ["", "---", "", "## 4. 상류 산출물 (이 표들의 근거)", "",
          "| 파일 | sha256 |", "|---|---|"]
    for n, v in m["upstream"].items():
        L.append(f"| `{n}` | `{v}` |")
    L += ["", "---", "", "## 5. 검증", "", "```bash",
          "python3 tables/lock_manifest.py --verify", "```", "",
          "MD·PNG·source data·코드·상류 산출물의 해시를 현재 파일과 대조한다. "
          "PDF 는 생성시각이 박히므로 대조에서 뺀다.", ""]
    return "\n".join(L) + "\n"


def verify(m: dict) -> bool:
    ok = True

    def chk(lab: str, want: str, f: Path) -> None:
        nonlocal ok
        got = sha(f) if f.exists() else "🔴 없음"
        good = got == want
        ok &= good
        print(f"  {'🟢' if good else '🔴'} {lab}")

    print("=" * 78)
    print(f"LOCK manifest 대조 — {m['lock_date']}")
    print("=" * 78)
    print("\n표 산출물 (MD·PNG · PDF 는 생성시각 때문에 제외)")
    for sid, e in m["tables"].items():
        for ext in ("md", "png"):
            chk(f"{sid} .{ext}", e["files"][ext]["sha256"],
                ROOT / e["files"][ext]["path"])
    print("\nsource data")
    for n, v in m["source_data"].items():
        chk(n, v["sha256"], DATA / n)
    print("\n생성 코드")
    for n, v in m["code"].items():
        chk(n, v, ROOT / n)
    print("\n상류 산출물")
    for n, v in m["upstream"].items():
        chk(n, v, ROOT / n)
    print()
    print("🟢 LOCK 상태 그대로" if ok else "🔴 LOCK 이후 바뀐 파일이 있다 — amendment 필요")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.verify:
        if not MANIFEST_JSON.exists():
            raise SystemExit("🔴 manifest 가 없다. 먼저 인자 없이 실행한다.")
        raise SystemExit(0 if verify(json.loads(MANIFEST_JSON.read_text())) else 1)
    m = collect()
    MANIFEST_JSON.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n")
    MANIFEST_MD.write_text(render(m))
    print(f"🔒 LOCK manifest 생성 — 표 {len(m['tables'])} · source {len(m['source_data'])}"
          f" · 코드 {len(m['code'])} · 상류 {len(m['upstream'])}")
    print(f"  → {MANIFEST_MD.relative_to(ROOT)}")
    print(f"  → {MANIFEST_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
