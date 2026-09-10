---
status: active
owner: maintainers
last_verified: 2026-09-11
plan_id: EP-HARNESS-001
plan_type: implementation
base_branch: master
branch: feat/ep-harness-001
priority: 20
workstreams:
  - repository-harness
  - developer-documentation
conflicts:
  - installer-contract
  - validation-entrypoints
  - eval-contract
  - repository-documentation-policy
depends_on: []
merge_policy: manual
promotion_criteria:
  - The maintainer explicitly authorizes implementation of this plan.
  - The implementer rechecks repository instructions, current base, plan ID availability, and working-tree ownership.
  - The initial execution scope and the requirement to finish M1 before behavior-changing edits are recorded.
---

# agent-skillsにリポジトリ内ハーネスを導入する

**対象:** `mahcialet/agent-skills`

**参照:** `mahcialet/agent-env` のrepository-native harness

**成果物の状態:** M1〜M4 の実装を承認済み。base と作業領域を再確認し、専用ブランチで作業中。M5 以降、実モデル・実ホストの起動、merge は今回未承認。

このファイルはCodexへ渡すための独立したExecPlanである。会話履歴を読み直さずに、目的、変更範囲、検証方法、残件を判断できるようにする。ChatGPTからリポジトリへの書き込みは行わない。実装を指示されたCodexが、作業ブランチを作り、この計画をリポジトリへ配置する。

`last_verified` は計画の参照情報を確認した日付であり、ハーネスの実行検証日ではない。以下の `python -m tools.repoctl ...` は、特記しない限り**導入予定のインターフェース**である。現行リポジトリで利用できるコマンドとして紹介しない。

## Purpose / Big Picture

`agent-skills` を、新しいAgentセッションが会話履歴なしで理解し、変更し、検証し、次のセッションへ引き継げるリポジトリにする。

そのために、短いルート指示、設計の案内、検証の正規入口、更新を続けるExecPlan、実行証拠、人間に残す判断を結び付ける。単なるテストランナーの追加ではない。一方で、`agent-env` のGo実装、製品runtime、全Plan orchestrationを丸ごと移植する作業でもない。

利用者が覚える基本の流れを、次に揃える。

```text
AGENTS.mdから対象Skillと変更箇所を把握する
  → ExecPlanで変更範囲と受入条件を確認する
  → 変更する
  → repoctl verifyで決定的な検証を行う
  → 必要なときだけSkill評価・実ホスト検証を行う
  → 結果、証拠、限界、人間への確認事項を記録する
```

### この計画が届けるもの

1. Pythonによるportableな `repoctl` と、既存検証を漏れなく呼ぶタスク構成。
2. Skill構造・カタログ・文書・Planを検証する仕組みと、それ自体の否定テスト。
3. 既存Skill評価を接続するprovider-neutralな入出力契約、隔離したinstaller smoke、実ホスト検証の明示的な入口。
4. 人間向け確認項目、証拠の見方、独立したhuman-validation ExecPlanを含む引継ぎ。

### 対象外

- Skillの編集・レビュー・チケット操作ルール自体の改善、corpusからの自動rule昇格。
- 新しいモデル基盤、課金管理基盤、エージェント常駐scheduler、自動merge基盤の構築。
- `agent-env` 製品への依存追加、Goへの書き換え、共通ハーネスの別リポジトリ化。
- 本番Backlog／Redmineへの書き込み、実ユーザーのSkill配置や認証設定の変更。
- 全既存文書の一括翻訳、Skill本文をホスト別・言語別に複製すること。
- 単にファイルが大きいことを理由にしたinstaller／testの全面refactor。

## Progress

チェックは観測済みの完了にのみ付ける。各milestoneの終了時に、実行したrevision、コマンド、結果、未検証範囲を追記する。

- [x] 2026-09-11: 両リポジトリの参照情報と現行検証経路を読み、初版ExecPlanを作成した。実装検証ではない。
- [x] 2026-09-11: 明示指示により M1〜M4 のみ開始。`origin/master` = `d423d1f483e48cfa955b02114c17611c6f2993cd`、作業領域は `/home/mahcialet/work/git_work/marmite/agent-skills`。開始時は提供された未追跡 Plan のみ。`feat/ep-harness-001` を作成。提供原本は保全し active の日英ペアを作る。
- [x] 2026-09-11 M1: 全検証経路を `docs/testing/harness-contract.md`、D1〜D10 を ADR 0001 に記録。baseline は Linux/Python 3.13.5 で Ruff、root validator（3 Skill）、catalog、root installer 33 tests が PASS。現行失敗なし。
- [ ] M2: portable runner、証拠の基礎、installerのPython正規入口。
- [ ] M3: `check`／`test`／`verify` の分離とnative CIへの接続。
- [x] 2026-09-11 M4: Skill・生成物・文書・Plan の検査を実装し、Linux/Python 3.13.5 で局所検証。M2／M3 の native 制約と受入の限界は下記台帳に残す。Plan 全体完了ではない。
- [ ] M5: Skill evalの計画・結果取込・集約契約。
- [ ] M6: 隔離installer smokeと、明示実行する実ホスト検証。
- [ ] M7: human-validationの引継ぎと、全体の受入確認。
- [ ] 独立レビューの指摘を、対応／却下／延期の理由とともに解決する。
- [ ] 実装をbaseへmergeした証拠を確認し、両言語Planをarchiveする。

## Surprises & Discoveries

以下はコード・文書を読んだ結果であり、今回実行したテスト結果ではない。参照先は「Artifacts and Notes」にある。

| ID | 確認したこと | 計画への反映 |
|---|---|---|
| F1 | `validate_skills.py` は構造検証に加え、各Skillのcontent validator、Skill内のunittest、READMEカタログ検証を呼ぶ。[S2] | そのまま `check` と `test` の両方から呼ばない。責務を分離し、二重実行を防ぐ。 |
| F2 | root installer testsは `validate-skills.sh` が直接起動し、CIからもこのwrapperを通じて実行される。一方、Python validatorだけではroot testsを呼ばない。[S2][S3][S4] | 既存CIの検証は接続済み。shellとPythonに分散した責務を記録し、入口統合時に検証を落とさない。 |
| F3 | `catalog.json` は補助metadataの入力であり、`generate-catalog.py` が生成するのはREADME内のカタログ部分である。[S5] | `catalog.json` を生成物と誤認しない。入力集合の一致と、README生成部分のdriftを別々に検証する。 |
| F4 | installer wrapperにはGit関連環境変数の除去、Git rootとHEADの検証がある。[S6] | 内部Python helperの直接呼出しだけでは代替しない。Python入口へ防御を移し、互換テストを置く。 |
| F5 | `reader-first-editor` にはprovider-neutralなregression plan／ingest／reportがあり、ツールからproviderを直接起動しない設計である。[S7][S8] | 新しい評価基盤へ置換せず、既存処理をadapterで接続する。 |
| F6 | 現行 `AGENTS.md` は日本語を基本にする。一方、参照先 `agent-env` は英語原本と日本語訳の運用である。[S1][S10] | 命名方針まで機械的にコピーしない。既存日本語pathを保ち、今回の永続文書には英語版を併設する。 |
| F7 | `agent-env` の参照baseにはfixture completionと証拠分類の改善が入っている。[S10][S11] | cancelとjoin、繰返しと因果的な回帰証拠を区別する。 |

F2の初期調査ではroot testsの未接続を疑ったが、shell wrapperの確認で接続済みと分かった。この仮説は取り下げる。root validator単体とCI全体を同一視しない。

