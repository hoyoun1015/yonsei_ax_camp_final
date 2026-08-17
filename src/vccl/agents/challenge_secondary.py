"""Identification challenge — **secondary 94** · condition V 단독.

사후등록 `docs/DECISION_LOG.md` 2026-08-16 (3) **post-hoc amendment**.

🔒 **이것은 확증 분석이 아니다.** primary 24 의 결과를 본 뒤 실행을 결정한
**post-hoc exploratory / descriptive supplementary analysis** 다. 새로운 p-value·
유의성 검정·확증 신뢰구간을 만들지 않고, primary 24 의 사전 지정 Poisson-binomial
검정과 결론을 바꾸지 않는다. RQ1 전체를 입증한다고 쓰지 않는다.

🔒 **관측 단위** — 동결본 문구 그대로 *"화학종 24종에서 나온 94개 관측"* 이다.
94 를 독립 표본처럼 취급하지 않는다 (한 화학종이 반응을 여럿 낸다 · pseudo-replication).

**primary 24 는 다시 실행하지 않는다.** 동결 secondary 94 안에 primary 24 가 전부
포함되어 있으므로 그 24 관측은 기존 결과에서 재사용하고, 아직 실행되지 않은 **70개만**
새로 실행한다. 같은 과제를 확률적 LLM 으로 재실행해 두 관측 중 하나를 고르는 것 자체가
선택 편향이다. 재사용 전 10가지 assertion 을 코드가 강제한다 (`preflight`).

**동결본과 기존 실행 경로를 그대로 쓴다.** 프롬프트·채점·τ·라벨을 새로 만들지 않고
`main_run` 의 `verify_frozen` · `to_spec` · `score_run` 과 `loop.run_task` ·
`pairs.load_tau` 를 import 한다. `challenge.py` 는 primary 24 의 provenance 이므로
건드리지 않고, `loop.py` · `schemas.py` · `prompts.py` · `main_run.py` · 동결 JSON 도
수정하지 않는다.

🔒 **chunk 사이에는 성능을 보지 않는다.** `--run` 은 quota · FAILED · 과제 커버리지 ·
동결 해시 · 원장 무결성만 출력한다. identification accuracy 와 부분집단 결과는
신규 70 이 전부 끝나고 `--finalize` 로 94 행이 모인 뒤 `--report` 에서만 나온다.

🔒 **provenance guard** (`DECISION_LOG` 2026-08-16 (5)) — 실행 전에 네 가지를 강제한다.

1. **모델은 상수다.** `--model` 옵션이 없다. 신규 70 은 `MODEL` 로만 돌아가고
   `--finalize` 도 CLI 인자가 아니라 상수를 쓴다. primary 의 model 만 검사하는 것으로는
   부족하다 — 신규분을 다른 모델로 돌리면 재사용 24 와 섞이는 순간 조건이 갈라진다.
2. **재사용 원본이 고정돼 있다.** 「최신 `chal_primary_*`」 자동 선택을 쓰지 않는다.
   경로와 파일 sha256 이 상수이며 `preflight` 가 대조한다.
3. **`--finalize` 가 chunk 자체의 provenance 를 다시 본다** — set·chunk 번호·조건·
   모델·동결 해시·task 순서·행 수·중복. 하나라도 어긋나면 결과 파일을 쓰지 않고,
   이미 있는 결과를 조용히 덮어쓰지도 않는다.
4. **미완료 attempt 는 자동 재실행을 막는다.** 디렉터리는 있는데
   `chunk_result.json` 이 없으면 중간에 죽은 실행이다. `--audit` 로 원장·범위·
   실패원인만 보고, `INVALID.md` 와 `DECISION_LOG` 기록을 남긴 뒤에야 다시 돈다.
5. **실행 유효성의 분모는 신규 실행 70 이다** (`DECISION_LOG` 2026-08-16 (7)).
   결합 94 중 24 는 이미 성공이 알려진 재사용이라 분모에 넣으면 신규 실행의 기술적
   실패율이 희석된다. 신규 FAILED 가 4건에 닿는 즉시 **추가 호출 없이 멈추고**
   `chunk_result.json` 을 쓰지 않는다 — 정상 결과로 위장하지 않으며 `--finalize`
   가 유효한 chunk 로 받아들이지 않는다. 결합 94 비율은 기술 통계로만 적는다.

사용:
    python3 src/vccl/agents/challenge_secondary.py --selftest    # LLM 0회 — 전제 검증
    python3 src/vccl/agents/challenge_secondary.py --run 1       # 신규 1–35
    python3 src/vccl/agents/challenge_secondary.py --status      # chunk 사이 확인
    python3 src/vccl/agents/challenge_secondary.py --run 2       # 신규 36–70
    python3 src/vccl/agents/challenge_secondary.py --finalize    # 94행 구성
    python3 src/vccl/agents/challenge_secondary.py --report      # 기술통계 (검정 없음)
    python3 src/vccl/agents/challenge_secondary.py --audit 1     # 미완료 attempt 감사
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.agents import quota_ledger  # noqa: E402
from vccl.agents.backend import Backend, Ledger, read_quota  # noqa: E402
from vccl.agents.loop import run_task  # noqa: E402
from vccl.agents.main_run import (  # noqa: E402
    ABORT_PCT, score_run, to_spec, verify_frozen,
)
from vccl.tasks.pairs import build_pool, load_tau  # noqa: E402

STAGE_A = ROOT / "data" / "tasks" / "frozen_rules_v1.json"
STAGE_B = ROOT / "data" / "tasks" / "frozen_stage_b_v1.json"
ORDER = ROOT / "data" / "tasks" / "execution_order_v1.json"
EXP = ROOT / "experiments"

CONDITION = "V"

# 🔒 모델은 상수다. CLI 로 바꿀 수 없다 — `--model` 옵션 자체를 두지 않는다.
#    primary 24 의 model 을 검사하는 것만으로는 부족하다. 신규 70 을 다른 모델로
#    돌리면 재사용 24 와 섞이는 순간 조건이 갈라진다. 실행 전에 강제한다.
MODEL = "gemini-3.6-flash-high"

# 🔒 재사용 원본을 지금 고정한다. 「최신 chal_primary_*」 자동 선택은 쓰지 않는다 —
#    나중에 더 최신 디렉터리가 생기면 재사용 원본이 조용히 바뀐다.
#    (DECISION_LOG 2026-08-16 (5))
PRIMARY_SOURCE = ("experiments/chal_primary_20260814T235648Z_gemini-3.6-flash-high"
                  "/challenge_result.json")
PRIMARY_SHA256 = "7c102f338210a80760489ded67a295c123f935db3dd148e1f9ce558fca1fab4a"

N_PRIMARY, N_SECONDARY, N_NEW = 24, 94, 70
CHUNKS = {1: (0, 35), 2: (35, 70)}         # remaining_ids 의 슬라이스 — 결과 보기 전 고정
CHUNK_SIZE = 35

# 🔒 **실행 유효성 게이트의 분모는 신규 실행 70 이다** (2026-08-16 정정).
#    처음에는 결합 94 를 분모로 잡았으나, 그 94 중 24 는 **이미 성공이 알려진**
#    primary 결과를 재사용하는 것이라 신규 실행의 기술적 실패율이 희석된다.
#    execution-integrity 는 이번에 실제로 API 를 태운 70 으로만 잰다.
#    (DECISION_LOG 2026-08-16 (7))
NEW_EXEC_DENOM = N_NEW                     # 70

# 70 기준 5% 초과 = 4건 이상 (3/70 = 4.29% 이내 · 4/70 = 5.71% 초과)
FAILED_ABORT_N = int(NEW_EXEC_DENOM * ABORT_PCT / 100.0) + 1

# 결합 94 기준 비율은 **기술 통계로만** 보고하고 유효성 판정에 쓰지 않는다.
COMBINED_DENOM = N_SECONDARY               # 94

PROV_REUSE, PROV_NEW = "primary_reuse", "secondary_new"

# 미완료 attempt 를 무효 처리하고 다시 돌리려면 그 디렉터리에 INVALID.md 가 있어야
# 하고, 그 안에 아래 선언과 DECISION_LOG 참조가 들어 있어야 한다.
INVALID_FILE = "INVALID.md"
INVALID_DECL = "부분 성능을 보고 선택한 재실행이 아니다"


# ── 동결 과제집합 ────────────────────────────────────────────────────
def frozen_sets() -> tuple[list[str], list[str]]:
    ic = json.loads(STAGE_B.read_text())["identification_challenge"]
    return ic["primary"]["task_ids"], ic["secondary"]["task_ids"]


def remaining_ids() -> list[str]:
    """동결 secondary 순서를 그대로 두고 primary 24 를 뺀 70개. 결정론적이다."""
    pri, sec = frozen_sets()
    pset = set(pri)
    return [t for t in sec if t not in pset]


def chunk_ids(n: int) -> list[str]:
    lo, hi = CHUNKS[n]
    return remaining_ids()[lo:hi]


def frozen_hashes() -> dict[str, str]:
    return {"stage_a": json.loads(STAGE_A.read_text())["sha256"],
            "stage_b": json.loads(STAGE_B.read_text())["sha256"],
            "execution_order": json.loads(ORDER.read_text())["sha256"]}


def file_sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    """저장소 기준 상대경로. 밖이면 절대경로 그대로 — 경로 때문에 터지지 않는다."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


