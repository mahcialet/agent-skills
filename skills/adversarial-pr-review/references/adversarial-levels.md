# Adversarial levels and evidence depth

敵対性levelと探索depthは独立した軸である。levelは想定する主体と能力、depthは調べる
証拠の広さを表す。priorityは影響と緊急度であり、どちらとも別に決める。

## A0〜A4

### A0: 合意的な正常利用

要件どおりの入力、通常の順序、主要なsuccess pathを確認する。契約、値、条件、UI、
互換性、通常時の状態遷移を中心に見る。

### A1: 偶発的な失敗と境界

A0に加え、誤操作、空値、境界値、timeout、retry、部分障害、偶発的重複、途中終了、
error handlingを確認する。通常の実行コードは少なくともA1とする。

### A2: 正規権限内の濫用

A1に加え、race、replay、順序操作、意図的重複、quota回避、cost増幅、resource exhaustion、
money・points・inventoryの二重反映を確認する。攻撃者は正規のentry pointと権限を持つが、
想定外の頻度・並行性・順序を選べる。

### A3: trust boundaryの突破

A2に加え、authorization bypass、tenant越境、IDOR、upload・parser injection、forged webhook
やcallback、secret露出、入力と認可contextの不一致を確認する。外部入力は攻撃者が制御し、
境界を越えることを意図する。

### A4: supply chain・特権主体の侵害

A3に加え、dependency、CI/CD、release、operator、IAM、PKI、signing、privileged workerの
侵害を前提に、blast radius、封じ込め、鍵失効、rollback、recovery、監査可能性を見る。
A4はあらゆる侵害を防げるという意味ではない。

## `level=auto`

変更されたassetとboundaryから必要な上限を選び、`minimum` 未満にしない。

- docs-onlyは、repository policyまたはユーザーが許し、実行可能な例、運用手順、
  security-sensitive configを含まない場合にA0候補となる。
- 通常の実行コード、error handling、timeout、retry、partial failureは最低A1。
- concurrency、queue、idempotency、money、points、inventory、quota、costはA2候補。
- auth、authorization、tenant、upload、webhook、parser、secret、外部入力境界はA3候補。
- CI、release、dependency verification、IAM、PKI、signingはA4候補。

trigger wordだけで決めず、変更がそのasset・boundaryへ実際に到達するか確認する。複数の
path ruleが一致する場合は最高levelを採用する。

## 明示levelとminimum

明示 `level=Ax` はreview上限である。A0からAxまでを含め、それより上位のtriggerはreviewを
拡張せず、残余リスクの `unreviewed higher-level threats` に記録する。

`minimum=Ax` は `level=auto` だけに適用する。明示levelと矛盾するminimumを使ってlevelを
上げない。指定の矛盾は入力上の注意として報告する。

## Evidence depth

### focused

diff、変更file全体、直接caller/callee、直結test、直接contractを調べる。狭いscopeを明示し、
推移的影響やhistoryを未確認として残す。

### standard

focusedに加え、全参照、類似・対称実装、config、schema、migration、lockfile、error path、
retry、timeout、rollbackを調べる。既定値。

### deep

standardに加え、history/blame、推移的影響、公式な外部仕様、競合・故障条件、運用経路、
rollback・recovery、supply-chain境界を調べる。外部資料を確認できない場合は推測で埋めず、
未検証として残す。

例: `A3 / focused` は攻撃者を想定するが探索範囲は狭い。`A1 / deep` は悪意を想定しないが、
故障と波及を広く追う。
