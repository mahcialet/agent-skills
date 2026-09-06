# Templates and semantic merge

## Merge contract

Agentはbase、proposed、latestの意味を比較し、完了済み項目を未完了へ戻さず、他者の更新、Goal、
Constraints、受け入れ条件、意思決定、未解決事項を保持する。runtimeは次を決定的に検査する。

- markup別のsection境界と重複見出し。
- `edited_sections` 外の変更。
- section順序変更に必要な `__structure__` 宣言。
- Goal/目的/Constraints/制約の変更検出と、実反映時のcurrent revisionへの確認記録。
- base description hash、template ID/hash、予定payload hash。

曖昧なら全文置換や文字列置換で補完せずNEEDS_REVIEW/NEEDS_REMERGEへ止める。code block、table、list、
inline code、link、image、quote、provider固有macroを無関係なsectionで書き換えない。

## Snapshot

snapshotは本文の再要約ではなく更新後の構造化入力から生成する。goal、current_state、decisions、
constraints、progress、blockers、unresolved_issues、next_actions、verification_statusを必須とし、
change summary、固定時刻、opaque operation markerを付ける。`@` はzero-width spaceで中和し、意図しない
mention再発火を避ける。visibilityを確認できない内容は投稿しない。

## Built-in default

profileにtemplate IDがない場合の初期構造として、SkillはMarkdown、Textile、Backlog記法のdefaultを
`assets/default-ticket.*.txt`に同梱する。各variantはsnapshot contractと同じ9項目を同じ順序で持つ。
これはticket-state固有の`SNAPSHOT_FIELDS`とlabelから設計した配布assetであり、local corpusや特定の
Backlog/Redmine instanceから昇格したtemplateではない。

defaultは、profile templateがなく空のdescriptionを更新するときに使う。空ではないが定型構造のない
descriptionへ構造を追加するには、ユーザーの明示指示を必要とする。既存の見出し、preamble、provider
macro、自由記述をdefaultへ自動移行しない。profileに承認済みtemplateが設定されている場合はそちらを
優先し、欠落・ID不一致・hash不一致をdefault fallbackで迂回しない。

default適用時も`edited_sections`へ変更対象と`__structure__`を明示し、目的/制約の追加または変更には
previewを保存して、実反映前に具体的な変更への確認を記録する。廃止された`protected_change_approval`は
requestへ含めず、承認者名を要求しない。全placeholderは`未設定`から始め、推測で埋めない。
該当なしを確認できた項目だけ`なし`へ変更する。

このfallback ruleは人間が要求した汎用初期構造として追加した。再配布する見出し、順序、既定値、
適用条件の変更は挙動変更として、支持例・反例・境界例と明示的なhuman reviewを必要とする。

## Template lifecycle

`template extract` は明示targetだけを読み、見出し頻度・順序・例外・evidence hashをlocal candidateへ
保存する。1件だけならNEEDS_MORE_EVIDENCE、順序不整合ならNEEDS_REVIEWになる。candidateは自動で
approvedにならず、更新実行中のtemplateを切り替えない。

人間が候補と例外を確認し、用途とversionを判断した場合だけ `template approve` を実行する。approved
artifactはcandidate hash、approver、理由、時刻を持つ。local観察を人間のreviewなしにcore ruleや
再配布templateへ昇格しない。
