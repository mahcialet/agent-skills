# 話題のつながり

内部機能名は `discourse-continuity` とする。利用者向けには、原則として「話題のつながり」と
表現する。目的は接続詞を増やして文章を滑らかに見せることではない。タイトル、導入、目的、
各段落・節の関係、新しい概念の初出を確認し、読者が「なぜここでこの話をするのか」を推測する
負荷を減らす。

中核契約:

```text
つながらない段落を不要と決めつけない。
文章のつながりを作るために、原文にない因果、目的、前提、設計判断を作らない。
安全に直せない部分は、直したふりをせず利用者へ示す。
```

この手順は `semantic-preservation.md` を置き換えない。bridge、並べ替え、見出し、scope変更を
検討する前後に、特に因果、目的、条件、例外、scope、modality、actor、時系列を比較する。

## 適用範囲

次の場合に使う。

- 複数段落・複数sectionを持つ文書
- 導入で示した目的と後続sectionの関係を確認するreview
- 話題が唐突、新しい概念が準備なく現れる、配置理由が分からないという依頼
- 段落やsectionを追加・並べ替えた後の改稿
- `authoring` で文書入口とsectionの鎖を先に設計するとき

一文だけの局所修正、用語や表記だけの修正では通常適用しない。`jtf-only` では適用しない。

## 先に文書種別と入口を確認する

すべての文書へ「背景→問題→解決」を強制しない。タイトルから最初の主要sectionまでを読み、
文書種別に合う入口の鎖があるか確認する。

- 説明・論説: 読者の状況 → 問いまたは問題 → 目的 → scope → 最初の主張
- how-to・runbook: 達成する作業 → 対象読者 → 前提 → 最初の操作
- 意思決定記録: 背景 → 制約 → 決定すべき対象 → 決定
- 障害報告: 事象 → 影響 → 現在状態 → 時系列または対応
- reference・FAQ: 対象範囲 → 分類規則または検索入口 → 独立項目

これは固定templateではなく確認例である。入口にある全要素を必須にせず、読者が文書の目的、
自分との関係、次に読む内容を予測できるかを確認する。

## eligible blockを追跡する

通常段落、見出し直下の導入、手順、注意、例、calloutなど、読者が意味上の役割を判断するblockを
対象にする。表、list、code fenceを途中で分割しない。

API option、用語集、FAQ、error code、設定一覧、release note、索引、比較表などは、直前blockでは
なく見出し、scope、分類規則との関係で理解できることがある。その場合は
`independent-under-heading` または `not-applicable` とし、線形な物語へ変えない。

内部の作業記録では、各eligible blockについて少なくとも次を確認する。

- location
- そのblockの役割
- anchor: 前段、見出し、数段落前の主張、文書目的、上位手順など
- 意味上のrelation
- `why_here`: なぜこの位置に必要かを説明する一文
- 初めて導入する概念、actor、component、data store、protocol、時点、環境、scope
- 開始、停止、待機、継続、再開するactor・動作・対象と、その遷移条件
- 確認済み、candidate、unresolved、not-checked、not-applicableの別
- candidateの場合の修正可能性とlimitation

内部記録の語彙を新しいschemaや利用者向けlabelとして固定しない。全eligible blockを確認したかを
追跡するための作業表であり、relation labelの一致率や件数を品質指標にしない。

## anchorとrelationを確認する

各blockを直前の段落だけへ接続しない。適切なanchorは次のいずれでもよい。

- 直前の段落・手順
- 直近の見出し
- 数段落前の主張・問い
- 文書全体の目的・scope
- procedureの上位goal
- referenceの分類規則

relationの内部語彙には、`start`、`continue`、`elaborate`、`reason`、`evidence`、`result`、
`contrast`、`example`、`condition`、`exception`、`comparison`、`solution`、`procedure`、
`conclusion`、`independent-under-heading`、`unknown` などを使える。閉じたenumではない。

primary relationは、判断できる場合に一つ置く。secondary relationは、複数の関係が読者影響や
修正判断を変える場合だけ補助的に置く。labelより `why_here` の平易な説明を優先する。
`transition` や「話題転換」だけでは、なぜその話題が必要かを説明したことにならない。

十分な `why_here` の例:

