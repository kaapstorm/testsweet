import importlib
import unittest

from assertions import Test, discover
from assertions._markers import TEST_MARKER
from assertions._test_class import _public_methods


class TestMarkerPropagation(unittest.TestCase):
    def test_test_itself_has_no_marker(self):
        self.assertFalse(hasattr(Test, TEST_MARKER))

    def test_subclass_has_marker(self):
        class Sub(Test):
            pass

        self.assertIs(getattr(Sub, TEST_MARKER), True)

    def test_sub_subclass_has_marker(self):
        class Sub(Test):
            pass

        class SubSub(Sub):
            pass

        self.assertIs(getattr(SubSub, TEST_MARKER), True)


class TestDiscoverIntegration(unittest.TestCase):
    def test_discover_returns_test_subclass(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        result = discover(mod)
        self.assertEqual([cls.__name__ for cls in result], ['Simple'])

    def test_discover_skips_imported_test_base_itself(self):
        # Import Test into a namespace and confirm discover doesn't
        # return the Test class itself.
        import types

        mod = types.ModuleType('synthetic')
        mod.Test = Test  # type: ignore[attr-defined]
        result = discover(mod)
        self.assertEqual(result, [])


class TestPublicMethods(unittest.TestCase):
    def test_returns_leaf_methods_in_definition_order(self):
        class Cls(Test):
            def b_method(self):
                pass

            def a_method(self):
                pass

        names = [f.__name__ for f in _public_methods(Cls)]
        self.assertEqual(names, ['b_method', 'a_method'])

    def test_excludes_underscore_prefixed_methods(self):
        class Cls(Test):
            def _private(self):
                pass

            def public(self):
                pass

            def __dunder(self):
                pass

        names = [f.__name__ for f in _public_methods(Cls)]
        self.assertEqual(names, ['public'])

    def test_includes_inherited_methods_with_leaf_priority(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_with_inheritance',
        )
        names = [f.__name__ for f in _public_methods(mod.Leaf)]
        # Leaf-defined first in definition order, then base's
        # remaining methods. The override 'overridden' appears once,
        # in the leaf's position.
        self.assertEqual(
            names,
            ['leaf_method', 'overridden', 'base_method'],
        )


class TestPublicMethodsCurrentBehavior(unittest.TestCase):
    # These tests document existing behavior of _public_methods for
    # cases that the spec did not explicitly call out. They are not
    # contracts — they are observations. Future changes to broaden or
    # narrow what counts as a "public method" should update them.

    def test_diamond_inheritance_follows_mro(self):
        # MRO is leaf, then bases in declaration order. Methods unique
        # to a base appear in that base's position; a method defined
        # on multiple ancestors is taken from the first MRO ancestor
        # that defines it.
        class A(Test):
            def from_a(self):
                pass

            def shared(self):
                pass

        class B(Test):
            def from_b(self):
                pass

            def shared(self):
                pass

        class Leaf(A, B):
            def from_leaf(self):
                pass

        names = [f.__name__ for f in _public_methods(Leaf)]
        self.assertEqual(
            names,
            ['from_leaf', 'from_a', 'shared', 'from_b'],
        )

    def test_staticmethod_is_included(self):
        # Python 3.10+ made staticmethod callable, so the
        # `callable(value)` filter does not exclude it.
        class Cls(Test):
            @staticmethod
            def a_static():
                pass

            def regular(self):
                pass

        names = [f.__name__ for f in _public_methods(Cls)]
        self.assertEqual(names, ['a_static', 'regular'])

    def test_classmethod_is_excluded(self):
        # The classmethod descriptor stored in vars(cls) is not
        # callable directly (unlike staticmethod), so the
        # `callable(value)` filter drops it. Accessing it via
        # getattr(cls, name) would yield a bound method, which is
        # callable — but _public_methods looks at vars(cls), not
        # getattr.
        class Cls(Test):
            @classmethod
            def a_class(cls):
                pass

            def regular(self):
                pass

        names = [f.__name__ for f in _public_methods(Cls)]
        self.assertEqual(names, ['regular'])


if __name__ == '__main__':
    unittest.main()