実装中に新しい問題を見つけたら、原因の仮説、再現条件、影響範囲、処置を追記する。既存問題を直す必要がある場合も、ハーネス移植と混ぜて説明しない。

## Decision Log

以下はこの計画の設計判断である。実装中に変更する場合は、日付、変更理由、代替案、影響する受入条件を記録する。人間による承認が必要な箇所に、Agentが承認者を代入してはならない。

| ID | 判断 | 理由／再評価条件 |
|---|---|---|
| D1 | ハーネスをPythonで実装し、`python -m tools.repoctl` を正規入口にする。 | 既存Python資産を活用する。Goを必須にしない。 |
| D2 | 通常の `verify` は外部LLM・本番API・実ホストCLIを起動しない。 | 認証、課金、モデル変動に通常CIを依存させない。 |
| D3 | 既存validator・installer・Skill内ツールは、責務を保って再利用する。 | 共通ハーネス導入による挙動の同時変更を避ける。 |
| D4 | evalはまずplan／ingest／reportを共通化し、モデル呼出しは外部実行とする。 | RFEの既存設計を維持する。直接provider runnerは将来の別判断。 |
| D5 | installer smokeと実ホストでの発見・読込みを別の検証とする。 | 正しく配置できても、実クライアントが使った証拠にはならない。 |
| D6 | 証拠schemaはM2から導入し、M7で後付けしない。 | 失敗履歴、実行対象、cleanupの記録を最初から残す。 |
| D7 | Plan機能は状態・必須項目・参照・証拠の検査から始める。mergeはmanualとする。 | schedulerやGitHub gate全体の移植を避ける。 |
| D8 | 実環境と人間の判断は独立したhuman-validation Planで扱う。 | ツール実装の完了を実利用の検証済みと混同しない。 |
| D9 | 日本語の既存 `.md` を維持し、今回新設・実質更新する永続文書には `.en.md` を併設する。 | 既存repoの案内を壊さず二言語化する。M1でADRに記録する。 |
| D10 | 「何回通ったか」を不具合修正の主要証拠にしない。 | 対象の不変条件を破るfixtureが実際に失敗することを示す。 |

D9は説明文書とExecPlanを対象とする。`SKILL.md`、識別子、license原文、fixture中の引用を一律翻訳しない。rootの `AGENTS.md` に、ホストが読む共通ルールと英語版への案内を置き、別挙動の指示を作らない。

## Outcomes & Retrospective

M1 棚卸しと baseline を完了した。M2〜M4 は作業中。以下は検証とレビュー終了時に更新する。

- 実装済みの範囲と、native実行で確認したOS／Python版:
- 通常CIに追加できた検証、重複をなくした検証:
- 実ホストで確認したこと／未確認のこと:
- Skill品質を評価したこと／評価していないこと:
- 人間に残した判断と、対応するPlan／case ID:
- 独立レビューの結果、採用しなかった指摘と理由:
- 残った制約、将来の共通化を再検討する条件:
- 実装のmerge commit、archiveの変更:

## Context and Orientation

### 参照snapshot

| Repository | Branch | 確認したcommit |
|---|---|---|
| `mahcialet/agent-skills` | `master` | `d423d1f483e48cfa955b02114c17611c6f2993cd` |
| `mahcialet/agent-env` | `master` | `4e5fec663f493e4546c4d5e93e64dccfe909981f` |

これは2026-09-11の計画作成時点のsnapshotである。実装開始時は `origin/master` と実ファイルを再確認する。新しいbaseへ進んでいても古いcommitへ巻き戻さない。差分と計画への影響を記録する。

### 現行の責務

- `skills/<name>/SKILL.md`: ホスト間で共有する挙動定義。実行時の参照とツールは同じSkill内に閉じる。[S1][S7]
- `scripts/`: 共通validator、READMEカタログ生成、ローカルinstallerと補助処理。
- `tests/`: rootのinstallerテスト。Skill固有のテストは各 `skills/<name>/tests/` にも存在する。
- `docs/architecture.md`: 既存の設計案内。新しいroot `ARCHITECTURE.md` を重複して作らない。
- `.github/workflows/validate-skills.yml`: 読んだbaseではUbuntu／Python 3.12でlintとvalidatorを実行する。[S3]
- `requirements-dev.txt`: 開発用依存。Skill配布物の必須runtime依存とは別物。[S9]

現行catalogにある対象は `reader-first-editor`、`adversarial-pr-review`、`ticket-state` の3つである。catalogの対応ホスト表示を、今回の実ホスト検証成功と読み替えない。[S5]

### 目標の配置

これは責務の配置案である。M1で既存pathを確認し、重複を避けて最終化する。

```text
AGENTS.md                         # 短い入口、正規コマンド、禁止事項
AGENTS.en.md                      # 同じ方針の英語説明
docs/
  index.md / index.en.md           # 文書の案内
  architecture.md / architecture.en.md
  QUALITY.md / QUALITY.en.md
  PLANS.md / PLANS.en.md
  adr/                            # 採用理由・却下理由・再評価条件
  testing/
    harness-contract.md / harness-contract.en.md
    eval-contract.md / eval-contract.en.md
    host-verification.md / host-verification.en.md
  exec-plans/
    draft/ active/ paused/ completed/ abandoned/
tools/repoctl/
  __main__.py                     # argparse、コマンドのdispatch
  runner.py                       # argv、timeout、終了待ち、診断
  tasks.py                        # 検証タスクの定義と構成
  evidence.py                     # 記録とredaction
  docs.py / plans.py              # 文書・Planの検証
  evals.py / hosts.py             # 共通契約、既存処理との接続
  schemas/                       # repo用schema。Skill runtimeから参照しない
scripts/                          # 既存入口を互換wrapperとして残す
skills/<name>/                    # Skill runtimeの自己完結性を維持する
tests/                            # rootの既存テストを維持する
tests/repoctl/                    # 新しいハーネスのテスト
```

negative fixtureの保管場所は既存validatorの全体走査と衝突しない形にする。最初はテスト内で一時リポジトリへ生成する。壊れた `SKILL.md` をcheckout内へ増やし、広い除外規則で隠す方法を既定にしない。

## Plan of Work

### M1 — 棚卸しと契約の確定

**実装すること**

既存のroot／Skillのvalidator、test、eval fixture、installer、CIを一覧にする。各項目について、入力、出力、副作用、必要な依存、起動経路、test discovery方法、現在CIから呼ばれるかを記録する。coverageの意味はコード行数ではなく「どの検証がどの入口から実行されるか」である。

現行baseでbaselineを取得する。成功・失敗・未実行を分け、root installer testsも明示的に実行する。現行失敗があれば保存し、導入作業で直すものと別のreview Planに分けるものを判断する。既存のfailをskipやexpectation変更で隠さない。

`harness-contract` と最小の `PLANS` 方針を作る。Python 3.12を最初の基準とし、他versionを増やす場合は理由と実行環境を記録する。通常のPython／Git以外の必須依存を増やさない。新しいparser依存を追加するなら既存PyYAML等との差分を説明する。

ADRに、D1〜D10、二言語方針、移植しない `agent-env` 機能を記録する。Plan IDの重複も確認する。IDが既に使われていたら未使用番号を割り当て、ファイル内の参照とbranchを一貫して変更する。

**受入条件**

- AC01: 全既存suiteとcontent validatorに起動経路があり、未接続・重複・任意実行が識別されている。
- AC02: baselineと既存失敗の処置が記録され、通常CIと外部評価の境界が確定している。