```text
前段で示した認証失敗が、長時間動作するclientへ与える影響を説明するため。
```

不十分な例:

```text
Redisについて説明するため。
```

後者では、なぜRedisをここで説明するのか分からない。説明できないblockは削除対象ではなく、
追加contextとreader impactを確認するcontinuity candidateとする。

## 接続標識と意味上の関係を分ける

`また`、`さらに`、`一方で`、`therefore`、`however` などの接続標識はcandidate signalにはなるが、
relationの証拠にはならない。

```text
また、Redisについて説明する。
```

この文だけではRedisを扱う理由は分からない。一方、次は接続副詞がなくても関係が明確である。

```text
refresh tokenをserver側で保持するには保存先が必要になる。
ここではRedisを使う。
```

接続詞がない、topic語彙が変わる、新語が現れるという事実だけでfindingにしない。前後の意味、
見出し、文書目的、読者影響を確認する。

## 語彙の連続と論点の連続を分ける

同じ主題語や名詞が隣接blockに現れても、話題のつながりが成立するとは限らない。各blockがその語に
ついて何を述べているかを比較する。

- actorや対象の役割
- 述語が示す動作、状態、判断
- 答えようとしている問い
- 評価軸や観察軸
- 原因、結果、条件、時点、scope

たとえば、前段が「どこで誰が判断するか」を説明し、次段が「なぜ時間が増えるか」を説明するなら、
共通の名詞があっても段落の役割と問いは切り替わっている。切替え自体を問題にせず、前段までの情報と
見出し・文書目的だけを使って「なぜ次にこのblockを置くのか」を一文で説明できるか確認する。

配置理由がさらに後のblockを読んで初めて分かる場合は、後続情報で前の境界を読めたことにせず、
理由が後置されたcontinuity candidateとして記録する。その後、後続情報が関係を一意に示すことを
確認できた場合だけ、既存文の局所的な並べ替えまたは短いbridgeを検討する。複数の関係が成立し得る
場合は本文を補わず、必要な情報を示す。

## 過程の停止と継続を対応付ける

停止、止める、中断、待機、継続、続ける、再開、終了など、動作や状態の遷移を示す表現が現れたら、
単語どうしではなく過程の参加者と動作を対応付ける。少なくとも、読者の判断や操作に必要な範囲で
次を確認する。

- 誰・何が停止などの状態変化を起こすか
- 誰・何の動作が変化するか。状態変化を起こす主体と同じとは限らない
- どの動作が開始、停止、待機、継続、再開、終了するか
- その動作の対象は何か
- どの条件・時点・eventで状態が変わるか
- その間またはその後に、別の主体・動作・対象が続くか
- 後続文の省略された主体と動作を前の記述から一意に戻せるか

一つの動作が止まっても、過程全体や同じ主体の全動作が止まるとは限らない。

「行き詰まる」のように広い停滞を表す語と、同じ主体に関する別の動作が同じ文脈にある場合も、
字面だけで矛盾または整合と決めない。本来進めたい動作、進まない動作、別に続く動作または未完了の
状態を分ける。

```text
根拠がそろわず行き詰まると、追加確認がいつまでも完了しません。
```

人の活動全体が止まるのではなく、特定の選定や判断を進められず、別の確認が未完了のままになる意味
とも読める。しかし、何が進まないのかを「行き詰まる」にまとめたため、追加確認の未完了状態との
関係を読者が戻って解釈する必要がある。本来の動作を周囲から確認できるなら、`revise-safe`では
その動作だけを次のように明示できる。

```text
根拠がそろわないと、担当者は候補を選定できず、追加確認がいつまでも完了しません。
```

本来の動作を一意に確認できなければ、「判断」「実装」などを推測して補わず、何が進まないのかを
要確認として示す。未完了状態を能動的な継続へ変える場合も、そのactionをcontextから確認できなければ
主体やmodalityを補わない。

```text
gatewayは新規requestの受付を停止します。
workerは受付済みrequestの処理を完了まで続けます。
```

停止するのはgatewayによる新規受付であり、続くのはworkerによる受付済みrequestの処理である。
主体、動作、対象が異なるため矛盾ではなく、語の対照だけでfindingにしない。

