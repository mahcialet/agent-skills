# リポジトリ内の証拠に基づく校閲例

## 対象

`README.md`:

> 機能は既定で有効です。

`config/defaults.yaml`:

```yaml
enabled: false
```

## repository-review

```text
[DOC↔CONFIG][CONTRADICTED][HIGH]
対象claim: README.mdは、機能が既定で有効だと説明しています。
証拠: config/defaults.yamlでは、enabledの既定値がfalseです。
不一致・不足: 文書と設定の既定値が一致していません。どちらがsource of truthかを
判断できる宣言は、確認した範囲では見つかりませんでした。
読者への影響: 利用者が機能の有効化状態を誤認する可能性があります。
修正案・追加確認: 期待する既定値を確認し、README.mdまたは設定を更新してください。

確認scope: README.md、config/defaults.yaml
未実施検証: runtimeでの起動確認。校閲依頼は実行権限を含まないため実施していません。
```

設定を無条件に正しいとみなさず、具体的な矛盾と追加確認事項を示す。対象fileは変更しない。

## 外部citationがある場合

> この方式はAWSの推奨方式です（根拠: `https://example.com/aws-doc`）。

URL先を確認していない通常の `repository-review` では、判定を
`SUPPORTED-BY-CITATION` とする。確認できたのはcitationの存在だけであり、AWSが
実際に推奨しているとは断定しない。
