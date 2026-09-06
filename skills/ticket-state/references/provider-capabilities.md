# Provider capabilities and limitations

確認日: 2026-09-06。公式公開APIの基本契約をfixture/mockで検証し、非公開の閉域テスト環境で
Redmine 2.6.10、3.0.7、3.1.7、3.2.9、3.3.9、3.4.13、4.0.9、4.1.7、4.2.10、
5.0.12、5.1.12、6.0.11、6.1.4、7.0.1をlive検証した。実Backlog API v2も限定的にread/writeを
確認した（サービスversion未取得）。確認した操作と未完了・未実施の範囲は[README](../README.md#実装状態)を
参照する。Redmineの実運用instanceと、providerごとのinstance固有拡張は未検証である。
plugin、version、role、markup設定により結果が異なる場合はunknownとして安全停止する。

## Backlog

- Read: `GET /api/v2/issues/{issueIdOrKey}`、commentsは同issueの `/comments`。
- Combined update: form-encoded `PATCH` にdescriptionとcomment。
- Comment only: form-encoded `POST .../comments` にcontent。
- Auth: `Backlog-API-Key` header。base URL pathは許可しない。
  [公式認証仕様のheader例](https://developer.nulab.com/docs/backlog/auth/#request-example-request-header)
  （2026-09-06確認）に対応方式として明記されている。query方式への変更は不要で、API keyをURLへ載せない。
- Commentsはcount最大100、minId/maxIdを使う。total/cursor/snapshot一貫性は公開契約にない。

## Redmine

- Read: `GET <subpath>/issues/{id}.json?include=journals`。
- Combined/comment update: JSON `PUT` の `issue.description` / `issue.notes`。snapshotは公開コメントとし、
  `private_notes: false` を明示する。
- Update response: 現行系の204に加え、Redmine 2.6.10のlive検証で確認した200を受理する。
  どちらもresponseだけでは `APPLIED` とせず、description/commentを再取得して完全一致を確認する。
- Auth: `X-Redmine-API-Key` header。設定済みsubpathを保持する。
- nested journalsのpagination契約はなく、表示順も設定依存のためID/markerで確認する。
- REST API有効化、role、text formatting、plugin拡張はinstance側設定に依存する。標準API契約と異なる
  private-note拡張を持つinstanceはlive確認まで未検証として扱う。

## 共通の非保証

ETag/If-Match、lock version、idempotency key、server-side CAS、atomicity、exactly-onceは確認できない。
combined requestでdescriptionとcommentを送れても、全副作用が不可分とは主張しない。timeout、切断、
曖昧な5xxはUNKNOWN_REMOTE_RESULTとして再取得し、同じcommentをblind retryしない。

GETの401/403/404、validation error、429、5xxの意味はproxy/pluginを含め一意に決めつけない。
TLS検証を既定で有効にし、3xx redirectは追わない。
