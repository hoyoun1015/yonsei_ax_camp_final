# RESUME_HERE — 세션이 죽으면 이 파일부터 읽는다

**현재 시점 2026-08-18 · 마감 9/2**

이 파일에는 **지금 상태만** 적는다. 과거 이력(무효 배치, 수정 전 설계, 지난 계획,
디버깅 기록)은 **여기서 반복하지 않고 `docs/DECISION_LOG.md`** 를 본다.

---

## 지금 상태 한 줄

**본실행 N=92 확증 완료. Figure F0~F4 LOCK · Main Table 1 LOCK.** 지금은 식별
챌린지 secondary 94(post-hoc 탐색적)는 완료돼 S6 (나)에 반영됐고, cross-model replication은
**23/30**(chunk 1·2·3 VALID)에서 chunk 4 만 남았다. **성능은 전량 완료 전까지 열람하지
않는다 — 지금도 BLINDED 다.** 본문 집필은 승인 전 시작하지 않는다.

| 단계 | 상태 |
|---|---|
| 본실행 N=92 (V · V−τ) | 🟢 완료 · FAILED 0/92 · 911호출 |
| identification challenge primary 24 | 🟢 완료 · 24/24 |
| Figure F0~F4 | 🟢 **LOCK** (`figures/draft/`) |
| Main Table 설계 | 🟢 완료 (`paper_logic/table_design.md`) |
| Main Table 1 제작 | 🟢 **LOCK** (`tables/draft/T1_system.md|.pdf|.png`) |
| secondary 94 (식별 챌린지) | 🟢 **완료** · 94/94 · post-hoc 탐색적 (S6 (나) 반영) |
| cross-model replication (sonnet, V 단독, N=30) | 🟡 **23/30** · chunk 4 남음 · 성능 BLINDED |
| Supplementary Table S1~S8 | 🟢 **LOCK** (2026-08-17) · `tables/supplementary/LOCK_MANIFEST.md` |
| 본문 집필 | 🔲 승인 전 시작 금지 |

---

## 확증 결과 (N=92)

| 지표 | R0 | V | V−τ |
|---|---:|---:|---:|
| 근거가 충분한 결론 | 56/92 | **74/92** | 54/92 |
| 과대해석 (사전등록 주 지표) | 0 | **0/92** | 3/92 |
| 과도한 신중 | — | **0/92** | 20/92 |
| 참조방향 정확 | 56 | 74 | 56 |
| 계산 비용 (ALL_L3 대비 · 실측) | 0.02% | **30.6%** | **139.3%** |
| 최종 판단 수준이 L3인 과제 / L3 실행 횟수 | 0 | 45/92 · 45회 | 91/92 · **101회** |
| 자율 식별 정확도 | 해당 없음 | 76/76 | 76/76 |
| FAILED | — | **0/92** | **0/92** |

**Band C (25과제)** — V 22 · V−τ 11 · R0 8

### 통계검정 (정확 McNemar · paired · 동일 92과제)

| 비교 | 불일치 (b:c) | p |
|---|---|---|
| **V 대 V−τ** (근거가 충분한 결론) | 21 : 1 | **1.1×10⁻⁵** |
| **V 대 R0** | 23 : 5 | **9.1×10⁻⁴** |
| V−τ 대 R0 | 15 : 17 | 0.86 |
| **V 대 V−τ (Band C)** | 11 : 0 | **9.8×10⁻⁴** |
| V 대 R0 (Band C) | 15 : 1 | 5.2×10⁻⁴ |
| V 대 R0 (Band C 밖) | 8 : 4 | 0.39 |
| **과대해석 V 대 V−τ** | 0 : 3 | **0.25 (유의하지 않음)** |
| 과도한 신중 V 대 V−τ | 0 : 20 | 1.9×10⁻⁶ |

### 해석할 때 지킬 것

