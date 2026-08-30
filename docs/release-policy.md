# リリース方針

このモノレポでは、リポジトリ全体に一つのSemVer versionを付ける。tag形式は
`vMAJOR.MINOR.PATCH` とし、一つのtag／releaseを、その時点のcatalog全体を固定した
記録（snapshot）として扱う。

Skill個別versionや独自の `version` fieldは、複数ホストで共有する `SKILL.md` の
frontmatterへ置かない。同じ内容を再現する必要がある利用者は、確認済みのrepository tag
またはcommit SHAへ固定（pin）する。pinしない場合、installerはrepository releaseまたは
default branchを解決するため、後日の再インストール結果が変わり得る。

## SemVerの判断

- **MAJOR**: 既存Skillの起動契約（起動方法・条件）、既定動作、出力契約（形式・必須項目・意味）、
  安全境界（実行しない操作など）、対応host、installation layoutなどに互換性のない変更がある。
- **MINOR**: 後方互換なSkill追加、mode・reference・evalの追加、対応範囲の拡張がある。
- **PATCH**: 挙動契約を壊さない文章修正、validator修正、互換な安全性・明確性改善を行う。

一つのSkillだけに互換性のない変更（breaking change）がある場合も、repository release全体の
MAJORとして扱う。各Skillの変更点はrelease notesで明示し、利用者が影響を受けるSkillを
判別できるようにする。

## Release前の確認

tag対象のcommitでroot validator、catalog check、各Skillのcontent validatorを実行する。
ホスト上の動作確認結果には、実際に確認したversionとscopeだけを記録する。tagによって
既存releaseの意味を書き換えず、force updateしない。

本方針の採用はrelease作成を意味しない。release／tagの作成は別途明示された作業として行う。
