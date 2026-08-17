"""3-에이전트 closed loop — PI · Computational Chemist · Skeptical Reviewer.

기획안 §5.2·§5.3 의 구현이다. **역할 수를 줄이지 않는다.** 한 condition 안에서는
세 역할이 **같은 모델**을 쓴다(backend.py).

```
원 가설(고정)
  ↓
PI 조작화 ── 무엇을 비교할지 스스로 결정
  ↓
Comp Chemist 수준 선택 → 실행층 → 관찰
  ↓
Skeptical Reviewer 점검
  ↓
 ┌─ 분기 A: escalate        → 상위 수준으로 재실행
 ├─ 분기 B: reoperationalize → 조작화로 되돌아감
 └─ 종료: PI 최종 결론
```

🔒 **분기 B 제약** — 재조작화는 operationalization 만 바꾼다. **원 가설은 고정이고,
최종 결론은 반드시 원 가설에 답해야 한다.** 실행층이 원 가설을 시작 시점에 기록하고
결정론적으로 검사한다.

🔒 **구조 이름을 그대로 노출하지 않는다.** GMTKN55 의 `H_ttt`·`H_ggg` 같은 이름에는
회전각 패턴이 인코딩돼 있어 답을 알려주는 셈이 된다. 과제마다 불투명 라벨로 바꾸고
매핑은 로그에만 남긴다(오염 방어, G5).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vccl.agents import schemas
from vccl.agents.backend import Backend
from vccl.executor import cached
from vccl.scoring.labels import Conclusion, Tau

MAX_ROUNDS = 3
LEVEL_DESC = {
    "L1": "GFN2-xTB 단일점. 반응당 약 0.02초.",
    "L3": "B3LYP-D3(BJ)/def2-TZVP 단일점. 반응당 25초~53분 (원자 수에 따라).",
}


@dataclass
class TaskSpec:
    """에이전트에게 주어지는 것. 참조값과 정답은 들어 있지 않다."""
    task_id: str
    subset: str
    rtype: str
    hypothesis: str                       # 원 가설. 고정이다
    candidates: dict[str, str]            # 불투명 라벨 → 기하 서술
    real_names: dict[str, str] = field(repr=False, default_factory=dict)
    reference_pair: tuple[str, str] = field(repr=False, default=())
    # 채점용 부호 규약 — 참조값과 동일해야 한다. ΔE = Σ cᵢ·Eᵢ
    ref_names: tuple[str, ...] = field(repr=False, default=())
    ref_coeffs: tuple[int, ...] = field(repr=False, default=())
    # 쌍 지정형(paired) — 비교할 두 구조를 «라벨로» 명시해 준다. (claimed, other).
    # None 이면 자율 식별형이고, 그 경로의 프롬프트는 예전 그대로다.
    specified_pair: tuple[str, str] | None = field(default=None)

    def __post_init__(self):
        # 🔴 Batch 1 무효의 직접 원인 — 가설 없이 실행됐다. 구조적으로 막는다
        if not (self.hypothesis or "").strip():
            raise ValueError(
                f"{self.task_id}: 가설 문장이 비어 있다. 검증할 가설 없이 과제를 "
                "실행할 수 없다 (DECISION_LOG 2026-08-12 (4)).")
        if self.specified_pair and not all(
                lb in self.candidates for lb in self.specified_pair):
            raise ValueError(
                f"{self.task_id}: 지정된 쌍 {self.specified_pair} 이 후보에 없다")


@dataclass
class LoopResult:
    task_id: str
    conclusion: Conclusion | None
    level_used: str | None
    delta_calc: float | None
    rounds: int
    branch_a: int                          # escalation 횟수
    branch_b: int                          # 재조작화 횟수
    identified_pair: tuple[str, str] | None
    identification_correct: bool | None
    hypothesis_restated: str | None
    ambiguity_flagged: bool
    trace: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    # ── 식별 오류 추적 (DECISION_LOG 2026-08-12 (5)) ──────────────────
    # 예전에는 에이전트가 참조 쌍과 «다른» 쌍을 고르면 KeyError 로 죽었고, 식별 실패가
    # 점수가 아니라 크래시가 되어 지표에서 조용히 빠졌다. 이제 실행을 계속하고
    # 아래를 분리해 남긴다 — 식별 오류가 downstream 판단에 어떻게 전파됐는지 본다.
    selected_pair: tuple[str, str] | None = None      # 에이전트가 고른 실제 구조명
    gold_pair: tuple[str, str] | None = None          # 참조 쌍
    delta_evidence: float | None = None               # 고른 쌍의 ΔE — 에이전트 «자기 증거»
    delta_gold_convention: float | None = None        # 참조 부호 규약 ΔE. 식별 오류면 None
    specified_pair_given: bool = False                # 쌍 지정형이었는가


def anonymize(names: list[str], task_id: str) -> tuple[dict[str, str], dict[str, str]]:
    """구조 이름 → 불투명 라벨. 과제별로 결정론적이되 순서는 섞는다."""
    rng = random.Random(f"anon::{task_id}")
    shuffled = list(names)
    rng.shuffle(shuffled)
    to_label = {n: f"S{i + 1}" for i, n in enumerate(shuffled)}
    return to_label, {v: k for k, v in to_label.items()}


def _tau_block(rtype: str, tau: Tau | None) -> str:
    if tau is None:
        return ""
    return (
        "\n## 이 방법들의 알려진 오차 (방법오차 τ)\n\n"
        f"- L1 (GFN2-xTB): **{tau.get(rtype, 'L1'):.2f} kcal/mol**\n"
        f"- L3 (B3LYP-D3(BJ)/def2-TZVP): **{tau.get(rtype, 'L3'):.2f} kcal/mol**\n\n"
        "계산된 에너지 차이가 그 방법의 τ보다 작으면, 그 차이는 방법오차 안에 묻혀 있어\n"
        "어느 쪽이 안정한지 **말할 수 없다.**\n")


def _pi_operationalize_paired(be: Backend, spec: TaskSpec, rnd: int,
                              feedback: str | None) -> dict:
    """쌍 지정형 — 비교할 두 구조를 명시해 준다 (DECISION_LOG 2026-08-12 (5)).

    이 계열은 어떤 기하 서술로도 두 구조를 특정할 수 없어(`min_precision` = None)
    자율 식별이 원리적으로 불가능하다. 그래서 식별 부담을 지우지 않고 쌍을 준다.
    **가설 자체는 그대로 주어지고, 판단(수준 선택·증거 충분성·결론)은 전부 남아 있다.**

    자율 식별형 프롬프트는 이 함수와 무관하다 — 문구를 바꾸지 않았다.
    """
    claimed, other = spec.specified_pair
    cand = "\n".join(f"- **{lab}**: {desc}" for lab, desc in spec.candidates.items())
    fb = f"\n## 이전 라운드의 지적\n\n{feedback}\n" if feedback else ""
    prompt = f"""당신은 계산화학 연구팀의 PI다. 아래 가설을 검증 가능한 계산 실험으로 조작화하라.

