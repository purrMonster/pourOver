"""Find existing tasks from a few words ("done electricity bill")."""

from __future__ import annotations

import re

from .world import TaskRef

STOPWORDS = {"the", "a", "an", "my", "to", "for", "of", "ka", "ki", "ke", "wala", "wali", "task", "pls", "please"}


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in STOPWORDS]


def _close(a: str, b: str) -> bool:
    """Equal, a prefix of the title word, or one typo away (words of 4+ letters)."""
    if a == b or (len(a) >= 3 and b.startswith(a)):
        return True
    if min(len(a), len(b)) < 4 or abs(len(a) - len(b)) > 1:
        return False
    # Levenshtein distance <= 1
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(long_)):
        if long_[:i] + long_[i + 1:] == short:
            return True
    return False


def find_tasks(query: str, tasks: list[TaskRef]) -> list[TaskRef]:
    q = tokens(query)
    if not q:
        return []
    exact = [t for t in tasks if tokens(t.title) == q]
    if exact:
        return exact
    hits = []
    for t in tasks:
        title = tokens(t.title)
        if all(any(_close(w, tw) for tw in title) for w in q):
            hits.append(t)
    return hits
