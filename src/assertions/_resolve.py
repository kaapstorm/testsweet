import functools
from contextlib import nullcontext
from types import ModuleType
from typing import Any, Callable, Iterator

from assertions._class_helpers import _public_methods
from assertions._discover import discover
from assertions._params import PARAMS_MARKER


def resolve_units(
    module: ModuleType,
    names: list[str] | None = None,
) -> list[Iterator[tuple[str, Callable[[], Any]]]]:
    units = discover(module)
    plan = _build_plan(units, names)
    out: list[Iterator[tuple[str, Callable[[], Any]]]] = []
    for unit in units:
        if names is not None and unit.__qualname__ not in plan:
            continue
        method_filter = (
            plan.get(unit.__qualname__) if names is not None else None
        )
        out.append(_expand_unit(unit, method_filter))
    return out


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
    names: list[str] | None,
) -> dict[str, set[str] | None]:
    # plan[unit_qualname] = None  -> run as today (whole unit)
    #                    = set    -> run only these method names
    if names is None:
        return {}
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
