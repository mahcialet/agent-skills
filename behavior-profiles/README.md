# Behavior Profiles（実験実装）

このディレクトリは、Agentが既に持つ能力を**どのように使うか**を記述する
Behavior Profileの試験実装を収める。ProfileはSkill、custom agent、tool-level
policyではなく、repositoryのinstruction surfaceへ任意で重ねるconduct layerである。

現時点の状態は `experimental` である。package validatorの成功は構造整合性だけを
示し、Agentの服従、security、compliance、enforcement、production readiness、host間や
model間の一貫性を証明しない。

## 収録Profile

- [`scope-control`](scope-control/README.md): 依頼範囲とno-touch境界を先に可視化し、
  隣接cleanupなどのscope expansionを抑える。
- [`independent-adversarial-verification`](independent-adversarial-verification/README.md):
  reviewerとimplementerを分離し、review、裁定、明示的に許可されたremediation、
  read-only re-reviewを追跡可能にする。

機械可読な一覧は [`catalog.json`](catalog.json)、共通形式は
[`FORMAT.md`](FORMAT.md)、実episodeの記録項目は
[`EVIDENCE_TEMPLATE.json`](EVIDENCE_TEMPLATE.json) を参照する。

## Skillとの境界

ProfileはSkillへ新しい能力やwrite authorityを与えない。たとえば
`independent-adversarial-verification` は、既存の `adversarial-pr-review` Skillを
任意のreview capabilityとして利用できるが、runtime hard dependencyにはしない。
Profileをinstallしなくても、既存Skillは単独でinstall・実行でき、その安全境界は
変化しない。

Profileは `SKILL.md` に偽装せず、root Skill catalogにも登録しない。Provider固有の
metadataや本文複製も置かない。

## Install surface

PoCの共通surfaceは、repository rootまたは利用者が明示したnested directoryの
`AGENTS.md` である。installerはcanonical profileからmanaged blockを生成する。

```bash
python3 scripts/install_behavior_profiles.py \
  --profile scope-control \
  --profile independent-adversarial-verification
```

targetなしではstdoutへrenderするだけである。`--target` のみではdry-run diffを表示し、
`--target ... --apply` がある場合だけ対象fileを更新する。詳しくは
[`docs/behavior-profiles.md`](../docs/behavior-profiles.md) を参照する。

Installerはhostごとのinstruction precedenceやProfile間のsemantic conflictを解決したと
主張しない。利用者は生成順、repository固有instruction、hostの現行仕様を確認する必要が
ある。

## Validationとevidence

```bash
python3 scripts/validate_behavior_profiles.py
./scripts/validate-skills.sh
```

前者はfrontmatter、section構造、local link、catalog、fixture等のpackage構造を検査する。
実際のAgent episodeは別に評価し、`PASS` / `FAIL` / `CONFUSED` とlimitationsを記録する。
Synthetic fixtureやpackage validationをAgent behaviorの証拠として扱ってはならない。
2026-08-31のsanitized CLI recordは [`evidence/`](evidence/README.md) に置く。

状態語は次のように使い分ける。

- `planned`: 設計または実施予定で、成果物・観測結果がまだない。
- `implemented`: repository内に実装がある。
- `structurally validated`: package validatorが対象revisionを検査した。
- `observed`: 特定host・version・model・fixtureのepisodeで挙動を観測した。
- `verified`: 明示した範囲と根拠に限って追加検証を完了した。

## Removal

Profileを外す場合は、`AGENTS.md` 内の次のmarkerを含むblockだけを削除する。

```text
<!-- BEGIN agent-skills behavior-profiles -->
...
<!-- END agent-skills behavior-profiles -->
```

managed block外はProfile installerの管理対象ではない。
