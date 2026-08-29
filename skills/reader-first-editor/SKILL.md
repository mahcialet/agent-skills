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

各指摘のprefixは `[証拠種別][判定状態][HIGH|MEDIUM|LOW]` とする。支持・反証の
証拠がない指摘は証拠種別に `[EVIDENCE-GAP]` を使い、種別を省略しない。

## literalと構造化要素を保護する

ユーザーが明示的に対象へ含めない限り、コードブロック、inline code、コマンド、
パス、URL、識別子、設定キー・値、UIラベル、エラーメッセージ、Markdownリンク先、
参照ラベル、表構造、anchorを書き換えない。検索可能な技術用語を維持する。

## 編集前に診断する

`references/core/reread-risk.md` を使い、重要な指摘だけを報告する。

- `HIGH`: 誤読、条件・scopeの誤認、行動ミス、複数回の読み返しにつながる。
- `MEDIUM`: 理解速度を明確に下げる、または情報階層を隠す。
- `LOW`: 表記統一や局所的な流れに限られる。

文長、同じ文頭、受身、段落長を自動的な不合格条件にしない。context内で再読する
ためのtripwireとして使う。

## 必要なreferencesだけを読む

常に読む。

- `references/core/semantic-preservation.md`
- `references/core/revision-procedure.md`
- `references/core/output-modes.md`

原則またはrisk解釈が必要なら読む。

- `references/core/principles.md`
- `references/core/reread-risk.md`

日本語は `references/ja/japanese-techniques.md` から始め、主題、構文、モダリティ、
register、pacing、技術内容、ジャンル、JTF層へ振り分ける。構造決定後にだけ
`references/ja/jtf-alignment.md` を適用する。

英語は `references/en/english-techniques.md` から始め、該当する場合だけ
`references/en/idiomaticity.md` または
`references/en/rhythm-and-pacing.md` を読む。

日英混在文ではliteralと用語を先に保護し、各言語層をそれぞれのproseへ適用する。
依頼されていない翻訳をしない。

## 最終意味保存gate

返答または保存前に、元文と改稿案の事実、主体、行動、対象、数値、日付、条件、
例外、否定、因果、scope、義務、禁止、許可、推奨、可能性、不確実性、用語、
識別子、読者の行動、必要な返信、registerを比較する。

差分があれば黙って進めない。元へ戻す、承認が必要な意味変更候補として分離する、
または曖昧さを報告する。不足情報は不足のまま保つか、`[要確認]`、`[TODO]` などの
明示的なplaceholderで示す。
