# ライセンスとプライバシー

状態: planned（未実装）

corpus recordはsourceのprovenanceと、raw textを保存・再配布できる権利を分離して記録する。
public repositoryであること、repositoryにlicenseがあること、textを匿名化したことだけでは、
PR本文やreview commentの再配布権限を確認済みと扱わない。

## 既定値

third-party sourceのrightsが未確認なら、次を既定にする。

```text
raw text: 保存しない
storage: reference-only
rights status: unknown
local only: true
public promotion: reject
```

URLだけでなくimmutable commit SHA、PR番号、file、取得日時、content hashを保存する。
source reputationやmerge済みという事実をlicenseまたはqualityの代わりにしない。

## 必須provenance

- source type、repository、PR・commit・file・span
- immutable revisionと取得日時
- authorship、AI assistance、review signal
- repository licenseとして観測した値と確認方法
- raw text、PR本文、review commentそれぞれのredistribution status
- local-only、public候補、redaction、改変の有無
- record作成者とannotationの由来

review commentの権利をrepository licenseから自動推定しない。licenseやrightsが混在する場合は、
content単位でstatusを分ける。

## Privacy

private repositoryや社内文書は既定で収集しない。明示指定されたlocal collectionでも、token、
secret、credential、個人情報を保存しない。raw textの保存前にredaction previewと保存先を示し、
利用者が確認できるようにする。

project-local dataは誤commitを避ける必要がある。toolはignore状態を確認するが、利用者の
`.gitignore` を無断で変更しない。unignoredなdirectoryへのwriteは警告または明示overrideを
要求する。

## Public promotion

publicなbundled corpusへ昇格するには、raw text再配布権限、attribution、NOTICE更新、sourceの
固定、review commentの扱い、third-party contentの分離を確認する。`unknown`、`unlicensed`、
`restricted` のrecordはpublic promotionを拒否する。

local-only recordはlocal evalへ利用できるが、repositoryのfixture、investigation bundle、
reportへraw textを転載しない。権利確認後にstatusを変更する場合もaudit logを残す。
