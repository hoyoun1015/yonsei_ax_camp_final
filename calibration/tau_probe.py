#!/usr/bin/env python3
"""τ 예비 실측 — GMTKN55 참조값 대비 GFN2-xTB 오차를 수준별로 잰다.

수준 정의 (2026-08-09 개정):
  L1 = 제공된 참조 지오메트리에 GFN2-xTB 단일점
  L2 = 제공된 지오메트리를 GFN2-xTB로 국소 최적화 (conformer 정체성 보존)

conformer 전역 탐색은 쓰지 않는다 — 참조 conformer 쌍을 같은 구조로 붕괴시킨다
(실측 확인: ACONF H_ggg → CREST 전역최저 = H_ttt, ΔE가 0이 된다).

사용: python3 tau_probe.py <gmtkn55_root> <작업디렉터리> [서브셋 ...]
"""
import os
import re
import subprocess
import sys
import statistics as st
from pathlib import Path

HARTREE = 627.5094740631
TMER = re.compile(r"^\s*\$tmer\s+(.*?)\s+x\s+(.*?)\s+\$w\s+(-?[\d.]+)\s*$")
XTB = os.environ.get("XTB_BIN", str(Path.home() / "micromamba/envs/vccl/bin/xtb"))


def expand(token):
    token = token.replace("/$f", "")
    m = re.search(r"\{([^}]*)\}", token)
    if not m:
        return [token]
    pre, post = token[:m.start()], token[m.end():]
    return [pre + p + post for p in m.group(1).split(",")]


def reactions(res_path):
    out = []
    for line in res_path.read_text(errors="ignore").splitlines():
        m = TMER.match(line)
        if not m:
            continue
        names = []
        for tok in m.group(1).split():
            names.extend(expand(tok))
        coeffs = [int(c) for c in m.group(2).split()]
        if len(names) != len(coeffs):
            continue
        out.append((names, coeffs, float(m.group(3))))
    return out


def energy(src_dir, work_dir, mode):
    """mode: 'sp' | 'opt'.  성공 시 Hartree, 실패 시 None."""
    work_dir.mkdir(parents=True, exist_ok=True)
    xyz = work_dir / "in.xyz"
    if not xyz.exists():
        xyz.write_bytes((src_dir / "struc.xyz").read_bytes())
        for meta in (".CHRG", ".UHF"):
            if (src_dir / meta).exists():
                (work_dir / meta).write_bytes((src_dir / meta).read_bytes())
    log = work_dir / f"{mode}.log"
    if not log.exists():
        cmd = [XTB, "in.xyz", "--gfn", "2"] + (["--opt"] if mode == "opt" else [])
        env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
        try:
            r = subprocess.run(cmd, cwd=work_dir, env=env, capture_output=True,
                               text=True, timeout=1800)
        except subprocess.TimeoutExpired:
            return None
        log.write_text(r.stdout + r.stderr)
    txt = log.read_text(errors="ignore")
    if "normal termination of xtb" not in txt:
        return None
    if mode == "opt" and "FAILED TO CONVERGE" in txt.upper():
        return None
    m = re.findall(r"TOTAL ENERGY\s+(-?\d+\.\d+)", txt)
    return float(m[-1]) if m else None


def main():
    root, work = Path(sys.argv[1]), Path(sys.argv[2])
    subs = sys.argv[3:] or ["ACONF", "ICONF", "SCONF", "PCONF21", "CDIE20",
                            "Amino20x4", "ISO34", "ISOL24"]
    grand = {"sp": [], "opt": []}
    print(f"{'서브셋':<12} {'반응':>4} {'L1 MAE':>8} {'L2 MAE':>8} {'L1 max':>8} {'L2 max':>8}")
    print("-" * 54)
    for sub in subs:
        rxns = reactions(root / sub / ".res")
        errs = {"sp": [], "opt": []}
        for names, coeffs, ref in rxns:
            for mode in ("sp", "opt"):
                es = [energy(root / sub / n, work / sub / mode / n, mode) for n in names]
                if any(e is None for e in es):
                    continue
                calc = sum(c * e for c, e in zip(coeffs, es)) * HARTREE
                errs[mode].append(abs(calc - ref))
        for m in ("sp", "opt"):
            grand[m].extend(errs[m])
        f = lambda v: f"{st.mean(v):.3f}" if v else "  —  "
        g = lambda v: f"{max(v):.2f}" if v else "  —  "
        print(f"{sub:<12} {len(rxns):>4} {f(errs['sp']):>8} {f(errs['opt']):>8} "
              f"{g(errs['sp']):>8} {g(errs['opt']):>8}")
    print("-" * 54)
    print(f"{'전역 τ':<12} {len(grand['opt']):>4} "
          f"{st.mean(grand['sp']):>8.3f} {st.mean(grand['opt']):>8.3f} "
          f"{max(grand['sp']):>8.2f} {max(grand['opt']):>8.2f}")
    print("\n(단위 kcal/mol · L1 = 참조 지오메트리 단일점 · L2 = 국소 최적화)")


if __name__ == "__main__":
    main()
