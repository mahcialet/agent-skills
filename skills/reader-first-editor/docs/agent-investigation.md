# Agentによる調査

状態: implemented（bundleから明示applyまで）

Agentはruleを積極的に考案する役ではなく、危険な一般化を壊す役として使う。toolは
provider-neutralなinvestigation bundleを生成し、CodexまたはCopilotが明示起動された場合だけ
そのbundleを読む。通常reviewへlocal corpusを暗黙に注入しない。bundle作成、Agent resultの
runtime gate、human-unapproved proposal draft、regression結果の集約、人間の明示承認、限定した
rule applyを実装している。

## 既定姿勢

```text
Default decision: DO NOT PROMOTE
```

有用なruleを見逃すcostより、有害なruleをcoreへ導入するcostを高く扱う。広いruleより狭い
rule、処方箋より観察、早い採用より `HOLD` を選ぶ。

## Investigationの順序

1. 既存ruleで説明できるか確認する。
2. 支持例のsource相関とconfounderを確認する。
3. clean・borderline・rejected sampleから反例を探す。
4. 最小反例を作り、仮説が広すぎる条件を特定する。
5. 発火例と非発火例のminimal pairで境界を調べる。
6. language、genre、reader、purpose、translation依存までscopeを縮める。
7. semantic、unnecessary revision、register、literal、repository-reviewの回帰を調べる。
8. 未説明の反例がなければproposal候補を作る。

## 役割

- **Pattern Miner**: 共通特徴をruleではなく仮説として記録し、confounderを示す。
- **Counterexample Hunter**: 反例と修正不要な類似例を最優先で探す。
- **Boundary Tester**: minimal pairから隠れた適用条件を特定する。
- **Regression Analyst**: false positive、semantic damage、genre bias、provider差を比較する。
- **Rule Reviewer**: 既存ruleで十分かを再確認し、既定をreject／hold側に置く。

同じAgentが複数役を担う場合も、output sectionと判断を分離する。proposal作成contextとは
別のfresh contextで反証reviewを行うことが望ましい。

## Bundle

bundleには、仮説、対象scope、record ID、source correlation、支持例、反例、known exception、
semantic invariants、既存rule、提案eval、未確認事項を含める。raw third-party textをrights確認
なしにbundleへ複製せず、reference-only recordは参照とhashだけを渡す。

Agentの出力はproposal recordのdraftであり、toolのstate transitionや人間の承認を代行しない。
未説明の反例があればdecisionを `HOLD` にし、情報が足りなければ
`NEEDS_MORE_EVIDENCE` にする。

## CLI workflow

最初に、人間がsupportとcontrolを明示選択する。supportにはaccepted／promoted recordだけを
使用でき、controlにはaccepted／promoted／rejected recordを使用できる。candidateからの直接調査は
拒否する。

```bash
tool=skills/reader-first-editor/scripts/corpus_tool.py
data_dir=/path/to/reader-first-editor-data

python3 "$tool" --data-dir "$data_dir" rules bundle \
  --hypothesis "限定した仮説" \
  --support-record <record-id-1> --support-record <record-id-2> \
  --control-record <record-id-3> --purpose "初読理解" \
  --actor reviewer --reason "adversarial investigation"
```

既定はpreviewであり、`--apply` を付けた場合だけ
`investigations/<bundle-id>/bundle.json` へ保存する。bundleはraw textを複製せず、record path、
content hash、provenance、分類metadataだけを持つ。embeddedなlocal textも別fileへcopyしない。

Agentにはbundleと `../references/core/rule-investigation.md` を明示して調査を依頼し、
`investigation.schema.json` に適合するJSONを作らせる。resultは次で検証する。

```bash
python3 "$tool" --data-dir "$data_dir" rules validate-investigation \
  --bundle-id <bundle-id> --result investigation.json
```

toolはsupport数をrecord件数ではなくcorrelation groupから再計算する。bundle外record、改ざんされた
source correlation、未説明のcounterexample、provenance未確認、固定閾値だけ、頻度だけ、duplicate
ruleを検出する。無効な `PROMOTE` はeffective statusを `HOLD` として返し、`--apply` があっても
保存しない。`HOLD` と `NEEDS_MORE_EVIDENCE` は正常な調査結果として保存できる。

gateを通過した `PROMOTE` resultとhuman-reviewedなrule diffから、次でproposal draftを作る。

```bash
python3 "$tool" --data-dir "$data_dir" rules propose \
  --bundle-id <bundle-id> --result-id <result-id> --rule-diff rule.diff
```

このcommandも既定はpreviewで、`--apply` はlocal `proposals/` への保存だけを意味する。proposalの
`human_approval.approved` は必ずfalse、regression statusは全て `not-run` で始まり、
`SKILL.md`、references、evalsを変更しない。

proposal後は、bundled eval、promoted corpus、positive／negative／boundary evalを含むplanを
`rules regression-plan` で作る。CodexとGitHub Copilotで実行したresultは
`rules regression-ingest` で取り込み、`rules regression-report` で全provider・repeatを集約する。
toolはproviderを直接起動せず、planとresultの検証・保存・再集計だけを担う。

全gateがpassのreportだけを `rules approve` で別artifactとして承認できる。`rules apply` は既定で
previewを返し、`--apply` がある場合だけ、承認済みのexact diffを許可対象のSkill本文・reference・
evalへ適用する。詳細なgateとartifactの関係は[ルール昇格](rule-promotion.md)を参照する。
