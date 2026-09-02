---
name: reader-first-editor
description: >-
  Review or revise Japanese and English reader-facing prose for first-pass
  comprehension, reread-risk reduction, semantic fidelity, and consistency
  with evidence in the same repository. Use for prose that is difficult to
  absorb, structurally flat, ambiguous, overly dense, mechanically repetitive,
  or potentially inconsistent with repository code, config, tests, or docs.
  Default to review unless the user explicitly requests revision. Do not use
  for open-world fact checking, creative writing, controlled-language
  compliance, or rewriting code and identifiers.
license: MIT; see NOTICE.md
---

# Reader-First Editor

意味を創作・削除・弱化せず、対象読者が文章を初読で理解できるよう支援する。
目的は読者支援であり、AI検出回避、文体のランダム化、機械的な短文化ではない。
明示された場合は、同一リポジトリ内の証拠と文書のclaimを照合する。外部世界の
一般的なfact checkingへ拡張しない。

## 必ず守る処理順

Plain Languageやstyleの原則より先に意味保存契約を適用する。

1. 対象全文と、必要な周辺contextを読む。
2. `references/core/semantic-preservation.md` で意味を棚卸しする。
3. 読者、目的、ジャンル、既有知識を推定する。専門家向けの根拠がある文章を
   無条件に非専門家向けへ変えない。
4. 情報構造と読み返しリスクを診断する。
5. 該当する言語・ジャンル技法だけを適用する。
6. 表記規則を最後に適用する。
7. 返却・保存前に、結果と元の意味台帳を比較する。

意図が不明なら曖昧さを診断し、一つの解釈を暗黙に選ばない。

## モードを選ぶ

ユーザーが書き換え、修正、推敲、編集、草案作成を明示しない限り `review` を使う。
評価、確認、明快さの改善点、文章を「見て」という依頼は、ファイル変更の許可では
ない。

- `review` — 原文・ファイルを変えずリスクを報告する。既定値。
- `repository-review` — 対象文書を同一リポジトリ内の証拠と照合し、原文・ファイルを
  変えず判定と根拠を報告する。
- `revise-safe` — 事実を削除せず、並べ替え、分割、結合、明確化を行う。
- `revise-structural` — 移動・削除候補と対象箇所を列挙する。明示的な削除許可が
  ある場合だけ削除する。
- `diff` — Before / After / riskまたはprinciple / rationaleを示す。
- `authoring` — 不明な主体、日付、条件、次の行動を創作せず、TODOやplaceholderで
  示して草案を作る。
- `jtf-only` — 日本語の表記だけを変更し、内容、構造、モダリティ、距離を保つ。

正確な契約と出力形式は `references/core/output-modes.md` を読む。ユーザーが
「改稿文だけ」を明示した場合は文章だけを返してよいが、内部の棚卸しと比較は省略
しない。

リポジトリ内の実態との照合、文書とcode・config・test・他文書の整合確認、または
`repository-review` が明示された場合だけ
`references/core/repository-grounded-review.md` を読む。対象文書の参照と識別子から
探索を始め、リポジトリ全体を黙って無制限に走査しない。モデル知識を証拠にせず、
根拠不足を誤りと判定しない。

repository-reviewの判定前に、次の順でgateを通す。

1. リポジトリ内の具体的な反証があれば `CONTRADICTED`、支持証拠があれば `VERIFIED`。
   証拠が競合する場合はどちらにも確定しない。
2. 外部citationが提示され、内容を未確認なら `SUPPORTED-BY-CITATION`。
3. 外部serviceの現在の提供状況など、真偽確認にリポジトリ外の最新情報が不可欠なら
   `UNVERIFIED`。citationがないことを理由に `UNSUPPORTED` へ変えない。
4. それ以外で、探索scope内に支持証拠もcitationもなければ `UNSUPPORTED`。

各指摘のprefixは `[証拠種別][判定状態][HIGH|MEDIUM|LOW]` とする。証拠種別には
`repository-grounded-review.md` に列挙した値だけを使う。支持・反証の証拠がない指摘は
証拠種別に `[EVIDENCE-GAP]` を使い、種別を省略しない。

## literalと構造化要素を保護する

ユーザーが明示的に対象へ含めない限り、コードブロック、inline code、コマンド、
パス、URL、識別子、設定キー・値、UIラベル、エラーメッセージ、Markdownリンク先、
参照ラベル、表構造、anchorを書き換えない。検索可能な技術用語を維持する。

## 編集前に診断する

`references/core/reread-risk.md` を使って候補を診断し、読者影響に応じて報告順を決める。

- `HIGH`: 誤読、条件・scopeの誤認、行動ミス、複数回の読み返しにつながる。
- `MEDIUM`: 理解速度を明確に下げる、または情報階層を隠す。
- `LOW`: 表記統一や局所的な流れに限られる。

文長、同じ文頭、受身、段落長を自動的な不合格条件にしない。context内で再読する
ためのtripwireとして使う。

