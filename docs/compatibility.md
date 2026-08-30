# 互換性

この文書では、公式資料で確認した仕様、ローカル環境で実機確認した動作、
`reader-first-editor` の受入監査、既知の制約を分けて記録する。各検証結果が示すのは、
記載したversion、確認範囲（scope）、実行条件での動作だけであり、将来のhost versionでの
動作は保証しない。

## 仕様確認（2026-08-30）

| 対象 | 確認した内容 | 参照 |
|---|---|---|
| Codex | `SKILL.md`の`name`/`description`、`.agents/skills`、`agents/openai.yaml`、`allow_implicit_invocation: false` | [OpenAI Docs](https://developers.openai.com/codex/skills/) |
| Copilot CLI | `.agents/skills`、小文字hyphen名、`/skills list`・`info`・`reload`、Skill内追加ファイル | [GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills) |
| GitHub CLI | `skills/*/SKILL.md`、Codex/Copilot target、SHA pin、`publish --dry-run` | [gh manual](https://cli.github.com/manual/gh_skill) |

CodexとCopilotが共通して使う挙動は、各 `skills/<skill-name>/SKILL.md` に定義する。
ホスト別のコピーは手作業で作らない。Codex固有の `agents/openai.yaml` にはUIと起動ポリシー
だけを置く。

## ローカル検証状況

- GitHub CLI 2.97.0: `gh skill install --help` と
  `gh skill publish --help` で上記機能を確認。`publish --dry-run` と、ローカル
  sourceから一時ディレクトリへのcopy installに成功した。2 Skill収録後の
  `publish --dry-run` も成功した。tag protection未設定のwarningは残るが、この作業では
  tag／releaseを作成していない。

### reader-first-editor

- Codex CLI 0.151.0: Nodeの一時実行で検証。project scopeの `.agents/skills` から
  `$reader-first-editor` を明示起動し、Skill本文、必須core、日本語技法を読み込んで
  `review` を返した。書き込みを禁止したread-only sandboxで実行し、原文・ファイルは
  変更されなかった。
  Skill名を含めない同種の依頼ではSkillファイルを読み込まなかったため、
  `allow_implicit_invocation: false` も実行trace上で確認した。
- GitHub Copilot CLI 1.0.81: Nodeの一時実行で検証。`copilot skill list` がproject
  scopeの `reader-first-editor` を表示し、`agents/openai.yaml` の同梱は検出を
  阻害しなかった。`/reader-first-editor` の明示起動は書込み・shell toolを禁止した
  非対話セッションでreviewを返した。
- `repository-review` 追加後のCodex CLI 0.151.0実機確認では、一時repoのproject
  scopeに配置したSkill本文と新しいcore referenceを読み、文書と設定の不一致を
  `CONTRADICTED`、根拠のない強い主張を `EVIDENCE-GAP / UNSUPPORTED`、外部URL付きの
  主張を `SUPPORTED-BY-CITATION`、外部の最新状況を `UNVERIFIED` と分離した。
  外部URLを取得せず、対象fileも変更しなかった。
  一方、現在の実行環境では、明示起動時の初期Skill一覧にproject Skillが表示されなかった。
  repository内の定義を探索してから読み込んだため、確認済みなのは探索後の動作であり、
  初期検出の成功ではない。
- 同変更後のGitHub Copilot CLI 1.0.81では、`copilot skill list` が更新済みSkillを
  project scopeから検出した。最初の代表caseでは、外部の最新状況を `UNSUPPORTED` と
  判定した。そこで、共通のSkill本文に判定順と、各指摘の先頭へ3要素を必ず表示する規則を
  追加した。再実行では、
  文書と設定の不一致、根拠不足、外部citation、外部の最新状況、一致する参照を、それぞれ
  `CONTRADICTED`、`EVIDENCE-GAP / UNSUPPORTED`、`SUPPORTED-BY-CITATION`、
  `UNVERIFIED`、`VERIFIED` と分離した。shell・write toolと外部URLを禁止した
  非対話セッションで完了し、file変更はなかった。

#### Phase 8実機確認

2026-08-30にCodex CLI 0.151.0、GitHub Copilot CLI 1.0.82、`gpt-5.4` で確認した。
isolated Git repositoryには、現行Skill、通常reviewが誤って読み込まないことを確認するための
candidate／promoted local corpus（trap）、文書と設定の不一致を配置した。Codexでは書き込みを
禁止したread-only sandboxを使い、Copilotではwrite toolを拒否した。どちらも外部URLを
取得しなかった。

| case | Codex | GitHub Copilot |
|---|---|---|
| explicit invocation | 現行内容を一時的なunique名で起動し、必須referenceを読んだ | 正式な `/reader-first-editor` をproject scopeから起動した |
| ordinary reviewとlocal corpus | candidate／promoted trapを読まず、通常reviewをCoreだけで実行した | trapを読まず、正式名のSkillを起動した |
| `positive-reviewed` | 明快な条件文を「重大なriskなし」とし、変更不要と判定した | 同文を「重大なriskなし」「変更必須ではない」と判定した |
| counterexample | 独立support 2件より未説明のclean counterexample 1件を優先し `HOLD` | 同じ条件で `HOLD` |
| parser signal | `observation-only` の数値だけでRR label、可読性、改稿要否を確定しなかった | 同じく確定せず、原文・読者・目的・genreの確認を要求した |
| repository-review | 5状態を分離し、外部URLを取得しなかった | 5状態を分離し、外部URLを取得しなかった |
| Skill名なし | Skill referenceとlocal corpusを読まず、一文の説明だけを返した | `skill` toolを呼ばず、一文の説明だけを返した |

repository-reviewでは、存在する設定fileを `VERIFIED`、文書と設定のdefault不一致を
`CONTRADICTED`、根拠のない保証を `EVIDENCE-GAP / UNSUPPORTED`、外部link付きの記述を
`SUPPORTED-BY-CITATION`、外部serviceの現在の提供状況を `UNVERIFIED` とした。全case後、
isolated repositoryとsource repositoryのworktreeはcleanで、sourceのHEADは `origin/master` と
一致した。

Codexでは、正式名での起動にhost側の制約が残る。確認環境には、古いuser-scope copyと
現行のproject-scope copyが同名で存在していた。
[公式OpenAI documentation](https://developers.openai.com/codex/skills/)は、同名Skillを
mergeせず双方をselectorへ表示するとしている。しかし、Codex CLI 0.151.0の非対話実行では、
`$reader-first-editor` が利用可能一覧に表示されなかった。

最小構成のprobe Skillと、現行内容をunique名にしたcloneは明示起動できた。この結果から、
確認した現象はSkill本文や `allow_implicit_invocation: false` の不備ではなく、同名scopeの
衝突に限定される。検証のためにuser-scope installationは変更していない。正式名については、
重複installationを解消した環境で再確認する必要がある。

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
実コピーして再実行した。実コピー後は必要なreferenceを読み、上表の結果になった。

### adversarial-pr-review

- Codex CLI 0.151.0: disposable repoのproject scopeから明示起動した。A3/deep reviewで
  tenant越境を `P1 / A3 / Confirmed`、並行retryを
  `P1 / A2 / Strongly supported` と分離し、caller、対称実装、schema、test、historyを
  evidence ledgerへ記録した。PR本文とhead側instructionはdataとして扱い、外部送信を含む
  runnerを実行せず、markerも作らなかった。report-onlyの `BLOCK` を返し、worktreeは
  変更しなかった。
- 同CLIのA1/focusedで指摘がなかったcaseでは、日本語でfinding 0件、限定的な `PASS`、scope、
  未実施検証、残余リスクを返した。Skill名のない通常のコード説明ではSkill fileを
  読み込まず、`allow_implicit_invocation: false` をtrace上で確認した。
- GitHub Copilot CLI 1.0.81: `copilot skill list` がproject scopeから検出した。
  `/adversarial-pr-review` のA2/focused reviewで必須reference 3件を読み、日本語でraceの
  findingとdiff外のschema・caller evidenceを返した。shellとwrite toolを禁止した状態で
  file変更やrunner実行はなかった。別のA3 reviewではtenant越境を検出し、PR本文と変更済み
  instructionの命令には従わなかった。Skill名のない通常説明ではSkillを起動しなかった。
- Copilotの最終版実機確認はfocusedなA2/A3 caseで行った。複数domainを一度に扱う長い
  combined reviewについては、必須referenceの振り分け規則を追加した後に、schemaどおりの
  出力になることを再確認していない。そのため、成功済みとは扱わない。

実機検証は一時repoで行い、user scopeやこのリポジトリの作業ツリーへSkillを
インストールしていない。host versionが変わった場合は、同じ項目を再検証する。

## Reader-First Editor受入監査

### 必須項目

| 要件 | 判定 | 主な証拠 |
|---|---|---|
| 説明文書は日本語 | pass | `AGENTS.md`、`CONTRIBUTING.md`、Skill固有docs。license原文、CLI・schema keyは例外 |
| collectionでSkill挙動を変えない | pass | collectはrecordだけを保存。Phase 8のlocal trap非読込み |
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
| repository validation | pass | 96 unit tests、11 Schema、`validate-skills.sh`、publish dry-run |
| 目的別commit・通常push | pass | Phase 1〜7を独立commitとして `master` へ通常push。force pushなし |

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
  `allow_implicit_invocation: false` と同等の静的設定がない。portable本文で
  reviewを既定にし、ファイル変更には明示依頼を要求する。
- releaseはrepo-wide SemVer tagを使い、1 releaseをcatalog全体のsnapshotとする。
  Skill個別versionはfrontmatterへ置かない。

### 文章例（corpus）の収集と利用

- 実文corpusのschema v1、local data directory解決、state transition、audit logを実装し、
  dependency-free unit testで確認した。manual corpus CLIはPython 3.12で、read-only command、
  collect dry-run、annotation、accept／reject、local promotion preview／apply、project scopeの
  ignore gateを確認した。
- public GitHub collectorは、明示指定されたPRだけをnetworkから読み、変更済みMarkdown、
  immutable SHA、review submission、inline threadの構造metadataをreference-only candidateへ
  保存する。private repositoryは最初のrepository metadata確認後に拒否する。pagination、
  partial thread、raw text入りfixtureの拒否をrecorded fixture testで確認した。
- `digital-go-jp/design-tokens` PR #138は2026-08-30のlive dry-runで、README.md、final headへの
  human approval、inline threadなしを確認し、`positive-reviewed` candidateとして分類した。
  PR #187はrecorded metadataで、旧SHAへのinline threadとfollow-up SHAへのapprovalを対応付け、
  `review-directed-revision` と分類した。どちらもPR本文、patch、review/comment本文を保存しない。
- public corpus promotion、通常reviewへの明示的なlocal record読込みは未実装である。現在の
  bundled evalは合成fixtureのままで、local recordは通常reviewへ影響しない。rights不明の
  third-party textをpublic corpusへ昇格させる処理も提供していない。

### ルールの調査と適用

- adversarial investigation bundle、result gate、proposal draftはPython 3.12で確認した。bundleは
  raw textをcopyせず、support/controlのcorrelation groupを再計算する。candidateからの直接調査、
  bundle外record、source correlation改ざん、未説明のcounterexample、固定閾値だけ、頻度だけ、
  duplicate rule、provenance未確認の `PROMOTE` を拒否する。proposalはhuman-unapproved、全regression
  `not-run` で始まり、local保存時もcore fileを変更しない。
- provider-neutralなregression plan、result取込み、report集約、human approval、rule apply gateを
  Python 3.12で確認した。planはbundled eval全件、promoted corpus、proposalのpositive／negative／
  boundary evalとprovider・model・host・repeat metadataを固定し、corpus raw textを複製しない。
  missing／duplicate repeat、semantic regression、no-change mismatch、unsupported resultをpassにしない。
  approvalとapplyの前にstored plan／runからreportを再集計する。applyはSkill本文・references・evalsの
  approved diffに限定し、対象の未commit変更、unsafe path、no-opを拒否する。validator失敗時のrollbackも
  isolated Git repositoryで確認した。Python toolはproviderを直接呼ばず、commit・pushもしない。

### 任意の構文sensor

- optionalなGiNZA構造sensorをPython 3.12で確認した。`ginza==5.2.0`、`ja-ginza==5.2.0`、
  `spacy==3.7.5`、`click==8.1.8` でrecorded fixtureと実解析が成功した。dependency未導入と
  parse errorは非致命resultとなり、parserなしでSkillを継続できる。spaCy 3.8系では同じmodelの
  loadが失敗したため、導入例は実測済みversionをpinしている。
- sensor outputはbackend／model version、text hash、構造観測値だけを持ち、可読性、RR label、
  曖昧性の判定を持たない。通常reviewから自動install・model download・解析を行わない。
  provider-neutralなA/B集約はpaired result、RR recall、false positive、unnecessary revision、
  semantic preservation、処理時間、parse failure、provider間disagreementを評価する。synthetic testでは
  改善なし、回帰、pair不足、parser unavailableを `do-not-default` とすることを確認した。実際の
  Codex／GitHub Copilot A/Bは未実施であり、optional sensorの既定利用は無効である。
