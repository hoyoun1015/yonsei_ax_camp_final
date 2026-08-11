"""Stage A 동결 — 과학적 규칙을 고정한다. API 와 무관한 것만.

**동결하는 것 (여기)**
  τ 실측치 · 라벨 유도 규칙 · 밴드 정의 · 서술자 정의 · 화학종 정의 ·
  자율 식별 판정 규칙

**동결하지 않는 것 (Stage B — API 한도·예산 확인 후)**
  최종 과제 수 · 반복 횟수 · ablation 범위

`CLAUDE.md` 불변조건 7 — "τ와 라벨은 동결 후 불변. 동결 시점을 문서에 남기고,
결과를 본 뒤에는 어떤 이유로도 수정하지 않는다."

τ 는 문헌에서 가져오지 않고 `calibration/` 의 캐시된 계산에서 다시 계산한다.
따라서 이 스크립트를 돌리면 언제든 같은 값이 나온다(재현성).

사용: python3 src/vccl/tasks/freeze.py
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics as st
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from vccl.tasks.gmtkn import (  # noqa: E402
    ANGLE_BINS, BOND_TOL, CONFORMER_SUBSETS, HARTREE, HBOND_ANGLE_MIN,
    HBOND_MAX, ISOMER_SUBSETS, load_reactions, reaction_type, species_map,
)

GMTKN = ROOT / "data" / "reference" / "gmtkn55"
CAL = ROOT / "calibration"
TAG_L1 = ("tau_work", "sp", "sp.log")                 # xTB
TAG_L3 = ("dft_work", "b3lyp-d3bj_def2-TZVP", "sp.out")
TAG_L2 = ("dft_work", "b3lyp-d3bj_def2-SVP", "sp.out")   # 폐기됨. 기록만
OUT = ROOT / "data" / "tasks" / "frozen_rules_v1.json"
TAU_FLOOR = 0.2
LEAK: dict = {}
ALL_SUBSETS = CONFORMER_SUBSETS + ISOMER_SUBSETS


def _xtb_energy(p: Path):
    if not p.exists():
        return None
    t = p.read_text(errors="ignore")
    if "normal termination of xtb" not in t:
        return None
    m = re.findall(r"TOTAL ENERGY\s+(-?\d+\.\d+)", t)
    return float(m[-1]) if m else None


def _psi4_energy(p: Path):
    if not p.exists():
        return None
    t = p.read_text(errors="ignore")
    if "Psi4 exiting successfully" not in t:
        return None
    m = re.findall(r"Total Energy\s*=\s*(-?\d+\.\d+)", t)
    return float(m[-1]) if m else None


def _energy(subset: str, name: str, level: str):
    if level == "L1":
        d, mid, fn = TAG_L1
        return _xtb_energy(CAL / d / subset / mid / name / fn)
    d, mid, fn = TAG_L3 if level == "L3" else TAG_L2
    return _psi4_energy(CAL / d / subset / mid / name / fn)


def measure_tau():
    """반응 유형 × 수준의 τ. 반응별 오차를 그대로 들고 나온다(LOO 계산에 필요).

    **누락을 조용히 건너뛰지 않는다.** 에너지가 하나라도 없으면 그 반응은 τ 에서
    빠지는데, 그러면 동결본이 "일부만 쓴 τ"가 되면서도 그 사실이 드러나지 않는다.
    기대 개수와 대조해 어긋나면 즉시 실패한다.
    """
    per_type = defaultdict(lambda: defaultdict(dict))   # 유형 → 수준 → {rid: 오차}
    per_subset = {}
    missing = defaultdict(list)
    for sub in ALL_SUBSETS:
        rxns = load_reactions(GMTKN, sub)
        rt = reaction_type(sub)
        row = {}
        for level in ("L1", "L2", "L3"):
            errs = {}
            for r in rxns:
                es = [_energy(sub, n, level) for n in r.names]
                if any(e is None for e in es):
                    missing[(sub, level)].append(r.rid)
                    continue
                calc = sum(c * e for c, e in zip(r.coeffs, es)) * HARTREE
                errs[r.rid] = abs(calc - r.ref)
            if errs:
                vals = list(errs.values())
                row[level] = {"mae": round(st.mean(vals), 6),
                              "median": round(st.median(vals), 6),
                              "max": round(max(vals), 6), "n": len(vals)}
                per_type[rt][level].update(errs)
        per_subset[sub] = {"type": rt, "n_reactions": len(rxns), "levels": row}

    if missing:
        lines = [f"  {sub}/{lv}: {len(ids)}개 — {', '.join(ids[:3])}..."
                 for (sub, lv), ids in sorted(missing.items())]
        raise SystemExit(
            "동결 중단 — 계산이 누락된 반응이 있다. 조용히 건너뛰면 동결본이 "
            "«일부만 쓴 τ»가 되면서도 그 사실이 드러나지 않는다.\n"
            + "\n".join(lines)
            + "\n\n해당 서브셋을 calibration/safe_dft.py 로 마저 돌린 뒤 다시 동결할 것.")

    tau = {rt: {lv: round(st.mean(list(d.values())), 6) for lv, d in lvls.items()}
           for rt, lvls in per_type.items()}
    counts = {rt: {lv: len(d) for lv, d in lvls.items()}
              for rt, lvls in per_type.items()}
    return tau, counts, per_subset, per_type


def loo_tau(per_type, rtype, level, rid):
    """leave-one-out τ — 그 반응 자신을 빼고 계산한 τ.

    τ 를 224반응 전량에서 계산하고 그 안에서 평가 과제를 뽑으면, 과제 i 의 라벨
    임계값이 과제 i 자신의 오차에 일부 의존한다(calibration/test leakage).
    LOO 는 그 순환을 정확히 제거한다.
    """
    d = per_type[rtype][level]
    others = [v for k, v in d.items() if k != rid]
    return st.mean(others)


def leakage_impact(per_type, floor=TAU_FLOOR):
    """LOO 로 바꾸면 밴드 배정이 몇 개나 달라지는가."""
    def band(a, lo, hi):
        if a <= lo:
            return "D"
        if a <= hi:
            return "C"
        return "B" if a <= 3 * hi else "A"

    changed, total, max_shift = [], 0, 0.0
    for sub in ALL_SUBSETS:
        rt = reaction_type(sub)
        for r in load_reactions(GMTKN, sub):
            total += 1
            g_lo = max(st.mean(list(per_type[rt]["L3"].values())), floor)
            g_hi = max(st.mean(list(per_type[rt]["L1"].values())), floor)
            l_lo = max(loo_tau(per_type, rt, "L3", r.rid), floor)
            l_hi = max(loo_tau(per_type, rt, "L1", r.rid), floor)
            max_shift = max(max_shift, abs(g_hi - l_hi), abs(g_lo - l_lo))
            b1, b2 = band(abs(r.ref), g_lo, g_hi), band(abs(r.ref), l_lo, l_hi)
            if b1 != b2:
                changed.append((r.rid, b1, b2))
    return changed, total, max_shift


def species_counts():
    out = {}
    for sub in ALL_SUBSETS:
        sm = species_map(load_reactions(GMTKN, sub))
        out[sub] = len(set(sm.values()))
    return out


def git_rev(path: Path) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def main():
    tau, counts, per_subset, per_type = measure_tau()

    changed, total, max_shift = leakage_impact(per_type)
    global LEAK
    LEAK = {"changed": [{"rid": r, "global": a, "loo": b} for r, a, b in changed],
            "total": total, "max_shift": max_shift,
            "finding": (f"동일 풀 사용에 따른 self-influence 를 leave-one-out 으로 "
                        f"검사했으며 {total}/{total} 에서 band assignment 변화가 "
                        f"없었다." if not changed else
                        f"leave-one-out 검사에서 {len(changed)}/{total} 의 "
                        f"band assignment 가 달라졌다."),
            "note": "τ 값 자체는 LOO 에서 이동한다(최대 이동은 max_tau_shift 참조). "
                    "밴드 경계를 넘지 않았을 뿐이다. 이 검사는 self-influence 가 "
                    "밴드 배정에 미친 영향을 잰 것이며, 그 이상을 주장하지 않는다.",
            "action": ("전역 τ 를 그대로 쓴다." if not changed else
                       "LOO τ 채택 여부를 결정할 것.")}

    payload = {
        "version": "v1",
        "stage": "A",
        "frozen_at": "2026-08-11",
        "scope": {
            "frozen_here": [
                "τ 실측치 (반응 유형 × 수준)", "τ 물리적 바닥",
                "라벨 유도 규칙", "밴드 정의", "에스컬레이션 정답 규칙",
                "화학종 정의", "기하 서술자 정의", "자율 식별 판정 규칙",
            ],
            "deferred_to_stage_B": [
                "최종 과제 수", "조건별 반복 횟수", "ablation 범위",
            ],
            "why_deferred": "API 일일 요청 한도와 예산에 의존한다. "
                            "먼저 동결하면 한도 확인 후 재동결해야 하고, "
                            "그것은 동결의 의미를 없앤다.",
        },
        "ladder": {
            "levels": {
                "L1": {"method": "GFN2-xTB", "type": "single point",
                       "cost_s": 0.02},
                "L3": {"method": "B3LYP-D3(BJ)/def2-TZVP", "type": "single point",
                       "cost_s_range": [25, 3193]},
            },
            "retired": {
                "L2": {"method": "B3LYP-D3(BJ)/def2-SVP",
                       "reason": "단조성이 8개 서브셋 중 4개에서만 성립. "
                                 "ISOL24 는 L2 가 L3 보다 정확(3.345 대 5.562). "
                                 "구조 이성질체 유형에서 τ_L2 < τ_L3 이라 밴드 C 가 "
                                 "음수 폭이 된다.",
                       "evidence": "docs/D1_실측결과.md §8-3"},
            },
            "geometry": "GMTKN55 제공 지오메트리 고정. 최적화하지 않는다.",
        },
        "tau": {
            "values": {rt: v for rt, v in tau.items()},
            "n_reactions": counts,
            "floor": TAU_FLOOR,
            "floor_reason": "GMTKN55 참조값 자체의 추정 오차 ±0.2 kcal/mol "
                            "(ISOL24 .res 주석, DLPNO-CCSD(T)/CBS). "
                            "어떤 수준의 τ 도 이보다 작아질 수 없다.",
            "scope_rule": "τ 는 반응 유형별이다. 서브셋별로 두지 않는다 — "
                          "에이전트가 런타임에 조회해야 하는데 오염 방어가 "
                          "서브셋 정체를 숨기도록 요구하기 때문(기획안 §3.2). "
                          "반응 유형은 결합 그래프 비교로 판정 가능하다.",
            "per_subset_detail": per_subset,
        },
        "reaction_type_rule": {
            "conformer": "두 구조의 결합 그래프가 동일",
            "isomer": "분자식은 같고 결합 그래프가 다름",
            "subsets": {"conformer": CONFORMER_SUBSETS, "isomer": ISOMER_SUBSETS},
        },
        "label_rule": {
            "formula": "정답(과제, M) = ABSTAIN if |ΔE_ref| ≤ τ(유형, M) "
                       "else sign(ΔE_ref)",
            "note": "하나의 과제에 하나의 정답이 있는 것이 아니라, 실제로 사용한 "
                    "수준 M 에 대해 정답이 정의된다. 방향이 우연히 맞아도 "
                    "증거가 τ 안이면 과대해석으로 기록한다.",
            "sign_convention": "ΔE = Σ c_i·E_i. 2성분 (A,B) 에 계수 (−1,+1) 이면 "
                               "ΔE = E_B − E_A 이므로 ΔE > 0 이면 A 가 더 안정하다.",
            "implementation": "src/vccl/scoring/labels.py",
            "tests": "tests/test_labels.py",
        },
        "band_rule": {
            "A": "|ΔE_ref| > 3·τ_L1",
            "B": "τ_L1 < |ΔE_ref| ≤ 3·τ_L1",
            "C": "τ_L3 < |ΔE_ref| ≤ τ_L1   ← 에스컬레이션이 값을 하는 유일한 구간",
            "D": "|ΔE_ref| ≤ τ_L3",
            "escalation_answer": {"A": "SUFFICIENT", "B": "SUFFICIENT",
                                  "C": "ESCALATION", "D": "FUTILE"},
        },
        "species_rule": {
            "definition": "반응 그래프의 연결성분. 한 반응에 함께 등장하는 구조를 "
                          "같은 화학종으로 묶고 이행적으로 닫는다.",
            "why": "이름 규칙으로 뽑으면 CDIE20 의 R21→P20 처럼 번호를 넘나드는 "
                   "반응에서 한 반응이 두 화학종으로 쪼개져 pseudo-replication "
                   "방지 취지가 깨진다.",
            "counts": species_counts(),
        },
        "descriptor_rule": {
            "torsion_bins_deg": {k: list(v) for k, v in ANGLE_BINS.items()},
            "bins_source": "IUPAC 관례 (syn / gauche=synclinal / skew=anticlinal / "
                           "anti=antiperiplanar). 임의로 정한 값이 아니다.",
            "backbone": "중원자(비수소) 사슬의 가장 긴 경로. 탄소만 보면 ICONF 의 "
                        "H2S2O7·H4P2O7 처럼 탄소 없는 분자를 다룰 수 없다.",
            "bond_tolerance": BOND_TOL,
            "hbond": {"max_H_acceptor_A": HBOND_MAX,
                      "min_DHA_angle_deg": HBOND_ANGLE_MIN,
                      "why": "SCONF(당)·PCONF21(펩타이드)은 수소결합이 배좌 안정성을 "
                             "지배하므로 회전각만으로 구조가 구분되지 않는다."},
        },
        "identification_rule": {
            "levels": {"L1": "조성 — 회전각 유형의 개수만",
                       "L2": "패턴 — 순서는 주되 부호는 버림",
                       "L3": "부호 — 부호까지"},
            "rule": "반응의 두 구성원이 각자의 화학종 안에서 유일해지는 가장 거친 "
                    "단계를 쓴다. L1·L2 로 유일해지면 자율 식별형(autonomous), "
                    "L3 가 필요하거나 어느 단계로도 유일하지 않으면 쌍 지정형(paired).",
            "why_not_L3": "부호까지 명시하면 사실상 구조 ID 를 풀어쓴 것이며 "
                          "자율 식별이라 부를 수 없다.",
            "ambiguous_tasks": "L3·불가로 분류된 반응은 대표 사례 트랙에서 "
                               "«모호성 인식 → 재조작화» 시연 재료로 쓴다. "
                               "평가 트랙에서는 배제한다.",
            "pilot": "calibration/hypothesis_pilot.py — conformer 계열 67% 가능",
        },
        "leakage_check": {
            "issue": "τ 를 224반응 전량에서 계산하고 같은 풀에서 평가 과제를 뽑으므로, "
                     "과제 i 의 라벨 임계값이 과제 i 자신의 오차에 일부 의존한다 "
                     "(self-influence).",
            "method": "leave-one-out τ — 각 반응의 밴드를 그 반응을 뺀 τ 로 다시 매겨 "
                      "배정이 달라지는 개수를 센다.",
            "band_changes": LEAK["changed"],
            "n_changed": len(LEAK["changed"]),
            "n_total": LEAK["total"],
            "max_tau_shift": round(LEAK["max_shift"], 6),
            "finding": LEAK["finding"],
            "note": LEAK["note"],
            "action": LEAK["action"],
        },
        "provenance": {
            "gmtkn55": {"repo": "grimme-lab/GMTKN55", "branch": "v2",
                        "commit": "b904e46"},
            "tools": {"xtb": "6.7.1", "psi4": "1.11",
                      "dispersion": "dftd3-python / simple-dftd3"},
            "machine": "Apple M4, 10 core, 16 GB RAM, arm64, GPU 없음",
            "measured_on": "2026-08-09 ~ 2026-08-10",
            "repo_commit": git_rev(ROOT),
        },
    }

    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    digest = hashlib.sha256(body.encode()).hexdigest()
    payload["sha256"] = digest

    # 동결본 덮어쓰기 방지 — 불변조건 7. 이미 동결된 파일을 말없이 갈아치우면
    # "동결"이라는 말이 의미를 잃는다. 내용이 같으면 통과, 다르면 중단한다.
    if OUT.exists():
        prev = json.loads(OUT.read_text())
        if prev.get("sha256") == digest:
            print(f"이미 동결돼 있고 내용이 동일하다 (SHA-256 {digest[:16]}…). "
                  "재현성 확인 완료.")
            return
        if "--force" not in sys.argv:
            raise SystemExit(
                f"동결 중단 — {OUT.name} 이 이미 존재하고 내용이 다르다.\n"
                f"  기존 {prev.get('sha256', '?')[:16]}…\n"
                f"  신규 {digest[:16]}…\n\n"
                "동결본을 바꾸는 것은 CLAUDE.md 불변조건 7 위반일 수 있다 — "
                "«τ와 라벨은 동결 후 불변. 결과를 본 뒤에는 어떤 이유로도 수정하지 "
                "않는다».\n정당한 재동결이라면 DECISION_LOG 에 근거를 남기고 "
                "--force 로 다시 실행할 것.")
        print("⚠️  --force — 기존 동결본을 덮어쓴다. DECISION_LOG 에 근거를 남길 것.\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    print("Stage A 동결 완료\n")
    print(f"{'유형':<12} {'τ_L1':>8} {'τ_L3':>8} {'(폐기) τ_L2':>12} {'반응':>5}")
    print("-" * 50)
    for rt in ("conformer", "isomer"):
        v = tau[rt]
        print(f"{rt:<12} {v['L1']:>8.4f} {v['L3']:>8.4f} {v.get('L2', 0):>12.4f} "
              f"{counts[rt]['L3']:>5}")
    print(f"\n화학종: {sum(species_counts().values())}종")
    print(f"바닥: τ := max(실측, {TAU_FLOOR})")
    print(f"\n→ {OUT.relative_to(ROOT)}")
    print(f"   SHA-256 {digest}")
    print(f"\n누출 검사 (leave-one-out): 밴드가 달라지는 반응 "
          f"{len(LEAK['changed'])}/{LEAK['total']}개 · "
          f"τ 최대 변동 {LEAK['max_shift']:.4f} kcal/mol")
    print("\n동결하지 않은 것 (Stage B — API 한도 확인 후): "
          "최종 과제 수 · 반복 횟수 · ablation 범위")


if __name__ == "__main__":
    main()
