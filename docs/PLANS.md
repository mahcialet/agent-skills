---
status: active
owner: maintainers
last_verified: 2026-09-11
---

# ExecPlan の運用

[English](PLANS.en.md) ／ [文書入口](index.md)

会話履歴なしに目的、範囲、検証、残件を判断できる生きた計画を `docs/exec-plans/<status>/` に置く。状態は `draft`／`active`／`paused`／`completed`／`abandoned`。日本語と英語のペアは同じ ID の 1 論理 Plan とする。

frontmatter の必須項目は `status`、`owner`、`last_verified`、`plan_id`、`plan_type`、`base_branch`、`branch`、`merge_policy`。通常 `merge_policy: manual`。依存と親参照は存在・自己参照・循環を検査し、親子関係と実行依存を区別する。翻訳間で ID、状態、branch、依存、受入条件を変えない。

必須節は次の 12 節（見出し識別子は英語のまま保持）:

1. Purpose / Big Picture
2. Progress
3. Surprises & Discoveries
4. Decision Log
5. Outcomes & Retrospective
6. Context and Orientation
7. Plan of Work
8. Concrete Steps
9. Validation and Acceptance
10. Idempotence and Recovery
11. Artifacts and Notes
12. Interfaces and Dependencies

`python -m tools.repoctl plans list` は一覧、`plans check` は構造と必要な Git 到達性を検査する。状態変更・Agent 起動・fetch・merge はしない。`docs-check` は checkout の構造だけを判定する。履歴不足を成功へ変換しない。

`paused` は理由と再開条件、`abandoned` は理由を残す。`completed` は実 delivery merge commit が base から到達可能なことを確認してから両言語を移す。未来の SHA を書かず、未 merge の実装は active のまま。必要な remote freshness は実行者が明示 fetch で確保する。

機械検査用の field は `pause_reason`、`resume_criteria`、`abandon_reason` を使用する。

draft、paused、human-validation は自動起動しない。人間用 Plan は `execution_mode: human-kick` と merged 依存を明示し、観測者名を認証済み承認と扱わない。予定日や認証情報があっても実行許可ではない。

各 checkpoint で exact revision／dirty fingerprint、argv/cwd、環境、結果、証拠 class、失敗段階、artifact 参照、限界、review disposition を記録する。成功回数だけを証拠にしない。機密を除去し、生ログの mirror は保存しない。

今回の [EP-HARNESS-001](exec-plans/active/EP-HARNESS-001.md) は M1〜M4 のみ承認済み。M5 以降・実モデル・実ホスト・merge は別指示が必要。M3 native matrix が未実行なら全体完了にしない。
