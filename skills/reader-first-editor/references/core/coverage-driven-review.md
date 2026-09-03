# coverage-driven review

長文、複数file、または網羅性を求められた非破壊reviewでは、一回の総合判断だけで完了しない。
重大度を付ける前に、確認範囲と観点を分けてcandidateを収集する。

## 実行順

1. 全文と必要な周辺contextを読む。
2. 見出し、段落群、表、list、code fenceをinventory化し、構造単位のchunkへ分ける。
3. 各chunkを、semantic preservation、情報構造、構文・読み返しリスク、関係の省略、
   モダリティとscopeの観点で局所確認する。
4. 全chunkを対象に、用語・定義・参照・pacing・モダリティ・局所整合性のglobal passを行う。
   話題のつながりが対象なら、入口、section間の移動、初出概念、文書目的から外れたblockも確認する。
5. 必要なcandidateだけrepository evidenceを確認する。
6. candidateを `finding`、`excluded`、`unresolved` に分類し、全locationを保持したまま重複を統合する。
7. すべてのcandidateを記録してからseverityと報告順を決める。

表、list、code fenceを途中で分割しない。構造blockが補助上限を超える場合はblockを保持し、
limitationsを記録する。固定文字数や固定件数を品質規則にしない。

Markdown fileを確認できる環境では、次のinventoryを補助に使える。

```bash
python3 scripts/review_coverage.py inventory --file <target.md>
```

空または空白のみのMarkdownはinventory段階で拒否する。report skeletonの作成と検証では、手製・
置換済みinventoryをcoverage根拠にしないため、inventoryと同じ元Markdownを再度渡す。

```bash
python3 scripts/review_coverage.py new-report --inventory <inventory.json> --file <target.md> --mode <review|repository-review>
python3 scripts/review_coverage.py validate-report <report.json> --inventory <inventory.json> --file <target.md> --mode <review|repository-review>
```

日本語の関係表現は、次のscannerで候補語の全出現位置を列挙できる。

```bash
python3 scripts/scan_relationships.py --file <target.md>
```

両ツールのJSONは候補収集を支援するだけで、文脈passとglobal passを省略しない。ツールがない、
未対応形式、読み込み失敗の場合はreviewを継続し、該当coverageを `partial` として理由を残す。
reportを検証するときは作成元のinventoryと元Markdownを渡す。validatorはMarkdownからinventoryを
再生成し、本文hash、全field、source、全chunk、既定の必須観点、candidate所属、局所passとglobal
passの順序を照合する。`repository-review` modeでは `repository-consistency` も必須観点にする。
coverage workflow artifactはschema v2を使い、旧v1は元Markdownから再生成する。

話題のつながりを独立して追跡する場合、現行schema v2が許す追加観点として
`--dimension discourse-continuity` を指定できる。既存v2 reportとの互換性を保つため既定の必須観点
には追加していない。Agentは各eligible blockのrole、anchor、`why_here`、初出概念を確認するが、
現行toolはparagraph edgeの全件確認を機械検証しない。toolだけを根拠に「全edgeを確認済み」と
表現しない。

## coverage記録

各chunkと観点に、次のいずれかを記録する。

- `checked`: 定義した範囲を確認した。0 candidatesまたは0 findingsでもよい。
- `partial`: 一部に未確認範囲、未対応形式、scanner/parser失敗、権限・時間制約がある。
- `not-checked`: 確認していない。0件とは表現しない。

観点ごとに、status、candidate数、finding数、excluded数、unresolved数、除外理由、未確認範囲を
示す。candidate数は分類した件数の合計と一致させる。`checked / 0 findings` と
`not-checked` を区別する。

## 検出と優先付け

重大度はcandidate収集後に付ける。LOWであること、前半ですでに複数件見つけたこと、概要の
表示上限を理由に探索や記録を止めない。supported findingをtop-Nへ縮めない。概要を短くする場合も、
全candidate、分類、locationをmachine-readable reportまたは追跡可能なappendixへ残す。

scannerやparserの出力はcandidateでありfindingではない。候補語、少数値、dominance ratioだけで
問題と決めず、文脈、semantic peer group、読者影響、repository evidenceを確認する。

## global pass

全chunkの局所確認後に必ず実行する。少なくとも次を確認する。

- 前半と後半の用語、定義、対象読者、前提の変化
- 章をまたぐ指示語、参照、条件、例外、モダリティ
- 同じ役割を持つ要素群の表記、型、nullable、default、constraint
- 全体の情報階層とpacing
- 話題のつながりを対象にした場合の入口、sectionの鎖、初出概念、改稿による新しいgap

global passを実施できなければcoverage全体を完了扱いにせず、その状態と理由を示す。

## consolidator

重複を統合するときは統合元candidate IDと全locationを保持する。異なる原因、異なる読者影響、
未解決candidateを一つの代表例へ縮めない。除外には文脈上の理由を必要とし、severityを理由にしない。

話題のつながりでは、確認済みno-changeを `excluded` と理由、情報不足で判定できないcandidateを
`unresolved` と不足内容へ分ける。未確認blockや独立したfresh-reader passを利用できなかった範囲は
`partial` または `not-checked` とlimitationsへ記録し、0 findingsへ読み替えない。

詳細な設計、report項目、補助ツールの位置付けは
[`docs/coverage-driven-review.md`](../../docs/coverage-driven-review.md)を参照する。
