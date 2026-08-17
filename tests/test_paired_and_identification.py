"""회귀 테스트 — Batch 1 을 무효로 만든 두 결함을 고정한다.

DECISION_LOG 2026-08-12 (4) 에서 발견 · (5) 에서 수정.

  ① paired 실행 경로가 없어 과제 16개가 «가설 없이» 실행됐다
  ② 에이전트가 참조 쌍과 다른 쌍을 고르면 KeyError 로 죽어, 식별 실패가
     측정되지 않고 사라졌다

두 결함 모두 **smoke 가 결함 과제를 필터로 배제하고 있어서** 7/7 통과에도 잡히지
않았다. 그래서 여기서는 «의도적으로 틀리게 고르는» 경우를 명시적으로 만든다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents.loop import TaskSpec, run_task
from vccl.agents.main_run import faithful_in_agent_frame, score_run, to_spec
from vccl.agents.r0 import to_task
from vccl.scoring.labels import Conclusion, IdentificationMode
from vccl.tasks import prompts
from vccl.tasks.pairs import build_pool, load_tau

STAGE_B = ROOT / "data" / "tasks" / "frozen_stage_b_v1.json"


def _pool() -> dict[str, dict]:
    return {t["tid"]: t for t in build_pool()}


def _main_ids() -> list[str]:
    return json.loads(STAGE_B.read_text())["primary_experiment"]["main_benchmark"]["task_ids"]


# ── ① paired 경로 ────────────────────────────────────────────────────
def test_every_main_task_has_a_hypothesis():
    """🔴 Batch 1 무효의 직접 원인. 92개 중 하나라도 가설이 없으면 실패한다."""
    pool = _pool()
    missing = [t for t in _main_ids()
               if not ((pool[t].get("hypothesis") or {}).get("neutral") or "").strip()]
    assert not missing, f"가설이 없는 과제 {len(missing)}개: {missing[:5]}"


def test_paired_hypothesis_is_rendered_not_template():
    """템플릿 자리표시자가 그대로 프롬프트에 나가면 안 된다."""
    pool = _pool()
    n_paired = 0
    for tid in _main_ids():
        spec = to_spec(pool[tid])
        assert spec.hypothesis.strip(), tid
        assert "{claimed}" not in spec.hypothesis, tid
        assert "{other}" not in spec.hypothesis, tid
        if spec.specified_pair:
            n_paired += 1
            assert all(lb in spec.candidates for lb in spec.specified_pair), tid
            assert spec.specified_pair[0] != spec.specified_pair[1], tid
    assert n_paired == 16, f"paired 과제가 16개여야 한다 (실측 {n_paired})"


def test_paired_specified_pair_is_the_gold_pair():
    """쌍 지정형은 «지정»이므로 참조 쌍과 같아야 한다."""
    pool = _pool()
    for tid in _main_ids():
        e = pool[tid]
        if e["identification"] != IdentificationMode.PAIRED.value:
            continue
        spec = to_spec(e)
        real = {spec.real_names[lb] for lb in spec.specified_pair}
        assert real == set(e["names"]), f"{tid}: {real} != {set(e['names'])}"


def test_taskspec_rejects_empty_hypothesis():
    """가설 없이 과제를 만들 수 없어야 한다 — 구조적으로 막는다."""
    for bad in (None, "", "   "):
        try:
            TaskSpec(task_id="x", subset="ACONF", rtype="conformer",
                     hypothesis=bad, candidates={"S1": "a", "S2": "b"})
        except ValueError:
            continue
        raise AssertionError(f"가설 {bad!r} 인데 TaskSpec 이 만들어졌다")


def test_paired_prompt_does_not_leak_into_autonomous():
    """자율 식별형 프롬프트 문구는 바뀌지 않았다."""
    pool = _pool()
    tid = next(t for t in _main_ids()
               if pool[t]["identification"] == IdentificationMode.AUTONOMOUS.value)
    spec = to_spec(pool[tid])
    assert spec.specified_pair is None
    assert "지정" not in spec.hypothesis


def test_render_paired_rejects_empty_template():
    try:
        prompts.render_paired("", "S1", "S2")
    except ValueError:
        return
    raise AssertionError("빈 템플릿을 렌더링했다")


# ── ② 식별 오류가 크래시가 아니라 측정값이 된다 ───────────────────────
class _Call:
    def __init__(self):
        self.level_selected = None
        self.tool_result = None


class _Ledger:
    def __init__(self):
        self.calls: list[_Call] = []


class _ScriptedBackend:
    """PI 가 «틀린 쌍» 을 고르도록 강제한다. LLM 을 부르지 않는다."""

    def __init__(self, pair, level="L1", conclusion="SUPPORTED"):
        self.ledger = _Ledger()
        self.pair, self.level, self.conclusion = pair, level, conclusion

    def ask(self, *, task_id, agent_role, round, prompt, schema, prompt_version):
        self.ledger.calls.append(_Call())
        if agent_role == "PI" and "operationalize" in prompt_version:
            return {"structure_more_stable": self.pair[0],
                    "structure_other": self.pair[1],
                    "observable": "relative electronic energy",
                    "identification_basis": "테스트", "ambiguous": False,
                    "ambiguity_note": ""}
        if agent_role == "ComputationalChemist":
            return {"level": self.level, "reasoning": "테스트"}
        if agent_role == "SkepticalReviewer":
            return {"evidence_sufficient": True, "recommendation": "conclude",
                    "concern": "", "reasoning": "테스트"}
        return {"conclusion": self.conclusion,
                "restates_original_hypothesis": "원 가설",
                "reasoning": "테스트"}


def _wrong_pair_case():
    """후보가 3개 이상인 과제에서 참조 쌍이 «아닌» 쌍을 고른다."""
    pool = _pool()
    for tid in _main_ids():
        spec = to_spec(pool[tid])
        if len(spec.candidates) < 3:
            continue
        gold = {lb for lb in spec.candidates
                if spec.real_names[lb] in set(pool[tid]["names"])}
        wrong = [lb for lb in spec.candidates if lb not in gold]
        if wrong:
            a = sorted(gold)[0]
            return pool[tid], spec, (a, wrong[0])
    raise AssertionError("후보 3개 이상인 과제를 찾지 못했다")


def test_identification_mismatch_does_not_crash():
    """🔴 예전에는 여기서 KeyError 가 났다."""
    entry, spec, wrong = _wrong_pair_case()
    res = run_task(_ScriptedBackend(wrong), spec, load_tau())
    assert res.error is None, f"크래시했다: {res.error}"
    assert res.conclusion is not None, "결론까지 도달해야 한다"
    assert res.identification_correct is False
    assert res.delta_evidence is not None, "고른 쌍의 ΔE 는 있어야 한다"
    assert res.delta_gold_convention is None, "참조 규약 ΔE 는 계산할 수 없다"


def test_identification_mismatch_logs_both_pairs():
    """선택 쌍과 정답 쌍이 모두 남아야 전파를 추적할 수 있다."""
    entry, spec, wrong = _wrong_pair_case()
    res = run_task(_ScriptedBackend(wrong), spec, load_tau())
    assert res.selected_pair and res.gold_pair
    assert set(res.selected_pair) != set(res.gold_pair)
    ex = [t for t in res.trace if t["step"] == "execute"]
    assert ex and ex[0]["selected_pair"] and ex[0]["gold_pair"]
    assert ex[0]["identification_correct"] is False


def test_identification_mismatch_scored_as_wrong_conclusion():
    """식별이 틀리면 원 가설에 대한 결론은 오답이다. 자기 증거 축은 정상 채점한다."""
    entry, spec, wrong = _wrong_pair_case()
    tau = load_tau()
    res = run_task(_ScriptedBackend(wrong), spec, tau)
    row = score_run(entry, res, tau)
    assert row["identification_correct"] is False
    assert row["level_relative_correct"] is False
    assert row["reference_direction_correct"] is False
    assert row["justified_resolution"] is False
    assert row["error_class"] in ("agent-limited", "compound")
    # 자기 증거 축은 «계산됐다» — 크래시로 빠지지 않는다
    assert row["evidence_adequate"] in (True, False)
    assert row["overinterpretation"] in (True, False)
    assert row["delta_evidence"] is not None
    assert row["delta_gold_convention"] is None


def test_correct_identification_still_scores_normally():
    """정상 경로가 망가지지 않았는지 — 참조 규약 ΔE 가 그대로 쓰인다."""
    pool = _pool()
    tid = next(t for t in _main_ids()
               if pool[t]["identification"] == IdentificationMode.AUTONOMOUS.value)
    entry = pool[tid]
    spec = to_spec(entry)
    gold = [lb for lb in spec.candidates
            if spec.real_names[lb] in set(entry["names"])]
    tau = load_tau()
    res = run_task(_ScriptedBackend((gold[0], gold[1])), spec, tau)
    assert res.error is None
    assert res.identification_correct is True
    assert res.delta_gold_convention is not None
    assert res.delta_calc == res.delta_gold_convention
    row = score_run(entry, res, tau)
    assert row["level_relative_correct"] in (True, False)
    assert row["justified_resolution"] in (True, False)


def test_paired_task_runs_end_to_end():
    """쌍 지정형이 실제로 끝까지 돈다 — Batch 1 에서는 여기서 FAILED 였다."""
    pool = _pool()
    tid = next(t for t in _main_ids()
               if pool[t]["identification"] == IdentificationMode.PAIRED.value)
    entry = pool[tid]
    spec = to_spec(entry)
    tau = load_tau()
    res = run_task(_ScriptedBackend(spec.specified_pair), spec, tau)
    assert res.error is None, res.error
    assert res.conclusion is not None
    assert res.identification_correct is True
    row = score_run(entry, res, tau)
    assert row["identification_mode"] == "paired"
    # 쌍 지정형은 식별을 «수행하지 않았다» — 정확도 지표 분모에서 빠진다
    assert row["identification_accuracy"] is None
    assert row["identification_performed"] is False


def test_faithful_in_agent_frame_uses_selected_pair():
    """자기 증거 충실성은 참조 쌍이 아니라 «고른 쌍» 으로 정의된다."""
    tau = load_tau()

    class R:
        level_used = "L1"
        delta_evidence = -50.0          # 지목한 구조가 훨씬 안정
        conclusion = Conclusion.SUPPORTED
    assert faithful_in_agent_frame(R(), tau, "conformer") is True
    R.conclusion = Conclusion.REFUTED
    assert faithful_in_agent_frame(R(), tau, "conformer") is False
    R.delta_evidence = 0.0001           # 오차에 묻힘 → 보류가 충실한 것
    R.conclusion = Conclusion.ABSTAIN
    assert faithful_in_agent_frame(R(), tau, "conformer") is True
