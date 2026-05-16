import io

from testsweet import test
from testsweet._outcomes import (
    Errored,
    Failed,
    Passed,
    Skipped,
    XFailed,
    XPassed,
)

Outcome = Passed | Failed | Errored | Skipped | XFailed | XPassed
Results = list[tuple[str, Outcome]]
from testsweet._report import (
    format_result_line,
    print_failure_detail,
    summarize,
)


def _capture(full_name, outcome):
    buf = io.StringIO()
    print_failure_detail(full_name, outcome, file=buf)
    return buf.getvalue()


@test
class FormatResultLine:
    def pass_outcome(self):
        assert format_result_line('mod.t', Passed()) == 'mod.t ... ok'

    def skipped_with_reason(self):
        line = format_result_line('mod.t', Skipped('not yet'))
        assert line == 'mod.t ... skipped: not yet'

    def skipped_without_reason(self):
        line = format_result_line('mod.t', Skipped())
        assert line == 'mod.t ... skipped'

    def xfailed_with_reason(self):
        line = format_result_line(
            'mod.t', XFailed(ValueError('boom'), 'see #42'),
        )
        assert line == 'mod.t ... xfailed: see #42'

    def xfailed_without_reason(self):
        line = format_result_line('mod.t', XFailed(ValueError('boom')))
        assert line == 'mod.t ... xfailed'

    def xpassed_with_reason(self):
        line = format_result_line('mod.t', XPassed('see #42'))
        assert line == 'mod.t ... XPASSED: see #42'

    def xpassed_without_reason(self):
        line = format_result_line('mod.t', XPassed())
        assert line == 'mod.t ... XPASSED'

    def failed_for_assertion_error(self):
        outcome = Failed(AssertionError('1 == 2'))
        line = format_result_line('mod.t', outcome)
        assert line == 'mod.t ... FAIL: AssertionError: 1 == 2'

    def errored_for_other_exception(self):
        outcome = Errored(TypeError("'int' object is not iterable"))
        line = format_result_line('mod.t', outcome)
        assert line == (
            "mod.t ... ERROR: TypeError: 'int' object is not iterable"
        )


@test
class PrintFailureDetail:
    def passed_emits_nothing(self):
        assert _capture('mod.t', Passed()) == ''

    def skipped_emits_nothing(self):
        assert _capture('mod.t', Skipped('reason')) == ''

    def xfailed_emits_nothing(self):
        assert _capture('mod.t', XFailed(ValueError('x'), 'r')) == ''

    def xpassed_emits_marker_message(self):
        out = _capture('mod.t', XPassed('see #42'))
        assert 'XPASSED' in out
        assert 'mod.t' in out
        assert '@xfail' in out
        assert 'remove the marker' in out

    def xpassed_does_not_emit_traceback(self):
        out = _capture('mod.t', XPassed())
        assert 'Traceback' not in out

    def failed_emits_traceback_block(self):
        try:
            assert 1 == 2
        except AssertionError as exc:
            out = _capture('mod.t', Failed(exc))
        assert 'FAIL: mod.t' in out
        assert 'AssertionError' in out

    def errored_emits_error_block(self):
        try:
            raise TypeError('nope')
        except TypeError as exc:
            out = _capture('mod.t', Errored(exc))
        assert 'ERROR: mod.t' in out
        assert 'TypeError' in out


@test
class Summarize:
    def empty_results(self):
        assert summarize([]) == '0 tests'

    def all_passes(self):
        results = [('a', Passed()), ('b', Passed())]
        assert summarize(results) == '2 passed'

    def mixed_outcomes(self):
        results: Results = [
            ('p1', Passed()),
            ('p2', Passed()),
            ('f1', Failed(AssertionError('x'))),
            ('e1', Errored(TypeError('y'))),
            ('s1', Skipped('later')),
            ('xf1', XFailed(ValueError('z'))),
            ('xp1', XPassed()),
        ]
        assert summarize(results) == (
            '2 passed, 1 failed, 1 error, '
            '1 skipped, 1 xfailed, 1 xpassed'
        )

    def zero_categories_omitted(self):
        results = [('s1', Skipped()), ('s2', Skipped())]
        assert summarize(results) == '2 skipped'

    def category_order_is_stable(self):
        # Insertion order in `results` doesn't matter — summarize
        # always emits passed → failed → error → skipped → xfailed
        # → xpassed.
        results: Results = [
            ('xp1', XPassed()),
            ('p1', Passed()),
            ('s1', Skipped()),
            ('f1', Failed(AssertionError())),
        ]
        assert summarize(results) == (
            '1 passed, 1 failed, 1 skipped, 1 xpassed'
        )
