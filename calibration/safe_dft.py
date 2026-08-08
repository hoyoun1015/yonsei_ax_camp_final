#!/usr/bin/env python3
"""DFT 수준 τ 실측 — 메모리 안전 · 재개 가능 러너.

`dft_tau_probe.py`를 대체한다. 과제 범위는 동일하고 실행 방식만 바꿨다.

2026-08-09에 계산 중 머신이 죽은 원인과 대응:

1. **메모리 초과.** 구 러너는 워커 4개 × `memory 6 GB` = 24 GB를 16 GB 머신에
   요구했다. 여기서는 잡을 **직렬로 하나씩** 돌리고, 선언 메모리를
   `SAFE_MEM_GB`(기본 3)로 묶는다. 원자수가 크면 `SCF_SUBTYPE DISK_DF`로
   out-of-core를 강제해 in-core 폭증을 막는다.
2. **완료 판정 버그.** 구 러너는 `sp.out` 존재만 보고 완료로 처리해서,
   죽다 만 잡이 영구히 건너뛰어졌다. 여기서는 psi4의 성공 마커를 확인하고,
   실패한 잡은 지우고 다시 돌린다. 그래서 **언제 죽어도 이어서** 실행된다.
3. **감시견.** 실행 중 RSS를 폴링해 `KILL_RSS_GB`를 넘으면 그 잡만 죽이고
   더 낮은 메모리 + DISK_DF로 한 번 재시도한다. 머신 전체를 끌고 들어가지 않는다.
4. **스크래치.** 잡별 스크래치를 따로 주고 끝나면 지운다. 디스크 여유가
   `MIN_DISK_GB` 밑으로 떨어지면 새 잡을 시작하지 않고 멈춘다.

사용:
    python3 safe_dft.py <gmtkn55_root> <작업디렉터리> <서브셋> [basis] [functional]

환경변수:
    SAFE_MEM_GB=3      psi4 선언 메모리 (기본 3)
    KILL_RSS_GB=6      이 RSS를 넘으면 잡을 죽이고 재시도 (기본 6)
    MIN_DISK_GB=15     이 밑으로 남으면 새 잡 시작 안 함 (기본 15)
    PSI4_THREADS=8     잡 하나가 쓰는 스레드 (직렬이므로 넉넉히)
    DISK_DF_ATOMS=40   이 원자수 이상이면 처음부터 DISK_DF
    JOB_TIMEOUT=21600  잡당 상한 초 (기본 6시간)
"""
import os
import re
import shutil
import statistics as st
import subprocess
import sys
import time
from pathlib import Path

HARTREE = 627.5094740631
TMER = re.compile(r"^\s*\$tmer\s+(.*?)\s+x\s+(.*?)\s+\$w\s+(-?[\d.]+)\s*$")
SUCCESS = "Psi4 exiting successfully"

PSI4 = os.environ.get("PSI4_BIN", str(Path.home() / "micromamba/envs/psi4env/bin/psi4"))
NPROC = int(os.environ.get("PSI4_THREADS", "8"))
MEM_GB = float(os.environ.get("SAFE_MEM_GB", "3"))
KILL_RSS_GB = float(os.environ.get("KILL_RSS_GB", "6"))
MIN_DISK_GB = float(os.environ.get("MIN_DISK_GB", "15"))
DISK_DF_ATOMS = int(os.environ.get("DISK_DF_ATOMS", "40"))
JOB_TIMEOUT = int(os.environ.get("JOB_TIMEOUT", "21600"))


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


def succeeded(out_path):
    """psi4가 정상 종료했는가. 파일 존재만으로 판단하지 않는다."""
    if not out_path.exists():
        return False
    return SUCCESS in out_path.read_text(errors="ignore")


def energy_of(out_path):
    m = re.findall(r"Total Energy\s*=\s*(-?\d+\.\d+)", out_path.read_text(errors="ignore"))
    return float(m[-1]) if m else None


