# BPR-EE18236-RR-02 修正記録

## 対象、来歴、authorization

- 対象report: `BPR-EE18236-RR-02`
- 対象finding: `BPR-EE18236-RR-02-NF001`
- Finding対象revision: `7ae75aeecec1fabdda1e4841a03dc12e51689c7c`
- Remediation開始revision: `55eef13a830c9cd986788b30b04fe6ee34f27f0f`
- 実装、回帰test、Evidence契約revision:
  `6e5108740f7b562d228769f2347d397bce2706f8`
- 対象branch: `experiment/behavior-profiles`
- 実行環境: Debian GNU/Linux 13.6 (trixie)、Linux 6.12.101+deb13-amd64、x86_64、
  Python 3.13.5

Findingの出典と来歴は、fresh read-only re-review `BPR-EE18236-RR-02` と、その結果を記録した
`behavior-profiles/evidence/BPR-EE18236-RR-01-remediation.md` である。変更前のreportではfindingを
新規として記録するだけに留め、同一authorizationで自動修正しなかった。その後、ユーザーが
RR-01 remediationの全findingを対象とする修正を依頼し、さらに同じroot cause、変更scope、
acceptance criteriaに属する派生境界例は細かな再承認なしで継続する方針を示した。この明示的な
reviewとauthorizationに基づき、本findingと同一原因の境界だけを修正した。

Repository内のfileはproject rootからの相対pathで記録する。以下の `%23`、`%3F`、backslashを
含むpathは、拒否または受理の動作を再現するsynthetic inputであり、実行環境のartifact locatorでは
ないためliteralを保持する。一時directory、session ID、auth/configなど、再現に寄与しない
実行環境依存のlocatorは記録しない。一方、OS、kernel、architecture、Python versionはpath実装と
test結果の解釈に必要となり得るため保持する。

## Findingの裁定と修正

| Finding | Priority | Classification | `action_required` | `action_status` |
|---|---|---|---|---|
| `BPR-EE18236-RR-02-NF001` | Medium | `confirmed` | `yes` | `fixed` |

このfindingは `BPR-EE18236-RR-01-NF001` の残余境界であり、本修正により同findingの最終rollupも
`fixed` となる。旧文書の `not-fixed` は当時の履歴なので書き換えない。

- 未対応finding: `NONE`
- 未対応理由: `N/A`（対象findingはすべて修正済み）

反復percent-decode後の値を `urlsplit()` へ渡し、POSIX / Windows component検査には
`parsed.path` だけを使っていた。このため、decodeされた `#` または `?` より後ろの完全な `..`
componentがfragment / queryとして検査対象から外れ、次の入力をproject-relative pathとして
受理していた。

- `src/%23/../../../outside.py`
- `src/%3F/../../../outside.py`

修正後も `urlsplit()` はschemeとnetwork locationの検査に使うが、POSIX / Windows双方のroot、
anchor、完全な `..` componentはdecode後の文字列全体で検査する。これによりURL parserが
fragment / queryとして分離した領域もpure filesystem pathの検査対象になる。

同じroot causeに属する次のnegative controlも回帰testへ含めた。

- raw delimiter: `src/#/../../../outside.py`、`src/?/../../../outside.py`
- single encoded delimiter: `src/%23/../../../outside.py`、`src/%3F/../../../outside.py`
- double encoded delimiter: `src/%2523/../../../outside.py`、
  `src/%253F/../../../outside.py`
- Windows separatorとの混在: `src/%23\..\..\outside.py`、
  `src/%3F%5C..%5Coutside.py`
- Formal Evidence field経由: `reviewer.code_changes` に入れたsingle / double encoded 4入力

`#` と `?` 自体は禁止していない。次のpositive / boundary controlを受理し、完全な `..`
componentだけを拒否することを固定した。

- `src/hash#name.py`、`src/query?name.py`
- `src/hash%23name.py`、`src/query%3Fname.py`
- `src/#/module.py`、`src/?/module.py`
- `src/%23/..notes.py`、`src/%3F/..notes.py`
- `src/file#draft?.md: 変更理由`
- 既存のPOSIX / Windows相対path、encoded space、`relative/path: 説明`、`docs/..notes.md`

この支持例、反例、境界例と判定規則を `behavior-profiles/FORMAT.md` に同期した。変更は
`scripts/validate_behavior_profiles.py`、`tests/test_validate_behavior_profiles.py`、同format文書に
限定した。Profile本文、catalog、actual Evidence JSON、installerは変更していない。

## 修正前後の再現とverification

| 段階 | 結果 |
|---|---|
| RR-02対象revisionで代表 `%23` / `%3F` inputを直接probe | 2件とも `errors=[]` で受理 |
| 修正後testへ旧 `PurePosixPath(parsed.path)` / `PureWindowsPath(parsed.path)` 動作だけをruntime適用 | 境界8件とEvidence統合4件、計12 failures |
| 修正後targeted 2 test | 2 tests PASS |
| Validator suite | 76 tests PASS |
| Actual Evidence検査 | 2 packageのtemplate / recordを含めPASS |
| Full gate | `./scripts/validate-skills.sh`: 140 tests PASS |
| 実装commit delta検査 | `git diff --check 55eef13a830c9cd986788b30b04fe6ee34f27f0f..6e5108740f7b562d228769f2347d397bce2706f8`: PASS |

追加または拡張したtestは次の2件である。

- `test_recorded_project_path_cross_platform_boundaries`
- `test_evidence_encoded_delimiter_path_escapes_are_rejected`

