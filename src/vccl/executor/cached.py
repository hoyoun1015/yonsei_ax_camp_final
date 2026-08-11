"""실행층 — 결정론적. 판단하지 않는다.

기획안 §5.1: *"실행층은 무엇을 비교할지, 어떤 결과가 가설을 지지하는지, 최종 결론이
무엇인지를 결정하지 않는다. 제출된 계산 명세만 실행한다."*

평가 트랙의 224반응 331구조는 **이미 전량 계산돼 캐시에 있다**(2026-08-09~10).
따라서 이 모듈은 캐시를 조회해 즉시 반환한다 — 파일럿에서 계산을 다시 돌리지 않는다.
캐시에 없으면 조용히 넘어가지 않고 실패한다.

**M_used 는 여기서 기록된다.** 에이전트 자기보고를 쓰지 않는다(기획안 §5.1·구현설계 §2).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CAL = ROOT / "calibration"
HARTREE = 627.5094740631

# 수준 → (캐시 디렉터리, 하위 태그, 파일명, 파서)
LEVELS = {
    "L1": ("tau_work", "sp", "sp.log", "xtb"),
    "L3": ("dft_work", "b3lyp-d3bj_def2-TZVP", "sp.out", "psi4"),
}
LEVEL_COST_S = {"L1": 0.02, "L3": 40.0}      # 표시용 근사. 실제 비용은 D1 실측 참조


class ExecutionError(RuntimeError):
    pass


@dataclass
class CalcRequest:
    """에이전트가 제출하는 계산 명세. 판단은 담기지 않는다."""
    subset: str
    structures: tuple[str, ...]
    level: str

    def __post_init__(self):
        if self.level not in LEVELS:
            raise ExecutionError(
                f"알 수 없는 계산 수준 '{self.level}'. 가능한 값 {sorted(LEVELS)}")


@dataclass
class CalcResult:
    request: CalcRequest
    energies: dict[str, float]          # 구조 → Hartree
    level: str
    cost_s: float
    qc_ok: bool = True
    notes: list[str] = field(default_factory=list)

    def delta(self, minus: str, plus: str) -> float:
        """ΔE = E_plus − E_minus (kcal/mol). 부호 규약은 라벨 모듈과 같다."""
        return (self.energies[plus] - self.energies[minus]) * HARTREE


def _xtb(p: Path):
    if not p.exists():
        return None
    t = p.read_text(errors="ignore")
    if "normal termination of xtb" not in t:
        return None
    m = re.findall(r"TOTAL ENERGY\s+(-?\d+\.\d+)", t)
    return float(m[-1]) if m else None


def _psi4(p: Path):
    if not p.exists():
        return None
    t = p.read_text(errors="ignore")
    if "Psi4 exiting successfully" not in t:
        return None
    m = re.findall(r"Total Energy\s*=\s*(-?\d+\.\d+)", t)
    return float(m[-1]) if m else None


def run(req: CalcRequest) -> CalcResult:
    """명세를 실행한다 — 지금은 캐시 조회. 도구의 성공 신호를 확인한다."""
    d, tag, fname, parser = LEVELS[req.level]
    fn = _xtb if parser == "xtb" else _psi4
    energies, missing = {}, []
    for s in req.structures:
        e = fn(CAL / d / req.subset / tag / s / fname)
        if e is None:
            missing.append(s)
        else:
            energies[s] = e
    if missing:
        raise ExecutionError(
            f"캐시에 없거나 성공 마커가 없다: {req.subset}/{req.level} {missing}. "
            "조용히 건너뛰지 않는다 — calibration/safe_dft.py 로 해당 구조를 채울 것.")
    return CalcResult(request=req, energies=energies, level=req.level,
                      cost_s=LEVEL_COST_S[req.level] * len(req.structures))
