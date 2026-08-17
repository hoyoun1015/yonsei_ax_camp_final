"""본실행 — V · V−τ. **동결본을 소비하는 확증 실행이다.**

`smoke.py` 의 확장이 아니라 별도 진입점이다. smoke 는 main N=92 를 **제외**하지만
여기서는 그 92개가 대상이다.

**동결 이후 아무것도 바꾸지 않는다.** 프롬프트·채점·과제 선택·τ 는 전부 동결본에서
읽어 적용만 한다. 시작 전에 해시를 검증하고, 하나라도 어긋나면 실행하지 않는다.

**조건 두 개의 차이는 τ 블록 하나뿐이다.**

    V       run_task(be, spec, tau)     — τ 모듈 있음
    V−τ     run_task(be, spec, None)    — `_tau_block` 이 빈 문자열을 돌려준다

같은 과제의 두 조건을 **연속으로** 실행한다(같은 배치·인접 시점). 과제 인덱스 짝수는
V 먼저, 홀수는 V−τ 먼저로 번갈아 조건에 고정된 순서 효과를 남기지 않는다.
호출은 매번 새 subprocess 이고 대화 상태를 공유하지 않으므로 조건 간 이월은 없다.

**사전등록된 실패 규칙만 적용한다** (DECISION_LOG 2026-08-11 (4)) —
재시도 3경로 실패 → FAILED · 후보에 없는 라벨 → FAILED · 라운드 상한 → FAILED 아님 ·
캐시 미스 → 중단. **한 condition 에서 FAILED 가 5% 를 넘으면 그 실행은 무효다.**

**로그는 지우지 않는다.** `calls.jsonl` 에서 대표 사례 trajectory 를 뽑는다.

사용:
    python3 src/vccl/agents/main_run.py --batch 1
    python3 src/vccl/agents/main_run.py --batch 1 --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents import quota_ledger  # noqa: E402
from vccl.agents.backend import Backend, Ledger, read_quota  # noqa: E402
from vccl.agents.loop import TaskSpec, anonymize, run_task  # noqa: E402
from vccl.agents.pilot import phrase  # noqa: E402
from vccl.agents.r0 import to_task  # noqa: E402
from vccl.scoring.headroom import (  # noqa: E402
    justified_resolution, reference_direction_correct,
)
from vccl.scoring.labels import (  # noqa: E402
    Band, Conclusion, ErrorClass, IdentificationMode, Run, band_of,
    correct_escalation, error_class, evidence_adequate, is_correct,
    is_over_cautious, is_overinterpretation, oracle_action,
)
from vccl.tasks import prompts  # noqa: E402
from vccl.tasks.gmtkn import describe, load_reactions, species_map  # noqa: E402
from vccl.tasks.pairs import build_pool, load_tau  # noqa: E402

GMTKN = ROOT / "data" / "reference" / "gmtkn55"
STAGE_A = ROOT / "data" / "tasks" / "frozen_rules_v1.json"
STAGE_B = ROOT / "data" / "tasks" / "frozen_stage_b_v1.json"
ORDER = ROOT / "data" / "tasks" / "execution_order_v1.json"
ABORT_PCT = 5.0
CONDITIONS = ("V", "V-tau")


# ── 동결 검증 ────────────────────────────────────────────────────────
def _digest(obj: dict) -> str:
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True).encode()).hexdigest()


def content_sha256(path: Path) -> tuple[str, str]:
    """동결본의 내용 해시. 파일 바이트가 아니라 «스탬프 전 payload» 를 해싱한다.

    🔴 **두 freeze 스크립트의 규약이 다르다.** 어느 쪽인지 알아서 맞춘다.

      freeze.py           provenance.repo_commit 을 payload 안에 넣고 해싱한다
      freeze_stage_b.py   digest 를 찍은 **뒤에** repo_commit 을 붙인다

    한쪽 규약만 가정하면 멀쩡한 동결본이 «어긋났다» 로 뜬다. 어느 규약으로 맞았는지
    함께 돌려주어 조용히 통과시키지 않는다.
    """
    p = json.loads(path.read_text())
    emb = p.pop("sha256", None)

    if _digest(p) == emb:
        return emb, "repo_commit 포함"

    prov = p.get("provenance")
    if isinstance(prov, dict) and "repo_commit" in prov:
        prov.pop("repo_commit")
        if not prov:
            p.pop("provenance")
        if _digest(p) == emb:
            return emb, "repo_commit 스탬프 후 추가"

    return _digest(p), "🔴 어느 규약으로도 맞지 않는다"


def verify_frozen() -> dict:
    """동결본과 프롬프트 소스를 검증한다. 하나라도 어긋나면 실행하지 않는다."""
    sb = json.loads(STAGE_B.read_text())
    checks, ok = [], True

    for path in (STAGE_A, STAGE_B):
        emb = json.loads(path.read_text())["sha256"]
        got, convention = content_sha256(path)
        ok &= got == emb
        checks.append((path.name, got == emb, f"{emb[:16]}…  ({convention})"))

    for rel, want in sb["execution_protocol"]["prompt_source_sha256"].items():
        got = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        ok &= got == want
        checks.append((rel, got == want, f"{want[:16]}…"))

    order = json.loads(ORDER.read_text())
    emb = order["sha256"]
    o = {k: v for k, v in order.items() if k != "sha256"}
    got = hashlib.sha256(
        json.dumps(o, ensure_ascii=False, indent=2, sort_keys=True).encode()).hexdigest()
    ok &= got == emb
    checks.append((ORDER.name, got == emb, f"{emb[:16]}…"))
    ok &= order["derived_from"]["sha256"] == json.loads(STAGE_B.read_text())["sha256"]

    return {"ok": ok, "checks": checks, "stage_b": sb, "order": order}


# ── 과제 → 에이전트 입력 ─────────────────────────────────────────────
def to_spec(entry: dict) -> TaskSpec:
    """과제 → 에이전트 입력. 참조값·정답은 담기지 않는다.

    **쌍 지정형(paired)은 여기서 가설 문장을 렌더링한다.** 구조 라벨이 과제마다 실행
    시점에 익명화되므로 풀에는 자리표시자를 둔 템플릿이 들어 있다
    (DECISION_LOG 2026-08-12 (5)). 자율 식별형 경로는 예전 그대로다.
    """
    task = to_task(entry)
    rxns = load_reactions(GMTKN, task.subset)
    smap = species_map(rxns)
    desc = {x: describe(GMTKN / task.subset / x / "struc.xyz")
            for x in {y for r in rxns for y in r.names}}
    members = sorted(x for x in desc if smap[x] == smap[task.names[0]])
    to_label, from_label = anonymize(members, task.tid)

    hyp = (entry.get("hypothesis") or {}).get("neutral")
    specified = None
    if entry["identification"] == IdentificationMode.PAIRED.value:
        claimed = task.claimed_more_stable
        other = next(n for n in task.names if n != claimed)
        specified = (to_label[claimed], to_label[other])
        hyp = prompts.render_paired(hyp, *specified)

    return TaskSpec(
        task_id=task.tid, subset=task.subset, rtype=task.rtype,
        hypothesis=hyp,
        candidates={to_label[m]: phrase(desc[m], "L2") for m in members},
        real_names=from_label, reference_pair=tuple(task.names),
        ref_names=task.names, ref_coeffs=task.coeffs,
        specified_pair=specified)


# ── 채점 ─────────────────────────────────────────────────────────────
def escalation_appropriate(task, res, tau) -> bool | None:
    """**기획안 §7.3 — 행동 기준.**

    SUFFICIENT(A·B) 불필요하게 올리지 않았는가 · ESCALATION(C) 올렸는가 ·
    FUTILE(D) 포기했는가.

    ⚠️ headroom audit 의 `escalation_action` 은 정책을 밴드에서 직접 매핑하므로
    완벽 정책이 구성상 92/92 가 된다. 실제 에이전트에는 그것을 쓰지 않는다.
    """
    if res.level_used is None:
        return None
    b = band_of(task, tau)
    if b is Band.C:
        return res.level_used == "L3"
    if b is Band.D:
        return res.conclusion is Conclusion.ABSTAIN
    return res.level_used == "L1"


def faithful_in_agent_frame(res, tau, rtype: str) -> bool:
    """에이전트가 «자기가 본 숫자» 에 충실했는가. 참조 쌍을 쓰지 않는다.

    식별이 틀려도 정의된다 — `delta_evidence` 는 에이전트가 지목한 쌍의
    E(더 안정하다고 본 구조) − E(비교 대상) 이므로, 음수면 자기 증거가 가설을
    지지하는 방향이다. 이 축이 있어야 «식별은 틀렸지만 자기 증거에는 충실했다» 와
    «둘 다 틀렸다» 를 가를 수 있다.
    """
    d = res.delta_evidence
    if not evidence_adequate(d, rtype, res.level_used, tau):
        return res.conclusion is Conclusion.ABSTAIN
    if res.conclusion is Conclusion.ABSTAIN:
        return False
    return res.conclusion is (Conclusion.SUPPORTED if d < 0 else Conclusion.REFUTED)


def score_run(entry: dict, res, tau) -> dict:
    task = to_task(entry)
    band = band_of(task, tau).value
    paired = entry["identification"] == IdentificationMode.PAIRED.value
    # 쌍 지정형은 «식별을 수행하지 않는다» — 정확도 지표의 분모에서 뺀다.
    # 그래도 지정을 따르지 않았다면 이상이므로 값 자체는 남긴다.
    ident_perf = None if paired else res.identification_correct
    mismatch = res.identification_correct is False

    out = {
        "tid": task.tid, "band": band, "abs_ref": round(task.abs_ref, 4),
        "identification_mode": entry["identification"],
        "failed": res.conclusion is None, "error": res.error,
        "level_used": res.level_used, "rounds": res.rounds,
        "branch_a": res.branch_a, "branch_b": res.branch_b,
        # ── 식별 축을 분리해 남긴다 (DECISION_LOG 2026-08-12 (5)) ──────
        "selected_pair": list(res.selected_pair) if res.selected_pair else None,
        "gold_pair": list(res.gold_pair) if res.gold_pair else None,
        "identification_correct": res.identification_correct,
        "identification_performed": not paired,
        "identification_accuracy": ident_perf,     # 지표용 — paired 는 None
        "specified_pair_given": res.specified_pair_given,
        "delta_evidence": (None if res.delta_evidence is None
                           else round(res.delta_evidence, 4)),
        "delta_gold_convention": (None if res.delta_gold_convention is None
                                  else round(res.delta_gold_convention, 4)),
        "ambiguity_flagged": res.ambiguity_flagged,
        "escalation_answer": correct_escalation(task, tau).value,
        "escalation_appropriate": escalation_appropriate(task, res, tau),
        "used_l3": res.level_used == "L3",
        "cost_s": round(sum(t.get("cost_s", 0.0) for t in res.trace
                            if t.get("step") == "execute"), 3),
    }
    if res.conclusion is None:
        return out | {k: None for k in (
            "stated", "delta_calc", "level_relative_correct",
            "reference_direction_correct", "justified_resolution", "resolved",
            "overinterpretation", "over_cautious", "error_class",
            "evidence_adequate", "hypothesis_fidelity")}

    # 자기 증거 축(§7.1)은 «에이전트가 고른 쌍» 으로 잰다. 참조값을 쓰지 않는 지표라
    # 식별이 틀려도 정의되며, 그래야 식별 오류가 판단에 어떻게 전파됐는지 보인다
    adequate = evidence_adequate(res.delta_evidence, task.rtype, res.level_used, tau)
    ev_run = Run(res.level_used, res.delta_evidence, res.conclusion)
    common = {
        "stated": res.conclusion.value,
        "delta_calc": round(res.delta_calc, 4),
        "resolved": res.conclusion is not Conclusion.ABSTAIN,
        "evidence_adequate": adequate,
        "overinterpretation": is_overinterpretation(task, ev_run, tau),
        "over_cautious": is_over_cautious(task, ev_run, tau),
        "hypothesis_fidelity": bool(res.hypothesis_restated),
    }

    if mismatch:
        # 🔴 식별이 틀렸다. 에이전트는 «다른 두 구조» 를 비교했으므로 원 가설에 대한
        # 결론은 오답이다. 자기 증거 축은 위에서 정상 채점했다.
        faithful = faithful_in_agent_frame(res, tau, task.rtype)
        return out | common | {
            "oracle_at_level": oracle_action(task, res.level_used, tau).value,
            "level_relative_correct": False,
            "reference_direction_correct": False,
            "justified_resolution": False,
            "faithful_to_own_evidence": faithful,
            # 도구는 시킨 대로 돌았다. 잘못된 대상을 고른 것은 에이전트다
            "error_class": (ErrorClass.AGENT_LIMITED if faithful
                            else ErrorClass.COMPOUND).value,
            "scoring_note": "identification mismatch — 결론 정확성은 오답 처리, "
                            "자기 증거 축은 고른 쌍으로 채점",
        }

    run = Run(res.level_used, res.delta_calc, res.conclusion)
    return out | common | {
        "oracle_at_level": oracle_action(task, res.level_used, tau).value,
        "level_relative_correct": is_correct(task, run, tau),
        "reference_direction_correct": reference_direction_correct(task, run),
        "justified_resolution": justified_resolution(task, run, tau),
        "error_class": error_class(task, run, tau).value,
    }


def case_study_score(row: dict, res) -> tuple[int, list[str]]:
    """대표 사례 후보 점수. 멘토님이 관심 보인 «계산 과정» 이 드러나는 trajectory.

    자연어 가설 → 구조 식별 → xTB → Reviewer 증거 부족 판단 → DFT escalation →
    결과 해석 → 최종 결론. 이 사슬이 **전부** 보이는 것을 높게 친다.
    """
    marks, s = [], 0
    levels = [t["level"] for t in res.trace if t.get("step") == "execute"]
    if row["branch_a"] >= 1:
        s += 3
        marks.append("Reviewer 가 증거 부족으로 escalate 요구")
    if levels[:1] == ["L1"] and "L3" in levels:
        s += 3
        marks.append("L1(xTB) → L3(DFT) 실제 상승")
    if row["identification_correct"]:
        s += 2
        marks.append("구조 식별 정확")
    if row["band"] == "C":
        s += 2
        marks.append("밴드 C — escalation 이 값을 하는 유일한 구간")
    if not row["failed"]:
        s += 1
    if row["justified_resolution"]:
        s += 1
        marks.append("근거 있는 해결")
    if row["branch_b"] >= 1:
        s += 1
        marks.append("분기 B(재조작화) 사용")
    if row["hypothesis_fidelity"]:
        s += 1
    return s, marks


# ── 집계 ─────────────────────────────────────────────────────────────
def rate(rows: list[dict], key: str) -> tuple[int, int]:
    """None(FAILED·미해당)을 분모에서 뺀다. 개수를 함께 돌려준다."""
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(bool(v) for v in vals), len(vals)


def summarize(cond: str, rows: list[dict]) -> dict:
    n = len(rows)
    failed = sum(r["failed"] for r in rows)
    pct = 100.0 * failed / n if n else 0.0
    out = {"condition": cond, "n": n, "failed": failed,
           "failed_pct": round(pct, 2),
           "abort_rule_violated": pct > ABORT_PCT,
           "cost_s": round(sum(r["cost_s"] for r in rows), 1),
           "used_l3": sum(bool(r["used_l3"]) for r in rows),
           "branch_a": sum(r["branch_a"] for r in rows),
           "branch_b": sum(r["branch_b"] for r in rows),
           "error_class": dict(Counter(
               r["error_class"] for r in rows if r["error_class"])),
           "metrics": {}, "by_band": {}}
    for k in ("justified_resolution", "reference_direction_correct",
              "level_relative_correct", "resolved", "overinterpretation",
              "over_cautious", "escalation_appropriate",
              "identification_accuracy", "hypothesis_fidelity"):
        c, d = rate(rows, k)
        out["metrics"][k] = {"n": c, "d": d}
    # 식별 오류가 몇 건이고 그 결론이 어떻게 됐는지는 따로 센다
    mism = [r for r in rows if r["identification_correct"] is False]
    out["identification_mismatch"] = {
        "n": len(mism),
        "tids": [r["tid"] for r in mism],
        "faithful_to_own_evidence": sum(
            bool(r.get("faithful_to_own_evidence")) for r in mism),
        "note": "식별이 틀린 과제. 결론 정확성은 오답 처리하되 자기 증거 축은 "
                "고른 쌍으로 채점했다 — 크래시로 빠뜨리지 않는다",
    }
    out["by_identification_mode"] = {
        m: {"n": sum(1 for r in rows if r["identification_mode"] == m),
            "failed": sum(r["failed"] for r in rows
                          if r["identification_mode"] == m),
            "justified_resolution": rate(
                [r for r in rows if r["identification_mode"] == m],
                "justified_resolution")}
        for m in sorted({r["identification_mode"] for r in rows})}
    for b in ("A", "B", "C", "D"):
        sub = [r for r in rows if r["band"] == b]
        if not sub:
            continue
        out["by_band"][b] = {
            "n": len(sub),
            "used_l3": sum(bool(r["used_l3"]) for r in sub),
            **{k: {"n": rate(sub, k)[0], "d": rate(sub, k)[1]}
               for k in ("justified_resolution", "escalation_appropriate",
                         "overinterpretation")},
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True, choices=(1, 2, 3))
    ap.add_argument("--model", default=None, help="기본값은 동결본의 primary_model")
    ap.add_argument("--dry-run", action="store_true",
                    help="LLM 을 부르지 않고 검증·계획만 출력한다")
    args = ap.parse_args()

    v = verify_frozen()
    print("=" * 78)
    print(f"본실행 — V · V−τ  ·  Batch {args.batch}")
    print("=" * 78)
    print("동결 검증")
    for name, good, h in v["checks"]:
        print(f"  {'🟢' if good else '🔴'} {name:<40} {h}")
    if not v["ok"]:
        raise SystemExit("\n🔴 동결이 어긋났다. 원인을 밝히기 전에 본실행을 시작하지 않는다.")

    sb, order = v["stage_b"], v["order"]
    model = args.model or sb["primary_experiment"]["primary_model"]
    batch = order["batches"][args.batch - 1]
    tau = load_tau()
    pool = {t["tid"]: t for t in build_pool()}
    entries = [pool[t] for t in batch["task_ids"]]

    print(f"\n  모델 {model} · 과제 {len(entries)}개 · 조건 {' · '.join(CONDITIONS)}")
    print(f"  밴드 " + " ".join(f"{k}={v_}" for k, v_ in
                                sorted(batch["band_counts"].items())))
    print(f"  예상 호출 약 {len(entries) * 2 * 4}~{len(entries) * 2 * 5}회 "
          f"(과제당 조건별 4~5회)")
    print(f"  사전등록 실패 규칙  FAILED > {ABORT_PCT}% → 그 실행 무효")

    if args.dry_run:
        print("\n[dry-run] 실행 순서 (과제 · 먼저 도는 조건)")
        for i, e in enumerate(entries):
            first = CONDITIONS[i % 2]
            print(f"  {i + 1:>2}. [{e['tid']:<34}] 밴드 "
                  f"{band_of(to_task(e), tau).value} · {first} 먼저")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "experiments" / f"main_b{args.batch}_{stamp}_{model}"
    ledger = Ledger(out_dir / "calls.jsonl")
    backends = {c: Backend(model=model, ledger=ledger, condition=c)
                for c in CONDITIONS}

    q0 = read_quota()
    print(f"\n  quota(시작)  5시간 "
          f"{q0.get('Gemini Models', {}).get('Five Hour Limit Remaining')} · 주간 "
          f"{q0.get('Gemini Models', {}).get('Weekly Limit Remaining')}")

    rows: dict[str, list[dict]] = {c: [] for c in CONDITIONS}
    cases: list[dict] = []
    t_start = time.time()

    for i, e in enumerate(entries):
        spec = to_spec(e)
        band = band_of(to_task(e), tau).value
        # 짝수는 V 먼저, 홀수는 V−τ 먼저 — 조건에 고정된 순서 효과를 없앤다
        seq = CONDITIONS if i % 2 == 0 else CONDITIONS[::-1]
        print(f"\n{'-' * 78}\n[{i + 1}/{len(entries)}] {e['tid']}  밴드 {band}")
        for cond in seq:
            res = run_task(backends[cond], spec, tau if cond == "V" else None)
            row = score_run(e, res, tau)
            rows[cond].append(row)
            flag = "🔴 FAILED" if row["failed"] else (
                f"{row['stated']:<9} {row['level_used']}")
            print(f"    {cond:<6} {flag} · 라운드 {row['rounds']} · "
                  f"분기A {row['branch_a']} B {row['branch_b']} · "
                  f"식별 {'○' if row['identification_correct'] else '×'} · "
                  f"esc {'○' if row['escalation_appropriate'] else '×'}")
            if row["error"]:
                print(f"           ⚠️ {row['error']}")
            if not row["failed"]:
                s, marks = case_study_score(row, res)
                if s >= 8:
                    cases.append({"tid": e["tid"], "condition": cond, "band": band,
                                  "score": s, "marks": marks,
                                  "trace": res.trace})
            # 중간 크래시에 대비해 과제마다 즉시 기록한다
            (out_dir / "rows_partial.json").write_text(json.dumps(
                rows, ensure_ascii=False, indent=2, default=str) + "\n")

    elapsed = time.time() - t_start
    q1 = read_quota()
    quota_ledger.record(model=model, n_calls=len(ledger.calls),
                        tokens=ledger.summary()["usage"], before=q0, after=q1,
                        seconds=elapsed, context=f"main/batch{args.batch}")

    summ = {c: summarize(c, rows[c]) for c in CONDITIONS}
    cases.sort(key=lambda x: -x["score"])

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "batch": args.batch, "model": model, "conditions": list(CONDITIONS),
        "task_ids": batch["task_ids"],
        "frozen": {"stage_a": json.loads(STAGE_A.read_text())["sha256"],
                   "stage_b": sb["sha256"], "execution_order": order["sha256"]},
        "elapsed_s": round(elapsed, 1),
        "summary": summ, "rows": rows,
        "case_study_candidates": cases,
        "ledger_summary": ledger.summary(),
        "quota_before": q0, "quota_after": q1,
    }
    (out_dir / "batch_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")
    (out_dir / "rows_partial.json").unlink(missing_ok=True)

    # ── 보고 ─────────────────────────────────────────────────────────
    print(f"\n{'=' * 78}\nBatch {args.batch} 요약\n{'=' * 78}")
    for c in CONDITIONS:
        s = summ[c]
        print(f"\n  {c}  n={s['n']} · FAILED {s['failed']} ({s['failed_pct']}%)"
              + ("  🔴 사전등록 무효 기준 초과" if s["abort_rule_violated"] else ""))
        m = s["metrics"]
        for k, label in (("justified_resolution", "justified resolution"),
                         ("reference_direction_correct", "참조방향 정확도"),
                         ("overinterpretation", "과대해석 (§7.1 주 지표)"),
                         ("escalation_appropriate", "escalation 적절성"),
                         ("identification_accuracy", "구조 식별 (자율식별형 한정)")):
            print(f"      {label:<28} {m[k]['n']}/{m[k]['d']}")
        mm = s["identification_mismatch"]
        print(f"      {'식별 오류':<28} {mm['n']}건 "
              f"(자기증거 충실 {mm['faithful_to_own_evidence']})")
        for mode, v_ in sorted(s["by_identification_mode"].items()):
            print(f"        {mode:<24} n={v_['n']} FAILED={v_['failed']} "
                  f"justified={v_['justified_resolution'][0]}/"
                  f"{v_['justified_resolution'][1]}")
        print(f"      {'L3 사용':<28} {s['used_l3']}/{s['n']} · "
              f"계산비용 {s['cost_s']}초")
        print(f"      {'분기 A / B':<28} {s['branch_a']} / {s['branch_b']}")
        print(f"      오류 분해  " + " · ".join(
            f"{k} {v_}" for k, v_ in sorted(s["error_class"].items(),
                                            key=lambda x: -x[1])) or "—")

    print(f"\n  밴드 C — escalation 이 값을 하는 유일한 구간")
    for c in CONDITIONS:
        bc = summ[c]["by_band"].get("C")
        if bc:
            print(f"      {c:<6} n={bc['n']} · L3 상승 {bc['used_l3']} · "
                  f"justified {bc['justified_resolution']['n']}/"
                  f"{bc['justified_resolution']['d']} · "
                  f"esc {bc['escalation_appropriate']['n']}/"
                  f"{bc['escalation_appropriate']['d']}")

    print(f"\n  대표 사례 후보 {len(cases)}건 (점수 8 이상)")
    for c in cases[:5]:
        print(f"      [{c['score']:>2}] {c['tid']} · {c['condition']} · 밴드 {c['band']}")
        print(f"           {' / '.join(c['marks'])}")

    ls = ledger.summary()
    print(f"\n  호출 {ls['n_calls']} · 실패 {ls['failures']} · "
          f"토큰 {ls['usage']['total_tokens']:,} · 경과 {elapsed / 60:.1f}분")
    print(f"  quota  5시간 "
          f"{q0.get('Gemini Models', {}).get('Five Hour Limit Remaining')} → "
          f"{q1.get('Gemini Models', {}).get('Five Hour Limit Remaining')} · 주간 "
          f"{q0.get('Gemini Models', {}).get('Weekly Limit Remaining')} → "
          f"{q1.get('Gemini Models', {}).get('Weekly Limit Remaining')}")
    print(f"\n→ {out_dir.relative_to(ROOT)}")
    print("   calls.jsonl 은 대표 사례 trajectory 보존용으로 삭제하지 않는다.")


if __name__ == "__main__":
    main()
