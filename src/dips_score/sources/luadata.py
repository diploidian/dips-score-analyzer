"""Reads a WoW SavedVariables file as data.

The file is Lua, but only the small subset the game writes: `name = value` statements where a
value is a table, string, number, boolean or nil. This parses that subset; nothing in the file
is ever run as code.

Tables become dicts; a table with only the keys 1..n becomes a list.
"""
from __future__ import annotations

import re

_TOKEN = re.compile(
    r"""
    (?P<ws>\s+|--[^\n]*)                       # whitespace, comments (the game writes "-- [1]")
  | (?P<str>"(?:[^"\\]|\\.|\\\n)*")            # "text"
  | (?P<num>-?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?))
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>[{}\[\]=,;])
    """,
    re.VERBOSE | re.DOTALL,
)

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
            "\\": "\\", '"': '"', "'": "'", "\n": "\n"}


class LuaDataError(ValueError):
    pass


def _unquote(s: str) -> str:
    body = s[1:-1]
    if "\\" not in body:
        return body
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        nxt = body[i + 1]
        if nxt.isdigit():  # \ddd, a byte
            m = re.match(r"\d{1,3}", body[i + 1:])
            out.append(chr(int(m.group())))
            i += 1 + len(m.group())
        else:
            out.append(_ESCAPES.get(nxt, nxt))
            i += 2
    return "".join(out)


def _tokens(text: str):
    pos, n = 0, len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            raise LuaDataError(f"unexpected text at {pos}: {text[pos:pos + 30]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        yield kind, m.group()


class _Parser:
    def __init__(self, text: str):
        self.toks = list(_tokens(text))
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self, value=None):
        tok = self.peek()
        if tok[0] is None:
            raise LuaDataError("file ends too early")
        if value is not None and tok[1] != value:
            raise LuaDataError(f"expected {value!r}, got {tok[1]!r}")
        self.i += 1
        return tok

    def value(self):
        kind, v = self.take()
        if kind == "str":
            return _unquote(v)
        if kind == "num":
            if v.lower().lstrip("-").startswith("0x"):
                return int(v, 16)
            f = float(v)
            return int(f) if re.fullmatch(r"-?\d+", v) else f
        if kind == "name":
            if v in ("true", "false"):
                return v == "true"
            if v == "nil":
                return None
            raise LuaDataError(f"unexpected name {v!r}")
        if v == "{":
            return self.table()
        raise LuaDataError(f"unexpected {v!r}")

    def table(self):
        out: dict = {}
        n = 0
        while True:
            kind, v = self.peek()
            if v == "}":
                self.take()
                break
            if v == "[":
                self.take()
                key = self.value()
                self.take("]")
                self.take("=")
                out[key] = self.value()
            elif kind == "name" and self.toks[self.i + 1][1] == "=":
                self.take()
                self.take("=")
                out[v] = self.value()
            else:
                n += 1
                out[n] = self.value()
            if self.peek()[1] in (",", ";"):
                self.take()
        if out and all(isinstance(k, int) for k in out) and sorted(out) == list(range(1, len(out) + 1)):
            return [out[k] for k in range(1, len(out) + 1)]
        return out

    def statements(self) -> dict:
        out = {}
        while self.peek()[0] is not None:
            _, name = self.take()
            self.take("=")
            out[name] = self.value()
        return out


def loads(text: str) -> dict:
    """{variable name: value} for every saved variable in the file's text."""
    return _Parser(text).statements()


def load(path) -> dict:
    with open(path, encoding="utf-8", errors="replace") as f:
        return loads(f.read())
