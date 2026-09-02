# 話題のつながりの確認

## 状態

`discourse-continuity` は、段落・節・話題のつながりを確認する実装済みのAgent workflowである。
利用者向けには原則として「話題のつながり」と表現する。日本語と英語に同じcore手順を使う。

実装済み:

- 文書種別に応じた入口の確認
- eligible blockごとのrole、anchor、relation、`why_here`、初出概念の確認
- continuity candidateと修正可能性の分離
- `review`、`repository-review`、`revise-safe`、`revise-structural`、`authoring`、`jtf-only` の境界
- 改稿後のfresh-reader passと独立性不足の通知
- coverage schema v2の任意dimensionへの接続
- positive、negative、boundary、no-changeの日英eval

未実装:

- 専用のparagraph parserやcontinuity scanner
- paragraph edgeを永続化するcontinuity ledger schema
- relation、修正要否、severityの自動判定
- 新しいRR ID
- provider固有のsub-agent起動処理

詳細な規則は[core reference](../references/core/discourse-continuity.md)を参照する。

## 何を確認するか

文法的に正しい段落でも、読者が次を推測しなければならない場合がある。

- 文書が何を解決・説明するのか
- この段落が前段、見出し、文書目的のどれを受けるのか
- なぜ、この位置でこの話題を扱うのか
- 新しい製品名、actor、component、data store、scopeを今導入する理由
- 次に何を説明するのか

確認では、文書の入口と各eligible blockを先にinventory化する。各blockについてrole、anchor、
意味上のrelation、`why_here`、初出概念を記録し、候補を集めてからreader impactを判断する。

## 文書種別を先に決める

説明文、runbook、意思決定記録、障害報告、reference、FAQでは必要な入口が異なる。how-toへ論説文の
問題提起を追加したり、API option間へ物語上のtransitionを追加したりしない。

reference、FAQ、用語集、error code、設定一覧、release note、索引、比較表は、見出しや分類規則を
anchorに独立できる。直前項目と直接つながらないことだけでfindingにしない。

一方、外見がlistでも手順は順序依存である。各stepが上位goalと前後の状態をどう受けるか確認する。

## 「なぜここで？」を確認する

各対象blockについて、なぜこの位置に必要かを一文で説明する。

```text
前段で示した認証失敗が、長時間動作するclientへ与える影響を説明するため。
```

「Redisについて説明するため」のように対象名を言い直すだけでは配置理由にならない。説明できない
blockは削除対象ではなくcandidateである。bridge不足、前提不足、配置不良、scope不足、意図不明、
構造上の限界を区別する。

## 接続詞では判定しない

`また` や `however` があっても意味上のrelationが明示されているとは限らない。逆に、接続副詞が
なくても、前段が保存先の必要性を示し、次段がRedisを保存先として示すならrelationは明確である。

接続詞の有無、新語、語彙の変化はcandidate signalとして使えるが、findingや修正要否の判定器には
しない。

## 修正可能性

確認結果と、修正できるかどうかを分ける。

- `safe-bridge`: 本文または確認済みcontextだけで短いbridgeを作れる
- `local-reorder`: 近接blockの順序を変えても条件、scope、時系列、強調が変わらない
- `move-candidate`: 内容は有効だが別の位置を提案できる
- `heading-or-scope-candidate`: 見出しやscope明示で関係を示せる可能性がある
- `missing-prerequisite`: 読者に必要な前提が本文にない
- `intent-unknown`: 配置理由や目的を確認できない
- `evidence-gap`: relationを補うには未確認事実が必要
- `structural-limit`: 局所修正では足りず、導入や章構成の再設計が必要
- `no-change`: 関係が明確、または文書種別上独立している

この語彙は内部の作業用であり、schemaの閉じたenumではない。利用者には、確認できた関係、足りない
情報、読者影響、可能な次の対応を平易に返す。

## mode別の動作

| mode | 動作 |
|---|---|
| `review` | 原文を変えず、candidate、reader impact、不足情報、limitationsを報告する |
| `repository-review` | 明示された場合だけrepository evidenceでrelationや目的を確認する |
| `revise-safe` | 一意に確認できる局所bridge、目的明示、近接reorderだけを行う |
| `revise-structural` | section移動、見出し、scope分割、appendix化、前提追加をproposalとして示す |
| `authoring` | entry chainとsection chainを先に作り、不明な関係をTODOにする |
| `jtf-only` | 話題のつながりを診断・変更しない |

`revise-safe` では、大規模移動、段落削除、原文にない因果・目的・前提・actorの追加を行わない。
`revise-structural` でも、明示的な削除許可がなければ削除しない。

## fresh-reader pass

改稿後は、変更箇所前後、入口、全文の順に再確認する。可能なら別contextへ、改稿後本文、想定読者、
文書目的、必要なtechnical contextだけを渡す。改稿理由、元の作業表、変更箇所、期待する正解は
渡さない。

別contextを利用できなければ同一Agentで補助passを行えるが、独立した初見確認ではないことを
limitationとして示す。単独の `review` へ形式的な改稿後passを追加しない。

## coverage reportへの接続

長文では既存のcoverage workflowを使い、必要に応じて追加dimensionを指定する。

```bash
python3 scripts/review_coverage.py new-report \
  --inventory <inventory.json> \
  --file <target.md> \
  --mode review \
  --dimension discourse-continuity
```

`discourse-continuity` は既定dimensionへ追加していないため、既存schema v2 reportとの互換性は
変わらない。candidateは既存reportへlocation付きで記録し、`finding`、`excluded`、`unresolved` に
分類する。no-changeは `excluded` と理由、情報不足は `unresolved` と不足内容を残す。

現行toolはparagraph edge、role、anchor、relation、`why_here` の全件確認を機械検証しない。schema
validationの成功を、全段落のつながりを確認した証拠として扱わない。未確認block、非対応形式、
独立したfresh-reader passを使えなかった範囲は `partial` または `not-checked` とlimitationsへ残す。

## 安全に修正できない場合

次を利用者へ示す。

- 対象箇所
- 確認できたこと
- 不足していること
- 推測して修正しなかった理由
- 安全に行える範囲
- 必要な追加情報
- 情報が得られた場合の修正候補
- 局所修正で足りるか、構造再設計が必要か

安全に修正できないことは失敗ではない。もっともらしいrelationを作るより、不足を不足のまま示す。
