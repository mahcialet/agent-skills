# 日本語構造sensorの実行契約

このreferenceを読むのは、利用者がGiNZAによるsyntax signalまたはLLM-onlyとのA/B評価を
明示した場合だけである。通常の `review`、`revise-safe`、`repository-review` ではparserを
起動しない。optional packageのinstall、model download、syntax fixtureの読込みも行わない。

## 観測と判断を分離する

`scripts/analyze_ja.py analyze` の出力は、文数、文節数、dependency distance、modifier depth、
条件・例外・否定marker、指示語、並列幅などの観測値である。`interpretation` は常に
`observation-only` とする。

次をparser outputだけから決めない。

- RR label、severity、可読性の合否
- 曖昧である、または曖昧でないという判定
- 改稿の要否
- semantic preservation
- rule promotion

Agentは原文、読者、目的、genre、contextを読み、signalが示す構造を本文上で確認する。固定閾値
だけでFAILにせず、数値を満たすために文章を機械的に短くしない。

## Availability

`available: false` は文章の誤りを意味しない。`dependency-not-installed`、`model-not-installed`、
`model-load-error`、`parse-error` を区別して記録し、LLM-onlyの処理を継続する。通常reviewを
失敗扱いにせず、成功したsignalがあるようにも装わない。

available resultではbackend、backend version、model、model version、Python version、text hashを
確認する。異なるversionの結果を同一条件として比較しない。

## A/B評価

同じcase、provider、model version、host version、repeat indexで `llm-only` と
`llm-plus-signals` を対にする。CodexとGitHub Copilotの両方を含め、RR recall、false positive、
unnecessary revision、semantic preservation、expected behavior accuracy、処理時間、parse failure、
provider間のrisk判定差を比較する。

改善なし、semantic regression、false positiveまたはunnecessary revisionの増加、provider差の増加、
parser unavailable、paired result不足のいずれかがあれば `do-not-default` とする。自動blockerが
なく改善が観測されても `human-review-required` に留め、toolだけで既定利用を有効化しない。

install条件、CLI例、schemaは `docs/syntax-analysis.md` を参照する。
