"""Stage B 동결 — 실행 규모와 실행 규약을 고정한다.

Stage A(`frozen_rules_v1.json`)가 **과학적 규칙**을 고정했다. Stage B 는 **무엇을
얼마나, 어떤 규약으로 돌리는가**를 고정한다.

`CLAUDE.md` 불변조건 7 — 동결 후에는 결과를 본 뒤 수정하지 않는다. 동결 이후의 변경은
`DECISION_LOG.md` 에 exploratory 로 표시하고 확증 결과를 대체하지 않는다.

**Flash 주간 quota 미확인은 과학적 설계를 바꾸는 근거로 쓰지 않는다** — 실행 스케줄
문제로만 취급하고, 필요하면 여러 quota window 에 나눠 돌린다.

사용:
    python3 src/vccl/tasks/freeze_stage_b.py
    python3 src/vccl/tasks/freeze_stage_b.py --force     # 재동결 (DECISION_LOG 필수)
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents import loop, schemas  # noqa: E402
from vccl.tasks import prompts  # noqa: E402
from vccl.tasks.pairs import (  # noqa: E402
    build_pool, identification_challenge, load_tau, stratify,
)

STAGE_A = ROOT / "data" / "tasks" / "frozen_rules_v1.json"
OUT = ROOT / "data" / "tasks" / "frozen_stage_b_v1.json"

TARGET_92 = {"A": 30, "B": 22, "C": 25, "D": 15}
PRIMARY_MODEL = "gemini-3.6-flash-high"

# 프롬프트를 «생성하는 코드» 를 해시한다. 프롬프트가 f-string 이라 텍스트만 따로
# 떼어낼 수 없으므로, 생성 로직 전체를 고정하는 것이 정확하다.
PROMPT_SOURCES = [
    "src/vccl/agents/loop.py",       # 역할별 프롬프트 본문과 루프
    "src/vccl/agents/schemas.py",    # 출력 스키마와 PROMPT_VERSION
    "src/vccl/tasks/prompts.py",     # 가설 문장(중립·오도) 생성
]


def sha256_file(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def git_rev() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def build() -> dict:
    stage_a = json.loads(STAGE_A.read_text())
    pool = build_pool()
    main_set = stratify(pool, TARGET_92)          # strict=True — 부족하면 예외
    chal = identification_challenge(pool)

    if len(main_set) != sum(TARGET_92.values()):
        raise SystemExit(f"Main benchmark 수가 맞지 않는다: {len(main_set)}")

    return {
        "version": "v1",
        "stage": "B",
        "frozen_at": datetime.now(timezone.utc).date().isoformat(),
        "depends_on": {"stage_a": "frozen_rules_v1.json",
                       "stage_a_sha256": stage_a.get("sha256")},

        # ── 실험 규모 ────────────────────────────────────────────────
        "primary_experiment": {
            "main_benchmark": {
                "n": len(main_set),
                "per_band": TARGET_92,
                "species_unique": True,
                "inference_unit": "화학종 (한 화학종에서 과제를 여러 개 뽑지 않는다)",
                "task_ids": [t["tid"] for t in main_set],
            },
            "conditions": {
                "V": {"desc": "본 시스템 — 3-agent + τ 모듈 + 사다리",
                      "llm_calls_per_task": "4~5 (실측)"},
                "V-tau": {"desc": "V 에서 τ 블록만 제거 — **주 대비**",
                          "llm_calls_per_task": "4~5"},
                "L0": {"desc": "LLM 단독, 도구 없음 — 오염 프로브(G5)",
                       "llm_calls_per_task": 1},
                "R0": {"desc": "oracle-pair / decision-rule baseline. "
                               "구조 쌍·관측량·수준(L1)을 오라클로 받고 규칙 하나 적용. "
                               "**자율 시스템 기준선이 아니다** — RQ1·RQ2·RQ3 를 "
                               "수행하지 않으므로 결론 판단 축에서만 비교한다.",
                       "llm_calls_per_task": 0,
                       "result": "results/r0_baseline.json"},
            },
            "agents": {
                "roles": ["PI", "ComputationalChemist", "SkepticalReviewer"],
                "note": "역할 수를 줄이지 않는다. 한 condition 안에서는 세 역할이 "
                        "같은 모델을 쓴다 — 섞으면 결과를 모델 차이에 귀속할 수 없다.",
            },
            "primary_model": PRIMARY_MODEL,
        },

        # ── 2층 평가 ────────────────────────────────────────────────
        "identification_challenge": {
            "primary": {"n": len(chal["primary"]),
                        "inference_unit": "화학종 24종 — **유의성 검정은 이것으로 한다**",
                        "task_ids": [t["tid"] for t in chal["primary"]]},
            "secondary": {"n": len(chal["secondary"]),
                          "use": "기술 통계·정성 분석 전용. 유의성 검정에 쓰지 않는다",
                          "note": "화학종 24종에서 나온 94관측이라고 명시 보고",
                          "task_ids": [t["tid"] for t in chal["secondary"]]},
            "r0_exclusion": "R0 는 구조 쌍을 오라클로 받으므로 식별을 수행하지 않는다. "
                            "이 세트에서 R0 와 V 의 식별 정확도를 비교하지 않는다.",
            "limitation": "primary 24개 중 15개가 Amino20x4 다. 식별 성능이 아미노산 "
                          "배좌 판정에 좌우되며 다른 화학 계열로 일반화된다고 주장하지 "
                          "않는다. 밴드 분포도 불균형(A13 B9 C1 D1)이라 이 세트로 "
                          "밴드 의존적 주장을 하지 않는다.",
        },

        # ── 실행 규약 ────────────────────────────────────────────────
        "execution_protocol": {
            "prompt_version": schemas.PROMPT_VERSION,
            "prompt_source_sha256": {p: sha256_file(p) for p in PROMPT_SOURCES},
            "max_rounds": loop.MAX_ROUNDS,
            "max_rounds_note": "분기 A(escalate)와 분기 B(reoperationalize)를 합산한다. "
                               "상한 도달 시 강제 종료하고 그 시점 판단을 기록한다.",
            "retry_policy": {
                "ladder": [
                    "1) --json-schema 없이 프롬프트로 형식 지시",
                    "2) --json-schema 강제 (다른 코드 경로)",
                    "3) 2 + «이전 응답이 비었다» 재요청",
                ],
                "why_ladder": "동일 요청 재시도는 무의미했다 — 실패가 프롬프트·스키마 "
                              "조합에 결정적이어서 3회가 모두 같은 방식으로 실패했다. "
                              "시도마다 다른 경로를 쓴다.",
                "effort_flag": "사용 금지 — -high/-low 모델명과 충돌해 "
                               "invalid model selection 하드 에러가 난다",
                "timeout_s": 300,
            },
            "structured_output_parser": {
                "impl": "src/vccl/agents/backend.py :: _salvage, _json_nudge",
                "rules": [
                    "structured_output 이 있으면 그대로 사용",
                    "없으면 본문에서 코드펜스를 벗기고 최외곽 {…} 를 JSON 파싱",
                    "required 키 존재 + **타입·enum 소속까지 검증**",
                    "enum 은 프롬프트에 \"A\" | \"B\" 로 표기 — 배열로 쓰면 "
                    "모델이 값이 배열이라고 읽는다(claude-sonnet-4-6 실측 3/3 실패)",
                ],
            },
            "determinism": {
                "task_ordering": "밴드·tid 오름차순. 층화 정렬 키는 "
                                 "(자율식별 여부, −|ΔE_ref|, tid) 로 완전히 정해진다",
                "seeds": {
                    "claimed_more_stable": "random.Random(f'claim::{rid}')",
                    "structure_anonymization": "random.Random(f'anon::{task_id}')",
                },
                "note": "층화·챌린지 선택·가설 문장·구조 익명화가 모두 결정론적이다. "
                        "LLM 샘플링만 비결정적이며 그것은 원장으로 추적한다.",
            },
            "failure_handling": {
                "backend_exhausted": "재시도 사다리 3경로가 모두 실패하면 그 과제를 "
                                     "FAILED 로 기록하고 주 지표에서 제외한다. "
                                     "제외 개수와 사유를 반드시 함께 보고한다.",
                "executor_cache_miss": "캐시에 없거나 성공 마커가 없으면 **중단한다**. "
                                       "조용히 건너뛰지 않는다.",
                "invalid_structure_label": "에이전트가 후보에 없는 라벨을 지정하면 "
                                           "FAILED 로 기록한다.",
                "round_limit": "강제 종료하고 그 시점 판단을 기록한다 (FAILED 아님).",
                "abort_threshold": {
                    "value_pct": 5,
                    "rule": "한 condition 에서 FAILED 가 5% 를 넘으면 그 실행을 "
                            "무효로 보고 원인을 고친 뒤 재실행한다. 부분 결과를 "
                            "확증 결과로 쓰지 않는다.",
                    "note": "사전등록 항목이다. 결과를 본 뒤 이 기준을 바꾸지 않는다.",
                },
            },
            "quota_scheduling": {
                "status": "Flash 주간 용량 미확인",
                "policy": "**과학적 설계를 바꾸는 근거로 쓰지 않는다.** 실행 스케줄 "
                          "문제로만 취급하고 필요하면 여러 quota window 에 나눠 돌린다.",
                "measured": {"five_hour_capacity_calls": 566,
                             "weekly": "미측정 — quota_ledger 로 누적 추정 중"},
                "estimated_primary_calls": {
                    "V": len(main_set) * 5, "V-tau": len(main_set) * 5,
                    "L0": len(main_set), "R0": 0,
                    "total": len(main_set) * 11,
                },
            },
        },

        # ── 부차 실험 ────────────────────────────────────────────────
        "secondary_experiment": {
            "cross_model_replication": {
                "model": "claude-sonnet-4-6",
                "separation": "**primary claim 과 분리된다.** 주 결과를 대체하거나 "
                              "보강하는 근거로 쓰지 않으며 재현성 확인 목적만이다.",
                "quota_measured": {"five_hour_capacity_calls": 61,
                                   "weekly_capacity_calls": 169},
                "scope_recorded_in_advance": {
                    "n_tasks": "30~40 (주간 용량 169회 ÷ 과제당 약 5회 = 약 34)",
                    "selection": "Main benchmark 92개에서 밴드 비율을 유지해 부분집합",
                    "conditions": "V 만. V−τ·L0 는 예산상 제외",
                    "note": "실제 범위는 실행 직전 quota 를 확인해 확정하고 "
                            "DECISION_LOG 에 기록한다. **이 범위를 결과를 본 뒤 "
                            "늘리지 않는다.**",
                },
            },
        },

        # ── 동결 후 순서 ────────────────────────────────────────────
        "next_steps_in_order": [
            "1) G5 오염 검사 — L0(도구 없음)가 R0 만큼 맞히면 «도구를 썼기 때문»이라는 "
            "주장이 무너진다",
            "2) dev/smoke 실행 — main N=92 와 **겹치지 않는** 과제로 end-to-end 확인",
            "3) 본실행 — V · V−τ · L0",
            "4) 부차: cross-model replication",
        ],
    }


def main():
    payload = build()
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    digest = hashlib.sha256(body.encode()).hexdigest()
    payload["sha256"] = digest
    payload.setdefault("provenance", {})["repo_commit"] = git_rev()

    if OUT.exists():
        prev = json.loads(OUT.read_text())
        if prev.get("sha256") == digest:
            print(f"이미 동결돼 있고 내용이 동일하다 (SHA-256 {digest[:16]}…).")
            return
        if "--force" not in sys.argv:
            raise SystemExit(
                f"동결 중단 — {OUT.name} 이 이미 존재하고 내용이 다르다.\n"
                f"  기존 {prev.get('sha256', '?')[:16]}…\n  신규 {digest[:16]}…\n\n"
                "불변조건 7 위반이 아닌지 확인하고, 정당한 재동결이면 "
                "DECISION_LOG 에 근거를 남기고 --force 로 실행할 것.")
        print("⚠️  --force — 기존 동결본을 덮어쓴다. DECISION_LOG 에 근거를 남길 것.\n")

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    pe = payload["primary_experiment"]
    ep = payload["execution_protocol"]
    print("Stage B 동결 완료\n")
    print(f"  Main benchmark      N={pe['main_benchmark']['n']} "
          f"{pe['main_benchmark']['per_band']}")
    print(f"  Conditions          {', '.join(pe['conditions'])}")
    print(f"  Primary model       {pe['primary_model']}")
    print(f"  3-agent             {' / '.join(pe['agents']['roles'])}")
    print(f"  Ident. challenge    primary {payload['identification_challenge']['primary']['n']} · "
          f"secondary {payload['identification_challenge']['secondary']['n']}")
    print()
    print(f"  프롬프트 버전        {ep['prompt_version']}")
    for k, v in ep["prompt_source_sha256"].items():
        print(f"    {k:<32} {v[:16]}…")
    print(f"  최대 라운드          {ep['max_rounds']}")
    print(f"  재시도 경로          {len(ep['retry_policy']['ladder'])}단 사다리")
    print(f"  실패 무효 기준        FAILED > {ep['failure_handling']['abort_threshold']['value_pct']}%")
    print(f"  예상 호출            {ep['quota_scheduling']['estimated_primary_calls']['total']}회 "
          f"(V·V−τ·L0, R0 는 0)")
    print()
    print(f"→ {OUT.relative_to(ROOT)}")
    print(f"   SHA-256 {digest}")
    print()
    print("다음 순서")
    for s in payload["next_steps_in_order"]:
        print(f"  {s}")


if __name__ == "__main__":
    main()
