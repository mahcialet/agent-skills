# BPR-EE18236 remediation evidence

## 対象と判定方法

- 対象finding group / report prefix: `BPR-EE18236`
- 対象revision: `ee182367d4fe810c2188de8ff2f913b75ee3f880`
- 対象branch: `experiment/behavior-profiles`
- Remediation revisions:
  - 実装修正: `92ddf5ab1490718ece2932e338fc4866a13bc0c1`
  - Evidence契約文書: `4ffed415616c185e33cd339b761dbddcf6bf7fae`
  - Repository root anchor hardening: `c396215e0c669e545c307e8743b7355257971854`
- 実行環境: Debian GNU/Linux 13 (trixie)、Linux 6.12.101+deb13-amd64、x86_64、
  Python 3.13.5
- 手順: 対象revisionをread-onlyで再現し、各findingを `confirmed` / `rejected` /
  `inconclusive` と `action_required` に独立に裁定した。修正対象は、今回authorizeされた
  `confirmed` かつ `action_required=yes` のfindingだけに限定し、先に回帰testを追加した。

Repository内のfileはproject rootからの相対pathで記録する。Temporary run root、session ID、
auth/configなど再現に寄与しない一時的locatorは残さない。以下に記録する
`/tmp/reviewer-change.py` と `/tmp/implementer-change.py` は実行環境のartifact locatorではなく、
absolute pathを拒否できることを再現するsynthetic invalid inputであるため、入力値をそのまま保持する。

対象2 findingはいずれも `confirmed`、`action_required=yes` と裁定し、一回のremediation passで
両方へ対応した。Fresh re-reviewではNF002の解消を確認した一方、NF001のpath invariantに新しい
境界例が見つかったため、最終statusは下表とre-review節のとおり更新した。

## Findingごとの裁定と解消

| Finding | Priority | Classification | `action_required` | 修正と決定的な証拠 | `action_status` |
|---|---|---|---|---|---|
| `BPR-EE18236-NF001` | Medium | `confirmed` | `yes` | 提示されたschema、action status、POSIX absolute path、control decisionの拒否漏れは解消。Fresh re-reviewでWindows形式・encoded schemeの残存bypassを確認 | `not-fixed` |
| `BPR-EE18236-NF002` | Low | `confirmed` | `yes` | Repositoryへanchorしたcomponent単位のno-follow readと、決定的な交換race testを追加 | `fixed` |

### BPR-EE18236-NF001 — Evidence契約の拒否漏れ

対象revisionでは、次の契約違反recordがすべて `errors=[]` で受理された。

| 変異 | 修正前の結果 | 修正後の期待とtest evidence |
|---|---|---|
| `schema_version="999.0"` | ACCEPTED | Evidence schema `1.0`との完全一致を要求しREJECT |
| `action_status="residual"` | ACCEPTED | Canonical 5値以外としてREJECT。Residual riskはreport本文へ記録 |
| `reviewer.code_changes=["/tmp/reviewer-change.py"]`、top-level `decision=FAIL` | ACCEPTED | Pure path fieldのabsolute pathとしてREJECT |
| `implementer.code_changes=["/tmp/implementer-change.py"]` | ACCEPTED | Pure path fieldのabsolute pathとしてREJECT |
| Canonical `control_decisions` の `fixture_run=PASS` / `embedded_observation=FAIL` を `FAIL` / `PASS` へ反転 | ACCEPTED | Top-level decisionおよびcanonical fixtureの `expected_decisions` と不一致としてREJECT |

Schema version、canonical action status、reviewer / implementer / artifactのproject-relative path、
optional `control_decisions` の型と二層decision invariantをvalidatorと
[`FORMAT.md`](../FORMAT.md)へ同期した。`CONSOLIDATED_REPORT_TEMPLATE.md` にだけ存在した
契約外の `residual` statusも除去した。正しいcontrol decisionと相対pathのpositive controlは
引き続き受理する。

Fresh re-reviewでは、UNC path、Windows rooted path、backslash形式の `..`、percent-encoded
schemeをpure path fieldへ入れたformal recordが、なお `errors=[]` で受理されることを確認した。
提示されたPOSIX absolute pathのcaseは解消したがproject-relative invariant全体は未解消なので、
このfindingの最終statusを `not-fixed` とする。このre-review findingは同じauthorizationで
自動修正していない。

### BPR-EE18236-NF002 — containment checkとreadの交換race

対象revisionでは、repository containment checkが成功した直後に対象fileをrepository外sentinelへの
symlinkへ交換すると、readerは `OUTSIDE-SENTINEL` を読み、errorを返さなかった。Pathの確認と
content readが別operationだったため、静的なrepository外symlink testだけではこのraceを防げなかった。

修正後はrepository directory descriptorへanchorし、各ancestor componentとfinal componentを
no-followで開いてからregular fileであることを確認する。決定的なinterposition testで、final fileの
交換とancestor directoryの交換をそれぞれ発生させ、repository外sentinel contentを読まずfail closedに
なることを確認した。Text / JSON、canonical bytes / hash、validator内のfrontmatter parseは同じ
secure readerを共有し、安全なreader capabilityがない環境でもfail closedとする。

