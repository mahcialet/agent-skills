# コーパス運用

状態: planned（未実装）

この文書は、実文、review履歴、採用・却下判断をlocal corpus候補として蓄積し、
明示的な審査を経てcorpusへ昇格するworkflowを定義する。現在のSkillには、このworkflowを
実行するCLIやlocal stateはまだない。

## 原則

候補収集とSkillの挙動変更を分離する。

> 候補は蓄積できるが、Skillへの反映には明示的な操作が必要である。

`collect` はcandidateだけを作り、`SKILL.md`、references、examples、bundled evalsを
変更しない。candidate、accepted record、promoted local corpusも通常reviewでは暗黙に
読み込まない。

## 状態遷移

```text
collect
  ↓
candidate
  ↓
inspect / annotate
  ├── accept ──→ accepted
  └── reject ──→ rejected
                   ↓
          corpus promotion proposal
                   ↓
            明示的なpromotion
                   ↓
                promoted
```

corpus promotionは実例を評価可能にする処理であり、rule変更ではない。candidateから
behavior-changing ruleへ直接遷移できないようにする。

## 初版CLIの方針

初版はprovider-neutralかつ標準ライブラリ中心の `scripts/corpus_tool.py` を計画する。
特定providerのAPIやCLIを内部から起動しない。networkなしで次を利用できる構成から始める。

```text
corpus list
corpus inspect <candidate-id>
corpus annotate <candidate-id>
corpus accept <candidate-id>
corpus reject <candidate-id>
corpus validate
corpus promote <candidate-id>
corpus promote <candidate-id> --apply
```

`promote` の既定動作はdry-runとし、書込み対象、検証結果、拒否理由、生成予定diffを表示する。
`--apply` がない場合はstateもcorpusも変更しない。

## Local data

Local dataはインストール済みSkillのsource directoryから分離する。解決順は次を計画する。

1. 明示された `--data-dir`
2. 明示的なproject scopeの `<repository>/.reader-first-editor/`
3. user scopeのdata directory

user scopeはXDG data directoryを優先し、platform固有の標準directoryへfallbackする。
project scopeはopt-inとし、`.gitignore` で保護されていない場合は警告または拒否する。
CLIが利用者の `.gitignore` を無断で変更することはない。

概念上のdirectoryは次のとおりである。

```text
reader-first-editor-data/
├── candidates/
├── accepted/
├── rejected/
├── promoted/
├── investigations/
├── proposals/
├── cache/
└── audit/
```

## 収集するsample

少なくとも `problematic`、`clean`、`borderline` を扱う。問題文だけでなく、長いが明確、
自然な主語省略、必要な反復など、変更すべきでないsampleをnegative controlとして保存する。

GitHub由来のrecordは、`positive-reviewed`、`review-directed-revision`、`human-revision`、
`rejected-suggestion` を区別する。mergeやsource reputationだけをgold labelにしない。

## Promotion gate

corpus promotionには、schema、provenance、immutable source、rights status、annotation、
expected behavior、duplicate確認、reviewer decisionが必要である。rightsが不明なrecordは
local-onlyに限る。publicなbundled corpusへ移す場合は、raw textの再配布権限、NOTICE、
attribution、third-party contentの分離を追加で確認する。

## Audit

収集、annotation、accept、reject、promotionの各操作を追記型audit logへ記録する。
元recordを黙って上書きせず、actor、時刻、旧state、新state、理由、tool versionを残す。
