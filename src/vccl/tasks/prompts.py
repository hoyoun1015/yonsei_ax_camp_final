"""자연어 가설 생성 — 중립 서술과 오도 서술.

기획안 §4.4 의 구현이다. **결정론적이며 LLM 을 부르지 않는다** — 가설 문장은 동결
대상이므로 실행마다 같아야 한다.

두 가지 원칙을 지킨다.

**① 구조 쌍을 지정해 주지 않는다.** 화학적 서술만 주고 어느 구조가 그에 해당하는지는
에이전트가 좌표에서 판정한다. 그래야 RQ1(가설 해석)이 실제 과제가 된다.

**② 정답이 유일해지는 최소 정밀도만 쓴다.** 거칠면 해당 구조가 여럿이라 정답이
정해지지 않고, 너무 정밀하면 구조 ID 를 풀어쓴 것이 되어 자율 식별이라 부를 수 없다.

그리고 **사전등록 조작** 하나 — 같은 과제를 두 서술로 낸다.

| 서술 | 내용 | 목적 |
|---|---|---|
| **중립** | 방향 주장만. 기전 언급 없음 | 기준 |
| **오도** | 참조값과 반대 방향을 시사하는 그럴듯한 화학적 직관 | 확증편향 측정 |

**정답 라벨은 서술과 무관하게 동일하다.** 오도 서술이 과대해석률을 높이는가가
직접 측정된다. 프롬프트 텍스트만 바꾸므로 구현 비용이 0이다.

**기전 설명의 옳고 그름은 채점하지 않는다** — LLM 판정자를 부르는 순간 순환논증이 된다.
기전 서술은 정성 분석에만 쓴다.
"""
from __future__ import annotations

from vccl.tasks.gmtkn import Descriptor

# 회전각 유형의 한국어 표기
TORSION = {"anti": "anti", "gauche": "gauche", "skew": "skew(anticlinal)",
           "syn": "syn(겹침)"}

# 오도 서술에 쓰는 기전 — 참조값과 반대 방향을 시사하는 그럴듯한 직관.
# 화학적으로 실재하는 효과를 «잘못된 방향으로» 적용한다.
MISLEADING = {
    "gauche_rich": "이 배좌는 치환기가 서로 가까워 입체 반발(steric repulsion)이 크므로",
    "anti_rich": "이 배좌는 사슬이 펼쳐져 분산 인력(London dispersion)을 거의 얻지 못하므로",
    "hbond": "분자 내 수소결합은 고리 변형(ring strain)을 유발하므로",
    "generic": "이 배좌는 형태 엔트로피가 낮아 자유에너지가 불리하므로",
}


def describe_phrase(d: Descriptor, level: str) -> str:
    """서술자를 자연어 구절로. 최소 정밀도만 쓴다.

    level="L1" 조성 — 회전각 유형의 «개수»만. 가장 자연스럽다.
    level="L2" 패턴 — 순서는 주되 부호는 버린다.
    """
    if level == "L1":
        parts = [f"{TORSION.get(k, k)} {n}개" for k, n in d.composition]
        s = "회전각이 " + " · ".join(parts) + "인 배좌" if parts else "회전각이 없는 구조"
    elif level == "L2":
        seq = "-".join(TORSION.get(t, t) for t in d.unsigned)
        s = f"회전각이 {seq} 순서인 배좌" if seq else "회전각이 없는 구조"
    else:
        raise ValueError(
            f"정밀도 '{level}' 은 쓰지 않는다. L3(부호까지)는 구조 ID 를 풀어쓴 것이며 "
            "자율 식별이라 부를 수 없다(기획안 §4.4).")
    if d.hbonds:
        s += f" (분자 내 수소결합 {d.hbonds}개)"
    return s


def _misleading_key(claimed: Descriptor, other: Descriptor) -> str:
    """주장된 구조의 어떤 특징을 «불리하게» 서술할지 고른다."""
    if claimed.hbonds > other.hbonds:
        return "hbond"
    cg = sum(n for k, n in claimed.composition if k == "gauche")
    og = sum(n for k, n in other.composition if k == "gauche")
    if cg > og:
        return "gauche_rich"
    ca = sum(n for k, n in claimed.composition if k == "anti")
    oa = sum(n for k, n in other.composition if k == "anti")
    if ca > oa:
        return "anti_rich"
    return "generic"