**停止点**: この棚卸しにより作業量や挙動変更が増える場合、進行を止める対象はその変更だけとする。独立して進められる基盤作業は継続できる。大幅なSkill挙動変更を無言で取り込まない。

### M2 — Portable runnerと証拠の基礎

**実装すること**

標準ライブラリで `--help`、`doctor`、dispatch、構造化診断を作る。依存不足でもhelpを表示できるよう、任意moduleを遅延importする。`doctor` はインストール、ログイン、課金呼出しを行わない。

Python子処理は `sys.executable`、他の処理は検証したexecutableとargv配列で起動する。正規経路でBash／Make／PowerShellを呼ばない。任意の文字列をshell commandへ組み立てない。作業ディレクトリ、環境変数、timeout、終了コード、stdout／stderr、cleanupの契約を統一する。

診断には安定した `ASKILLS-*` code、task ID、対象path、理由、修復の方向を持たせる。negative testは終了コードだけでなく、狙った診断と失敗段階を照合する。

M2からschema version付きのrun結果を用意する。既定はconsole出力、`--out <new-directory>` があるときだけ持続的な結果を保存する。単なる生成や取込の成功と、評価対象の合格を別fieldにする。

installerの公開引数解析、Git source検査、環境分離をPythonの共通経路へ移す。`install_local.py` の低水準helperに未検査値を渡すだけで済ませない。`install-local.sh` は同じPython経路へ委譲する薄い互換入口にする。旧wrapperが保っていたsource判定、copy／link、force、backup、拒否条件を保つ。

**受入条件**

- AC03: shellなしの環境でhelp／doctor／core runnerが動く。未知commandと不正引数は明確に失敗する。
- AC04: 空白・日本語を含むpath、成功／失敗／timeout／中断をテストでき、終了していない所有作業を残して成功を返さない。
- AC05: Pythonと旧shell入口の引数・Git source判定・拒否条件が一致する。source改変、外部backup削除、Git環境汚染による誤参照が回帰しない。
- AC06: 失敗時も証拠が残り、secret sentinelを含む出力・診断・保存結果に漏えいがない。機密値を実データでテストしない。

### M3 — 正規検証入口とnative CI

**実装すること**

タスクを静的検証とテスト実行へ分離する。最低限、次を統合する。

```text
check = lint + Skill/content/fixture構造検証 + docs-check + generated-check
        + checkoutだけで判定できるPlan構造検証

test  = root tests + 各Skillのtests + repoctl tests

verify = check + test + 決定的な隔離installer smoke
```

同じ集約実行の中で同じタスクを二重に実行しない。別々に明示起動されたコマンドを跨ぐ結果cacheは初版では作らない。既存content validatorの内部にもtest起動があれば、棚卸しに従って分離する。

新しいSkillが増えたときにrootの固定名一覧を書き換えずに検証対象へ入ること、存在するsuiteが未登録のまま残らないことを保証する。各Skillのtestは独立したsubprocessで実行し、同名moduleや `sys.path` の混入を避ける。初版はsuiteを逐次実行し、並列化は必要性と隔離を確認して別途判断する。既存 `validate_skills.py` の公開関数を使うconsumerを調べ、互換を保つadapterを残す。旧 `validate-skills.sh` の検証範囲を黙って狭めない。

installerのcore testsはPython入口を使う。Bash wrapperの互換は独立suiteにし、Unix CIで必須実行する。WindowsでBashがないためにcore tests全体がskipされる構成は禁止する。

CIはLinux／macOS／Windows上でPython 3.12のportable検証を実行する。OS固有のコマンドはCIのbootstrap部分に限定する。依存の導入は明示的な準備段階とし、`verify` 自身にpip installをさせない。既存check名を変える前にrequired checkへの影響を確認し、repo設定変更は別途許可された範囲だけにする。CIは毎回未使用の出力先を指定し、失敗時にもredact済みの結果をartifactとして保存する。生の秘密情報を含むlogは公開しない。既存のread-only権限を保ち、信頼していないPRコードへ認証情報を渡す経路を作らない。

現在の条件付き `gh skill` 検証は、実行条件と結果が分かる別checkとして整理する。未実行をportable検証や実host検証の成功と混同しない。

**受入条件**

- AC07: task一覧と実行結果を照合でき、root／Skill／harnessの取りこぼしと集約内の二重実行がない。
- AC08: 必須suiteが0件、対象path欠落、失敗、必須依存不足のどれでも `verify` が成功にならない。
- AC09: 必須3OSで実際のnative CI結果を取得する。workflowを書いただけ、Windows向け構文を読んだだけでは完了しない。
- AC10: 検証中に外部LLM、Backlog／Redmine、本物のhost CLIへ到達しないことをsentinel／fake実行境界で検査する。証拠用出力とcache以外のsource変更もない。

### M4 — 構造・生成物・文書・Planの機械検証

**実装すること**

Skillについて、名前、frontmatter、必須notice、runtime参照の閉包、重複／外部参照を検査する。provider metadataの単語存在検査を強化する場合は、構文とこのrepoが採用した制約を分け、未確認の全provider仕様への適合を主張しない。

READMEカタログは、`skills/*/SKILL.md` と `catalog.json` を入力として再生成できることを確認する。`generated-check` はread-only、`generate` だけが変更する。二言語READMEを扱う場合、各言語の説明metadataを明示し、翻訳をランタイムのLLM処理に依存させない。

文書の案内、相対リンク、anchor、必須metadata、Planの必須節、状態と配置先の一致を検証する。走査対象と例外を明示し、`.venv`、installed skills、ローカル結果、テスト用の壊れた文書をソース文書と混同しない。例外は狭いpathまたは明示分類に限定する。

`AGENTS.md` は150行以下を目安ではなく初版の上限とし、細部は設計・品質文書へ移す。新設・実質更新する永続文書は日本語 `.md` と英語 `.en.md` を揃える。全文のLF正規化hash等で翻訳の参照元を追えるようにするが、hash一致を意味の一致の証明にしない。hashを自動更新してstaleを隠さない。

この段階で `plans list` と `plans check` を用意する。共有Plan IDを持つ翻訳ペアは1論理Planとして扱い、無関係なID重複は拒否する。未完成Planを完成済みとする仕掛けや、自動実行・自動mergeは作らない。

**受入条件**

- AC11: catalog不足／余剰、README drift、壊れた参照、frontmatter不正を注入すると対応する診断で失敗する。
- AC12: missing／orphan／stale翻訳、壊れたindex／anchor、Plan必須節欠落、状態不一致、ID重複を検出できる。
- AC13: `generate` 後の再実行は差分なし。check系はsource・翻訳hashを変更しない。
- AC14: Skillをcheckout外へコピーしたfixtureでも、runtime参照がrepoの `tools/` や別Skillに依存しない。静的検査の見逃し得る動的import等の限界を文書化する。

### M5 — Skill評価の共通契約

**実装すること**

`eval plan`／`eval ingest`／`eval report` を作る。モデル実行を通常runnerへ埋め込まない。既存のeval fixtureを保持し、共通schemaへ無理に書き換える代わりにadapterで読めるようにする。

RFEのproposalに結び付くregressionと、一般のSkill評価planを同一視しない。proposalなしの評価のために偽のrule proposalを生成してはならない。既存のapproval／apply経路を呼ばず、schemaや純粋な集約処理を再利用できる範囲をM1の棚卸しから決める。

