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

        self.assertEqual(
            _public_methods(Cls),
            ['b_method', 'a_method'],
        )

    def test_excludes_underscore_prefixed_methods(self):
        class Cls(Test):
            def _private(self):
                pass

            def public(self):
                pass

            def __dunder(self):
                pass

        self.assertEqual(_public_methods(Cls), ['public'])

    def test_includes_inherited_methods_with_leaf_priority(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_with_inheritance',
        )
        # Leaf-defined first in definition order, then base's
        # remaining methods. The override 'overridden' appears once,
        # in the leaf's position.
        self.assertEqual(
            _public_methods(mod.Leaf),
            ['leaf_method', 'overridden', 'base_method'],
        )


class TestPublicMethodsCurrentBehavior(unittest.TestCase):
    # These tests document existing behavior of _public_methods for
    # cases that the spec did not explicitly call out. They are not
    # contracts — they are observations. Future changes to broaden or
    # narrow what counts as a "public method" should update them.

    def test_diamond_inheritance_follows_mro(self):
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

        self.assertEqual(
            _public_methods(Leaf),
            ['from_leaf', 'from_a', 'shared', 'from_b'],
        )

    def test_staticmethod_is_included(self):
        class Cls(Test):
            @staticmethod
            def a_static():
                pass

            def regular(self):
                pass

        self.assertEqual(
            _public_methods(Cls),
            ['a_static', 'regular'],
        )

    def test_classmethod_is_excluded(self):
        class Cls(Test):
            @classmethod
            def a_class(cls):
                pass

            def regular(self):
                pass

        self.assertEqual(_public_methods(Cls), ['regular'])


if __name__ == '__main__':
    unittest.main()