- **사전등록 주 지표(과대해석)는 유의하지 않았다.** τ가 과대해석을 줄였다고 쓰지 않는다.
  실제 차이는 근거가 충분한 결론·과도한 신중·Band C에서 나왔다.
- **Band C 밖 p = 0.39는 «차이가 없다»가 아니라 «유의한 차이가 검출되지 않았다»** 이다.
- **ALL_L3(75/92)는 상한이 아니라 비교용 정책이다.** «…% 성능» 같은 비율로 쓰지 않는다.
  고정 문구 — *"ALL_L3가 해결한 75과제 중 74과제를 30.6% 비용으로 해결했다."*
- **tool-limited를 «줄일 수 없는 오류»로 쓰지 않는다.** 지금 쓴 도구·수준에서 판단만
  고쳐서는 해결하기 어려웠다는 뜻이며, 더 높은 수준으로 줄일 수 있는지는 알 수 없다.
- **경로 B는 92과제 중 1회만 쓰였다.** «완전한 closed-loop을 검증했다»고 쓰지 않는다.
  동시에 그것만으로 «단순 fidelity router»라고 규정하지도 않는다.

---

## 동결 해시 (현재)

```
frozen_rules_v1.json     0bfc4cee6a6cf0e087d104610fa83975ca5223ef99381130d301317f84995e8b
frozen_stage_b_v1.json   2e80a29588b91bafa646065ab1726d979e611014d31cf0ff6fa961f15eac014b
execution_order_v1.json  09f8ea4f4512c392ad75658d5929809549196eaf49e40756b67ab816992a92b0
loop.py 5b7b79cf…  ·  schemas.py 94d70bed…  ·  prompts.py 85224e4b…
```

**Band 경계는 반응 유형별 τ다** (서브셋별 MAE가 아니다) —
conformer 0.405 / 1.213 / 3.638 · isomer 3.407 / 9.036 / 27.107 (kcal/mol).

---

## 재현 명령

```bash
cd "(진짜_이게_최종)"

python3 src/vccl/scoring/aggregate.py --check     # 동결·무결성 점검 (API 0)
python3 src/vccl/scoring/aggregate.py --save      # N=92 집계 (API 0)
python3 src/vccl/scoring/plot_data.py             # 동결본 → results/plot_data/ (assertion)
python3 figures/make_figures.py                   # plot_data → figures/draft/ (LOCK된 그림 재생성)

python3 - <<'PY'                                  # 테스트 49개 (pytest 없음)
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
```

**실행 중 감시** `python3 src/vccl/agents/batch_status.py` (로컬 파일만 읽는다)

---

## 문서 지도

| | |
|---|---|
| `paper_logic/anchor_fol.md` | 앵커 논문(arXiv 2604.18805)의 주장 사슬 |
| `paper_logic/new_fol.md` | 우리 주장 사슬 NEW-FOL-1~18 + 근거·금지 표현 |
| `paper_logic/claim_evidence_map.md` | 주장–증거 대응표 + 한계 L1~L8 |
| `paper_logic/gap_analysis.md` | 앵커 대비 · 핵심 명제 후보 · 부정적 결과 목록 |
| `paper_logic/figure_design.md` | Figure 설계 근거 |
| `paper_logic/table_design.md` | **Main Table 설계 (최신)** |
| `figures/captions.md` | Figure 설명문 (LOCK) |
| `tables/draft/T1_system.md` | Main Table 1 (LOCK) |
| `tables/supplementary/` | 보충자료 표 S1~S8 (LOCK 전) |
| `docs/incidents/` | 사고 원본 증거 (`DECISION_LOG` 2026-08-16 (4)) |
| `docs/DECISION_LOG.md` | **모든 결정·정정 이력. 과거 상태는 여기서 본다** |
| `docs/HEADROOM_AUDIT.md` | 본실행 전 audit (⚠️ 문서 상단의 정정 표시를 먼저 읽을 것) |

---

## 남은 할 일

