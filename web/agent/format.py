"""Make a model reply readable in a small chat box."""

from __future__ import annotations

import re

_LATEX_DOLLAR_BLOCK = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_LATEX_BRACKETS = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_LATEX_PARENS = re.compile(r"\\\((.+?)\\\)", re.DOTALL)
_LATEX_DOLLAR = re.compile(r"\$(.+?)\$", re.DOTALL)
_FRAC = re.compile(r"\\frac\{([^{}]+)\}\{([^{}]+)\}")
_TEXT = re.compile(r"\\(?:text|mathrm|operatorname|textit|textbf)\{([^{}]*)\}")
_SPACING = re.compile(r"\\[,;! ]")
_MACRO = re.compile(r"\\(cos|sin|tan|log|ln|cdot|times|left|right)\b")

_MACRO_PLAIN = {
    "cdot": "*",
    "times": "*",
    "left": "",
    "right": "",
}


def _latex_to_plain(inner: str) -> str:
    out = _FRAC.sub(r"\1 / \2", inner)
    out = _TEXT.sub(r"\1", out)
    out = _SPACING.sub(" ", out)
    out = _MACRO.sub(lambda m: _MACRO_PLAIN.get(m.group(1), m.group(1)), out)
    out = out.replace("{", "").replace("}", "").replace("\\", "")
    return re.sub(r"\s+", " ", out).strip()


def plain_reply(text: str) -> str:
    """Unwrap LaTeX math. Markdown emphasis is left for the chat renderer."""
    out = text
    for pattern in (
        _LATEX_DOLLAR_BLOCK,
        _LATEX_BRACKETS,
        _LATEX_PARENS,
        _LATEX_DOLLAR,
    ):
        out = pattern.sub(lambda match: _latex_to_plain(match.group(1)), out)
    return out.strip()
