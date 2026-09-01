"""
Minimal C# syntax highlighter for infographic code panels.

Escapes HTML first, then wraps tokens in spans. No external deps — safe for
Playwright inline HTML renders.
"""
from __future__ import annotations

import html
import re

_KEYWORDS = frozenset({
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char",
    "class", "const", "continue", "decimal", "default", "delegate", "do",
    "double", "else", "enum", "event", "explicit", "extern", "false", "finally",
    "fixed", "float", "for", "foreach", "goto", "if", "implicit", "in",
    "int", "interface", "internal", "is", "lock", "long", "namespace", "new",
    "null", "object", "operator", "out", "override", "params", "private",
    "protected", "public", "readonly", "record", "ref", "return", "sealed",
    "short", "sizeof", "stackalloc", "static", "string", "struct", "switch",
    "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked",
    "unsafe", "using", "var", "virtual", "void", "volatile", "while", "yield",
    "async", "await", "init", "required", "file", "when", "where",
})

_STRING_RE = re.compile(r'(@?"(?:\\.|[^"\\])*")')
_COMMENT_RE = re.compile(r"(//[^\n]*|/\*.*?\*/)", re.DOTALL)
_WORD_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def highlight_csharp(code: str) -> str:
    """Return HTML with syntax-colored spans for a C# code block."""
    if not code:
        return ""
    escaped = html.escape(code.strip())
    placeholders: dict[str, str] = {}
    counter = 0

    def _stash(match: re.Match[str], css_class: str) -> str:
        nonlocal counter
        key = f"@@HL{counter}@@"
        counter += 1
        placeholders[key] = f'<span class="{css_class}">{match.group(0)}</span>'
        return key

    text = _COMMENT_RE.sub(lambda m: _stash(m, "hl-comment"), escaped)
    text = _STRING_RE.sub(lambda m: _stash(m, "hl-string"), text)

    def _color_word(match: re.Match[str]) -> str:
        word = match.group(0)
        if word in _KEYWORDS:
            return f'<span class="hl-keyword">{word}</span>'
        if word[0].isupper():
            return f'<span class="hl-type">{word}</span>'
        return word

    text = _WORD_RE.sub(_color_word, text)
    for key, value in placeholders.items():
        text = text.replace(key, value)
    return text
