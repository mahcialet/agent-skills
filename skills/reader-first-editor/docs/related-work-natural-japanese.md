# `natural-japanese`との目的・設計上の関係

## この文書の目的

この文書は、[`coji/natural-japanese`](https://github.com/coji/natural-japanese)を
先行実装として調査し、`reader-first-editor`へ何を取り込むか、何を取り込まないかを
判断した記録である。一般的な製品比較や優劣の評価ではない。

調査は2026年9月3日に、次のrevisionを固定して行った。

| 対象 | revision |
|---|---|
| `agent-skills`の実装基点 | `a763873c8da484972bef76c89d930a7d4420ff13` |
| `coji/natural-japanese`の`main` | `0f1cc1c5a4e2aa7590598c88a15c213a60d9545a` |

参照revisionへ継続的に自動追従はしない。将来再評価する場合は、その時点のrevisionを
別途記録する。

## 目的の違い

両Skillは、日本語の文章を機械的に観察し、最終判断を文脈へ残す点で領域が重なる。
ただし、最適化する対象は異なる。

- `natural-japanese`は、AIらしい表現や構造を検出し、自然な日本語へ近づける機能を
  含む。自然度scoreや、人間文とAI文の違いを使った校正も扱う。
- `reader-first-editor`は作者を判定せず、人間とAIの双方が意味、関係、条件、例外、
  情報階層を誤読せず、不要な再読や推測をせずに理解できることを目指す。
  styleや自然さより先に意味保存を適用する。

このため、AIらしく見える表現でも意味と関係が明確なら変更しないことがある。反対に、
自然な表現でも主体や条件のscopeが曖昧なら、読者負荷の候補として扱う。均質な表現が
結果として減ることはあっても、AIらしさの低減自体は成果指標にしない。

## 一致する設計思想

次の方向は一致している。

- deterministicな処理は候補を列挙し、findingかどうかはAgentまたは人間が文脈で判断する
- genreによる違いを考慮し、一つの表面規則や数値thresholdを普遍化しない
- 構文解析やembeddingなどの重い処理を、通常の確認から分離する
- corpusの結果が仮説と逆なら、検出器の撤回や格下げを正常な結果として扱う
- 再配布できない本文を無条件にrepositoryへ保存しない

`reader-first-editor`には、coverage inventory、関係候補scanner、DB peer group分析、
local corpus、counterexample-firstなrule調査、optionalなGiNZA sensorがすでにある。
一致する思想はこれらの既存契約を補強する根拠として参照し、同じ責務の実装を並立させない。

## 採否

分類は次の意味で使う。

- `ADOPT`: 目的と安全契約が一致し、既存実装でも維持する
- `ADAPT`: 方向は一致するが、reader-firstの目的と安全条件へ読み替える
- `REJECT`: 目的または意味保存契約と衝突するため採用しない
- `DEFER`: 追加価値、eval、依存、互換性の検討が不足しているため保留する

| upstreamの要素 | 分類 | 判断 |
|---|---|---|
| 機械的な候補抽出と文脈判断の分離 | `ADOPT` | 既存scannerのcandidate-only契約を維持し、hitをfindingやAI生成の証拠にしない |
| 行番号を保持した候補抽出 | `ADOPT` | 既存のcoverage、関係候補、DB分析がlocationを保持しており、新しい基盤は追加しない |
| genre別の分析と単一thresholdの非普遍化 | `ADOPT` | reader、purpose、genreを先に決め、表面頻度だけで変更しない |
| 重い解析をoptional laneへ分離 | `ADOPT` | 現行GiNZA adapterの非致命failureと`default_enabled=false`を維持し、新依存は追加しない |
| corpusで仮説を反証する手順 | `ADAPT` | human/AI弁別率ではなく、意味保存、不要改稿、coverage、provider差などで評価する |
| Markdown masking | `ADAPT` | literal保護は一致するが、見出し、表、listを確認対象から落とさない。別parserは追加しない |
| copyrighted corpusのlocal取得 | `ADAPT` | 現行のrights、provenance、reference-only、local-only契約を優先する |
| AIらしさ・自然度の0〜100 score | `REJECT` | 読者影響や意味保存と一致せず、score最適化が不要な言い換えを誘発する |
| 人間文とAI文の分類精度を成果指標にする | `REJECT` | 作者推定はSkillの目的ではない |
| 禁止語や定型句の除去数を成果にする | `REJECT` | 語の存在だけでは読者影響を示せず、確信度やregisterを変えるおそれがある |
| 文体規則を全genreへ一律適用する | `REJECT` | 手順書、reference、仕様書には均質な構文やlabel見出しが有効な反例がある |
| `outline.py`相当の追加 | `DEFER` | 既存inventoryとの重複、H4以降やblockquoteの価値、schema互換性を示すevalがない |
| `terms.py`相当の追加 | `DEFER` | 専門語の説明要否を表面だけで決められず、Sudachiなしのportable設計も未確定 |
| findingのbaseline比較 | `DEFER` | 移動、分割、統合、accepted exceptionを安全に同一視するidentityが未設計 |
| embedding、style profile、quick/full mode | `DEFER` | 説明可能性、依存、scope、privacy、coverage改善の証拠が不足している |

## 今回反映したもの

今回の変更は次に限定する。

1. AIらしさの除去や作者判定が目的ではないことをREADMEとSkill契約へ明記する。
2. この文書とNOTICEへ、目的の違い、採否、参照revision、licenseを記録する。
3. 表面上の自然さとreader-firstの判定が独立であることを、既存eval suiteへ追加する。

新しいscanner、parser、outline、terms、baseline、corpus runner、dependencyは実装していない。
upstreamのcode、文書本文、禁止語一覧、corpus、report、数値thresholdもコピーしていない。

## Licenseとattribution

`coji/natural-japanese`はMIT Licenseで公開されている。確認した`LICENSE`には
`Copyright (c) 2026 coji`と記載されている。今回の利用は設計上の概念参照に限る。
詳細は[`../NOTICE.md`](../NOTICE.md)を参照する。

`reader-first-editor`は独立した非公式のSkillである。この参照は、upstream作者による
推奨、提携、互換性、同等性を示さない。将来codeまたは相当量の文書を適応する場合は、
対象file、copyまたはadaptした範囲、変更内容、copyright notice、MIT License noticeを
実態に合わせて追加する。

## 再評価条件

保留項目は、次の証拠を用意できた場合に別の事前検査で再評価する。

- 既存機能では取得できない情報と、追加機能による読者上の改善を示せる
- positive、negative、boundary、no-changeのevalがあり、表面patternを正解にしない
- unnecessary revisionとsemantic regressionを増やさない
- 長文の後半、表、list、blockquote、protected literalのcoverageを後退させない
- parserやmodelがなくても通常reviewを継続できる
- schema互換性、provider portability、license、privacyを説明できる

これらを満たすまでは、保留項目を利用可能または実装済みとは表現しない。
