# 日本語構文解析

状態: optional sensor implemented（既定利用は無効）

GiNZA adapterが返すのは、日本語文の構造観測値であり、可読性の合否判定ではない。
通常のreviewからは自動起動せず、GiNZA、spaCy、modelをCoreの必須依存に含めない。そのため、
parserがない環境でもSkill全体の処理は継続する。

## 2026-08-30時点の確認結果

| package | version | metadata / 実測 |
|---|---:|---|
| `ginza` | `5.2.0` | MIT、Python `>=3.8`、wheel 21,203 bytes |
| `ja-ginza` | `5.2.0` | MIT License、model wheel 59,112,919 bytes |
| `spacy` | `3.7.5` | Python 3.12でmodel loadを確認したpin |
| `click` | `8.1.8` | 上記のisolated実行で使用したpin |

参照した公式metadata:

- [ginza on PyPI](https://pypi.org/project/ginza/)
- [ja-ginza on PyPI](https://pypi.org/project/ja-ginza/)
- [GiNZA repository](https://github.com/megagonlabs/ginza)

`ginza==5.2.0` と `ja-ginza==5.2.0` のdependency宣言では、spaCy `<4.0.0,>=3.4.4` が許容される。
repositoryに保存している再現可能な結果は、Python 3.12.13、`spacy==3.7.5`、`click==8.1.8` での
解析成功である。spaCy 3.8系でloadに失敗したという当時の観察については、exact version、error、
failure fixtureが残っていないため、この文書では3.8系の非互換をclaimしない。導入例はrecorded
fixtureと一致する3.7.5をpinしている。将来versionを変更する場合は、同じload testとrecorded
fixtureを再実行する。

初回installにはnetwork接続が必要である。約59 MBのmodel wheelに加え、spaCyやSudachiの依存も
取得する。通常のreviewがpackage installやmodel downloadを開始することはない。GiNZA modelは
packageに含まれるため、install済み環境での解析時にはmodelをnetworkから取得しない。

## 明示的な実行

Coreへ依存を追加せず、isolated environmentで実行する例:

```bash
uv run --python 3.12 \
  --with ginza==5.2.0 \
  --with ja-ginza==5.2.0 \
  --with spacy==3.7.5 \
  --with click==8.1.8 \
  python skills/reader-first-editor/scripts/analyze_ja.py analyze \
  --text-file /path/to/input-ja.txt
```

依存を導入せずに同じcommandを実行した場合も、失敗終了せず、exit code 0でavailability resultを
返す。

```json
{
  "available": false,
  "reason": "dependency-not-installed",
  "signals": null,
  "interpretation": "observation-only"
}
```

`model-not-installed`、`model-load-error`、`parse-error` も非致命resultである。これらを文章の誤りや
解析成功と読み替えず、LLM-onlyの処理を継続する。

## Sensor output

完全な形式は `schemas/syntax-signal.schema.json` で定義する。available resultは次を記録する。

- backend、backend version、model、model version、Python version
- 入力本文を複製しないSHA-256 hash
- 文数、token数、文節数
- 主述語までの最大距離、最大dependency distance
- modifier depth、連体修飾dependency distance
- 条件・例外・否定markerと指示語
- 同一述語へ対応付けた条件marker数、並列幅
- 解析時間とwarning

これらの観測値はtokenizationとparseに依存する。数値やmarkerだけを根拠に `RR-04` などを付与
しない。一つのparseが返っただけでは、読者が文を一意に解釈できる証拠にはならない。合成文の
recorded resultは `tests/fixtures/syntax/ginza-5.2.0-ja-ginza-5.2.0.json` に保存している。

## LLM-onlyとのA/B

`schemas/syntax-ab-input.schema.json` に従い、同じcaseを次の2条件で記録する。

```text
llm-only
llm-plus-signals
```

各observationにはcase ID、provider、model・version、host version、repeat index、status、
expected riskの有無、risk検出、unnecessary revision、semantic preservation、expected behavior一致、
syntax availability、処理時間を含める。CodexとGitHub Copilotの両providerを必須とする。

```bash
python3 skills/reader-first-editor/scripts/analyze_ja.py ab-report \
  --input /path/to/syntax-ab-observations.json
```

reportはRR recall、false-positive rate、unnecessary-revision rate、semantic-preservation rate、
expected-behavior accuracy、処理時間、parse-failure rateを条件間で比較する。さらに、provider別の
accuracyのspreadと、同じcaseに対するrisk判定のdisagreement rateも比較する。

paired result不足、unsupported／error、parser unavailable、semantic regression、false positiveや
unnecessary revisionの増加、provider別accuracy spreadまたはrisk disagreementの増加、改善なしの
いずれかがあれば `do-not-default` とする。
blockerがなく改善が観測されても `human-review-required` に留め、`default_enabled` は常にfalseで
ある。実際のCodex／GitHub Copilot resultは未収集である。resultを収集し、人間が確認するまでは
optional機能を既定化しない。

高度なcoreference、bridging reference、discourse relationが必要だという実文上の証拠が得られた
場合だけ、KWJAなどをexperimental backendとして比較する。重い依存をCoreへ追加しない。
