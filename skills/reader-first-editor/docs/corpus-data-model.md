# コーパスデータモデル

状態: implemented（schema v1とlocal stateを実装済み）

一つのrecordは、一つのJSON fileとして保存する。この形式は既存evalと同じくPython標準ライブラリで
検証でき、key順とindentを安定させれば変更内容もdiffで追いやすい。
schemaはversionを持ち、unknown fieldを黙って捨てない。recordの形式を定義するschemaは
`../schemas/corpus-record.schema.json` である。

## recordの役割

recordは、原文に正解labelを付けるためのものではない。provenance、観察、期待挙動、人間の判断を
分けて保存する。GitHubのapproval、RR annotation、rule proposalも一つのfieldへまとめない。

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
- rights status、raw text再配布可否、local-only、匿名化・redaction・変更の有無。repository
  licenseの値がある場合は、取得・確認方法を空でない `rights.notes` に記録する。schemaとcustom
  validatorの両方がこの条件を検証する
- raw text、reference-only、hashのどれで保存したか
- expected behavior、annotation rationale、semantic invariants、do-not-change constraints
- decision state、reviewer、日時、理由

unknownは推測で埋めず、許可されたenumの `unknown` または明示的なnullで保持する。

## deterministic ID

IDは、正規化したsource identity、immutable revision、対象file・span、sample typeから生成する。
raw textだけを材料にしないため、同じsource recordを重複して収集した場合に検出できる。
hash algorithm、canonicalization version、入力fieldはrecordへ残す。recordの読込み時にもIDを
再計算し、外部編集によってsource identityとIDがずれたrecordを拒否する。

同一PRや同一文書の複数spanを、独立したsource evidenceとして数えない。相関groupを保存し、
集計ではsource diversityとsample countを分ける。

## textの保存形式

`text.storage` は少なくとも次を区別する。

| 値 | 意味 |
|---|---|
| `embedded` | raw textをrecord内へ保存。rightsとprivacyの確認状態は `rights` と `handling` で別に記録 |
| `redacted` | 明示したredactionを施したtextを保存 |
| `reference-only` | raw textを保存せず、利用可能なsource参照metadataとhashを保存。manual sourceではURLやpathがnullの場合もある |

匿名化やredactionを行っただけでは、再配布可能とはみなさない。rightsがunknownの場合は
GitHub collectorが `reference-only` と `local_only: true` を設定する。manual collectionは
`embedded` を含むcaller-supplied recordを自動変換しないため、利用者がrightsとprivacyを確認する。

## decision履歴

現在のstateに加えて、candidate作成、annotation、accept、reject、promotionの履歴をaudit logへ
残す。acceptedとrejectedの双方を保持するため、却下された提案もnegative controlに利用できる。
rejectされたrecordは削除せず、判断根拠を残す。

## schema evolution

GitHub collectorが作るrecordは、互換性を保つoptionalな `github_evidence` を持つ。PRの
base／head／merge SHA、変更fileのblob SHA、review submissionのstateと対象SHA、inline threadの
path・line・reply数を構造化して保存する。thread集約はparent commentがreplyより先に並ぶ入力を
前提とし、並び替えは行わない。source repositoryのowner/nameは保存するが、PR author、reviewer、
commenterのaccount名やPR本文、patch、review/comment本文は保存しない。`body_present` は本文の
有無だけを示し、内容を含まない。

state変更には、pending journal、record、原子的に置き換えるaudit logを使う。audit commit前に
失敗した場合は旧stateへrollbackする。process停止によってpending journalが残った場合は、次回の
初期化時にaudit eventの有無を確認し、commitまたはrollbackが完了した状態へ回復する。store全体の
process間lockにより、duplicate判定、state変更、auditのread-modify-replaceを直列化する。

schema migrationのCLI、preview、backupは未実装である。将来実装するmigrationでは明示的なpreviewと
backupを要求し、新しいvalidatorが古いrecordを黙って書き換えない方針とする。現行validatorは、
未対応version、破損record、unknown fieldを区別して報告する。

## 調査artifact

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
proposal IDはresult、rule diff、eval候補から生成し、同じID materialの重複を検出する。
ここでimmutableとは、toolが同じ保存pathを上書きしないwrite-once契約を指す。修正がartifactごとに
定義されたID materialを変える場合は別IDになるが、全fieldがID materialに含まれるわけではない。
たとえばproposalのhypothesisだけを変更してもproposal IDは変わらず、同じpathへの保存は拒否される。
外部編集を暗号学的に防止する契約ではない。

bundleはrecord本文をcopyせず、参照するlocal recordのpathとcontent hashを持つ。読み込むときは、
record summary、correlation group、source analysis、readinessをlocal store上のrecordと再照合する。
再照合した値が食い違うartifactは拒否する。ただし、bundleのcustom validatorはnested fieldに対する
JSON Schemaの全型制約と双方向同値ではない。たとえば、sourceが1件の場合、外部編集された
`source_analysis.independent_sources: true` はPythonの等値比較で `1` と同値になり、現行の再照合を
通過する。schema適合性を独立に保証するgateとして扱わない。

regression planはproposal ID、exact diff hash、provider matrix、全caseを固定する。callerが
`--corpus-record` で選んだpromoted recordは、raw textをplanへ複製せず、record pathとcontent hashで
参照する。planはpromoted record全件を自動選択しない。runはprovider、model、version、host、
repeat indexを固定し、reportはplanと全runから再計算できる集約値を持つ。

approvalには、pass済みreportとexact diffに対するcaller-suppliedなreviewer attestationを保存する。
toolはreviewerが人間かを認証しないため、人間によるreviewはtool外の運用責任である。approvalは
proposalとは別のimmutable artifactとし、proposalの `human_approval` fieldを後からtrueへ書き換えない。
apply時はproposal、report、approvalのIDとdiff hashを再照合する。
