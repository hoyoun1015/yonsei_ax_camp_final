"""역할별 구조화 출력 스키마. `agy --json-schema` 로 강제한다.

프롬프트 버전을 여기서 고정한다 — 원장에 버전과 해시가 함께 남아, 나중에
"어느 프롬프트로 얻은 결과인가"를 로그만으로 재구성할 수 있다.
"""
PROMPT_VERSION = "v1"

# ── PI · 1단계: 가설 조작화 (비교 대상 식별) ─────────────────────────
OPERATIONALIZE = {
    "type": "object",
    "properties": {
        "structure_more_stable": {
            "type": "string",
            "description": "가설이 «더 안정하다»고 주장하는 구조의 라벨"},
        "structure_other": {
            "type": "string",
            "description": "비교 대상이 되는 다른 구조의 라벨"},
        "observable": {
            "type": "string",
            "description": "판정에 쓸 관측량. 상대 전자에너지라면 'relative electronic energy'"},
        "identification_basis": {
            "type": "string",
            "description": "각 구조가 가설의 서술에 해당한다고 판단한 기하학적 근거"},
        "ambiguous": {
            "type": "boolean",
            "description": "서술에 해당하는 구조가 둘 이상이라 비교가 정의되지 않는가"},
        "ambiguity_note": {
            "type": "string",
            "description": "모호하다면 무엇이 모호한지. 아니면 빈 문자열"},
    },
    "required": ["structure_more_stable", "structure_other", "observable",
                 "identification_basis", "ambiguous", "ambiguity_note"],
    "additionalProperties": False,
}

# ── Computational Chemist · 계산 수준 선택 ───────────────────────────
CHOOSE_LEVEL = {
    "type": "object",
    "properties": {
        "level": {"type": "string", "enum": ["L1", "L3"],
                  "description": "L1 = GFN2-xTB 단일점(0.02초). L3 = B3LYP-D3(BJ)/def2-TZVP 단일점(25초~53분)"},
        "reasoning": {"type": "string"},
    },
    "required": ["level", "reasoning"],
    "additionalProperties": False,
}

# ── Skeptical Reviewer · 증거 점검 ───────────────────────────────────
REVIEW = {
    "type": "object",
    "properties": {
        "evidence_sufficient": {
            "type": "boolean",
            "description": "지금 증거로 방향을 단정할 수 있는가"},
        "recommendation": {
            "type": "string", "enum": ["conclude", "escalate", "reoperationalize"],
            "description": "conclude = 결론으로 간다 · escalate = 상위 수준으로 재계산 · "
                           "reoperationalize = 비교 대상 설정을 다시 세운다"},
        "concern": {"type": "string", "description": "지적 사항. 없으면 빈 문자열"},
        "reasoning": {"type": "string"},
    },
    "required": ["evidence_sufficient", "recommendation", "concern", "reasoning"],
    "additionalProperties": False,
}

# ── PI · 최종 결론 ───────────────────────────────────────────────────
CONCLUDE = {
    "type": "object",
    "properties": {
        "conclusion": {"type": "string",
                       "enum": ["SUPPORTED", "REFUTED", "ABSTAIN"],
                       "description": "**원 가설**에 대한 결론"},
        "restates_original_hypothesis": {
            "type": "string",
            "description": "지금 답하고 있는 원 가설을 그대로 다시 적는다"},
        "reasoning": {"type": "string"},
    },
    "required": ["conclusion", "restates_original_hypothesis", "reasoning"],
    "additionalProperties": False,
}