「operatorがgatewayの受付を停止する」のように、状態変化を起こす主体と動作が止まる主体が異なる
場合もある。文法上の主語だけを、停止する過程のactorとして記録しない。

一方、次はcandidateになる。

```text
障害を検知すると停止します。
その後も処理を続けます。
```

何が何を停止し、誰のどの処理が続くかを一意に確認できない。見出しや前段から補える可能性を確認し、
確認できなければactor、動作、対象、時間関係の不足とreader impactを示す。「systemが受付を止め、
workerが既存jobを続ける」など、もっともらしい実装を本文へ作らない。

同じactor・動作・対象について停止後の継続が書かれている場合は、再開条件、別phase、既処理分などの
区別が本文にあるか確認する。区別がなければ過程の不整合candidateとする。逆に、明示された条件後の
再開や、異なる動作の継続はno-changeにできる。停止や継続を示す語の出現だけではcandidateやfindingに
しない。

## 新しい概念の初出を確認する

概念、固有名詞、略語、製品、component、actor、data store、protocol、exception、評価軸、時点、
環境、scopeが初めて現れる箇所を確認する。初出であること自体は問題ではない。

- 前段や見出しから導入理由が分かるか
- 読者に必要な前提がすでにあるか
- 名前の前に役割を説明する必要があるか
- technical literalや検索語として名前を先に示す方がよいか
- 後段を読んでから前へ戻らないと理解できないか

technical literal、API名、UI label、error codeは検索性のため名前を先に示す方がよい場合がある。
一律に「役割を説明してから名前を出す」へ変えない。

## candidateとfindingを分ける

次はcandidate signalであり、単独ではfindingではない。

- `why_here` を一文で説明できない
- 新しい語・actor・scopeが初出する
- 接続詞がない、または接続詞と意味関係が合わない
- 同じ主題語が続いていても、段落の役割、述語、問い、評価軸が説明なく切り替わる
- 停止する主体・動作・対象と、続く主体・動作・対象を対応付けられない
- 同じ主体・動作・対象が、再開条件なしに停止後も継続すると記述されている
- 配置理由が後続blockを読まないと分からない
- topicや語彙が大きく変わる
- 直前段落とのrelationが見つからない

適切な見出しや文書目的がanchorになっていればno-changeにできる。relationが確認できなくても、
追加context不足なのかreader impactが成立するのかを確認してからfindingへ分類する。

## 検出結果と修正可能性を分ける

candidateを次の観点で分類する。この語彙も永続schemaの閉じたenumではない。

- `safe-bridge`: 前後関係が本文または確認済みcontextから一意に確定し、短いbridgeで明確になる
- `local-reorder`: 近接blockの順序を変えても条件、scope、時系列、強調が変わらない
- `move-candidate`: 内容は有効だが現在位置の理由を説明しにくく、移動先を提案できる
- `heading-or-scope-candidate`: 見出し、節分割、scope明示で関係を示せる可能性がある
- `missing-prerequisite`: 理解に必要な前提が本文にない
- `intent-unknown`: なぜ扱うかを本文・指定contextから確認できない
- `evidence-gap`: 因果や目的を補うには未確認の事実が必要
- `structural-limit`: 局所bridgeや近接reorderでは足りず、導入・章構成の再設計が必要
- `no-change`: 関係が明確、または文書種別上独立している

continuityの判定と修正可能性は直交する。findingでも安全な改稿が `intent-unknown` のため不可能な
場合がある。candidateがno-changeなら確認済み除外として残し、修正を要求しない。

## 検出してから改稿する

次の順を変えない。

```text
入口とeligible blockを確認する
  → role、anchor、relation、why_here、初出概念を記録する
  → candidateを列挙する
  → 文脈、文書種別、意味保存を確認する
  → 修正可能性を分類する
  → 許可されたmodeの範囲で改稿する
  → 変更箇所前後、入口、全文を再確認する
  → fresh-reader passを行う
  → 未解決事項と限界を通知する
```

先に改稿してから、もっともらしいrelationを説明として後付けしない。

## mode別の境界

- `review`: 原文を変えない。candidate、読者影響、修正可能性、不足情報、limitationsを報告する
- `repository-review`: 明示された場合だけrepository evidenceでrelationや目的を確認する。根拠が
  見つからないことを「関係がない」という証拠にしない
