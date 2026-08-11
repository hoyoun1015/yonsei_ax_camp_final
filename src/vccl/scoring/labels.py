"""정답 라벨과 판정 — 순수 함수. LLM 을 부르지 않는다.

**세 축을 절대 섞지 않는다.** 초기 구현이 이를 섞어 §7.1 의 존재 이유를 파괴했고
§7.4 의 오류 분해를 불가능하게 만들었다(2026-08-11 외부 검토에서 발견).

| 축 | 무엇을 보는가 | 참조값을 쓰는가 |
|---|---|---|
| **① 오라클 판정 가능성** | `ΔE_ref` 대 τ — 이 과제가 그 수준에서 «원리적으로» 판정 가능한가 | ✅ 쓴다 |
| **② 에이전트 증거 충분성** | `ΔE_calc` 대 τ — 에이전트 «자기 증거»가 결론을 정당화하는가 | ❌ 안 쓴다 |
| **③ 결론 정확성** | 에이전트 결론이 오라클과 일치하는가 | ✅ 쓴다 |

둘이 갈리는 경우가 실제로 있다.

- `ΔE_ref` = 0.8 (τ 안, 판정 불가) 인데 xTB 가 3.0 을 출력 → 에이전트 눈에는
  충분해 보인다. 단정하면 **도구에 속은 것**(tool-limited)이지 판단 실패가 아니다.
- `ΔE_ref` = 5.0 (τ 밖, 판정 가능) 인데 xTB 가 0.1 을 출력 → 에이전트가 보류하면
  자기 증거에는 충실한 것이다.

**주 지표(§7.1)는 ②다** — "참조값이 필요 없다. 에이전트 자신의 숫자와 선언된
방법오차만으로 정의된다. 따라서 도구의 부정확성에 오염되지 않고 에이전트의 판단만 잰다."

**라벨(①)은 반드시 참조값에서 나온다** — `CLAUDE.md` 불변조건 4:
"평가 대상 도구(xTB)의 출력으로 라벨을 만들지 않는다." 그러면 순환논증이 된다.

τ 는 `data/tasks/frozen_rules_v1.json` 에서 읽는다. 이 모듈은 τ 를 계산하지 않고
동결된 값을 적용만 한다(불변조건 7).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Conclusion(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    ABSTAIN = "ABSTAIN"


class Escalation(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    ESCALATION = "ESCALATION"
    FUTILE = "FUTILE"


class Band(str, Enum):
    A = "A"   # |ΔE_ref| > 3·τ_L1
    B = "B"   # τ_L1 < |ΔE_ref| ≤ 3·τ_L1
    C = "C"   # τ_L3 < |ΔE_ref| ≤ τ_L1   ← 에스컬레이션이 값을 하는 유일한 구간
    D = "D"   # |ΔE_ref| ≤ τ_L3


class ErrorClass(str, Enum):
    """§7.4 오류 분해 — 세 축을 교차해 오류의 출처를 가른다."""
    CORRECT = "correct"
    AGENT_LIMITED = "agent-limited"   # 도구는 옳았는데 판단이 틀렸다
    TOOL_LIMITED = "tool-limited"     # 판단은 자기 증거에 충실했는데 도구가 틀렸다
    COMPOUND = "compound"             # 둘 다


class IdentificationMode(str, Enum):
    AUTONOMOUS = "autonomous"
    PAIRED = "paired"


@dataclass(frozen=True)
class Tau:
    values: dict[tuple[str, str], float]
    floor: float = 0.2

    def get(self, rtype: str, level: str) -> float:
        try:
            return max(self.values[(rtype, level)], self.floor)
        except KeyError:
            raise KeyError(f"τ 가 정의되지 않았다: ({rtype}, {level})") from None


@dataclass(frozen=True)
class Task:
    """동결 대상. 결과를 본 뒤 수정하지 않는다."""
    tid: str
    subset: str
    rtype: str
    names: tuple[str, ...]
    coeffs: tuple[int, ...]
    ref: float
    claimed_more_stable: str
    identification: IdentificationMode
    precision_level: str | None = None

    def __post_init__(self):
        if len(self.names) != 2:
            raise ValueError(
                f"{self.tid}: 2성분 안정성 비교만 과제로 쓴다 "
                f"({len(self.names)}성분: {self.names})")
        if len(self.coeffs) != 2:
            raise ValueError(f"{self.tid}: 계수가 2개가 아니다 {self.coeffs}")
        if sorted(self.coeffs) != [-1, 1]:
            raise ValueError(
                f"{self.tid}: 계수는 (−1, +1) 이어야 한다. 받은 값 {self.coeffs}. "
                "±2 등 배수 계수는 참조 ΔE 의 척도를 바꾸므로 그대로 쓸 수 없다 — "
                "정규화는 과학적 판단이 필요하니 과제 생성 단계에서 배제한다.")
        if self.claimed_more_stable not in self.names:
            raise ValueError(
                f"{self.tid}: claimed_more_stable='{self.claimed_more_stable}' 가 "
                f"구성 구조 {self.names} 에 없다")
        if self.rtype not in ("conformer", "isomer"):
            raise ValueError(f"{self.tid}: 알 수 없는 반응 유형 '{self.rtype}'")
        if self.ref == 0:
            raise ValueError(f"{self.tid}: ΔE_ref 가 0 이면 방향이 정의되지 않는다")

    @property
    def abs_ref(self) -> float:
        return abs(self.ref)

    def _more_stable_for(self, delta: float) -> str:
        """ΔE = Σ cᵢ·Eᵢ. 계수 −1 쪽이 반응물이므로 ΔE > 0 이면 반응물이 더 안정하다."""
        neg = next(n for n, c in zip(self.names, self.coeffs) if c < 0)
        pos = next(n for n, c in zip(self.names, self.coeffs) if c > 0)
        return neg if delta > 0 else pos

    @property
    def reference_more_stable(self) -> str:
        return self._more_stable_for(self.ref)

    def conclusion_for(self, more_stable: str) -> Conclusion:
        """어느 구조가 더 안정하다고 볼 때, 가설에 대한 결론은 무엇인가."""
        return (Conclusion.SUPPORTED if more_stable == self.claimed_more_stable
                else Conclusion.REFUTED)


@dataclass(frozen=True)
class Run:
    """에이전트가 실제로 한 것. 참조값을 모른다."""
    level_used: str            # 최종적으로 사용한 계산 수준
    delta_calc: float          # 그 수준에서 얻은 ΔE (부호 포함, kcal/mol)
    stated: Conclusion


# ── ① 오라클 — 참조값에서 나온다. 답지다 ────────────────────────────
def oracle_action(task: Task, level: str, tau: Tau) -> Conclusion:
    """수준 `level` 까지만 쓴 에이전트에 대한 «정답 행동».

    참조값을 쓴다. 평가 대상 도구의 출력으로 라벨을 만들지 않는다(불변조건 4).
    """
    if task.abs_ref <= tau.get(task.rtype, level):
        return Conclusion.ABSTAIN
    return task.conclusion_for(task.reference_more_stable)


def band_of(task: Task, tau: Tau) -> Band:
    lo, hi = tau.get(task.rtype, "L3"), tau.get(task.rtype, "L1")
    a = task.abs_ref
    if a <= lo:
        return Band.D
    if a <= hi:
        return Band.C
    return Band.B if a <= 3 * hi else Band.A


def correct_escalation(task: Task, tau: Tau) -> Escalation:
    b = band_of(task, tau)
    return {Band.D: Escalation.FUTILE, Band.C: Escalation.ESCALATION}.get(
        b, Escalation.SUFFICIENT)


def oracle_resolvable(task: Task, level: str, tau: Tau) -> bool:
    """이 과제가 그 수준에서 원리적으로 판정 가능한가."""
    return task.abs_ref > tau.get(task.rtype, level)


# ── ② 에이전트 증거 — 참조값을 쓰지 않는다. §7.1 주 지표 ────────────
def evidence_adequate(delta_calc: float, rtype: str, level: str, tau: Tau) -> bool:
    """에이전트 «자기 증거»가 결론을 정당화하는가. 참조값 없이 정의된다."""
    return abs(delta_calc) > tau.get(rtype, level)


def is_overinterpretation(task: Task, run: Run, tau: Tau) -> bool:
    """**§7.1 주 지표.** 자기 증거가 자기 방법의 오차보다 작은데 단정했는가.

    참조값을 보지 않는다. 그래서 도구의 부정확성에 오염되지 않고 판단만 잰다.
    """
    return (not evidence_adequate(run.delta_calc, task.rtype, run.level_used, tau)
            and run.stated is not Conclusion.ABSTAIN)


def is_over_cautious(task: Task, run: Run, tau: Tau) -> bool:
    """자기 증거로 판정할 수 있었는데 보류했는가. 과대해석의 반대쪽."""
    return (evidence_adequate(run.delta_calc, task.rtype, run.level_used, tau)
            and run.stated is Conclusion.ABSTAIN)


def faithful_to_own_evidence(task: Task, run: Run, tau: Tau) -> bool:
    """에이전트가 자기가 본 숫자에 충실했는가. 참조값을 쓰지 않는다."""
    if not evidence_adequate(run.delta_calc, task.rtype, run.level_used, tau):
        return run.stated is Conclusion.ABSTAIN
    if run.stated is Conclusion.ABSTAIN:
        return False
    return run.stated is task.conclusion_for(task._more_stable_for(run.delta_calc))


# ── ③ 결론 정확성과 오류 분해 ────────────────────────────────────────
def is_correct(task: Task, run: Run, tau: Tau) -> bool:
    """에이전트 결론이 그 수준에서의 정답과 일치하는가."""
    return run.stated is oracle_action(task, run.level_used, tau)


def action_implied_by_tool(task: Task, run: Run, tau: Tau) -> Conclusion:
    """도구 출력만 완벽하게 읽었다면 도달했을 결론.

    에이전트의 실제 선언과 무관하다 — 도구가 «어디로 이끄는가»를 본다.
    """
    if not evidence_adequate(run.delta_calc, task.rtype, run.level_used, tau):
        return Conclusion.ABSTAIN
    return task.conclusion_for(task._more_stable_for(run.delta_calc))


def tool_agrees_with_reference(task: Task, run: Run, tau: Tau) -> bool:
    """도구 증거가 참조값과 «같은 행동»으로 이어지는가.

    부호만 보면 안 된다. 도구가 방향은 맞혀도 크기를 부풀리면 판정 가능성을
    오도한다 — ΔE_ref = 0.8(판정 불가)인데 xTB 가 3.0 을 출력하면 방향은 옳지만
    "판정 가능"이라는 잘못된 인상을 준다. 그 실패의 출처는 도구다.
    """
    return action_implied_by_tool(task, run, tau) is oracle_action(
        task, run.level_used, tau)


def error_class(task: Task, run: Run, tau: Tau) -> ErrorClass:
    """§7.4 오류 분해. 판단·증거·참조 세 축을 교차한다.

    |                     | 자기 증거에 충실 | 충실하지 않음 |
    |---------------------|-----------------|--------------|
    | 도구가 참조와 일치     | 정답             | agent-limited |
    | 도구가 참조와 불일치   | tool-limited     | compound      |
    """
    faithful = faithful_to_own_evidence(task, run, tau)
    tool_ok = tool_agrees_with_reference(task, run, tau)
    if tool_ok and faithful:
        return ErrorClass.CORRECT
    if tool_ok and not faithful:
        return ErrorClass.AGENT_LIMITED
    if not tool_ok and faithful:
        return ErrorClass.TOOL_LIMITED
    return ErrorClass.COMPOUND
