# GitHub collectorのrecorded fixture

このdirectoryのJSONは、GitHub REST APIで確認した次のPRについて、collectorが使用する
事実metadataだけを正規化したtest fixtureである。

- <https://github.com/digital-go-jp/design-tokens/pull/138>
- <https://github.com/digital-go-jp/design-tokens/pull/187>

確認日は2026-08-30である。保存している情報には、repository・PR番号、file path、commit／blob SHA、
review state、inline threadの位置と件数が含まれる。PR本文、file content、patch、review body、
comment body、account名は保存していない。`body_present` は本文の存在だけを表すboolean metadataで
あり、本文そのものを復元できる情報ではない。

fixture内のrepository licenseはGitHub APIが返した観測値である。PRやreview commentの
再配布権限を確認済みとする根拠には使用しない。
