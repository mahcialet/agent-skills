# 長文のcoverage-driven review例

## 対象

複数章からなる運用手順をreviewする。前半には用語揺れ、単位前の空白、表内の英語表記があり、
後半には次の文がある。

> `config/base.yaml`を正本とする。

## 処理

見出し単位でinventoryを作り、各chunkを局所確認する。前半で3件を見つけても終了せず、後半の
「正本」をscanner candidateとして記録する。その後、全chunkを使うglobal passで用語、定義、
モダリティ、関係の省略、局所整合性を確認する。

「正本」は禁止語ではない。周囲に直接編集対象、生成方向、不一致時の優先先などの説明がないため、
この例では一つの関係を推測せず、読者が何を判断できないかをfindingとして報告する。

## coverage summaryの例

| 確認観点 | 状態 | candidates | findings | excluded | unresolved | 未確認範囲 |
|---|---:|---:|---:|---:|---:|---|
| semantic preservation | checked | 0 | 0 | 0 | 0 | なし |
| 情報構造 | checked | 1 | 1 | 0 | 0 | なし |
| 構文・読み返しリスク | checked | 1 | 1 | 0 | 0 | なし |
| 関係の省略 | checked | 1 | 1 | 0 | 0 | なし |
| モダリティとscope | checked | 0 | 0 | 0 | 0 | なし |
| 局所整合性 | checked | 1 | 1 | 0 | 0 | なし |
| repository整合性 | not-checked | 0 | 0 | 0 | 0 | 通常reviewのため未実施 |

0件の観点も `checked` として残す。通常reviewで依頼されていないrepository照合は0件とせず、
`not-checked` と理由を示す。

## findingの例

```text
[MEDIUM]
対象: 第5節「管理するファイル」

問題:
`config/base.yaml`を「正本」としていますが、直接編集するfile、生成元、内容が異なる場合の
優先先のどれを示すか、周囲の文から確定できません。

読者への影響:
運用担当者は、どのfileを変更し、食い違いがある場合にどれを採用するかを別の資料から
推測する必要があります。

改善方針:
実際の関係を確認し、必要な関係を直接記述してください。一つの意味を推測して補いません。
```

人向け出力を短くする場合も、全candidate、分類、locationをmachine-readable reportに保持する。
machine-readable reportのseverityは `HIGH`、`MEDIUM`、`LOW` のいずれかとする。
`CRITICAL` などの未定義値やseverityの欠落はvalidatorで拒否する。
validatorはrootの必須fieldと未知fieldも確認し、integer fieldの `true`／`false` を数値として
受理しない。
