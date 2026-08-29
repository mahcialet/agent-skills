# Review domains

次の11領域を、変更されたasset、boundary、invariant、actor、code pathへ結び付けて調べる。
全項目に同じ量を費やす必要はないが、該当しない理由を説明できる状態にする。

1. **隣のコードとの一貫性**
   類似・対称実装、create/delete、encode/decode、sync/async、成功/error pathで契約が
   ずれていないか。差が意図的なら根拠があるか。
2. **契約と意図の保存**
   public API、type、schema、migration、CLI、UI、serialization、backward compatibilityが
   保たれるか。要件と実装の条件・例外が一致するか。
3. **値・条件の正しさ**
   単位、境界、nullability、default、rounding、overflow、比較、否定、ordering、timezoneを
   確認する。
4. **失敗の検知可能性**
   errorを握り潰さないか。callerが失敗・partial success・retryable failureを区別できるか。
   log、metric、traceがsecretを漏らさず原因を特定できるか。
5. **利用者・運用者から見た挙動**
   user-visible state、重複操作、キャンセル、進捗、再試行、runbook、alert、recovery手順が
   実際の状態と一致するか。
6. **外部境界**
   authorization context、tenant、webhook、callback、parser、upload、network、third-party API、
   timeout、rate limit、signature、replay protectionを確認する。
7. **データ整合性と障害時状態**
   transaction、unique constraint、idempotency key、atomicity、ordering、outbox、compensation、
   crash後の中間状態、再実行を確認する。
8. **設計と可読性**
   invariantとownershipが表現されているか。複雑さが誤実装や安全な変更を阻害する具体的な
   経路があるか。好みだけをfindingにしない。
9. **速度・資源・コスト**
   algorithm、query fan-out、cache、memory、file descriptor、queue、quota、unbounded input、
   retry storm、cost amplificationを確認する。
10. **変更の波及範囲**
    caller、consumer、job、migration、config、feature flag、lockfile、deployment order、mixed
    version、rollbackへの影響を追う。
11. **検証可能性**
    invariantを観測・再現できるか。testの有無だけでなく、fixtureが意味のあるpathを通るか、
    false positiveを区別できるか、安全に実行できるかを見る。

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

検索結果がないことだけを不在の証明にしない。生成、reflection、dynamic dispatch、設定経由の
到達があり得る場合は、その制約をevidence ledgerへ記録する。
