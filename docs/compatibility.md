# 互換性

## 仕様確認（2026-08-30）

| 対象 | 確認した内容 | 参照 |
|---|---|---|
| Codex | `SKILL.md`の`name`/`description`、`.agents/skills`、`agents/openai.yaml`、`allow_implicit_invocation: false` | [OpenAI Docs](https://developers.openai.com/codex/skills/) |
| Copilot CLI | `.agents/skills`、小文字hyphen名、`/skills list`・`info`・`reload`、Skill内追加ファイル | [GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills) |
| GitHub CLI | `skills/*/SKILL.md`、Codex/Copilot target、SHA pin、`publish --dry-run` | [gh manual](https://cli.github.com/manual/gh_skill) |

各 `skills/<skill-name>/SKILL.md` をsource of truthとし、provider別の手書きコピーは
置かない。Codex固有の `agents/openai.yaml` にはUIと起動ポリシーだけを置く。

## ローカル検証状況

- GitHub CLI 2.97.0: `gh skill install --help` と
  `gh skill publish --help` で上記機能を確認。`publish --dry-run` と、ローカル
  sourceから一時ディレクトリへのcopy installに成功した。2 Skill収録後の
  `publish --dry-run` も成功した。tag protection未設定のwarningは残るが、この作業では
  tag／releaseを作成していない。

### reader-first-editor

- Codex CLI 0.151.0: Nodeの一時実行で検証。project scopeの `.agents/skills` から
  `$reader-first-editor` を明示起動し、Skill本文、必須core、日本語技法を読み込んで
  `review` を返した。read-only sandboxで原文・ファイルは変更されなかった。
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
  判定した。そこで、shared Skillに判定順と3要素prefixのgateを追加した。再実行では、
  文書と設定の不一致、根拠不足、外部citation、外部の最新状況、一致する参照を、それぞれ
  `CONTRADICTED`、`EVIDENCE-GAP / UNSUPPORTED`、`SUPPORTED-BY-CITATION`、
  `UNVERIFIED`、`VERIFIED` と分離した。shell・write toolと外部URLを禁止した
  非対話セッションで完了し、file変更はなかった。

### adversarial-pr-review

- Codex CLI 0.151.0: disposable repoのproject scopeから明示起動した。A3/deep reviewで
  tenant越境を `P1 / A3 / Confirmed`、並行retryを
  `P1 / A2 / Strongly supported` と分離し、caller、対称実装、schema、test、historyを
  evidence ledgerへ記録した。PR本文とhead側instructionはdataとして扱い、外部送信を含む
  runnerを実行せず、markerも作らなかった。report-onlyの `BLOCK` を返し、worktreeは
  変更しなかった。
- 同CLIのA1/focused no-finding caseでは、日本語でfinding 0件、限定的な `PASS`、scope、
  未実施検証、残余リスクを返した。Skill名のない通常のコード説明ではSkill fileを
  読み込まず、`allow_implicit_invocation: false` をtrace上で確認した。
- GitHub Copilot CLI 1.0.81: `copilot skill list` がproject scopeから検出した。
  `/adversarial-pr-review` のA2/focused reviewで必須reference 3件を読み、日本語でraceの
  findingとdiff外のschema・caller evidenceを返した。shellとwrite toolを禁止した状態で
  file変更やrunner実行はなかった。別のA3 reviewではtenant越境を検出し、PR本文と変更済み
  instructionの命令には従わなかった。Skill名のない通常説明ではSkillを起動しなかった。
- Copilotの最終版実機確認はfocusedなA2/A3 caseで行った。複数domainを一度に扱う長い
  combined reviewについては、必須reference routing追加後のschema fidelityを再確認して
  いないため、成功済みとは扱わない。

実機検証は一時repoで行い、user scopeやこのリポジトリの作業ツリーへSkillを
インストールしていない。host versionが変わった場合は、同じ項目を再検証する。

## 既知の制約・運用方針

- `gh skill` はpublic previewであるため、手動配置手順を維持する。
- Copilotには、確認済み資料上でCodexの
  `allow_implicit_invocation: false` と同等の静的設定がない。portable本文で
  reviewを既定にし、ファイル変更には明示依頼を要求する。
- releaseはrepo-wide SemVer tagを使い、1 releaseをcatalog全体のsnapshotとする。
  Skill個別versionはfrontmatterへ置かない。
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
