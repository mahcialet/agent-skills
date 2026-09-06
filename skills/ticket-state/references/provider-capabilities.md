# Provider capabilities and limitations

確認日: 2026-09-06。実装は公式公開APIの基本契約をfixture/mockで検証しており、live instanceでは
未検証である。plugin、version、role、markup設定により結果が異なる場合はunknownとして安全停止する。

## Backlog

- Read: `GET /api/v2/issues/{issueIdOrKey}`、commentsは同issueの `/comments`。
- Combined update: form-encoded `PATCH` にdescriptionとcomment。
- Comment only: form-encoded `POST .../comments` にcontent。
- Auth: `Backlog-API-Key` header。base URL pathは許可しない。
- Commentsはcount最大100、minId/maxIdを使う。total/cursor/snapshot一貫性は公開契約にない。

## Redmine

- Read: `GET <subpath>/issues/{id}.json?include=journals`。
- Combined/comment update: JSON `PUT` の `issue.description` / `issue.notes`。snapshotは公開コメントとし、
  `private_notes: false` を明示する。
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
