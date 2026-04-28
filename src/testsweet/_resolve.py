import functools
import itertools
from contextlib import nullcontext
from types import ModuleType
from typing import Any, Callable, Iterator

from testsweet._class_helpers import _public_methods
from testsweet._discover import discover
from testsweet._params import PARAMS_MARKER


def resolve_units(
    module: ModuleType,
    names: list[str] | None = None,
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
            _expand_unit(unit, None) for unit in units
        )
    plan = _build_plan(units, names)
    return itertools.chain.from_iterable(
        _expand_unit(unit, plan[unit.__qualname__])
        for unit in units
        if unit.__qualname__ in plan
    )


def _expand_unit(
    unit: Any,
    method_filter: set[str] | None,
) -> Iterator[tuple[str, Callable[[], Any]]]:
    if isinstance(unit, type):
        instance = unit()
        cm = (
            instance
            if hasattr(instance, '__enter__')
            else nullcontext(instance)
        )
        with cm:
            for method_name in _public_methods(unit):
                if (
                    method_filter is not None
                    and method_name not in method_filter
                ):
                    continue
                bound = getattr(instance, method_name)
                yield from _expand_callable(bound, bound.__qualname__)
    else:
        yield from _expand_callable(unit, unit.__qualname__)


def _expand_callable(
    func: Callable[..., Any],
    qualname: str,
) -> Iterator[tuple[str, Callable[[], Any]]]:
    params = getattr(func, PARAMS_MARKER, None)
    if params is None:
        yield qualname, func
        return
    for i, args in enumerate(params):
        yield f'{qualname}[{i}]', functools.partial(func, *args)


def _build_plan(
    units: list[Any],
    names: list[str],
) -> dict[str, set[str] | None]:
    # plan[unit_qualname] = None  -> run as today (whole unit)
    #                    = set    -> run only these method names
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