# ── 기존 primary 결과 ────────────────────────────────────────────────
def primary_result_path() -> Path | None:
    """🔒 **고정 경로**를 돌려준다. 최신 디렉터리를 자동 선택하지 않는다.

    더 최신 `chal_primary_*` 가 생겨도 재사용 원본은 바뀌지 않는다. 파일 자체의
    sha256 도 `preflight` 가 `PRIMARY_SHA256` 과 대조한다.
    """
    p = EXP / Path(PRIMARY_SOURCE).relative_to("experiments")
    return p if p.exists() else None


def chunk_dir(n: int) -> Path | None:
    """**완성된** chunk 디렉터리. `chunk_result.json` 이 있어야 완성으로 본다."""
    ds = sorted(d for d in EXP.glob(f"chal_sec_c{n}_*")
                if (d / "chunk_result.json").exists())
    return ds[-1] if ds else None


def incomplete_attempts(n: int) -> list[Path]:
    """중간에 죽은 attempt — 디렉터리는 있는데 `chunk_result.json` 이 없다.

    이것을 무시하고 같은 chunk 를 새로 돌리면 **부분 실행이 조용히 사라진다.**
    자동 재실행을 막고 감사를 먼저 하게 한다.
    """
    return sorted(d for d in EXP.glob(f"chal_sec_c{n}_*")
                  if not (d / "chunk_result.json").exists())


def attempt_documented(d: Path) -> bool:
    """무효 처리가 문서화됐는가 — INVALID.md + 선언 + DECISION_LOG 참조."""
    f = d / INVALID_FILE
    if not f.exists():
        return False
    t = f.read_text()
    return INVALID_DECL in t and "DECISION_LOG" in t


def undocumented_attempts(n: int) -> list[Path]:
    return [d for d in incomplete_attempts(n) if not attempt_documented(d)]


def chunk_rows(n: int) -> list[dict]:
    d = chunk_dir(n)
    return [] if d is None else json.loads((d / "chunk_result.json").read_text())["rows"]


def cumulative_failed() -> int:
    """누적 FAILED. primary 24 는 0 임이 assertion 되므로 신규분만 센다."""
    return sum(r["failed"] for n in CHUNKS for r in chunk_rows(n))


# ── preflight — 10가지 assertion (LLM 0회) ───────────────────────────
def preflight() -> dict:
    """하나라도 어긋나면 실행하지 않는다. 읽기 전용이다."""
    checks: list[tuple[str, bool, str]] = []

    def chk(name: str, good: bool, detail: str = "") -> bool:
        checks.append((name, bool(good), detail))
        return bool(good)

    ok = True
    v = verify_frozen()
    for name, good, h in v["checks"]:
        ok &= chk(f"동결 {name}", good, h)

    pri, sec = frozen_sets()
    ok &= chk("① primary n = 24", len(pri) == N_PRIMARY, f"{len(pri)}")
    ok &= chk("② secondary n = 94", len(sec) == N_SECONDARY, f"{len(sec)}")
    ok &= chk("③ primary ⊆ secondary", set(pri) <= set(sec),
              "포함" if set(pri) <= set(sec) else f"밖 {len(set(pri) - set(sec))}개")
    inter = len(set(pri) & set(sec))
    ok &= chk("④ 교집합 = 24", inter == N_PRIMARY, f"{inter}")
    rem = remaining_ids()
    ok &= chk("⑤ 신규 실행 대상 = 70", len(rem) == N_NEW, f"{len(rem)}")
    dup = len(sec) - len(set(sec))
    ok &= chk("⑥ secondary ID 중복 = 0", dup == 0, f"{dup}")

    pp = primary_result_path()
    if pp is None:
        ok &= chk("⑦⑧⑨⑩ primary 결과 파일", False,
                  f"🔴 고정 경로에 없다 — {PRIMARY_SOURCE}")
        p = None
    else:
        got = file_sha256(pp)
        # 경로는 마지막 두 조각(디렉터리·파일명)으로 본다 — 저장소 밖에서 돌려도
        # 성립하고, 「최신 자동 선택」으로 되돌아가면 반드시 깨진다.
        ok &= chk("⑦− 재사용 원본이 고정 경로",
                  pp.parts[-2:] == Path(PRIMARY_SOURCE).parts[-2:],
                  "/".join(pp.parts[-2:]))
        ok &= chk("⑦− 재사용 원본 sha256 고정값", got == PRIMARY_SHA256,
                  f"{got[:16]}…" + ("" if got == PRIMARY_SHA256 else " 🔴 다르다"))
        p = json.loads(pp.read_text())
        ok &= chk("⑦ primary model", p.get("model") == MODEL,
                  f"{p.get('model')}")
        ok &= chk("⑧ primary condition", p.get("condition") == CONDITION,
                  f"{p.get('condition')}")
        fh, pf = frozen_hashes(), p.get("frozen", {})
        same = all(pf.get(k) == v_ for k, v_ in fh.items())
        ok &= chk("⑨ 동결 해시 3종 일치", same,
                  " · ".join(f"{k}={'○' if pf.get(k) == v_ else '×'}"
                             for k, v_ in fh.items()))
        rows = p.get("rows", [])
        nf = sum(r["failed"] for r in rows)
        ok &= chk("⑩ primary FAILED = 0", nf == 0 and len(rows) == N_PRIMARY,
                  f"FAILED {nf} · 행 {len(rows)}")
        ok &= chk("⑩+ primary 행 tid = 동결 primary",
                  {r["tid"] for r in rows} == set(pri), "")
        ok &= chk("⑩+ primary 는 smoke 가 아니다", p.get("smoke") is False,
                  f"smoke={p.get('smoke')}")

    # ⑪ 미완료 attempt — 무시하고 새로 돌리면 부분 실행이 조용히 사라진다
    bad_att = {n: undocumented_attempts(n) for n in CHUNKS}
    n_bad = sum(len(v) for v in bad_att.values())
    ok &= chk("⑪ 문서화되지 않은 미완료 attempt = 0", n_bad == 0,
              "없다" if not n_bad else " · ".join(
                  f"chunk {n}: {d.name}" for n, v in bad_att.items() for d in v))

    return {"ok": ok, "checks": checks, "primary_path": pp, "primary": p,
            "remaining": rem, "incomplete": bad_att}


def print_preflight(pf: dict) -> None:
    for name, good, detail in pf["checks"]:
        print(f"  {'🟢' if good else '🔴'} {name:<42} {detail}")


