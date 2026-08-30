# コーパスデータモデル

状態: planned（未実装）

初版は、一record一fileのJSONを使用する計画である。既存evalと同様にPython標準ライブラリで
検証でき、安定したkey順とindentによりdiffを確認しやすいためである。schemaはversionを持ち、
unknown fieldを黙って捨てない。

## Recordの役割

recordは原文の正解labelではなく、provenance、観察、期待挙動、人間の判断を分離して保存する。
GitHubのapproval、RR annotation、rule proposalを同じfieldへまとめない。

## 必須情報

- `schema_version` とdeterministicな `id`
- `language`、`genre`、`reader`、翻訳文かどうか
- `sample_type`: `positive-reviewed`、`review-directed-revision`、
  `human-revision`、`rejected-suggestion`、`manual`
- `quality_class`: `problematic`、`clean`、`borderline`
- immutableなsource、取得日時、source内の相関を識別する情報
- authorshipとAI assistanceの既知・不明
- review signalと、その根拠
- rights status、raw text再配布可否、local-only、redaction
- raw text、reference-only、hashのどれで保存したか
- expected behavior、annotation rationale、semantic invariants、do-not-change constraints
- decision state、reviewer、日時、理由

unknownは推測で埋めず、許可されたenumの `unknown` または明示的なnullで保持する。

## Deterministic ID

IDは、正規化したsource identity、immutable revision、対象file・span、sample typeから生成する。
raw textだけをID材料にせず、同じsource recordの重複収集を検出できるようにする。hash algorithm、
canonicalization version、入力fieldをrecordへ残す。

同一PRや同一文書の複数spanは、独立したsource evidenceとして水増ししない。相関groupを保存し、
集計時にsource diversityとsample countを分ける。

## Text storage

`text.storage` は少なくとも次を区別する。

| 値 | 意味 |
|---|---|
| `embedded` | rightsとprivacyを確認したraw textをrecord内へ保存 |
| `redacted` | 明示したredactionを施したtextを保存 |
| `reference-only` | URL、immutable revision、path、hashだけを保存 |

匿名化やredactionだけで再配布可能になるとは扱わない。rightsがunknownの場合は
`reference-only` と `local_only: true` を既定にする。

## Decision history

現在stateだけでなく、candidate作成、annotation、accept、reject、promotionの履歴をaudit logへ
残す。acceptedとrejectedの双方を保持し、却下された提案をnegative controlに利用できるように
する。rejectされたrecordを削除して判断根拠を失わない。

## Schema evolution

schema migrationは明示的なpreviewとbackupを要求する。新しいvalidatorが古いrecordを黙って
書き換えず、未対応version、破損record、unknown fieldを区別して報告する。
