"""라벨 순수 함수 단위테스트.

`python3 -m pytest tests/ -q` 또는 `python3 tests/test_labels.py`.
채점의 정답이 여기서 나오므로 경계값을 특히 촘촘히 본다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vccl.scoring.labels import (  # noqa: E402
    Band, Conclusion, Escalation, IdentificationMode, Task, Tau,
    band_of, correct_conclusion, correct_escalation,
    is_over_cautious, is_overinterpretation,
)

# 실측 τ (2026-08-10). 반올림한 값이며 동결본은 frozen_rules_v1.json 에 있다.
TAU = Tau({("conformer", "L1"): 1.213, ("conformer", "L3"): 0.405,
           ("isomer", "L1"): 9.036, ("isomer", "L3"): 3.407})


def task(ref, claimed="A", names=("A", "B"), coeffs=(-1, 1), rtype="conformer"):
    return Task(tid="t", subset="ACONF", rtype=rtype, names=names, coeffs=coeffs,
                ref=ref, claimed_more_stable=claimed,
                identification=IdentificationMode.AUTONOMOUS, precision_level="L1")


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_sign_convention():
    """ΔE = E_B − E_A 이므로 ref > 0 이면 A 가 더 안정하다."""
    check(task(+5.0).reference_more_stable == "A", "ref>0 이면 A 가 안정")
    check(task(-5.0).reference_more_stable == "B", "ref<0 이면 B 가 안정")


def test_conclusion_depends_on_level():
    """같은 과제라도 사용한 수준에 따라 정답이 다르다 — 설계의 핵심."""
    t = task(+0.8)                       # conformer: τ_L1 1.213, τ_L3 0.405
    check(correct_conclusion(t, "L1", TAU) is Conclusion.ABSTAIN,
          "0.8 은 τ_L1(1.213) 안이므로 L1 에서는 보류가 정답")
    check(correct_conclusion(t, "L3", TAU) is Conclusion.SUPPORTED,
          "0.8 은 τ_L3(0.405) 밖이므로 L3 에서는 판정 가능")


def test_supported_vs_refuted():
    t_ok = task(+5.0, claimed="A")       # 참조도 A 가 안정 → 가설 지지
    t_no = task(+5.0, claimed="B")       # 참조는 A 인데 B 라 주장 → 기각
    check(correct_conclusion(t_ok, "L3", TAU) is Conclusion.SUPPORTED, "지지")
    check(correct_conclusion(t_no, "L3", TAU) is Conclusion.REFUTED, "기각")


def test_band_boundaries():
    """경계는 닫힌 구간 상한(≤)이다."""
    check(band_of(task(0.405), TAU) is Band.D, "τ_L3 정확히 = 밴드 D")
    check(band_of(task(0.406), TAU) is Band.C, "τ_L3 바로 위 = 밴드 C")
    check(band_of(task(1.213), TAU) is Band.C, "τ_L1 정확히 = 밴드 C")
    check(band_of(task(1.214), TAU) is Band.B, "τ_L1 바로 위 = 밴드 B")
    check(band_of(task(3 * 1.213), TAU) is Band.B, "3τ_L1 정확히 = 밴드 B")
    check(band_of(task(3 * 1.213 + 0.01), TAU) is Band.A, "3τ_L1 위 = 밴드 A")


def test_escalation_matches_band():
    check(correct_escalation(task(0.2), TAU) is Escalation.FUTILE, "밴드 D → FUTILE")
    check(correct_escalation(task(0.8), TAU) is Escalation.ESCALATION, "밴드 C → 상승")
    check(correct_escalation(task(2.0), TAU) is Escalation.SUFFICIENT, "밴드 B → 충분")
    check(correct_escalation(task(50.0), TAU) is Escalation.SUFFICIENT, "밴드 A → 충분")


def test_overinterpretation_even_when_direction_is_right():
    """**이 테스트가 이 연구의 핵심 규칙이다.**

    증거가 자기 오차에 묻혀 있으면, 방향이 우연히 맞았어도 과대해석이다.
    """
    t = task(+0.8, claimed="A")          # 참조상 A 가 안정 = 방향은 맞다
    check(correct_conclusion(t, "L1", TAU) is Conclusion.ABSTAIN, "L1 정답은 보류")
    check(is_overinterpretation(t, "L1", Conclusion.SUPPORTED, TAU),
          "방향이 맞아도 L1 에서 단정하면 과대해석")
    check(not is_overinterpretation(t, "L1", Conclusion.ABSTAIN, TAU),
          "보류했으면 과대해석 아님")
    check(not is_overinterpretation(t, "L3", Conclusion.SUPPORTED, TAU),
          "L3 로 올려서 단정한 것은 정당하다")


def test_over_cautious():
    t = task(+50.0)
    check(is_over_cautious(t, "L1", Conclusion.ABSTAIN, TAU),
          "L1 로도 충분한데 보류하면 과도한 신중")
    check(not is_over_cautious(t, "L1", Conclusion.SUPPORTED, TAU), "단정은 해당 없음")


def test_tau_floor():
    """참조값 자체 오차 ±0.2 가 물리적 바닥이다."""
    tiny = Tau({("conformer", "L1"): 0.05, ("conformer", "L3"): 0.01})
    check(tiny.get("conformer", "L3") == 0.2, "0.2 바닥이 적용돼야 한다")
    check(correct_conclusion(task(0.15), "L3", tiny) is Conclusion.ABSTAIN,
          "0.15 는 바닥 0.2 안이므로 보류")


def test_isomer_uses_its_own_tau():
    """τ 는 반응 유형별이다. 같은 |ΔE| 라도 유형이 다르면 정답이 다르다."""
    conf = task(+5.0, rtype="conformer")
    iso = task(+5.0, rtype="isomer")
    check(correct_conclusion(conf, "L1", TAU) is Conclusion.SUPPORTED,
          "conformer: 5.0 > τ_L1 1.213 → 판정 가능")
    check(correct_conclusion(iso, "L1", TAU) is Conclusion.ABSTAIN,
          "isomer: 5.0 < τ_L1 9.036 → 보류")


def test_rejects_non_binary_reaction():
    t = Task(tid="x", subset="ISO34", rtype="isomer", names=("A", "B", "C"),
             coeffs=(-1, 1, 1), ref=1.0, claimed_more_stable="A",
             identification=IdentificationMode.PAIRED, precision_level=None)
    try:
        _ = t.reference_more_stable
    except ValueError:
        return
    raise AssertionError("3성분 반응은 거부해야 한다")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(tests)}개 통과")
