# ライセンスとプライバシー

状態: 一部implemented（local schema・rights validationとpublic GitHub reference-only収集を実装済み。
機密情報検出とredaction previewは未実装）

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
planned public promotion: reject
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
- repository licenseとして観測した値と確認方法。確認方法は `rights.notes` に記録し、GitHub
  collectorはGitHub REST APIのrepository metadataから取得したことを明記する。schemaとcustom
  validatorは、`repository_license` が非nullの場合に空でない `rights.notes` を要求する
- raw text、PR本文、review commentそれぞれのredistribution status
- local-only、public候補、redaction、改変の有無
- record作成者とannotationの由来

review commentの権利をrepository licenseから自動推定しない。licenseやrightsが混在する場合は、
content単位でstatusを分ける。

## Privacy

GitHub collectorはprivate repositoryを収集しない。一方、public repository内の文書が社内向けか、
機密情報を含むかは判定しない。reference-only recordにもpath、SHAなどのmetadataは保存する。
manualなlocal collectionは、利用者が明示したJSON recordを保存する機能であり、token、secret、
credential、個人情報を自動検出・削除しない。`corpus collect --dry-run` はschema・rights制約を
検証し、record IDと保存先を示すが、redaction previewは生成しない。利用者は保存前にraw textを
確認し、機密情報と不要な個人情報を削除またはredactする。

project-local dataは、誤ってcommitされないように保護する必要がある。toolはignore状態を確認するが、
利用者の `.gitignore` は無断で変更しない。unignoredなdirectoryへのwriteを拒否し、
明示overrideがある場合だけ続行する。

## Public promotion（planned policy・未実装）

public promotionのCLIとruntime gateは未実装である。将来実装する場合は、publicなbundled corpusへ
昇格する前に、raw text再配布権限、attribution、NOTICE更新、sourceの固定、review commentの扱い、
third-party contentの分離を確認する。rights statusが `unknown`、`unlicensed`、`restricted` のrecordを
拒否するpolicyとする。

local-only recordはlocal evalへ利用できる。ただし、repositoryのfixture、investigation bundle、
reportへraw textを転載しない。権利確認後にstatusを変更する場合もaudit logを残す。
