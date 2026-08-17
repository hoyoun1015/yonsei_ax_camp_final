"""본실행 결과 집계 + 자동 sanity check. **읽기 전용 · LLM 호출 0회.**

이 스크립트는 **아무것도 채점하지 않는다.** `main_run.py` 가 기록한 값을 읽어 모으고
검사만 한다. 채점 정의를 다시 구현하면 두 곳이 갈라지므로 하지 않는다
(2026-08-11 외부 검토에서 같은 종류의 사고가 있었다).

동결본·프롬프트·평가 규칙을 수정하지 않는다. 어떤 파일에도 쓰지 않는다 —
`--save` 를 줄 때만 `results/main_run_aggregate.json` 하나를 쓴다.

**🔴 해시가 다른 배치를 섞지 않는다.** 구 Batch 1(2026-08-12, 무효 판정)은 수정 전
프롬프트 해시로 돌았다. 그것을 새 결과와 합치면 서로 다른 시스템의 결과를 더하는
것이 된다. 현재 동결본과 해시가 일치하는 배치만 집계하고, 나머지는 사유와 함께
제외 목록에 남긴다.

사용:
    python3 src/vccl/scoring/aggregate.py            # 집계 + sanity check
    python3 src/vccl/scoring/aggregate.py --check    # sanity check 만
    python3 src/vccl/scoring/aggregate.py --save     # results/ 에 기록
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents.main_run import content_sha256  # noqa: E402  (해시 규약 재사용)

STAGE_A = ROOT / "data" / "tasks" / "frozen_rules_v1.json"
STAGE_B = ROOT / "data" / "tasks" / "frozen_stage_b_v1.json"
ORDER = ROOT / "data" / "tasks" / "execution_order_v1.json"
HEADROOM = ROOT / "results" / "oracle_headroom_audit.json"
CONDITIONS = ("V", "V-tau")
ABORT_PCT = 5.0
TAU_MARKER = "방법오차 τ"          # `loop._tau_block` 이 넣는 표지
# τ 를 받아야 하는 단계. `_pi_operationalize` 는 **설계상 제외** — 식별에는 τ 가
# 불필요하다. 이 구분을 놓치면 정상 실행에 거짓 경보가 난다(실제로 한 번 냈다).
TAU_STAGES = frozenset({"choose_level", "review", "conclude"})
N_TARGET = 92


# ── 배치 수집 ────────────────────────────────────────────────────────
def current_hashes() -> dict[str, str]:
    return {
        "stage_a": json.loads(STAGE_A.read_text())["sha256"],
        "stage_b": json.loads(STAGE_B.read_text())["sha256"],
        "execution_order": json.loads(ORDER.read_text())["sha256"],
    }


def collect() -> tuple[list[dict], list[dict]]:
    """현재 동결본과 해시가 맞는 배치만 고른다. 제외 사유를 함께 남긴다."""
    want = current_hashes()
    used, skipped = [], []
    for d in sorted(p for p in (ROOT / "experiments").glob("main_b*") if p.is_dir()):
        f = d / "batch_result.json"
        if not f.exists():
            skipped.append({"dir": d.name, "reason": "batch_result.json 없음 "
                                                     "(실행 중이거나 중단됨)"})
            continue
        p = json.loads(f.read_text())
        got = p.get("frozen", {})
        diff = [k for k in want if got.get(k) != want[k]]
        if diff:
            skipped.append({"dir": d.name, "batch": p.get("batch"),
                            "reason": f"동결 해시 불일치 {diff} — 수정 전 시스템의 "
                                      "결과다. 섞지 않는다",
                            "their_stage_b": (got.get("stage_b") or "?")[:16] + "…"})
            continue
        p["_dir"] = d.name
        used.append(p)
    return used, skipped


def merge(batches: list[dict]) -> dict[str, list[dict]]:
    rows: dict[str, list[dict]] = {c: [] for c in CONDITIONS}
    for b in batches:
        for c in CONDITIONS:
            rows[c].extend(b["rows"].get(c, []))
    return rows


# ── 집계 ─────────────────────────────────────────────────────────────
def rate(rows: list[dict], key: str) -> tuple[int, int]:
    v = [r[key] for r in rows if r.get(key) is not None]
    return sum(bool(x) for x in v), len(v)


def fmt(n: int, d: int) -> str:
    return f"{n}/{d}" + (f" ({100 * n / d:.0f}%)" if d else "")


def baseline_rows(policy: str, tids: set[str]) -> list[dict]:
    """headroom audit 의 과제별 행에서 같은 과제만 뽑는다 — 과제 매칭 비교."""
    if not HEADROOM.exists():
        return []
    h = json.loads(HEADROOM.read_text())
    return [r for r in h["rows"].get(policy, []) if r["tid"] in tids]


def measured_cost(rs: list[dict]) -> tuple[float, int, int]:
    """**실측 wall time 기준** 총비용. rows 를 수정하지 않는다.

    🔴 DECISION_LOG 2026-08-14 (1) 정정 ②.
    `rows["cost_s"]` 는 `cached.LEVEL_COST_S` 의 «표시용 근사»(L3 = 구조당 40초)다.
    ALL_L3·R0 는 psi4 **실측 wall time** 이므로 그대로 비교하면 기준이 섞인다 —
    그렇게 만든 18.1% / 40.6% 는 무효였다.

    과제별 L3 비용은 2.9초~3,631초로 1,250배 편차가 있어 고정값으로 대체할 수 없다.
    여기서는 근사 비용에서 L1/L3 **실행 횟수를 역산**한 뒤 실측 단가를 다시 곱한다.
    (역산은 정확하다 — 근사 단가가 상수라 정수해가 유일하다.)

    돌려주는 값: (실측 총비용, L1 실행 횟수, L3 실행 횟수)
    """
    from vccl.agents.r0 import to_task
    from vccl.executor import cached
    from vccl.scoring.headroom import task_cost_s
    from vccl.tasks.pairs import build_pool

    pool = {t["tid"]: t for t in build_pool()}
    c1 = cached.LEVEL_COST_S["L1"] * 2       # 과제 = 구조 2개
    c3 = cached.LEVEL_COST_S["L3"] * 2
    total = n1_tot = n3_tot = 0.0
    for r in rs:
        c = r["cost_s"]
        n3 = int(round(c / c3)) if c >= c3 / 2 else 0
        n1 = int(round((c - n3 * c3) / c1))
        if abs(n3 * c3 + n1 * c1 - c) > 0.005:
            raise ValueError(
                f"{r['tid']}: 실행 횟수를 역산하지 못했다 (cost_s={c}). "
                "비용 근사 단가가 바뀌었는지 확인할 것")
        total += n1 * c1 + n3 * task_cost_s(to_task(pool[r["tid"]]), "L3")
        n1_tot += n1
        n3_tot += n3
    return total, int(n1_tot), int(n3_tot)


def report(rows: dict[str, list[dict]], batches: list[dict], skipped: list[dict]):
    done = {r["tid"] for r in rows["V"]}
    n = len(done)
    P = print
    P("=" * 78)
    P("본실행 집계 — 읽기 전용 · LLM 호출 0회")
    P("=" * 78)
    P(f"  집계한 배치  {[b['batch'] for b in batches] or '없음'} · 과제 {n}/{N_TARGET}")
    if skipped:
        P("\n  제외한 디렉터리")
        for s in skipped:
            P(f"    ⊘ {s['dir']}")
            P(f"        {s['reason']}")
    if n < N_TARGET:
        P(f"\n  ⚠️ **잠정치다.** {N_TARGET - n}개 과제가 남아 있어 확증 결과가 아니다.")
    if not n:
        return

    # 실패 처리 — 사전등록 규칙
    P(f"\n{'-' * 78}\n실패 처리 (사전등록: 한 condition 에서 FAILED > {ABORT_PCT}% → 무효)")
    invalid = False
    for c in CONDITIONS:
        f = sum(r["failed"] for r in rows[c])
        pct = 100.0 * f / len(rows[c])
        bad = pct > ABORT_PCT
        invalid |= bad
        P(f"  {'🔴' if bad else '🟢'} {c:<7} FAILED {f}/{len(rows[c])} ({pct:.1f}%)")
        for r in rows[c]:
            if r["failed"]:
                P(f"        {r['tid']:<32} {r['error']}")
    if invalid:
        P("  🔴 **이 실행은 사전등록상 무효다.** 부분 결과를 확증 결과로 쓰지 않는다.")

    # ① justified resolution — R0 대비
    P(f"\n{'-' * 78}\n① justified resolution (R0 대비 주 비교축)")
    r0 = baseline_rows("R0", done)
    r0_jr = sum(bool(r["justified_resolution"]) for r in r0)
    P(f"  {'R0 (규칙 기준선)':<24}{fmt(r0_jr, len(r0))}")
    for c in CONDITIONS:
        vn, vd = rate(rows[c], "justified_resolution")
        delta = vn - r0_jr
        P(f"  {c:<24}{fmt(vn, vd)}   R0 대비 {delta:+d}과제")
    P("  🔒 R0 는 구조 쌍·관측량·수준을 오라클로 받는다. 비교가 성립하는 축은")
    P("     «결론 판단» 하나뿐이다 (r0.py 참조).")

    # ② 밴드 C escalation appropriateness
    P(f"\n{'-' * 78}\n② 밴드 C — escalation appropriateness (행동 기준, 기획안 §7.3)")
    for c in CONDITIONS:
        sub = [r for r in rows[c] if r["band"] == "C"]
        if not sub:
            continue
        l3 = sum(bool(r["used_l3"]) for r in sub)
        P(f"  {c:<7} n={len(sub):<3} L3 상승 {l3}/{len(sub)} · "
          f"esc 적절 {fmt(*rate(sub, 'escalation_appropriate'))} · "
          f"justified {fmt(*rate(sub, 'justified_resolution'))} · "
          f"ABSTAIN {sum(1 for r in sub if r['stated'] == 'ABSTAIN')}")
    P("  ⚠️ headroom audit 의 +40 은 정책을 밴드에서 직접 매핑해 구성상 92/92 가")
    P("     나온 값이다. 위 숫자와 같은 표에 두지 않는다 (DECISION_LOG 08-12 (3)).")

    # ③ V vs V−τ — 과대해석 / 증거 충분성
    P(f"\n{'-' * 78}\n③ V vs V−τ — 과대해석(§7.1 주 지표) · 증거 충분성")
    for c in CONDITIONS:
        P(f"  {c:<7} 과대해석 {fmt(*rate(rows[c], 'overinterpretation'))} · "
          f"과도한 신중 {fmt(*rate(rows[c], 'over_cautious'))} · "
          f"증거충분 {fmt(*rate(rows[c], 'evidence_adequate'))} · "
          f"단정 {fmt(*rate(rows[c], 'resolved'))}")
    ov = {c: rate(rows[c], "overinterpretation")[0] for c in CONDITIONS}
    if ov["V"] == ov["V-tau"] == 0:
        P("  ⚠️ **두 조건 모두 0 이면 §7.1 이 이 대비를 잡아내지 못한 것이다.**")
        P("     차이가 있다면 over-caution 축에서 나온다 — 멘토링 Q2 와 직결된다.")

    # ④ 비용 — **실측 wall time 기준만 쓴다** (DECISION_LOG 2026-08-14 (1) 정정 ②)
    P(f"\n{'-' * 78}\n④ 계산비용 — ALL_L3 대비  **psi4 실측 wall time 기준**")
    all_l3 = baseline_rows("ALL_L3", done)
    c_all = sum(r["cost_s"] for r in all_l3)
    c_r0 = sum(r["cost_s"] for r in r0)
    P(f"  {'ALL_L3 (전량 고비용)':<22}{c_all:>10.0f}초  100.0%")
    P(f"  {'R0 (전량 저비용)':<22}{c_r0:>10.0f}초  "
      f"{100 * c_r0 / c_all if c_all else 0:>5.1f}%")
    for c in CONDITIONS:
        cc, n1, n3 = measured_cost(rows[c])
        l3 = sum(bool(r["used_l3"]) for r in rows[c])
        P(f"  {c:<22}{cc:>10.0f}초  {100 * cc / c_all if c_all else 0:>5.1f}%"
          f"   최종 수준 L3 {l3}/{len(rows[c])} · L3 실행 {n3}회 · L1 실행 {n1}회")
    P("  🔒 «표시용 근사»(L3 = 구조당 40초)로 잰 18.1% / 40.6% 는 무효다 —")
    P("     ALL_L3 와 기준이 달랐다. 위 값은 양쪽 모두 실측 wall time 이다.")
    P("  🔒 비용만 단독으로 주장하지 않는다 — 품질(justified resolution)을 함께 본다.")
    jr_v = rate(rows["V"], "justified_resolution")[0]
    jr_all = sum(bool(r["justified_resolution"]) for r in all_l3)
    cc_v = measured_cost(rows["V"])[0]
    P(f"\n  📌 보고 문구 (고정) — ALL_L3 의 {jr_all}개 대비 **{jr_v}개의 justified")
    P(f"     resolution 을 {100 * cc_v / c_all:.1f}% 의 계산비용으로 달성**")
    P("     («…% 성능» 같은 비율 표현을 쓰지 않는다)")

    # ⑤ 오류 분해
    P(f"\n{'-' * 78}\n⑤ 오류 분해 (§7.4) — tool-limited 대 agent-limited")
    for c in CONDITIONS:
        ec = Counter(r["error_class"] for r in rows[c] if r["error_class"])
        tot = sum(ec.values())
        P(f"  {c:<7} " + " · ".join(
            f"{k} {v}" for k, v in sorted(ec.items(), key=lambda x: -x[1])) +
          f"   (n={tot})")
    P("  🔒 이 분석에서 tool-limited 로 분류된 과제는 현재 사용한 계산 도구와 수준")
    P("     에서 에이전트 판단만 고쳐서는 해결하기 어려운 경우다. 더 높은 수준이나")
    P("     다른 계산 절차로 줄일 수 있는지는 이 결과만으로 알 수 없다.")

    # ⑥ 식별
    P(f"\n{'-' * 78}\n⑥ 구조 식별 (identification)")
    for c in CONDITIONS:
        P(f"  {c:<7} 자율식별형 정확도 {fmt(*rate(rows[c], 'identification_accuracy'))} · "
          f"식별 오류 {sum(1 for r in rows[c] if r['identification_correct'] is False)}건")
        for mode in ("autonomous", "paired"):
            sub = [r for r in rows[c] if r.get("identification_mode") == mode]
            if sub:
                P(f"          {mode:<12} n={len(sub):<3} FAILED "
                  f"{sum(r['failed'] for r in sub)} · "
                  f"justified {fmt(*rate(sub, 'justified_resolution'))}")
    P("  🔒 paired 는 식별을 «수행하지 않는다» — 정확도 분모에서 뺀다.")
    P("     R0 도 쌍을 오라클로 받으므로 이 축에서 R0 와 비교하지 않는다.")

    # 대표 사례
    cases = [c for b in batches for c in b.get("case_study_candidates", [])]
    P(f"\n{'-' * 78}\n대표 사례 후보 {len(cases)}건")
    for c in sorted(cases, key=lambda x: -x["score"])[:5]:
        P(f"  [{c['score']:>2}] {c['tid']} · {c['condition']} · 밴드 {c['band']}")


# ── 자동 sanity check ────────────────────────────────────────────────
def checks(batches: list[dict], rows: dict[str, list[dict]]) -> list[tuple]:
    out: list[tuple] = []

    def add(name, ok, detail=""):
        out.append((name, bool(ok), detail))

    # ── 배치가 없어도 항상 도는 검사 — 실행 직전 점검용 ────────────────
    # 1) 동결본 자체가 무결한가
    for p in (STAGE_A, STAGE_B):
        emb = json.loads(p.read_text())["sha256"]
        got, conv = content_sha256(p)
        add(f"{p.name} 내용 해시", got == emb, conv)

    # 2) 실행 순서 산출물이 현재 Stage B 를 참조하는가
    o = json.loads(ORDER.read_text())
    body = {k: v for k, v in o.items() if k != "sha256"}
    add("execution_order 내용 해시",
        hashlib.sha256(json.dumps(body, ensure_ascii=False, indent=2,
                                  sort_keys=True).encode()).hexdigest() == o["sha256"])
    add("execution_order → 현재 Stage B 참조",
        o["derived_from"]["sha256"] == json.loads(STAGE_B.read_text())["sha256"],
        f"참조 {o['derived_from']['sha256'][:16]}…")

    # 3) 프롬프트 소스 해시가 동결본과 일치하는가
    sb = json.loads(STAGE_B.read_text())
    for rel, wanted in sb["execution_protocol"]["prompt_source_sha256"].items():
        got = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        add(f"{rel.split('/')[-1]} 프롬프트 해시", got == wanted, f"{wanted[:16]}…")

    # 4) 과제 전량이 가설을 갖는가 — Batch 1 무효의 직접 원인
    try:
        from vccl.tasks.pairs import build_pool
        pool = {t["tid"]: t for t in build_pool()}
        ids = sb["primary_experiment"]["main_benchmark"]["task_ids"]
        no_hyp = [t for t in ids
                  if not ((pool[t].get("hypothesis") or {}).get("neutral") or "").strip()]
        add("N=92 전량 가설 존재", not no_hyp, f"누락 {len(no_hyp)}개")
    except Exception as e:  # noqa: BLE001
        add("N=92 전량 가설 존재", False, f"확인 실패: {e}")

    if not batches:
        out.append(("(배치 결과 없음 — 아래 배치별 검사는 생략)", True,
                    "실행 전이거나 유효 배치가 아직 없다"))
        return out

    # 5) 실행 시점 해시 == 현재 해시
    want = current_hashes()
    for b in batches:
        same = all(b["frozen"].get(k) == want[k] for k in want)
        add(f"b{b['batch']} 동결 해시 == 현재", same,
            f"stage_b {b['frozen']['stage_b'][:16]}…")

    # 3) 과제 커버리지 — 조건별로 정확히 1회씩
    order = json.loads(ORDER.read_text())
    for b in batches:
        planned = set(order["batches"][b["batch"] - 1]["task_ids"])
        for c in CONDITIONS:
            got = [r["tid"] for r in b["rows"][c]]
            add(f"b{b['batch']} {c} 과제 커버리지",
                set(got) == planned and len(got) == len(planned),
                f"계획 {len(planned)} · 실행 {len(got)} · 중복 "
                f"{len(got) - len(set(got))}")

    # 4) 원장 무결 — 줄 수 일치 · 파싱 실패 0
    for b in batches:
        f = ROOT / "experiments" / b["_dir"] / "calls.jsonl"
        lines = f.read_text().splitlines() if f.exists() else []
        bad = 0
        for ln in lines:
            try:
                json.loads(ln)
            except Exception:  # noqa: BLE001
                bad += 1
        add(f"b{b['batch']} 원장 무결", f.exists() and not bad
            and len(lines) == b["ledger_summary"]["n_calls"],
            f"{len(lines)}줄 · 요약 {b['ledger_summary']['n_calls']} · 파싱실패 {bad}")

    # 5) 🔴 ablation 무결성 — 주 대비가 실제로 성립했는지 원장으로 확인한다
    #
    # ⚠️ «V 의 모든 프롬프트에 τ 가 있다» 가 아니다. `_pi_operationalize` 는 설계상
    # τ 를 받지 않는다(식별 단계에는 τ 가 불필요하다). 단계별로 봐야 한다 —
    # 이 구분을 놓치면 정상 실행에 대해 거짓 경보가 난다.
    for b in batches:
        f = ROOT / "experiments" / b["_dir"] / "calls.jsonl"
        agg: dict[tuple[str, str], dict[str, int]] = {}
        for ln in (f.read_text().splitlines() if f.exists() else []):
            c = json.loads(ln)
            if c["condition"] not in CONDITIONS:
                continue
            stage = c["prompt_version"].split("#")[0].split("/")[-1]
            d = agg.setdefault((c["condition"], stage), {"with": 0, "without": 0})
            d["with" if TAU_MARKER in c["prompt"] else "without"] += 1

        bad = []
        for (cond, stage), d in sorted(agg.items()):
            expect_tau = cond == "V" and stage in TAU_STAGES
            wrong = d["without"] if expect_tau else d["with"]
            if wrong:
                bad.append(f"{cond}/{stage}({wrong})")
        add(f"b{b['batch']} ablation 무결성 (τ 블록)", not bad,
            (f"위반 {bad}" if bad else
             f"단계 {len(agg)}종 전부 기대와 일치 — V 는 "
             f"{'·'.join(sorted(TAU_STAGES))} 에 τ, V−τ 는 전 단계 τ 없음"))

    # 6) 가설 없이 채점된 과제 — Batch 1 무효의 원인
    ghost = [r["tid"] for c in CONDITIONS for r in rows[c]
             if not r["failed"] and r.get("identification_mode") == "paired"
             and r.get("specified_pair_given") is not True]
    add("paired 과제가 쌍 지정을 받았는가", not ghost, f"미지정 {ghost or '없음'}")

    # 7) 식별 오류가 크래시로 처리되지 않았는가
    crashed = [r["tid"] for c in CONDITIONS for r in rows[c]
               if r["error"] and "KeyError" in str(r["error"])]
    add("식별 오류가 크래시가 아닌가", not crashed, f"KeyError 발생 {crashed or '없음'}")

    # 8) 채점 내부 정합성 — 과대해석 정의
    viol = []
    for c in CONDITIONS:
        for r in rows[c]:
            if r["failed"] or r.get("evidence_adequate") is None:
                continue
            expect = (not r["evidence_adequate"]) and r["stated"] != "ABSTAIN"
            if bool(r["overinterpretation"]) != expect:
                viol.append(f"{c}/{r['tid']}")
    add("과대해석 정의 정합성", not viol, f"불일치 {viol[:3] or '없음'}")

    # 9) 식별 오류 시 결론 정확성이 오답 처리됐는가
    viol2 = [f"{c}/{r['tid']}" for c in CONDITIONS for r in rows[c]
             if r.get("identification_correct") is False and not r["failed"]
             and (r.get("reference_direction_correct")
                  or r.get("justified_resolution"))]
    add("식별 오류 → 결론 오답 처리", not viol2, f"미처리 {viol2 or '없음'}")

    # 10) trajectory 보존 — 대표 사례 후보의 사슬이 완결됐는가
    for b in batches:
        cs = b.get("case_study_candidates", [])
        broken = [c["tid"] for c in cs
                  if not {"operationalize", "execute", "review"} <=
                  {t["step"] for t in c.get("trace", [])}]
        add(f"b{b['batch']} 대표사례 trajectory 완결", not broken,
            f"후보 {len(cs)}건 · 불완전 {broken or '없음'}")

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="sanity check 만")
    ap.add_argument("--save", action="store_true",
                    help="results/main_run_aggregate.json 에 기록")
    args = ap.parse_args()

    batches, skipped = collect()
    rows = merge(batches)

    if not args.check:
        report(rows, batches, skipped)

    print(f"\n{'=' * 78}\n자동 sanity check\n{'=' * 78}")
    res = checks(batches, rows)
    for name, ok, detail in res:
        print(f"  {'🟢' if ok else '🔴'} {name:<40} {detail}")
    n_bad = sum(1 for _, ok, _ in res if not ok)
    print(f"\n  {'🟢 전부 통과' if not n_bad else f'🔴 {n_bad}건 실패'}")

    if args.save and batches:
        dest = ROOT / "results" / "main_run_aggregate.json"
        dest.write_text(json.dumps({
            "batches": [b["batch"] for b in batches],
            "skipped": skipped,
            "n_tasks": len({r["tid"] for r in rows["V"]}),
            "provisional": len({r["tid"] for r in rows["V"]}) < N_TARGET,
            "frozen": current_hashes(),
            "rows": rows,
            "sanity_check": [{"name": n, "pass": o, "detail": d} for n, o, d in res],
        }, ensure_ascii=False, indent=2) + "\n")
        print(f"\n→ {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
