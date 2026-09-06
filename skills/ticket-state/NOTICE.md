# Notice

## License

`ticket-state` のinstructions、runtime、schema、examples、evals、testsは、このリポジトリの
MIT Licenseで提供されます。

## API仕様の参照

実装時に次の公式資料でAPI契約を確認しました。資料本文や第三者コードをこのSkillへ複製せず、
method、path、認証方式、payload、公開された制約を独自に実装・要約しています。

- Backlog API: [Get Issue](https://developer.nulab.com/docs/backlog/api/2/get-issue/)、
  [Get Comment List](https://developer.nulab.com/docs/backlog/api/2/get-comment-list/)、
  [Update Issue](https://developer.nulab.com/docs/backlog/api/2/update-issue/)、
  [Add Comment](https://developer.nulab.com/docs/backlog/api/2/add-comment/)、
  [Authentication](https://developer.nulab.com/docs/backlog/auth/)、
  [Error Response](https://developer.nulab.com/docs/backlog/error-response/)、
  [Rate Limit](https://developer.nulab.com/docs/backlog/rate-limit/)
- Redmine REST API: [Issues](https://www.redmine.org/projects/redmine/wiki/Rest_Issues)、
  [Issue Journals](https://www.redmine.org/projects/redmine/wiki/Rest_IssueJournals)、
  [REST API](https://www.redmine.org/projects/redmine/wiki/Rest_api)、
  [Text Formatting](https://www.redmine.org/projects/redmine/wiki/RedmineTextFormatting)

参照日: 2026-09-06。

## Provenance

初期設計はリポジトリ内の `.codex/CHATGPT_HANDOFF_20.md` を要件として作成しました。この
handoffは配布Skillのruntime依存ではなく、install後のSkillは自身のdirectory内だけで動作します。
