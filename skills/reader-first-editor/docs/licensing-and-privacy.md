# ライセンスとプライバシー

状態: 一部implemented（local validationとpublic GitHub reference-only収集を実装済み）

corpus recordでは、sourceのprovenanceと、raw textを保存・再配布できる権利を別々に記録する。
public repositoryであること、repositoryにlicenseがあること、textを匿名化したことだけを根拠に、
PR本文やreview commentを再配布できるとは判断しない。

## 既定値

third-party sourceのrightsが未確認なら、次を既定にする。

```text
raw text: 保存しない
storage: reference-only
rights status: unknown
local only: true
public promotion: reject
```

URLに加えて、immutable commit SHA、PR番号、file、取得日時、content hashを保存する。
source reputationやmerge済みという事実を、licenseまたはqualityの証明として使わない。

GitHub collectorはrepository licenseのSPDX IDを観測値として保存する。ただし、この値だけを根拠に
PR本文、patch、review commentの権利を確認済みとは扱わない。live responseからは本文fieldを
破棄する。recorded fixtureにraw text fieldが含まれる場合も拒否する。account名は保存せず、
human／bot／unknownの種別だけを残す。

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

private repositoryや社内文書は既定では収集しない。明示指定されたlocal collectionでも、token、
secret、credential、個人情報を保存しない。raw textを保存する前にredaction previewと保存先を示し、
利用者が内容と保存場所を確認できるようにする。

project-local dataは、誤ってcommitされないように保護する必要がある。toolはignore状態を確認するが、
利用者の `.gitignore` は無断で変更しない。unignoredなdirectoryへのwriteを拒否し、
明示overrideがある場合だけ続行する。

## Public promotion

publicなbundled corpusへ昇格する前に、raw text再配布権限、attribution、NOTICE更新、sourceの
固定、review commentの扱い、third-party contentの分離を確認する。rights statusが `unknown`、`unlicensed`、
`restricted` のrecordはpublic promotionを拒否する。

local-only recordはlocal evalへ利用できる。ただし、repositoryのfixture、investigation bundle、
reportへraw textを転載しない。権利確認後にstatusを変更する場合もaudit logを残す。