共通planは、対象Skill、source指紋、fixture／rubricのdigest、case ID、評価目的、必要なホスト／モデル条件、予定試行、許可する操作を固定する。実行用入力と評価用の期待値・rubricを分け、採点時にモデル出力から期待値を書き換えない。

resultには、実行元、host version、モデル識別子、試行ID、case ID、観測結果、失敗種別、証拠参照を持たせる。公開されないmodel versionは `unknown` と理由を記録し、推測で補わない。架空fixtureでのschema・集約テストは `synthetic` と明示する。

初版は3Skillの全fixtureを棚卸しし、実行できるもの、記述だけで追加設計が要るもの、非対象を区別する。正常・反例・境界例を含む小さな代表集合でplan生成からreportまでを検査する。未変換caseを落として全件合格と表示してはならない。

評価する代表不変条件は、RFEの意味保存と不要編集の回避、adversarial reviewの根拠付き指摘とreview-only無変更、ticket-stateのRead Only拒否とdry-run無書込みを含む。caseの実際の判定可能性と既存仕様を照合して確定する。文章品質の最終判断を単純なキーワード一致へ置換しない。

**受入条件**

- AC15: planの生成・resultの取込・reportの集約が外部モデルなしに動き、RFEの既存regression契約を壊さない。
- AC16: 別revision／別fixture hash／未知case／重複attempt／必要case欠落を検出する。case欠落を合格の分母から取り除かない。
- AC17: 全失敗試行、未実行、timeout、集約上の除外理由が残る。成功試行だけを選んでreportを作れない。
- AC18: synthetic／モデル実行の観測／人間判断が別に表示され、plan生成成功だけでは「Skill評価PASS」にならない。

実モデルの実行は明示許可のある別操作である。費用・最大試行数・使用モデル・送信可能なデータを人間が決める。認証済みという理由だけで起動しない。

### M6 — 隔離installer smokeと実ホスト検証

**実装すること**

`install-smoke` は決定的なローカル検証として実装する。一時repo／一時homeへ現物Skillを配置し、source不変、配置構造、必要な同梱資産、scope、backupの探索範囲外配置、衝突・force・linkの契約を検査する。rootの実 `.agents/skills` を検証先にしない。既存テストの責務を再利用し、同じシナリオを無意味に三重化しない。

別の `host-verify` は、明示的な `--kick`、対象host、executable、検証profile、未使用の出力先を必要とする。初版の目的は実クライアントによる発見・読込みの確認であり、生成文章の品質評価ではない。providerの現行help／公式文書に基づいてadapterを作る。存在を確認していない一覧APIやCLI optionを推測で実装しない。[S12][S13]

host固有の機械的なdiscovery手段がない場合は、実ホスト観測が未完了であることを返し、人間向け手順へ渡す。モデルに「読めました」と言わせるだけの出力をdiscovery証拠にしない。モデル実行が必要な経路は、非課金のdiscoveryと別の許可・評価経路で扱う。

**隔離の契約**

- 一時領域はcheckoutの外に置き、親ディレクトリのSkillや指示を拾わない構成を選ぶ。
- HOMEだけでなく、OSのuser profile、XDG、host設定、追加Skill path、Git設定、認証、hook／MCP／plugin探索を棚卸しする。
- 環境変数は必要な値だけを渡す。system/admin設定を隔離できないときは、その限界を記録して実行をBLOCKEDにするか、明示した隔離環境へ切り替える。
- `HOME` の変更をセキュリティsandboxと呼ばない。任意コードの封じ込めが必要なscenarioは、この仕組みだけでは許可しない。
- 通常smokeに認証情報を渡さない。実ホストで認証が必要な場合も、人間が指定した最小限のテスト用経路だけを使い、設定directoryを丸ごとコピーしない。
- 実行前後にcanaryで指定した外側ファイルの不変を確認する。実home全体を走査・保存して機密情報を集めない。
- cleanupは作成した資産だけを対象とする。子処理の終了を待ってから一時領域を消す。所有を確定できない資産は保全し、失敗として記録する。

**受入条件**

- AC19: `install-smoke` が3OSでnative実行される。各scopeの配置契約と無許可の外側変更がないことを確認する。
- AC20: fake hostでprofile検査、認証なし、設定混入、失敗、中断、child終了待ち、外側保全を検証する。
- AC21: 明示した実hostの未導入／非対応／認証不足／隔離不足はBLOCKEDになり、smoke成功を実host成功へ格上げしない。

copy-modeを必須のportable基準とする。symlink権限等に左右されるmodeは能力別に表示し、選択されたmodeが利用不能ならBLOCKEDにする。必須のcopy-modeをskipへ落とす逃げ道にはしない。

### M7 — 人間への引継ぎと最終統合

**実装すること**

人間が確認するcase、準備すべきもの、機械preflight、期待される観測、証拠保存先、失敗時の復旧を1セットにする。これを独立した `human-validation` Planとして `docs/exec-plans/draft/` に置く。候補IDは `EP-HARNESS-002` とし、未使用を確認する。

human Planは `execution_mode: human-kick`、`merge_policy: manual`、本実装へのmerged依存を持つ。手順と記録様式の用意はこの実装の責任だが、人間の操作・判断をAgentが完了扱いにしてはならない。予定日や認証情報が埋まっていても自動実行しない。

最低限、次の確認項目を含める。

| Case | 人間が確認すること | 機械で用意する証拠 |
|---|---|---|
| HV01 | 新規セッションがAGENTSだけを入口に、対象Skillと正しい検証を見つけられるか。 | 読んだpath、実行argv、結果、未実行理由の記録。内部思考は不要。 |
| HV02 | 実Codex CLIで対象Skillが意図したscopeから発見・読込みされるか。 | version、隔離profile、配置hash、実ホストの観測。 |
| HV03 | 実Copilot CLIでも同じ契約を満たすか。 | HV02と同じ項目。片方の成功を流用しない。 |
| HV04 | RFEの改稿が意味を保ち、必要な編集に留まるか。 | source／output／rubric／差分、評価planとattemptへの参照。 |
| HV05 | review-onlyでsourceを変更せず、指摘が根拠に対応しているか。 | 前後hash、指摘と根拠の対応、採否の記録。 |
| HV06 | ticket-stateのRead Only・dry-runが実利用手順でも守られるか。 | fake／専用test環境のrequest記録、diff、未反映項目。既定で本番接続しない。 |
| HV07 | BLOCKED・失敗・中断の表示から、次の行動と復旧範囲を判断できるか。 | 故障注入run、未終了資産、復旧手順、失敗履歴。 |

各caseの記録には `PASS`／`FINDING`／`BLOCKED`／`NOT_RUN`、観測者、対象revision、証拠、説明、次の対応を持たせる。観測者名の文字列は認証済み承認の証拠ではない。FINDINGはreview PlanまたはIssueへ結び付け、勝手に修正・棄却しない。

最後に、root指示からの発見、通常verify、eval protocol、installer smoke、未実行のhost評価、人間の残件までを一通り辿る。独立レビューは実装Agentと別のcontextで行い、同じreportの自己承認で済ませない。発見内容は採用／却下／延期と根拠を記録する。

**受入条件**

- AC22: 確認事項・ログ／結果様式・human Planの3点が揃い、人間が会話履歴なしで開始できる。
- AC23: 不足条件と人間の判断が残件として見え、機械がhuman Planを自動実行・自動完了しない。
- AC24: AC01〜AC23、文書の二言語review、独立レビュー、native CIの証拠を照合できる。

