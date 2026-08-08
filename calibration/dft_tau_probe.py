#!/usr/bin/env python3
"""DFT 수준의 τ 실측 — 제공 지오메트리 위의 단일점.

G2 게이트("계산 수준을 올리면 τ가 줄어드는가")를 검정한다.
GMTKN55는 제공 지오메트리 위의 단일점으로 평가하도록 만들어져 있으므로
지오메트리를 건드리지 않는다.

사용: python3 dft_tau_probe.py <gmtkn55_root> <작업디렉터리> <서브셋> [basis] [functional]
"""
import os
import re
import subprocess
import sys
import statistics as st
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

HARTREE = 627.5094740631
TMER = re.compile(r"^\s*\$tmer\s+(.*?)\s+x\s+(.*?)\s+\$w\s+(-?[\d.]+)\s*$")
PSI4 = os.environ.get("PSI4_BIN", str(Path.home() / "micromamba/envs/psi4env/bin/psi4"))
NPROC = int(os.environ.get("PSI4_THREADS", "2"))
NWORKERS = int(os.environ.get("PROBE_WORKERS", "4"))


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
        if len(names) == len(coeffs):
            out.append((names, coeffs, float(m.group(3))))
    return out


def dft_energy(src_dir, work_dir, basis, func):
    work_dir.mkdir(parents=True, exist_ok=True)
    out = work_dir / "sp.out"
    if not out.exists():
        lines = (src_dir / "struc.xyz").read_text().splitlines()
        n = int(lines[0].split()[0])
        chg = int((src_dir / ".CHRG").read_text().split()[0]) if (src_dir / ".CHRG").exists() else 0
        uhf = int((src_dir / ".UHF").read_text().split()[0]) if (src_dir / ".UHF").exists() else 0
        inp = ["memory 6 GB", "molecule mol {", f"{chg} {uhf + 1}"]
        inp += [" ".join(l.split()[:4]) for l in lines[2:2 + n] if l.split()]
        inp += ["units angstrom", "no_reorient", "no_com", "}",
                f"set basis {basis}", "set scf_type df", "set freeze_core true",
                f"energy('{func}')"]
        (work_dir / "sp.in").write_text("\n".join(inp) + "\n")
        subprocess.run([PSI4, "-i", "sp.in", "-o", "sp.out", "-n", str(NPROC)],
                       cwd=work_dir, capture_output=True, timeout=14400)
    if not out.exists():
        return None
    m = re.findall(r"Total Energy\s*=\s*(-?\d+\.\d+)", out.read_text(errors="ignore"))
    return float(m[-1]) if m else None


def main():
    root, work, sub = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    basis = sys.argv[4] if len(sys.argv) > 4 else "def2-TZVP"
    func = sys.argv[5] if len(sys.argv) > 5 else "b3lyp-d3bj"

    rxns = reactions(root / sub / ".res")
    needed = sorted({n for names, _, _ in rxns for n in names})
    print(f"{sub}: {len(rxns)} 반응 / {len(needed)} 구조 · {func}/{basis} · "
          f"워커 {NWORKERS} × {NPROC} 스레드", flush=True)

    tag = f"{func}_{basis}".replace("/", "_")
    energies = {}

    def job(name):
        return name, dft_energy(root / sub / name, work / sub / tag / name, basis, func)

    with ThreadPoolExecutor(max_workers=NWORKERS) as ex:
        for i, (name, e) in enumerate(ex.map(job, needed), 1):
            energies[name] = e
            print(f"  [{i}/{len(needed)}] {name} {'OK' if e else 'FAIL'}", flush=True)

    errs, missing = [], 0
    for names, coeffs, ref in rxns:
        es = [energies.get(n) for n in names]
        if any(e is None for e in es):
            missing += 1
            continue
        errs.append(abs(sum(c * e for c, e in zip(coeffs, es)) * HARTREE - ref))

    print(f"\n{sub} · {func}/{basis}")
    print(f"  반응 {len(errs)}개 사용 (누락 {missing})")
    if errs:
        print(f"  MAE  = {st.mean(errs):.3f} kcal/mol")
        print(f"  중앙 = {st.median(errs):.3f}")
        print(f"  최대 = {max(errs):.2f}")


if __name__ == "__main__":
    main()