- `revise-safe`: `safe-bridge`、意味を変えない近接reorder、既存情報による短い目的明示だけを行う。
  sectionをまたぐ大規模移動、削除、推測した因果は行わない
- `revise-structural`: section移動、見出し、scope分割、appendix化、前提追加、削除をproposalとして
  示せる。削除許可がなければ削除せず、不足情報があれば確定稿にしない
- `authoring`: entry chainとsection chainを先に作り、不明な因果・目的・前提はTODOまたは要確認にする
- `diff`: bridgeや構造候補ごとに根拠と意味リスクを対応付ける
- `jtf-only`: 話題のつながりを診断・変更しない

## 安全なbridgeを確認する

bridgeへ追加する内容が、元文または明示・検証済みcontextから一意に導けるか確認する。自然に
読めることは意味保存の証拠ではない。次の差分が一つでも根拠なく増える場合は本文へ加えない。

- 因果、理由、目的、結果
- actor、責任、対象
- 条件、例外、scope、modality
- 時系列、優先順位、設計判断
- 停止対象、継続対象、再開条件、過程の状態
- 確実性、不確実性

安全に確定できなければ原文を維持し、本文外へ必要情報を示す。

## 修正できない場合の通知

安全に修正できない箇所を黙って残したり、つながったように見せかけたりしない。利用者へ次を
平易に示す。

- 対象箇所
- 確認できたこと
- 不足していること
- 推測して修正しなかった理由
- 安全に行える範囲
- 必要な追加情報
- 情報が得られた場合の修正候補
- 局所修正で足りるか、構造再設計が必要か

`discourse-continuity`、relation label、repairability labelを既定の見出しとして出さず、利用者向け
には「話題のつながり」「この位置で扱う理由」「追加で確認したい情報」などを使う。

## 改稿後のfresh-reader pass

改稿した場合は、変更箇所の前後、入口の鎖、全文の順に読み直し、新しいgapや意味変更がないかを
確認する。可能なら改稿担当とは別のcontextへ次だけを渡す。

- 改稿後の本文
- 想定読者
- 文書目的
- 理解に必要なtechnical context

次は渡さない。

- 改稿理由
- 元のcontinuity作業表
- 変更箇所の説明
- 書き手の意図を補う内部メモ
- 期待する正解

fresh-readerは、現在の話題、前段・見出し・目的との関係、新概念の準備、前へ戻らず理解できるか、
次の内容を自然に予測できるか、誰のどの動作が止まり何が続くかを追えるかを確認する。
別contextを使えなければ同一Agentで補助passを続けるが、
「独立した初見確認ではない」というlimitationを明記する。改稿しない単独 `review` へ形式的な
改稿後passを追加しない。

## coverage-driven reviewへの接続

長文・複数sectionでは `coverage-driven-review.md` と併用する。現在のcoverage schema v2とtoolは
任意dimensionを受理するため、必要に応じて `--dimension discourse-continuity` を追加できる。
`DEFAULT_DIMENSIONS` へは追加しないため、既存v2 reportの互換性は変わらない。

continuity candidateは既存のcandidateへlocationとともに記録し、確認後に `finding`、
`excluded`、`unresolved` のいずれかへ分類する。確認済みno-changeは `excluded` と理由、情報不足は
`unresolved` と不足内容を残す。未確認範囲はrootの `limitations` と観点の `unchecked_scope` へ
記録し、0 findingsへ読み替えない。

現在のtoolは個々のparagraph edge、role、anchor、relation、`why_here` を機械検証しない。これらは
Agentの作業記録であり、全edgeをtoolが検証済みとは表現しない。局所pass後のglobal passでは、
入口の鎖、section間の移動、初出概念、blockをまたぐ過程の停止・継続・再開、全文の目的から外れた
block、改稿による新しいgapを確認する。

## 初版の実装境界

初版で実装済みなのは、このAgent workflow、既存coverageへの任意dimension接続、examples、evalで
ある。専用parser、scanner、永続continuity ledger schema、自動relation判定、severity判定、
新しいRR IDは実装していない。toolがない、または独立contextを使えない場合もreviewを継続し、
coverageとlimitationを正直に記録する。
