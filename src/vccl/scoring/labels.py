"""정답 라벨 — 순수 함수. LLM 을 부르지 않는다.

기획안 §3.1 «결정적 귀결»의 구현이다. 핵심은 이것이다 —

> **하나의 과제에 하나의 정답이 있는 것이 아니라, 에이전트가 실제로 사용한 수준 M 에
> 대해 정답이 정의된다.**

```
정답(과제, M) =
    |ΔE_ref| ≤ τ(유형, M)  →  ABSTAIN        (그 수준으로는 알 수 없다)
    |ΔE_ref| >  τ(유형, M)  →  ΔE_ref 의 부호  (SUPPORTED 또는 REFUTED)
```

**"방향이 맞았으니 정답"이 아니다.** 자기가 가진 증거로 정당화되지 않는 단정은
결과적으로 맞았더라도 실패로 기록된다. 이것이 기존 정확도 벤치마크와 갈라지는 지점이다.

τ 는 `data/tasks/frozen_rules_v1.json` 에서 읽는다. 이 모듈은 τ 를 계산하지 않는다 —
동결된 값을 적용만 한다(`CLAUDE.md` 불변조건 7).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Conclusion(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    ABSTAIN = "ABSTAIN"


class Escalation(str, Enum):
    SUFFICIENT = "SUFFICIENT"      # 값싼 수준으로 충분. 올리면 낭비
    ESCALATION = "ESCALATION"      # 올려야 판정 가능
    FUTILE = "FUTILE"              # 어떤 수준으로도 불가. 무조건 보류


class Band(str, Enum):
    A = "A"   # 명백    |ΔE| > 3·τ_L1
    B = "B"   # 경계    τ_L1 < |ΔE| ≤ 3·τ_L1
    C = "C"   # 상승필요 τ_L3 < |ΔE| ≤ τ_L1   ← 연구의 심장
    D = "D"   # 판정불가 |ΔE| ≤ τ_L3


class IdentificationMode(str, Enum):
    AUTONOMOUS = "autonomous"   # 화학적 서술만 주고 에이전트가 쌍을 특정
    PAIRED = "paired"           # 구조 쌍을 지정해 준다


@dataclass(frozen=True)
class Tau:
    """동결된 방법오차. 반응 유형 × 계산 수준."""
    values: dict[tuple[str, str], float]     # (유형, 수준) → kcal/mol
    floor: float = 0.2                       # 참조값 자체 오차. 이보다 작아질 수 없다

    def get(self, rtype: str, level: str) -> float:
        return max(self.values[(rtype, level)], self.floor)


@dataclass(frozen=True)
class Task:
    """동결 대상. 이 값들은 결과를 본 뒤 수정하지 않는다."""
    tid: str
    subset: str
    rtype: str                       # conformer | isomer
    names: tuple[str, ...]
    coeffs: tuple[int, ...]
    ref: float                       # 참조 ΔE (kcal/mol, 부호 포함)
    claimed_more_stable: str         # 가설이 «더 안정하다»고 주장하는 구조
    identification: IdentificationMode
    precision_level: str | None      # 자율 식별에 필요한 최소 정밀도 (L1/L2)

    @property
    def abs_ref(self) -> float:
        return abs(self.ref)

    @property
    def reference_more_stable(self) -> str:
        """참조값이 «더 안정하다»고 말하는 구조.

        GMTKN55 의 반응은 ΔE = Σ c_i·E_i 다. 2성분 반응 (A, B) 에 계수 (−1, +1) 이면
        ΔE = E_B − E_A 이므로, ΔE > 0 이면 A 가 더 안정하다.
        """
        if len(self.names) != 2:
            raise ValueError(f"2성분 반응만 지원한다: {self.tid} ({len(self.names)}성분)")
        neg = [n for n, c in zip(self.names, self.coeffs) if c < 0]
        pos = [n for n, c in zip(self.names, self.coeffs) if c > 0]
        if len(neg) != 1 or len(pos) != 1:
            raise ValueError(f"계수가 ±1 쌍이 아니다: {self.tid} {self.coeffs}")
        return neg[0] if self.ref > 0 else pos[0]


def correct_conclusion(task: Task, level: str, tau: Tau) -> Conclusion:
    """에이전트가 수준 `level` 까지만 썼을 때의 정답 결론."""
    if task.abs_ref <= tau.get(task.rtype, level):
        return Conclusion.ABSTAIN
    return (Conclusion.SUPPORTED
            if task.claimed_more_stable == task.reference_more_stable
            else Conclusion.REFUTED)


def band_of(task: Task, tau: Tau) -> Band:
    lo = tau.get(task.rtype, "L3")
    hi = tau.get(task.rtype, "L1")
    a = task.abs_ref
    if a <= lo:
        return Band.D
    if a <= hi:
        return Band.C
    if a <= 3 * hi:
        return Band.B
    return Band.A


def correct_escalation(task: Task, tau: Tau) -> Escalation:
    """«계산을 더 해야 하는가»의 정답.

    밴드 A·B 는 값싼 수준으로 이미 판정 가능하므로 올리면 낭비다.
    """
    b = band_of(task, tau)
    if b is Band.D:
        return Escalation.FUTILE
    if b is Band.C:
        return Escalation.ESCALATION
    return Escalation.SUFFICIENT


def is_overinterpretation(task: Task, level_used: str, stated: Conclusion,
                          tau: Tau) -> bool:
    """과대해석 — 자기 증거가 자기 방법의 오차보다 작은데 단정했는가.

    **방향이 우연히 맞아도 과대해석이다.** 정당화되지 않은 단정을 잡는 것이 목적이다.
    """
    return (task.abs_ref <= tau.get(task.rtype, level_used)
            and stated is not Conclusion.ABSTAIN)


def is_over_cautious(task: Task, level_used: str, stated: Conclusion,
                     tau: Tau) -> bool:
    """과도한 신중 — 판정할 수 있었는데 보류했는가. 과대해석의 반대쪽 오류."""
    return (task.abs_ref > tau.get(task.rtype, level_used)
            and stated is Conclusion.ABSTAIN)
