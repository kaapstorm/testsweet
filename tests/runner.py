import importlib
from contextlib import contextmanager

from testsweet import catch_exceptions, discover, run, test
from testsweet._class_helpers import _public_methods
from testsweet._markers import TEST_MARKER
from testsweet import params
from testsweet._outcomes import (
    Errored,
    Failed,
    Passed,
    Skipped,
    XFailed,
    XPassed,
)
from testsweet._skip import skip
from testsweet._xfail import xfail


@test
class Run:
    def single_passing_test(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        results = run(mod)
        assert len(results) == 2
        for _, outcome in results:
            assert isinstance(outcome, Passed)

    def single_failing_assert(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        results = run(mod)
        assert results[0][0] == 'passes'
        assert isinstance(results[0][1], Passed)
        assert results[1][0] == 'fails'
        assert isinstance(results[1][1], Failed)
        assert isinstance(results[1][1].exc, AssertionError)

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
        name, outcome = results[0]
        assert name == 'raises_value_error'
        assert isinstance(outcome, Errored)
        assert isinstance(outcome.exc, ValueError)

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
        for _, outcome in results:
            assert isinstance(outcome, Passed)

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
        assert isinstance(results[0][1], Passed)
        assert isinstance(results[1][1], Failed)
        assert isinstance(results[1][1].exc, AssertionError)

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
        for _, outcome in results:
            assert isinstance(outcome, Passed)

    def failure_recorded_at_correct_index(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_with_failure',
        )
        results = run(mod)
        names = [name for name, _ in results]
        assert names == ['adds[0]', 'adds[1]', 'adds[2]']
        assert isinstance(results[0][1], Passed)
        assert isinstance(results[1][1], Failed)
        assert isinstance(results[1][1].exc, AssertionError)
        assert isinstance(results[2][1], Passed)

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
        for _, outcome in results:
            assert isinstance(outcome, Passed)

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
        for _, outcome in results:
            assert isinstance(outcome, Passed)


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
        for _, outcome in results:
            assert isinstance(outcome, Passed)

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
        for _, outcome in results:
            assert isinstance(outcome, Passed)


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
        outcomes = dict(results)
        assert isinstance(outcomes['Simple.passes'], Passed)
        assert isinstance(outcomes['Simple.fails'], Failed)
        assert isinstance(outcomes['Simple.fails'].exc, AssertionError)

    def runs_decorated_class_with_context_manager(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_decorated_with_cm',
        )
        results = run(mod)
        assert [name for name, _ in results] == ['WithCM.uses_fixture']
        assert isinstance(results[0][1], Passed)
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


@test
class RunWithWrapUnit:
    def wrap_unit_brackets_each_test(self):
        events: list[str] = []

        @contextmanager
        def wrap(name):
            events.append(f'enter:{name}')
            try:
                yield
            finally:
                events.append(f'exit:{name}')

        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        results = run(mod, wrap_unit=wrap)
        assert [name for name, _ in results] == [
            'passes_one', 'passes_two',
        ]
        assert events == [
            'enter:passes_one', 'exit:passes_one',
            'enter:passes_two', 'exit:passes_two',
        ]

    def no_wrap_unit_argument_works(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        results = run(mod)
        assert len(results) == 2

    def wrap_unit_enter_failure_attributed_to_test(self):
        @contextmanager
        def wrap(name):
            raise RuntimeError(f'enter:{name}')
            yield  # pragma: no cover

        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        results = run(mod, wrap_unit=wrap)
        for _, outcome in results:
            assert isinstance(outcome, Errored)
            assert isinstance(outcome.exc, RuntimeError)

    def wrap_unit_exit_failure_attributed_to_test(self):
        @contextmanager
        def wrap(name):
            try:
                yield
            finally:
                raise RuntimeError(f'exit:{name}')

        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        results = run(mod, wrap_unit=wrap)
        for _, outcome in results:
            assert isinstance(outcome, Errored)
            assert isinstance(outcome.exc, RuntimeError)


@test
class RunWithTestContext:
    def params_combine_with_test_context(self):
        # Each parametrized index is wrapped in __test_context__
        # independently — the per-method fixture brackets every call.
        mod = importlib.import_module(
            'tests.fixtures.runner.class_test_context_with_params',
        )
        mod.CALLS.clear()
        results = run(mod)
        names = [name for name, _ in results]
        assert names == ['Cls.method[0]', 'Cls.method[1]']
        for _, outcome in results:
            assert isinstance(outcome, Passed)
        assert mod.CALLS == [
            'enter',
            'ctx-enter', 'method(1,2)', 'ctx-exit',
            'ctx-enter', 'method(3,4)', 'ctx-exit',
            'exit',
        ]

    def test_context_enter_failure_attributed_to_test(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_test_context_raises',
        )
        results = run(mod, names=['TestContextEnterRaises'])
        assert [name for name, _ in results] == [
            'TestContextEnterRaises.passes',
        ]
        outcome = results[0][1]
        assert isinstance(outcome, Errored)
        assert isinstance(outcome.exc, RuntimeError)
        assert 'enter failed' in str(outcome.exc)

    def test_context_exit_failure_attributed_to_test(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_test_context_raises',
        )
        results = run(mod, names=['TestContextExitRaises'])
        assert [name for name, _ in results] == [
            'TestContextExitRaises.passes',
        ]
        outcome = results[0][1]
        assert isinstance(outcome, Errored)
        assert isinstance(outcome.exc, RuntimeError)
        assert 'exit failed' in str(outcome.exc)


@test
class RunWithOutcomes:
    def skip_bare_skips_without_running_body(self):
        called: list[str] = []

        @test
        @skip
        def skipped():
            called.append('ran')  # pragma: no cover

        @test
        def runs():
            called.append('runs')

        mod = _module_with(skipped=skipped, runs=runs)
        results = run(mod)
        outcomes = dict(results)
        assert isinstance(outcomes['skipped'], Skipped)
        assert isinstance(outcomes['runs'], Passed)
        assert called == ['runs']

    def skip_with_condition_false_runs_normally(self):
        called: list[str] = []

        @test
        @skip(condition=False)
        def maybe():
            called.append('ran')

        mod = _module_with(maybe=maybe)
        results = run(mod)
        assert called == ['ran']
        assert len(results) == 1
        assert results[0][0] == 'maybe'
        assert isinstance(results[0][1], Passed)

    def skip_with_callable_condition_evaluated_at_run_time(self):
        # The callable is invoked when the runner gets to the test,
        # not at decoration time — so passing a function reference
        # (without parens) does what the user expects.
        called: list[str] = []

        def is_skipped() -> bool:
            called.append('cond')
            return True

        @test
        @skip(condition=is_skipped, reason='lazy')
        def maybe():
            called.append('ran')  # pragma: no cover

        mod = _module_with(maybe=maybe)
        results = run(mod)
        assert called == ['cond']
        outcome = results[0][1]
        assert isinstance(outcome, Skipped)
        assert outcome.reason == 'lazy'

    def skip_with_callable_condition_returning_false_runs_test(self):
        called: list[str] = []

        @test
        @skip(condition=lambda: False)
        def maybe():
            called.append('ran')

        mod = _module_with(maybe=maybe)
        results = run(mod)
        assert called == ['ran']
        assert isinstance(results[0][1], Passed)

    def skip_callable_condition_raising_records_errored(self):
        @test
        @skip(condition=lambda: 1 / 0)
        def maybe():
            pass  # pragma: no cover

        mod = _module_with(maybe=maybe)
        results = run(mod)
        outcome = results[0][1]
        assert isinstance(outcome, Errored)
        assert isinstance(outcome.exc, ZeroDivisionError)

    def skip_reason_appears_on_skipped(self):
        @test
        @skip(reason='not yet implemented')
        def pending():
            pass  # pragma: no cover

        mod = _module_with(pending=pending)
        results = run(mod)
        _, exc = results[0]
        assert isinstance(exc, Skipped)
        assert exc.reason == 'not yet implemented'

    def xfail_body_raises_records_xfailed(self):
        @test
        @xfail(reason='known bug')
        def broken():
            raise ValueError('boom')

        mod = _module_with(broken=broken)
        results = run(mod)
        _, exc = results[0]
        assert isinstance(exc, XFailed)
        assert isinstance(exc.actual, ValueError)
        assert exc.reason == 'known bug'

    def xfail_body_passes_records_xpassed(self):
        @test
        @xfail(reason='supposedly broken')
        def secretly_works():
            pass

        mod = _module_with(secretly_works=secretly_works)
        results = run(mod)
        _, exc = results[0]
        assert isinstance(exc, XPassed)
        assert exc.reason == 'supposedly broken'

    def skip_wins_over_xfail_when_both_present(self):
        called: list[str] = []

        @test
        @skip(reason='skip me')
        @xfail
        def both():
            called.append('ran')  # pragma: no cover

        mod = _module_with(both=both)
        results = run(mod)
        _, exc = results[0]
        assert isinstance(exc, Skipped)
        assert exc.reason == 'skip me'
        assert called == []

    def skip_on_parametrized_skips_every_combo(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.skip_on_params',
        )
        importlib.reload(mod)
        results = run(mod)
        assert [name for name, _ in results] == [
            'parametrized[0]', 'parametrized[1]',
        ]
        for _, exc in results:
            assert isinstance(exc, Skipped)
            assert exc.reason == 'blocked'
        assert mod.CALLS == []

    def xfail_on_parametrized_evaluated_independently(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.xfail_on_params',
        )
        results = run(mod)
        outcomes = dict(results)
        # x == 1 raises -> XFailed
        assert isinstance(outcomes['parametrized[0]'], XFailed)
        assert isinstance(outcomes['parametrized[0]'].actual, ValueError)
        # x == 2 passes -> XPassed
        assert isinstance(outcomes['parametrized[1]'], XPassed)

    def skip_on_class_method_skips_method_only(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.skip_on_class_method',
        )
        mod.CALLS.clear()
        results = run(mod)
        outcomes = dict(results)
        assert isinstance(
            outcomes['Cls.skipped_method'], Skipped,
        )
        assert outcomes['Cls.skipped_method'].reason == 'not yet'
        assert isinstance(outcomes['Cls.runs'], Passed)
        # __enter__ / __exit__ still fire; skipped body does not.
        assert mod.CALLS == ['enter', 'runs', 'exit']


def _module_with(**funcs):
    """Build a throwaway module exposing ``funcs`` as test units.

    Used by RunWithOutcomes to test in-line decorator combinations
    without spawning a fixture file per case.
    """
    import types

    mod = types.ModuleType('tests.runner._inline')
    for name, func in funcs.items():
        # Rebind __qualname__ so resolve_units yields predictable names.
        try:
            func.__qualname__ = name
        except (AttributeError, TypeError):
            pass
        setattr(mod, name, func)
    return mod
