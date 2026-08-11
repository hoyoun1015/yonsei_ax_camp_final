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
        """구조화 출력을 강제해 한 번 호출한다. 실패하면 재시도한다."""
        spath = self._schema_dir / f"{sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()[:16]}.json"
        if not spath.exists():
            spath.write_text(json.dumps(schema, ensure_ascii=False))

        cmd = [AGY, "-p", prompt, "--model", self.model,
               "--output-format", "json", "--json-schema", str(spath),
               "--disable-slash-commands"]
        if self.effort:
            cmd += ["--effort", self.effort]

        last_err = None
        for attempt in range(self.retries + 1):
            t0 = time.time()
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      timeout=self.timeout_s)
                out = proc.stdout.strip()
                payload = json.loads(out.splitlines()[-1]) if out else {}
            except subprocess.TimeoutExpired:
                payload, last_err = {}, f"시간초과 {self.timeout_s}s"
            except (json.JSONDecodeError, IndexError) as e:
                payload, last_err = {}, f"응답 파싱 실패: {e}"
            dt = time.time() - t0

            parsed = payload.get("structured_output")
            status = payload.get("status", "ERROR")
            if parsed is None:
                # 스키마 강제가 실패해도 본문이 JSON 이면 건져낸다. 실측에서
                # status=SUCCESS 인데 structured_output 이 비고 response 도 빈
                # 경우가 있었다(사고 토큰만 소비). 그 경우는 재시도로 넘어간다.
                raw = (payload.get("response") or "").strip()
                if raw.startswith("{"):
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        parsed = None
                if parsed is None and raw:
                    last_err = f"구조화 출력 없음. 본문 앞부분: {raw[:120]!r}"
                elif parsed is None:
                    last_err = "구조화 출력과 본문이 모두 비어 있다 (사고 토큰만 소비)"
            call = Call(
                call_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc).isoformat(),
                task_id=task_id, condition=self.condition, agent_role=agent_role,
                model=self.model, quota_group=self.quota_group, round=round,
                prompt_version=prompt_version,
                prompt_sha256=sha256(prompt.encode()).hexdigest(),
                prompt=prompt,
                raw_response=payload.get("response", ""),
                parsed=parsed, status=status, duration_s=round_(dt),
                usage=payload.get("usage", {}) or {},
                conversation_id=payload.get("conversation_id"),
                error=None if parsed else (last_err or f"status={status}"),
            )
            self.ledger.write(call)

            if parsed is not None and status == "SUCCESS":
                return parsed
            last_err = call.error
        raise BackendError(
            f"{agent_role} 호출이 {self.retries + 1}회 모두 실패했다: {last_err}")


def round_(x: float, n: int = 3) -> float:
    return float(f"{x:.{n}f}")
