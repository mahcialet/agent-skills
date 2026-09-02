# Coverage-gap audit例: 初回findingにない3系統を確認する

この例のcode pathとfileはsynthetic fixtureである。historical provenanceは、一般化の契機となった
review commentを示すだけであり、runtimeでlive PRを取得する必要はない。

## Scope and parameters

- Target: schema-backed review resultへ2 fieldを追加する変更
- Repository label: `sample-repo`
- Base / head: `main` / synthetic review head
- Level / minimum / depth / mode: `A1` / `A1` / `deep` / `review`
- Selection rationale: normal producer、alternate mode、validator、consumer、repository companionを追う
- Excluded scope: production service、external API、A2〜A4
- Identifier scope: new report

## Review contract

- Specification status: sufficient
- Purpose / actors: review runnerがstatusとevidence typeを一貫して受け渡す
- Criteria sources: result schema、base `AGENTS.md`、consumer contract
- Expected outcomes: 全producerがpaired fieldを生成し、valid relationshipだけをconsumerへ渡す
- Forbidden outcomes: alternate producerでfieldが欠落する、invalid pairがpassになる、required exampleが欠ける
- Declared scope / non-scope: schema、main producer、validator / external runner
- Declared impact: result fixtureとvalidator
- Unresolved decisions: generated producerの有無
- Final decision owner: unresolved

## Requirement traceability

| Source reference | Kind | Requirement / forbidden outcome | Implementation path | Test / evidence | Status |
|---|---|---|---|---|---|
| result schema / paired oracle fields | repository contract | statusとevidence typeを対応付ける | producer → serializer → validator → consumer | E-01〜E-05 | Violated |
| base `AGENTS.md` / behavior-changing rule | repository contract | exampleとpositive／negative／boundary evalを更新する | Skill decision boundary → companion artifacts | E-06〜E-07 | Violated |

## Impact comparison

- Declared impact: main result fixtureとvalidator
- Discovered impact: exact-key allowlistを持つrepository-review producer、consumerのpass decision、Skill example
- Undeclared impact requiring follow-up: generated producerは存在を確認できずUnverified

## Coverage gap audit

- Inspection separation: 初回findingを見ていないindependent read-only reviewerがblind passを行った。
- Initial findings were not used as the completion criterion: 初回13 findingsを固定し、未対応changed conceptから探索した。

### Change-obligation coverage

| Changed concept | Route inspected | Status | Evidence | Linked finding / hypothesis |
|---|---|---|---|---|
| paired oracle fields | schema declaration | Inspected | E-01 | F-001、F-003 |
| paired oracle fields | main fixture producer | Inspected | E-02 | none |
| paired oracle fields | repository-review alternate producerとexact-key allowlist | Inspected | E-03 | F-001 |
| paired oracle fields | serializer、validator、pass consumer | Inspected | E-04〜E-05 | F-001、F-003 |
| paired oracle fields | generated producer | Unverified | generated outputとruntime dispatchを取得できない | H-001 |

### Relational-invariant coverage

| Field / state group | Relationship checked | Status | Evidence |
|---|---|---|---|
| `observed_statuses`、`observed_evidence_types` | paired presence、非空、status exactly one、compatible pair | Inspected | E-01、E-04〜E-05 |
| modeとoracle fields | repository-reviewでは必須、通常reviewでは根拠付き省略可 | Inspected | E-01〜E-05 |
| schema versionと旧fixture | legacy field欠落時の扱い | Unverified | migration contractを取得できない |

### Repository-rule obligations

| Base instruction | Triggering change | Required companion | Status | Evidence |
|---|---|---|---|---|
| behavior-changing ruleはexamplesとeval fixturesを更新 | Skillの判定境界とevalを変更 | supporting example、counterexample、boundary eval | Inspected | E-06〜E-07。evalのみ存在しexample欠落 |
| root catalogとSkill metadataを同期 | display metadataは変更していない | root catalog更新 | Not applicable | diffのmetadataとroot catalogを確認 |

### Blind-spot result

初回findingに現れなかったalternate producer、repository companion、field relationshipからF-001〜F-003を
追加した。generated routeとlegacy compatibilityは確定できないためfindingへ水増しせずH-001とResidual
risksへ分けた。

false-positive controlとして、runtime behavior、decision boundary、metadataを変えない誤字修正では
example／eval companionを `Not applicable` とする。また、versioned contractが特定modeだけを唯一の
producerと定義しdispatcherとconsumerが強制する場合、他modeのproducer欠落をpropagation findingにしない。

## Findings

### F-001: alternate producerがpaired oracle fieldsを破棄する

