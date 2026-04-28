import importlib

from testsweet import catch_exceptions, discover, run, test
from testsweet._class_helpers import _public_methods
from testsweet._markers import TEST_MARKER


@test
class Run:
    def single_passing_test(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        results = run(mod)
        assert len(results) == 2
        for _, exc in results:
            assert exc is None

    def single_failing_assert(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        results = run(mod)
        assert results[0][0] == 'passes'
        assert results[0][1] is None
        assert results[1][0] == 'fails'
        assert isinstance(results[1][1], AssertionError)

    def results_in_discover_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        results = run(mod)
        assert [name for name, _ in results] == ['passes', 'fails']

    def empty_module_returns_empty_list(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.empty',
        )
        results = run(mod)
        assert results == []

    def non_assertion_exception_is_caught(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.non_assertion_error',
        )
        results = run(mod)
        assert len(results) == 1
        name, exc = results[0]
        assert name == 'raises_value_error'
        assert isinstance(exc, ValueError)

    def keyboard_interrupt_propagates(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.keyboard_interrupt',
        )
        outer: list[BaseException] = []
        try:
            run(mod)
        except KeyboardInterrupt as exc:
            outer.append(exc)
        assert len(outer) == 1


@test
class RunClass:
    def class_with_passing_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        results = run(mod)
        assert len(results) == 2
        names = [name for name, _ in results]
        assert names == ['Simple.first', 'Simple.second']
        for _, exc in results:
            assert exc is None

    def underscore_methods_are_skipped(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_with_underscore_methods',
        )
        results = run(mod)
        names = [name for name, _ in results]
        assert names == ['WithUnderscores.public']

    def enter_and_exit_run_around_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_calls_recorded',
        )
        mod.CALLS.clear()
        run(mod)
        assert mod.CALLS == ['enter', 'first', 'second', 'exit']

    def failing_method_does_not_abort_class(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_method_fails',
        )
        results = run(mod)
        assert len(results) == 2
        names = [name for name, _ in results]
        assert names == ['HasFailure.passes', 'HasFailure.fails']
        assert results[0][1] is None
        assert isinstance(results[1][1], AssertionError)

    def enter_exception_propagates(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_enter_raises',
        )
        with catch_exceptions() as excs:
            run(mod)
        assert len(excs) == 1
        assert isinstance(excs[0], RuntimeError)

    def exit_exception_propagates(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_exit_raises',
        )
        with catch_exceptions() as excs:
            run(mod)
        assert len(excs) == 1
        assert isinstance(excs[0], RuntimeError)

    def mixed_function_and_class_in_vars_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_mixed_with_function',
        )
        results = run(mod)
        names = [name for name, _ in results]
        assert names == ['free_function', 'ClassUnit.method']


@test
class RunParamsEager:
    def runs_each_tuple_in_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_simple',
        )
        results = run(mod)
        names = [name for name, _ in results]
        assert names == ['adds[0]', 'adds[1]']
        for _, exc in results:
            assert exc is None

    def failure_recorded_at_correct_index(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_with_failure',
        )
        results = run(mod)
        names = [name for name, _ in results]
        assert names == ['adds[0]', 'adds[1]', 'adds[2]']
        assert results[0][1] is None
        assert isinstance(results[1][1], AssertionError)
        assert results[2][1] is None

    def empty_param_list_produces_no_results(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_empty',
        )
        assert run(mod) == []

    def function_without_params_unchanged(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_no_decoration',
        )
        results = run(mod)
        names = [name for name, _ in results]
        assert names == ['plain', 'parameterized[0]']
        for _, exc in results:
            assert exc is None

    def accepts_generator(self):
        # The generator was consumed at decoration time, so the second
        # run() call sees the same materialized tuple.
        mod = importlib.import_module(
            'tests.fixtures.runner.params_generator',
        )
        first = run(mod)
        second = run(mod)
        assert [name for name, _ in first] == [
            'adds[0]',
            'adds[1]',
            'adds[2]',
        ]
        assert [name for name, _ in second] == [
            'adds[0]',
            'adds[1]',
            'adds[2]',
        ]

    def on_class_method(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_on_class_method',
        )
        results = run(mod)
        names = [name for name, _ in results]
        assert names == ['Cls.method[0]', 'Cls.method[1]']
        for _, exc in results:
            assert exc is None


@test
class RunParamsLazy:
    def runs_each_yielded_tuple(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_lazy_generator',
        )
        # Re-import so the module-level generator is freshly created.
        importlib.reload(mod)
        results = run(mod)
        names = [name for name, _ in results]
        assert names == ['adds[0]', 'adds[1]', 'adds[2]']
        for _, exc in results:
            assert exc is None

    def generator_is_consumed_after_first_run(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_lazy_generator',
        )
        importlib.reload(mod)
        first = run(mod)
        second = run(mod)
        assert len(first) == 3
        assert second == []

    def list_is_idempotent(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_lazy_list',
        )
        importlib.reload(mod)
        first = run(mod)
        second = run(mod)
        names_first = [name for name, _ in first]
        names_second = [name for name, _ in second]
        assert names_first == ['equals[0]', 'equals[1]']
        assert names_second == ['equals[0]', 'equals[1]']

    def on_class_method(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_lazy_on_class_method',
        )
        importlib.reload(mod)
        results = run(mod)
        names = [name for name, _ in results]
        assert names == ['Cls.method[0]', 'Cls.method[1]']
        for _, exc in results:
            assert exc is None