# ── 과제 메타 (기존 species-mapping 로직 재사용) ─────────────────────
def enrich(row: dict, entry: dict, prov: str, idx: int) -> dict:
    """행에 provenance 와 과제 메타를 붙인다. **채점값은 건드리지 않는다.**

    화학종은 `build_pool()` 이 이미 붙여 놓은 `species` 를 그대로 쓴다 — 동결
    `identification_challenge()` 가 세트를 만들 때 쓴 키와 같은 `(subset, species)` 다.
    task 문자열을 잘라 추정하지 않는다.
    """
    out = dict(row)
    out["provenance"] = prov
    out["secondary_index"] = idx
    out["subset"] = entry["subset"]
    out["species"] = entry["species"]
    out["species_key"] = f"{entry['subset']}:{entry['species']}"
    out["n_candidates"] = entry["n_candidates"]
    return out


# ── selftest — LLM 0회 ───────────────────────────────────────────────
def selftest() -> bool:
    print("=" * 78)
    print("challenge secondary selftest — LLM 호출 0회")
    print("=" * 78)
    print("사후등록 docs/DECISION_LOG.md 2026-08-16 (3) · post-hoc exploratory")

    pf = preflight()
    print("\n동결 검증 · 재사용 assertion")
    print_preflight(pf)
    ok = pf["ok"]

    ic = json.loads(STAGE_B.read_text())["identification_challenge"]
    print("\n동결본 규정 (그대로 인용)")
    print(f"  secondary.use   {ic['secondary']['use']}")
    print(f"  secondary.note  {ic['secondary']['note']}")
    print(f"  limitation      {ic['limitation'][:66]}…")

    pool = {t["tid"]: t for t in build_pool()}
    pri, sec = frozen_sets()
    rem = pf["remaining"]

    # ── 구성 검증 ────────────────────────────────────────────────────
    print("\n24 재사용 + 70 신규 구조")
    reuse = [t for t in sec if t in set(pri)]
    ok &= _chk("재사용 24 + 신규 70 = 94", len(reuse) + len(rem) == N_SECONDARY,
               f"{len(reuse)} + {len(rem)}")
    ok &= _chk("두 집합이 겹치지 않는다", not (set(reuse) & set(rem)), "교집합 0")
    ok &= _chk("합집합 = 동결 secondary", set(reuse) | set(rem) == set(sec), "")
    ok &= _chk("동결 순서 보존", [t for t in sec if t in set(reuse) | set(rem)] == sec, "")
    c1, c2 = chunk_ids(1), chunk_ids(2)
    ok &= _chk("chunk 1 + chunk 2 = 70", len(c1) + len(c2) == N_NEW,
               f"{len(c1)} + {len(c2)}")
    ok &= _chk("chunk 가 겹치지 않는다", not (set(c1) & set(c2)), "교집합 0")
    ok &= _chk("chunk 이어붙이면 remaining", c1 + c2 == rem, "")
    h = hashlib.sha256(json.dumps(rem, ensure_ascii=False).encode()).hexdigest()
    print(f"  ·  remaining_ids sha256  {h[:16]}…")
    print(f"  ·  chunk 1  {c1[0]}  →  {c1[-1]}")
    print(f"  ·  chunk 2  {c2[0]}  →  {c2[-1]}")

    # ── 과제 전제 (94 전량) ──────────────────────────────────────────
    print("\n과제 전제 검증 (secondary 94 전량)")
    a = b = c = d = 0
    for t in sec:
        e = pool[t]
        s = to_spec(e)
        gold = set(e["names"])
        if gold <= {s.real_names[l] for l in s.candidates}:
            a += 1
        if len(gold) == 2:
            b += 1
        if len(set(s.real_names.values())) == len(s.real_names):
            c += 1
        if len(s.candidates) == e["n_candidates"]:
            d += 1
    n = len(sec)
    for label, got in (("gold 2구조가 후보에 포함", a), ("gold pair 유일", b),
                       ("라벨↔실구조 전단사", c), ("후보 수 = 동결 n_candidates", d)):
        ok &= _chk(label, got == n, f"{got}/{n}")
    modes = Counter(pool[t]["identification"] for t in sec)
    ok &= _chk("전량 autonomous", set(modes) == {"autonomous"}, f"{dict(modes)}")
    nt = sum(1 for t in sec if pool[t]["identification_nontrivial"])
    ok &= _chk("전량 identification_nontrivial", nt == n, f"{nt}/{n}")

    # ── species 복구 가능성 (§7 의 전제) ─────────────────────────────
    print("\n화학종 복구 가능성 (기존 species-mapping 재사용)")
    grp: dict[tuple, list[str]] = defaultdict(list)
    for t in sec:
        grp[(pool[t]["subset"], pool[t]["species"])].append(t)
    ok &= _chk("secondary 94 → 화학종 24종", len(grp) == N_PRIMARY, f"{len(grp)}종")
    ok &= _chk("그룹마다 primary 정확히 1개",
               all(sum(1 for t in v if t in set(pri)) == 1 for v in grp.values()), "")
    sizes = sorted(Counter(len(v) for v in grp.values()).items())
    print(f"  ·  화학종당 관측 수 분포  " +
          " · ".join(f"{k}관측 {v}종" for k, v in sizes))
    print(f"  🔒 한 화학종이 최대 {max(len(v) for v in grp.values())}관측을 낸다 — "
          f"94 를 독립 표본으로 다루지 않는다")

    # ── 기술통계 축 (p-value 없음) ───────────────────────────────────
    print("\n보고 예정 축 (전부 기술통계 · 검정 없음)")
    print(f"  후보 구조 수  " + " · ".join(
        f"{k}개 {v}과제" for k, v in sorted(Counter(
            pool[t]["n_candidates"] for t in sec).items())))
    print(f"  계열          " + " · ".join(
        f"{k} {v}" for k, v in sorted(Counter(
            pool[t]["subset"] for t in sec).items())))
    print(f"  밴드          " + " · ".join(
        f"{k} {v}" for k, v in sorted(Counter(
            pool[t]["band"] for t in sec).items())))
    print("  🔒 밴드는 참고로만 센다 — 동결본 limitation 이 이 세트로 밴드 의존적")
    print("     주장을 하지 말라고 규정했다.")

    # ── 실행 규모 · 실패 기준 ────────────────────────────────────────
    print("\n실행 계획")
    if pf["primary"] is not None:
        p = pf["primary"]
        per_call = p["ledger_summary"]["n_calls"] / N_PRIMARY
        per_sec = p["elapsed_s"] / N_PRIMARY
        print(f"  primary 실측  {p['ledger_summary']['n_calls']}호출 / {N_PRIMARY}과제 "
              f"· {p['elapsed_s']:.1f}초 / {N_PRIMARY}과제")
        print(f"  신규 70 예상  약 {N_NEW * per_call:.0f}호출 · "
              f"약 {N_NEW * per_sec / 60:.0f}분")
        print(f"  chunk 당      약 {35 * per_call:.0f}호출 · "
              f"약 {35 * per_sec / 60:.0f}분")
    print(f"  실행 유효성   FAILED > {ABORT_PCT}% · **분모는 신규 실행 "
          f"{NEW_EXEC_DENOM}** → **{FAILED_ABORT_N}건 이상이면 무효**")
    print(f"                (3/70 = {3/70:.2%} 이내 · 4/70 = {4/70:.2%} 초과)")
    print(f"                재사용 {N_PRIMARY} 는 이미 성공이 알려진 관측이라 분모에서 "
          f"뺀다")
    print(f"                결합 {COMBINED_DENOM} 기준 비율은 기술 통계로만 보고한다")
    print(f"                누적 {FAILED_ABORT_N}건에 닿으면 즉시 중단하고 chunk 2 도 "
          f"잇지 않는다")

    print("\n🔒 provenance guard (DECISION_LOG 2026-08-16 (5))")
    import inspect
    opts = cli_options()
    ok &= _chk("CLI 에 모델 옵션이 없다",
               not any("model" in o for o in opts),
               f"옵션 {sorted(o for o in opts if o.startswith('--'))} · 고정 {MODEL}")
    ok &= _chk("실행 함수가 CLI 모델을 받지 않는다",
               "model" not in inspect.signature(execute).parameters
               and "model" not in inspect.signature(finalize).parameters,
               "execute(chunk) · finalize()")
    ok &= _chk("재사용 원본 경로 고정", PRIMARY_SOURCE.startswith("experiments/"),
               PRIMARY_SOURCE.split("/")[1])
    ok &= _chk("재사용 원본 sha256 고정", len(PRIMARY_SHA256) == 64,
               f"{PRIMARY_SHA256[:16]}…")
    ok &= _chk("finalize 가 chunk provenance 재검증", "verify_chunk" in
               inspect.getsource(finalize), "set·번호·조건·모델·해시·순서·행수")
    ok &= _chk("미완료 attempt 탐지 동작",
               all(not undocumented_attempts(n) for n in CHUNKS), "현재 0건")

    print("\n🔒 지위 확인")
    for line in ("post-hoc exploratory / descriptive supplementary analysis 다",
                 "primary 24 의 사전 지정 검정·결론을 바꾸지 않는다",
                 "새로운 p-value·유의성 검정·확증 CI 를 만들지 않는다",
                 "RQ1 전체를 입증한다고 쓰지 않는다",
                 "정확도는 «24 화학종에서 나온 94 관측» 을 병기한다"):
        print(f"     · {line}")

    print(f"\n  {'🟢 selftest 통과' if ok else '🔴 selftest 실패 — 실행하지 않는다'}")
    return ok


