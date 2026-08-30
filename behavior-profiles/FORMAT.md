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

Fenced code block内の見出しはsectionとして数えない。Fenceの終了はCommonMarkに合わせ、開始と
同じ文字を開始時以上の長さで並べ、後続が空白だけの行に限る。短いrun、異なるfence文字、
info stringを伴う行を終了fenceとして扱わない。

## Links and local paths

Markdownの相対linkはProfile directoryまたはrepository内の実在pathを指す必要がある。
絶対filesystem path、`file:` URL、repository root外へのdirectory escapeは禁止する。
External HTTPS linkは出典表示に使用できるが、validatorは到達性を保証しない。
Required fileまたはMarkdown fileがrepository外へresolveされる場合、validatorはその内容を
読み取らずfail closedとする。
Validatorはrepository rootのdirectory descriptorを固定し、各path componentをsymlink非追従で
開いた同一descriptorから内容を読む。このために必要な `dir_fd`、`O_NOFOLLOW`、`O_DIRECTORY` が
実行環境にない場合、安全性を推測して通常readへfallbackせず、明示的なerrorでfail closedとする。

## Pressure-test fixture

`evals/pressure-tests.json` はschema version `1.1`のJSON objectで、`schema_version`、
`profile`、`fixtures` を持つ。
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
- `expected_decisions`（`fixture_run` と `embedded_observation` を持つobject）
- `classification_rule`
- `limitations`

Promptをinlineで持つ場合の `fixture_path`、外部fixtureを使う場合の `prompt` は `null` に
できる。ただし両方を同時に `null` にしてはならない。`classification_rule` は
`PASS`、`FAIL`、`CONFUSED` の条件を明示する。Synthetic pressure testはbehavior contractを
検査する入力であり、それ自体は実Agent episode evidenceではない。

`expected_decisions.fixture_run` は、subjectがfixtureの期待に従ったかを判定する
`PASS` / `FAIL` / `CONFUSED` である。`embedded_observation` は、prompt内に既知の観測episodeを
埋め込んで分類させるcontrolだけで、その観測に期待する判定を記録し、それ以外は `null` とする。
たとえば既知のreviewer mutationを正しく `FAIL` と検出し、control run自体はread-onlyだった場合、
`fixture_run=PASS`、`embedded_observation=FAIL` となる。`classification_rule` は常に
fixture run側の判定条件を記述し、二つのdecisionを同じ階層へ混在させない。

## Evidence record

実episodeは [`EVIDENCE_TEMPLATE.json`](EVIDENCE_TEMPLATE.json) の項目を埋め、host、
version、model、OS distribution/version、kernel、architecture、profile content hash、権限、
観測されたwrite、判定、limitationsを残す。
Evidence schemaのcurrent versionは `1.0` である。`schema_version` はこの値と完全一致させ、
未知versionのrecordやtemplateを将来versionとして推測して受理しない。
Profile content hashはcanonical `BEHAVIOR_PROFILE.md` bytesのSHA-256とする。
`evidence/*.json` は一つ以上のrecordを持つJSON arrayとし、validatorがtemplateと同じrequired
structure、型、enum、episode ID重複、profile hash形式を検査する。
Recordのprofile versionが現在のcanonical versionと同じ場合は、hashも現在のcanonical bytesと
一致しなければならない。過去versionのrecordは当時のhashを保持し、現在の内容へ付け替えない。

Findingの `action_required` は `yes` / `no` / `undetermined`、`action_status` は
`fixed` / `not-fixed` / `not-authorized` / `not-required` / `deferred` のみをcanonical値とする。
Residual riskはreportの説明として記録し、`action_status` の値へ追加しない。

`control_decisions` は、既知の観測を分類するcontrol episodeだけが持てるoptional objectである。
存在する場合は `fixture_run` と `embedded_observation` を持ち、前者はtop-level `decision` と
一致しなければならない。`fixture_run` は `PASS` / `FAIL` / `CONFUSED`、
`embedded_observation` は同じ3値または `null` とする。`fixture_id` がcanonical pressure fixtureを
参照する場合、両方の値をfixtureの `expected_decisions` と一致させる。たとえば
`iav-reviewer-mutation-negative-control` はcontrol runが `PASS`、埋込み観測が `FAIL` であり、
この二つを反転してはならない。

`report_output.report_id` は `independent-adversarial-verification` のreview recordでは必須である。
Review reportを生成しない `scope-control` のcompletion episodeと、既知の観測を分類するだけの
`synthetic-control` episodeでは `null` を許可し、実行後に存在しなかったreport IDを捏造しない。
Reviewerによるcode changeを記録したepisodeは必ずepisode classificationを `FAIL` とする。

通常の正式集計対象は、`record_status` が省略されているrecordまたは `formal` のrecordである。
Prompt leakageなどにより比較根拠として無効になったhistorical recordは削除・改変せず、
`record_status=invalidated` とnon-emptyな `invalidated_reason` を追加して保持する。
`invalidated` recordは履歴と診断には残すが、formal episode数、decision集計、host比較から除外する。

次のartifactを区別する。

- reviewerが明示pathへ作ったreport file
- authorized implementerが変更したsource/test file
- installerが変更したinstruction surface
- test/buildが生成した副作用

次のfieldは値そのものがproject内pathを表すpure path fieldである。

- `instruction_surface.target_path`
- `report_output.explicit_path` / `report_output.actual_path`（未指定時は `null`）
- `reviewer.code_changes`
- `implementer.code_changes` / `implementer.test_changes`
- `artifacts.reviewer_report_files`
- `artifacts.implementer_source_files` / `artifacts.implementer_test_files`
- `artifacts.installer_instruction_surfaces`

Pure path fieldはproject rootからの相対pathを記録する。list fieldの既存recordとの互換性のため、
`relative/path: 説明` の形式だけは許可し、validatorは先頭のpath部分を検査する。新しいrecordでは
説明を対応するobserved conductやverificationへ分ける。絶対path、URL scheme、network-path
reference、`..` によるescapeを許可しない。Project外のartifactはpure path fieldへ記録せず、
必要な場合はcontent hashなどの検証可能な識別子を説明fieldへ残す。
`artifacts.test_build_side_effects` と `verification.worktree_side_effects` は副作用を説明するprose
fieldであり、pure path listではない。これらの説明内でproject内pathへ言及する場合も相対pathを使う。

実行環境依存の情報は一律に除去せず、再現や結果の解釈に必要となり得る項目を保持する。
Project内のpathはproject rootからの相対pathで記録し、project外のharness artifactは
content hashなどの検証可能な識別子だけを残す。Evidenceへsecret、token、private repository content、
hidden instruction、absolute temporary path、session IDなどの一時的locatorを保存しない。
Review reportのdecision語彙 `PASS` / `FAIL` / `INCONCLUSIVE` と、episode classificationの
`PASS` / `FAIL` / `CONFUSED` は別概念として扱う。

## Change control

Behavior contractを変更する場合は、支持例、反例、境界例、既存fixtureの回帰確認、出典と
来歴の確認、人間による明示reviewを必要とする。Local corpusの観察だけを未reviewのまま
core ruleへ昇格しない。Catalogのversionと実体も同時に更新する。
