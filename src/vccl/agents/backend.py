"""LLM 백엔드 어댑터와 호출 원장.

**백엔드는 교체 가능해야 한다.** 한 실험 condition 안에서는 세 역할이 **같은 모델**을
쓴다 — 역할별로 모델을 섞으면 결과의 원인을 모델 차이에 귀속할 수 없다.

지금 구현은 Antigravity CLI(`agy`)를 headless subprocess 로 호출한다.

| 후보 모델 | 용도 | quota 그룹 |
|---|---|---|
| `gemini-3.6-flash-high` | 개발·파일럿, large-N 주 실행 | Gemini |
| `gemini-3.1-pro-high` | 고품질 확인 실험 | Gemini |
| `claude-sonnet-4-6` | 독립 replication | Claude/GPT (별도 quota) |

**모든 호출을 원장에 남긴다.** 재현과 사후 분석이 로그만으로 가능해야 한다 —
task_id · 역할 · 모델 · 라운드 · 프롬프트 버전과 해시 · 원본 응답 · 파싱된 결정 ·
선택한 계산 수준 · 도구 실행 결과 · 타임스탬프 · 토큰 사용량.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
AGY = os.environ.get("AGY_BIN", str(Path.home() / ".local" / "bin" / "agy"))
DEFAULT_TIMEOUT_S = 300

GEMINI_QUOTA = "gemini"
ANTHROPIC_QUOTA = "claude-gpt"
QUOTA_GROUP = {
    "gemini-3.6-flash-high": GEMINI_QUOTA,
    "gemini-3.6-flash-medium": GEMINI_QUOTA,
    "gemini-3.1-pro-high": GEMINI_QUOTA,
    "gemini-3.1-pro-low": GEMINI_QUOTA,
    "claude-sonnet-4-6": ANTHROPIC_QUOTA,
    "claude-opus-4-6-thinking": ANTHROPIC_QUOTA,
    "gpt-oss-120b-medium": ANTHROPIC_QUOTA,
}


class BackendError(RuntimeError):
    pass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, o: "Usage") -> "Usage":
        return Usage(*(getattr(self, f) + getattr(o, f) for f in
                       ("input_tokens", "output_tokens", "thinking_tokens",
                        "cache_read_tokens", "total_tokens")))


@dataclass
class Call:
    """원장 한 줄. 이 레코드만으로 호출을 재구성할 수 있어야 한다."""
    call_id: str
    timestamp: str
    task_id: str
    condition: str
    agent_role: str
    model: str
    quota_group: str
    round: int
    prompt_version: str
    prompt_sha256: str
    prompt: str
    raw_response: str
    parsed: dict[str, Any] | None
    status: str
    duration_s: float
    usage: dict[str, int]
    conversation_id: str | None = None
    error: str | None = None
    # 이 호출에서 파생된 행동 — 있으면 채운다
    level_selected: str | None = None
    tool_result: dict[str, Any] | None = None


class Ledger:
    """JSONL 원장. 한 줄 = 한 호출."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.calls: list[Call] = []

    def write(self, call: Call) -> None:
        self.calls.append(call)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(call), ensure_ascii=False) + "\n")

    @property
    def usage(self) -> Usage:
        tot = Usage()
        for c in self.calls:
            tot = tot + Usage(**c.usage)
        return tot

    def summary(self) -> dict[str, Any]:
        by_role: dict[str, int] = {}
        by_quota: dict[str, dict[str, int]] = {}
        for c in self.calls:
            by_role[c.agent_role] = by_role.get(c.agent_role, 0) + 1
            q = by_quota.setdefault(c.quota_group, {"calls": 0, "total_tokens": 0})
            q["calls"] += 1
            q["total_tokens"] += c.usage.get("total_tokens", 0)
        u = self.usage
        return {"n_calls": len(self.calls), "by_role": by_role,
                "by_quota_group": by_quota, "usage": asdict(u),
                "failures": sum(1 for c in self.calls if c.status != "SUCCESS")}