def _chk(label: str, good: bool, detail: str) -> bool:
    print(f"  {'🟢' if good else '🔴'} {label:<32} {detail}")
    return bool(good)


# ── 실행 ─────────────────────────────────────────────────────────────
def execute(chunk: int) -> None:
    model = MODEL                      # 🔒 상수다. CLI 로 바꿀 수 없다.
    ids = chunk_ids(chunk)
    print("=" * 78)
    print(f"identification challenge — secondary 신규 · chunk {chunk} "
          f"({CHUNKS[chunk][0] + 1}–{CHUNKS[chunk][1]} / {N_NEW})")
    print("=" * 78)
    print("사후등록 docs/DECISION_LOG.md 2026-08-16 (3) · **post-hoc exploratory**")

    pf = preflight()
    print_preflight(pf)

    # ── 미완료 attempt 정책 (DECISION_LOG 2026-08-16 (5) §4) ─────────
    bad = undocumented_attempts(chunk)
    if bad:
        raise SystemExit(
            f"\n🔴 chunk {chunk} 에 **미완료 attempt** 가 있다 — "
            f"{' · '.join(d.name for d in bad)}\n"
            f"   디렉터리는 있는데 chunk_result.json 이 없다. 중간에 죽은 실행이다.\n"
            f"   **자동 재실행하지 않는다.** 먼저 이 순서를 밟는다:\n"
            f"     1. `--audit {chunk}` 로 원장·실행 범위·실패 원인만 감사한다\n"
            f"        (🔒 성능 내용은 열어보지 않는다)\n"
            f"     2. 그 디렉터리에 {INVALID_FILE} 를 쓴다 — 무효 사유, DECISION_LOG "
            f"참조,\n"
            f"        그리고 «{INVALID_DECL}» 선언을 반드시 포함한다\n"
            f"     3. DECISION_LOG 에 incident/correction 을 남긴다\n"
            f"   그 뒤에야 같은 chunk 를 다시 돌릴 수 있다.")

    if not pf["ok"]:
        raise SystemExit("\n🔴 전제가 어긋났다. 실행하지 않는다.")

    if chunk_dir(chunk) is not None:
        raise SystemExit(
            f"🔴 chunk {chunk} 결과가 이미 있다 ({chunk_dir(chunk).name}). 덮어쓰지 않는다.")
    if chunk == 2 and chunk_dir(1) is None:
        raise SystemExit("🔴 chunk 1 이 아직 없다. 순서대로 실행한다.")

    # 🔒 신규 실행 자체의 모델을 강제한다 — Backend 생성보다 앞이다
    if model != MODEL:
        raise SystemExit(f"🔴 모델이 {model} 이다. 신규 70 은 {MODEL} 로만 돌린다.")
    done = [d for d in incomplete_attempts(chunk)]
    if done:
        print(f"\n  ⚠️ 무효 처리된 미완료 attempt {len(done)}건이 남아 있다 "
              f"({' · '.join(d.name for d in done)}) — {INVALID_FILE} 확인됨.")

    # 사전등록 실패 규칙 — chunk 1 에서 이미 초과가 확정되면 잇지 않는다
    if chunk == 2:
        cf = cumulative_failed()
        if cf >= FAILED_ABORT_N:
            raise SystemExit(
                f"\n🔴 누적 신규 FAILED {cf}건 — 신규 실행 {NEW_EXEC_DENOM} 기준 "
                f"{ABORT_PCT}% 초과가 확정됐다 (기준 {FAILED_ABORT_N}건).\n"
                f"   chunk 2 를 자동으로 잇지 않는다. 중단하고 보고한다.")
        print(f"\n  🟢 누적 FAILED {cf}건 (중단 기준 {FAILED_ABORT_N}건) — 이어서 실행한다")

    pool = {t["tid"]: t for t in build_pool()}
    tau = load_tau()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = EXP / f"chal_sec_c{chunk}_{stamp}_{model}"
    ledger = Ledger(out_dir / "calls.jsonl")
    be = Backend(model=model, ledger=ledger, condition=CONDITION)

    print(f"\n  과제 {len(ids)}개 · 조건 {CONDITION} 단독 · 모델 {model}")
    print(f"  재사용 24 는 실행하지 않는다 — 이 chunk 는 신규분만 돈다")
    print(f"  실행 유효성  FAILED > {ABORT_PCT}% · 분모는 신규 실행 "
          f"{NEW_EXEC_DENOM} → {FAILED_ABORT_N}건 이상이면 무효")
    print(f"               재사용 {N_PRIMARY} 는 분모에서 뺀다 (이미 성공이 알려진 관측)")
    print(f"\n  🔒 이 실행은 성능을 출력하지 않는다. quota · FAILED · 커버리지 · "
          f"동결 해시 · 원장 무결성만 본다.")

    q0 = read_quota()
    g = q0.get("Gemini Models", {})
    print(f"  quota(시작)  5시간 {g.get('Five Hour Limit Remaining')} · "
          f"주간 {g.get('Weekly Limit Remaining')}")

    rows, t0 = [], time.time()
    prior_failed = cumulative_failed()
    for i, t in enumerate(ids):
        e = pool[t]
        print(f"\n[{i + 1}/{len(ids)}] {t}", flush=True)
        res = run_task(be, to_spec(e), tau)
        row = enrich(score_run(e, res, tau), e, PROV_NEW, -1)
        rows.append(row)
        # 🔒 성능 비출력 — 실행 사실과 오류만
        nf = prior_failed + sum(r["failed"] for r in rows)
        print(f"    {'🔴 FAILED' if row['failed'] else '완료'}"
              + (f" · ⚠️ {row['error']}" if row["error"] else "")
              + f"  ·  신규 누적 FAILED {nf}  ·  {(time.time() - t0) / 60:.1f}분")
        (out_dir / "rows_partial.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2, default=str) + "\n")

        # 🔒 임계 도달 → **추가 API 호출 없이 즉시 중단한다.**
        #    정상 chunk_result.json 을 쓰지 않으므로 이 디렉터리는 «미완료 attempt»
        #    로 남고, --finalize 가 유효한 chunk 로 받아들이지 않는다.
        if nf >= FAILED_ABORT_N:
            _abort(out_dir, chunk, ids, rows, i + 1, nf, ledger, q0, t0)

    elapsed = time.time() - t0
    q1 = read_quota()
    quota_ledger.record(model=model, n_calls=len(ledger.calls),
                        tokens=ledger.summary()["usage"], before=q0, after=q1,
                        seconds=elapsed, context=f"challenge_secondary/c{chunk}")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "amendment": "docs/DECISION_LOG.md 2026-08-16 (3)",
        "analysis_status": "post-hoc exploratory / descriptive supplementary",
        "set": "secondary", "chunk": chunk, "chunk_slice": list(CHUNKS[chunk]),
        "condition": CONDITION, "model": model,
        "task_ids": ids, "frozen": frozen_hashes(),
        "elapsed_s": round(elapsed, 1), "rows": rows,
        "ledger_summary": ledger.summary(),
        "quota_before": q0, "quota_after": q1,
        "no_inference_note": ("secondary 에서는 p-value·유의성 검정·확증 CI 를 "
                              "만들지 않는다. 24 화학종에서 나온 94 관측이다."),
    }
    (out_dir / "chunk_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")
    (out_dir / "rows_partial.json").unlink(missing_ok=True)

    integrity(out_dir, ids, rows, ledger, elapsed, q0, q1)
    print(f"\n→ {rel(out_dir)}")
    nf = cumulative_failed()
    if chunk == 1:
        if nf >= FAILED_ABORT_N:
            print(f"\n  🔴 누적 FAILED {nf}건 — chunk 2 를 자동으로 잇지 않는다. 보고한다.")
        else:
            print(f"\n  다음 — quota 회복 후 `--run 2`. 그 전에는 `--status` 만 본다.")
    else:
        print(f"\n  다음 — `--finalize` 로 94행을 구성한 뒤 `--report`.")


