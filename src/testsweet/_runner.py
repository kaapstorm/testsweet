from types import ModuleType

from testsweet._plugins import unit as plugin_unit
from testsweet._resolve import resolve_units


def run(
    module: ModuleType,
    names: list[str] | None = None,
    plugins: list[object] | None = None,
) -> list[tuple[str, Exception | None]]:
    plugins = plugins or []
    results: list[tuple[str, Exception | None]] = []
    for name, call in resolve_units(module, names):
        try:
            with plugin_unit(plugins, name):
                call()
        except Exception as exc:
            results.append((name, exc))
        else:
            results.append((name, None))
    return results