- Priority: P1
- Adversarial level: A1
- Confidence: Confirmed
- Location: `sample-repo/src/repository_review.py:84`
- Contract / invariant reference: `sample-repo/schema/result.json:31` / repository-review resultはpaired oracle fieldsを持つ
- Actor / trigger: normal callerがrepository-review modeのproposalを生成する
- Precondition: alternate producerがexact-key allowlistを使う
- Code path: repository-review producer → allowlist copy → serializer → downstream validator
- Broken invariant: 全producerがconsumerの必須paired fieldsを生成する
- Impact: caller側で回避できず、正規workflowがvalidation errorで停止する
- Evidence: main producerは両fieldを作るが、alternate allowlistにはどちらもなく、consumerは両方を要求する
- Reproduction or verification: synthetic repository-review fixtureをproducerからvalidatorへ通すとfield欠落を返す
- Fix direction: declarationから全producerとcopy helperへfieldを伝播し、alternate mode testを追加する
- False-positive condition: versioned contractでrepository-review producerが当該consumerを通らないと確認できる場合

### F-002: behavior-changing ruleに必要なexampleがない

- Priority: P2
- Adversarial level: A0
- Confidence: Confirmed
- Location: `sample-repo/SKILL.md:118`
- Contract / invariant reference: base `AGENTS.md` / behavior-changing ruleにはexamplesとeval fixtureを要求
- Actor / trigger: maintainerが変更済みSkillを利用・reviewする
- Precondition: decision boundaryとevalは変更されたがexampleは更新されていない
- Code path: Skill instruction → user-facing behavior → regression assets
- Broken invariant: base repository ruleが要求するcompanion artifactが変更と同時に更新される
- Impact: counterexampleとboundaryで新しい判断を確認できず、変更契約を誤解しやすい
- Evidence: base instruction、Skill diff、eval diff、examples directoryを照合した
- Reproduction or verification: base instructionのtriggerとrequired companionをdiff inventoryへ対応付ける
- Fix direction: supporting、counterexample、boundaryを含むexampleを追加する
- False-positive condition: diffがruntime behaviorもdecision boundaryも変えないdocs-only修正である場合

### F-003: allowed value検証がfield間のinvalid relationshipを許す

- Priority: P2
- Adversarial level: A1
- Confidence: Confirmed
- Location: `sample-repo/src/validate_result.py:52`
- Contract / invariant reference: `sample-repo/schema/result.json:31` / statusとevidence typeのpaired contract
- Actor / trigger: normal callerが片側欠落、空配列、複数status、非互換pairを渡す
- Precondition: validatorが各elementのallowed valueだけを確認する
- Code path: result input → per-field enum validation → pass decision
- Broken invariant: paired presence、non-empty、single status、compatibility、mode条件
- Impact: schema上無効なresultがpassし、後段の判断が曖昧または誤りになる
- Evidence: 各fieldのelement checkはあるがcross-field checkがなく、4つのnegative fixtureがpassする
- Reproduction or verification: empty、片側欠落、multiple statuses、incompatible pairをparameterized testで渡す
- Fix direction: field groupのrelationshipを一つのvalidator contractとして実装する
- False-positive condition: downstreamが到達前に同じrelationshipを必ず強制する証拠がある場合

## Hypotheses

### H-001: generated producerにも伝播漏れがある可能性

generated outputとdynamic dispatchを取得できない。存在や欠落を確定せず、生成物とruntime routeの確認を
follow-upに残す。

## Evidence ledger

| ID | Source | Checked | Result / limitation |
|---|---|---|---|
| E-01 | schema | paired fieldsとmode contract | relationを定義 |
| E-02 | main producer | field生成 | 両fieldを生成 |
| E-03 | alternate producer | exact-key allowlist | 両fieldを破棄 |
| E-04 | validator | enumとrelationship | enumだけを確認 |
| E-05 | consumer | pass decision | paired fieldを要求 |
| E-06 | base instruction | companion rule | exampleとevalを要求 |
| E-07 | diff inventory | Skill、eval、examples | example更新なし |

Historical provenance:

- propagation: `mahcialet/agent-skills#2 @ 8bf6c1ff9749a8736e4e4b6444883324465432c9 / discussion_r3917733760`
- repository companion: `mahcialet/agent-skills#2 @ 8bf6c1ff9749a8736e4e4b6444883324465432c9 / discussion_r3917733769`
- relational invariant: `mahcialet/agent-skills#2 @ 8bf6c1ff9749a8736e4e4b6444883324465432c9 / discussion_r3917733777`

## Test evidence

| Test / check | Provenance | Source / command | Result | Limitation |
|---|---|---|---|---|
| synthetic fixture contract | claimed | `evals/coverage-gap-audit.yaml` | expected: main path succeeds、alternate path fails | static oracle only。実行log／CI resultはない |

## Unexecuted validation

synthetic fixtureのmain／alternate pathは実行しておらず、保存済みlogやCI resultもない。generated
producerとdynamic dispatchはsourceを取得できず未実施。live PRはcanonical fixtureではないため、runtime
dependencyとして取得していない。

## Residual risks

- generated producerの有無とfield伝播は未確認。
- legacy schemaと新consumerのmixed-version behaviorは未確認。
- synthetic fixtureとvalidatorは、modelが実際に同じfindingへ到達することまでは証明しない。
