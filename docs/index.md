---
status: active
owner: maintainers
last_verified: 2026-09-11
---

# 文書案内

[English](index.en.md)。新規セッションは [AGENTS.md](../AGENTS.md) から対象 Skill と承認範囲を確認する。

- [アーキテクチャ](architecture.md) ／ [English](architecture.en.md): Skill と repository の責務境界。
- [品質](QUALITY.md) ／ [English](QUALITY.en.md): 検証入口と証拠の限界。
- [Plan 運用](PLANS.md) ／ [English](PLANS.en.md): 状態・必須項目・manual merge。
- [ハーネス契約](testing/harness-contract.md) ／ [English](testing/harness-contract.en.md): 全既存 suite の到達範囲。
- [ADR 0001](adr/0001-repository-harness.md) ／ [English](adr/0001-repository-harness.en.md): D1〜D10 と二言語方針。
- [active EP-HARNESS-001](exec-plans/active/EP-HARNESS-001.md) ／ [English](exec-plans/active/EP-HARNESS-001.en.md): M1〜M4、実行証拠、残件。
- [英語版 repository instructions](../AGENTS.en.md)。
- [インストール](installation.md)、[互換性](compatibility.md)、[開発参加](../CONTRIBUTING.md)、[Skill カタログ](../README.md)。

日本語の既存 path を維持する。今回新設・実質変更した永続文書だけを日英ペアの対象とし、Skill 本文・引用・license と既存未変更文書は一括翻訳しない。対応表と source hash は `tools/repoctl/doc-manifest.json`。hash は stale を検出するが翻訳品質を保証しない。

M5 eval contract、M6 host verification、M7 human-validation の文書・機能は今回未着手。将来の予定を現在利用可能と読まない。
