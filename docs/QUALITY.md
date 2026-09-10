---
status: active
owner: maintainers
last_verified: 2026-09-11
---

# 品質と検証

[English](QUALITY.en.md) ／ [契約](testing/harness-contract.md) ／ [文書入口](index.md)

通常の正規入口は `python -m tools.repoctl verify`。準備として project venv に `requirements-dev.txt` を明示導入する。verify 自身は依存をインストールしない。`check` は静的検査、`test` は suite discovery と実行、`test --list` は対象確認。既存 shell 入口は互換のため残す。

通常検証では外部 LLM、Backlog／Redmine、実ホスト CLI、実ユーザー配置先へ到達しない。M1〜M4 では installer standalone smoke と実ホスト評価は `NOT_REQUESTED`。配置の unit/integration tests と実 host 発見を混同しない。

| 証拠 class | 証明するもの | 証明しないもの |
|---|---|---|
| Forced invariant | 狙った違反を fixture が正しい段階・診断で捕捉する | 全 OS・全 interleaving |
| Direct native / integration | 記録した revision・OS・version の実行 | 別 OS・host・本番 |
| Structural / tooling | schema、構造、lint、drift | 意味保存・文章品質・host 発見 |
| Model observation | 指定試行での出力 | 将来全出力・人間承認 |
| Human observation | 指定 case の観測と判断 | merge 承認・未確認 case |
| Repetition / stability | 指定回数の安定性 | 因果的再現・証拠の格上げ |

新しい検査には破損 fixture の negative control を置く。exit code だけでなく stable `ASKILLS-*` code と失敗段階を検証する。動的 import や任意 Python の意味は静的 runtime 閉包検査で完全証明できないため、コピー隔離 fixture と実利用検証の限界を分ける。

check は read-only、`generate` のみ生成区画を更新する。日本語原本と英語訳の source hash は stale 検査であり意味一致の証明ではない。翻訳を読まず hash だけ更新してはならない。

証拠は既定 console、明示 `--out <new-directory>` だけ永続化する。失敗を上書きせず、秘密 sentinel で redaction を検証する。timeout/cancel は所有 child の終了・cleanup を確認してから完了扱いにする。出力欠落や未終了資産は制約として残す。

必須 native matrix は Linux/macOS/Windows × Python 3.12。workflow が存在するだけでは verified ではない。local の別 Python version は別証拠。AC ごとの実結果と未実施範囲は active ExecPlan を正とする。

レビューは実装 context と分け、指摘を採用／却下／延期と根拠付きで記録する。対応後は影響範囲を再検証する。チェック成功と人間による承認は別物である。
