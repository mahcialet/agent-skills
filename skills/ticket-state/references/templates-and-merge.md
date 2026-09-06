# Templates and semantic merge

## Merge contract

Agentはbase、proposed、latestの意味を比較し、完了済み項目を未完了へ戻さず、他者の更新、Goal、
Constraints、受け入れ条件、意思決定、未解決事項を保持する。runtimeは次を決定的に検査する。

- markup別のsection境界と重複見出し。
- `edited_sections` 外の変更。
- section順序変更に必要な `__structure__` 宣言。
- Goal/目的/Constraints/制約の変更に必要なhuman review情報。
- base description hash、template ID/hash、予定payload hash。

曖昧なら全文置換や文字列置換で補完せずNEEDS_REVIEW/NEEDS_REMERGEへ止める。code block、table、list、
inline code、link、image、quote、provider固有macroを無関係なsectionで書き換えない。

## Snapshot

snapshotは本文の再要約ではなく更新後の構造化入力から生成する。goal、current_state、decisions、
constraints、progress、blockers、unresolved_issues、next_actions、verification_statusを必須とし、
change summary、固定時刻、opaque operation markerを付ける。`@` はzero-width spaceで中和し、意図しない
mention再発火を避ける。visibilityを確認できない内容は投稿しない。

## Template lifecycle

`template extract` は明示targetだけを読み、見出し頻度・順序・例外・evidence hashをlocal candidateへ
保存する。1件だけならNEEDS_MORE_EVIDENCE、順序不整合ならNEEDS_REVIEWになる。candidateは自動で
approvedにならず、更新実行中のtemplateを切り替えない。

人間が候補と例外を確認し、用途とversionを判断した場合だけ `template approve` を実行する。approved
artifactはcandidate hash、approver、理由、時刻を持つ。local観察を人間のreviewなしにcore ruleや
再配布templateへ昇格しない。
