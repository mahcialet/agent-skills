# コーパス運用

状態: 一部implemented（manual CLI、public GitHub収集、local promotionまで）

この文書は、実文、review履歴、採用・却下判断をlocal corpus候補として蓄積し、
明示的な審査を経てcorpusへ昇格するworkflowを定義する。schema v1、local data directory
解決、state transition、audit log、manual CLI、public GitHub PR収集、local promotionは
実装済みである。public promotion、通常reviewへのlocal corpus読込みは未実装である。

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
  ├── reject ──→ rejected
  └── accept ──→ accepted
                   ↓
    corpus promotion proposal（preview）
                   ↓
       明示的なpromotion（--apply）
                   ↓
                promoted
```

corpus promotionは実例を評価可能にする処理であり、rule変更ではない。candidateから
behavior-changing ruleへ直接遷移できないようにする。

## CLIの実装範囲

provider-neutralかつ標準ライブラリ中心の `scripts/corpus_tool.py` を実装している。
特定providerのAPIやCLIを内部から起動せず、networkなしで次を利用できる。

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

`promote` の既定動作はdry-runとし、書込み対象、検証結果、拒否理由、生成予定diffを表示する。
`--apply` がない場合はstateもcorpusも変更しない。

`collect` には一record一fileのJSON、`annotate` には `annotations` objectだけを持つJSONを渡す。
`accept` はannotated recordに限り、`reject` はcandidateまたはannotated recordを保存したまま
rejectedへ移す。`validate` はrecord、state、auditの整合をread-onlyで確認する。

## GitHub収集

`collect-github` はpublic repositoryとPR番号を明示した場合だけGitHub REST APIへ接続する。
通常review、manual collection、validationからnetwork収集を起動しない。`GH_TOKEN` または
`GITHUB_TOKEN` があればrequest headerだけに使用し、record、fixture、errorへ値を出力しない。

全paginationを取得し、repository metadata、PR metadata、変更file、review submission、inline
review commentのendpointが全て成功してからcandidateを組み立てる。途中responseや親commentの
欠けたthreadは拒否し、収集開始前のstateを維持する。private repositoryはrepository metadataの
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
なければ `positive-reviewed`、旧revisionへのhuman threadまたはchanges-requested後にfinal headが
approveされていれば `review-directed-revision` のcandidate draftにする。これはmetadataによる
保守的な仮分類であり、annotation rationaleは空のままにする。人間が `annotate` と `accept` を
実行するまでcorpusへ昇格できない。

test用の `--fixture` はraw textを除いたrecorded snapshotだけを読む。fixture内に `body`、
`content`、`patch`、`diff_hunk` があれば拒否する。PR #138と#187のfixtureはGitHub上の事実metadata
だけを保存し、第三者の文章をrepositoryへ複製しない。

## Local data

Local dataはインストール済みSkillのsource directoryから分離する。保存先は次の順に
解決する。

1. 明示された `--data-dir`
2. 明示的なproject scopeの `<repository>/.reader-first-editor/`
3. user scopeのdata directory

実装済みのpath解決は、user scopeでXDG data directoryを優先し、Windows、macOS、Linuxの
標準directoryへfallbackする。project scopeはopt-inである。`.gitignore` の確認と警告は
write commandの実行前に行い、未保護なら拒否する。利用者の `.gitignore` を無断で変更しない。
明示的な `--data-dir` がGit worktree内を指す場合もignore状態を確認する。
`--allow-unignored-project-data` だけを利用者による明示overrideとして扱う。

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
元recordを黙って上書きせず、actor、時刻、旧state、新state、理由、schema versionを残す。
recordとauditの更新前にpending journalを作り、audit commit前の失敗は旧stateへrollbackする。
process停止後も、次回のstore初期化時に未完了journalを回復する。