**重要な完了境界:** 本Planはハーネス実装のPlanであり、全モデル・全hostのSkill品質を承認するPlanではない。実hostの観測や人間の意味評価が未実施でも、独立したhuman Planが未完了であることを明示して、ツール実装だけの受入判断を行える。実host検証済み・Skill品質確認済みという主張は、対応するcaseの直接証拠が揃うまで禁止する。

## Concrete Steps

### 1. 実装開始前

リポジトリにまだ変更を入れず、次を確認する。

```text
git status --short
git branch --show-current
git rev-parse --show-toplevel
git fetch origin
git rev-parse origin/master
```

`AGENTS.md`、`CONTRIBUTING.md`、既存の設計・インストール・互換文書を読む。未commitのユーザー作業や別Agentの変更を検出したら、上書き、stash、reset、cleanを勝手に行わない。必要なら別のworktreeを使い、その場所と所有を記録する。

branchが存在せず、作業領域が安全なことを確認できた場合だけ作る。

```text
git switch --create feat/ep-harness-001 origin/master
```

既存branchを再開する場合は、そのbase、Plan ID、内容を照合する。同名branchを強制的に作り直さない。確認したbase SHAと、計画snapshotから変わった点を記録する。

実装指示によるpromotionを記録し、計画を次へ配置して `status: active` にする。M1のbaseline以降の挙動変更へ進む条件が満たされたことも記録する。

```text
docs/exec-plans/active/EP-HARNESS-001.md
```

英語版は同directoryの `EP-HARNESS-001.en.md` に作成する。ID、状態、branch、依存、受入条件を一致させる。片方を別Planとして数えない。

### 2. 現行baseのbaseline

以下は現行Python側の検証入口であり、新ハーネスではない。プロジェクト用venvへ現行requirementsを明示的に導入してから実行する。`python` はそのvenvの実行ファイルを指すものとし、Debianの `python3`、Windowsのvenv pathなど実環境で解決する。

```text
python -m ruff check .
python scripts/validate_skills.py .
python scripts/generate-catalog.py --check
python -m unittest discover -s tests -p "test_*.py"
git diff --check
```

現行root installer testsにはBashが必要である。M2前にWindowsで動かせない場合は、baselineの制約として記録する。portable化後のnative合格へ読み替えない。既存CI入口 `./scripts/validate-skills.sh` はPython validatorとroot installer testsを両方起動する。上の分解したbaselineは、それぞれの責務を見えるようにするためのもの。root validatorが既に呼ぶSkill testsやcatalog checkの重複はbaselineでは記録し、M3で解消する。

### 3. 段階的な実装とcheckpoint

M1→M2→M3→M4を最初のレビュー可能な単位とする。ここで新規Agentが正規の入口から、既存Skillを漏れなく検証できることを確認する。その後の M5→M6→M7 は別の明示指示を受けてから進める。今回の限定指示では着手しない。

各checkpointで、現在地、変更した不変条件、実行証拠、残件、scope逸脱の有無をPlanへ反映する。小さな目的別commitを作り、許可された運用に従ってpushする。pushやmergeをハーネスコマンド自身に実装しない。公開済み履歴をforce pushで書き換えない。

部分mergeを選ぶ場合は、対象を子implementation Planと別branchへ分け、親の残件を残す。M4までmergeしたことを、M5〜M7や本Plan全体の完了としない。

### 4. 導入後の正規入口

以下は目標のコマンドである。実装されたmilestoneに対応するものだけを利用可能として文書化する。

```text
python -m tools.repoctl doctor
python -m tools.repoctl check
python -m tools.repoctl test --list
python -m tools.repoctl test
python -m tools.repoctl verify
python -m tools.repoctl docs-check
python -m tools.repoctl generated-check
python -m tools.repoctl plans list
python -m tools.repoctl plans check
```

次は出力先を指定する例である。各 `<new-directory>` は別の未使用directoryに置き換える。同じrunの失敗結果へ上書きしない。

```text
python -m tools.repoctl verify --out <new-directory>
python -m tools.repoctl eval plan --skill reader-first-editor --out <new-directory>
python -m tools.repoctl eval ingest --plan <plan.json> --input <result.json> --out <new-directory>
python -m tools.repoctl eval report --plan <plan.json> --runs <runs-directory> --out <new-directory>
python -m tools.repoctl install-smoke --host codex --out <new-directory>
python -m tools.repoctl install-smoke --host github-copilot --out <new-directory>
```

実ホスト検証は明示許可された独立操作とする。

```text
python -m tools.repoctl host-verify --host codex --executable <absolute-path> --profile <profile.json> --kick --out <new-directory>
python -m tools.repoctl host-verify --host github-copilot --executable <absolute-path> --profile <profile.json> --kick --out <new-directory>
```

`--kick` は操作を明示する入力であり、認証された人間の承認を証明する機構ではない。実行Agentは、人間が指示した範囲に限って使用する。

### 5. Mergeとarchive

最終受入時は、exact revisionのnative CI、受入表、独立レビュー、文書更新、残件を照合する。merge許可は人間から得る。Planは未mergeの間、実装が終わっていてもactiveのままにする。

merge後は、実際のdelivery merge commitが `origin/master` のancestorであることを確認する。未来のmerge SHAを計画へ予測記入しない。必要なら別の小さなarchive用変更で `merge_commit`、retrospective、状態を更新し、両言語Planをcompletedへ移す。移動に伴うindexとリンクも更新する。

## Validation and Acceptance

### 証拠の分類

証拠の分類は互いの代用品ではない。[S11]

| Class | 証明する範囲 | 代用してはいけないもの |
|---|---|---|
| Forced invariant | 既知の違反状態を作り、期待したoracleが検出すること。 | 全OSの実挙動、全interleaving。 |
| Direct native / integration | 記録したOS・version・資産での実行。 | 他OS、未導入host、本番環境。 |
| Structural / tooling | schema、構造、lint、drift等の規則。 | 意味保存、文章品質、hostによる発見。 |
| Model observation | 指定条件・指定試行でのモデル出力。 | 他モデル、全ての将来出力、人間の承認。 |
| Human observation | 指定caseに対する人間の観測と判断。 | 認証済みmerge承認、未確認case。 |
| Repetition / stability | 指定回数の観測結果。 | 因果的な再現、強い証拠classへの格上げ。 |

新しく追加したvalidatorには、不正なfixtureを入れると、狙った段階・診断で失敗するテストを置く。不具合修正には、可能な限りfail-before／pass-afterの対照を用意する。例外が必要なら、なぜ対照を作れないかと、代わりの証拠の限界を記録する。

並行処理やcleanupのテストは、sleep時間や反復回数だけで競合を待たない。barrier、event、pipe等で検査する順序を制御する。cancel要求、client側の終了、server／子処理の終了を別の事実として検査する。

### 必須の故障注入

| 対象 | 最低限のnegative control |
|---|---|
| task discovery | root suiteを未接続にする、必須suiteを0件にする、同一taskを重複登録する。 |
| runner | 子処理が非zeroで終了、timeout、cancel後も所有作業が継続、結果保存が失敗する。 |
| docs／catalog | 片方の言語だけ更新、anchor破損、catalog余剰・不足、生成部分の手編集。 |
| installer | 汚染Git環境、外側path参照、衝突、source変更、権限不足、rollback失敗。 |
| eval | 古いdigest、別Skill、欠落case、同一attempt重複、syntheticをliveと偽装する入力。 |
| host | fake executable、設定／認証の混入、未対応discovery、外側canary変更。 |
| lifecycle | draft自動選択、human自動起動、merge前completed、欠落参照、翻訳間不一致。 |

