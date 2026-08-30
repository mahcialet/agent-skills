# Behavior Profilesの試験運用

Behavior Profileは、Agentが既に持つSkillやtoolを「どのような境界で使うか」を記述する
任意のconduct layerである。Skillのように能力を追加せず、custom agentやtool-level policyにも
変換しない。このrepositoryでは [`behavior-profiles/`](../behavior-profiles/README.md) を
Skillとは別catalog・別validatorで管理する。

この試験実装のstatusは `experimental` である。Profile textはinstructionであり、file access、
edit、command、commit、外部actionを機械的に阻止するenforcementではない。Security、compliance、
production readiness、host・version・modelをまたぐ一貫性、永続的memory、必ず従うことも保証しない。

## Canonical sourceと構成

各Profileの正本は `behavior-profiles/<name>/BEHAVIOR_PROFILE.md` である。Codex版とCopilot版の
本文を分けず、Provider metadataを正本へ混ぜない。

```text
canonical BEHAVIOR_PROFILE.md
              │
              ├── package validator ── 構造整合性だけを判定
              │
              └── installer ───────── AGENTS.md managed blockを生成
                                      ├── Codex CLI
                                      └── GitHub Copilot CLI
```

Profileは指定順で連結する。InstallerはProfile同士、repository固有instruction、host固有の
instruction precedenceにsemantic conflictがないとは判定しない。利用者が生成結果をreviewする。

## Host instruction surface

PoCの共通install surfaceは、repository rootまたは利用者が明示したnested directoryの
`AGENTS.md` である。2026-08-31に次の公式文書を確認した。

