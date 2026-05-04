"""Expand discovered units into per-test callables.

Functions yield (name, callable) directly. Classes are entered as
context managers (their ``__enter__/__exit__`` brackets the iteration
of their methods); each public method is yielded as its own unit, and
``__test_context__`` — if defined — wraps every method call.
"""
import functools
import itertools
from contextlib import nullcontext
from types import ModuleType
from typing import Any, Callable, Iterator

from testsweet._class_helpers import _public_methods
from testsweet._discover import discover
from testsweet._markers import TAGS_MARKER
from testsweet._params import PARAMS_MARKER


TagFilter = Callable[[frozenset[str]], bool]


def resolve_units(
    module: ModuleType,
    names: list[str] | None = None,
    keep: TagFilter | None = None,
) -> Iterator[tuple[str, Callable[[], Any]]]:
    # `_build_plan` runs synchronously here (above
    # `chain.from_iterable`), so `LookupError` for unmatched names
    # fires at call time, before any iteration. The returned chain
    # advances units sequentially: each `_expand_unit` generator is
    # exhausted (running its `with cm:` `__exit__`) before the next
    # one's `__enter__` runs. Per-class fixture lifecycles are
    # therefore non-overlapping, even though the chain looks flat.
    units = discover(module)
    if names is None:
        return itertools.chain.from_iterable(
            _expand_unit(unit, None, keep) for unit in units
        )
    plan = _build_plan(units, names)
    return itertools.chain.from_iterable(
        _expand_unit(unit, plan[unit.__qualname__], keep)
        for unit in units
        if unit.__qualname__ in plan
    )


def _expand_unit(
    unit: Any,
    method_filter: set[str] | None,
    keep: TagFilter | None,
) -> Iterator[tuple[str, Callable[[], Any]]]:
    if isinstance(unit, type):
        class_tags: frozenset[str] = getattr(
            unit, TAGS_MARKER, frozenset(),
        )
        eligible = [
            method_name
            for method_name in _public_methods(unit)
            if (
                method_filter is None
                or method_name in method_filter
            )
            and (
                keep is None
                or keep(class_tags | _method_tags(unit, method_name))
            )
        ]
        if not eligible:
            return
        instance = unit()
        cm = (
            instance
            if hasattr(instance, '__enter__')
            else nullcontext(instance)
        )
        with cm:
            test_context = getattr(instance, '__test_context__', None)
            for method_name in eligible:
                bound = getattr(instance, method_name)
                if test_context is not None:
                    bound = _wrap_in_cm(bound, test_context)
                yield from _expand_callable(bound, bound.__qualname__)
    else:
        if keep is not None:
            tags: frozenset[str] = getattr(
                unit, TAGS_MARKER, frozenset(),
            )
            if not keep(tags):
                return
        yield from _expand_callable(unit, unit.__qualname__)


def _method_tags(cls: type, method_name: str) -> frozenset[str]:
    method = getattr(cls, method_name)
    return getattr(method, TAGS_MARKER, frozenset())


def _wrap_in_cm(
    call: Callable[..., Any],
    cm_factory: Callable[[], Any],
) -> Callable[..., Any]:
    @functools.wraps(call)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        with cm_factory():
            return call(*args, **kwargs)
    return wrapped


def _expand_callable(
    func: Callable[..., Any],
    qualname: str,
) -> Iterator[tuple[str, Callable[[], Any]]]:
    params = getattr(func, PARAMS_MARKER, None)
    if params is None:
        yield qualname, func
        return
    for i, args in enumerate(params):
        partial = functools.partial(func, *args)
        # `functools.partial` does not inherit attributes from its
        # underlying function, so markers like ``__testsweet_skip__``
        # would be invisible to the runner. Copy ``__dict__`` (where
        # markers live) onto the partial via ``update_wrapper``.
        functools.update_wrapper(partial, func)
        yield f'{qualname}[{i}]', partial


def _build_plan(
    units: list[Any],
    names: list[str],
) -> dict[str, set[str] | None]:
    """Map unit qualnames to method-name filters.

    The value is ``None`` when the user asked to run the whole unit,
    or a ``set`` of method names when only specific methods were
    selected. Class-form selectors (``Foo``) win over method-form
    selectors (``Foo.bar``) for the same class.
    """
    plan: dict[str, set[str] | None] = {}
    discovered_unit_names = {u.__qualname__: u for u in units}
    unmatched: list[str] = []
    for name in names:
        if '.' in name:
            head, _, method = name.partition('.')
            unit = discovered_unit_names.get(head)
            if (
                unit is None
                or not isinstance(unit, type)
                or method not in _public_methods(unit)
            ):
                unmatched.append(name)
                continue
            existing = plan.get(head, set())
            if existing is None:
                # already a whole-unit selector for this class — wins.
                continue
            existing.add(method)
            plan[head] = existing
        else:
            if name not in discovered_unit_names:
                unmatched.append(name)
                continue
            plan[name] = None  # whole unit; class form wins
    if unmatched:
        raise LookupError(f'no test units matched: {sorted(unmatched)}')
    return plan
