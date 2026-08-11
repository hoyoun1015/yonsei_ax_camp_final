# RESUME_HERE — 세션이 죽으면 이 파일부터 읽는다

최종 갱신: **2026-08-12** · 마감 **9/2** (3주 남음)

## 지금 상태 한 줄

**시스템 구현·동결·사전 검증 전부 끝났다. 남은 것은 본실행(V · V−τ) 하나다.**
멘토링(8/12)에서 **"무엇을 헤드라인으로 쓸지"** 답을 받아온 뒤 시작하기로 했다.

## 🔴 다음에 할 일 — 이 순서대로

### 1. 멘토링 답변을 `docs/DECISION_LOG.md`에 먼저 기록한다

받아올 답 3개 (`멘토링_대비_내가_알아야_할것.md` §7) —

1. **세 축 중 뭘 주된 주장으로?** 정확도(13문제·14%p) / 비용(14.4%) / 판단(40문제·43%p)
2. **주 지표(§7.1)가 R0와 비교 불가능한 게 논문으로 괜찮은가**
3. **남은 3주를 실제 실험 완성도 vs 사례 몇 개 깊게 중 어디에**

**답이 분석 우선순위를 바꾼다** — 비용 축이면 L3 사용량 프로파일, 판단 축이면
밴드 C 에스컬레이션 로그가 중심이 된다. **그래서 기록을 먼저 하고 실행한다.**

### 2. 본실행 (V · V−τ)

```bash
cd "(진짜_이게_최종)"
# 아직 러너 진입점을 안 만들었다 — smoke.py 를 본실행용으로 확장해야 한다
# (main N=92 제외 로직을 끄고, condition 을 V / V-tau 로 받게)
python3 src/vccl/agents/smoke.py --n 3     # 파이프라인 재확인용 (7/7 통과 이력)
```

⚠️ **한 번에 다 못 돌린다.** 5시간 quota 용량이 **566호출**이고 V+V−τ 가 약 920호출
이므로 **두 개 이상의 quota window 로 나눈다.** `/usage` 를 먼저 확인하고
`src/vccl/agents/quota_ledger.py` 에 누적한다.

⚠️ **로그는 절대 지우지 않는다.** 대표 사례(representative case study) trajectory 를
여기서 뽑는다. `experiments/*/calls.jsonl` 전부 보존.

⚠️ **FAILED 가 한 condition 에서 5% 를 넘으면 그 실행을 무효로 보고 원인을 고친 뒤
재실행한다.** 부분 결과를 확증 결과로 쓰지 않는다 (사전등록 항목).

### 3. 본실행 뒤 분석

- **밴드 C 25개에서 실제로 L3 로 올렸나** (여기서만 R0 를 이길 수 있다)
- **Loop Utilization — 분기 B(재조작화)를 썼나.** smoke 에서 0회였다.
  0이면 "자유도를 줬으나 사용하지 않았다"가 그대로 결과다.
- 대표 사례 3~5개 · cross-model 복제(secondary, Sonnet, 30~40과제, V만)

### 4. 아직 안 한 것 (본실행과 무관하게 남아 있음)

- 🙋 **API RPD 확인 — 사용자만 가능**
- 🔲 **선행연구 조사.** "최초 사례" 주장은 `docs/기획안_v3.md` §3.2 에
  **미확인으로 표시돼 있다.** 글쓰기 전에 확인할 것.
- 🔲 **Flash 주간 용량 미측정.** 이건 **실행 스케줄 문제로만 취급한다** —
  과학적 설계를 바꾸는 근거로 쓰지 않는다 (사용자 확정).
- 🔲 pytest 가 이 머신 `python3` 에 없다. 테스트는 아래 러너로 돌린다.

## 완료된 것

| | 상태 |
|---|---|
| 8개 서브셋 331구조 224반응 L1·L3 계산 | 🟢 전량 완료, 누락 0 |
| τ (반응유형별) · 밴드 A/B/C/D | 🟢 동결 (`frozen_rules_v1.json`) |
| 문제 92개 · Identification challenge 24/94 | 🟢 동결 (`frozen_stage_b_v1.json`) |
| 3-agent 루프 (PI / 계산담당 / 비판자) | 🟢 구현·smoke 7/7 통과 |
| R0 기준선 | 🟢 실측 (`results/r0_baseline.json`) |
| G5 오염 검사 | 🟢 통과 (`docs/G5_CONTAMINATION.md`) |
| oracle headroom audit | 🟢 완료 (`docs/HEADROOM_AUDIT.md`) |
| 멘토링 자료 | 🟢 `멘토님께.md` (push) + 개인 메모(git 제외) |
| **V · V−τ 본실행** | 🔴 **미실행** |

### 동결 해시 (바뀌면 안 된다)

```
frozen_rules_v1.json    0bfc4cee6a6cf0e087d104610fa83975ca5223ef99381130d301317f84995e8b
frozen_stage_b_v1.json  20c83da8ffc6035363235327bf1ec7722557f00c0546720492d0731b9867abd2
```

### τ 실측값 (참고 — 실제 사용은 반응유형별이다)

| 서브셋 | τ_L1 | τ_L3 | | 서브셋 | τ_L1 | τ_L3 |
|---|---:|---:|---|---|---:|---:|
| ISOL24 | 12.190 | 5.562 | | SCONF | 1.643 | 0.651 |
| ISO34 | 6.902 | 1.949 | | ICONF | 1.629 | 0.328 |
| CDIE20 | 1.802 | 1.079 | | Amino20x4 | 0.954 | 0.235 |
| PCONF21 | 1.757 | 0.537 | | ACONF | 0.193 | 0.065 |

