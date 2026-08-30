# コーパス運用

状態: 一部implemented（manual CLI、public GitHub収集、local promotionまで実装済み）

この文書では、実文、review履歴、採用・却下判断をlocal corpus候補として蓄積し、人間の審査を
経てcorpusへ昇格する手順を説明する。schema v1、local data directory解決、state transition、
audit log、manual CLI、public GitHub PR収集、local promotionは実装済みである。一方、public
promotionと、通常のreviewでのlocal corpus読込みは未実装である。

## 原則

候補収集とSkillの挙動変更を分離する。

> 候補は蓄積できるが、Skillへの反映には明示的な操作が必要である。

`collect` が作るのはcandidateだけであり、`SKILL.md`、references、examples、bundled evalsは
変更しない。candidate、accepted record、promoted local corpusも、通常のreviewでは自動的に
読み込まない。

## 状態遷移

```text
collect
  ↓
candidate
  ↓
inspect / annotate
  ├── reject ──→ rejected
  └── accept ──→ accepted
                   ↓
    corpus promotion proposal（preview）
                   ↓
       明示的なpromotion（--apply）
                   ↓
                promoted
```

corpus promotionは、実例を評価に使える状態へ移す処理であり、ruleの変更ではない。
candidateからbehavior-changing ruleへ直接遷移することはできない。

## CLIの実装範囲

provider-neutralかつ標準ライブラリ中心の `scripts/corpus_tool.py` を実装している。
特定providerのAPIやCLIを内部から起動せず、networkに接続しない次の操作を利用できる。

```text
corpus list
corpus inspect <candidate-id>
corpus annotate <candidate-id>
corpus accept <candidate-id>
corpus reject <candidate-id>
corpus validate
corpus promote <candidate-id>
corpus promote <candidate-id> --apply
corpus collect-github --repository <owner/name> --pr-number <number> ...
```

`promote` の既定動作はdry-runである。書込み対象、検証結果、拒否理由、生成予定diffを表示するが、
`--apply` がなければstateもcorpusも変更しない。

`collect` には、一つのrecordを格納したJSON fileを渡す。`annotate` に渡すJSONは、
`annotations` objectだけを持つ。`accept` の対象はannotated recordに限る。`reject` はcandidate
またはannotated recordを削除せず、rejectedへ移す。`validate` はrecord、state、auditの整合を
確認するだけで、変更しない。

## GitHub収集

`collect-github` はpublic repositoryとPR番号を明示した場合だけGitHub REST APIへ接続する。
通常のreview、manual collection、validationからnetwork収集を起動しない。`GH_TOKEN` または
`GITHUB_TOKEN` があればrequest headerだけに使用し、record、fixture、errorへ値を出力しない。

全paginationを取得し、repository metadata、PR metadata、変更file、review submission、inline
review commentのendpointが全て成功してからcandidateを組み立てる。途中responseや親commentが
欠けたthreadは拒否し、収集開始前のstateを維持する。private repositoryではrepository metadataの
確認直後に停止し、その後のPR endpointを読まない。

対象は変更済みMarkdownだけで、fileごとにcandidateを作る。PR本文、file content、patch、
review/comment本文は保存せず、final head SHA、blob SHA、path、review state、対象SHA、threadの
位置・reply数を保持する。raw textの有無はbooleanだけで記録する。rightsは次で固定する。

```text
storage: reference-only
rights.status: unknown
rights.local_only: true
raw_text_redistribution: unknown
review_comment_redistribution: unknown
```

merged PRのfinal headにhuman approvalがあり、対象fileにrevisionを示すhuman inline threadが
なければ、candidate draftを `positive-reviewed` とする。旧revisionへのhuman threadがある場合、
またはchanges-requested後にfinal headがapproveされている場合は、`review-directed-revision` とする。
いずれもmetadataに基づく保守的な仮分類であり、annotation rationaleは空のままにする。人間が
`annotate` と `accept` を実行するまでcorpusへ昇格できない。

test用の `--fixture` はraw textを除いたrecorded snapshotだけを読む。fixture内に `body`、
`content`、`patch`、`diff_hunk` があれば拒否する。PR #138と#187のfixtureはGitHub上の事実metadata
だけを保存し、第三者の文章をrepositoryへ複製しない。

## Local data

Local dataはインストール済みSkillのsource directoryから分離する。保存先は次の順に
解決する。

1. 明示された `--data-dir`
2. 明示的なproject scopeの `<repository>/.reader-first-editor/`
3. user scopeのdata directory

実装済みのpath解決では、user scopeではXDG data directoryを優先し、Windows、macOS、Linuxの
標準directoryへfallbackする。project scopeはopt-inである。write commandの実行前に
`.gitignore` の状態を確認し、未保護なら警告して拒否する。利用者の `.gitignore` は無断で
変更しない。明示的な `--data-dir` がGit worktree内を指す場合もignore状態を確認する。
利用者による明示overrideとして扱うのは、`--allow-unignored-project-data` だけである。

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

少なくとも `problematic`、`clean`、`borderline` を扱う。問題文だけを集めるのではない。
長くても明確な文、自然な主語省略、必要な反復など、変更すべきでないsampleもnegative controlとして
保存する。

GitHub由来のrecordは、`positive-reviewed`、`review-directed-revision`、`human-revision`、
`rejected-suggestion` を区別する。mergeやsource reputationだけをgold labelにしない。

## Promotion gate

corpus promotionには、schema、provenance、immutable source、rights status、annotation、
expected behavior、duplicate確認、reviewer decisionが必要である。rightsが不明なrecordは
local-onlyに限る。publicなbundled corpusへ移す場合は、raw textの再配布権限、NOTICE、
attribution、third-party contentの分離も確認する。

## Audit

収集、annotation、accept、reject、promotionの各操作を追記型audit logへ記録する。元recordを
黙って上書きせず、actor、時刻、旧state、新state、理由、schema versionを残す。recordとauditを
更新する前にpending journalを作り、audit commit前に失敗した場合は旧stateへrollbackする。
processが停止しても、次回のstore初期化時に未完了journalを回復する。
