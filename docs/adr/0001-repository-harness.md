---
status: active
owner: maintainers
last_verified: 2026-09-11
---

# ADR 0001: Python のリポジトリ内ハーネス

状態: accepted（M1〜M4 の実装判断、後続 milestone の実行承認ではない）。日付: 2026-09-11。

対応する [英語版](0001-repository-harness.en.md)。根拠と進捗は [EP-HARNESS-001](../exec-plans/active/EP-HARNESS-001.md)。

| ID | 採用判断 | 理由／再評価条件 |
|---|---|---|
| D1 | Python、`python -m tools.repoctl` | 既存 Python 資産を再利用。Go 必須化を却下。 |
| D2 | 通常 verify は決定的・ローカル | 外部 LLM、本番 API、実ホストの起動を除外。通常 CI を課金・認証・モデル変動に依存させない。 |
| D3 | validator／installer／Skill tool の責務を保持 | ハーネス導入と Skill 挙動変更を混ぜない。 |
| D4 | eval は plan／ingest／report、provider-neutral | RFE の既存契約を再利用。直接モデル runner は別途判断。今回 M5 は未着手。 |
| D5 | installer smoke と実ホスト検証を区別 | 配置成功はクライアントの利用証拠ではない。今回 M6 は未着手。 |
| D6 | M2 から versioned evidence | 失敗・実行対象・cleanup を後付けしない。 |
| D7 | Plan 状態・必須項目・参照・証拠を検査、manual merge | scheduler／GitHub gate 全体の移植を却下。 |
| D8 | human-validation を独立 Plan へ | 実装完了と実利用確認を区別。今回は M7 未着手。 |
| D9 | 日本語 `.md` 原本、今回新設・実質変更した永続文書の `.en.md` | 既存 path を維持。SKILL.md／識別子／license／引用は一括翻訳しない。訳は別挙動定義ではない。source hash manifest は stale 検査であり翻訳品質の証明ではない。 |
| D10 | 破損 fixture の狙った失敗を回帰証拠にする | 成功回数だけを因果的な修正証拠にしない。 |

`agent-env` の Go runtime、製品依存、scheduler、全 Plan orchestration、自動 merge、課金基盤は移植しない。共通化は複数 repo の契約が安定したときに再検討する。

ユーザーの限定指示を優先し M1〜M4 だけ進める。M3 の smoke／native matrix 受入は、M6 の範囲と実行可能な環境を分け、未実施を pending と記録する。追加 Python parser は不要。
