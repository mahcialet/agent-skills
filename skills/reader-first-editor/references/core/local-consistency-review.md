# 局所整合性review

文書、表、schema、設定の中で同じ意味上の役割を持つ要素群に強い規則性がある場合、そこから
外れる少数例をoutlier candidateとして確認する。少数派であること自体は誤りの根拠にしない。

## 処理順

1. 比較する属性より先にsemantic peer groupを定義する。
2. group内の全要素とsource locationを列挙する。
3. type、nullable、default、constraint、命名、表記など、目的に関係する属性の分布を確認する。
4. 強いdominant patternから外れる値をcandidateとして記録する。
5. candidateが同じpeer groupに属するか、抽出・正規化の誤りでないかを文脈で再確認する。
6. 対象の参照、識別子、table・column名からrepository evidenceを限定的に探索する。
7. `EXPLAINED`、`UNEXPLAINED`、`CONTRADICTED`、`NOT-AN-OUTLIER` のいずれかへ解決する。

候補段階で修正しない。reviewまたはrepository-reviewの非破壊契約を維持する。

## semantic peer group

全file、全table、全columnの最多値を正解とみなさない。同じ業務上・技術上の役割を持つ根拠が
ある要素だけを比較する。名前のsuffix、同じtable、同じ表のsection、同じ生成元は候補群を
作る手掛かりにはなるが、それだけで同じ意味を確定しない。

たとえば、監査用日時列の `created_at`、`updated_at`、`deleted_at` は比較候補になり得る。
一方、暦日を示す `birth_date`、利用者の現地時刻を示す `local_time`、監査日時は、近い場所に
記載されていても同じpeer groupとは限らない。

groupを報告するときは、group名、選択基準、全member、除外した近接要素と理由を残す。

## candidate生成

dominance ratio、最低group件数、少数値の件数は、見直す候補を作るためのtripwireとして使える。
固定閾値をfindingの判定条件にしない。閾値に届かなくても文書上の明示規則と矛盾する要素は別の
観点で確認し、閾値に届いても意図的な例外なら問題として報告しない。

構造化できるMarkdown table、CSV、DDL、ORM schemaでは、可能な範囲で全rowを抽出してから
分布を作る。parserの失敗や未対応形式は `partial` とlimitationsへ記録し、問題なしとしない。
typeの正規化はdialectを固定して行う。たとえばPostgreSQLでは `TIMESTAMPTZ` と
`timestamp with time zone` を同じ表現へ正規化できるが、この対応を他のDBへ無条件に適用しない。

nullableを示すheaderと必須性を示すheaderは極性が逆である。`nullable` では `yes` を
`nullable`、`no` を `not-null` として扱う。`必須` では `yes` を `not-null`、
`no` を `nullable` として扱う。同じ表に `nullable` と `必須` の両方がある場合は、
`nullable` を抽出値として優先するが、両列の整合を確認できないためparser coverageを
`partial` とする。

実装済みの構造化parserはMarkdown tableを対象とする。semantic peer groupはAgentが文脈から
先に定義し、column名と必要ならtable名のpatternとして明示する。

```bash
python3 scripts/scan_db_consistency.py \
  --file <database-definition.md> \
  --dialect postgresql \
  --peer-group 'audit-timestamps=_at$' \
  --attribute type
```

出力の `declared_semantic_group` は、groupを呼出側が明示したことを示すだけで、名前のpatternが
意味上の同一性を証明したことを示さない。全memberを文脈で再確認する。CSV、DDL、ORM schemaの
構造化parserは未実装であり、その形式ではLLM-only確認を続けてcoverageを `partial` とする。

## repository evidence

candidateごとに、関連する範囲から次を確認する。

- schema、DDL、migration、column comment
- application code、validation、test、fixture
- ADR、設計書、README、CHANGELOG
- Git履歴。ただし履歴依存の理由、証拠競合、明示依頼がある場合に限る

探索したpath・検索語、見つかった証拠、見つからなかったもの、競合、未確認範囲を記録する。
大規模repositoryを無条件に全件走査しない。

呼出し中のSkillに同梱されたeval、example、testが同じ少数値patternを含んでいても、対象schemaの
例外理由には使わない。それらはreview手順の検証dataであり、対象文書がSkill自体を扱う場合を除き
repository evidenceから除外する。

## anomaly statusとevidence status

局所整合性の解決状態は `anomaly_status`、既存repository-reviewの5状態は `evidence_status` として
別fieldにする。

| `anomaly_status` | 意味 | `evidence_status`との関係 |
|---|---|---|
| `EXPLAINED` | 少数例だが、意図的な例外を示す根拠がある | 通常は根拠claimが `VERIFIED` |
| `UNEXPLAINED` | 探索範囲内で理由を確認できない | 通常は `UNSUPPORTED`。誤りではない |
| `CONTRADICTED` | 少数例が明示仕様・test・schemaなどと矛盾する | 同じ反証を使う場合は `CONTRADICTED` |
| `NOT-AN-OUTLIER` | peer group外、抽出誤り、または文脈上の差で候補を除外した | 必要な場合だけ証拠状態を記録する |

`CONTRADICTED` を使う場合は、何と何が矛盾するかを示す。同名の状態を独立した意味で二重定義せず、
anomalyの解決とrepository claimの判定をfieldで分ける。

重要:

```text
UNEXPLAINED != WRONG
```

根拠が見つからないだけでは型や値の変更を提案の前提にしない。追加確認を求める。

## 報告項目

candidateまたはfindingには最低限、次を含める。

- dominant patternと分布
- 少数例の値と全location
- peer groupの根拠と除外範囲
- 確認したrepository evidenceと未確認範囲
- `anomaly_status` と、該当する場合は `evidence_status`
- 読者・実装への影響
- 次に必要な確認

`EXPLAINED` は確認済み例外としてcoverage記録へ残すが、修正を求めない。`UNEXPLAINED` は
要確認として断定を避ける。`CONTRADICTED` は具体的な反証と影響を示す。

## 禁止事項

- global frequencyだけでpeer groupや正解を決めない。
- 少数派、珍しいliteral、閾値超過だけでfindingにしない。
- parserやscannerの出力をground truthにしない。
- evidenceがないcandidateを誤りと表現しない。
- review中に型、nullable、default、constraint、文書を自動修正しない。
