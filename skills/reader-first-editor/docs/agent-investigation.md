# Agentによる調査

状態: implemented（bundleの作成から明示的なapplyまで）

Agentを使う目的は、ruleを積極的に考案することではない。適用範囲が広すぎるruleを見つけ、
反例によって退けることを優先する。通常のreviewではlocal corpusを自動で読み込まない。
toolが生成したprovider-neutralなinvestigation bundleを読むのは、CodexまたはCopilotが
明示的に起動された場合だけである。

bundle作成から、対象を限定したrule applyまでの経路は実装済みである。この経路では、
Agent resultのruntime gate、human-unapproved proposal draft、regression結果の集約、
tool外の人間review、caller-suppliedなapproval artifactを順に扱う。

## 既定姿勢

```text
Default decision: DO NOT PROMOTE
```

有用なruleを採用し損ねることより、有害なruleをcoreへ導入することを重く扱う。そのため、
広いruleより狭いrule、処方箋より観察、早い採用より `HOLD` を選ぶ。

## Investigationの順序

1. 既存ruleだけで説明できるか確認する。
2. 支持例同士が同じsourceに由来して相関していないか、confounderがないか確認する。
3. clean・borderline・rejected sampleから反例を探す。
4. 最小反例を作り、仮説の適用範囲が広すぎる条件を特定する。
5. 発火例と非発火例のminimal pairを使って境界を調べる。
6. language、genre、reader、purpose、translation依存までscopeを縮める。
7. semantic、unnecessary revision、register、literal、repository-reviewの回帰を調べる。
8. 未説明の反例がなければproposal候補を作る。

## 役割

- **Pattern Miner**: 共通する特徴をruleではなく仮説として記録し、confounderを示す。
- **Counterexample Hunter**: 反例と修正不要な類似例を最優先で探す。
- **Boundary Tester**: minimal pairから隠れた適用条件を特定する。
- **Regression Analyst**: false positive、semantic damage、genre bias、provider差を比較する。
- **Rule Reviewer**: 既存ruleで十分かを再確認し、既定の判断をreject／hold側に置く。

同じAgentが複数の役割を担う場合も、役割ごとにoutput sectionと判断を分ける。反証reviewには、
proposal作成時とは別のfresh contextを使うことが望ましい。

## Bundle

bundleには、仮説、対象scope、support／control record ID、source correlation、分類metadata、
expected behavior、source・rights summary、textの参照とhash、Agentの役割、readiness blocker、
output contractを含める。rightsを確認していないraw third-party textはbundleへ複製しない。
semantic invariantsはbundleが参照するlocal recordに保持する。Agentは参照先recordと既存ruleを
確認し、known exception、既存rule分析、提案eval、未確認事項をinvestigation resultの
counterexamples、`existing_rule_analysis`、`proposed_evals`、decisionへ記録する。

Agentの出力はproposal recordのdraftにすぎず、toolのstate transitionや人間の承認を代行しない。
未説明の反例があればdecisionを `HOLD` にし、情報が足りなければ
`NEEDS_MORE_EVIDENCE` にする。

## CLI workflow

### bundleを作る

最初に、callerがsupportとcontrolを明示的に選ぶ。supportに使用できるのは
accepted／promoted recordだけである。controlにはaccepted／promoted／rejected recordを
使用できる。candidateから直接調査を始めることはできない。人間による選択はtool外の運用要件であり、
toolはcallerや `--actor` が人間かを認証しない。

```bash
tool=skills/reader-first-editor/scripts/corpus_tool.py
data_dir=/path/to/reader-first-editor-data

python3 "$tool" --data-dir "$data_dir" rules bundle \
  --hypothesis "限定した仮説" \
  --support-record <record-id-1> --support-record <record-id-2> \
  --control-record <record-id-3> --purpose "初読理解" \
  --actor reviewer --reason "adversarial investigation"
```

既定ではpreviewだけを返す。`investigations/<bundle-id>/bundle.json` へ保存するのは、
`--apply` を付けた場合だけである。bundleはraw textを複製せず、record path、recordに保存された
content hash、provenance、分類metadataだけを持つ。embeddedなlocal textも別fileへcopyしない。