@test
class RunNames:
    def filters_to_named_function(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        results = run(mod, names=['passes_one'])
        assert [name for name, _ in results] == ['passes_one']

    def class_name_runs_all_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        results = run(mod, names=['Simple'])
        assert [name for name, _ in results] == [
            'Simple.first',
            'Simple.second',
        ]

    def class_method_selector_runs_one(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        results = run(mod, names=['Simple.first'])
        assert [name for name, _ in results] == ['Simple.first']

    def two_method_selectors_run_in_vars_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        results = run(
            mod,
            names=['Simple.second', 'Simple.first'],
        )
        # vars() order, NOT argv order — Simple.first defined first.
        assert [name for name, _ in results] == [
            'Simple.first',
            'Simple.second',
        ]

    def class_form_wins_over_method_form(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        results = run(mod, names=['Simple', 'Simple.first'])
        assert [name for name, _ in results] == [
            'Simple.first',
            'Simple.second',
        ]

    def unmatched_name_raises_lookup_error(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        with catch_exceptions() as excs:
            run(mod, names=['nonexistent'])
        assert len(excs) == 1
        assert isinstance(excs[0], LookupError)
        assert 'nonexistent' in str(excs[0])

    def validation_runs_before_execution(self):
        # If any name is unmatched, NO test runs — the matched ones are
        # not partially executed before the error.
        mod = importlib.import_module(
            'tests.fixtures.runner.class_calls_recorded',
        )
        mod.CALLS.clear()
        with catch_exceptions() as excs:
            run(mod, names=['Recorded.first', 'Recorded.nonexistent'])
        assert len(excs) == 1
        assert isinstance(excs[0], LookupError)
        assert mod.CALLS == []

    def parameterized_function_selector_runs_all_params(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_simple',
        )
        results = run(mod, names=['adds'])
        assert [name for name, _ in results] == ['adds[0]', 'adds[1]']

    def class_method_unknown_method_raises(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        with catch_exceptions() as excs:
            run(mod, names=['Simple.nonexistent'])
        assert len(excs) == 1
        assert isinstance(excs[0], LookupError)


@test
class DecoratedClass:
    def runs_decorated_class_without_context_manager(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_decorated_simple',
        )
        results = run(mod)
        names = sorted(name for name, _ in results)
        assert names == ['Simple.fails', 'Simple.passes']
        outcomes = {name: exc for name, exc in results}
        assert outcomes['Simple.passes'] is None
        assert isinstance(outcomes['Simple.fails'], AssertionError)

    def runs_decorated_class_with_context_manager(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_decorated_with_cm',
        )
        results = run(mod)
        assert [name for name, _ in results] == ['WithCM.uses_fixture']
        assert results[0][1] is None
        assert mod.CALLS == ['enter', 'test', 'exit']

    def class_with_enter_only_propagates_type_error(self):
        # The runner only checks for __enter__; a class missing
        # __exit__ falls through to Python's `with` machinery, which
        # raises TypeError ("does not support the context manager
        # protocol") before __enter__ is called. The error escapes
        # run() rather than being recorded as a test failure.
        mod = importlib.import_module(
            'tests.fixtures.runner.class_enter_only',
        )
        with catch_exceptions() as excs:
            run(mod)
        assert len(excs) == 1
        assert isinstance(excs[0], TypeError)
        assert '__exit__' in str(excs[0])


@test
class DecoratorOnClass:
    def decorator_marks_class(self):
        @test
        class Cls:
            pass

        assert getattr(Cls, TEST_MARKER) is True

    def undecorated_class_has_no_marker(self):
        class Cls:
            pass

        assert not hasattr(Cls, TEST_MARKER)

    def marker_propagates_to_subclass(self):
        @test
        class Parent:
            pass

        class Child(Parent):
            pass

        assert getattr(Child, TEST_MARKER) is True


@test
class DiscoverIntegration:
    def discover_returns_decorated_class(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        result = discover(mod)
        assert [cls.__name__ for cls in result] == ['Simple']


@test
class PublicMethods:
    def returns_leaf_methods_in_definition_order(self):
        @test
        class Cls:
            def b_method(self):
                pass

            def a_method(self):
                pass

        assert _public_methods(Cls) == ['b_method', 'a_method']

    def excludes_underscore_prefixed_methods(self):
        @test
        class Cls:
            def _private(self):
                pass

            def public(self):
                pass

            def __dunder(self):
                pass

        assert _public_methods(Cls) == ['public']

    def includes_inherited_methods_with_leaf_priority(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_with_inheritance',
        )
        assert _public_methods(mod.Leaf) == [
            'leaf_method',
            'overridden',
            'base_method',
        ]

    def diamond_inheritance_follows_mro(self):
        class A:
            def from_a(self):
                pass

            def shared(self):
                pass

        class B:
            def from_b(self):
                pass

            def shared(self):
                pass

        @test
        class Leaf(A, B):
            def from_leaf(self):
                pass

        assert _public_methods(Leaf) == [
            'from_leaf',
            'from_a',
            'shared',
            'from_b',
        ]

    def staticmethod_is_included(self):
        @test
        class Cls:
            @staticmethod
            def a_static():
                pass

            def regular(self):
                pass

        assert _public_methods(Cls) == ['a_static', 'regular']

    def classmethod_is_excluded(self):
        @test
        class Cls:
            @classmethod
            def a_class(cls):
                pass

            def regular(self):
                pass

        assert _public_methods(Cls) == ['regular']
