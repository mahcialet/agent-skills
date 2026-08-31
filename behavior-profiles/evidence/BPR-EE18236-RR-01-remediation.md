# BPR-EE18236-RR-01 remediation evidence

## 対象と判定方法

- 対象report: `BPR-EE18236-RR-01`
- 対象revision: `804d403dcaaea47b7728f2354ad699727e806c96`
- 対象branch: `experiment/behavior-profiles`
- Remediation revisions:
  - Validator実装と回帰test:
    `d03d529d111ad31f54ac71339529a065f0526c0c`
  - Evidence契約文書:
    `9fbe054912c1cb6d115a29a7631218b6ee0ecb0a`
- 実行環境: Debian GNU/Linux 13 (trixie)、Linux 6.12.101+deb13-amd64、x86_64、
  Python 3.13.5
- 手順: 対象revisionで各findingを独立に再現・裁定し、今回authorizeされた
  `confirmed` かつ `action_required=yes` のfindingだけを修正した。実装前に回帰testを追加し、
  修正対象の不具合を捕捉することを確認した。

Repository内のfileはproject rootからの相対pathで記録する。以下のWindows rooted path、UNC、
backslash traversal、encoded schemeは、拒否動作を再現するsynthetic invalid inputであり、実行環境の
artifact locatorではない。再現に必要な入力値なのでliteralを保持する。Temporary run root、session ID、
auth/configなど、再現に寄与しない実行環境依存のlocatorは記録しない。

## Findingごとの裁定と解消

| Finding | Priority | Classification | `action_required` | 修正と決定的な証拠 | `action_status` |
|---|---|---|---|---|---|
| `BPR-EE18236-RR-01-NF001` | Medium | `confirmed` | `yes` | 提示されたcross-platform root、backslash `..`、single/double encoded schemeは拒否。Fresh re-reviewでencoded query/fragment delimiter後のparent componentが検査から外れる新規bypassを確認 | `not-fixed` |
| `BPR-EE18236-RR-01-NF002` | Low | `confirmed` | `yes` | Enumをstring型確認後に照合し、array/object等をfield単位のvalidation errorとして返すtestを追加 | `fixed` |
| `BPR-EE18236-RR-01-NF003` | Low | `confirmed` | `yes` | Repository path外側ancestorの交換でreaderがre-anchorしないことを固定するcommitted regression testを追加 | `fixed` |

### BPR-EE18236-RR-01-NF001 — cross-platform / encoded pathの拒否漏れ

対象revisionでは、Evidenceのpure path fieldに入れた次の契約違反を受理した。

- UNC path: `\\server\share\review.py`
- Windows rooted path: `\tmp\implementation.py`
- Backslash traversal: `src\..\outside.py`
- Percent-encoded scheme: `file%3A///tmp/test.py`

加えて、drive-qualified path、extended-length Windows path、encoded absolute path、encoded
backslash traversal、double-encoded schemeを境界testへ含めた。修正後は、percent encodingを値が
安定するまでdecodeしてschemeとnetwork locationを検査し、POSIXとWindows双方のanchorと完全な
`..` componentを拒否する。Validator実行hostがPOSIXでもWindows表記を受理しない。

`src/module.py`、`src\module.py`、`src/path%20with%20spaces.py`、既存互換の
`src/module.py: 変更理由` はpositive controlとして受理する。`docs/..notes.md` も `..` が独立した
path componentではないため受理する。この契約を [`FORMAT.md`](../FORMAT.md) に同期した。

### BPR-EE18236-RR-01-NF002 — malformed enumの非controlled例外

対象revisionでは、Evidenceまたはpressure fixtureのenum fieldへJSON arrayなどhash不可能な値を
入れると、set membershipで `TypeError` が発生し、field単位のcontrolled validation errorにならなかった。

修正後は共通のenum predicateが先にJSON stringであることを確認し、その後でcanonical valueを照合する。
Evidenceのhost、decision、report output、control decision、finding classification、
`action_required`、`action_status`、record statusと、pressure fixtureのreport destination、
expected decisionをmalformed inputで検査した。Profile nameも非string値で例外終了せず、controlled
errorを返す。CLI entry pointへ不正な `action_status` を渡すtestでは、tracebackではなく診断をstderrへ
出し、exit code 1を返すことを確認した。この型要件も [`FORMAT.md`](../FORMAT.md) に同期した。

### BPR-EE18236-RR-01-NF003 — repository外側ancestor固定testの欠落

対象revisionのsecure reader実装はrepository path外側のancestorからdescriptorを固定しており、
この交換を防いでいたが、その不変条件を直接固定するcommitted regression testがなかった。したがって
実装変更は行わず、test-onlyで解消した。

