# コーパスデータモデル

状態: implemented（schema v1とlocal state）

一record一fileのJSONを使用する。既存evalと同様にPython標準ライブラリで検証でき、安定した
key順とindentによりdiffを確認しやすいためである。schemaはversionを持ち、unknown fieldを
黙って捨てない。正規schemaは `../schemas/corpus-record.schema.json` である。

## Recordの役割

recordは原文の正解labelではなく、provenance、観察、期待挙動、人間の判断を分離して保存する。
GitHubのapproval、RR annotation、rule proposalを同じfieldへまとめない。

## 必須情報

- `schema_version` とdeterministicな `id`
- ID生成algorithm、canonicalization version、入力field
- `language`、`genre`、`reader`、翻訳文かどうか
- `sample_type`: `positive-reviewed`、`review-directed-revision`、
  `human-revision`、`rejected-suggestion`、`manual`
- `quality_class`: `problematic`、`clean`、`borderline`
- immutableなsource、取得日時、source内の相関を識別する情報
- authorshipとAI assistanceの既知・不明
- review signalと、その根拠
- rights status、raw text再配布可否、local-only、匿名化・redaction・変更の有無
- raw text、reference-only、hashのどれで保存したか
- expected behavior、annotation rationale、semantic invariants、do-not-change constraints
- decision state、reviewer、日時、理由

unknownは推測で埋めず、許可されたenumの `unknown` または明示的なnullで保持する。

## Deterministic ID

IDは、正規化したsource identity、immutable revision、対象file・span、sample typeから生成する。
raw textだけをID材料にせず、同じsource recordの重複収集を検出できるようにする。hash algorithm、
canonicalization version、入力fieldをrecordへ残す。recordの読込み時にもIDを再計算し、外部編集で
source identityとIDがずれたrecordを拒否する。

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

GitHub collectorが作るrecordは、互換性を保つoptionalな `github_evidence` を持つ。PRの
base／head／merge SHA、変更fileのblob SHA、review submissionのstateと対象SHA、inline threadの
path・line・reply数を構造化して保存する。account名やPR本文、patch、review/comment本文は
保存しない。`body_present` は本文の有無だけを示し、内容を含まない。

state変更はpending journal、record、原子的に置き換えるaudit logを使う。audit commit前の
失敗は旧stateへrollbackし、process停止でpending journalが残った場合は次回初期化時に
audit eventの有無からcommitまたはrollbackを回復する。store全体のprocess間lockにより、
duplicate判定、state変更、auditのread-modify-replaceを直列化する。

schema migrationは明示的なpreviewとbackupを要求する。新しいvalidatorが古いrecordを黙って
書き換えず、未対応version、破損record、unknown fieldを区別して報告する。

## Investigation artifact

corpus recordとは別に、次のdeterministic IDを持つimmutableなlocal artifactを保存する。

```text
rfb-...  investigation bundle
rfi-...  Agentのinvestigation result
rfp-...  rule proposal draft
rfrp-... regression plan
rfrr-... regression run
rfrt-... regression report
rfa-...  human rule approval
```

bundle IDはhypothesis、scope、support／control record IDから生成する。result IDはAgent output、
proposal IDはresult、rule diff、eval候補から生成し、同じ内容の重複を検出する。artifactは
上書きせず、修正版は別IDとして保存する。

bundleはrecord本文をcopyせず、authoritativeなlocal record pathとcontent hashを持つ。読込み時に
record summary、correlation group、source analysis、readinessをlocal storeと再照合し、外部編集で
食い違ったartifactを拒否する。

regression planはproposal ID、exact diff hash、provider matrix、全caseを固定する。promoted corpusは
raw textをplanへ複製せず、record pathとcontent hashで参照する。runはprovider、model、version、
host、repeat indexを固定し、reportはplanと全runから再計算できる集約値を持つ。

approvalはpass済みreportとexact diffに対する人間の判断を、proposalとは別のimmutable artifactへ
保存する。proposalの `human_approval` fieldを後からtrueへ書き換えない。apply時はproposal、report、
approvalのIDとdiff hashを再照合する。
