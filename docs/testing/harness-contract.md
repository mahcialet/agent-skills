---
status: active
owner: maintainers
last_verified: 2026-09-11
---

# リポジトリハーネス契約

日本語原本。対応する [English translation](harness-contract.en.md)。EP-HARNESS-001 の M1 で確定した契約であり、検証状態は [active ExecPlan](../exec-plans/active/EP-HARNESS-001.md) を参照する。

## 既存検証の到達範囲（base d423d1f）

| 資産／入力 | 出力・副作用・依存 | discovery／起動経路 | base CI |
|---|---|---|---|
| `scripts/validate_skills.py`、全 `SKILL.md`、catalog | 構造診断。Python/PyYAML。下記 content・Skill tests・catalog を子起動 | root Python validator → Skill ごとの validator と `unittest discover -s skills/<name>/tests` | shell wrapper 経由で実行 |
| `reader-first-editor/scripts/validate_content.py`、Skill 内文書と eval | 内容・fixture・参照整合性の診断。Python/PyYAML。5 つの同梱 tool の `--version` をローカル起動、モデルなし | root validator → content validator。unittest の入れ子実行なし | 実行 |
| `adversarial-pr-review/scripts/validate_content.py`、Skill 文書と eval | 内容・fixture・参照の診断。Python/PyYAML、外部書込みなし | root validator → content validator | 実行 |
| `ticket-state/scripts/validate_content.py`、Skill 文書・schema・eval | 内容・fixture・schema の診断。Python/PyYAML/jsonschema、実 API なし | root validator → content validator | 実行 |
| `skills/reader-first-editor/tests/test_*.py`（9 files） | unittest 結果。一時資産・ローカル tool、Python 開発依存 | root validator の Skill ごとの discovery | 実行 |
| `skills/adversarial-pr-review/tests/test_*.py`（1 file） | unittest 結果。一時資産、Python 開発依存 | 同上 | 実行 |
| `skills/ticket-state/tests/test_*.py`（10 files） | unittest 結果。一時資産・mock transport、実 API 書込みなし | 同上 | 実行 |
| `tests/test_install_local.py`（1 file） | installer 33 tests。一時 Git repo／一時配置先、Python/Git/Bash | shell wrapper → root unittest discovery。Python validator 単独では未到達 | 実行 |
| `scripts/generate-catalog.py --check`、catalog と Skill metadata | README 管理区画の drift 診断。Python/PyYAML。`--check` は書込みなし | root validator → generator | 実行 |
| `scripts/validate-skills.sh` | Python validator と root unittest の結果。Bash | 開発者／CI の互換入口 | 実行 |
| `ruff check .`、全 Python | lint 診断、Ruff 開発依存 | CI 独立 step | 実行 |
| `gh skill validate`、Skill metadata | GitHub CLI が存在・機能利用可能な場合のホスト形式検査 | CI の条件付き step | 任意／条件付き |
| RFE eval 8 files、adversarial eval 6 files、ticket eval 4 files | YAML case の静的検証。動的モデル評価の成功を意味しない | content validators | 静的のみ |
| RFE regression plan／ingest／report | provider-neutral JSON、入力結果の検査と集約。明示出力先への書込み、外部モデルは別実行 | Skill 内 tool の明示起動 | 動的評価は未接続・任意 |
| `scripts/install-local.sh` と `scripts/install_local.py` | Skill 配置、選択した symlink/copy、Git 環境除去と root/HEAD 検査。Python/Git/Bash | 利用者の明示起動、上記 installer tests | 実配置なし、隔離 tests のみ |

`catalog.json` は入力であり生成物ではない。生成物は README の管理区画である。base CI は Ubuntu／Python 3.12。Skill runtime の依存を repository 開発依存と混同しない。

## 正規入口と分離

- `python -m tools.repoctl check`: 静的構造、全 content validator、catalog、文書、Plan、lint。unittest は起動しない。content の決定的な同梱 tool version probe は許容する。
- `python -m tools.repoctl test`: root、各 Skill、repoctl の unittest suite を各 1 回 discovery する。
- `python -m tools.repoctl verify`: 上記 check と test を集約。M6 smoke は今回 `NOT_REQUESTED` とし、未実行を成功に変換しない。
- `python -m tools.repoctl doctor`: Python/Git／開発依存を読み取り確認するだけ。インストール・ログイン・課金・実ホスト起動をしない。
- Python installer を正規入口とし、shell は互換 wrapper とする。既存の root/HEAD 検証、Git 関連環境の除去、target 限定、overwrite 契約を保つ。

最初の native 基準は Python 3.12。CI の Linux/macOS/Windows matrix を設定しても、実行証拠なしに native verified と表記しない。現地 Linux Python 3.13.5 の結果は別に記録する。追加 parser 依存は導入せず、既存 PyYAML を使用する。

## 実行と証拠

Python 子処理は `sys.executable`、その他は検証済み executable と argv 配列を使う。正規経路に shell を挟まない。cwd、許可された環境、timeout、exit code、stdout/stderr、終了待ちと cleanup を明示する。中断要求と終了確認を区別する。

診断には安定した `ASKILLS-*` code、task ID、対象、理由、修復方向を含める。negative fixture は目的の code と stage を検証する。壊した fixture は一時 repo に置き、実 Skill の走査を弱めない。

既定の証拠は console のみ。`--out <new-directory>` の明示時のみ versioned run record を保存する。既存出力を上書きせず、実行対象・結果・cleanup を記録し、秘密を除去する。処理成功と対象の合格は別 field。繰返し成功、因果的 regression、実利用 evidence を区別する。

## 今回の境界

M1〜M4 のみ承認済み。M5 eval adapter、M6 standalone smoke／実ホスト、M7 human-validation、実モデル、実 API 書込み、merge は未着手。Skill の挙動を変更しない。元 Plan の M3 smoke を理由に M6 へ進まず、AC09 の全体完了は pending とする。

installer の既存 transaction は `fcntl`、`dir_fd`、`flock`、`pthread_sigmask` に依存していた。Python 公開入口への移行でこの安全性を弱めず、native Windows の実配置は `ASKILLS-INSTALL-PLATFORM`／exit 3（BLOCKED）とする。これは portable copy-mode の受入成功ではなく、AC05／AC09 の残件である。

文書検査は root／docs／skills の Markdown を対象とし、tests、`.venv`、`.agents`、`.codex`、`.tokensave` を除外する。提供された root intake `execplan_agent_skills_repository_harness.md` は原本保全のため対象外。リンク検査は Markdown inline link と ATX／HTML anchor が対象であり、任意の HTML・動的リンク生成の完全検証ではない。
