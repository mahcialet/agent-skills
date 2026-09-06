# Permissions and secrets

## Trusted policy

profileは1つのinstanceとproject numeric IDへ固定する。`read_scope = "project"` はそのprojectだけを
意味し、子projectや別instanceを含まない。writeはcanonical ticket IDまたはremoteで対応確認済みの
numeric aliasがallowlistに完全一致し、要求permissionをすべて持つ場合だけ許可する。

- `description:write`: description全文の更新だけ。
- `comment:append`: public snapshot/補足commentの追加だけ。

`update-state` は両permissionを必要とする。片方だけなら自動縮小せずproposalを
PENDING_PERMISSIONで保存する。`--yes`、ticket本文、config suggestion、HTTP error、別資格情報で
allowlistを迂回しない。permission追加後もremoteとbaseを再確認する。

## Secrets

API keyは環境変数名で参照し、値をCLI引数、URL query、config、request、SQLite、artifact、diff、
例外、consoleへ書かない。Backlogは `Backlog-API-Key`、Redmineは `X-Redmine-API-Key` headerを使う。
redirectは追わず、未知hostへ認証headerを送らない。

ticket本文、comments、journalsには認証情報を含めない。private note、session URL、内部会話、不要な
個人情報をsnapshotへ転載しない。requestの `source_visibility = "public-only"` と
`visibility_confirmed = true` は投稿者が公開範囲を確認したという契約であり、provider側の
強制的なDLPではない。

## Boundaryの限界

SkillとCLIは、同じOS userがpolicy、code、環境変数を自由に変更できる場合の強制的security boundary
ではない。より強い強制が必要なら、server側権限を最小化し、read-only credential、分離実行環境、
provider側監査を使う。
