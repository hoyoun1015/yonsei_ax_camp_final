# 보충자료 표 S9 — LOCK 기록 (cross-model replication)

**LOCK 2026-08-19** · 생성 2026-08-19

이 표의 **수치·통계·문구·행·열·각주는 확정**됐다. 이후 변경은 제출 형식에 따른 레이아웃 조정만 허용하며, 그 밖의 변경은 **먼저 amendment 로 보고**한다.

> ⚠️ PDF 는 matplotlib 이 /CreationDate 를 박아 재생성 시 해시가 달라진다. 내용 동일성은 PNG 로 확인한다.

🔒 **이것은 S1~S8 과 별도의 기록이다.** `tables/supplementary/LOCK_MANIFEST.md` · `lock_manifest.json` · `lock_manifest.py` · `make_supp_tables.py` 를 **수정하지 않았다.**

**영향받지 않는 기존 LOCK**

- Figure F0~F4 (figures/captions.md · figures/draft/)
- Main Table 1 (tables/draft/T1_system.*)
- Supplementary S1~S8 (tables/supplementary/LOCK_MANIFEST.md)

---

## 1. 표 산출물

| 파일 | 크기 | sha256 |
|---|---:|---|
| `tables/supplementary/S9_replication.md` | 6,469 | `79da87d0eb123e248399ba4a64b5f59c2ec705d94c71ff153e1c087ed468dab3` |
| `tables/supplementary/S9_replication.pdf` | 21,340 | `afa55a93892d30996548782b8368f76d5c32f5739c64cf590a52c0181d77185e` |
| `tables/supplementary/S9_replication.png` | 148,921 | `6fef0bd20468b7aca326e0a59e8a6c4393e02cb153823073c96a47e441acaaa1` |

## 2. 생성 코드

| 파일 | sha256 |
|---|---|
| `tables/make_replication_table.py` | `a489ee1bbe3c9f5349621762ae34a978de686db319c740b10d25cfcfd2c5d32e` |
| `src/vccl/scoring/replication_final.py` | `01d3fdd3f6b38d8a22901611f42c0f0d4a5f8dcff4765628fa5b3f87d3462678` |

## 3. 상류 산출물

| 파일 | sha256 |
|---|---|
| `results/cross_model_replication_final.json` | `078c351268b6eebbbca46da8b3a9791c1adbfc147c3370b8abced9919420b821` |
| `experiments/repl_c1_20260814T011558Z_claude-sonnet-4-6/replication_result.json` | `d237778c6282600609b24eb5c5c2a149c6a73ba5b044c7c6cb41450d95803253` |
| `experiments/repl_c2_20260814T064515Z_claude-sonnet-4-6/replication_result.json` | `251abb45d6f06e5177b4b0d96189e56c0bfc23efb41761de607988d18a6f4646` |
| `experiments/repl_c3_20260818T084420Z_claude-sonnet-4-6/replication_result.json` | `295ef2586a12c15a1025d1f07a6b00f9624e457fda42a8e1b6dbb22eb9f11358` |
| `experiments/repl_c4_20260818T155836Z_claude-sonnet-4-6/replication_result.json` | `1b15b805782587865c2a331530b07dc87479ef292fd8d653e30aeb9c6ee401ba` |

## 4. 동결 해시

```
stage_a         0bfc4cee6a6cf0e087d104610fa83975ca5223ef99381130d301317f84995e8b
stage_b         2e80a29588b91bafa646065ab1726d979e611014d31cf0ff6fa961f15eac014b
execution_order 09f8ea4f4512c392ad75658d5929809549196eaf49e40756b67ab816992a92b0
```

## 5. 검증

```bash
python3 tables/make_replication_table.py --verify
```

기계가 읽는 기록은 `tables/supplementary/S9_lock.json` 이다.
