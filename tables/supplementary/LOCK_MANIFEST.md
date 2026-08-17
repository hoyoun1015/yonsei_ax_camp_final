# 보충자료 표 S1~S8 — LOCK MANIFEST

**LOCK 2026-08-17** · 생성 2026-08-17

이 표들의 **수치·통계·문구·행·열·각주는 확정**됐다. 이후 변경은 제출 형식에 따른 레이아웃 조정만 허용하며, 그 밖의 변경은 **먼저 amendment 로 보고**한다.

> ⚠️ PDF 는 matplotlib 이 /CreationDate 를 박아 재생성 시 해시가 달라진다. 내용 동일성은 PNG 로 확인한다.

**영향받지 않는 기존 LOCK**

- Figure F0~F4 (figures/captions.md · figures/draft/)
- Main Table 1 (tables/draft/T1_system.*)

---

## 1. 표 산출물

### S1 — 통계검정 요약 (정확 McNemar 8건)

| 형식 | 크기 | sha256 |
|---|---:|---|
| `.md` | 6,192 | `445e7f2dbf66bc9022128ee151f97afa7184be6b43f82c88a208bc5332ebec48` |
| `.pdf` | 25,032 | `8225e2625c46a73ae76c1e622c27ad5d4614479dc714705b8b04344646b2ffe2` |
| `.png` | 155,153 | `bdcc090c5cbe5074a6b2edaefb8e13463868594f8a6e6f6227cf3b28d979ff06` |

### S2 — 반응 유형·서브셋별 방법 오차 τ 실측

| 형식 | 크기 | sha256 |
|---|---:|---|
| `.md` | 4,177 | `5c033532742da71062fe2c4009389e75ee5e47e0eb52e8775b2bc71fd68f6d29` |
| `.pdf` | 19,169 | `780b33416b45e1d42156c1f68889b22435758f5f2b8bd0264598a1f1b5835b36` |
| `.png` | 163,649 | `55bab0ca9036005e931b3e67defc5db26b379dfa4307ff52cf66f8d29e5a332c` |

### S3 — 오류 분해 (탐색적)

| 형식 | 크기 | sha256 |
|---|---:|---|
| `.md` | 3,157 | `bc4b8467ca9b6c359ff0024154e2688112401598dbf1ab2797db7f24e031dc00` |
| `.pdf` | 17,311 | `2082bfd40af6add19c3ca4b3413d7333420c38935606267d5a0c6282f883c6f2` |
| `.png` | 87,826 | `34e0819addb83ad3eca5f3fa499fe56f0c1aca7137a5b895271db0573ee8bb3b` |

### S4 — 벤치마크 구성 (N=92)

| 형식 | 크기 | sha256 |
|---|---:|---|
| `.md` | 4,183 | `fe047b87cd4d10f527414f4f9186070af98ca9652a118d8534caf2b1041a8b17` |
| `.pdf` | 21,717 | `e4aff8e9bc8099418f062b3f57c6f152cafb8d9c7cad3dd9dab3e8a874931b4a` |
| `.png` | 166,380 | `92143446dabfd6ac7136b3b7a9dd9a0af548d152400e0d38f8b68ac7c85ad3ab` |

### S5 — 계산시간·비용 상세 (psi4 실측)

| 형식 | 크기 | sha256 |
|---|---:|---|
| `.md` | 5,429 | `0333c71a9207fa964d4363821a2022bf8101583946c2ddf0c61bcaaef7565f6d` |
| `.pdf` | 21,980 | `411ba7b9fb467ad0d719bae503c8a1678e4a3f2ec0acbd3821b980ddab5981f9` |
| `.png` | 181,007 | `1834fec1aaaa7b21e02fb35be7bd44f4bf00ac506cc8164fca9cc9284b21446d` |

### S6 — 구조 식별 보조 검증 (primary 24 · secondary 94)

| 형식 | 크기 | sha256 |
|---|---:|---|
| `.md` | 9,005 | `1768899165852870b72ef05b113c4d0a27d357ab0ae7a617710bb5f567d6b708` |
| `.pdf` | 36,201 | `d09deea8b4715305a8de1e5d34605dd648b63a388009c0fd4d81fe3b94ebffa1` |
| `.png` | 451,170 | `ab0b784cd332ff4dd77d284d176b94c87969575dd61fad2753b4cad9fa73cd5e` |

### S7 — 계산 도구 없이 답하게 한 검사 (L0 probe)

| 형식 | 크기 | sha256 |
|---|---:|---|
| `.md` | 3,510 | `cec36ae06f4cd23c0a14bbf573ba586dbe694d13b732ac7aac968180d1989c69` |
| `.pdf` | 18,575 | `fb5140582d5344e2a89eb4031b4f805079e0bf501319eab89059f0cdd5a0a9e1` |
| `.png` | 122,399 | `f2797cb17f331bfdbc331261b2cd66e4e740ef81fd1389e4051cf53d135dc6c3` |

### S8 — 그림 5 사례의 에이전트 출력 전문

