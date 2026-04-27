from types import ModuleType

from assertions._resolve import resolve_units


def run(
    module: ModuleType,
    names: list[str] | None = None,
) -> list[tuple[str, Exception | None]]:
    results: list[tuple[str, Exception | None]] = []
    for unit_iter in resolve_units(module, names):
        for name, call in unit_iter:
            try:
                call()
            except Exception as exc:
                results.append((name, exc))
            else:
                results.append((name, None))
    return results
