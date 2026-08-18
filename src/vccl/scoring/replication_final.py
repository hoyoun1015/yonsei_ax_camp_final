"""cross-model replication 정본 집계 — **읽기 전용 · LLM 0회 · 새 분석을 하지 않는다.**

`replication.py --report` 가 화면에 찍는 것과 **같은 값을 같은 코드 경로로** 모아
기계가 읽을 수 있는 파일 하나로 남긴다. 지표 정의도 검정도 여기서 다시 구현하지
않는다 — `replication.mcnemar` 와 `rows` 에 이미 기록된 필드를 그대로 쓴다
(채점을 두 곳에 두면 갈라진다. `aggregate.py` 와 같은 원칙이다).

**이 파일이 만들지 않는 것** — 새 지표 · 새 검정 · 새 subgroup · 새 p 값 ·
새 성공 기준. 사전등록(`docs/DECISION_LOG.md` 2026-08-14 (2)) 에 적힌 것만 담는다.

**모든 산출물에 assertion 을 건다** — 동결 원본에서 재현되지 않으면 파일을 쓰지 않는다.
기대값은 30/30 완료 후 unblind 한 확정값이다 (`DECISION_LOG` 2026-08-19 (1)).

사용:
    python3 src/vccl/scoring/replication_final.py            # 점검만 (쓰지 않는다)
    python3 src/vccl/scoring/replication_final.py --save     # results/ 에 기록
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents.replication import (  # noqa: E402
    CHUNKS, CONDITION, HEADROOM, MAIN_AGG, MODEL, N_TOTAL, SUBSET_SHA,
    chunk_slice, frozen_hashes, load_chunk, mcnemar, out_dir_for, subset,
)

OUT = ROOT / "results" / "cross_model_replication_final.json"

# 30/30 완료 후 unblind 한 확정값. 재현되지 않으면 쓰지 않는다.
EXPECTED = {
    "justified_resolution": {"sonnet_V": 21, "gemini_V": 25, "R0": 18},
    "reference_direction_correct": {"sonnet_V": 21, "gemini_V": 25, "R0": 18},
    "overinterpretation": {"sonnet_V": 0, "gemini_V": 0, "R0": 0},
    "over_cautious": {"sonnet_V": 4, "gemini_V": 0, "R0": 0},
    "used_l3": {"sonnet_V": 18, "gemini_V": 16, "R0": 0},
    "tests": {"sonnet_vs_r0": (5, 2, 0.4531), "sonnet_vs_gemini": (1, 5, 0.2188)},
    "band_c": {"sonnet_V": 7, "gemini_V": 6, "R0": 3, "sonnet_used_l3": 8, "n": 8},
    "error_class": {"correct": 24, "compound": 2, "agent-limited": 2, "tool-limited": 2},
    "identification": (26, 26),
}
KEYS = ("justified_resolution", "reference_direction_correct",
        "overinterpretation", "over_cautious", "used_l3")


def collect() -> tuple[dict, list[str]]:
    """4개 chunk 의 rows 를 모은다. 무효 1차 시도(`repl_h1_*`)는 glob 에 잡히지 않는다."""
    fails: list[str] = []
    ids = subset()
    chunks, rows = [], {}
    for c in range(1, len(CHUNKS) + 1):
        p = load_chunk(c)
        if p is None:
            raise SystemExit(f"🔴 chunk {c} 결과가 없다. 정본을 만들지 않는다.")
        exp = ids[chunk_slice(c)]
        d = out_dir_for(c)
        tids = [r["tid"] for r in p["rows"]]
        if tids != exp:
            fails.append(f"chunk {c} task_ids 가 동결 subset 과 다르다")
        if p["frozen"] != frozen_hashes():
            fails.append(f"chunk {c} 동결 해시가 현재와 다르다")
        if p["model"] != MODEL or p["condition"] != CONDITION:
            fails.append(f"chunk {c} 모델·condition 이 사전등록과 다르다")
        if p["subset_sha16"] != SUBSET_SHA:
            fails.append(f"chunk {c} subset 해시가 사전등록과 다르다")
        chunks.append({
            "chunk": c, "n_planned": CHUNKS[c - 1], "n_rows": len(p["rows"]),
            "path": str(d.relative_to(ROOT)), "run_id": d.name.split("_")[2],
            "generated_at": p["generated_at"],
            "failed": sum(bool(r["failed"]) for r in p["rows"]),
            "n_calls": p["ledger_summary"]["n_calls"],
            "elapsed_s": p["elapsed_s"],
            "quota_before": p["quota_before"].get("Claude and GPT models", {}),
            "quota_after": p["quota_after"].get("Claude and GPT models", {}),
        })
        for r in p["rows"]:
            rows[r["tid"]] = r
    if len(rows) != N_TOTAL:
        fails.append(f"과제 수가 {len(rows)} 로 {N_TOTAL} 이 아니다")
    return {"chunks": chunks, "rows": rows, "ids": ids, "fails": fails}, fails


def build() -> tuple[dict, list[str]]:
    got, fails = collect()
    rows, ids, chunks = got["rows"], got["ids"], got["chunks"]
    all_tids = [r["tid"] for c in range(1, len(CHUNKS) + 1) for r in load_chunk(c)["rows"]]
    ok = [t for t in ids if not rows[t]["failed"]]

    gem = {r["tid"]: r for r in json.loads(MAIN_AGG.read_text())["rows"]["V"]
           if r["tid"] in rows}
    r0 = {r["tid"]: r for r in json.loads(HEADROOM.read_text())["rows"]["R0"]
          if r["tid"] in rows}
    if len(gem) != N_TOTAL or len(r0) != N_TOTAL:
        fails.append(f"비교군 매칭 실패 — gemini {len(gem)} · R0 {len(r0)}")

    counts = {k: {"sonnet_V": sum(bool(rows[t][k]) for t in ok),
                  "gemini_V": sum(bool(gem[t][k]) for t in ok),
                  "R0": sum(bool(r0[t][k]) for t in ok)} for k in KEYS}
    counts["used_l3"]["R0"] = 0        # R0 는 도구를 쓰지 않는다 (report() 와 동일)

    tests = {}
    for name, other in (("sonnet_vs_r0", r0), ("sonnet_vs_gemini", gem)):
        b, c, p = mcnemar(rows, other, ok, "justified_resolution")
        tests[name] = {"metric": "justified_resolution", "discordant_b": b,
                       "discordant_c": c, "p_exact_two_sided": round(p, 4),
                       "alpha": 0.05, "significant": p < 0.05}

    bc = [t for t in ok if rows[t]["band"] == "C"]
    band_c = {"n": len(bc), "descriptive_only": True,
              "sonnet_V_justified": sum(bool(rows[t]["justified_resolution"]) for t in bc),
              "gemini_V_justified": sum(bool(gem[t]["justified_resolution"]) for t in bc),
              "R0_justified": sum(bool(r0[t]["justified_resolution"]) for t in bc),
              "sonnet_V_used_l3": sum(bool(rows[t]["used_l3"]) for t in bc)}

    ec = dict(Counter(rows[t]["error_class"] for t in ok).most_common())
    ident_n = sum(1 for t in ok if rows[t]["identification_accuracy"] is not None)
    ident_ok = sum(1 for t in ok if rows[t]["identification_accuracy"])

    # ── assertion — unblind 확정값에서 재현되는가 ────────────────────
    for k in KEYS:
        if counts[k] != EXPECTED[k]:
            fails.append(f"{k} 불일치 {counts[k]} != {EXPECTED[k]}")
    for name, (b, c, p) in EXPECTED["tests"].items():
        t = tests[name]
        if (t["discordant_b"], t["discordant_c"], t["p_exact_two_sided"]) != (b, c, p):
            fails.append(f"검정 {name} 불일치 {t} != {(b, c, p)}")
    if (band_c["sonnet_V_justified"], band_c["gemini_V_justified"], band_c["R0_justified"],
            band_c["sonnet_V_used_l3"], band_c["n"]) != tuple(EXPECTED["band_c"][k] for k in
            ("sonnet_V", "gemini_V", "R0", "sonnet_used_l3", "n")):
        fails.append(f"밴드 C 불일치 {band_c}")
    if ec != EXPECTED["error_class"]:
        fails.append(f"오류 분해 불일치 {ec} != {EXPECTED['error_class']}")
    if (ident_ok, ident_n) != EXPECTED["identification"]:
        fails.append(f"식별 불일치 {(ident_ok, ident_n)} != {EXPECTED['identification']}")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact": "cross-model replication — 정본 (canonical)",
        "note": ("`replication.py --report` 와 같은 코드 경로로 모은 값이다. "
                 "새 지표·새 검정·새 p 값을 만들지 않았다."),
        "preregistration": ["docs/DECISION_LOG.md 2026-08-14 (2)",
                            "docs/DECISION_LOG.md 2026-08-14 (3) — schedule-only amendment"],
        "provenance": {
            "model": MODEL, "condition": CONDITION, "n_tasks": N_TOTAL,
            "execution_route": ("Antigravity CLI (`agy`) headless subprocess — "
                                "src/vccl/agents/backend.py"),
            "quota_group": "claude-gpt",
            "subset": "execution_order_v1.json Batch 1 (30과제·동일 순서)",
            "subset_sha16": SUBSET_SHA,
            "frozen": frozen_hashes(),
            "chunk_partition": list(CHUNKS),
            "chunks": chunks,
            "invalid_first_attempt": {
                "path": "experiments/repl_h1_20260813T175407Z_claude-sonnet-4-6",
                "status": "INVALID — provenance 로만 보존",
                "reason": "quota 소진으로 FAILED 2/30 = 6.7% > 5% (DECISION_LOG 2026-08-14 (3))",
                "included_in_this_artifact": False},
            "blinding": ("30/30 integrity 를 모두 확인한 뒤에 처음 unblind 했다. "
                         "chunk 실행 모드는 성능 지표를 출력하지 않으며 `--report` 는 "
                         "4개 chunk 전량 완료 전 SystemExit 이다."),
        },
        "integrity": {
            "valid_chunks": f"{len(chunks)}/{len(CHUNKS)}",
            "n_rows": len(rows), "expected": N_TOTAL,
            "failed": sum(bool(r["failed"]) for r in rows.values()),
            "duplicate": len(all_tids) - len(set(all_tids)),
            "missing": len(set(ids) - set(rows)),
            "unexpected": len(set(rows) - set(ids)),
            "frozen_task_identity": all_tids == ids,
            "bands": dict(sorted(Counter(rows[t]["band"] for t in ids).items())),
            "abort_rule": "FAILED > 5% (30과제 기준 2과제 이상) 이면 무효",
        },
        "preregistered_results": {
            "counts_over_30_tasks": counts,
            "sonnet_error_decomposition": {"values": ec,
                                           "status": "exploratory / descriptive only"},
            "sonnet_autonomous_identification": {
                "correct": ident_ok, "n": ident_n,
                "status": "descriptive — 천장 효과로 분산이 없다"},
            "band_c": band_c,
        },
        "preregistered_tests": {
            "definition": "정확 McNemar · 양측 · α=0.05 · 동일 30과제 paired",
            "n_tests": 2, "multiplicity_correction": False,
            "tests": tests,
        },
        "success_criterion": {
            "defined_before_execution": True,
            "definition": ("V_sonnet 의 justified resolution 이 R0 대비 «같은 방향(우위)» "
                           "이면 «패턴이 복제됐다», 아니면 «복제되지 않았다»"),
            "requires_statistical_significance": False,
            "observed": {"sonnet_V": counts["justified_resolution"]["sonnet_V"],
                         "R0": counts["justified_resolution"]["R0"]},
            "met": counts["justified_resolution"]["sonnet_V"] > counts["justified_resolution"]["R0"],
        },
        "interpretation_boundaries": {
            "can_say": [
                "Sonnet 4.6 에서도 V 가 R0 보다 근거가 충분한 결론을 더 많이 냈다 (21 vs 18).",
                "사전 정의한 방향성 복제 기준(directional replication criterion)은 충족했다.",
                "Sonnet V 에서 과대해석 0/30 이 관측됐다.",
                "밴드 C 결과는 main N=92 에서 관측된 밴드 C 중심 패턴과 정성적으로 어긋나지 않는다.",
            ],
            "cannot_say": [
                "«유의하게 우수했다» — 사전 지정 검정이 p = 0.4531 로 유의하지 않았다.",
                "«τ 효과가 모델 간에 복제됐다» — V−τ 를 실행하지 않았다 (사전등록에 명시).",
                "«독립적 확증» · «완전한 cross-model replication» — 30과제·V 단독·단일 실행이다.",
                "모델 우열 — sonnet 21 vs gemini 25, p = 0.2188. 열세의 증명도 동등의 증명도 아니다.",
                "«밴드 C 효과가 유의하게 복제됐다» — n=8 은 검정하지 않았다 (descriptive only).",
            ],
            "canonical_summary_ko": (
                "사전 정의한 방향성 복제 기준은 충족되었다. Sonnet 4.6 에서도 V 는 R0 보다 "
                "더 많은 근거 있는 결론을 냈다(21/30 vs 18/30). 다만 이 차이는 통계적으로 "
                "유의하지 않았으며(exact McNemar p=0.453), V−τ 조건을 재실행하지 않았으므로 "
                "τ 효과 자체의 모델 간 일반화가 검증된 것은 아니다."),
            "canonical_summary_en": (
                "The preregistered directional replication criterion was met: under Sonnet 4.6, "
                "V produced more justified resolutions than R0 (21/30 vs 18/30). However, the "
                "difference was not statistically significant (exact McNemar p=0.453), and "
                "because the V−tau condition was not replicated, this experiment does not "
                "establish cross-model generalization of the tau ablation effect."),
        },
        "comparators": {
            "gemini_V": "results/main_run_aggregate.json rows.V (동일 30과제 부분집합)",
            "R0": "results/oracle_headroom_audit.json rows.R0 (동일 30과제 부분집합)",
            "caveat": ("R0 는 구조 쌍·관측량·수준을 오라클로 받는다 — 비교가 성립하는 축은 "
                       "«결론 판단» 하나뿐이다."),
        },
        "does_not_modify": ["figures/draft F0~F4", "tables/draft Main Table 1",
                            "tables/supplementary S1~S8", "lock_manifest",
                            "results/main_run_aggregate.json", "results/r0_baseline.json",
                            "results/oracle_headroom_audit.json", "동결본 3종"],
    }
    return payload, fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true", help="results/ 에 기록한다")
    a = ap.parse_args()
    payload, fails = build()
    P = print
    P("=" * 78)
    P("cross-model replication 정본 집계 (읽기 전용 · LLM 0회)")
    P("=" * 78)
    it = payload["integrity"]
    P(f"  valid chunks {it['valid_chunks']} · rows {it['n_rows']}/{it['expected']} · "
      f"FAILED {it['failed']} · 중복 {it['duplicate']} · 누락 {it['missing']}")
    P(f"  frozen task identity {'🟢 PASS' if it['frozen_task_identity'] else '🔴 FAIL'} · "
      f"밴드 {it['bands']}")
    c = payload["preregistered_results"]["counts_over_30_tasks"]["justified_resolution"]
    P(f"  justified resolution  sonnet {c['sonnet_V']} · gemini {c['gemini_V']} · R0 {c['R0']}")
    for n, t in payload["preregistered_tests"]["tests"].items():
        P(f"  {n:<18} 불일치 {t['discordant_b']}:{t['discordant_c']} · "
          f"p={t['p_exact_two_sided']} · 유의 {t['significant']}")
    sc = payload["success_criterion"]
    P(f"  directional criterion  {'🟢 met' if sc['met'] else '🔴 not met'} "
      f"(유의성을 요구하지 않는 기준)")
    if fails:
        raise SystemExit("\n🔴 assertion 실패 — 파일을 쓰지 않는다:\n  "
                         + "\n  ".join(fails))
    P("\n  🟢 assertion 전부 통과 (unblind 확정값에서 재현됨)")
    if a.save:
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        P(f"  🟢 기록 → {OUT.relative_to(ROOT)}")
    else:
        P("  (쓰지 않았다 — 기록하려면 --save)")


if __name__ == "__main__":
    main()
