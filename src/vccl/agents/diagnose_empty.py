"""empty SUCCESS 실패 모드 진단.

**증상.** `agy` 가 `status=SUCCESS` 를 돌려주면서 `structured_output` 과 `response` 가
모두 비어 있다. 사고 토큰만 소비하고 최종 출력이 없다. 재시도해도 같은 방식으로 실패한다.

**파일럿 실측 (gemini-3.6-flash-high, 37호출).** 실패 13회(35%)가 스키마 크기에
정확히 상관했다.

| 프롬프트 | 스키마 속성 수 | 실패 |
|---|---:|---:|
| choose_level | 2 | 9 |
| conclude | 3 | 4 |
| review | 4 | 0 |
| operationalize | 6 | 0 |

**가설.** 속성이 적은 스키마에서 최종 출력이 비는 경향이 있다. 대안 셋을 비교한다.

  A 대조군    현행 그대로
  B effort    --effort low — 이 결정은 단순하므로 깊은 사고가 불필요하다
  C 스키마    필드를 늘려 review/operationalize 와 같은 형태로 만든다

사용: python3 src/vccl/agents/diagnose_empty.py [--n 5] [--model ...]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AGY = str(Path.home() / ".local" / "bin" / "agy")
SDIR = ROOT / "experiments" / "_schemas"
SDIR.mkdir(parents=True, exist_ok=True)

# 파일럿에서 9회 실패한 실제 프롬프트 (choose_level)
PROMPT = """당신은 계산화학 연구팀의 Computational Chemist다. 어느 계산 수준으로 실행할지 정하라.

## 검증할 비교

**S2** 대 **S1** — 상대 전자에너지

## 선택지

- **L1** — GFN2-xTB 단일점. 반응당 약 0.02초.
- **L3** — B3LYP-D3(BJ)/def2-TZVP 단일점. 반응당 25초~53분 (원자 수에 따라).

## 이 방법들의 알려진 오차 (방법오차 τ)

- L1 (GFN2-xTB): **1.21 kcal/mol**
- L3 (B3LYP-D3(BJ)/def2-TZVP): **0.41 kcal/mol**

계산된 에너지 차이가 그 방법의 τ보다 작으면, 그 차이는 방법오차 안에 묻혀 있어
어느 쪽이 안정한지 **말할 수 없다.**

비용 격차가 1,000배 이상이다. 값싼 수준으로 충분하면 올리는 것은 낭비이고,
부족한데 올리지 않으면 판정할 수 없다.

## 할 일

이번 라운드에 실행할 수준 하나를 고르고 이유를 적는다."""

SCHEMA_SMALL = {
    "type": "object",
    "properties": {
        "level": {"type": "string", "enum": ["L1", "L3"]},
        "reasoning": {"type": "string"},
    },
    "required": ["level", "reasoning"],
    "additionalProperties": False,
}

# 필드를 늘린 형태 — 실패하지 않는 스키마(review, operationalize)와 같은 규모
SCHEMA_RICH = {
    "type": "object",
    "properties": {
        "level": {"type": "string", "enum": ["L1", "L3"],
                  "description": "실행할 계산 수준"},
        "expected_resolvable": {
            "type": "boolean",
            "description": "이 수준의 τ 로 방향을 판정할 수 있다고 보는가"},
        "cost_consideration": {
            "type": "string", "description": "비용 대 정확도를 어떻게 저울질했는가"},
        "reasoning": {"type": "string", "description": "선택 이유"},
    },
    "required": ["level", "expected_resolvable", "cost_consideration", "reasoning"],
    "additionalProperties": False,
}


def spath(schema):
    p = SDIR / f"{sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()[:16]}.json"
    p.write_text(json.dumps(schema, ensure_ascii=False))
    return p


JSON_NUDGE = """

## 출력 형식

**아래 JSON 객체 하나만 출력한다.** 설명문·코드펜스·머리말을 붙이지 않는다.