## 원 가설 (고정 — 바꾸지 않는다)

> {spec.hypothesis}

## 비교할 구조 (지정됨)

이 과제는 비교 대상이 **지정되어 있다.** 기하 서술만으로는 두 구조를 특정할 수 없는
계열이기 때문이다. 아래 쌍을 그대로 쓴다.

- 가설이 «더 안정하다»고 주장하는 구조: **{claimed}**
- 비교 대상: **{other}**

## 참고 — 이 화학종의 구조 목록

{cand}
{fb}
## 할 일

1. 위에 지정된 쌍을 그대로 반환한다 (`structure_more_stable` = {claimed},
   `structure_other` = {other})
2. 이 비교로 원 가설을 검증할 수 있는지, 관측량이 무엇인지 적는다
3. 지정된 쌍이 가설과 맞지 않는다고 판단되면 `ambiguous=true` 로 표시하고 이유를 적는다"""
    return be.ask(task_id=spec.task_id, agent_role="PI", round=rnd, prompt=prompt,
                  schema=schemas.OPERATIONALIZE,
                  prompt_version=f"{schemas.PROMPT_VERSION}/operationalize_paired")


def _pi_operationalize(be: Backend, spec: TaskSpec, rnd: int,
                       feedback: str | None) -> dict:
    if spec.specified_pair:
        return _pi_operationalize_paired(be, spec, rnd, feedback)
    cand = "\n".join(f"- **{lab}**: {desc}" for lab, desc in spec.candidates.items())
    fb = f"\n## 이전 라운드의 지적\n\n{feedback}\n" if feedback else ""
    prompt = f"""당신은 계산화학 연구팀의 PI다. 아래 가설을 검증 가능한 계산 실험으로 조작화하라.

