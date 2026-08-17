# 🔴 이 실행은 무효다 — 결과를 사용하지 않는다

**cross-model replication 1차 시도 (2026-08-13)** · `claude-sonnet-4-6` · condition V

## 무효 사유

전반 15과제 중 10개를 마친 시점에 **Claude quota 가 소진**됐다.

```
Individual quota reached. Please upgrade your subscription... Resets in 4h21m9s.
```

11·12번 과제가 연속 FAILED → **FAILED 2/30 = 6.7% > 5%** 로
사전등록된 무효 기준을 넘겼다 (`docs/DECISION_LOG.md` 2026-08-14 (2)).

## 처리

- **완료된 10과제 결과도 사용하지 않는다** (사용자 지시 2026-08-14).
- **성능 지표를 한 번도 보지 않았다.** 러너가 실행 모드에서 성능을 출력하지 않는다.
- `replication_result.json` 은 기록되지 않았다 — 집계·보고 경로에 잡히지 않는다.
- 이 디렉터리는 **provenance 보존 목적으로만** 남긴다.

## 남아 있는 것

- `calls.jsonl` 69줄 (성공 61 · 에러 8) — 원장
- `rows_partial.json` 12과제분 채점 결과 — **분석에 쓰지 않는다**

## 재실행

`docs/DECISION_LOG.md` 2026-08-14 (3) 의 schedule-only amendment 에 따라
**8 + 8 + 7 + 7 chunk** 로 처음부터 다시 돌린다. N=30 · subset · 순서 · 모델 ·
프롬프트 · 채점은 바뀌지 않았다. 새 실행은 `experiments/repl_c{1..4}_*` 에 쌓인다.