🔒 **밴드는 서브셋이 아니라 «반응유형별» τ 로 정의한다** (§3.2). 서브셋별 τ 로 밴드를
가르는 것은 규칙 위반이다 — 한 번 그렇게 해서 "ACONF 전부 밴드 A" 라는 가짜 결론을
냈던 이력이 있다.

## 🔴 headroom audit 결과 — 본실행 결과 해석의 전제

**"이길 여지 4문제"는 채점 기준 하나에서만 나오는 값이었다.** (`docs/HEADROOM_AUDIT.md`)

| 지표 | R0 | 완벽 정책 | headroom |
|---|---:|---:|---:|
| Escalation Appropriateness (§7.3) | 52 | 92 | **+40** (43.5%p) |
| 참조방향 정확도 | 56 | 69 | **+13** (14.1%p) |
| justified resolution | 56 | 69 | **+13** (14.1%p) |
| 수준상대 정답 (`is_correct`) | 77 | 81 | +4 (4.3%p) |
| 과대해석률 (§7.1 주 지표) | 0 | 0 | **+0** |

**본실행 결과를 읽을 때 반드시 지킬 것 4가지** (`DECISION_LOG.md` 2026-08-12 (1)) —

1. **R0 대비 주 비교축을 `is_correct` 로 두지 않는다.** `oracle_action` 이 «사용한
   수준»에 따라 달라져 밴드 C 에서 R0 의 L1 보류가 정답 처리된다(17과제 무상 취득).
   → **justified resolution · 참조방향 정확도**로 읽는다.
2. **§7.1 은 V vs V−τ 전용이다.** R0 의 0 은 구성상 하한이라 이길 수 없고 질 수만 있다.
3. **§7.3 Correct Abstention Rate 는 «L1 한정»임을 명시해 보고한다.** 완벽한 adaptive
   정책이 R0(68%)보다 나쁘게 나온다(16%). 정의는 바꾸지 않는다.
4. **비용을 함께 보고한다.** 전량 L3 의 92%(69/75) 성능을 **14.4% 비용**으로.
   단 ALL_L3 우위 6과제 중 4개가 밴드 D 우연이라 A/B/C 한정 71 대 68 도 함께 적는다.

**줄일 수 없는 몫이 11과제다** (완벽 정책의 tool-limited). 실제 V 의 agent-limited 는
이 11개 «밖에서» 센다.

## 명령어

```bash
cd "/Users/hoyoun/Documents/Yonsei_AX_Camp/(진짜_이게_최종)"

# 테스트 37개 (pytest 없음 → 직접 러너)
python3 - <<'PY'
import sys, traceback, importlib.util; from pathlib import Path
sys.path.insert(0, "src"); ok = fail = 0
for f in sorted(Path("tests").glob("test_*.py")):
    s = importlib.util.spec_from_file_location(f.stem, f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    for n in [n for n in dir(m) if n.startswith("test_")]:
        try: getattr(m, n)(); ok += 1
        except Exception: fail += 1; print(f"🔴 {f.name}::{n}"); traceback.print_exc()
print(f"{'🟢' if not fail else '🔴'} 통과 {ok} · 실패 {fail}")
PY

python3 src/vccl/agents/r0.py            # 기준선 재현 (LLM 0회)
python3 src/vccl/scoring/headroom.py     # headroom 감사 (LLM 0회)
python3 src/vccl/agents/quota_probe.py   # quota 확인
```

## 크래시 대비 (2026-08-09 에 컴퓨터가 죽었다)

**계산은 전부 끝났으므로 이제 DFT 를 다시 돌릴 일이 없다.** 다만 다시 돌릴 상황이
오면 **반드시 `calibration/safe_dft.py`** 를 쓴다 (구 러너 `dft_tau_probe.py` 는
워커 4개 × 6 GB 를 16 GB 머신에 요구해서 머신을 죽였다).

| | 구 러너 | safe_dft.py |
|---|---|---|
| 동시 잡 | 4 | **1 (직렬)** |
| 선언 메모리 | 6~10 GB | **3 GB** |
| 완료 판정 | 파일 존재 ❌ | **`Psi4 exiting successfully` 마커** |
| 대형 분자 | in-core DF | **`scf_type disk_df`** (40원자↑) |

두 개의 함정 — **`scf_subtype disk_df` 는 없는 옵션이다**(`scf_type disk_df` 가 맞다) ·
**`PSI_SCRATCH` 는 반드시 절대경로**(상대경로면 sp.out 조차 안 만들고 즉사).

**계산이 멈추면 먼저 `/private/tmp` 를 본다** — `du -sh /private/tmp/* | sort -rh | head`

## git

**전부 커밋·push 완료.** 최근 커밋 `6beaf2a`.
`멘토링_대비_내가_알아야_할것.md` 와 `연구방향_검토요청.md` 는 **의도적으로 git 제외**
(`.gitignore`). 저장소 https://github.com/hoyoun1015/yonsei_ax_camp_final

## 잊지 말 것

- 주제·RQ·**위계(주인공은 에이전트)** 는 `CLAUDE.md`. 임의로 바꾸지 않는다.
- **τ · 224반응 계산 · 비용 측정 · benchmark 는 다시 건드리지 않는다.** 완료된 평가
  인프라다.
- **3-agent 구조를 축소하지 않는다.** 한 condition 안에서 역할별로 모델을 섞지 않는다.
- **동결 후 불변.** 결과를 본 뒤 τ·라벨·지표 정의를 고치지 않는다.
- **분기 B 는 원 가설을 바꾸지 않는다.** 조작화만 수정하고 최종 결론은 원 가설에 답한다.
- 계산 규모를 줄여서 문제를 피하지 않는다. 실행 방식으로 푼다.
- 문서는 전문용어 없이, 사용자 목소리로 쓴다 (AI 는 알지만 화학은 모르는 독자).
