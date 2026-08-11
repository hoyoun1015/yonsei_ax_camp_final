"""과제 후보 풀·층화·가설 문장 단위테스트.

`python3 tests/test_pairs.py`

**이 파일이 지키는 것 넷.**

1. 층화가 N=92 후보(A30/B22/C25/D15)를 **화학종 중복 없이** 채운다
2. 생성된 모든 과제가 `Task` validation 을 통과한다
3. `prompts.py` 가 **L3 정밀도를 자율 식별형으로 허용하지 않는다**
4. 선택이 **결정론적**이고, 목표를 못 채우면 **조용히 축소하지 않고 실패**한다

풀 생성이 0.1초라 매 테스트에서 전체를 새로 만든다 — 캐시 파일에 의존하지 않는다.
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vccl.scoring.labels import (  # noqa: E402
    Band, Conclusion, IdentificationMode, Task, band_of, oracle_action,
)
from vccl.tasks import prompts  # noqa: E402
from vccl.tasks.gmtkn import Descriptor  # noqa: E402
from vccl.tasks.pairs import (  # noqa: E402
    StratifyShortfall, build_pool, load_tau, stratify,
)

TARGET_92 = {"A": 30, "B": 22, "C": 25, "D": 15}
POOL = build_pool()
TAU = load_tau()


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


# ── 1. 층화 ──────────────────────────────────────────────────────────
def test_stratify_fills_n92_exactly():
    sel = stratify(POOL, TARGET_92)
    got = Counter(t["band"] for t in sel)
    check(len(sel) == 92, f"총 92개여야 한다. 받은 값 {len(sel)}")
    for band, want in TARGET_92.items():
        check(got[band] == want, f"밴드 {band}: {want} 개여야 한다. 받은 값 {got[band]}")


def test_stratify_has_no_duplicate_species():
    """추론 단위가 화학종이므로 한 화학종에서 과제를 여러 개 뽑으면 n 이 부풀려진다."""
    sel = stratify(POOL, TARGET_92)
    keys = [(t["subset"], t["species"]) for t in sel]
    dup = [k for k, c in Counter(keys).items() if c > 1]
    check(not dup, f"화학종이 중복됐다: {dup}")


def test_stratify_species_uniqueness_spans_bands():
    """같은 화학종이 «다른 밴드»에서 다시 뽑히는 것도 막아야 한다."""
    sel = stratify(POOL, TARGET_92)
    by_species = {}
    for t in sel:
        k = (t["subset"], t["species"])
        check(k not in by_species,
              f"화학종 {k} 가 밴드 {by_species.get(k)} 와 {t['band']} 에서 중복됐다")
        by_species[k] = t["band"]


def test_stratify_is_deterministic():
    """난수를 쓰지 않으므로 같은 입력이면 항상 같은 결과여야 한다."""
    a = [t["tid"] for t in stratify(POOL, TARGET_92)]
    b = [t["tid"] for t in stratify(POOL, TARGET_92)]
    check(a == b, "같은 입력에 다른 선택이 나왔다")
    # 풀 순서를 섞어도 결과가 같아야 한다 — 정렬 키가 완전히 정해져 있으므로
    shuffled = list(reversed(POOL))
    c = [t["tid"] for t in stratify(shuffled, TARGET_92)]
    check(a == c, "풀 순서에 따라 선택이 달라졌다 — 정렬 키가 불완전하다")


def test_stratify_fails_loudly_on_shortfall():
    """목표를 못 채우면 조용히 적게 반환하지 않고 실패해야 한다."""
    impossible = {"A": 30, "B": 22, "C": 25, "D": 999}
    try:
        stratify(POOL, impossible)
    except StratifyShortfall as e:
        check("D" in str(e), f"어느 밴드가 부족한지 메시지에 있어야 한다: {e}")
        return
    raise AssertionError("부족한데도 예외를 던지지 않았다")


def test_stratify_can_opt_out_of_strict():
    """strict=False 면 축소를 허용한다 — 탐색용. 기본값은 strict 다."""
    sel = stratify(POOL, {"D": 999}, strict=False)
    check(0 < len(sel) < 999, f"가능한 만큼만 반환해야 한다. 받은 값 {len(sel)}")


def test_stratify_prefers_autonomous():
    sel = stratify(POOL, TARGET_92)
    auto = sum(1 for t in sel if t["identification"] == "autonomous")
    pool_rate = sum(1 for t in POOL if t["identification"] == "autonomous") / len(POOL)
    check(auto / len(sel) >= pool_rate,
          f"자율 식별형을 우선해야 한다. 선택 {auto/len(sel):.0%} 대 풀 {pool_rate:.0%}")


# ── 2. Task validation ──────────────────────────────────────────────
def test_every_pool_entry_passes_task_validation():
    """풀의 모든 항목이 Task 로 구성 가능해야 한다 — 계수·claimed·ref 검증 포함."""
    for t in POOL:
        Task(tid=t["tid"], subset=t["subset"], rtype=t["rtype"],
             names=tuple(t["names"]), coeffs=tuple(t["coeffs"]), ref=t["ref"],
             claimed_more_stable=t["claimed_more_stable"],
             identification=IdentificationMode(t["identification"]),
             precision_level=t["precision_level"])


def test_pool_band_and_oracle_are_consistent():
    """저장된 밴드·오라클이 동결된 τ 로 다시 계산한 값과 일치해야 한다."""
    for t in POOL:
        task = Task(tid=t["tid"], subset=t["subset"], rtype=t["rtype"],
                    names=tuple(t["names"]), coeffs=tuple(t["coeffs"]), ref=t["ref"],
                    claimed_more_stable=t["claimed_more_stable"],
                    identification=IdentificationMode(t["identification"]),
                    precision_level=t["precision_level"])
        check(band_of(task, TAU) is Band(t["band"]),
              f"{t['tid']}: 밴드 불일치 {t['band']}")
        for lv in ("L1", "L3"):
            check(oracle_action(task, lv, TAU) is Conclusion(t["oracle"][lv]),
                  f"{t['tid']}: 오라클({lv}) 불일치")


def test_pool_mixes_supported_and_refuted():
    """가설 방향을 섞어야 «항상 지지» 를 학습할 여지를 없앤다."""
    got = Counter(t["oracle"]["L3"] for t in POOL)
    check(got["SUPPORTED"] > 0 and got["REFUTED"] > 0,
          f"SUPPORTED/REFUTED 가 섞여야 한다: {dict(got)}")


def test_claimed_is_one_of_the_pair():
    for t in POOL:
        check(t["claimed_more_stable"] in t["names"],
              f"{t['tid']}: claimed 가 구성 구조에 없다")


# ── 3. 가설 문장 ─────────────────────────────────────────────────────
def _desc(torsions, hbonds=0):
    return Descriptor(n_heavy=6, torsions=list(torsions), hbonds=hbonds)


def test_prompts_rejects_l3_precision():
    """L3(부호까지)는 구조 ID 를 풀어쓴 것이므로 자율 식별형으로 쓸 수 없다."""
    a, b = _desc(["anti", "anti"]), _desc(["gauche+", "gauche-"])
    for level in ("L3", "l3", "L4", ""):
        try:
            prompts.describe_phrase(a, level)
        except ValueError:
            continue
        raise AssertionError(f"정밀도 '{level}' 을 허용했다")
    # L1·L2 는 허용
    for level in ("L1", "L2"):
        check(prompts.describe_phrase(a, level), f"{level} 은 허용해야 한다")
    check(prompts.neutral(a, b, "L1"), "중립 서술 생성 실패")


def test_prompts_l2_is_sign_invariant():
    """L2 는 부호를 버린 «패턴»이다. 부호만 다른 두 구조가 같은 서술을 받아야 한다.

    초안 테스트는 문자열에서 '+'·'-' 를 찾았는데, L2 서술의 하이픈은 패턴 구분자여서
    그 방식으로는 아무것도 검증되지 않았다. 불변식으로 직접 검사한다.
    """
    a = _desc(["gauche+", "anti", "gauche-"])
    b = _desc(["gauche-", "anti", "gauche+"])   # 부호만 뒤집었다
    check(prompts.describe_phrase(a, "L2") == prompts.describe_phrase(b, "L2"),
          "부호만 다른 구조가 다른 L2 서술을 받았다 — 부호가 새고 있다")
    # 그리고 L1(조성)도 부호에 무관해야 한다
    check(prompts.describe_phrase(a, "L1") == prompts.describe_phrase(b, "L1"),
          "L1 조성이 부호에 의존한다")
    # 반대로 «패턴이 다르면» 서술도 달라야 한다 (변별력 확인)
    c = _desc(["anti", "gauche+", "gauche-"])
    check(prompts.describe_phrase(a, "L2") != prompts.describe_phrase(c, "L2"),
          "순서가 다른데 같은 L2 서술이 나왔다 — 변별력이 없다")


def test_prompts_neutral_has_no_mechanism():
    """중립 서술은 방향 주장만 — 기전을 언급하지 않는다."""
    a, b = _desc(["gauche+"]), _desc(["anti"])
    s = prompts.neutral(a, b, "L1")
    for word in ("입체", "분산", "수소결합은", "엔트로피"):
        check(word not in s, f"중립 서술에 기전이 들어갔다 ({word}): {s}")


def test_prompts_misleading_keeps_same_direction():
    """오도 서술은 «기전»만 바꾼다. 주장 방향이 바뀌면 정답 라벨이 달라져 버린다."""
    a, b = _desc(["gauche+", "gauche-"]), _desc(["anti", "anti"])
    both = prompts.both(a, b, "L1")
    pa = prompts.describe_phrase(a, "L1")
    pb = prompts.describe_phrase(b, "L1")
    for key in ("neutral", "misleading"):
        s = both[key]
        check(s.index(pa) < s.index(pb),
              f"{key}: 주장된 구조가 먼저 와야 한다 (방향 동일) — {s}")
    check(both["misleading"] != both["neutral"], "두 서술이 같다")
    check(len(both["misleading"]) > len(both["neutral"]), "오도 서술에 기전이 붙어야 한다")


def test_selected_tasks_have_hypotheses():
    """자율 식별형으로 선택된 과제는 두 서술을 모두 가져야 한다."""
    for t in stratify(POOL, TARGET_92):
        if t["identification"] != "autonomous":
            continue
        h = t["hypothesis"]
        check(h["neutral"] and h["misleading"],
              f"{t['tid']}: 가설 문장이 비었다")
        check(t["precision_level"] in ("L1", "L2"),
              f"{t['tid']}: 정밀도가 {t['precision_level']} 이다")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(tests)}개 통과")
