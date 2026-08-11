"""라벨·판정 단위테스트.

`python3 tests/test_labels.py`

**이 파일이 지키는 것은 «세 축을 섞지 않는다»이다.**
초기 구현이 오라클(ΔE_ref)과 에이전트 증거(ΔE_calc)를 섞어 §7.1 의 존재 이유를
파괴했고 §7.4 오류 분해를 불가능하게 만들었다. 그 회귀를 막는다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vccl.scoring.labels import (  # noqa: E402
    Band, Conclusion, ErrorClass, Escalation, IdentificationMode, Run, Task, Tau,
    band_of, correct_escalation, error_class, evidence_adequate,
    faithful_to_own_evidence, is_correct, is_over_cautious, is_overinterpretation,
    oracle_action, oracle_resolvable,
)

FROZEN = ROOT / "data" / "tasks" / "frozen_rules_v1.json"

# 동결본과 일치해야 한다. test_frozen_tau_has_not_drifted 가 검사한다.
TAU = Tau({("conformer", "L1"): 1.212518, ("conformer", "L3"): 0.40522,
           ("isomer", "L1"): 9.035798, ("isomer", "L3"): 3.406928})


def task(ref, claimed="A", rtype="conformer", names=("A", "B"), coeffs=(-1, 1)):
    return Task(tid="t", subset="ACONF", rtype=rtype, names=names, coeffs=coeffs,
                ref=ref, claimed_more_stable=claimed,
                identification=IdentificationMode.AUTONOMOUS, precision_level="L1")


def run(delta, stated, level="L1"):
    return Run(level_used=level, delta_calc=delta, stated=stated)


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def expect_raises(fn, msg):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError(msg)


# ── ① 오라클 — 참조값 ────────────────────────────────────────────────
def test_sign_convention():
    check(task(+5.0).reference_more_stable == "A", "ref>0 → A 가 안정")
    check(task(-5.0).reference_more_stable == "B", "ref<0 → B 가 안정")


def test_oracle_depends_on_level():
    t = task(+0.8)
    check(oracle_action(t, "L1", TAU) is Conclusion.ABSTAIN, "0.8 < τ_L1 → 보류")
    check(oracle_action(t, "L3", TAU) is Conclusion.SUPPORTED, "0.8 > τ_L3 → 판정")


def test_band_boundaries():
    check(band_of(task(0.40522), TAU) is Band.D, "τ_L3 정확히 = D")
    check(band_of(task(0.40523), TAU) is Band.C, "τ_L3 바로 위 = C")
    check(band_of(task(1.212518), TAU) is Band.C, "τ_L1 정확히 = C")
    check(band_of(task(1.2126), TAU) is Band.B, "τ_L1 바로 위 = B")
    check(band_of(task(3 * 1.212518), TAU) is Band.B, "3τ_L1 정확히 = B")
    check(band_of(task(3 * 1.212518 + 0.01), TAU) is Band.A, "3τ_L1 위 = A")


def test_escalation_matches_band():
    for ref, want in ((0.2, Escalation.FUTILE), (0.8, Escalation.ESCALATION),
                      (2.0, Escalation.SUFFICIENT), (50.0, Escalation.SUFFICIENT)):
        check(correct_escalation(task(ref), TAU) is want, f"|ΔE|={ref}")


def test_isomer_uses_its_own_tau():
    check(oracle_action(task(+5.0, rtype="conformer"), "L1", TAU) is Conclusion.SUPPORTED,
          "conformer: 5.0 > 1.21 → 판정 가능")
    check(oracle_action(task(+5.0, rtype="isomer"), "L1", TAU) is Conclusion.ABSTAIN,
          "isomer: 5.0 < 9.04 → 보류")


def test_tau_floor():
    tiny = Tau({("conformer", "L1"): 0.05, ("conformer", "L3"): 0.01})
    check(tiny.get("conformer", "L3") == 0.2, "참조값 오차 0.2 가 바닥")
    check(oracle_action(task(0.15), "L3", tiny) is Conclusion.ABSTAIN, "0.15 < 0.2")


# ── ② 에이전트 증거 — 참조값을 쓰지 않는다 ─────────────────────────
def test_overinterpretation_ignores_reference():
    """**주 지표는 참조값에 의존하지 않는다** (§7.1).

    참조값만 다르고 에이전트가 본 숫자가 같으면 판정이 같아야 한다.
    """
    r = run(0.5, Conclusion.SUPPORTED)          # 0.5 < τ_L1 1.21 → 증거 불충분
    for ref in (+0.8, +50.0, -0.3):
        check(is_overinterpretation(task(ref), r, TAU),
              f"ΔE_calc 가 같으면 ref={ref} 여도 과대해석 판정이 같아야 한다")


def test_reviewer_case_1_tool_inflates():
    """ref=0.8 (판정 불가) 인데 xTB 가 3.0 을 출력한 경우.

    에이전트 눈에는 충분해 보인다. 단정해도 **과대해석이 아니다** — 도구에 속은 것이다.
    """
    t, r = task(+0.8, claimed="A"), run(+3.0, Conclusion.SUPPORTED)
    check(not oracle_resolvable(t, "L1", TAU), "오라클: L1 로는 판정 불가")
    check(evidence_adequate(3.0, "conformer", "L1", TAU), "에이전트 증거는 충분해 보인다")
    check(not is_overinterpretation(t, r, TAU),
          "자기 증거로는 정당하므로 과대해석이 아니다")
    check(not is_correct(t, r, TAU), "그래도 오라클 기준 정답은 아니다(보류가 정답)")
    check(error_class(t, r, TAU) is ErrorClass.TOOL_LIMITED,
          "도구가 부풀렸으므로 tool-limited")


def test_reviewer_case_2_tool_deflates():
    """ref=5.0 (판정 가능) 인데 xTB 가 0.1 을 출력한 경우.

    에이전트가 보류하면 자기 증거에는 충실한 것이다.
    """
    t, r = task(+5.0, claimed="A"), run(+0.1, Conclusion.ABSTAIN)
    check(oracle_resolvable(t, "L1", TAU), "오라클: L1 로 판정 가능")
    check(not evidence_adequate(0.1, "conformer", "L1", TAU), "에이전트 증거는 불충분")
    check(faithful_to_own_evidence(t, r, TAU), "보류는 자기 증거에 충실하다")
    check(not is_over_cautious(t, r, TAU), "자기 증거 기준으로는 과도한 신중이 아니다")
    check(not is_correct(t, r, TAU), "오라클 기준 정답은 SUPPORTED 였다")


def test_overinterpretation_when_evidence_thin():
    t = task(+0.8, claimed="A")
    check(is_overinterpretation(t, run(0.3, Conclusion.SUPPORTED), TAU),
          "0.3 < τ_L1 인데 단정 → 과대해석")
    check(not is_overinterpretation(t, run(0.3, Conclusion.ABSTAIN), TAU),
          "보류했으면 아니다")
    check(is_overinterpretation(t, run(0.3, Conclusion.SUPPORTED, "L3"), TAU),
          "0.3 < τ_L3 0.405 이므로 L3 로 올려도 여전히 과대해석")
    check(is_overinterpretation(t, run(0.6, Conclusion.SUPPORTED, "L1"), TAU),
          "0.6 < τ_L1 1.21 → L1 에서는 과대해석")
    check(not is_overinterpretation(t, run(0.6, Conclusion.SUPPORTED, "L3"), TAU),
          "같은 0.6 이라도 L3 에서는 τ 0.405 를 넘으므로 정당하다")


def test_over_cautious_uses_own_evidence():
    t = task(+50.0)
    check(is_over_cautious(t, run(+50.0, Conclusion.ABSTAIN), TAU),
          "증거가 충분한데 보류 → 과도한 신중")
    check(not is_over_cautious(t, run(+0.1, Conclusion.ABSTAIN), TAU),
          "증거가 얇으면 보류가 옳다")


# ── ③ 오류 분해 ──────────────────────────────────────────────────────
def test_error_class_quadrants():
    t = task(+5.0, claimed="A")        # 참조: A 가 안정, conformer τ_L1 1.21
    check(error_class(t, run(+5.0, Conclusion.SUPPORTED), TAU) is ErrorClass.CORRECT,
          "도구 옳음 + 증거에 충실 → 정답")
    check(error_class(t, run(+5.0, Conclusion.REFUTED), TAU) is ErrorClass.AGENT_LIMITED,
          "도구는 A 라 했는데 B 라 결론 → agent-limited")
    check(error_class(t, run(-5.0, Conclusion.REFUTED), TAU) is ErrorClass.TOOL_LIMITED,
          "도구가 부호를 틀렸고 에이전트는 그대로 따름 → tool-limited")
    check(error_class(t, run(-5.0, Conclusion.SUPPORTED), TAU) is ErrorClass.COMPOUND,
          "도구도 틀리고 에이전트도 자기 증거를 안 따름 → compound")


# ── 검증 ─────────────────────────────────────────────────────────────
def test_validation():
    expect_raises(lambda: Task("x", "S", "conformer", ("A", "B", "C"), (-1, 1, 1),
                               1.0, "A", IdentificationMode.PAIRED),
                  "3성분은 거부")
    expect_raises(lambda: task(1.0, coeffs=(-2, 2)), "±2 계수는 거부")
    expect_raises(lambda: task(1.0, coeffs=(-1, -1)), "부호가 쌍이 아니면 거부")
    expect_raises(lambda: task(1.0, claimed="Z"), "구성에 없는 claimed 는 거부")
    expect_raises(lambda: task(0.0), "ΔE_ref = 0 은 거부")
    expect_raises(lambda: task(1.0, rtype="unknown"), "알 수 없는 반응 유형 거부")


def test_unknown_tau_key_raises():
    try:
        TAU.get("conformer", "L2")
    except KeyError:
        return
    raise AssertionError("동결본에 없는 수준을 조회하면 실패해야 한다")


# ── 동결본과의 정합 ──────────────────────────────────────────────────
def test_frozen_tau_has_not_drifted():
    """동결본이 바뀌면 테스트가 깨져야 한다. 조용한 drift 를 막는다."""
    if not FROZEN.exists():
        raise AssertionError(f"동결본이 없다: {FROZEN}")
    d = json.loads(FROZEN.read_text())
    frozen = d["tau"]["values"]
    for (rtype, level), v in TAU.values.items():
        got = frozen[rtype][level]
        check(abs(got - v) < 1e-9,
              f"τ drift: ({rtype},{level}) 동결본 {got} 대 테스트 {v}. "
              "동결본을 바꿨다면 불변조건 7 위반이 아닌지 확인하고 "
              "테스트 상수도 함께 갱신할 것")
    check(abs(d["tau"]["floor"] - TAU.floor) < 1e-12, "τ 바닥 drift")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(tests)}개 통과")
