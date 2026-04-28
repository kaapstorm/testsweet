import unittest
import warnings

from testsweet import catch_exceptions, catch_warnings


class TestCatchExceptions(unittest.TestCase):
    def test_captures_exception_instance(self):
        with catch_exceptions() as excs:
            raise ValueError('boom')
        self.assertEqual(len(excs), 1)
        self.assertIsInstance(excs[0], ValueError)
        self.assertEqual(str(excs[0]), 'boom')

    def test_captures_subclass_of_exception(self):
        class MyError(ValueError):
            pass

        with catch_exceptions() as excs:
            raise MyError('subclass')
        self.assertEqual(len(excs), 1)
        self.assertIsInstance(excs[0], MyError)

    def test_propagates_keyboard_interrupt(self):
        captured: list[Exception] = []
        with self.assertRaises(KeyboardInterrupt):
            with catch_exceptions() as excs:
                captured = excs
                raise KeyboardInterrupt
        self.assertEqual(captured, [])

    def test_empty_when_body_returns_normally(self):
        with catch_exceptions() as excs:
            x = 1 + 1  # noqa: F841
        self.assertEqual(excs, [])

    def test_list_is_empty_inside_block_before_raise(self):
        observed_inside = None
        with catch_exceptions() as excs:
            observed_inside = list(excs)
            raise ValueError('boom')
        self.assertEqual(observed_inside, [])
        self.assertEqual(len(excs), 1)


class TestCatchWarnings(unittest.TestCase):
    def test_captures_single_warning(self):
        with catch_warnings() as warns:
            warnings.warn('hello', DeprecationWarning)
        self.assertEqual(len(warns), 1)
        self.assertIs(type(warns[0]), DeprecationWarning)
        self.assertIn('hello', str(warns[0]))

    def test_captures_multiple_warnings_in_emission_order(self):
        with catch_warnings() as warns:
            warnings.warn('first', DeprecationWarning)
            warnings.warn('second', UserWarning)
            warnings.warn('third', DeprecationWarning)
        self.assertEqual(len(warns), 3)
        self.assertIs(type(warns[0]), DeprecationWarning)
        self.assertIs(type(warns[1]), UserWarning)
        self.assertIs(type(warns[2]), DeprecationWarning)
        self.assertIn('first', str(warns[0]))
        self.assertIn('second', str(warns[1]))
        self.assertIn('third', str(warns[2]))

    def test_empty_when_no_warnings(self):
        with catch_warnings() as warns:
            x = 1 + 1  # noqa: F841
        self.assertEqual(warns, [])

    def test_exception_propagates_with_warnings_already_captured(self):
        warns_ref = None
        with self.assertRaises(ValueError):
            with catch_warnings() as warns:
                warns_ref = warns
                warnings.warn('before raise', DeprecationWarning)
                raise ValueError('boom')
        self.assertIsNotNone(warns_ref)
        self.assertEqual(len(warns_ref), 1)
        self.assertIs(type(warns_ref[0]), DeprecationWarning)
        self.assertIn('before raise', str(warns_ref[0]))

    def test_outer_filter_error_does_not_escalate_inside(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            with catch_warnings() as warns:
                warnings.warn('caught', DeprecationWarning)
        self.assertEqual(len(warns), 1)
        self.assertIs(type(warns[0]), DeprecationWarning)

    def test_outer_filter_ignore_does_not_silence_inside(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with catch_warnings() as warns:
                warnings.warn('caught', DeprecationWarning)
        self.assertEqual(len(warns), 1)
        self.assertIs(type(warns[0]), DeprecationWarning)


if __name__ == '__main__':
    unittest.main()
