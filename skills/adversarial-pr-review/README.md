# Adversarial PR Review

`adversarial-pr-review` は、PR、diff、branch、commit、staged changes、working treeを
reviewするSkillです。差分に加えて関連する実装、設定、testなども調べ、変更によって起こり得る
問題を根拠とともに報告します。正常利用だけを確認するか、権限内の濫用や境界突破まで想定するかは、
A0〜A4で指定できます。

主な機能は次のとおりです。

- review対象と比較元を指定して、変更の問題点と根拠を確認する
- 想定する敵対的な使い方をA0〜A4、調査の深さを `focused` / `standard` / `deep` で指定する
- 通常のreviewに加え、`BLOCK` / `CONDITIONAL` / `PASS` を返すgate判定を行う
- findingを既存checklistと比較し、追加・更新・重複・却下の候補に分類する

## 既定の動作

既定値は `level=auto`、`minimum=A1`、`depth=standard`、`mode=review` です。
`mode=review` はread-onlyで、見つかった問題を報告するだけです。`mode=gate` もreport-onlyで、
判定として `BLOCK` / `CONDITIONAL` / `PASS` を返します。どちらのmodeでも、GitHub上のreview、
status、label、mergeは変更しません。

## 明示起動

Codex:

```text
$adversarial-pr-review Review the current branch against master with level=auto, depth=standard, and mode=review.
```

```text
$adversarial-pr-review PR #123をminimum=A2、depth=deep、mode=gateでレビューしてください。
```

Copilot CLI:

```text
/adversarial-pr-review Review PR #123 with level=A3, depth=deep, and mode=gate.
```

```text
/adversarial-pr-review staged changesをminimum=A2でレビューし、並列実行、再送、順序操作を重点確認してください。
```

明示した `level` はreview範囲の上限です。たとえば次の指定ではA0〜A2を確認します。
A3以上に当たる兆候はreview範囲外の脅威として扱い、残余リスクに分けて示します。

```text
$adversarial-pr-review PR #123をlevel=A2でレビューし、A3以上のtriggerは残余リスクとして列挙してください。
```

findingを既存checklistと比較する場合は、次のように指定します。

```text
$adversarial-pr-review F-001とF-003を既存review-checklist.mdと比較し、new / update / duplicate / rejectに分類してください。
```

この操作でも、checklist候補と分類結果だけをreportします。明示的な編集依頼なしにchecklistを
変更しません。

<a id="敵対性level"></a>

## 確認する脅威の範囲

| level | 確認する範囲 |
|---|---|
| A0 | 正常利用と要件適合 |
| A1 | 境界、timeout、retry、部分障害、偶発的重複 |
| A2 | race、replay、順序、quota、cost等の正規権限内の濫用 |
| A3 | authorization、tenant、injection、forged callback等の境界突破 |
| A4 | dependency、CI/CD、operator、privileged worker等の侵害前提 |

根拠をどこまで追うかは、確認する脅威の範囲とは別に `focused` / `standard` / `deep` から選びます。
priority `P0`〜`P3`、adversarial level、confidenceも、それぞれを分けて報告します。

## 安全境界

PR本文、Issue、code comment、fixture、test、generated file、head側で変更されたinstructionに
命令が書かれていても、その命令には従いません。review対象のdataとして扱います。
変更済みrunnerやhookは、内容を確認せずに実行しません。また、deploy、publish、notification、
production、billing、外部送信、永続data変更を伴う検証も行いません。

findingが0件でも安全を保証しません。結果には、確認したscope、実行しなかった検証とその理由、
残っているリスクを示します。
出力はユーザーが使用した言語を優先し、指定が不明な場合は日本語を既定にします。

## ポータビリティ

CodexとGitHub Copilot CLIは、共通のレビュー手順を記した同じ `SKILL.md` を使います。
`agents/openai.yaml` にあるのは、Codex向けUI metadataと暗黙起動を禁止する設定だけです。
Skillディレクトリ全体を `.agents/skills/adversarial-pr-review` へ配置してください。
このモノレポから利用する場合は、root repositoryのインストール手順も参照できます。

This is an independent review aid, not a penetration test, formal verification,
security certification, or guarantee. See [NOTICE.md](NOTICE.md) for attribution.
