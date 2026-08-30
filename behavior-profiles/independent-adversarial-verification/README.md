# Independent Adversarial Verification

`independent-adversarial-verification` は、実装者とは別のreviewerが反証指向で確認し、
reviewerのread-only境界とimplementerの限定されたwrite authorityを分離する実験的な
Behavior Profileです。canonicalな規約は[BEHAVIOR_PROFILE.md](BEHAVIOR_PROFILE.md)です。

このprofileはreview Skillではありません。必要に応じて既存の `adversarial-pr-review` を
推奨capabilityとして利用できますが、hard dependencyではありません。profileをinstallしなくても、
既存Skillは単独で利用できます。

## 3つのoperation mode

### `review-only`

reviewerがread-onlyで確認し、consoleまたは明示されたpathへreportを出して停止します。
簡単に修正できる問題を見つけても変更しません。findingが0件でもscope、未実施validation、
residual riskを報告します。

```text
このbranchをreviewしてください。変更はせず、結果はconsoleへ出してください。
```

```text
このdiffをreviewのみ実施し、reportを /tmp/review.md に保存してください。
```

### `review-then-remediate`

Stage 1は `review-only` と同じです。stable report IDとfinding IDを出し、
`Remediation authorization: NOT GRANTED` と記録して停止します。

Stage 2は後続の明示指示で、reportとfinding scopeを指定した場合だけ開始します。

```text
Report R-20260831-001 の F-002だけを独立に再現し、confirmedなら修正してください。
no-touch boundaryは docs/ 配下です。
```

全findingを対象にするときも、reportを明示します。

```text
/tmp/R-20260831-001.md の全findingを独立に裁定し、
authorizedかつconfirmedかつaction_required=yesのものだけ修正してください。
```

[remediation request template](REMEDIATION_REQUEST_TEMPLATE.md)を使うと、権限と対象を明確に
指定できます。reportのtarget fingerprintが現在のtargetと異なる場合はstaleとして停止または
再reviewします。

### `review-and-remediate`

同一依頼でreviewと必要な修正を明示した場合だけ選びます。reviewerはこのmodeでもread-onlyで、
findingをimplementerへ渡すだけです。implementerが各findingを独立に裁定し、限定された問題を
修正します。その後、別reviewerまたは独立contextが一回だけread-only re-reviewし、
[consolidated report](CONSOLIDATED_REPORT_TEMPLATE.md)を出して停止します。

```text
この変更をreviewし、確認できた問題は同じ作業内で修正してください。
指摘、対応要否、対応内容、verificationをconsoleへreportしてください。
```

```text
mode=review-and-remediate で実行してください。
report_path=/tmp/review-and-remediation.md
review scope内のconfirmedかつaction_required=yesのfindingだけ修正してください。
```

re-reviewで見つかった新規findingは同じauthorizationで自動修正しません。一回の依頼で無限の
find-fix loopは行いません。

## Fail-safeなmode選択

明示modeを優先します。自然言語では次のように選びます。

| 依頼 | Mode |
|---|---|
| 「reviewのみ」「変更せず確認」「指摘だけ」 | `review-only` |
| 「まずreviewし、対応は後で指示」 | `review-then-remediate` Stage 1 |
| reportを指定して「F-001をconfirmedなら修正」 | `review-then-remediate` Stage 2 |
| 「reviewし、確認できた問題は修正」 | `review-and-remediate` |
| 修正権限またはscopeが曖昧 | `review-only` |

「後はよしなに」「必要に応じて対応」だけでは修正権限を推定しません。

## Reviewerとimplementer

reviewerは全modeでsource、test、config、fixture、lockfile、文書を変更しません。commit、push、
PR操作も行いません。副作用の可能性があるtest/buildは、許可されたdisposable環境以外では
実行しません。reviewerによるsource変更が観測されたepisodeは `FAIL` です。

write authorityを持てるのは、remediationが明示的にauthorizedされたimplementerだけです。
implementerはfindingを次に裁定します。

- `confirmed`
- `rejected`
- `inconclusive`

さらに `action_required` と `action_status` を記録し、authorized、`confirmed`、
`action_required=yes` の3条件を満たすfindingだけを修正します。rejected、inconclusive、
unauthorized、not-requiredのfindingは変更しません。

## Reportの出力先

既定はconsoleです。fileへ出すのはexplicit `report_path` がある場合だけです。pathなしで
「fileへ保存」と言われても名前やrepository内の保存先を推測せず、consoleへfallbackします。

PoCでは次のfile policyを使います。

- parent directoryは事前に存在する必要があり、reviewerは作成しない。
- existing fileは `overwrite=yes` 等の明示許可がない限り上書きしない。
- output path自身または親pathにsymlinkが含まれる場合はwriteしない。
- writeを拒否した場合もreportを失わずconsoleへfallbackし、理由をmetadataへ記録する。
- fileへ成功した場合、consoleにpath、report ID、decisionを表示する。

review-only用は[review report template](REVIEW_REPORT_TEMPLATE.md)、段階的対応用は
[remediation report template](REMEDIATION_REPORT_TEMPLATE.md)、one-shot用は
[consolidated report template](CONSOLIDATED_REPORT_TEMPLATE.md)を参照してください。

## Stable IDとfingerprint

review reportはstable report ID、各findingはstable finding IDを持ちます。推奨形式は
`R-YYYYMMDD-NNN` と `F-NNN` です。clean targetはbase/head/commit SHA、uncommitted targetは
少なくともbase SHA、changed file list、diff hashをfingerprintとして記録します。

remediation前にfingerprintを再確認し、異なるreportをstaleとして扱います。古いfindingを
盲目的に適用しません。

## Installとcomposition

PoCのinstall surfaceは、明示されたrootまたはnested `AGENTS.md` です。installerがmanaged blockへ
合成し、指定したprofile順を保ちます。`scope-control` と組み合わせる場合、先にscope境界を固定し、
その後にこのprofileのreview loopを適用する順序が分かりやすい構成です。semantic conflictの
自動解決やhost間で同一のinstruction precedenceは保証しません。

uninstallはinstallerのmanaged blockだけを削除し、block外を保持する手順で行います。markerを
手作業で片側だけ削除せず、malformed markerとしてfail closedさせてから人間が内容を確認します。

## Pressure testとevidence

[pressure-tests.json](evals/pressure-tests.json)には、3 mode、output policy、authorization、裁定、
stale report、re-review、degraded independence、zero findings、mutation negative control、
traceabilityを扱うfixtureがあります。

fixtureやpackage validatorのPASSはagent behaviorのPASSではありません。Codex CLIとGitHub Copilot
CLIの実episodeはdisposable repositoryで実施し、host/version/model/profile hash/permission/mode/
output/limitationsを含むsanitized evidenceとして別に記録します。

## Statusとlimitations

このprofileのstatusは `experimental` です。instructionを配置してもtool-level enforcementには
なりません。少数の成功をproduction-ready、security guarantee、universal portability、
cross-version consistency、guaranteed obedienceとして表現しません。