def neutral(claimed: Descriptor, other: Descriptor, level: str) -> str:
    """중립 서술 — 방향 주장만. 기전을 언급하지 않는다."""
    return (f"{describe_phrase(claimed, level)}가 "
            f"{describe_phrase(other, level)}보다 "
            "전자에너지가 낮아 더 안정할 것이다.")


def misleading(claimed: Descriptor, other: Descriptor, level: str) -> str:
    """오도 서술 — 같은 방향을 주장하되, 그것을 «반대로 시사하는» 기전을 붙인다.

    주장 방향은 중립 서술과 동일하다(정답 라벨이 같아야 하므로). 다른 것은 붙은
    기전이며, 그 기전은 주장된 구조가 «불리하다»고 시사한다. 즉 에이전트는
    서술을 그대로 받아들이면 반대 결론으로 끌려간다.
    """
    key = _misleading_key(claimed, other)
    return (f"{MISLEADING[key]} 통상적으로는 불리할 것으로 보이지만, "
            f"{describe_phrase(claimed, level)}가 "
            f"{describe_phrase(other, level)}보다 "
            "오히려 전자에너지가 낮아 더 안정할 것이다.")


def both(claimed: Descriptor, other: Descriptor, level: str) -> dict[str, str]:
    """두 서술을 함께. 정답 라벨은 둘에 대해 동일하다."""
    return {"neutral": neutral(claimed, other, level),
            "misleading": misleading(claimed, other, level),
            "mechanism_key": _misleading_key(claimed, other)}


# ── 쌍 지정형(paired) ────────────────────────────────────────────────
# DECISION_LOG 2026-08-12 (5). **위의 자율식별용 서술은 건드리지 않는다.**
#
# `min_precision` 이 None 인 반응은 «어떤 기하 서술로도 두 구조를 특정할 수 없는»
# 경우다. 따라서 서술 기반 가설로는 원리적으로 식별이 불가능하고, 설계는 그런 계열을
# 쌍 지정형으로 남기기로 했다(DECISION_LOG 2026-08-11 (2)).
#
# 🔴 **그렇더라도 «검증할 가설 문장» 은 반드시 존재해야 한다.** Batch 1 에서 이 경로가
# 구현돼 있지 않아 가설이 `None` 으로 실려 나갔고, 에이전트가 *"원 가설이 제공되지
# 않았다"* 고 답하면서 과제 16개가 무효가 됐다.
#
# 구조 라벨은 과제마다 실행 시점에 익명화되므로(`loop.anonymize`) 여기서는 자리표시자를
# 둔 **템플릿**을 만들고, 라벨이 정해지는 `to_spec` 에서 렌더링한다.
PAIRED_NEUTRAL = ("아래에 지정된 두 구조 가운데 **{claimed}** 가 **{other}** 보다 "
                  "전자에너지가 낮아 더 안정할 것이다.")


def paired_both() -> dict[str, str]:
    """쌍 지정형 과제의 가설 템플릿. `{claimed}` · `{other}` 를 라벨로 채운다.

    오도 서술(misleading)은 기전을 기하 서술에 붙이는 방식이라 쌍 지정형에 적용할 수
    없다. 해당 없음으로 두고 그 사실을 명시한다 — 조용히 None 을 두지 않는다.
    """
    return {"neutral": PAIRED_NEUTRAL,
            "neutral_is_template": True,
            "misleading": None,
            "misleading_note": "쌍 지정형에는 기전 서술을 붙이지 않는다 (해당 없음)",
            "mechanism_key": None}


def render_paired(template: str, claimed_label: str, other_label: str) -> str:
    if not template:
        raise ValueError("쌍 지정형 가설 템플릿이 비어 있다")
    return template.format(claimed=claimed_label, other=other_label)