追加testは、repositoryを含むtrusted parentをreaderのopenへ介入してrepository外directoryへのsymlinkに
交換し、readerが交換後のpathへre-anchorして `OUTSIDE_SENTINEL` を読まないことを確認する。現実装では
PASSした。一方、runtimeのanchor動作だけを `c396215^` 相当へ差し替えた独立probeでは
`OUTSIDE_SENTINEL` を読み、testがFAILした。これにより、単に現実装を追認するtestではなく、rootから
ancestor componentを固定するhardeningの退行を検出できることを確認した。

## 修正前後のtestとverification

| 段階 | 結果 |
|---|---|
| 対象revisionへNF001 / NF002のtable / integration 4 testとNF003 testを適用 | NF001 / NF002は計20 failures、NF003は現実装でPASS |
| 対象revisionのpublic mainへ `action_status=[]` を入力 | `TypeError`でabortすることを独立再現 |
| NF003 testへ `c396215^` 相当のruntime anchor動作を適用 | `OUTSIDE_SENTINEL` を読みFAIL |
| 修正後validator | 75 tests PASS |
| 修正後full gate | `./scripts/validate-skills.sh`: 139 tests PASS |
| 実Evidence検査 | Repository内のactual Evidence JSONを含めPASS |
| Diff検査 | `git diff --check`: PASS |

追加した6 test methodは次のとおりである。

- `test_evidence_cross_platform_path_escapes_are_rejected`
- `test_recorded_project_path_cross_platform_boundaries`
- `test_malformed_evidence_enums_are_controlled_validation_errors`
- `test_malformed_pressure_fixture_enums_are_controlled_errors`
- `test_malformed_action_status_returns_controlled_main_failure`
- `test_repository_parent_replacement_does_not_reanchor_reader`

Profile本文、catalog、actual Evidence JSONは変更していない。Canonical bytesが不変であるため、Profile
versionとcontent hashも変更していない。

- `scope-control`:
  `dea62230c512005a48425358727043f6575c5502ba38e5262ade92105d5b62d7`
- `independent-adversarial-verification`:
  `89a0350421ad882b18b69c1fd14117f690e14bcb7f592d7b17a1d361515eef0b`

## Acceptance criteriaの解消

| AC | Test / evidence | 判定 |
|---:|---|---|
| 21 | NF001 / NF002の実不具合を修正前に失敗するtargeted regression testで捕捉し、NF003の欠落testもhardening前相当のruntime動作でFAILすることを確認 | PROVEN |
| 26 | Reviewer mutationをFAILとして検出する既存testを維持し、`reviewer.code_changes` のcross-platform escapeも拒否するtestを追加 | PROVEN |
| 32 | Required structure、links、notice、catalog、fixtureの既存検査に加え、repository path外側ancestor交換を含むsecure readerの不変条件をcommitted regression testで固定 | PROVEN |
| 34 | Validator 75件と既存Skillを含むfull gate 139件がすべてPASS | PROVEN |
| 37 | 必須field、実行環境、Profile hash、permission、mode、output、limitationsの既存検査とenum型契約、提示されたcross-platform path caseはPASS。ただしencoded query/fragment delimiter後のparent componentを見落とす | NOT PROVEN |

AC 21、32で前回残っていた証拠gapは上記testで解消した。AC 26、34も回帰がないことを再確認した。
AC 37はfresh re-reviewで見つかった新規path bypassにより未達のままである。
今回の修正はvalidator、回帰test、Evidence format契約だけであり、Agent conduct contractやCLI episodeを
変更していないため、fresh CLI dogfood episodeは追加していない。

この結果は当該validator、synthetic input、記載した実行環境での観測である。一般的なfilesystem
security、security/compliance guarantee、production readinessを証明しない。

## Fresh read-only re-review

- Report ID: `BPR-EE18236-RR-02`
- Target: `7ae75aeecec1fabdda1e4841a03dc12e51689c7c`
- Reviewer mechanism: fresh independent read-only context
- Decision: `FAIL`
- Reviewer changes: `NONE`
- `BPR-EE18236-RR-01-NF001`: `PARTIALLY RESOLVED`
- `BPR-EE18236-RR-01-NF002`: `RESOLVED`
- `BPR-EE18236-RR-01-NF003`: `RESOLVED`
- Verification: validator 75 / 75、installer 31 / 31、full gate 139 / 139、actual Evidence、
  `git diff --check` がPASS。NF003 testはroot-anchor前相当の独立probeでFAILし、検出力も確認した。
- New findings automatically remediated: `NO`

新規 `BPR-EE18236-RR-02-NF001` はMedium、`confirmed`、`action_required=yes` である。反復decode後に
URL query / fragment delimiterとして解釈された文字より後ろの完全な `..` componentが
`parsed.path` の検査対象から外れ、pure path invariantを迂回できる。再現に必要なsynthetic inputは
`src/%23/../../../outside.py` および同型の `%3F` caseで、targetでは `errors=[]` だった。
このfindingはRR-02で初めて得たため、今回のauthorizationでは修正していない。

Re-reviewの開始・終了ともtarget SHAは不変でworktree clean、reviewer writeは0件だった。