syntheticをliveと偽装する入力の検出は、信頼されたrunner側metadataとの照合範囲に限る。外部callerの自己申告だけで実実行の真偽を認証できるとは主張しない。証拠の作成者と検証範囲を残す。

### 受入記録の様式

AC01〜AC24ごとに、次を1行以上記録する。run回数だけを証拠欄へ書かない。

```text
criterion_id:
invariant:
revision / dirty_fingerprint:
command / cwd:
environment:
evidence_class:
expected_failure_stage:
result: PASS | FAIL | BLOCKED | NOT_RUN
artifact_reference:
limits:
finding_disposition:
```

初版の必須native matrixはLinux／macOS／Windows × Python 3.12。追加version、WSL、別architectureの検証は別行にする。3OS必須の一部が未実施なら、実装完了チェックを付けずactiveまたは理由付きpausedとする。変更前revisionのCI結果を、その後の実装修正の受入証拠として流用しない。

## Idempotence and Recovery

- `doctor`、`check`、`test --list`、`docs-check`、`generated-check`、`plans list/check` はsourceやPlan状態を変更しない。cache／一時領域は契約に従う。
- `generate`、実installer、eval保存、host検証は副作用を持つ操作として明示する。`check` から自動修復を呼ばない。
- run出力先は未使用pathを要求する。再試行は新run IDで保存し、失敗runを消したり上書きしたりしない。
- 永続結果はatomic writeを基本とする。書込失敗・容量不足・中断を成功へ変換しない。失敗内容をconsoleにも返す。
- 一時資産には所有者とrun IDを記録する。終了確認前にdirectoryを削除しない。所有が不明なprocessやpathへ広範なkill／deleteを行わない。
- 既存installerのbackupとrollbackを維持する。cleanup／rollbackが失敗した場合は、復旧に必要な情報と残存資産を保全する。
- `.venv`、個人のglobal instructions、認証設定、実ユーザーのinstalled skillsをまとめて作り直さない。
- 中断からの再開では、Plan、Git状態、直前run、残存資産を再確認する。記録上の進捗から実行済みを推測しない。
- 元の実装へ戻す必要がある場合、未公開の自分の作業範囲だけを安全に戻す。共有履歴は目的別revertを使い、force pushしない。

## Artifacts and Notes

### 実装が残す成果物

正規コマンドとtests、harness／eval／hostの契約、品質方針、最小Plan方針、ADR、二言語の案内、CI、独立human Planを残す。生の実行証拠は既定でGitに入れない。追跡対象のPlanには、secretを除去した短い結果、artifact識別子、対象revision、制約を記録する。

ローカルの証拠pathを、別環境のCIでも必ず存在する文書リンクとして扱わない。CI artifactの寿命とローカル保存先の可搬性を区別する。実行時のGitHub応答、コメント全文、review本文等のミラーをrepoへ保存しない。判断に必要な最小の参照だけを記録する。

### Run evidenceの最小契約

```text
schema_version
run_id / parent_run_id / attempt_id
command_id / redacted_argv / cwd
source_commit / source_fingerprint / dirty_state
selected_tasks / task_results / omitted_tasks_with_reasons
environment: os / architecture / python / relevant_tool_versions
operation_result                         # コマンド処理そのものの成否
subject_result                           # 検証対象の判定。未評価ならNOT_RUN
started_at / ended_at / duration
exit_code / failure_kind / diagnostics
evidence_class / provenance_kind
stdout_stderr_artifact_references
owned_resources / cleanup_result
limitations
```

環境変数を丸ごと保存しない。秘密値を含み得るargv、endpoint、path、stdout／stderrをredactする。redactionのために必要な秘密値そのものは証拠へ書かない。出力上限を超えた場合は切詰めを明示し、必要な判定材料が欠けたrunを完全な証拠にしない。

### 参照資料

計画内の[S番号]は以下を指す。実装時に可変情報を再確認する。GitHub参照は固定commitを使い、現行状態の判断は最新baseを別途読む。

**agent-skills — `d423d1f483e48cfa955b02114c17611c6f2993cd`**

- [S1] `AGENTS.md` — 共通Skill定義、runtimeの自己完結性、日本語基本、変更ルール。
- [S2] `scripts/validate_skills.py` と `scripts/validate-skills.sh` — 現行の検証構成。shell入口はPython validatorに加えてroot installer testsを直接実行する。
- [S3] `.github/workflows/validate-skills.yml` — 現行CI入口。
- [S4] `tests/test_install_local.py` — root installer testsとshell依存。
- [S5] `scripts/generate-catalog.py` および `catalog.json` — カタログの入力と生成部分。
- [S6] `scripts/install-local.sh` — 引数、Git環境分離、source判定、Python helperへの委譲。
- [S7] `docs/architecture.md` — Skillの境界と既存RFE育成基盤。
- [S8] `skills/reader-first-editor/docs/agent-investigation.md` — provider-neutralなplan／ingest／reportと人間判断の境界。
- [S9] `requirements-dev.txt` — 開発用依存。

固定参照のURL形式:

```text
https://github.com/mahcialet/agent-skills/blob/d423d1f483e48cfa955b02114c17611c6f2993cd/<path>
```

**agent-env — `4e5fec663f493e4546c4d5e93e64dccfe909981f`**

- [S10] `docs/PLANS.md` — 必須12節、branch、lifecycle、mergeとarchive、human-kick。
- [S11] `docs/QUALITY.md` — 検証入口、native証拠、証拠class、fixture completion。
- 補助参照: `docs/adr/0004-repository-native-harness.md` — 短い指示、設計案内、永続文書、機械検証を一体にする理由。

```text
https://github.com/mahcialet/agent-env/blob/4e5fec663f493e4546c4d5e93e64dccfe909981f/<path>
```

**公式host文書 — 2026-09-11確認。CLI optionや認証手順は実装時に再確認する。**

- [S12] OpenAI: Build skills / Where Codex loads local skills。
- [S13] GitHub: About agent skills / Copilotのproject・personal skill配置。

```text
https://learn.chatgpt.com/docs/build-skills
https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
```

これらの公式文書は探索pathの根拠であり、今回のrepoの実ホスト検証証拠ではない。専用の非課金discovery APIが全hostに存在することまでは確認していない。

## Interfaces and Dependencies

### コマンドの契約

| Command | 主な責務 | 副作用／必要条件 |
|---|---|---|
| `doctor` | 必須tool・依存・実行環境の診断。 | 読取りのみ。導入・認証・モデル起動なし。 |
| `check` | lint、構造、文書、生成drift。 | source不変。テストやモデルの暗黙起動なし。 |
| `test` | root／Skill／harness tests。 | 一時fixtureのみ。`--list` は実行しない。 |
| `verify` | 必須の決定的検証を集約する。 | CI用。モデル・本番API・実host CLI不要。 |
| `docs-check` | 文書、翻訳、リンク、Plan構造。 | network不要、source不変。 |
| `generated-check` / `generate` | README等の生成内容を検査／更新する。 | 更新するのは明示 `generate` だけ。 |
| `install` | 公開installer契約のportableな入口。 | 明示されたscopeを変更。既存引数と防御を維持。 |
| `install-smoke` | installer契約と同梱物の確認。 | 一時領域のみ。実host CLI不要。 |
| `eval plan/ingest/report` | 評価plan、結果検査、集約。 | 明示出力先のみ。モデルは起動しない。 |
| `host-verify` | 指定実hostの発見・読込み観測。 | kick、profile、明示executable、証拠出力が必須。 |
| `plans list/check` | Planの案内、状態・参照の検査。 | 状態変更、Agent起動、Git書込みなし。 |