## 원 가설 (고정 — 바꾸지 않는다)

> {spec.hypothesis}

## 사용 가능한 구조

각 구조의 기하 정보다. 어느 것이 가설의 서술에 해당하는지는 **당신이 판단해야 한다.**

{cand}
{fb}
## 할 일

1. 가설이 «더 안정하다»고 주장하는 구조와, 그 비교 대상을 고른다
2. 각각을 그렇게 판단한 기하학적 근거를 적는다
3. 서술에 해당하는 구조가 둘 이상이면 `ambiguous=true` 로 표시한다 —
   그 경우에도 가장 타당한 후보를 고르되 무엇이 모호한지 적는다

구조 라벨은 위 목록의 것을 그대로 쓴다."""
    return be.ask(task_id=spec.task_id, agent_role="PI", round=rnd, prompt=prompt,
                  schema=schemas.OPERATIONALIZE,
                  prompt_version=f"{schemas.PROMPT_VERSION}/operationalize")


def _chemist_level(be: Backend, spec: TaskSpec, rnd: int, pair: tuple[str, str],
                   tau: Tau | None, history: str) -> dict:
    prompt = f"""당신은 계산화학 연구팀의 Computational Chemist다. 어느 계산 수준으로 실행할지 정하라.

## 검증할 비교

**{pair[0]}** 대 **{pair[1]}** — 상대 전자에너지

## 선택지

- **L1** — {LEVEL_DESC['L1']}
- **L3** — {LEVEL_DESC['L3']}
{_tau_block(spec.rtype, tau)}
비용 격차가 1,000배 이상이다. 값싼 수준으로 충분하면 올리는 것은 낭비이고,
부족한데 올리지 않으면 판정할 수 없다.
{history}
## 할 일

이번 라운드에 실행할 수준 하나를 고르고 이유를 적는다."""
    return be.ask(task_id=spec.task_id, agent_role="ComputationalChemist", round=rnd,
                  prompt=prompt, schema=schemas.CHOOSE_LEVEL,
                  prompt_version=f"{schemas.PROMPT_VERSION}/choose_level")


def _reviewer(be: Backend, spec: TaskSpec, rnd: int, pair: tuple[str, str],
              level: str, delta: float, tau: Tau | None, ambiguous: bool,
              rounds_left: int) -> dict:
    amb = ("\n⚠️ PI 가 비교 대상 식별이 모호하다고 표시했다.\n" if ambiguous else "")
    lower = pair[1] if delta > 0 else pair[0]
    prompt = f"""당신은 계산화학 연구팀의 Skeptical Reviewer다. 지금 증거로 결론을 내려도 되는지 점검하라.

## 원 가설

> {spec.hypothesis}

## 지금까지의 증거

- 비교: **{pair[0]}** 대 **{pair[1]}**
- 사용한 수준: **{level}** — {LEVEL_DESC[level]}
- E({pair[0]}) − E({pair[1]}) = **{delta:+.3f} kcal/mol**
- 따라서 계산상 더 낮은 에너지(= 더 안정)는 **{lower}** 이고, 두 구조의 차이 크기는
  **{abs(delta):.3f} kcal/mol** 이다
{_tau_block(spec.rtype, tau)}{amb}
남은 라운드: {rounds_left}

## 할 일

증거가 결론을 정당화하는지 판정하고, 다음 행동을 하나 고른다.

- `conclude` — 지금 증거로 결론을 낸다
- `escalate` — 상위 계산 수준으로 다시 실행한다
- `reoperationalize` — 비교 대상 설정이 잘못됐으므로 다시 세운다
  (**원 가설은 바꾸지 않는다.** 무엇을 비교할지만 다시 정한다)"""
    return be.ask(task_id=spec.task_id, agent_role="SkepticalReviewer", round=rnd,
                  prompt=prompt, schema=schemas.REVIEW,
                  prompt_version=f"{schemas.PROMPT_VERSION}/review")


def _pi_conclude(be: Backend, spec: TaskSpec, rnd: int, pair: tuple[str, str],
                 level: str, delta: float, tau: Tau | None, concern: str) -> dict:
    lower = pair[1] if delta > 0 else pair[0]
    prompt = f"""당신은 계산화학 연구팀의 PI다. 최종 결론을 내려라.