Targeted testは次のcommandで再実行できる。

```bash
rtk proxy python3 -m unittest \
  tests.test_validate_behavior_profiles.BehaviorProfileValidatorTestCase.test_recorded_project_path_cross_platform_boundaries \
  tests.test_validate_behavior_profiles.BehaviorProfileValidatorTestCase.test_evidence_encoded_delimiter_path_escapes_are_rejected
```

Profile本文のcanonical bytesは不変である。

- `scope-control`:
  `dea62230c512005a48425358727043f6575c5502ba38e5262ade92105d5b62d7`
- `independent-adversarial-verification`:
  `89a0350421ad882b18b69c1fd14117f690e14bcb7f592d7b17a1d361515eef0b`

## Fresh read-only re-reviewと追補修正

- Report ID: `BPR-EE18236-RR-03`
- Target: `af47a9d20a8d94879734f87ffef4574c6707495e`
- Decision: `FAIL`
- `BPR-EE18236-RR-02-NF001`: `RESOLVED`
- Reviewer changes: `NONE`
- Target SHA before / after: 不変
- Worktree before / after: clean

Validator bypassは新たに見つからなかった。Bounded probeでは同じroot causeに絞ったadversarial
7,692入力をすべて拒否し、benign delimiter 2,640入力をすべて受理した。Rawから5重encodingの
`#` / `?`、POSIX / Windows / mixed separator、raw / single / double encoded `..`、delimiter位置と
percent hexの大文字小文字を含む。Targeted 2、validator 76、installer 31、full gate 140 testsと
actual Evidence validationもPASSした。

新規findingはEvidence精度に限られる。

| Finding | Priority | Classification | `action_required` | `action_status` |
|---|---|---|---|---|
| `BPR-EE18236-RR-03-NF001` | Low | `confirmed` | `yes` | `fixed` |

Clean worktreeで実行したbare `git diff --check` は検査対象deltaがなく、初回Evidence commit末尾の
余分な空行を検出していなかった。Range-awareな
`git show --check af47a9d20a8d94879734f87ffef4574c6707495e` はexit code 2となり、
`behavior-profiles/evidence/BPR-EE18236-RR-02-remediation.md` のEOFに新しい空行があると報告した。
余分な空行を削除し、検証を次のcommitted delta基準へ変更した。

- 実装delta:
  `git diff --check 55eef13a830c9cd986788b30b04fe6ee34f27f0f..6e5108740f7b562d228769f2347d397bce2706f8`
- 初回Evidenceからの追補delta:
  `git diff --check af47a9d20a8d94879734f87ffef4574c6707495e..51bb4291913152625aa42100b5806cdd21f22c7f`
- RR-04 targetまでのRemediation delta:
  `git diff --check 55eef13a830c9cd986788b30b04fe6ee34f27f0f..51bb4291913152625aa42100b5806cdd21f22c7f`

Acceptance criteria監査で、AC 22が要求する未対応理由の明記も不足していると判明した。対象は全件
修正済みなので、上記のとおり未対応findingを `NONE`、未対応理由を `N/A` と明記した。

固定SHA `51bb4291913152625aa42100b5806cdd21f22c7f` に対するfresh read-only re-review
`BPR-EE18236-RR-04` は、path findingを `RESOLVED`、EOF空行とAC 22 gapを解消済みと確認した。
ただし、上記2 commandが終点を省略し、named commitとmutable worktreeを比較していたため、decisionは
`FAIL` となった。

| Finding | Priority | Classification | `action_required` | `action_status` |
|---|---|---|---|---|
| `BPR-EE18236-RR-04-NF001` | Low | `confirmed` | `yes` | `fixed` |

終点をRR-04 target SHAへ固定した上記2 commandはいずれもPASSした。Reviewerによるfile変更、report file
作成、target SHA変更はなかった。Bounded probeの件数は独立reviewでも照合したが、generator自体は
commitしていないため、件数の再生成可能性にはこのlimitationがある。

## Acceptance criteriaの解消

| AC | Test / evidence | 判定 |
|---:|---|---|
| 19 | `confirmed`、`action_required=yes` のRR-02-NF001と同一原因の境界だけを修正 | PROVEN |
| 20 | Rejected、inconclusive、unauthorized、not-required findingへの変更なし | PROVEN |
| 21 | 旧動作で12 failures、修正後にtargeted 2 test PASSとなるpractical regressionをcommit | PROVEN |
| 22 | Finding、対応要否、修正、未対応finding `NONE`、未対応理由 `N/A`、verificationを保持 | PROVEN |
| 25 | RR-02作成時には新規findingを修正せず、後続authorization後にだけ対応 | PROVEN |
| 32 | Pure path helperとformal Evidence record経由のintegrationをともに回帰testで検査 | PROVEN |
| 34 | 既存SkillとBehavior Profileを含むfull gate 140 tests PASS | PROVEN |
| 37 | Actual Evidence validationがPASSし、path invariant、必要な環境情報、limitationsを記録 | PROVEN |
| 38 | 一般的なenforcement、security保証、production readinessを主張しない | PROVEN |
| 39 | 実装、Evidence、追補修正を目的別commitへ分離し、fast-forward pushとlocal / remote SHA一致を確認 | PROVEN |
| 40 | PR、merge、tag、release、force pushなし。対象branchはmasterへ未merge | PROVEN |

この結果が示すのは、記載したrevision、synthetic input、実行環境におけるvalidatorの動作である。
一般的なfilesystem security、security/compliance保証、production readinessを証明しない。