def _abort(out_dir: Path, chunk: int, ids: list[str], rows: list[dict],
           done: int, nf: int, ledger, q0: dict, t0: float) -> None:
    """실행 유효성 기준 초과 — 더 부르지 않고 멈춘다. **정상 결과로 위장하지 않는다.**

    `chunk_result.json` 을 쓰지 않으므로 이 디렉터리는 `incomplete_attempts()` 에
    잡히고, `--run` 은 `INVALID.md` 없이는 다시 돌지 않으며 `--finalize` 는 이것을
    유효한 chunk 로 세지 않는다.
    """
    (out_dir / "ABORTED.md").write_text(
        f"# chunk {chunk} 실행 중단 — 실행 유효성 기준 초과\n\n"
        f"**중단 시각(UTC)** {datetime.now(timezone.utc).isoformat()}\n\n"
        f"| | |\n|---|---|\n"
        f"| 신규 누적 FAILED | **{nf}건** |\n"
        f"| 무효 기준 | {FAILED_ABORT_N}건 (신규 실행 {NEW_EXEC_DENOM} 의 "
        f"{ABORT_PCT}% 초과) |\n"
        f"| 이 chunk 에서 실행한 과제 | {done} / {len(ids)} |\n"
        f"| 호출 | {len(ledger.calls)} |\n"
        f"| 경과 | {(time.time() - t0) / 60:.1f}분 |\n\n"
        f"**임계에 닿는 즉시 추가 API 호출 없이 멈췄다.** `chunk_result.json` 을 쓰지 "
        f"않았으므로 이 디렉터리는 미완료 attempt 로 남는다 — `--finalize` 가 유효한 "
        f"chunk 로 받아들이지 않는다.\n\n"
        f"## 다음\n\n"
        f"1. `--audit {chunk}` 로 원장·범위·실패 원인만 감사한다 "
        f"(🔒 성능 내용은 열지 않는다).\n"
        f"2. 원인을 밝히고 `DECISION_LOG` 에 incident 를 남긴다.\n"
        f"3. 다시 돌릴 경우 이 디렉터리에 `{INVALID_FILE}` 를 쓴다 — 무효 사유, "
        f"`DECISION_LOG` 참조, 그리고 «{INVALID_DECL}» 선언을 포함한다.\n\n"
        f"🔒 **{INVALID_DECL}.**\n")
    q1 = read_quota()
    quota_ledger.record(model=MODEL, n_calls=len(ledger.calls),
                        tokens=ledger.summary()["usage"], before=q0, after=q1,
                        seconds=time.time() - t0, context=f"challenge_secondary/c{chunk}-aborted")
    print(f"\n{'=' * 78}")
    print(f"🔴 실행 유효성 기준 초과 — 즉시 중단했다")
    print(f"{'=' * 78}")
    print(f"  신규 누적 FAILED  {nf}건 (무효 기준 {FAILED_ABORT_N}건 · 분모 "
          f"{NEW_EXEC_DENOM})")
    print(f"  실행한 과제       {done} / {len(ids)} · 호출 {len(ledger.calls)}")
    print(f"  🔒 chunk_result.json 을 쓰지 않았다 — 정상 결과로 위장하지 않는다.")
    print(f"  🔒 --finalize 는 이 디렉터리를 유효한 chunk 로 받아들이지 않는다.")
    print(f"\n→ {rel(out_dir)}/ABORTED.md")
    raise SystemExit(f"\n중단했다. `--audit {chunk}` 로 감사한 뒤 보고한다.")


def integrity(out_dir: Path, ids: list[str], rows: list[dict],
              ledger, elapsed: float, q0: dict, q1: dict) -> None:
    """🔒 chunk 사이에 볼 수 있는 다섯 가지만 출력한다."""
    ls = ledger.summary()
    lines = (out_dir / "calls.jsonl").read_text().splitlines()
    bad = sum(1 for l in lines if not _parses(l))
    failed = sum(r["failed"] for r in rows)
    cum = cumulative_failed()
    print(f"\n{'=' * 78}\n실행 무결성 (성능 정보 없음)\n{'=' * 78}")
    print(f"  🟢 동결 해시        " + " · ".join(
        f"{k}={v[:8]}…" for k, v in frozen_hashes().items()))
    print(f"  {'🟢' if len(rows) == len(ids) else '🔴'} 과제 커버리지    "
          f"계획 {len(ids)} · 실행 {len(rows)} · "
          f"중복 {len(rows) - len({r['tid'] for r in rows})}")
    print(f"  {'🟢' if not bad else '🔴'} 원장 무결        {len(lines)}줄 · "
          f"요약 {ls['n_calls']}호출 · 파싱실패 {bad} · 호출실패 {ls['failures']}")
    print(f"  {'🟢' if cum < FAILED_ABORT_N else '🔴'} FAILED           "
          f"이번 {failed}건 · 신규 누적 {cum}건 "
          f"(신규 {NEW_EXEC_DENOM} 기준 {100 * cum / NEW_EXEC_DENOM:.2f}% · "
          f"무효 {ABORT_PCT}% = {FAILED_ABORT_N}건)")
    print(f"     참고(기술통계)   결합 {COMBINED_DENOM} 기준 "
          f"{100 * cum / COMBINED_DENOM:.2f}% — 유효성 판정에는 쓰지 않는다")
    for r in rows:
        if r["failed"]:
            print(f"       {r['tid']:<34} {r['error']}")
    g, g1 = q0.get("Gemini Models", {}), q1.get("Gemini Models", {})
    print(f"  quota  5시간 {g.get('Five Hour Limit Remaining')} → "
          f"{g1.get('Five Hour Limit Remaining')} · 주간 "
          f"{g.get('Weekly Limit Remaining')} → {g1.get('Weekly Limit Remaining')}")
    print(f"  경과 {elapsed / 60:.1f}분 · 토큰 {ls['usage']['total_tokens']:,}")


def _parses(line: str) -> bool:
    try:
        json.loads(line)
        return True
    except Exception:  # noqa: BLE001
        return False