@dataclass
class Backend:
    """교체 가능한 LLM 백엔드. condition 하나 = 모델 하나."""
    model: str
    ledger: Ledger
    condition: str = "V"
    effort: str | None = None
    timeout_s: int = DEFAULT_TIMEOUT_S
    retries: int = 2
    _schema_dir: Path = field(default=None, repr=False)

    def __post_init__(self):
        if self.model not in QUOTA_GROUP:
            raise BackendError(
                f"알 수 없는 모델 '{self.model}'. `agy models` 로 확인할 것. "
                f"등록된 모델 {sorted(QUOTA_GROUP)}")
        self._schema_dir = ROOT / "experiments" / "_schemas"
        self._schema_dir.mkdir(parents=True, exist_ok=True)

    @property
    def quota_group(self) -> str:
        return QUOTA_GROUP[self.model]

    def ask(self, *, task_id: str, agent_role: str, round: int,
            prompt: str, schema: dict, prompt_version: str) -> dict:
        """구조화 출력을 받는다. **실패하면 경로를 바꿔 재시도한다.**

        초안은 동일한 요청을 그대로 반복했다. 그런데 실측에서 실패가 프롬프트·스키마
        조합에 결정적이어서 3회 재시도가 모두 같은 방식으로 실패했다
        (`status=SUCCESS` 인데 structured_output·response 가 모두 빔).
        그래서 시도마다 **다른 경로**를 쓴다.

          1  --json-schema + 프롬프트 형식 지시
          2  --json-schema 없이 프롬프트 형식 지시만 (CLI 강제를 우회)
          3  2 + 이전 시도가 비었다는 사실을 알려 재요청

        `--effort` 는 쓰지 않는다 — `-high`/`-low` 가 붙은 모델명과 충돌해
        "invalid model selection" 하드 에러가 난다(0 토큰).
        """
        nudge = _json_nudge(schema)
        # 실측 순서다(N=12 × 4변형, diagnose_empty.py).
        #   플래그 없이 프롬프트 지시   24/24 성공 · 평균 18.3k 토큰 · 12.3초
        #   --json-schema 강제          20/24 성공 · 평균 24.0k 토큰 · 17.0초
        # 플래그 경로에서만 빈 응답이 나왔고, 25% 비싸고 24% 느리다.
        # 그래서 플래그 없는 경로를 1순위로 두고, 실패 시 «다른 경로»로 넘어간다.
        ladder = [
            {"use_flag": False, "suffix": nudge},
            {"use_flag": True, "suffix": nudge},
            {"use_flag": False, "suffix": nudge + _RETRY_HINT},
        ]

        last_err = None
        for attempt, step in enumerate(ladder, 1):
            full = prompt + step["suffix"]
            cmd = [AGY, "-p", full, "--model", self.model,
                   "--output-format", "json", "--disable-slash-commands"]
            if step["use_flag"]:
                cmd += ["--json-schema", str(self._schema_path(schema))]

            t0 = time.time()
            payload: dict[str, Any] = {}
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      timeout=self.timeout_s)
                out = proc.stdout.strip()
                payload = json.loads(out.splitlines()[-1]) if out else {}
            except subprocess.TimeoutExpired:
                last_err = f"시간초과 {self.timeout_s}s"
            except (json.JSONDecodeError, IndexError) as e:
                last_err = f"CLI 응답 파싱 실패: {e}"
            dt = time.time() - t0

            status = payload.get("standard_status", payload.get("status", "ERROR"))
            parsed = payload.get("structured_output")
            raw = (payload.get("response") or "").strip()
            if parsed is None:
                parsed = _salvage(raw, schema)
            if parsed is None:
                last_err = (payload.get("error")
                            or ("빈 응답 (사고 토큰만 소비)" if not raw
                                else f"JSON 을 건져내지 못했다: {raw[:120]!r}"))

            self.ledger.write(Call(
                call_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc).isoformat(),
                task_id=task_id, condition=self.condition, agent_role=agent_role,
                model=self.model, quota_group=self.quota_group, round=round,
                prompt_version=f"{prompt_version}#try{attempt}"
                               f"{'' if step['use_flag'] else '+noflag'}",
                prompt_sha256=sha256(full.encode()).hexdigest(),
                prompt=full, raw_response=raw, parsed=parsed, status=status,
                duration_s=round_(dt), usage=payload.get("usage", {}) or {},
                conversation_id=payload.get("conversation_id"),
                error=None if parsed is not None else last_err,
            ))
            if parsed is not None:
                return parsed
        raise BackendError(
            f"{agent_role} 호출이 경로 {len(ladder)}개 모두 실패했다: {last_err}")

    def _schema_path(self, schema: dict) -> Path:
        p = self._schema_dir / (
            sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()[:16] + ".json")
        if not p.exists():
            p.write_text(json.dumps(schema, ensure_ascii=False))
        return p