| 형식 | 크기 | sha256 |
|---|---:|---|
| `.md` | 6,761 | `8a1f280cc3addd15de30f431ff8c03988a9050ea54f62577f958c84104d44454` |
| `.pdf` | 29,364 | `97be3a1388f77ea9016b52fe593e2ebd1424915937a3c123587fdb2bd9ff3f6d` |
| `.png` | 291,110 | `6f49db653a36a8ee5239a506c402215d0389220a0e95b52bdfc9b7ef9bae8aad` |

---

## 2. source data (`results/table_data/`)

표는 이 파일들만 읽는다. 값을 바꾸려면 생성기를 고쳐야 한다.

| 파일 | 크기 | sha256 |
|---|---:|---|
| `s1_tests.json` | 6,172 | `e2d65bfbc418b211c781c3f39ae7657212ac14860f5dfb480fc0e54af1b9205d` |
| `s2_tau.csv` | 892 | `db35508605569d8770b8fead7c8808c222fd153e2017072ab4ec39ed169f0f76` |
| `s2_tau.json` | 4,741 | `a520e09300998ecfae8c7ddac3676a01ae8d6e1894c7799fa4ac4b5b2428ced7` |
| `s3_errors.json` | 2,333 | `2b2499121dcc63dfb33ca7e929a2210e42ad2fa02b7a7ef31514fd16d6e60f14` |
| `s4_benchmark.json` | 4,036 | `a2c96b9b15d2c2d91b5d54b2a08c6eb282fe6d0234c3a8ab0d517ed7ae5835e9` |
| `s4_tasks.csv` | 6,658 | `38b153ec1a43b614249b220eb7ead826f4428498b4e57a5b5938f0cbd3f947b9` |
| `s5_cost.json` | 3,154 | `f48df5a795e3f169d6522470a70433b9844e08071dffc1463089a7fd2fdf88ed` |
| `s5_cost_by_task.csv` | 6,831 | `f07870521a81bdc92c15106cba312db1a4ec2badf75f0122b8d1baff106b0bb4` |
| `s6_identification.json` | 8,947 | `8fb3889bd0ca6d4d1bbe65b4f03b0bd697b63290799d0e8a7cbabe4e425e10a7` |
| `s7_l0.json` | 1,706 | `b880af3cefdce92654f2c45bed7c8544febd3248300336b588ef7e84da77437f` |
| `s8_trajectory.json` | 6,284 | `42700fe8d913a526e486b439905595cdf527a204ab13cdd87e52db21690d7fa1` |

---

## 3. 생성 코드

| 파일 | sha256 |
|---|---|
| `src/vccl/scoring/table_data.py` | `e1bb679090d9a9233f7e945c753074d84e412f4e28dac25869963c380687b0c4` |
| `tables/make_supp_tables.py` | `bccf939c3c409e668ae46c2b7ca0cbb03422aca040ce7ef2507b25e9db8f766a` |
| `tables/lock_manifest.py` | `5963bb3889b0ab5c762ceb59858ab4b0a5c80bbd950bc42823a9248481b44ba4` |

---

## 4. 상류 산출물 (이 표들의 근거)

| 파일 | sha256 |
|---|---|
| `data/tasks/frozen_rules_v1.json` | `5e3e781c10a2fd78b2a04c7dc50f4f720f19cc9439e3aa78e2dc6596efe13590` |
| `data/tasks/frozen_stage_b_v1.json` | `5a8694b957d2bf61dff4ceddb5e9a07041c3ad5f3d27a4230df5fa85941fac7c` |
| `data/tasks/execution_order_v1.json` | `b15c2e2cc2b21b03b696b07038ce4742210f816f76e396186944c0014bc07b19` |
| `results/main_run_aggregate.json` | `926ebfa1c17b5fa0b62baafb5a4845f15bc6fdc51429b9dbc6957c609738f157` |
| `results/oracle_headroom_audit.json` | `b64e7d594772944210fb8a01135a95141714bef86f6f8f7c2ab93436084faec8` |
| `experiments/chal_primary_20260814T235648Z_gemini-3.6-flash-high/challenge_result.json` | `7c102f338210a80760489ded67a295c123f935db3dd148e1f9ce558fca1fab4a` |
| `experiments/L0_20260811T134258Z_gemini-3.6-flash-high/l0_result.json` | `7865289a625008ae27f5bd83c10f27d3143a41305e907eee7a1715d4776fd141` |
| `experiments/chal_secondary94/secondary_result.json` | `ab2eb8ddf8c71feb4b575418f0c4b4a9168273a1959a8a6a7a1a44c366c7f937` |
| `experiments/main_b1_20260813T003426Z_gemini-3.6-flash-high/batch_result.json` | `0e0fbfd26e66355b0b60864c84e4b2668c00b6cb19d3afeef3e03175be017091` |

---

## 5. 검증

```bash
python3 tables/lock_manifest.py --verify
```

MD·PNG·source data·코드·상류 산출물의 해시를 현재 파일과 대조한다. PDF 는 생성시각이 박히므로 대조에서 뺀다.

