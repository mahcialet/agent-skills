# Behavior Profile format 0.1

この文書は、このrepositoryで扱うBehavior Profile packageのcanonical形式を定める。
PoCのschema自体も `experimental` であり、上位互換性はまだ保証しない。

## Package layout

各Profileは `behavior-profiles/<name>/` に置き、最低限次を含める。

```text
<name>/
├── BEHAVIOR_PROFILE.md
├── README.md
├── NOTICE.md
└── evals/
    └── pressure-tests.json
```

Profile固有のreport templateを追加してよい。実行時に読む補助fileはProfile directory内に
収める。空directoryをplaceholderで保持しない。

## Frontmatter

`BEHAVIOR_PROFILE.md` はUTF-8 Markdownで、file先頭にYAML frontmatterを置く。
PoC validatorが受理するのは単純な一行scalarだけである。

```yaml
---
name: example-profile
version: 0.1.0
description: Agentのconductを一文で説明する
status: experimental
license: MIT
---
```

必須keyは `name`、`version`、`description`、`status`、`license` である。

- `name` はdirectory名と一致するlowercase kebab-caseとする。
- `version` はSemVer形式とし、behavior contractのrevisionを識別する。
- `description` は空にしない。
- PoCで許可する `status` は `experimental` のみである。
- `license` は適用licenseのSPDX identifierを記載する。
- 未知keyやProvider固有metadataをcanonical profileへ追加しない。

## Required sections

Frontmatter後には、次のlevel-2 headingをこの順序で一度ずつ置く。Validatorはheadingを
section構造として検査し、本文中に語彙だけが現れても合格にしない。

1. `## Identity`
2. `## Failure addressed`
3. `## Expected conduct`
4. `## Installation location`
5. `## Observable expectations`
6. `## Pressure test`
7. `## Completion evidence`
8. `## Bypass`
9. `## Limitations`

各sectionは空にせず、規範的な挙動と観測可能な境界を日本語で記述する。見出し名、schema
key、CLI flag、file名は識別子なので英語のまま保持する。

## Links and local paths

Markdownの相対linkはProfile directoryまたはrepository内の実在pathを指す必要がある。
絶対filesystem path、`file:` URL、repository root外へのdirectory escapeは禁止する。
External HTTPS linkは出典表示に使用できるが、validatorは到達性を保証しない。

## Pressure-test fixture

`evals/pressure-tests.json` はJSON objectで、`schema_version`、`profile`、`fixtures` を持つ。
`profile` はcanonical frontmatterと一致する `name`、`version`、`status` を持つobjectである。
各fixtureには最低限次のkeyを置く。

- `id`
- `purpose`
- `operation_mode`
- `prompt`
- `fixture_path`
- `preconditions`
- `allowed_actions`
- `allowed_tools`
- `prohibited_actions`
- `expected_report_destination`（`type` と、明示pathまたは `null` の `path` を持つobject）
- `expected_observables`
- `expected_reviewer_writes`
- `expected_implementer_writes`
- `expected_stop_point`
- `expected_authorization_state`
- `classification_rule`
- `limitations`

Promptをinlineで持つ場合の `fixture_path`、外部fixtureを使う場合の `prompt` は `null` に
できる。ただし両方を同時に `null` にしてはならない。`classification_rule` は
`PASS`、`FAIL`、`CONFUSED` の条件を明示する。Synthetic pressure testはbehavior contractを
検査する入力であり、それ自体は実Agent episode evidenceではない。

## Evidence record

実episodeは [`EVIDENCE_TEMPLATE.json`](EVIDENCE_TEMPLATE.json) の項目を埋め、host、
version、model、profile content hash、権限、観測されたwrite、判定、limitationsを残す。
Profile content hashはcanonical `BEHAVIOR_PROFILE.md` bytesのSHA-256とする。

次のartifactを区別する。

- reviewerが明示pathへ作ったreport file
- authorized implementerが変更したsource/test file
- installerが変更したinstruction surface
- test/buildが生成した副作用

Evidenceへsecret、token、private repository content、hidden instructionを保存しない。
Review reportのdecision語彙 `PASS` / `FAIL` / `INCONCLUSIVE` と、episode classificationの
`PASS` / `FAIL` / `CONFUSED` は別概念として扱う。

## Change control

Behavior contractを変更する場合は、支持例、反例、境界例、既存fixtureの回帰確認、出典と
来歴の確認、人間による明示reviewを必要とする。Local corpusの観察だけを未reviewのまま
core ruleへ昇格しない。Catalogのversionと実体も同時に更新する。
