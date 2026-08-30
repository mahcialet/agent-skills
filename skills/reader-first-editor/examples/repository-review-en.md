# 英語文書のrepository-review例

英語の対象文書には英語で結果を返す。次の例では、外部citationが記載されていることと、
リンク先の内容を確認したことを区別し、読者が確認済みの範囲を判断できるようにする。

## Target

> This approach is recommended by Example Cloud.
> Source: `https://example.com/cloud-guidance`

## repository-review

```text
[CITATION][SUPPORTED-BY-CITATION][MEDIUM]
Claim: The document says that Example Cloud recommends this approach.
Evidence: The document provides https://example.com/cloud-guidance as an
external citation. The linked content was not retrieved or independently checked.
Gap: The repository shows that a citation is present, but it does not verify that
the source supports the claim or remains current.
Reader impact: Readers may interpret the recommendation as independently verified.
Suggested action: Verify the cited source separately, or qualify the statement to
make the verification boundary clear.

Reviewed scope: the target document and its repository-local references
Not performed: external URL retrieval or open-world fact checking
```

モデル知識を根拠に `VERIFIED` へ変更しない。対象fileも変更しない。