_RETRY_HINT = ("\n\n⚠️ 이전 시도에서 응답이 비어 있었다. **추론을 짧게 하고 "
               "위 JSON 객체만 즉시 출력하라.**")


def _json_nudge(schema: dict) -> str:
    """프롬프트에 출력 형식을 명시한다. CLI 강제를 쓰지 않는 경로에서 필수다.

    **enum 을 JSON 배열로 렌더링하면 안 된다.** 초안이 `"level": ["L1","L3"]` 로
    적었더니 claude-sonnet-4-6 이 "값이 배열이다"로 읽고 `{"level": ["L1"]}` 을
    돌려줬다(3/3 실패). Gemini 는 "둘 중 하나"로 읽어 우연히 통과했다.
    선택지는 배열이 아니라 **택일**임을 문법으로 드러낸다.
    """
    lines = []
    for k, v in schema["properties"].items():
        if v.get("enum"):
            spec = " | ".join(f'"{x}"' for x in v["enum"])
        elif v.get("type") == "boolean":
            spec = "true | false"
        elif v.get("type") == "integer":
            spec = "<정수>"
        elif v.get("type") == "number":
            spec = "<숫자>"
        else:
            spec = '"<문자열>"'
        lines.append((f'  "{k}": {spec}',
                      f"  // {v['description']}" if v.get("description") else ""))
    body = ",\n".join(a for a, _ in lines)
    # 주석은 별도 목록으로 둔다 — 값 뒤에 붙이면 콤마와 뒤섞여 읽기 어렵다
    notes = "\n".join(f'  {k.strip()}{c}' for (k, c) in
                      ((a.split(":")[0], c) for a, c in lines) if c)
    return ("\n\n## 출력 형식\n\n**아래 형태의 JSON 객체 하나만 출력한다.** "
            "설명문·코드펜스·머리말을 붙이지 않는다.\n"
            "`|` 는 택일을 뜻한다 — 배열이 아니라 값 하나를 고른다.\n\n"
            "{\n" + body + "\n}"
            + (f"\n\n각 항목의 뜻:\n{notes}" if notes.strip() else ""))


def _salvage(raw: str, schema: dict) -> dict | None:
    """본문에서 JSON 을 건져내고 필수 키를 검증한다. 코드펜스를 벗긴다."""
    if not raw:
        return None
    body = raw
    if "```" in body:
        parts = body.split("```")
        body = max(parts, key=len)
    i, j = body.find("{"), body.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        cand = json.loads(body[i:j + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(cand, dict):
        return None
    if [k for k in schema.get("required", []) if k not in cand]:
        return None
    # 타입·enum 을 검증한다. 키만 보면 `{"level": ["L1"]}` 같은 응답이 통과해
    # 뒤에서 unhashable 로 터진다(claude-sonnet-4-6 실측).
    for k, spec in schema.get("properties", {}).items():
        if k not in cand:
            continue
        v = cand[k]
        if spec.get("enum") is not None and v not in spec["enum"]:
            return None
        want = spec.get("type")
        if want == "string" and not isinstance(v, str):
            return None
        if want == "boolean" and not isinstance(v, bool):
            return None
        if want == "integer" and not isinstance(v, int):
            return None
        if want == "number" and not isinstance(v, (int, float)):
            return None
    return cand


def read_quota(timeout_s: int = 120) -> dict[str, dict[str, str]]:
    """Antigravity 의 남은 quota 를 조회한다 (`/usage`).

    실험 전후로 찍어 실제 소비량을 기록한다. 토큰 합계만으로는 quota 소비를
    알 수 없다 — 창(5시간/주간)별 백분율이 별도로 관리된다.
    """
    out = subprocess.run([AGY, "-p", "/usage", "--model", "gemini-3.6-flash-high",
                          "--output-format", "json"],
                         capture_output=True, text=True, timeout=timeout_s).stdout
    try:
        body = json.loads(out.strip().splitlines()[-1]).get("response", "")
    except (json.JSONDecodeError, IndexError):
        return {}
    quota: dict[str, dict[str, str]] = {}
    for line in body.splitlines():
        parts = [x.strip() for x in line.split("\t") if x.strip()]
        if len(parts) >= 3:
            group, window, pct = parts[0], parts[1], parts[2]
            quota.setdefault(group, {})[window] = pct
    return quota


def round_(x: float, n: int = 3) -> float:
    return float(f"{x:.{n}f}")
