# 暫定リリース方針

現在はexperimentalなSkillが一つだけなので、Skill別versionを定義しません。
再現性が必要な場合は、確認済みcommit SHAへpinしてください。pinしない場合、
installerによってrepository releaseまたはdefault branchが解決されます。

二つ目のSkillを追加する前に、repository-wide releaseかSkill接頭辞付きtagかを
決定し、公開前にここへ記録します。portableな `SKILL.md` frontmatterに独自の
version fieldは置きません。