# ── chunk 사이 확인 ──────────────────────────────────────────────────
def status() -> None:
    """🔒 quota · FAILED · 커버리지 · 동결 해시 · 원장 무결성만."""
    print("=" * 78)
    print("secondary 진행 상태 — 🔒 성능 정보는 출력하지 않는다")
    print("=" * 78)
    print("  🟢 동결 해시  " + " · ".join(
        f"{k}={v[:8]}…" for k, v in frozen_hashes().items()))
    done = 0
    for n in sorted(CHUNKS):
        d = chunk_dir(n)
        planned = len(chunk_ids(n))
        if d is None:
            print(f"\n  chunk {n}  🔲 미실행 (계획 {planned}과제)")
            continue
        p = json.loads((d / "chunk_result.json").read_text())
        rows = p["rows"]
        done += len(rows)
        lines = (d / "calls.jsonl").read_text().splitlines()
        bad = sum(1 for l in lines if not _parses(l))
        g0 = p["quota_before"].get("Gemini Models", {})
        g1 = p["quota_after"].get("Gemini Models", {})
        print(f"\n  chunk {n}  🟢 {d.name}")
        print(f"    커버리지  계획 {planned} · 실행 {len(rows)} · "
              f"중복 {len(rows) - len({r['tid'] for r in rows})}")
        print(f"    원장      {len(lines)}줄 · 요약 {p['ledger_summary']['n_calls']}호출 "
              f"· 파싱실패 {bad} · 호출실패 {p['ledger_summary']['failures']}")
        print(f"    FAILED    {sum(r['failed'] for r in rows)}건")
        print(f"    동결 해시 {'일치' if p['frozen'] == frozen_hashes() else '🔴 불일치'}")
        print(f"    quota     5시간 {g0.get('Five Hour Limit Remaining')} → "
              f"{g1.get('Five Hour Limit Remaining')} · 주간 "
              f"{g0.get('Weekly Limit Remaining')} → {g1.get('Weekly Limit Remaining')}")
    cum = cumulative_failed()
    print(f"\n  신규 진행   {done}/{N_NEW}   ·   재사용 예정 {N_PRIMARY}   ·   최종 "
          f"{done + N_PRIMARY}/{N_SECONDARY}")
    print(f"  {'🟢' if cum < FAILED_ABORT_N else '🔴'} 신규 누적 FAILED  {cum}건 "
          f"(무효 기준 {FAILED_ABORT_N}건 = 신규 실행 {NEW_EXEC_DENOM} 의 "
          f"{ABORT_PCT}% 초과)")
    print(f"     참고(기술통계)     결합 {COMBINED_DENOM} 기준 "
          f"{100 * cum / COMBINED_DENOM:.2f}%")
    if done < N_NEW:
        print(f"\n  🔒 신규 {N_NEW} 이 전부 끝나기 전에는 identification accuracy 와 "
              f"부분집단 결과를 보지 않는다.")


# ── 미완료 attempt 감사 ──────────────────────────────────────────────
def audit(chunk: int) -> None:
    """🔒 원장·실행 범위·실패 원인만 본다. **성능 내용은 열지 않는다.**

    중간에 죽은 attempt 를 어떻게 처리할지 정하기 위한 것이다. 여기서 식별 정확도나
    채점 결과를 보면 «부분 성능을 보고 고른 재실행» 이 되어버린다.
    """
    atts = incomplete_attempts(chunk)
    print("=" * 78)
    print(f"chunk {chunk} 미완료 attempt 감사 — 🔒 성능 내용은 열지 않는다")
    print("=" * 78)
    if not atts:
        print(f"  🟢 미완료 attempt 가 없다.")
        return
    for d in atts:
        print(f"\n  {d.name}")
        lines = ((d / "calls.jsonl").read_text().splitlines()
                 if (d / "calls.jsonl").exists() else [])
        bad = sum(1 for l in lines if not _parses(l))
        roles: Counter = Counter()
        tasks: list[str] = []
        for l in lines:
            if not _parses(l):
                continue
            c = json.loads(l)
            roles[c.get("agent_role")] += 1
            if c.get("task_id") not in tasks:
                tasks.append(c.get("task_id"))
        print(f"    원장       {len(lines)}줄 · 파싱실패 {bad}")
        print(f"    역할 분포  {dict(roles) if roles else '—'}")
        print(f"    닿은 과제  {len(tasks)}개 / 계획 {len(chunk_ids(chunk))}개")
        for t in tasks:
            print(f"                {t}")
        # 🔒 rows_partial 은 «몇 개가 실패했고 왜인가» 만 본다. 채점값은 읽지 않는다.
        rp = d / "rows_partial.json"
        if rp.exists():
            rows = json.loads(rp.read_text())
            nf = sum(1 for r in rows if r.get("failed"))
            print(f"    부분 행    {len(rows)}개 · FAILED {nf}건")
            for r in rows:
                if r.get("failed"):
                    print(f"                {r['tid']:<34} {r.get('error')}")
        else:
            print(f"    부분 행    없다 (채점 전에 죽었다)")
        print(f"    문서화     {'🟢 ' + INVALID_FILE + ' 확인됨' if attempt_documented(d) else '🔴 없다'}")

    if all(attempt_documented(d) for d in atts):
        print(f"\n  🟢 전부 문서화됐다. 같은 chunk 를 다시 돌릴 수 있다.")
        return
    print(f"\n{'=' * 78}")
    print(f"다시 돌리려면 각 디렉터리에 {INVALID_FILE} 를 쓴다 — 아래를 채운다")
    print("=" * 78)
    print(f"""
# chunk {chunk} attempt 무효 처리

**무효 사유** — (technical interruption / quota / 그 밖에 무엇인지 적는다)

**무효 처리 시점에 본 것** — 원장 줄 수, 닿은 과제 목록, FAILED 건수와 오류 문자열.
식별 정확도·채점 결과 등 성능 내용은 열지 않았다.

🔒 **{INVALID_DECL}.** 기술적 중단으로 chunk 전체를 무효 처리한 것이며,
부분 결과의 성능을 확인한 뒤 그것을 근거로 재실행을 선택한 것이 아니다.

**기록** — docs/DECISION_LOG.md 2026-08-16 (?) 에 incident/correction 으로 남겼다.
""")


# ── 94행 구성 ────────────────────────────────────────────────────────
def verify_chunk(n: int, d: Path, p: dict) -> None:
    """chunk 자체의 provenance 를 다시 강제한다. 하나라도 어긋나면 합치지 않는다.

    chunk 파일이 이 러너가 쓴 것이라는 보장이 없다 — 손으로 고쳤을 수도, 다른
    모델·조건으로 돌렸을 수도, 동결본이 그 사이 바뀌었을 수도 있다. **합치기 직전에
    다시 본다.**
    """
    want = chunk_ids(n)
    for label, got, exp in (
            ("set", p.get("set"), "secondary"),
            ("chunk 번호", p.get("chunk"), n),
            ("condition", p.get("condition"), CONDITION),
            ("model", p.get("model"), MODEL),
            ("동결 해시", p.get("frozen"), frozen_hashes()),
            ("task_ids (순서까지)", p.get("task_ids"), want),
            ("row 수", len(p.get("rows", [])), CHUNK_SIZE),
            ("row tid 순서", [r["tid"] for r in p.get("rows", [])], want)):
        if got != exp:
            s_got, s_exp = str(got), str(exp)
            raise SystemExit(
                f"🔴 chunk {n} ({d.name}) 의 {label} 가 기대와 다르다.\n"
                f"   기대  {s_exp[:160]}\n   실제  {s_got[:160]}\n"
                f"   secondary_result.json 을 쓰지 않는다.")