途中のfull gateでは、installerが利用する公開 `parse_profile(path)` APIの互換性regressionを検出した。
Validator内部だけをsecure text parserへ分離して公開APIを復元し、統合testを再実行して解消した。

## Acceptance criteriaの解消

| AC | Test / evidence | 判定 |
|---:|---|---|
| 26 | Reviewer mutationにはtop-level `decision=FAIL`を要求する既存testに加え、canonical negative controlの `fixture_run=PASS` / `embedded_observation=FAIL` を受理し、反転を拒否するtestを追加 | PROVEN |
| 32 | Required structure、links、notice、catalog、fixtureの既存検査を維持し、静的escape、final-component交換、repository内ancestor交換、全validator readerの共有、capability欠如時のfail closedを検査。Repository外側ancestor hardeningはre-review probeで動作確認したがcommitted regression testはない | PARTIALLY PROVEN |
| 34 | Validator 69件、installerとvalidatorの計100件、既存Skillを含むfull gate 133件がすべてPASS | PROVEN |
| 37 | Evidence schema `1.0`、canonical action enum、control decision invariant、POSIX absolute path拒否とrepository内の全実Evidence JSONはPASS。ただしWindows形式・encoded schemeのpath bypassが残る | NOT PROVEN |

Confirmed defectを先に捕捉する回帰testを追加したため、AC 21のpractical regression test要件も
維持している。Profile本文、catalog、JSON episodeは変更していない。

## Testとverification

| 段階 | 結果 |
|---|---|
| 対象revisionのbaseline | `./scripts/validate-skills.sh`: 118 tests PASS |
| NF001回帰test追加後 | Validator 65件中11件が意図どおりFAIL。正しいcontrol decisionと相対pathのpositive control 2件はPASS |
| NF002回帰test追加後 | 対象3件が意図どおりFAIL |
| 修正後validator | 69 tests PASS |
| 修正後installer + validator | 100 tests PASS |
| Root anchor hardeningを含む最終full gate | `./scripts/validate-skills.sh`: 133 tests PASS |
| 実Evidence検査 | Repository内のactual Evidence JSONを含めPASS |
| Diff検査 | `git diff --check`: PASS |
| Ruff | Repositoryへ導入されていないため未実施 |

Repository-root anchor hardening後にもfull gate、actual Evidence検査、diff検査を再実行し、上記の
PASSを確認した。Profile本文は不変であり、content hashも次の値から変わっていない。

- `scope-control`: `dea62230c512005a48425358727043f6575c5502ba38e5262ade92105d5b62d7`
- `independent-adversarial-verification`:
  `89a0350421ad882b18b69c1fd14117f690e14bcb7f592d7b17a1d361515eef0b`

今回の修正対象はvalidatorとEvidence契約である。Agentのconduct contractや既存episodeを変更して
いないため、fresh CLI dogfood episodeは追加せず、修正前に失敗するdeterministic regression testを
一次証拠とした。この結果は当該validatorと検査環境での観測であり、一般的なfilesystem security、
security/compliance guarantee、production readinessを証明しない。

## Read-only re-review

- Report ID: `BPR-EE18236-RR-01`
- Target: `dfd4b7de1d2c7348f1c9afa84afd792c4c76d5b4`
- Reviewer mechanism: fresh independent read-only context
- Decision: `FAIL`
- Reviewer changes: `NONE`
- NF001: `PARTIALLY RESOLVED`。未知schema、`residual`、提示されたPOSIX absolute path、反転した
  control decisionは解消したが、project-relative path invariantに残存bypassがある。
- NF002: `RESOLVED`。Final component、repository内ancestor、repository path外側ancestorの交換で
  repository外contentを読まずfail closedとなることを確認した。
- Verification: validator 69 / 69、installer 31 / 31、full gate 133 / 133、actual Evidence検査、
  `git diff --check` がPASS。追加negative regressionをbase実装へ差し替えた独立確認もNONPASS、
  positive controlはPASS。
- New findings automatically remediated: `NO`

新規findingは次のとおりであり、今回のauthorizationでは修正していない。

| ID | Priority | Finding | 状態 |
|---|---|---|---|
| `BPR-EE18236-RR-01-NF001` | Medium | UNC、Windows rooted path、backslash形式の `..`、percent-encoded schemeでpure path制約を迂回できる | `open` |
| `BPR-EE18236-RR-01-NF002` | Low | JSON arrayなどhash不可能なenum値がcontrolled validation errorではなく `TypeError` になる | `open` |
| `BPR-EE18236-RR-01-NF003` | Low | Repository path外側ancestorを固定するhardeningにcommitted regression testがない | `open` |

Re-reviewの開始・終了ともtarget SHAは不変でworktree clean、reviewer writeは0件だった。
