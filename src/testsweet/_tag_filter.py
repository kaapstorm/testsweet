"""Predicate for command-line tag filtering.

A test runs iff:
    (no ``--tag`` was given OR the test has at least one included tag)
    AND (the test has no excluded tag).

Set algebra; flag order is irrelevant. ``--exclude-tag`` is a hard
veto — a test carrying an excluded tag is never run, regardless of
which included tags it also carries.
"""
from typing import Callable


def make_tag_filter(
    include: frozenset[str],
    exclude: frozenset[str],
) -> Callable[[frozenset[str]], bool]:
    """Return a predicate over a test's effective tag set."""
    def keep(tags: frozenset[str]) -> bool:
        if include and tags.isdisjoint(include):
            return False
        return tags.isdisjoint(exclude)

    return keep
