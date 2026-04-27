from types import ModuleType
from typing import Callable

from assertions._discover import discover
from assertions._params import PARAMS_MARKER
from contextlib import nullcontext

from assertions._test_class import _public_methods


def run(
    module: ModuleType,
    names: list[str] | None = None,
) -> list[tuple[str, Exception | None]]:
    units = discover(module)
    results: list[tuple[str, Exception | None]] = []
    if names is None:
        for unit in units:
            _run_unit(unit, None, results)
        return results
    plan = _build_plan(units, names)
    for unit in units:
        unit_name = unit.__qualname__
        if unit_name not in plan:
            continue
        method_filter = plan[unit_name]
        _run_unit(unit, method_filter, results)
    return results


def _build_plan(units, names: list[str]) -> dict[str, set[str] | None]:
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


def _run_unit(
    unit,
    method_filter: set[str] | None,
    results: list[tuple[str, Exception | None]],
) -> None:
    if isinstance(unit, type):
        instance = unit()
        cm = (
            instance
            if hasattr(instance, '__enter__')
            else nullcontext(instance)
        )
        with cm:
            for name in _public_methods(unit):
                if method_filter is not None and name not in method_filter:
                    continue
                bound = getattr(instance, name)
                _invoke(bound, bound.__qualname__, results)
    else:
        _invoke(unit, unit.__qualname__, results)


def _invoke(
    func: Callable,
    qualname: str,
    results: list[tuple[str, Exception | None]],
) -> None:
    params = getattr(func, PARAMS_MARKER, None)
    if params is None:
        try:
            func()
        except Exception as exc:
            results.append((qualname, exc))
        else:
            results.append((qualname, None))
        return
    for i, args in enumerate(params):
        name = f'{qualname}[{i}]'
        try:
            func(*args)
        except Exception as exc:
            results.append((name, exc))
        else:
            results.append((name, None))
