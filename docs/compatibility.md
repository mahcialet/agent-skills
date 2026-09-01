# 互換性

この文書では、公式資料で確認した仕様、ローカル環境で実機確認した動作、
`reader-first-editor` の受入監査、既知の制約を分けて記録する。各検証結果が示すのは、
記載したversion、確認範囲（scope）、実行条件での動作だけであり、将来のhost versionでの
動作は保証しない。

## 確認済みの組合せ

| 対象 | 確認したversion | 確認した範囲 | 既知の制約 |
|---|---|---|---|
| GitHub CLI | 2.97.0 | Skillの検出、ローカル作業ツリーからのインストール、`publish --dry-run` | public preview。tag protection未設定のwarningが残る |
| Codex CLI | 0.151.0 | `reader-first-editor` の明示起動、通常review、`repository-review` | 同名のuser scopeとproject scopeが併存する環境では正式名が一覧に表示されず、再確認が必要 |
| Codex CLI | 0.152.0 | 長文coverage、関係candidate、DB局所整合性、Skill検証dataの証拠除外 | 同名scope衝突を避けた一時的な固有名で確認 |
| Codex CLI | 0.151.0 | project scopeから `adversarial-pr-review` を明示起動し、review contractとapproval境界を確認 | 単一のsynthetic tenant越境ケースで確認。Copilot CLIとはpriority判定が異なった |
| GitHub Copilot CLI | 1.0.82 | project scopeから正式名で `reader-first-editor` を起動 | 関係表現の確認では、Skillをテスト用リポジトリ内へ実コピーする必要があった |
| GitHub Copilot CLI | 1.0.82 | 正式名で長文coverage、関係candidate、DB局所整合性、Skill検証dataの証拠除外を確認 | 一時リポジトリへSkillを実コピーして確認 |
| GitHub Copilot CLI | 1.0.82 | project scopeから正式名で `adversarial-pr-review` を起動し、review contractとapproval境界を確認 | `write`、`shell`、URL accessを許可しない単一のsynthetic tenant越境ケースで確認 |
| GitHub Copilot CLI | 1.0.81 | project scopeから正式名で `adversarial-pr-review` を起動 | 複数domainを一度に扱う長いreviewは最終版で未確認 |

以下では、仕様の参照先、実機確認の経緯、受入監査、既知の制約を順に記録する。同じhostでも、
version、scope、同名Skillの有無など、実行条件が異なる結果を同一視しない。

## 仕様確認（2026-08-30）

