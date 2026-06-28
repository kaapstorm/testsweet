from testsweet import test
from testsweet._catches import catch_exceptions
from testsweet._markers import TAGS_MARKER
from testsweet._tag import tag


@test
class TagDecorator:
    def single_tag_attached_as_frozenset(self):
        @tag('slow')
        def f():
            pass

        tags = getattr(f, TAGS_MARKER)
        assert tags == frozenset({'slow'})
        assert isinstance(tags, frozenset)

    def multiple_positional_tags_in_one_call(self):
        @tag('slow', 'integration')
        def f():
            pass

        assert getattr(f, TAGS_MARKER) == frozenset({'slow', 'integration'})

    def stacked_calls_union(self):
        @tag('slow')
        @tag('integration')
        def f():
            pass

        assert getattr(f, TAGS_MARKER) == frozenset({'slow', 'integration'})

    def stacked_calls_with_overlap_dedupes(self):
        @tag('slow', 'integration')
        @tag('slow')
        def f():
            pass

        assert getattr(f, TAGS_MARKER) == frozenset({'slow', 'integration'})

    def empty_call_raises_type_error(self):
        with catch_exceptions() as caught:
            tag()
        assert len(caught) == 1
        assert isinstance(caught[0], TypeError)

    def non_string_arg_raises_type_error(self):
        with catch_exceptions() as caught:
            tag('slow', 7)
        assert len(caught) == 1
        assert isinstance(caught[0], TypeError)

    def all_non_string_args_raises_type_error(self):
        with catch_exceptions() as caught:
            tag(1, 2)
        assert len(caught) == 1
        assert isinstance(caught[0], TypeError)

    def returns_function_unchanged(self):
        def f():
            return 42

        decorated = tag('a')(f)
        assert decorated is f
        assert f() == 42


@test
def tags_marker_name_is_dunder_testsweet_tags():
    assert TAGS_MARKER == '__testsweet_tags__'
