# coverage-driven reviewの設計

## 状態

この文書は、長文の `review` と `repository-review` で確認範囲を監査可能にするための
実装済み設計を説明する。構造inventory、関係表現scanner、DB定義表の抽出は補助ツールであり、
文章上の問題や修正要否を自動判定しない。

## 背景と目的

長い文書を一度だけ総合判断すると、前半の目立つ問題を数件見つけた時点で探索が終わり、
後半の軽微な問題や章をまたぐ不整合が候補にも残らないことがある。件数の下限を設けると、
今度は問題の水増しや件数到達時の打切りを招く。

この設計では、検出と優先付けを分ける。

> Detect first. Prioritize later.

重大度は報告順や対応順に使えるが、候補を検出・記録する前の除外条件にはしない。目的は
多数の指摘を作ることではなく、どの範囲をどの観点で確認し、候補をどう処理したかを外部から
確認できるようにすることである。

## 適用条件

次のいずれかに該当する非破壊reviewへ適用する。

- 対象が複数の章・大きな表・複数fileにまたがる
- 一回のfocused passで全文と全観点を保持しにくい
- 利用者が網羅的な確認、coverage、見落とし防止を明示する
- 局所的な規則性や章をまたぐ用語・型の不一致を確認する

短い文書でも、利用者がcoverageを求めた場合は適用する。`revise-safe` などの改稿を同時に
依頼された場合も、review結果を先に確定してから別工程で改稿する。

## 処理モデル

処理順は次のとおりとする。

1. 文書と必要な周辺contextを読み、見出し、段落群、表、list、code fenceをinventory化する。
2. H1、H2、H3、段落群の順で構造単位を保ったchunkを作る。上限は補助条件であり、表、list、
   code fenceを途中で分割しない。
3. 各chunkを局所scanし、観点別にcandidateを記録する。0件でも確認済みなら `checked` とする。
4. 全chunkの記録を使い、文書全体の用語、定義、モダリティ、参照、pacing、局所整合性を
   cross-chunk passで確認する。
5. repository evidenceが必要なcandidateだけ、対象文書の参照や識別子から範囲を広げて確認する。
6. candidateを `finding`、`excluded`、`unresolved` に分類し、重複を統合する。
7. 全candidateを保持した後でseverityと対応優先度を決める。
8. findingsとcoverage summaryを返す。

固定文字数を文書品質の規則にはしない。補助ツールの上限を超える保護blockがある場合は、その
blockを壊さず一つのchunkとして残し、`partial` とlimitationsへ記録する。

## coverageの状態

観点とchunkには次の状態だけを使う。

| 状態 | 意味 |
|---|---|
| `checked` | 定義した範囲を確認した。候補・指摘が0件でもよい |
| `partial` | 一部を確認したが、未確認範囲または処理失敗が残る |
| `not-checked` | まだ確認していない。0件とは扱わない |

各観点には、状態、candidate数、finding数、excluded数、unresolved数、除外理由、未確認範囲を
記録する。candidate数は分類後の件数と一致させる。parserやscannerの失敗、未対応形式、時間・
権限による探索制約を「問題なし」へ読み替えない。

最低限の観点は次のとおりである。

- semantic preservation
- 情報構造
- 日本語または英語の構文・読み返しリスク
- 関係の省略
- モダリティとscope
- 局所整合性
- repository整合性（`repository-review` または根拠確認が必要な場合）

## candidateとfinding

scanner、parser、focused passが返すものはcandidateである。語の出現、少数値、統計的な優位だけを
findingにしない。candidateには安定したIDとsource、行・列または表のrowを付け、次のいずれかへ
必ず解決する。

- `finding`: 読者影響またはrepository evidenceにより報告対象とした
- `excluded`: 文脈確認により問題ではないと判断した。理由を残す
- `unresolved`: 必要なcontextや証拠が不足し、今回の範囲では確定できない

表示量を短くしてもcandidateを黙って捨てない。人向けの概要を短縮する場合は、完全な
machine-readable reportの保存先または残件を追跡できる識別子を示す。「主な3件」のような
top-Nを完了条件にしない。

## consolidatorの責務

consolidatorは、同じ原因を指すcandidateを統合できる。ただし、統合元のIDと全locationを保持する。
局所passのminor findingをglobal passのmajor findingで上書きせず、severityが低いことを除外理由に
しない。重複以外のcandidateを統合時に消さない。

## 補助ツールと障害時の扱い

`scripts/review_coverage.py inventory` はMarkdownの構造とchunkをJSONで返す。
`scripts/scan_relationships.py` は候補語の全出現位置をcandidate-only JSONで返す。
`scripts/scan_db_consistency.py` は対応するDB定義表を構造化し、明示されたpeer group内の分布と
少数値candidateを返す。
`scripts/review_coverage.py validate-report` はrootとclosed objectの必須・未知field、文字列list、
integer field、coverage固有の件数・参照整合性を検証する。JSONのbooleanをintegerとして受理しない。
`schema_version` もintegerとして検証し、`true` をversion 1として受理しない。
findingのseverityは `HIGH`、`MEDIUM`、`LOW` に限定し、欠落やそれ以外の値を拒否する。

ツールはAgentの判断を置き換えない。利用できない場合はLLM-onlyの確認を続け、coverageを
`partial` にして未実施処理を記録する。ツールの終了失敗をreview全体のhard failureにはしない。

## 来歴とreview gate

この設計は、2026-09-02に利用者から提示された長文での「正本」見落としと、DB定義で同じ役割を
持つ日時列の少数型を確認したいという事例を起点にしている。既存の関係明確性の支持例、法務用語・
文書内定義・明示済み関係の反例、異なるpeer groupの境界例をevalへ保持する。

候補抽出の閾値やlocal corpusの観察だけをcore ruleへ昇格しない。挙動変更は、positive、negative、
boundary fixture、既存eval全件、来歴を揃え、人間の明示reviewを受けてからverifiedと記録する。

## 制約

- coverageは完全性の保証ではない。未確認範囲を見えるようにする仕組みである。
- semantic peer groupは単純な全体頻度から自動確定できない。
- `UNEXPLAINED` は誤りを意味しない。
- reviewでは原文、schema、設定値を自動修正しない。
- repository探索は対象から段階的に広げ、無制限な全件走査を既定にしない。
