import unittest
import warnings

from assertions import catch_exceptions, catch_warnings


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
    pass


if __name__ == '__main__':
    unittest.main()
