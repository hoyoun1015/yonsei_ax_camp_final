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
    """반응 유형 × 수준의 τ 와, 서브셋별 내역."""
    per_type = defaultdict(lambda: defaultdict(list))
    per_subset = {}
    for sub in ALL_SUBSETS:
        rxns = load_reactions(GMTKN, sub)
        rt = reaction_type(sub)
        row = {}
        for level in ("L1", "L2", "L3"):
            errs = []
            for r in rxns:
                es = [_energy(sub, n, level) for n in r.names]
                if all(e is not None for e in es):
                    calc = sum(c * e for c, e in zip(r.coeffs, es)) * HARTREE
                    errs.append(abs(calc - r.ref))
            if errs:
                # 6자리로 둔다. 4자리로 자르면 표시 단계에서 이중 반올림이 생겨
                # 같은 데이터가 1.213 과 1.212 로 달라 보인다(실측 1.212518).
                row[level] = {"mae": round(st.mean(errs), 6),
                              "median": round(st.median(errs), 6),
                              "max": round(max(errs), 6), "n": len(errs)}
                per_type[rt][level].extend(errs)
        per_subset[sub] = {"type": rt, "n_reactions": len(rxns), "levels": row}
    tau = {rt: {lv: round(st.mean(v), 6) for lv, v in d.items()}
           for rt, d in per_type.items()}
    counts = {rt: {lv: len(v) for lv, v in d.items()} for rt, d in per_type.items()}
    return tau, counts, per_subset


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
    tau, counts, per_subset = measure_tau()

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
    print("\n동결하지 않은 것 (Stage B — API 한도 확인 후): "
          "최종 과제 수 · 반복 횟수 · ablation 범위")


if __name__ == "__main__":
    main()