## 원 가설 — 반드시 이 가설에 답한다

> {spec.hypothesis}

## 증거

- 비교: **{pair[0]}** 대 **{pair[1]}**
- 사용한 수준: **{level}**
- E({pair[0]}) − E({pair[1]}) = **{delta:+.3f} kcal/mol**
- 따라서 계산상 더 낮은 에너지(= 더 안정)는 **{lower}** 이고, 차이 크기는
  **{abs(delta):.3f} kcal/mol** 이다
{_tau_block(spec.rtype, tau)}
## Reviewer 의 지적

{concern or "없음"}

## 할 일

- **SUPPORTED** — 증거가 원 가설을 지지한다
- **REFUTED** — 증거가 원 가설에 반한다
- **ABSTAIN** — 지금 증거로는 어느 쪽인지 말할 수 없다

그리고 지금 답하고 있는 원 가설을 그대로 다시 적는다."""
    return be.ask(task_id=spec.task_id, agent_role="PI", round=rnd, prompt=prompt,
                  schema=schemas.CONCLUDE,
                  prompt_version=f"{schemas.PROMPT_VERSION}/conclude")


def run_task(be: Backend, spec: TaskSpec, tau: Tau | None) -> LoopResult:
    """한 과제에 대해 3-에이전트 루프를 돈다."""
    res = LoopResult(task_id=spec.task_id, conclusion=None, level_used=None,
                     delta_calc=None, rounds=0, branch_a=0, branch_b=0,
                     identified_pair=None, identification_correct=None,
                     hypothesis_restated=None, ambiguity_flagged=False)
    feedback, history, level_hint = None, "", None
    pair = None
    try:
        for rnd in range(1, MAX_ROUNDS + 1):
            res.rounds = rnd

            # ① PI — 조작화 (첫 라운드이거나 재조작화 요청이 있을 때)
            if pair is None:
                op = _pi_operationalize(be, spec, rnd, feedback)
                a, b = op["structure_more_stable"], op["structure_other"]
                if a not in spec.candidates or b not in spec.candidates or a == b:
                    res.error = f"PI 가 유효하지 않은 구조를 지정했다: {a}, {b}"
                    return res
                pair = (a, b)
                res.identified_pair = pair
                res.specified_pair_given = bool(spec.specified_pair)
                res.ambiguity_flagged = res.ambiguity_flagged or bool(op["ambiguous"])
                if spec.reference_pair:
                    # 쌍 지정형에서는 «식별을 수행하지 않았다». 여기 값은 지정을 그대로
                    # 따랐는지의 확인이며, 식별 정확도 지표에는 넣지 않는다(채점기에서 분리)
                    res.identification_correct = (
                        {spec.real_names[a], spec.real_names[b]}
                        == set(spec.reference_pair))
                res.trace.append({"round": rnd, "step": "operationalize", **op})

            # ② Computational Chemist — 수준 선택
            lv = _chemist_level(be, spec, rnd, pair, tau, history)
            level = lv["level"]
            res.trace.append({"round": rnd, "step": "choose_level", **lv})

            # ③ 실행층 — 결정론적. M_used 는 여기서 기록된다
            sel = (spec.real_names[pair[0]], spec.real_names[pair[1]])
            req = cached.CalcRequest(subset=spec.subset, structures=sel, level=level)
            out = cached.run(req)
            # **표시용 · 에이전트 자기 증거** — E(pair[0]) − E(pair[1]).
            # pair[0] 은 에이전트가 «더 안정하다»고 지목한 구조이므로, 음수면 자기 증거가
            # 가설을 지지하는 방향이다. 부호 의미를 프롬프트에서 명시한다
            delta = (out.energies[sel[0]] - out.energies[sel[1]]) * cached.HARTREE
            res.selected_pair, res.gold_pair = sel, tuple(spec.ref_names)
            res.delta_evidence = delta

            # **채점용** — 참조값과 같은 규약(ΔE = Σ cᵢ·Eᵢ)이어야 labels 가 맞게 판정한다.
            # 두 규약을 섞으면 부호가 뒤집혀 에이전트의 판단을 잘못 채점한다.
            #
            # 🔴 참조 쌍의 에너지는 «에이전트가 그 쌍을 골랐을 때만» 존재한다. 예전 코드는
            # 무조건 ref_names 로 조회해서, 식별이 틀리면 KeyError 로 죽었다 —
            # 식별 실패가 측정되지 않고 사라졌다(DECISION_LOG 2026-08-12 (4)).
            # 이제 계산하지 못하면 None 으로 두고 실행을 계속한다.
            if all(n in out.energies for n in spec.ref_names):
                delta_scoring = sum(
                    c * out.energies[n]
                    for n, c in zip(spec.ref_names, spec.ref_coeffs)) * cached.HARTREE
            else:
                delta_scoring = None
            res.delta_gold_convention = delta_scoring
            # 자기 증거 축(§7.1)은 «고른 쌍»으로 잰다 — 참조값을 쓰지 않는 지표이므로
            # 식별이 틀려도 정의된다. 결론 정확성은 채점기가 식별 실패로 처리한다.
            res.level_used = level
            res.delta_calc = delta_scoring if delta_scoring is not None else delta
            be.ledger.calls[-1].level_selected = level
            # 식별 오류의 전파를 추적할 수 있도록 축을 분리해 남긴다
            exec_record = {
                "level": level,
                "selected_pair": list(sel),
                "gold_pair": list(spec.ref_names),
                "identification_correct": res.identification_correct,
                "specified_pair_given": bool(spec.specified_pair),
                # 에이전트가 실제로 본 숫자 (자기 증거)
                "delta_evidence_kcal_mol": round(delta, 4),
                # 참조 부호 규약. 식별이 틀리면 계산할 수 없다
                "delta_gold_convention_kcal_mol": (
                    None if delta_scoring is None else round(delta_scoring, 4)),
                "cost_s": out.cost_s, "qc_ok": out.qc_ok}
            be.ledger.calls[-1].tool_result = exec_record | {
                "energies_hartree": {k: out.energies[v]
                                     for k, v in ((pair[0], sel[0]),
                                                  (pair[1], sel[1]))}}
            res.trace.append({"round": rnd, "step": "execute", **exec_record})

            # ④ Skeptical Reviewer
            rv = _reviewer(be, spec, rnd, pair, level, delta, tau,
                           res.ambiguity_flagged, MAX_ROUNDS - rnd)
            res.trace.append({"round": rnd, "step": "review", **rv})
            rec = rv["recommendation"]

            if rec == "escalate" and rnd < MAX_ROUNDS and level != "L3":
                res.branch_a += 1
                history = (f"\n## 이전 라운드\n\n{level} 로 계산해 "
                           f"{delta:+.3f} kcal/mol 을 얻었으나 증거가 부족하다고 "
                           f"판단됐다: {rv['concern']}\n")
                continue
            if rec == "reoperationalize" and rnd < MAX_ROUNDS:
                res.branch_b += 1
                feedback = rv["concern"] or rv["reasoning"]
                pair, history = None, ""
                continue

            # ⑤ PI — 최종 결론
            fin = _pi_conclude(be, spec, rnd, pair, level, delta, tau, rv["concern"])
            res.conclusion = Conclusion(fin["conclusion"])
            res.hypothesis_restated = fin["restates_original_hypothesis"]
            res.trace.append({"round": rnd, "step": "conclude", **fin})
            return res

        # 라운드 상한 도달 — 그 시점 판단을 기록한다
        fin = _pi_conclude(be, spec, MAX_ROUNDS, pair, res.level_used,
                           delta, tau, "라운드 상한에 도달했다.")
        res.conclusion = Conclusion(fin["conclusion"])
        res.hypothesis_restated = fin["restates_original_hypothesis"]
        res.trace.append({"round": MAX_ROUNDS, "step": "conclude_forced", **fin})
        return res
    except Exception as e:  # noqa: BLE001 — 파일럿에서는 실패도 기록 대상이다
        res.error = f"{type(e).__name__}: {e}"
        return res
