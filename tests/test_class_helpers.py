import importlib
import unittest

from testsweet import discover, test
from testsweet._markers import TEST_MARKER
from testsweet._class_helpers import _public_methods


class TestDecoratorOnClass(unittest.TestCase):
    def test_decorator_marks_class(self):
        @test
        class Cls:
            pass

        self.assertIs(getattr(Cls, TEST_MARKER), True)

    def test_undecorated_class_has_no_marker(self):
        class Cls:
            pass

        self.assertFalse(hasattr(Cls, TEST_MARKER))

    def test_marker_propagates_to_subclass(self):
        # The marker is set as a class attribute, so subclasses
        # inherit it via __mro__ lookup. Both parent and child are
        # discovered as test units when both live in a module.
        @test
        class Parent:
            pass

        class Child(Parent):
            pass

        self.assertIs(getattr(Child, TEST_MARKER), True)


class TestDiscoverIntegration(unittest.TestCase):
    def test_discover_returns_decorated_class(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        result = discover(mod)
        self.assertEqual([cls.__name__ for cls in result], ['Simple'])


class TestPublicMethods(unittest.TestCase):
    def test_returns_leaf_methods_in_definition_order(self):
        @test
        class Cls:
            def b_method(self):
                pass

            def a_method(self):
                pass

        self.assertEqual(
            _public_methods(Cls),
            ['b_method', 'a_method'],
        )

    def test_excludes_underscore_prefixed_methods(self):
        @test
        class Cls:
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

        self.assertEqual(
            _public_methods(Leaf),
            ['from_leaf', 'from_a', 'shared', 'from_b'],
        )

    def test_staticmethod_is_included(self):
        @test
        class Cls:
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
        @test
        class Cls:
            @classmethod
            def a_class(cls):
                pass

            def regular(self):
                pass

        self.assertEqual(_public_methods(Cls), ['regular'])


if __name__ == '__main__':
    unittest.main()