- [OpenAI Docs: Custom instructions with AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
  は、Codexがproject rootからcurrent working directoryまでを探索し、より近いinstructionを
  後から連結すると説明している。各directoryでは `AGENTS.override.md` が `AGENTS.md` より優先され、
  読み込み上限もある。
- [GitHub Docs: Adding custom instructions for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions)
  は、Copilot CLIがroot、current working directory、中間directory、作業対象file配下の
  standard locationから `AGENTS.md` を探索すると説明している。複数instruction fileの一般的な
  precedenceは定義されないため、競合を避ける必要がある。

この相違があるため、installerの成功はhostが同じ優先順位でProfileを適用したことや、実際に
Profileへ従ったことを証明しない。CLIの正確なversionとmodelは実episodeごとのevidenceへ記録する。
Instruction変更後はhostの新しいsessionで確認する。

`.github/copilot-instructions.md`、user-global instruction、`CLAUDE.md`、organization-wide
deploymentは今回の自動install対象外である。

## Installとdry-run

Targetなしではcanonical Profileをstdoutへrenderするだけで、fileを変更しない。

```bash
python3 scripts/install_behavior_profiles.py \
  --profile scope-control \
  --profile independent-adversarial-verification
```

`--target` だけを指定すると、既存fileとの差分を表示して停止する。

```bash
python3 scripts/install_behavior_profiles.py \
  --profile scope-control \
  --profile independent-adversarial-verification \
  --target /path/to/repository/AGENTS.md
```

明示的に更新するときだけ `--apply` を追加する。

```bash
python3 scripts/install_behavior_profiles.py \
  --profile scope-control \
  --profile independent-adversarial-verification \
  --target /path/to/repository/AGENTS.md \
  --apply
```

`--apply` はtargetとparentが安全な通常pathで、managed markerが0組または正しい1組のときだけ
atomic writeする。片側だけのmarker、複数block、nested block、symlink target、存在しないparentは
fail closedとする。既存blockがなければ文書を保持して末尾へ追加し、あればblock内だけを置換する。
同じ入力の2回目applyはno-opである。自動commit、push、PR作成はしない。

### Nested scope

Nested `AGENTS.md` へ入れる場合もtarget pathを明示する。

```bash
python3 scripts/install_behavior_profiles.py \
  --profile scope-control \
  --target /path/to/repository/services/payments/AGENTS.md \
  --apply
```

Nested fileの適用範囲と優先順位はhostによって異なる。Rootとnestedの両方へ同じProfileを入れる
必要性をinstallerは判断しない。

### Uninstall

PoCでは自動uninstall commandを提供しない。次のmarkerを含むblock全体だけを手動で削除し、
その外側を保持する。

```text
<!-- BEGIN agent-skills behavior-profiles -->
...
<!-- END agent-skills behavior-profiles -->
```

削除前後のdiffを確認し、新しいhost sessionでactive instructionを再確認する。

## Profile composition

`scope-control` はtask開始時のrequested scope、no-touch領域、許可されたaction、done条件、
stop/flag条件を可視化する。`independent-adversarial-verification` はreviewerとimplementerの
role、report、authorization、findingの裁定、re-reviewを制御する。併用時も、後者が前者の
no-touch境界を拡張することはない。

`adversarial-pr-review` Skillは、独立reviewerが利用できる任意の推奨capabilityである。
ProfileはSkillをruntime dependencyにせず、ProfileなしでもSkillは単独で安全にinstallできる。

## Independent verificationの3 mode

| Mode | Remediation authority | 必須の停止点 |
|---|---|---|
| `review-only` | なし | reportを出し、codeを変更せず停止 |
| `review-then-remediate` | Stage 1ではなし。後続の明示指示でreportとfinding scopeを指定した場合だけ付与 | Stage 1 report後に停止。Stage 2は許可findingだけを裁定・対応後に停止 |
| `review-and-remediate` | 同一依頼内の明示的なreview-and-fix指示だけ | 一回のremediationとread-only re-review後に停止 |

Modeまたはwrite authorityが曖昧なら `review-only` を選ぶ。Reviewerは全modeでread-onlyであり、
write authorityは明示的に許可された別roleのimplementerだけが持つ。同一contextのself-reviewしか
できない場合はindependenceを `degraded` と記録し、無条件の `PASS` にしない。

Reportの既定出力はconsoleである。Fileへ書けるのは明示的な `report_path` がある場合だけで、
file出力要求だけから名前や保存先を推測しない。Parent directoryを勝手に作らず、symlinkや既存fileは
明示的な安全条件・overwrite許可がない限り拒否する。GitHub comment、status、label、mergeはreportの
代替にしない。

### Request例

Reviewだけを依頼する例:

```text
operation_mode=review-only。HEAD差分を独立reviewし、reportはconsoleへ出してください。
Reviewerはsourceを変更せず、report後に停止してください。
```

Two-stageのStage 2を依頼する例:

```text
Report R-20260831-001 の F-001 だけをremediateしてください。
Findingを独立に再現し、confirmedかつaction_required=yesの場合だけ変更してください。
```

One-shotを依頼する例:

```text
operation_mode=review-and-remediate。独立reviewerがread-only reviewし、別implementerが
review scope内のauthorized・confirmed・action-required findingだけを修正してください。
その後、別のread-only reviewerが一度だけre-reviewしてください。
```

Implementerは各findingを `confirmed` / `rejected` / `inconclusive` に裁定し、
`action_required` と `action_status` を記録する。Authorized、confirmed、action-requiredなfinding
だけを変更する。Re-reviewで見つかった新規findingは同じauthorizationで自動修正しない。

## Validationと実episode

Package validationはfrontmatter、required section、link、NOTICE、catalog、JSON fixtureを検査する。
これは `structurally validated` という状態だけを示す。

Agent episodeはdisposable repositoryで実施し、host/version/model、Profile version/hash、permission、
mode、report destination、reviewer/implementerのwrite、verification、decision、limitationsを
[`EVIDENCE_TEMPLATE.json`](../behavior-profiles/EVIDENCE_TEMPLATE.json) に従って別に記録する。
Synthetic harness resultをAgent obedienceの証拠にせず、`FAIL`、`CONFUSED`、`INCONCLUSIVE` も
省略しない。