1. 🟢 **secondary 94 완료** — 94/94 · 신규 FAILED 0/70 · S6 (나) 반영됨.
   `DECISION_LOG` 2026-08-17 (1). **S1~S8 LOCK 에 포함됐다** (2026-08-17 (2)).


2. 🔲 **cross-model replication chunk 4** (마지막 7과제) — chunk 3 은 2026-08-18 에
   **VALID** 로 완료됐다 (7/7 · FAILED 0 · `DECISION_LOG` 2026-08-18 (1)). 진행 **23/30**.
   chunk 4 는 **다음 충분한 5시간 usage window 이후 별도 실행**한다
   (실행 규약 `DECISION_LOG` 2026-08-14 (3): Claude 5시간 ≥ 90% 에서 시작).
   사전등록 `DECISION_LOG` 2026-08-14 (2)·(3). **30과제 전량 완료 전 성능 열람 금지**
3. 🟢 **manuscript-source consistency cleanup 완료** (2026-08-17 · `DECISION_LOG` (3))
   — headroom «천장·상한» 정정 · L0 «우연 수준» 제거 · secondary 94 현재 상태 반영 ·
   옛 T/F 번호와 «후보 67건» 격리. **LOCK 산출물·결과 수치 무변경.**


4. 🔲 **본문 집필** — 승인 전 시작하지 않는다
5. 🔲 선행연구 재확인 — StatefulDiscovery 대비는 정리됨(`gap_analysis.md` §6),
   시스템 이름은 미정 (VirtualLab_CC와 충돌 회피 필요)

---

## 잊지 말 것 (프로젝트 불변조건)

- 주제·RQ·**위계(주인공은 에이전트)** 는 `CLAUDE.md`. 임의로 바꾸지 않는다.
- **τ · 224반응 계산 · 비용 측정 · benchmark 는 다시 건드리지 않는다.** 완료된 평가 인프라다.
- **동결 후 불변.** 결과를 본 뒤 τ·라벨·지표 정의를 고치지 않는다.
- **3-agent 구조를 축소하지 않는다.** 한 condition 안에서 역할별로 모델을 섞지 않는다.
- 문서는 전문용어 없이 사용자 목소리로 쓴다 (AI는 알지만 화학은 모르는 독자).
- DFT를 다시 돌릴 일은 없다. 만약 돌리게 되면 **반드시 `calibration/safe_dft.py`**
  (구 러너는 메모리 초과로 머신을 죽였다 — 상세는 `DECISION_LOG` 2026-08-09).

## git

저장소 https://github.com/hoyoun1015/yonsei_ax_camp_final (PUBLIC)

**2026-08-17 전량 푸시 완료.** 08-12~08-17 작업(본실행·식별 챌린지·replication 16/30 ·
Figure/Table LOCK · DECISION_LOG · paper_logic)이 모두 원격에 올라가 있다.

**미푸시 (2026-08-18)** — chunk 3 run 디렉터리
`experiments/repl_c3_20260818T084420Z_claude-sonnet-4-6/` (untracked) 와
이 파일·`DECISION_LOG` 의 이번 갱신이 아직 커밋되지 않았다.

**README 는 외부 독자용 랜딩 페이지다** (2026-08-17 재구성). 내부 진행 상황·집필 규칙은
README 가 아니라 이 파일과 `DECISION_LOG` 에 둔다. 재현 상세는 `docs/REPRODUCIBILITY.md`.
README 를 고칠 때 지켜야 할 것 — 조건 4종 정의 유지, R0 오라클 입력 단서 유지,
ALL_L3 를 상한이라 쓰지 않기, p 값 8건이 사후 분석이라는 표시 유지,
주 지표 p = 0.25 를 결과와 같은 자리에 두기, 시스템 이름 확정하지 않기.
`멘토링_대비_내가_알아야_할것.md` · `연구방향_검토요청.md` 는 의도적으로 git 제외.
