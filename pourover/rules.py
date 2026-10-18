"""Small deterministic helpers shared by the fast path and the offline fallback."""

from __future__ import annotations

import re
from typing import Optional

from .schema import Repeat

URGENT = re.compile(r"!!|\burgent\b|\basap\b|\bimportant\b|don'?t\s+forget|\bzaroor\b", re.I)
BUY = re.compile(r"^(buy|get|order|pick up|grab)\b", re.I)
CHORE = re.compile(r"\b(clean|wash|laundry|litter|dishes|sweep|mop|dust|iron)\b", re.I)

LEADING_FILLER = re.compile(
    r"^(?:(?:pls|plz|please|hey|ok|okay)\s+)*"
    r"(?:remind\s+me\s+(?:to\s+)?|don'?t\s+(?:let\s+me\s+)?forget\s+(?:to\s+)?|i\s+(?:need|have)\s+to\s+|need\s+to\s+|have\s+to\s+|add\s+|todo:?\s+|task:?\s+)?",
    re.I,
)
TRAILING_FILLER = re.compile(r"(?:\s+(?:pls|plz|please|tak|by|on|at))+$", re.I)


def clean_title(text: str) -> str:
    t = text.strip()
    t = LEADING_FILLER.sub("", t)
    t = re.sub(r"[!?.]+$", "", t).strip()
    t = TRAILING_FILLER.sub("", t).strip(" ,;:-")
    words = t.split()
    t = " ".join(words[:12])
    return t[:1].upper() + t[1:] if t else t


def labels_for(title: str, text: str, repeat: Optional[Repeat], known: list[str]) -> list[str]:
    out = {"pourover"}
    if URGENT.search(text):
        out.add("urgent")
    if BUY.search(title):
        out.add("shopping")
    if repeat is not None and CHORE.search(title):
        out.add("chores")
    return sorted(label for label in out if label in known)