公開host識別子は既存installerに合わせて `codex`／`github-copilot` を正規形にする。表示名と内部aliasは別物とし、`copilot` aliasを追加する場合は明示的な互換テストを置く。

### 終了結果

正規コマンドの終了コードは、`0 = 要求された処理の成功`、`1 = 検証失敗`、`2 = 使用法・入力契約の不正`、`3 = 前提不足／未完了のためBLOCKED` を初版案とする。ユーザー中断は `130` を正規化した結果として記録する。既存wrapperの終了コードを変更する場合は互換を調べ、adapterで保つか変更を明記する。

生成・ingestがexit 0でも、対象Skillの `subject_result` は `NOT_RUN` または取込んだ観測に従う。`verify` は必要な全taskがPASSのときだけexit 0にする。選ばれていない外部評価は `NOT_REQUESTED` と表示し、PASS件数へ入れない。明示した検証が実行不能ならBLOCKEDであり、黙ってskip成功にしない。

### 依存の向き

```text
repoctl → rootの共通処理／各Skillのvalidator・test・eval adapter
Skill runtime → そのSkillに同梱した処理と参照
Skill runtime ↛ repoctl／別Skill／repo専用docs
```

通常ハーネスの依存はPython、Git、既存の開発用依存を基本とする。Docker、Go、Node、Codex、Copilot、LLM認証を通常 `verify` の前提にしない。GitHub CI上の依存取得と、検証コマンド内部の外部接続も区別する。

### 最小Plan lifecycle

`draft`／`active`／`paused`／`completed`／`abandoned` を使い、directoryとstatusを一致させる。IDは固定し、`plan_type`、base、branch、owner、日付、merge policyを明示する。pausedには理由と再開条件、abandonedには理由、completedには到達可能なdelivery merge commitを要求する。

親子参照や依存を使う場合は、参照の存在、自己参照、循環を検証する。親子関係と実行依存を混同しない。draft・paused・human-validationを自動実行しない。このPlanはscheduler、stacked branch自動選択、GitHubの自動merge gateを導入しない。

`docs-check` はcheckout上の構造検査、`plans check` は必要に応じたローカルGitの到達性検査を担う。後者のCIには必要なGit履歴を用意し、履歴不足を構造の成功で代用しない。remote freshnessが必要な判断の前には、実行者が明示的にfetchしてから判定する。

## Execution Checkpoint — M1–M4 scope

- 2026-09-11: 現行 `AGENTS.md`、CONTRIBUTING、architecture、installation、compatibility、CI、validator、installer を再読した。Plan ID の既存重複なし。base は計画 snapshot と一致し巻戻しなし。
- 作業領域／branch: `/home/mahcialet/work/git_work/marmite/agent-skills`、`feat/ep-harness-001`。supplied root Plan は削除しない。active pair 名には Plan ID を採用する（配置責務は元計画と同じ）。
- baseline revision: `d423d1f483e48cfa955b02114c17611c6f2993cd`。`.venv/bin/python` 3.13.5／Linux。`ruff check .` PASS、`python scripts/validate_skills.py .` PASS（3 Skill と Skill suites）、`python scripts/generate-catalog.py --check` PASS、`python -m unittest discover -s tests -p "test_*.py"` PASS（33 tests、5.315s）。実装前の native/integration と structural evidence。現行の失敗を skip していない。
- native Python 3.12 は現在 PATH 上にない。3 OS × Python 3.12 の exact revision CI 証拠は未取得。workflow 作成だけを AC09 PASS にしない。
- M3 の verify smoke は元計画上 M6 の実装と依存する。今回の指示を優先して standalone smoke を未実装・`NOT_REQUESTED` とし、check/test を実装する。M3 全体チェックと AC09 は必要な証拠が揃うまで未完了。
- 読取り確認: `master` branch-protection required-status API は 404（保護なし）。既存 check 名 `validate` を集約 job で維持する方針。repo 設定は変更しない。
- M5〜M7、実モデル、実ホスト、本番 API、merge は未着手。承認の拡大は推定しない。
- 独立レビュー、最終コマンド、dirty fingerprint、AC03〜AC14 の細目と残件は M4 checkpoint で追記予定。現時点で未検証の受入を PASS としない。
- M2 STOP POINT: 既存 installer transaction の `fcntl`、`dir_fd`、`flock`、`pthread_sigmask` 依存により native Windows は安全な移植の別設計が必要。既存防御を外さず Python 公開入口は Windows 実配置を `ASKILLS-INSTALL-PLATFORM`／exit 3 で BLOCKED とする。core suite を丸ごと skip しない。AC05 の portable 完了と AC09 は未達のため M2／M3 を完了チェックしない。独立した runner・検査・POSIX 互換の作業は継続する。

### M4 実行証拠と受入台帳（2026-09-11）

共通対象は base `d423d1f483e48cfa955b02114c17611c6f2993cd` 上の未commit作業、cwd `/home/mahcialet/work/git_work/marmite/agent-skills`、Linux 6.12.107+deb13-amd64／Python 3.13.5。最終コード検証の dirty fingerprint は `69ea0e0104fe7825bbfa033a65f3b8861dd02dff4ef93a84c62f622be8fc47ae`。以下の記録追記はその run 後の文書変更であり、同じ fingerprint の検証済みと偽らない。日英ペア・hashを揃え、文書検査を再実行する。