### Agent resultを検証する

Agentにはbundle、bundle内の `text_reference.record_path` が指すlocal record、
`../references/core/rule-investigation.md` を明示して調査を依頼し、
`investigation.schema.json` のfield構成に沿うJSONを作らせる。`id` には空でないplaceholder stringを
指定する。次のCLIはcustom validatorでresultを検証し、submitted `id` を採用せず、内容から
deterministic IDを再計算する。JSON Schema validator自体は実行しないため、入力JSONそのものの
schema適合性を独立に保証するgateではない。

```bash
python3 "$tool" --data-dir "$data_dir" rules validate-investigation \
  --bundle-id <bundle-id> --result investigation.json
```

toolはsupport数をrecord件数ではなくcorrelation groupから再計算し、bundle外record、改ざんされた
source correlation、選択済みcontrolの `explained`／boundaryへの記載漏れを独立に検出する。nonemptyな
`unexplained` も拒否するが、`explained` に列挙されたcontrolの説明が妥当かは自然言語から判定しない。
boundary pairは各fieldが空でないstringであることを確認し、`does_not_fire` によって選択済みcontrolを
accountedにできる。一方、`fires` が選択済みsupportか、両IDがbundle内に実在するか、意味上のminimal
pairかは検証しない。これらはAgent resultと参照recordを後段の人間reviewで照合する。
provenance未確認、固定閾値・頻度だけの判断、duplicate ruleについては、Agent resultのstructured
booleanを検証して拒否する。toolは `mechanism` や `existing_rule_analysis` の自然言語からbooleanの
正しさを推論しないため、Agentの自己申告と本文、counterexample説明の整合は後段の人間reviewで
確認する。flag上で無効な `PROMOTE` はeffective statusを `HOLD` として返し、`--apply` があっても
保存しない。`HOLD` と `NEEDS_MORE_EVIDENCE` は正常な調査結果として保存できる。

### proposal draftを作る

gateを通過した `PROMOTE` resultと、review対象のnonemptyなrule diff draftから次でproposalを作る。

```bash
python3 "$tool" --data-dir "$data_dir" rules propose \
  --bundle-id <bundle-id> --result-id <result-id> --rule-diff rule.diff
```

このcommandも既定ではpreviewだけを返す。`--apply` が意味するのは、local `proposals/` への
保存だけである。proposalの `human_approval.approved` は必ずfalseであり、regression statusは全て
`not-run` で始まり、`SKILL.md`、references、evalsを変更しない。
この段階ではpatch構造、許可target、apply可能性を検証せず、human approvalも記録しない。これらは
regression後の `rules approve` と `rules apply` で検証する。positive／negative／boundary間で同じeval
IDを指定したresultもproposalとして保存できるが、後段のproposal validationはcategory間の重複を
拒否する。

### regressionから明示applyまで進める

proposal後は、既定の `--eval-dir` にあるbundled eval、`--corpus-record` で選んだpromoted record、
positive／negative／boundary evalを含むplanを `rules regression-plan` で作る。`--eval-dir` を明示すると
別directoryへ置き換わり、Skillのbundled eval全件を含むかは検証しない。promoted record全件は
自動選択しない。
CodexとGitHub Copilotで実行したresultは
`rules regression-ingest` で取り込み、`rules regression-report` で全provider・repeatを
集約する。toolはproviderを直接起動せず、planとresultの検証・保存・再集計だけを担う。

全gateがpassしたreportだけを、`rules approve` で別artifactとして承認できる。`rules apply` は
既定ではpreviewを返す。承認済みのexact diffを、意図したSkill本文・reference・evalへ適用する
のは、`--apply` がある場合だけである。ただし、現行target parserではquotedまたは空白を含む追加sectionが
許可path検査から漏れ得るため、previewだけをtarget限定の保証にしない。詳細なgateとartifactの関係は
[ルール昇格](rule-promotion.md)を参照する。
