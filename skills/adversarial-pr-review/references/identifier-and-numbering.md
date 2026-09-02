# 識別子と採番

この文書は、`adversarial-pr-review` のreport内で相互参照する識別子と、
外部から持ち込む識別子の境界を定める。ここでいう採番は、reportの読者が
同じfindingや証拠を追跡できるようにするためのものであり、repository全体の
グローバルな連番ではない。

## 採番するreport内の項目

| 種別 | 形式 | 用途 | scope |
|---|---|---|---|
| finding | `F-001`, `F-002`, … | 到達経路と証拠で成立を確認した問題 | reportまたは明示したreview series |
| hypothesis | `H-001`, `H-002`, … | 根拠不足でfindingに昇格していない懸念 | reportまたは明示したreview series |
| evidence ledger | `E-01`, `E-02`, … | source、確認内容、結果、制約の行 | reportまたは明示したreview series |

`F`、`H`、`E` は別々のsequenceで管理する。桁数は既存reportとの参照互換性を
保つため、findingとhypothesisは3桁、evidenceは2桁を標準とする。上限を超えたら
ゼロ埋めを増やさず、`F-1000`、`H-1000`、`E-100` のように続ける。

### 新規reportとfollow-up

- 新しい対象または新しいreview seriesでは、それぞれ `F-001`、`H-001`、`E-01` から始める。
- 同じPR／対象のfollow-upで、前のreportを継続すると明示された場合は、既存IDを保持し、
  各sequenceの最大値の次から追加する。したがって、既存の `F-001`〜`F-004` に新しいfindingを
  追加する場合は `F-005` とする。
- PR番号だけでは継続を推測しない。前のreportまたは継続指定がない場合は、新しいreport-local
  scopeとして扱い、採番範囲をreportに明記する。
- finding、hypothesis、evidenceを解決・削除しても番号を再利用しない。分割・昇格・差し替えが
  あった場合は、新しいIDを付け、旧IDとの対応を本文またはledgerに残す。
- `## Evidence ledger` への参照は、同じreport内の1行に一意に対応させる。follow-upで既存の
  evidenceを引き継ぐ場合もIDを変えず、追加証拠だけを次の番号にする。

## 外部IDとカタログID

次のIDはこのSkillが採番しない。元のsourceにある表記をそのまま保持し、必要ならreport-local
IDとの対応を記録する。

| 種別 | 例 | 扱い |
|---|---|---|
| 外部レビューのfinding／hypothesis | `APR-01`、`HYP-01` | source-preserved。`F-*`／`H-*`へ黙って変換しない |
| PR、Issue、review discussion | `PR #123`、`Issue #123`、`discussion_r3917733760` | source pointerとして保持。番号を創作しない |
| sourceの要件・ADR | `AC-01`、`REQ-123`、`ADR-014 §3.2` | sourceに実在するときだけ引用する。要件が無い場合に割り当てない |
| 固定カタログ | `RR-01`〜`RR-16`、`P0`〜`P3`、`A0`〜`A4` | catalog／enumの定義を保持し、新しい順番を作らない |

外部findingをこのreportで再評価する場合は、外部IDをEvidence、Contract reference、または
本文のsource pointerへ残す。ローカルのfindingとして扱う必要がある場合だけ新しい `F-*` を
割り当て、`source: APR-01` のように対応を明記する。

## coverage auditの行

Change-obligation、relational-invariant、repository-ruleの行は、表の内容だけで追跡できる
なら採番しない。複数のfindingや証拠から直接参照する必要がある場合だけ、次のreport-local
IDを付ける。

| 行種別 | 任意ID |
|---|---|
| Change-obligation | `CO-001`, `CO-002`, … |
| Relational-invariant | `RI-001`, `RI-002`, … |
| Repository-rule obligation | `RO-001`, `RO-002`, … |

これらは `F`、`H`、`E` と独立したsequenceで、同一report内だけ一意にする。番号を付けたら、
linked finding／hypothesisとcoverage表の同じ行で同じIDを使う。単発のtable rowに番号を
追加して見かけ上の完全性を示してはならない。

## 採番しない項目

report本体とそのsectionには専用の連番を付けない。Target、base／head、`Identifier scope`、
およびsource pointerでreportを識別する。

Requirement traceability、Test evidence、Unexecuted validation、Residual risksは、既存の
source pointer、test名・command、または箇条書きの内容で識別できるため、専用の連番を必須に
しない。これらを別の項目から参照する必要が生じた場合だけ、`E-*` のledger entryから参照する。

reader-first-editorが生成するartifact ID（`rfe-*`、`rfb-*`、`rfi-*`、`rfp-*`、`rfrp-*`、
`rfrr-*`、`rfrt-*`、`rfa-*`、`rfsab-*`）や、`CHUNK-0001`、`REL-0001`、`DBROW-0001`、`DB-0001` は、
それぞれのschema／producerが定める別のscopeである。このreportの `F`／`H`／`E` と混ぜず、
手動で採番し直さない。
