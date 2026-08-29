# リリース方針

このモノレポはrepository-wide SemVerを使う。tag形式は `vMAJOR.MINOR.PATCH` とし、
一つのtag／releaseを、その時点のcatalog全体のsnapshotとして扱う。

Skill個別versionや独自の `version` fieldはportableな `SKILL.md` frontmatterへ置かない。
再現性が必要な利用者は、確認済みのrepository tagまたはcommit SHAへpinする。pinしない
場合、installerはrepository releaseまたはdefault branchを解決するため、後日の
再インストール結果が変わり得る。

## SemVerの判断

- **MAJOR**: 既存Skillの起動契約、既定動作、出力契約、安全境界、対応host、installation
  layoutなどに互換性のない変更がある。
- **MINOR**: 後方互換なSkill追加、mode・reference・evalの追加、対応範囲の拡張がある。
- **PATCH**: 挙動契約を壊さない文章修正、validator修正、互換な安全性・明確性改善を行う。

一つのSkillのbreaking changeもrepository release全体のMAJORとして扱う。各Skillの変更点は
release notesで明示し、利用者が影響するSkillだけを判別できるようにする。

## Release前の確認

tag対象のcommitでroot validator、catalog check、各Skillのcontent validatorを実行し、
host runtime結果は実施したversionとscopeだけを記録する。tagは既存releaseの意味を
書き換えず、force updateしない。

本方針の採用はrelease作成を意味しない。release／tagの作成は別途明示された作業として行う。
