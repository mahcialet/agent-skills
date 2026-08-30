# コーパスデータモデル

状態: implemented（schema v1とlocal state）

一つのrecordを一つのJSON fileに保存する。この形式なら、既存evalと同じくPython標準ライブラリで
検証できる。また、key順とindentを安定させることで、変更内容をdiffで追いやすくなる。
schemaはversionを持ち、unknown fieldを黙って捨てない。正規schemaは
`../schemas/corpus-record.schema.json` である。

## recordの役割

recordは、原文に正解labelを付けるためのものではない。provenance、観察、期待挙動、人間の判断を
分けて保存する。GitHubのapproval、RR annotation、rule proposalも同じfieldへまとめない。

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
| `embedded` | rightsとprivacyを確認したraw textをrecord内へ保存 |
| `redacted` | 明示したredactionを施したtextを保存 |
| `reference-only` | URL、immutable revision、path、hashだけを保存 |

匿名化やredactionだけで再配布可能になるとは扱わない。rightsがunknownの場合は
`reference-only` と `local_only: true` を既定にする。

## decision履歴

現在stateに加えて、candidate作成、annotation、accept、reject、promotionの履歴をaudit logへ
残す。acceptedとrejectedの双方を保持することで、却下された提案をnegative controlに利用できる。
rejectされたrecordは削除せず、判断根拠を残す。

## schema evolution

GitHub collectorが作るrecordは、互換性を保つoptionalな `github_evidence` を持つ。PRの
base／head／merge SHA、変更fileのblob SHA、review submissionのstateと対象SHA、inline threadの
path・line・reply数を構造化して保存する。account名やPR本文、patch、review/comment本文は
保存しない。`body_present` は本文の有無だけを示し、内容を含まない。

state変更には、pending journal、record、原子的に置き換えるaudit logを使う。audit commit前に
失敗した場合は旧stateへrollbackする。process停止によってpending journalが残った場合は、次回の
初期化時にaudit eventの有無を確認し、commitまたはrollbackの状態を回復する。store全体の
process間lockにより、duplicate判定、state変更、auditのread-modify-replaceを直列化する。

schema migrationは明示的なpreviewとbackupを要求する。新しいvalidatorが古いrecordを黙って
書き換えず、未対応version、破損record、unknown fieldを区別して報告する。

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
proposal IDはresult、rule diff、eval候補から生成するため、同じ内容の重複を検出できる。
artifactは上書きせず、修正版を別IDとして保存する。

bundleはrecord本文をcopyせず、参照するlocal recordのpathとcontent hashを持つ。読込み時には
record summary、correlation group、source analysis、readinessをlocal store上のrecordと再照合する。
外部編集によって内容が食い違ったartifactは拒否する。

regression planはproposal ID、exact diff hash、provider matrix、全caseを固定する。promoted corpusは
raw textをplanへ複製せず、record pathとcontent hashで参照する。runはprovider、model、version、
host、repeat indexを固定し、reportはplanと全runから再計算できる集約値を持つ。

approvalには、pass済みreportとexact diffに対する人間の判断を保存する。proposalとは別の
immutable artifactとし、proposalの `human_approval` fieldを後からtrueへ書き換えない。
apply時はproposal、report、approvalのIDとdiff hashを再照合する。
