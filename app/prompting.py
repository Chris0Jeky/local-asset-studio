"""Prompt wildcards.  Pure module: no server import, no network, no writes.

`{a|b|c}` picks one alternative; `__name__` picks a line from
`presets/wildcards/<name>.txt`.  Both nest, and an unknown wildcard name is left
literal so a typo never silently empties a prompt.
"""
from __future__ import annotations

import re
from pathlib import Path

NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")
WILDCARD = re.compile(r"__([A-Za-z0-9_-]{1,64})__")
CHOICE = re.compile(r"\{([^{}]*)\}")
DEPTH = 4
LIMIT = 16000

def options(root, name):
    """Lines of presets/wildcards/<name>.txt; '#' comments and blanks dropped."""
    if root is None or not isinstance(name, str) or not NAME.fullmatch(name): return []
    path = Path(root) / "presets/wildcards" / (name + ".txt")
    try: raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError): return []
    return [line.strip() for line in raw.splitlines() if line.strip() and not line.lstrip().startswith("#")]

def _pick(root, name, rng, literal):
    choices = options(root, name)
    return rng.choice(choices) if choices else literal

def _once(text, rng, root):
    # Wildcards first, then the innermost {a|b}: one nesting level per pass.
    text = WILDCARD.sub(lambda m: _pick(root, m.group(1), rng, m.group(0)), text)
    return CHOICE.sub(lambda m: rng.choice([part.strip() for part in m.group(1).split("|")]), text)

def expand(text, rng, root=None, depth=DEPTH):
    """Resolve alternatives and wildcards deterministically from `rng`."""
    if not isinstance(text, str): return text
    for _ in range(max(1, int(depth))):
        grown = _once(text, rng, root)
        if len(grown) > LIMIT: raise ValueError(f"Prompt wildcards expand past {LIMIT} characters")
        if grown == text: return text
        text = grown
    return text

def has_wildcards(text):
    return isinstance(text, str) and ("{" in text or "__" in text)