{schema}
"""


def call(model, schema, effort=None, timeout=300, use_schema_flag=True):
    prompt = PROMPT
    cmd = [AGY, "-p", None, "--model", model, "--output-format", "json",
           "--disable-slash-commands"]
    if use_schema_flag:
        cmd += ["--json-schema", str(spath(schema))]
    else:
        # --json-schema 를 쓰지 않고 프롬프트로 형식을 지시한 뒤 파이썬에서 검증한다
        prompt = PROMPT + JSON_NUDGE.format(
            schema=json.dumps({k: (v.get("enum") or v["type"])
                               for k, v in schema["properties"].items()},
                              ensure_ascii=False))
    cmd[2] = prompt
    if effort:
        cmd += ["--effort", effort]
    t0 = time.time()
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=timeout).stdout.strip()
        p = json.loads(out.splitlines()[-1]) if out else {}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "why": f"{type(e).__name__}", "dt": time.time() - t0,
                "usage": {}}
    u = p.get("usage", {}) or {}
    so = p.get("structured_output")
    resp = (p.get("response") or "").strip()
    if so is None and resp:
        # 코드펜스를 벗기고 JSON 을 건져낸 뒤 필수 키를 검증한다
        body = resp
        if body.startswith("```"):
            body = body.split("```")[1]
            body = body[body.find("{"):]
        try:
            cand = json.loads(body[body.find("{"):body.rfind("}") + 1])
            if all(k in cand for k in schema["required"]):
                so = cand
        except (json.JSONDecodeError, ValueError):
            so = None
    ok = so is not None
    return {"ok": ok, "why": "" if ok else ("empty" if not resp else "unparsed"),
            "dt": time.time() - t0, "usage": u,
            "out_tok": u.get("output_tokens", 0), "think": u.get("thinking_tokens", 0),
            "total": u.get("total_tokens", 0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--model", default="gemini-3.6-flash-high")
    args = ap.parse_args()

    # B·D(effort) 는 제외한다 — --effort 는 -high/-low 모델명과 충돌해 하드 에러다
    # ("invalid model selection ... conflicts with --effort=low", 0 토큰)
    variants = [
        ("A 대조군 (스키마강제)", SCHEMA_SMALL, None, True),
        ("C 스키마 확장", SCHEMA_RICH, None, True),
        ("E 플래그 없이 프롬프트", SCHEMA_SMALL, None, False),
        ("F 확장+프롬프트", SCHEMA_RICH, None, False),
    ]

    print(f"모델 {args.model} · 변형당 {args.n}회\n")
    print(f"{'변형':<20}{'성공':>6}{'빈응답':>7}{'평균 out':>9}{'평균 think':>11}{'평균 total':>11}{'평균 초':>8}")
    print("-" * 74)
    summary = {}
    for name, schema, effort, use_flag in variants:
        rs = [call(args.model, schema, effort, use_schema_flag=use_flag)
              for _ in range(args.n)]
        ok = sum(r["ok"] for r in rs)
        empty = sum(1 for r in rs if r["why"] == "empty")
        avg = lambda k: sum(r.get(k, 0) for r in rs) / len(rs)  # noqa: E731
        print(f"{name:<20}{ok}/{args.n:<4}{empty:>7}{avg('out_tok'):>9.0f}"
              f"{avg('think'):>11.0f}{avg('total'):>11.0f}{avg('dt'):>8.1f}")
        summary[name] = {"ok": ok, "n": args.n, "empty": empty,
                         "avg_total_tokens": round(avg("total")),
                         "avg_seconds": round(avg("dt"), 1)}

    out = ROOT / "experiments" / f"diagnose_empty_{args.model}.json"
    out.write_text(json.dumps({"model": args.model, "n_per_variant": args.n,
                               "variants": summary}, ensure_ascii=False, indent=2))
    print(f"\n→ {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