def free_disk_gb(path):
    return shutil.disk_usage(path).free / 2**30


def rss_gb(pid):
    """프로세스 트리 전체의 RSS 합. psi4가 자식을 띄우는 경우까지 본다."""
    try:
        out = subprocess.run(["ps", "-Ao", "pid=,ppid=,rss="],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return 0.0
    kids, rss = {}, {}
    for line in out.splitlines():
        f = line.split()
        if len(f) == 3:
            p, pp, r = int(f[0]), int(f[1]), int(f[2])
            kids.setdefault(pp, []).append(p)
            rss[p] = r
    total, stack = 0, [pid]
    while stack:
        p = stack.pop()
        total += rss.get(p, 0)
        stack.extend(kids.get(p, []))
    return total / 2**20  # ps는 KB


def write_input(work_dir, src_dir, basis, func, mem_gb, disk_df):
    lines = (src_dir / "struc.xyz").read_text().splitlines()
    n = int(lines[0].split()[0])
    chg = int((src_dir / ".CHRG").read_text().split()[0]) if (src_dir / ".CHRG").exists() else 0
    uhf = int((src_dir / ".UHF").read_text().split()[0]) if (src_dir / ".UHF").exists() else 0
    inp = [f"memory {mem_gb:g} GB", "molecule mol {", f"{chg} {uhf + 1}"]
    inp += [" ".join(l.split()[:4]) for l in lines[2:2 + n] if l.split()]
    # disk_df는 DF 적분을 디스크에 두는 out-of-core JK다 (psi4 1.11에서
    # scf_subtype이 아니라 scf_type의 값이다 — 실측으로 확인).
    # 느려지지만 in-core 메모리 폭증을 막는다.
    scf_type = "disk_df" if disk_df else "df"
    inp += ["units angstrom", "no_reorient", "no_com", "}",
            f"set basis {basis}", f"set scf_type {scf_type}",
            "set freeze_core true", "set e_convergence 8"]
    inp.append(f"energy('{func}')")
    (work_dir / "sp.in").write_text("\n".join(inp) + "\n")
    return n


def run_once(work_dir, scratch, mem_gb, disk_df, label):
    """psi4 한 번 실행. RSS 감시견을 달고 돌린다. 성공 여부를 반환."""
    env = dict(os.environ, PSI_SCRATCH=str(scratch))
    scratch.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([PSI4, "-i", "sp.in", "-o", "sp.out", "-n", str(NPROC)],
                            cwd=work_dir, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0, peak, killed = time.time(), 0.0, None
    while proc.poll() is None:
        time.sleep(5)
        r = rss_gb(proc.pid)
        peak = max(peak, r)
        if r > KILL_RSS_GB:
            killed = f"RSS {r:.1f} GB > 상한 {KILL_RSS_GB:g} GB"
            proc.kill()
            break
        if time.time() - t0 > JOB_TIMEOUT:
            killed = f"시간초과 {JOB_TIMEOUT}초"
            proc.kill()
            break
    proc.wait()
    dt = time.time() - t0
    shutil.rmtree(scratch, ignore_errors=True)
    ok = succeeded(work_dir / "sp.out")
    (work_dir / "run.log").write_text(
        f"{label}\nmem={mem_gb:g}GB disk_df={disk_df} threads={NPROC}\n"
        f"peak_rss={peak:.2f}GB elapsed={dt:.1f}s ok={ok} killed={killed}\n")
    return ok, peak, dt, killed


def compute(src_dir, work_dir, scratch_root, basis, func):
    """한 구조의 에너지. 이미 성공한 잡은 건드리지 않는다."""
    out = work_dir / "sp.out"
    if succeeded(out):
        return energy_of(out), "캐시"

    work_dir.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()  # 죽다 만 결과는 신뢰하지 않는다

    scratch = scratch_root / work_dir.name
    n = write_input(work_dir, src_dir, basis, func, MEM_GB, disk_df=False)
    disk_df = n >= DISK_DF_ATOMS
    if disk_df:
        write_input(work_dir, src_dir, basis, func, MEM_GB, disk_df=True)

    ok, peak, dt, killed = run_once(work_dir, scratch, MEM_GB, disk_df, f"{work_dir.name} n={n}")
    if ok:
        return energy_of(out), f"{dt:.0f}s peak {peak:.1f}GB"

    # 재시도: 메모리를 절반으로, DISK_DF 강제
    retry_mem = max(1.0, MEM_GB / 2)
    print(f"      재시도 ({killed or '실패'}) → mem {retry_mem:g}GB + DISK_DF", flush=True)
    if out.exists():
        out.unlink()
    write_input(work_dir, src_dir, basis, func, retry_mem, disk_df=True)
    ok, peak, dt, killed = run_once(work_dir, scratch, retry_mem, True, f"{work_dir.name} n={n} retry")
    if ok:
        return energy_of(out), f"재시도 성공 {dt:.0f}s peak {peak:.1f}GB"
    return None, f"실패 ({killed or 'psi4 오류'})"


def main():
    # psi4는 잡 디렉터리를 cwd로 실행되므로 상대경로를 넘기면
    # PSI_SCRATCH가 어긋나 즉시 실패한다. 전부 절대경로로 고정한다.
    root, work, sub = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3]
    basis = sys.argv[4] if len(sys.argv) > 4 else "def2-TZVP"
    func = sys.argv[5] if len(sys.argv) > 5 else "b3lyp-d3bj"

    rxns = reactions(root / sub / ".res")
    needed = sorted({n for names, _, _ in rxns for n in names})
    tag = f"{func}_{basis}".replace("/", "_")
    scratch_root = work / "_scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)

    done = sum(1 for x in needed if succeeded(work / sub / tag / x / "sp.out"))
    print(f"{sub}: {len(rxns)} 반응 / {len(needed)} 구조 · {func}/{basis}", flush=True)
    print(f"  직렬 실행 · 잡당 {MEM_GB:g} GB · {NPROC} 스레드 · "
          f"RSS 상한 {KILL_RSS_GB:g} GB · 디스크 여유 {free_disk_gb(work):.0f} GB", flush=True)
    print(f"  이미 완료 {done}/{len(needed)} — 나머지만 돌린다\n", flush=True)

    energies, failed = {}, []
    for i, name in enumerate(needed, 1):
        if free_disk_gb(work) < MIN_DISK_GB:
            print(f"\n디스크 여유 {free_disk_gb(work):.0f} GB < {MIN_DISK_GB:g} GB — 중단. "
                  f"공간 확보 후 같은 명령으로 재개하면 이어서 돈다.", flush=True)
            break
        e, note = compute(root / sub / name, work / sub / tag / name,
                          scratch_root, basis, func)
        energies[name] = e
        print(f"  [{i}/{len(needed)}] {name:<24} {'OK ' if e else 'FAIL'} {note}", flush=True)
        if e is None:
            failed.append(name)

    shutil.rmtree(scratch_root, ignore_errors=True)

    errs, missing = [], 0
    for names, coeffs, ref in rxns:
        es = [energies.get(n) for n in names]
        if any(e is None for e in es):
            missing += 1
            continue
        errs.append(abs(sum(c * e for c, e in zip(coeffs, es)) * HARTREE - ref))

    print(f"\n{sub} · {func}/{basis}")
    print(f"  반응 {len(errs)}개 사용 (누락 {missing})")
    if failed:
        print(f"  실패 구조 {len(failed)}: {', '.join(failed)}")
    if errs:
        print(f"  MAE  = {st.mean(errs):.3f} kcal/mol")
        print(f"  중앙 = {st.median(errs):.3f}")
        print(f"  최대 = {max(errs):.2f}")
    if missing:
        print("  ⚠ 누락이 있으므로 이 MAE는 확정값이 아니다. 같은 명령으로 재개할 것.")


if __name__ == "__main__":
    main()
