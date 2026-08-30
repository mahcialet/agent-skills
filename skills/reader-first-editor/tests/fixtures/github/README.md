# GitHub collectorのrecorded fixture

このdirectoryのJSONは、GitHub REST APIで確認した次のPRについて、collectorが使用する
事実metadataだけを正規化したtest fixtureである。

- <https://github.com/digital-go-jp/design-tokens/pull/138>
- <https://github.com/digital-go-jp/design-tokens/pull/187>

確認日は2026-08-30。repository・PR番号、file path、commit／blob SHA、review state、inline
threadの位置と件数を保存している。PR本文、file content、patch、review body、comment body、
account名は保存していない。`body_present` は本文が存在したというboolean metadataであり、
本文そのものではない。

fixture内のrepository licenseはGitHub APIが返した観測値である。PRやreview commentの
再配布権限を確認済みとする根拠には使用しない。
