from types import ModuleType

from testsweet._resolve import resolve_units


def run(
    module: ModuleType,
    names: list[str] | None = None,
) -> list[tuple[str, Exception | None]]:
    results: list[tuple[str, Exception | None]] = []
    for name, call in resolve_units(module, names):
        try:
            call()
        except Exception as exc:
            results.append((name, exc))
        else:
            results.append((name, None))
    return results