def finalize() -> None:
    model = MODEL                      # 🔒 상수다. CLI 로 바꿀 수 없다.
    out = EXP / "chal_secondary94" / "secondary_result.json"
    if out.exists():
        raise SystemExit(
            f"🔴 {rel(out)} 이 이미 있다. **조용히 덮어쓰지 않는다.**\n"
            f"   다시 만들어야 한다면 왜 다시 만드는지 DECISION_LOG 에 남기고 기존\n"
            f"   파일을 직접 치운 뒤 실행한다.")

    pf = preflight()
    print("=" * 78)
    print("secondary 94 구성 — 재사용 24 + 신규 70")
    print("=" * 78)
    print_preflight(pf)
    if not pf["ok"]:
        raise SystemExit("\n🔴 전제가 어긋났다. 구성하지 않는다.")

    missing = [n for n in CHUNKS if chunk_dir(n) is None]
    if missing:
        raise SystemExit(f"🔴 chunk {missing} 이 아직 없다. 신규 70 이 전부 끝나야 한다.")

    pool = {t["tid"]: t for t in build_pool()}
    pri, sec = frozen_sets()
    by_tid: dict[str, dict] = {}

    for r in pf["primary"]["rows"]:
        by_tid[r["tid"]] = (r, PROV_REUSE)
    chunk_meta = {}
    for n in sorted(CHUNKS):
        d = chunk_dir(n)
        p = json.loads((d / "chunk_result.json").read_text())
        verify_chunk(n, d, p)
        print(f"  🟢 chunk {n} provenance  set·번호·조건·모델·동결해시·"
              f"task 순서·행 {CHUNK_SIZE} 전부 일치")
        for r in p["rows"]:
            if r["tid"] in by_tid:
                raise SystemExit(
                    f"🔴 {r['tid']} 가 두 번 나왔다 (chunk 간 또는 재사용 24 와 겹친다). "
                    f"구성하지 않는다.")
            by_tid[r["tid"]] = (r, PROV_NEW)
        chunk_meta[f"chunk_{n}"] = {
            "dir": rel(d),
            "task_ids": p["task_ids"], "elapsed_s": p["elapsed_s"],
            "ledger_summary": p["ledger_summary"],
            "quota_before": p["quota_before"], "quota_after": p["quota_after"],
            "calls_jsonl_sha256": file_sha256(d / "calls.jsonl"),
        }

    if set(by_tid) != set(sec):
        raise SystemExit(f"🔴 94 를 채우지 못했다 — {len(by_tid)}개 · "
                         f"빠짐 {len(set(sec) - set(by_tid))}")

    # 🔒 동결 secondary 순서로 다시 정렬한다
    rows = [enrich(by_tid[t][0], pool[t], by_tid[t][1], i)
            for i, t in enumerate(sec)]

    n_reuse = sum(1 for r in rows if r["provenance"] == PROV_REUSE)
    n_new = len(rows) - n_reuse
    if (n_reuse, n_new) != (N_PRIMARY, N_NEW):
        raise SystemExit(f"🔴 provenance 구성이 어긋났다 — 재사용 {n_reuse} · 신규 {n_new}")

    # 🔒 실행 유효성 게이트 — 분모는 신규 실행 70 이다 (DECISION_LOG 2026-08-16 (7))
    failed_new = sum(r["failed"] for r in rows if r["provenance"] == PROV_NEW)
    failed_all = sum(r["failed"] for r in rows)
    if failed_new >= FAILED_ABORT_N:
        raise SystemExit(
            f"🔴 신규 실행 FAILED {failed_new}건 — 신규 {NEW_EXEC_DENOM} 기준 "
            f"{100 * failed_new / NEW_EXEC_DENOM:.2f}% 로 {ABORT_PCT}% 를 넘었다 "
            f"(무효 기준 {FAILED_ABORT_N}건).\n"
            f"   실행이 무효이므로 secondary_result.json 을 쓰지 않는다.")
    print(f"  🟢 실행 유효성       신규 FAILED {failed_new} / {NEW_EXEC_DENOM} "
          f"({100 * failed_new / NEW_EXEC_DENOM:.2f}%) · 무효 기준 "
          f"{FAILED_ABORT_N}건")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "amendment": ["docs/DECISION_LOG.md 2026-08-16 (3)",
                      "docs/DECISION_LOG.md 2026-08-16 (5)"],
        "analysis_status": "post-hoc exploratory / descriptive supplementary",
        "inference_unit_note": ("화학종 24종에서 나온 94개 관측이다. 독립 표본이 "
                                "아니며 유의성 검정에 쓰지 않는다."),
        "no_inference_note": ("secondary 에서는 새로운 p-value·유의성 검정·확증 CI 를 "
                              "만들지 않고 primary 24 의 사전 지정 검정과 결론을 "
                              "바꾸지 않는다. RQ1 전체를 입증한다고 쓰지 않는다."),
        "set": "secondary", "condition": CONDITION, "model": model,
        "frozen": frozen_hashes(),
        "secondary_task_ids": sec,
        "reused_primary_ids": [t for t in sec if t in set(pri)],
        "new_executed_ids": remaining_ids(),
        "primary_source": {
            "pinned_path": PRIMARY_SOURCE,
            "pinned_sha256": PRIMARY_SHA256,
            "path": rel(pf["primary_path"]),
            "file_sha256": file_sha256(pf["primary_path"]),
            "model": pf["primary"]["model"],
            "condition": pf["primary"]["condition"],
            "elapsed_s": pf["primary"]["elapsed_s"],
            "ledger_summary": pf["primary"]["ledger_summary"],
            "quota_before": pf["primary"]["quota_before"],
            "quota_after": pf["primary"]["quota_after"],
        },
        "chunks": chunk_meta,
        "provenance_counts": {PROV_REUSE: n_reuse, PROV_NEW: n_new},
        # 🔒 실행 유효성은 **신규 실행 70** 으로만 잰다. 결합 94 비율은 기술 통계다.
        "validity_gate": {
            "denominator": NEW_EXEC_DENOM,
            "threshold_failed": FAILED_ABORT_N,
            "rule": f"신규 FAILED >= {FAILED_ABORT_N} 이면 실행 무효 "
                    f"({ABORT_PCT}% 초과)",
            "why": ("결합 94 중 24 는 이미 성공이 알려진 primary 재사용이므로 분모에 "
                    "넣으면 신규 실행의 기술적 실패율이 희석된다."),
            "ref": "DECISION_LOG 2026-08-16 (7)",
        },
        "failed_new_exec": failed_new,
        "failed_combined": failed_all,
        "failed_combined_note": (f"결합 {COMBINED_DENOM} 기준 비율은 기술 통계로만 "
                                 f"보고하고 유효성 판정에 쓰지 않는다."),
        "rows": rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")

    print(f"\n{'=' * 78}\n구성 결과 (성능 정보 없음)\n{'=' * 78}")
    print(f"  🟢 행 {len(rows)}개 = 재사용 {n_reuse} + 신규 {n_new}")
    print(f"  🟢 동결 secondary 순서로 정렬 · tid 중복 0")
    print(f"  🟢 모델 {model} 로 고정 (CLI override 없음)")
    print(f"  🟢 primary 원본  {payload['primary_source']['path']}")
    print(f"     sha256 {payload['primary_source']['file_sha256'][:16]}… "
          f"= 고정값 일치")
    print(f"  🟢 실행 유효성   신규 FAILED {failed_new}/{NEW_EXEC_DENOM} "
          f"({100 * failed_new / NEW_EXEC_DENOM:.2f}%) · 무효 기준 "
          f"{FAILED_ABORT_N}건")
    print(f"     참고(기술통계) 결합 FAILED {failed_all}/{COMBINED_DENOM} "
          f"({100 * failed_all / COMBINED_DENOM:.2f}%) — 유효성 판정에 쓰지 않는다")
    print(f"\n→ {rel(out)}")
    print(f"\n  다음 — `--report` (기술통계 · 검정 없음)")


