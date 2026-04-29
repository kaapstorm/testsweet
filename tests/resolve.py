import functools
import importlib

from testsweet import catch_exceptions, test
from testsweet._resolve import resolve_units


@test
class ResolveUnits:
    def plain_function_yields_one_pair(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        pairs = list(resolve_units(mod))
        names = [name for name, _ in pairs]
        assert names == ['passes_one', 'passes_two']
        # The first pair's callable is the function itself.
        assert pairs[0][1] is getattr(mod, 'passes_one')

    def parameterized_function_yields_indexed_partials(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_simple',
        )
        pairs = list(resolve_units(mod))
        names = [name for name, _ in pairs]
        assert names == ['adds[0]', 'adds[1]']
        for _, call in pairs:
            assert isinstance(call, functools.partial)

    def class_with_context_manager_brackets_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_calls_recorded',
        )
        mod.CALLS.clear()
        # Iterating the flat iterator runs __enter__ once before any
        # method call and __exit__ once after the last method.
        for _name, call in resolve_units(mod):
            call()
        assert mod.CALLS == ['enter', 'first', 'second', 'exit']

    def class_without_context_manager_runs_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        names = [name for name, _ in resolve_units(mod)]
        assert names == ['Simple.first', 'Simple.second']

    def class_method_selector_filters(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        names = [
            name
            for name, _ in resolve_units(mod, names=['Simple.first'])
        ]
        assert names == ['Simple.first']

    def unmatched_name_raises_lookup_error(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        with catch_exceptions() as excs:
            resolve_units(mod, names=['nonexistent'])
        assert len(excs) == 1
        assert isinstance(excs[0], LookupError)
        assert 'nonexistent' in str(excs[0])

    def validation_runs_before_any_iteration(self):
        # If any name is unmatched, the iterator is never advanced
        # because LookupError is raised at resolve_units(...) call
        # time, before chain.from_iterable is constructed.
        mod = importlib.import_module(
            'tests.fixtures.runner.class_calls_recorded',
        )
        mod.CALLS.clear()
        with catch_exceptions() as excs:
            resolve_units(
                mod,
                names=['Recorded.first', 'Recorded.nonexistent'],
            )
        assert len(excs) == 1
        assert isinstance(excs[0], LookupError)
        assert mod.CALLS == []

    def class_form_wins_over_method_selector(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        names = [
            name
            for name, _ in resolve_units(
                mod,
                names=['Simple', 'Simple.first'],
            )
        ]
        # Both methods run, not just the one named in the selector.
        assert names == ['Simple.first', 'Simple.second']

    def mixed_module_yields_pairs_in_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_mixed_with_function',
        )
        names = [name for name, _ in resolve_units(mod)]
        assert names == ['free_function', 'ClassUnit.method']

    def empty_module_returns_empty_iterator(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.empty',
        )
        assert list(resolve_units(mod)) == []

    def no_names_means_no_filtering(self):
        # When names is None, every discovered unit appears.
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        names = [name for name, _ in resolve_units(mod)]
        assert names == ['passes', 'fails']