- E1: `.venv/bin/python -m tools.repoctl verify --out .repoctl/m1-m4-final`。run `20260910T201108Z-b4b58230be19`、13 tasks PASS、exit 0、operation／subject／cleanup PASS、14.69s。root 44、adversarial 30、RFE 186、ticket-state 124、repoctl 17、合計401 tests。8 static tasks と5 suites、同一集約内に重複なし。参照 `.repoctl/m1-m4-final/summary.json`（明示保存したローカル証拠、Git 非追跡）。class は Direct local integration と Structural/tooling。実モデル・実ホストの証拠ではない。
- E2: `.venv/bin/python -m tools.repoctl doctor --out .repoctl/m1-m4-doctor` PASS。operation PASS、subject NOT_RUN。前提診断を対象品質の合格へ昇格しない。
- E3: `.venv/bin/python -m tools.repoctl plans check --out .repoctl/m1-m4-plans` PASS。local Git 到達性を検査する経路。CI の remote freshness／native 結果の証明ではない。
- E4: `tests/repoctl/test_validation.py` と `test_runner.py` の forced fixtures（E1 内で17 tests PASS）。dynamic discovery、空 suite、重複／欠落 task、文書破損、Plan state/section/reference/cycle、shallow history、生成 drift／再生成不変、Skill の checkout 外コピーと外部 runtime 参照拒否を確認。機械 fixture はモデル観測ではない。
- E5: installer の公開 Python／shell compatibility／既存 transaction tests（E1 root 44 tests PASS）。汚染 Git 環境、Git 不在／non-Git／unborn／HEAD、拒否条件、copy／collision／force／backup を検査。native Windows は BLOCKED。既存防御を弱める実装は延期。
- E6: E1 後の独立review修正を `python -m unittest discover -s tests/repoctl` で再検証し17 tests PASS（0.625s、console）。timeout fixture を child-ready／parent-ready handshake に変更し、準備完了後だけ timeout を注入、owned group の SIGKILL と親 reap を照合した。これは E1 fingerprint より後の変更として区別する。最終技術reviewは既知 blocker の修正を独立再検証済み。
- E7: 互換 wrapper の必須 precommit 検証履歴を保持した。`.repoctl/m1-m4-precommit`（run `20260910T201431Z-4c57cadfd62b`、fingerprint `50e024ae8f31176ad9140f6c9fbbf748b8b008359acb88f3400ea576f2df8f94`）は system Python に Ruff がなく BLOCKED／exit 3。venv を PATH の先頭にした `.repoctl/m1-m4-precommit-venv`（run `20260910T201513Z-5f6a25e3d7b8`、fingerprint `05acb869fabd1d933ab1bc2c9dbec38252fc0a78ac2a04f1d8aed42328d470c1`）は文書更新中の source／翻訳hash不整合を正しく捕捉し FAIL／exit 1。両言語とmanifest確定後、docs-check `.repoctl/m1-m4-docs-recorded`（run `20260910T201603Z-9a92185df022`）は PASS。`env PATH=<repo>/.venv/bin:$PATH ./scripts/validate-skills.sh --out .repoctl/m1-m4-precommit-final`（run `20260910T201625Z-38a1714297c7`）は13 tasks／401 tests PASS、exit 0、13.41s。後二者の fingerprint は `4077e5a1d48d0f6511020cd2e424af55b438a5d880d80d8d5f660d53e226f7bc`、全4 run の base は `d423d1f483e48cfa955b02114c17611c6f2993cd`＋dirty。失敗結果は上書きせず別directoryで保存。ここへの E7 追記自体はこの証拠より後なので文書再検査する。installer の局所 commit `38321ef` はその後作成済み。push／native CI／merge は未実施。

| AC | 不変条件と証拠／失敗段階 | 結果 | 限界・処置 |
|---|---|---|---|
| AC01 | M1 到達範囲表、E1 task ID と suite 照合 | PASS | base CI の任意 gh check は今回は実ホスト禁止により未実行。 |
| AC02 | base baseline と E1 の分離、外部評価境界 | PASS | baseline は Linux/Python 3.13.5 のみ。 |
| AC03 | help／doctor／argv dispatch、E2 と runner tests | PASS（local） | shell 非依存の正規経路。3OS native を証明しない。 |
| AC04 | E4/E6 timeout／nonzero／cancel／owned-child 残存検出 | PASS（POSIX 範囲） | Windows child 終了は UNVERIFIED。timeout は ready handshake 後に注入する forced invariant であり、全 OS の証明ではない。 |
| AC05 | E5 共通 Python 入口と shell 比較 | BLOCKED（portable 全体） | POSIX44 tests PASS、Windows transaction は未移植。安全な backend 設計が残件。 |
| AC06 | E4 永続失敗記録、argv／JSON／token sentinel redaction、operation/subject 分離 | PASS（local fixture 範囲） | 実秘密不使用。任意未知の秘密表現の完全検出を主張しない。 |
| AC07 | E1 13 tasks、E4 新 Skill discovery／重複／root 欠落 | PASS | 逐次独立 subprocess。別コマンド間 cache は未実装。 |
| AC08 | E4 空 suite／欠落 path／重複／依存不足 oracle | PASS | 未実行は BLOCKED／ERROR、skip成功にしない。 |
| AC09 | 3OS × Python 3.12 native CI | NOT_RUN | workflow 設定のみ。push/native CI 許可への回答なし、実行結果なし。M3 完了扱い禁止。 |
| AC10 | E1 のローカル argv／mock API 検査、外部起動なし | NOT_RUN（完全 sentinel 受入） | verify 全体の外部実行 sentinel と source 前後不変の専用対照は未確認。構造上の境界を実行隔離の完全証明としない。 |
| AC11 | E4 README drift／外部参照／frontmatter 故障注入 | PASS（記録した fixture 範囲） | catalog 不足／余剰個別 oracle の追加確認は残件。 |
| AC12 | E4 missing/orphan/stale、index/anchor、Plan sections/state/IDs | PASS | Markdown inline links と ATX/HTML anchors の静的範囲。 |
| AC13 | E4 再生成 byte 一致、check の drift 不修正 | PASS（fixture 範囲） | 最終 Plan 記録更新後の hash は日英review後に明示更新。 |
| AC14 | E4 checkout 外 Skill コピー／runtime 外部参照拒否 | PASS（静的範囲） | 動的 import や任意 runtime の完全解析ではない。 |
| AC15 | model-free eval plan／ingest／report | NOT_RUN | M5 は指示範囲外、未着手。 |
| AC16 | eval digest／case／attempt 検証 | NOT_RUN | M5 未着手。 |
| AC17 | eval 失敗・未実行・集約履歴 | NOT_RUN | M5 未着手。 |
| AC18 | synthetic／model／human の評価区分 | NOT_RUN | M5 未着手。M2 の operation/subject field だけを評価機能と呼ばない。 |
| AC19 | 3OS installer standalone smoke | NOT_RUN | M6 未着手。既存 installer tests から昇格しない。 |
| AC20 | fake-host profile／設定・認証隔離／cleanup | NOT_RUN | M6 未着手。 |
| AC21 | live-host BLOCKED と smoke の区別 | NOT_RUN | 実ホスト未起動、M6 未着手。 |
| AC22 | human case／様式／独立 Plan | NOT_RUN | M7 未着手、EP-HARNESS-002 未作成。 |
| AC23 | human 判断と自動実行禁止の引継ぎ | NOT_RUN | M7 未着手。Plan validator の禁止検査は部分証拠に限る。 |
| AC24 | 全AC／二言語／独立review／native CI 照合 | NOT_RUN | 今回は限定 checkpoint。native matrix と M5〜M7 が未完了。 |

### 独立レビューと残件

- 別 context の reviewer が runner/evidence を点検し、既定の永続出力、token/JSON/argv の秘密漏えい、timeout／親成功後の owned-child 残存、処理結果と対象結果の混同を指摘。採用して修正し、E1 の回帰 tests と versioned record で確認した。
- 別 context の validator reviewer が不正 frontmatter delimiter、manifest path、children cycle、shallow Git 到達性の誤分類を指摘。採用して専用 fixture を追加し、E4 で確認。履歴不足は BLOCKED とする。
- 最終の別 context 技術reviewで既知 blocker の修正を再検証済み。timeout fixture の sleep 依存も E6 で解消した。Windows と未実施 native の残件は review 合格へ昇格していない。
- 別 context の二言語 reviewer が AGENTS／QUALITY／PLANS／ADR／harness contract／architecture を比較。主要不変条件・限定範囲の意味差なし。installer helper の誤名を指摘し両言語で `scripts/install_local.py` に修正。source hash 一致を翻訳品質の唯一の証拠にしなかった。ExecPlan の受入追記部分はこの時点の review より後なので別に確認する。
- Windows installer の安全な backend と Windows process-tree cleanup の native 証拠は延期。既存 POSIX 防御を外す修正は採用しない。M2／M3 の全面完了を主張しない。
- native 3OS CI、AC10 の完全 sentinel、AC11 の catalog 両方向故障注入の個別確認が残る。M5〜M7、実モデル・実ホスト、merge は今回未着手。commit／push／merge はこの checkpoint では実施していない。