# ── 보고 — 기술통계만 ────────────────────────────────────────────────
def report() -> None:
    """🔒 p-value 를 붙이지 않는다. 어떤 부분집단에도 검정을 하지 않는다."""
    f = EXP / "chal_secondary94" / "secondary_result.json"
    if not f.exists():
        raise SystemExit("🔴 secondary_result.json 이 없다. `--finalize` 를 먼저.")
    p = json.loads(f.read_text())
    rows = p["rows"]
    if len(rows) != N_SECONDARY:
        raise SystemExit(f"🔴 {len(rows)}행뿐이다. 94 가 모이기 전에는 보지 않는다.")

    ok_rows = [r for r in rows if not r["failed"]]
    failed = len(rows) - len(ok_rows)
    n_sp = len({r["species_key"] for r in rows})

    print("=" * 78)
    print(f"identification challenge — secondary (n={len(rows)}) · condition V")
    print("=" * 78)
    print("사후등록 docs/DECISION_LOG.md 2026-08-16 (3)·(5)·(7)")
    print("🔒 **post-hoc exploratory / descriptive supplementary analysis** — "
          "검정하지 않는다.")
    print(f"🔒 **화학종 {n_sp}종에서 나온 {len(rows)}개 관측**이다. 독립 표본이 아니다.")
    print(f"\n  provenance   재사용 {p['provenance_counts'][PROV_REUSE]} · "
          f"신규 {p['provenance_counts'][PROV_NEW]}")
    f_new = sum(r["failed"] for r in rows if r["provenance"] == PROV_NEW)
    print(f"  실행 유효성   신규 FAILED {f_new}/{NEW_EXEC_DENOM} "
          f"({100 * f_new / NEW_EXEC_DENOM:.2f}%) · 무효 기준 {FAILED_ABORT_N}건 "
          f"{'🟢' if f_new < FAILED_ABORT_N else '🔴 초과'}")
    print(f"  참고(기술통계) 결합 FAILED {failed}/{len(rows)} "
          f"({100 * failed / len(rows):.2f}%) — 유효성 판정에 쓰지 않는다")

    k = sum(1 for r in ok_rows if r["identification_correct"])
    m = len(ok_rows)
    print(f"\n① 전체 식별 정확도")
    print(f"   **{k}/{m}** ({k / m:.1%}) — **화학종 {n_sp}종에서 나온 {len(rows)}개 "
          f"관측**")
    print(f"   🔒 이 {len(rows)} 를 독립 표본 {len(rows)}개처럼 취급하지 않는다.")
    print(f"   🔒 신뢰구간·p-value 를 붙이지 않는다. primary {N_PRIMARY} 의 사전 지정")
    print(f"      검정이 이 세트의 추론을 담당하며, 그 값을 이 {len(rows)} 로 갱신하지")
    print(f"      않는다.")

    # provenance 별 — 재사용 24 와 신규 70 을 나눠 본다 (확인용 기술통계)
    print(f"\n①-b provenance 별 (검정 없음 · 확인용 기술통계)")
    print(f"   {'출처':<28}{'맞음':>5}{'전체':>5}{'비율':>9}")
    print("   " + "-" * 47)
    for prov, label in ((PROV_REUSE, "재사용 (primary 24)"),
                        (PROV_NEW, "신규 실행 (secondary 70)")):
        sub = [r for r in ok_rows if r["provenance"] == prov]
        c = sum(1 for r in sub if r["identification_correct"])
        print(f"   {label:<28}{c:>5}{len(sub):>5}{c / len(sub):>9.1%}")
    print(f"   🔒 두 줄을 비교해 «복제됐다/안 됐다» 로 읽지 않는다. 재사용 24 는 새로")
    print(f"      실행한 관측이 아니라 primary 결과를 그대로 가져온 것이므로 두 줄은")
    print(f"      독립적인 두 실행이 아니다.")

    print(f"\n② 화학종별 correct / total")
    by_sp: dict[str, list[dict]] = defaultdict(list)
    for r in ok_rows:
        by_sp[r["species_key"]].append(r)
    print(f"   {'화학종':<26}{'맞음':>5}{'전체':>5}{'비율':>8}   재사용/신규")
    print("   " + "-" * 62)
    rates = []
    for key in sorted(by_sp):
        v = by_sp[key]
        c = sum(1 for r in v if r["identification_correct"])
        rates.append(c / len(v))
        nr = sum(1 for r in v if r["provenance"] == PROV_REUSE)
        print(f"   {key:<26}{c:>5}{len(v):>5}{c / len(v):>8.0%}   {nr}/{len(v) - nr}")

    print(f"\n③ 화학종 단위 descriptive macro summary ({len(rates)}종)")
    print(f"   평균 {statistics.mean(rates):.1%} · 중앙값 {statistics.median(rates):.1%} "
          f"· 범위 {min(rates):.0%}–{max(rates):.0%}")
    print(f"   전량 정답 {sum(1 for x in rates if x == 1.0)}종 · "
          f"전량 오답 {sum(1 for x in rates if x == 0.0)}종")
    print(f"   🔒 화학종 수가 {len(rates)}종뿐이다. 이 값으로 일반화하지 않는다.")

    for title, key in (("④ 후보 구조 수별 correct / total", "n_candidates"),
                       ("⑤ 계열(서브셋)별 correct / total", "subset")):
        print(f"\n{title}")
        g: dict = defaultdict(list)
        for r in ok_rows:
            g[r[key]].append(r)
        for kk in sorted(g):
            v = g[kk]
            c = sum(1 for r in v if r["identification_correct"])
            sp = len({r["species_key"] for r in v})
            print(f"   {str(kk):<14}{c:>4}/{len(v):<4} ({c / len(v):>5.0%})   "
                  f"화학종 {sp}종")
        print(f"   🔒 p-value 를 붙이지 않는다. 작은 n 에서 일반화하지 않는다.")

    print(f"\n⑥ 식별에 실패한 과제")
    wrong = [r for r in ok_rows if not r["identification_correct"]]
    if not wrong:
        print("   없다.")
    else:
        for r in sorted(wrong, key=lambda r: r["secondary_index"]):
            print(f"   {r['tid']}")
            print(f"      계열 {r['subset']} · 화학종 {r['species_key']} · "
                  f"후보 {r['n_candidates']}개 · {r['provenance']}")
            print(f"      고른 쌍 {r['selected_pair']}  ←→  정답 쌍 {r['gold_pair']}")
    if failed:
        print(f"\n   FAILED (식별을 수행하지 못한 과제)")
        for r in rows:
            if r["failed"]:
                print(f"   {r['tid']:<34} {r['error']}")

    print(f"\n{'=' * 78}")
    print("🔒 이 분석이 하지 않는 것")
    for line in (
            "새로운 p-value·유의성 검정·확증 신뢰구간을 만들지 않았다.",
            f"primary {N_PRIMARY} 의 사전 지정 Poisson-binomial 검정과 Clopper–Pearson "
            f"신뢰구간을 이 {len(rows)} 로 **갱신하지 않는다.** 그 값은 primary "
            f"{N_PRIMARY} 의 것으로 남는다.",
            f"이것을 primary {N_PRIMARY} 의 **replication 이라고 부르지 않는다** — "
            f"{N_PRIMARY} 개는 재실행이 아니라 같은 결과의 재사용이고, 신규 70 은 "
            f"같은 화학종에서 나온 다른 반응이다.",
            "RQ1 전체를 입증한다고 쓰지 않는다.",
            f"{len(rows)} 를 독립 표본처럼 취급하지 않는다 — 화학종 {n_sp}종에서 나온 관측이다.",
            "동결본 limitation 대로 밴드별·계열별 일반화 주장을 하지 않는다.",
            "결과를 보고 새로운 부분집단·문턱·검정법을 만들지 않았다.",
            f"main N=92 와 중복되는 과제를 합쳐 표본 수를 늘려 해석하지 않는다."):
        print(f"   · {line}")


def build_parser() -> argparse.ArgumentParser:
    """🔒 모델 옵션을 두지 않는다. 모델은 상수이며 CLI 로 바꿀 수 없다.

    `selftest` 가 이 파서의 option_strings 를 직접 훑어 모델 옵션이 없음을 확인한다.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--run", type=int, choices=tuple(CHUNKS), metavar="CHUNK")
    ap.add_argument("--audit", type=int, choices=tuple(CHUNKS), metavar="CHUNK",
                    help="미완료 attempt 를 원장·범위·실패원인만 감사한다")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--finalize", action="store_true")
    ap.add_argument("--report", action="store_true")
    return ap


def cli_options() -> set[str]:
    return {o for a in build_parser()._actions for o in a.option_strings}


def main() -> None:
    ap = build_parser()
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    elif a.run:
        execute(a.run)
    elif a.audit:
        audit(a.audit)
    elif a.status:
        status()
    elif a.finalize:
        finalize()
    elif a.report:
        report()
    else:
        ap.error("--selftest · --run N · --audit N · --status · --finalize · "
                 "--report 중 하나")


if __name__ == "__main__":
    main()
