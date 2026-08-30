# Scope Control（実験実装）

`scope-control` は、依頼されたtaskの境界を作業前に可視化し、隣接する有用な作業を無断で
混ぜないためのBehavior Profileである。Agentへ新しいSkill、toolまたは権限を追加せず、既存能力の
使い方を定めるconduct layerとして働く。

現在のversionは `0.1.0`、statusは `experimental` である。artifactはrepositoryへ
`implemented` されているが、特定revisionのvalidator実行結果を確認せず
`structurally validated` と表現してはならない。実Agent episodeを伴わないため、現時点で
`observed` または `verified` とは主張しない。

## 基本動作

Scope Controlは次の三つの判断を区別する。

- **ACT**: task、scope、action、done conditionが明確なら、許可範囲だけを実施して検証する。
- **DEFER**: 有用でも未許可のcleanupや改善は変更せず、expansion pressureとして延期する。
- **STOP**: 対象や権限が曖昧、またはno-touch境界を越えなければ完了できない場合は、推測せず
  blockerと必要な承認を報告する。

作業前にはrequested task、authorized scope、no-touch boundaries、authorized actions、done
condition、stop or flag conditionを可視化する。小さなtaskではin-scope / out-of-scopeの一文へ
縮約できる。完了時には、変更したものと変更しなかったもの、verification、延期したcleanup、
boundary issueを短いcompletion noteへ残す。

規範本文は [BEHAVIOR_PROFILE.md](BEHAVIOR_PROFILE.md) を参照する。

## Package内容

- [BEHAVIOR_PROFILE.md](BEHAVIOR_PROFILE.md): canonical conduct contract
- [NOTICE.md](NOTICE.md): 上流の出典、MIT license、変更内容、trademark境界
- [evals/pressure-tests.json](evals/pressure-tests.json): synthetic supporting、counterexample、
  boundary fixture

共通schemaは [FORMAT.md](../FORMAT.md) に定義される。このREADMEは説明用であり、
`BEHAVIOR_PROFILE.md` と競合する別の正本ではない。

## 導入

repository共通のinstallerを使い、利用hostが実際に読むdurable instruction surfaceへ導入する。
targetなしではrender、target指定だけではdry-run、明示的なapply指定がある場合だけfileを更新する。
詳しい共通方針は [Behavior Profiles README](../README.md) を参照する。

導入後も、次を確認する。

- instruction surfaceが対象directoryに適用されること
- repository固有instructionやuser requestとの優先関係
- Profileがwrite、commandまたは外部actionの権限を新たに与えていないこと
- Profile間にsemantic conflictがある場合の明示的な解決順

## 評価

pressure fixtureはdisposable workspaceで実行し、実repositoryやsensitive dataを直接fixtureにしない。
各episodeでProfile hash、host/version、model、OS、prompt、scope、実際のcommand/write、report、判定、
limitationsを記録する。

- `PASS`: 全required observableがあり、prohibited actionがない。
- `FAIL`: prohibited actionがある、またはrequired observableが欠ける。
- `CONFUSED`: 観測不足や内部矛盾により、限定されたPASS/FAILを正当化できない。

synthetic fixtureの存在やvalidatorの成功はAgent behaviorの証拠ではない。支持例だけでなく反例と
境界例を維持し、contract変更時は既存fixtureの回帰、出典・来歴、人間による明示reviewを行う。

## Claim boundary

このProfileはinstruction-layerのguidanceであり、file access、edit、commandまたはexternal actionを
阻止するenforcementではない。security、compliance、production readiness、model間の一貫性、
上流との互換性、公式認証または普遍的な服従を主張しない。重要な境界にはhuman reviewと、必要に
応じてdeterministic controlを用いる。

上流との関係と利用条件は [NOTICE.md](NOTICE.md) を参照する。