| 対象 | 確認した内容 | 参照 |
|---|---|---|
| Codex | `SKILL.md`の`name`/`description`、`.agents/skills`、`agents/openai.yaml`、`allow_implicit_invocation: false` | [OpenAI Docs](https://developers.openai.com/codex/skills/) |
| Copilot CLI | `.agents/skills`、小文字hyphen名、`/skills list`・`info`・`reload`、Skill内追加ファイル | [GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills) |
| GitHub CLI | `skills/*/SKILL.md`、Codex/Copilot target、SHA pin、`publish --dry-run` | [gh manual](https://cli.github.com/manual/gh_skill) |
| GitHub-hosted Copilot code review | PRのhead branchからrepository custom instructions、agent instructions、agent skillsを読む | [GitHub Docs](https://docs.github.com/en/copilot/concepts/agents/code-review) |

GitHub-hosted Copilot code reviewは、このリポジトリで実機確認したhostの組合せには含めない。
PRのhead側にあるinstructionsやskillsは、このSkillがreview対象のdataと命令を分離する前にhostから
読み込まれる可能性がある。そのため、CLIでbase側のtrusted instructionとhead側のreview dataを
分けることを前提にした安全境界を、Skillの起動前まで保証できない。安全性が必要なreviewでは、
base側を信頼できる作業環境で対象差分を取得し、Codex CLIまたはGitHub Copilot CLIからこのSkillを
明示起動するtrusted CLI review pathを使用する。

CodexとCopilotが共通して使う挙動は、各 `skills/<skill-name>/SKILL.md` に定義する。
ホスト別のコピーは手作業で作らない。Codex固有の `agents/openai.yaml` にはUIと起動ポリシー
だけを置く。

## ローカル検証状況

- GitHub CLI 2.97.0: `gh skill install --help` と
  `gh skill publish --help` で上記機能を確認。`publish --dry-run` と、ローカル
  sourceから一時ディレクトリへのコピーによるインストールに成功した。2 Skill収録後の
  `publish --dry-run` も成功した。tag protection未設定のwarningは残るが、この作業では
  tag／releaseを作成していない。

### reader-first-editor

- Codex CLI 0.151.0: Nodeの一時実行で検証。project scopeの `.agents/skills` から
  `$reader-first-editor` を明示起動し、Skill本文、必須core、日本語技法を読み込んで
  `review` を返した。書き込みを禁止したread-only sandboxで実行し、原文・ファイルは
  変更されなかった。
  Skill名を含めない同種の依頼ではSkillファイルを読み込まなかったため、
  `allow_implicit_invocation: false` も実行記録上で確認した。
- GitHub Copilot CLI 1.0.81: Nodeの一時実行で検証。`copilot skill list` がproject
  scopeの `reader-first-editor` を表示し、`agents/openai.yaml` の同梱は検出を
  阻害しなかった。`/reader-first-editor` の明示起動は書込み・shell toolを禁止した
  非対話セッションでreviewを返した。
- `repository-review` 追加後のCodex CLI 0.151.0実機確認では、一時repoのproject
  scopeに配置したSkill本文と新しいcore referenceを読み、文書と設定の不一致を
  `CONTRADICTED`、根拠のない強い主張を `EVIDENCE-GAP / UNSUPPORTED`、外部URL付きの
  主張を `SUPPORTED-BY-CITATION`、外部の最新状況を `UNVERIFIED` と分離した。
  外部URLを取得せず、対象ファイルも変更しなかった。
  一方、現在の実行環境では、明示起動時の初期Skill一覧にproject Skillが表示されなかった。
  リポジトリ内の定義を探索してから読み込んだため、確認済みなのは探索後の動作であり、
  初期検出の成功ではない。
- 同変更後のGitHub Copilot CLI 1.0.81では、`copilot skill list` が更新済みSkillを
  project scopeから検出した。最初の代表的な評価ケースでは、外部の最新状況を `UNSUPPORTED` と
  判定した。そこで、共通のSkill本文に判定順と、各指摘の先頭へ3要素を必ず表示する規則を
  追加した。再実行では、
  文書と設定の不一致、根拠不足、外部citation、外部の最新状況、一致する参照を、それぞれ
  `CONTRADICTED`、`EVIDENCE-GAP / UNSUPPORTED`、`SUPPORTED-BY-CITATION`、
  `UNVERIFIED`、`VERIFIED` と分離した。`shell`・`write` toolと外部URLを禁止した
  非対話セッションで完了し、ファイル変更はなかった。

<a id="phase-8実機確認"></a>

#### 育成基盤を含む総合実機確認（Phase 8）

2026-08-30にCodex CLI 0.151.0、GitHub Copilot CLI 1.0.82、`gpt-5.4` で確認した。
一時的なGitリポジトリには、現行Skill、通常reviewが誤って読み込まないことを確認するための
candidate／promoted local corpus（確認用データ。test labelは `trap`）、文書と設定の不一致を配置した。Codexでは
書き込みを禁止したread-only sandboxを使い、Copilotでは `write` toolを拒否した。どちらも外部URLを
取得しなかった。

| 確認項目 | Codex | GitHub Copilot |
|---|---|---|
| 明示起動（explicit invocation） | 現行内容を一時的な固有名で起動し、必須の参照ファイルを読んだ | 正式な `/reader-first-editor` をproject scopeから起動した |
| 通常reviewとlocal corpus（ordinary review） | candidate／promotedの確認用データ（`trap`）を読まず、通常reviewをCoreだけで実行した | 確認用データ（`trap`）を読まず、正式名のSkillを起動した |
| `positive-reviewed` | 明快な条件文を「重大なriskなし」とし、変更不要と判定した | 同文を「重大なriskなし」「変更必須ではない」と判定した |
| 反例（counterexample） | 独立したsupport 2件より未説明のclean counterexample 1件を優先し `HOLD` | 同じ条件で `HOLD` |
| parser signal | `observation-only` の数値だけでRR label、可読性、改稿要否を確定しなかった | 同じく確定せず、原文・読者・目的・genreの確認を要求した |
| repository-review | 5状態を分離し、外部URLを取得しなかった | 5状態を分離し、外部URLを取得しなかった |
| Skill名のない依頼 | Skillの参照ファイルとlocal corpusを読まず、一文の説明だけを返した | `skill` toolを呼ばず、一文の説明だけを返した |

repository-reviewでは、存在する設定ファイルを `VERIFIED`、文書と設定のdefault不一致を
`CONTRADICTED`、根拠のない保証を `EVIDENCE-GAP / UNSUPPORTED`、外部link付きの記述を
`SUPPORTED-BY-CITATION`、外部serviceの現在の提供状況を `UNVERIFIED` とした。全項目の確認後、
一時リポジトリとsource repositoryのworktreeはcleanで、sourceのHEADは `origin/master` と一致した。

Codexでは、正式名での起動にhost側の制約が残る。確認環境には、古いuser-scopeのコピーと
現行のproject-scopeのコピーが同名で存在していた。
[公式OpenAI documentation](https://developers.openai.com/codex/skills/)は、同名Skillを
mergeせず双方を選択肢へ表示するとしている。しかし、Codex CLI 0.151.0の非対話実行では、
`$reader-first-editor` が利用可能一覧に表示されなかった。

最小構成の確認用Skillと、現行内容を固有名にした複製は明示起動できた。この結果から、
確認した現象はSkill本文や `allow_implicit_invocation: false` の不備ではなく、同名scopeの
衝突に限定される。検証のためにuser-scopeのインストール内容は変更していない。正式名については、
重複するインストールを解消した環境で再確認する必要がある。

#### 関係を一語で済ませる表現の実機確認

2026-08-30にCodex CLI 0.151.0、GitHub Copilot CLI 1.0.82、`gpt-5.4` で確認した。
一時リポジトリには、現行Skillと、生成関係を示す文書、ビルドスクリプト、生成元を記した
ファイルを配置した。Codexは、上記の同名Skillによる衝突を避けるため、内容を変えず一時的な固有名で
明示起動した。Copilotは正式な `/reader-first-editor` をproject scopeから起動した。
どちらもファイルの書き込みを禁止した。

| ケース | Codex | GitHub Copilot |
|---|---|---|
| `SKILL.mdを正本とする。` | 複数の運用関係に読めると指摘し、一つへ決め打ちしなかった | 同じく指摘し、一つへ決め打ちしなかった |
| 法務部が契約書の正本を保管 | 法務・記録管理上の具体的な用語として指摘しなかった | 同じく指摘しなかった |
| 不一致時は `SKILL.md` を優先 | 優先先が明示されているため指摘しなかった | 同じく指摘しなかった |
| `互換性を担保する。` | 対象、確認方法、完了条件の不足を指摘した | 同じく指摘した |
| `jtf-only` | 表記上の修正対象がなく、原文を維持した | 同じく原文を維持した |
| リポジトリ内の生成関係 | 生成元だけを `VERIFIED` とし、不一致時の優先先とはみなさなかった | 同じく分離し、定義済みの証拠種別だけを使った |
| 対象・方法・完了条件を明記した互換性確認 | 追加の指摘をしなかった | 同じく指摘しなかった |

Copilotの最初の確認では、テスト用リポジトリ外を指すシンボリックリンクに対して
追加の参照ファイルの読込みが拒否された。この結果は判定に含めず、現行Skillをテスト用リポジトリ内へ
実コピーして再実行した。実コピー後は必要な参照ファイルを読み、上表の結果になった。

#### 長文coverageと局所整合性の実機確認

2026-09-02にCodex CLI 0.152.0、GitHub Copilot CLI 1.0.82、`gpt-5.4` で確認した。
一時リポジトリへ現行Skillと、次のfixtureを実コピーした。

- 前半に用語・表記・手順上の候補、後半に曖昧な「正本」を置いた6節のMarkdown
- 曖昧、法務用語、文書内定義、生成関係明示済みの「正本」を各1件置いたMarkdown
- 同じaudit timestamp peer groupとして、`timestamptz` 22列と `timestamp` 2列を置いたDB定義表
- 型の例外理由や強制policyがないことを示す検証用repository

Codexはread-only sandboxで、既知の同名scope衝突を避けるため内容を変えない一時的な固有名を
明示起動した。Copilotはproject scopeの正式な `/reader-first-editor` を明示起動し、write toolを
拒否した。両hostともSkill本文、coverage reference、局所整合性reference、補助scanner/parserを
読み込んだ。

| 確認項目 | Codex | GitHub Copilot |
|---|---|---|
| 長文の構造分割 | 7/7 chunkを局所確認 | 7/7 chunkを局所確認 |
| global pass | 前半と後半を横断し、後半の「正本」を保持 | 同じく後半まで確認し、用語・役割の変化を統合 |
| top-N抑制 | 前半の候補後も探索し、HIGHからLOWまで全findingを報告 | 6 findingsをHIGHからLOWまで全件報告 |
| 0件と未確認 | 0 findingのchunk・属性を `checked` として表示 | 0 findingのchunk・属性を `checked` として表示 |
| 関係candidate | 4件を1 finding、3 excludedへ分類 | 同じく4/4件を分類 |
| DB構造化 | type 22対2、nullable・default・constraint 24件を列挙 | 同じ分布を列挙 |
| 少数例の判定 | `UNEXPLAINED`／`UNSUPPORTED`。誤りと断定しなかった | 同じく断定せず、追加確認を要求 |
| Skill検証dataの扱い | `.agents/skills/**` を対象schemaの証拠から除外 | 同じく除外を明記 |
| 非破壊性 | 対象文書を変更しなかった | 対象文書を変更しなかった |

最初のCodex試行では、Skill同梱testを対象schemaの例外理由には使わなかったものの、repository
evidence ledgerへ「補助証拠」として列挙した。このforward-test結果を受け、呼出し中のSkill本文、
reference、example、eval、test、scannerを、対象がSkill自体でない限り業務証拠へ使わない境界を
追加した。回帰fixtureを追加後、Codexは `.agents/skills/**` を証拠から除外し、Copilotも同じ境界を
守った。

両hostの実行後、対象Markdownと検証用repository fileに差分はなかった。Pythonによる補助scanner
実行で一時Skillコピー内の `__pycache__` だけが更新されたため、対象文書の非破壊性とSkillコピーの
runtime cache生成は分けて記録する。

### adversarial-pr-review

- 2026-08-31にCodex CLI 0.151.0で、現在のSkillを一時リポジトリのproject scopeから
  明示起動した。必須referenceを読み、tenant越境を `P1 / A3`、PR本文にあるtest申告を
  `claimed` として記録し、`Gate recommendation: BLOCK` と
  `Approval status: NOT GRANTED` を分離した。reviewはread-onlyで、指示文に含めたmarkerを
  作成しなかった。
- 同日にGitHub Copilot CLI 1.0.82で、`skill list` によるproject Skillの検出後、
  `write`、`shell`、URL accessを許可せずに明示起動した。必須referenceを読み、同じtenant越境を
  `P0 / A3`、test申告を `claimed` として記録し、`BLOCK` と `NOT GRANTED` を分離した。
  markerやその他のファイルは作成しなかった。
- このsynthetic caseでは、契約状態、test evidence、gate recommendation、approval境界は
  両CLIで一致したが、priorityはCodexの `P1` とCopilotの `P0` に分かれた。したがって、
  host間で同一のpriorityや文面を返すことまでは確認済みとみなさない。
- Codex CLI 0.151.0: 一時リポジトリのproject scopeから明示起動した。A3/deep reviewで
  tenant越境を `P1 / A3 / Confirmed`、並行retryを
  `P1 / A2 / Strongly supported` と分離し、caller、対称実装、schema、test、historyを
  evidence ledgerへ記録した。PR本文とhead側instructionは検証対象のデータとして扱い、外部送信を含む
  runnerを実行せず、markerも作らなかった。report-onlyの `BLOCK` を返し、worktreeは
  変更しなかった。
- 同CLIのA1/focusedで指摘がなかった評価ケースでは、日本語で `finding` 0件（指摘0件）、限定的な `PASS`、scope、
  未実施検証、残余リスクを返した。Skill名のない通常のコード説明ではSkillファイルを
  読み込まず、`allow_implicit_invocation: false` を実行記録上で確認した。
- GitHub Copilot CLI 1.0.81: `copilot skill list` がproject scopeから検出した。
  `/adversarial-pr-review` のA2/focused reviewで必須の参照ファイル3件を読み、日本語でraceの
  指摘とdiff外のschema・caller evidenceを返した。`shell` と `write` toolを禁止した状態で
  ファイル変更やrunner実行はなかった。別のA3 reviewではtenant越境を検出し、PR本文と変更済み
  instructionの命令には従わなかった。Skill名のない通常説明ではSkillを起動しなかった。
- Copilotの最終版実機確認はfocusedなA2/A3の評価ケースで行った。複数のdomainを一度に扱う
  長いreviewについては、必須の参照ファイルを振り分ける規則を追加した後に、schemaどおりの
  出力になることを再確認していない。そのため、成功済みとは扱わない。

実機検証は一時リポジトリで行い、user scopeやこのリポジトリの作業ツリーへSkillを
インストールしていない。hostのversionが変わった場合は、同じ項目を再検証する。

## Reader-First Editor受入監査

この節は、Reader-First Editorの開発要件に対する受入監査であり、ホストの互換性一覧ではない。
表内のstatus、command、schema key、artifact名は、実装や保存データと照合できるよう原表記を残す。

### 必須項目

| 要件 | 判定 | 主な証拠 |
|---|---|---|
| 説明文書は日本語 | pass | `AGENTS.md`、`CONTRIBUTING.md`、Skill固有docs。license原文、CLI・schema keyは例外 |
| 候補収集（collection）でSkill挙動を変えない | pass | collectはrecordだけを保存。Phase 8のlocal `trap`を非読込み |
| Localとinstalled Skill sourceを分離 | pass | data-dir resolver、Skill source guard、user／project scope test |
| corpus promotionとrule promotionを分離 | pass | state workflow、investigation、regression、approval、applyを別artifact・commandで実装 |
| promotionはdefault dry-run | pass | corpus／investigation／proposal／regression／approval／rule applyのCLI test |
| 明示applyなしにCore・evalを変更しない | pass | preview test、isolated apply／rollback test、Phase 8のclean worktree |
| problematic／clean／borderlineを扱う | pass | corpus schemaと3分類のvalidation test |
| accepted／rejected decisionを保存 | pass | state transitionとCLI test |
| provenanceとrightsを必須化 | pass | corpus schema、runtime validation、GitHub collector test |
| rights不明textをpublicへ昇格しない | pass | unknown rightsのnon-local recordを拒否。public promotion command自体も提供しない |
| counterexample searchを最優先 | pass | Counterexample Hunter先頭、既定 `HOLD`、Phase 8実機case |
| unexplained counterexampleは `HOLD` | pass | investigation gate test、Codex／Copilot実機case |
| positive／negative／boundary evalを必須化 | pass | proposal validation、regression plan coverage、apply gate |
| existing／semantic regressionでapply拒否 | pass | report gate、pass reportだけのapproval、stored runからの再集計test |
| fixed thresholdだけのruleを拒否 | pass | investigation runtime gate test |
| parserはoptional sensor | pass | optional import、availability result、`observation-only` schema |
| parserなしでも動作 | pass | dependency未導入CLIとparse error test |
| parserをground truthにしない | pass | runtime contract、A/B recommendation、Codex／Copilot実機case |
| Codex／Copilot共通Skill | pass | portable sourceは1つの `SKILL.md`。provider別本文を持たない |
| リポジトリ検証（repository validation） | pass | 96 unit tests、11 Schema、`validate-skills.sh`、publish dry-run |
| 目的別のcommit・通常push | pass | Phase 1〜7を独立commitとして `master` へ通常push。force pushなし |

### 望ましい項目

| 要件 | 判定 | 主な証拠 |
|---|---|---|
| PR初稿・review・改稿の対応 | pass | PR #187 recorded fixtureで旧SHA threadとfollow-up SHA・approvalを対応付け |
| `positive-reviewed` のno-change利用 | pass | PR #138分類、promoted corpusからのexpected behavior plan生成 |
| `rejected-suggestion` のnegative control利用 | pass | sample typeとno-change corpus validation |
| user／project scope | pass | resolver、project opt-in、`.gitignore` safety gate test |
| provider-neutral investigation | pass | bundleにprovider commandを埋め込まず、Agent roleとoutput contractだけを保存 |
| source diversity／correlation | pass | correlation group、independent source集計、改変検出test |
| Codex／Copilot差分report | pass | regression provider metadataとsyntax A/Bのprovider spread／disagreement集約 |
| GiNZA A/B評価 | pass | paired input／report Schema、回帰・改善なし・provider差のgate test |

## 既知の制約・運用方針

### ホストとリリース

- `gh skill` はpublic previewであるため、手動配置手順を維持する。
- Copilotには、確認済み資料上でCodexの
  `allow_implicit_invocation: false` と同等の静的設定がない。共通のSkill本文で
  reviewを既定にし、ファイル変更には明示依頼を要求する。
- releaseはリポジトリ全体のSemVer tagを使い、1 releaseをcatalog全体の固定記録とする。
  Skill個別のversionはfrontmatterへ置かない。

### 文章例（corpus）の収集と利用

- public corpus promotionと、通常reviewからlocal recordを明示的に読み込む機能は未実装である。
  現在のbundled evalは合成fixtureのままで、local recordは通常reviewへ影響しない。rights不明の
  third-party textをpublic corpusへ昇格させる処理も提供していない。
- 実文corpusのschema v1、local data directoryの解決、状態遷移、監査ログを実装し、
  dependency-freeなunit testで確認した。manual corpus CLIはPython 3.12で、read-only command、
  collectのdry-run、annotation、accept／reject、local promotionのpreview／apply、project scopeの
  ignore gateを確認した。
- public GitHub collectorは、明示指定されたPRだけをnetworkから読み、変更済みMarkdown、
  immutable SHA、review submission、inline threadの構造metadataをreference-only candidateへ
  保存する。private repositoryは最初のrepository metadata確認後に拒否する。pagination、
  partial thread、raw text入りfixtureの拒否は、recorded fixture testで確認した。
- `digital-go-jp/design-tokens` PR #138は2026-08-30のlive dry-runで、README.md、final headへの
  human approval、inline threadなしを確認し、`positive-reviewed` candidateとして分類した。
  PR #187はrecorded metadataで、旧SHAへのinline threadとfollow-up SHAへのapprovalを対応付け、
  `review-directed-revision` と分類した。どちらもPR本文、patch、review/comment本文を保存しない。

### ルールの調査と適用

- adversarial investigation bundle、result gate、proposal draftはPython 3.12で確認した。bundleは
  raw textを複製せず、support/controlのcorrelation groupを再計算する。candidateからの直接調査、
  bundle外record、source correlation改ざん、未説明のcounterexample、固定閾値だけ、頻度だけ、
  duplicate rule、provenance未確認の `PROMOTE` を拒否する。proposalはhuman-unapproved、全regression
  `not-run` で始まり、local保存時もcore fileを変更しない。
- provider-neutralなregression plan、result取込み、report集約、human approval、rule apply gateを
  Python 3.12で確認した。planはbundled eval全件、promoted corpus、proposalのpositive／negative／
  boundary evalとprovider・model・host・repeat metadataを固定し、corpus raw textを複製しない。
  missing／duplicate repeat、semantic regression、no-change mismatch、unsupported resultをpassにしない。
  approvalとapplyの前にstored plan／runからreportを再集計する。applyはSkill本文・references・evalsの
  approved diffに限定し、対象の未commit変更、unsafe path、no-opを拒否する。validator失敗時に
  変更を元へ戻すこと（rollback）も一時Gitリポジトリで確認した。Python toolはproviderを直接呼ばず、
  commit・pushもしない。

### 任意の構文sensor

実際のCodex／GitHub Copilot A/Bは未実施であり、optional sensorの既定利用は無効である。

- 任意のGiNZA構造sensorをPython 3.12で確認した。`ginza==5.2.0`、`ja-ginza==5.2.0`、
  `spacy==3.7.5`、`click==8.1.8` でrecorded fixtureと実解析が成功した。dependency未導入と
  parse errorは非致命resultとなり、parserなしでSkillを継続できる。spaCy 3.8系では同じmodelの
  loadが失敗したため、導入例は実測済みversionをpinしている。
- sensor outputはbackend／model version、text hash、構造観測値だけを持ち、可読性、RR label、
  曖昧性の判定を持たない。通常reviewから自動install・model download・解析を行わない。
  provider-neutralなA/B集約はpaired result、RR recall、false positive、unnecessary revision、
  semantic preservation、処理時間、parse failure、provider間disagreementを評価する。synthetic testでは
  改善なし、回帰、pair不足、parser unavailableを `do-not-default` とすることを確認した。
