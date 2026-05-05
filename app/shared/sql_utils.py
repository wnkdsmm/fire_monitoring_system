from __future__ import annotations


def quote_identifier(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


__all__ = ["quote_identifier"]
