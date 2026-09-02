"""Schema-backed artifactに共通するversion検証。"""

from __future__ import annotations


def is_schema_version(value: object, expected: int = 1) -> bool:
    """JSON Schemaのinteger versionとしてexpectedと一致する場合だけtrueを返す。"""

    return isinstance(value, int) and not isinstance(value, bool) and value == expected


__all__ = ["is_schema_version"]
