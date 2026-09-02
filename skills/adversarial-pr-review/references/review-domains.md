# Review domains

次の11領域を、変更に関係するasset、boundary、invariant、actor、到達可能なcode pathへ
結び付けて調べる。各項目が変更に該当するかは確認する。すべてを同じ深さで
調べる必要はないが、該当しない項目は、その理由を説明できる状態にする。

1. **隣のコードとの一貫性**
   類似・対称実装、create/delete、encode/decode、sync/async、成功/error pathで契約が
   ずれていないか。差が意図的なら根拠があるか。
2. **契約と意図の保存**
   public API、type、schema、migration、CLI、UI、serialization、backward compatibilityが
   保たれるか。要件と実装の条件・例外が一致するか。変更したcontractについて、declarationから
   producer、transform、serialization、validator、consumerまでの伝播を確認する。
3. **値・条件の正しさ**
   単位、境界、nullability、default、rounding、overflow、比較、否定、ordering、timezoneを
   確認する。
4. **失敗の検知可能性**
   errorを握り潰さないか。callerが失敗、部分的な成功（partial success）、再試行できる失敗
   （retryable failure）を区別できるか。
   log、metric、traceがsecretを漏らさず原因を特定できるか。
5. **利用者・運用者から見た挙動**
   利用者に見える状態（user-visible state）、重複操作、キャンセル、進捗、再試行、runbook、
   alert、recovery手順が実際の状態と一致するか。
6. **外部境界**
   authorization context、tenant、webhook、callback、parser、upload、network、third-party API、
   timeout、rate limit、signature、replay protectionを確認する。
7. **データ整合性と障害時状態**
   transaction、unique constraint、idempotency key、atomicity、ordering、outbox、compensation、
   crash後の中間状態、再実行を確認する。
8. **設計と可読性**
   守るべきinvariantと、誰が管理するかを示すownershipが表現されているか。複雑さによって
   誤実装しやすくなる、または安全な変更が難しくなる具体的な経路があるか。好みだけを
   findingにしない。
9. **速度・資源・コスト**
   algorithm、query fan-out、cache、memory、file descriptor、queue、quota、unbounded input、
   retry storm、cost amplificationを確認する。
10. **変更の波及範囲**
    caller、consumer、job、migration、config、feature flag、lockfile、deployment order、mixed
    version、rollbackへの影響を追う。base側instructionから、変更種別が要求するexample、eval、
    catalog、NOTICE、migration documentation等のcompanion artifactも導出する。
11. **検証可能性**
    invariantを観測・再現できるか。testの有無だけでなく、fixtureが意味のあるpathを通るか、
    false positiveを区別できるか、安全に実行できるかを見る。関連field群のpaired presence、
    cardinality、empty／missing、compatibility、mode／version条件をfield単体と分けて確認する。

11領域でprimary explorationを終えた後は、領域を12個へ増やすのではなく、
[coverage-gap audit](coverage-gap-audit.md)で未確認obligationから独立したblind passを行う。

## Evidence routes

探索では少なくとも次のrouteを候補にする。

- changed symbolの定義と全参照
- entry pointからside effectまでのcaller/callee chain
- 類似・対称実装との差分
- tests、fixture、mockとproduction pathの一致
- schema、constraint、migration、seed data
- config、permission、feature flag、workflow、lockfile
- history、blame、過去の修正理由
- versionを特定できる公式な外部contract
- declarationから全producer、transform、serialization、validator、consumerまでのchain
- grouped fieldのpresence、cardinality、empty／missing、compatibility matrix
- base側instructionと、triggering changeから導出したcompanion artifact

検索結果が0件だったという理由だけで、その経路が存在しないと断定しない。生成、reflection、
dynamic dispatch、設定を介して到達する可能性が残る場合は、その制約をevidence ledgerへ記録する。