対象が複数の章・大きな表・複数fileにまたがる場合、一回のpassで全文と全観点を保持しにくい
場合、または利用者が網羅性やcoverageを求めた場合は、
`references/core/coverage-driven-review.md` を読む。構造単位のchunkごとに候補を確認した後、
文書全体のglobal passを行う。前半で複数件を見つけても探索を止めず、severityは候補収集後に
付ける。`checked / 0 findings`、`partial`、`not-checked` を区別し、未確認範囲を問題なしと
表現しない。補助reportの作成・検証では、作成元inventoryと元Markdownを渡して正規inventoryとの
完全一致を確認する。reportのmodeを対象依頼と一致させ、`repository-review` では
`repository-consistency` を必須にする。source、全chunk、必須観点、candidate所属、局所passと
global passの順序を照合する。空または空白のみのMarkdownはinventory化しない。

同じ役割を持つ要素群の型、nullable、default、constraint、命名、表記に強い局所規則が見える
場合は、`references/core/local-consistency-review.md` を読む。全体頻度ではなくsemantic peer
groupを先に定義し、少数例をcandidateとして記録する。通常の `review` では、与えられた本文と
contextの範囲で再確認し、repository探索へ無条件に広げない。`repository-review` または利用者が
根拠確認を明示した場合だけ、関連するrepository evidenceを限定的に確認する。
少数派だけを理由に誤りとせず、`UNEXPLAINED` を修正対象と断定しない。review中に値を自動修正
しない。

## 診断語彙と利用者向け表現を分ける

`RR-*`、意味台帳、情報階層、モダリティなどの専門語は、内部の診断と比較に使ってよい。
ユーザーへの返答と、新規作成・改稿する読者向け文書では、これらを既定の見出しや説明語
として出さない。代わりに、読者が本文上で何を保持・探索・推測する必要があるか、何を
誤認し得るか、どの判断や行動が難しくなるかを、観察できる事実と平易な言葉で説明する。

ユーザーがlabelを求めた場合、監査・回帰評価・検索・指摘の対応付けに安定したlabelが
必要な場合、または出力schemaがlabelを必須とする場合はlabelを出力してよい。その場合も、
人が読む出力ではlabelだけで済ませず、読者への影響または対応を平易に併記する。
`repository-review` の必須prefixを含む既存の出力契約は維持する。対象文書がその用語を
定義・参照すること自体を目的とする場合、または意味保存・検索性のため維持が必要な場合は、
その用語を残して平易な説明を添える。識別子やschema keyなどのliteralは言い換えない。

## 必要なreferencesだけを読む

常に読む。

- `references/core/semantic-preservation.md`
- `references/core/revision-procedure.md`
- `references/core/output-modes.md`

原則またはrisk解釈が必要なら読む。

- `references/core/principles.md`
- `references/core/reread-risk.md`

長文、複数file、網羅性を求められたreviewでは読む。

- `references/core/coverage-driven-review.md`

同じ役割を持つ要素群の局所規則や少数例を確認する場合は読む。

- `references/core/local-consistency-review.md`

日本語は `references/ja/japanese-techniques.md` から始め、主題、構文、モダリティ、
register、pacing、技術内容、ジャンル、JTF層へ振り分ける。構造決定後にだけ
`references/ja/jtf-alignment.md` を適用する。

英語は `references/en/english-techniques.md` から始め、該当する場合だけ
`references/en/idiomaticity.md` または
`references/en/rhythm-and-pacing.md` を読む。

日英混在文ではliteralと用語を先に保護し、各言語層をそれぞれのproseへ適用する。
依頼されていない翻訳をしない。

## 明示的なルール調査

利用者がlocal corpusのbundleまたはrule investigationを明示した場合だけ、
`references/core/rule-investigation.md` を読む。通常のreviewや改稿ではlocal corpus、
investigation、proposalを探索・読込みしない。調査の既定判断は `HOLD` とし、未説明の反例、
固定閾値だけの根拠、頻度だけの根拠、既存ruleのduplicateがあれば `PROMOTE` にしない。
`PROMOTE` をcoreへのapplyや安全保証として扱わない。

## 明示的な日本語構造sensor評価

利用者がGiNZAによるsyntax signalまたはLLM-onlyとのA/B評価を明示した場合だけ、
`references/core/syntax-sensor.md` を読む。通常のreviewや改稿ではparserを起動・installせず、
parserなしでも処理を継続する。parser outputは構造観測値に限定し、RR label、可読性、曖昧性、
改稿要否のground truthとして扱わない。A/B結果から既定利用を自動で有効化しない。

## 最終意味保存gate

返答または保存前に、元文と改稿案の事実、主体、行動、対象、数値、日付、条件、
例外、否定、因果、scope、義務、禁止、許可、推奨、可能性、不確実性、用語、
識別子、読者の行動、必要な返信、registerを比較する。

差分があれば黙って進めない。元へ戻す、承認が必要な意味変更候補として分離する、
または曖昧さを報告する。不足情報は不足のまま保つか、`[要確認]`、`[TODO]` などの
明示的なplaceholderで示す。
