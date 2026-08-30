# リリース方針

このモノレポでは、リポジトリ全体に一つのSemVerバージョンを付ける。tag形式は
`vMAJOR.MINOR.PATCH` とし、一つのtag／releaseを、その時点のcatalog全体を固定した
記録（snapshot）として扱う。

Skill個別のバージョンや独自の `version` fieldは、複数ホストで共有する `SKILL.md` の
frontmatterへ置かない。同じ内容を再現する必要がある利用者は、確認済みのリポジトリtag
またはcommit SHAへ固定（pin）する。pinしない場合、インストーラーはリポジトリのrelease
またはdefault branchを解決するため、後日の再インストール結果が変わり得る。

`install-local.sh` がコピー先の説明へ追加する短縮commit ID、commitのtreeとの違い、またはcommit IDを
取得できない理由は、インストール元を見分けるための情報であり、Skill固有のversion fieldや
release pinではない。コピー内容がcommitのtreeと異なる場合はHEADを基点として表示し、コピー内容
そのものを固定した値とはみなさない。

## SemVerの判断

- **MAJOR**: 既存Skillの起動契約（起動方法・条件）、既定動作、出力契約（形式・必須項目・意味）、
  安全境界（実行しない操作など）、対応host、installation layoutなどに互換性のない変更がある。
- **MINOR**: 後方互換なSkill追加、mode・reference・evalの追加、対応範囲の拡張がある。
- **PATCH**: 挙動契約を壊さない文章修正、validator修正、互換な安全性・明確性改善を行う。

一つのSkillだけに互換性のない変更（breaking change）がある場合も、リポジトリ全体のreleaseを
MAJORとして扱う。各Skillの変更点はリリースノートで明示し、利用者が影響を受けるSkillを
判別できるようにする。

<a id="release前の確認"></a>

## リリース前の確認

tag対象のcommitでルートvalidator、catalog check、各Skillのcontent validatorを実行する。
ホスト上の動作確認結果には、実際に確認したversionとscopeだけを記録する。tagによって
既存releaseの意味を書き換えず、force updateしない。

本方針の採用はreleaseの作成を意味しない。release／tagの作成は、別途明示された作業として行う。
