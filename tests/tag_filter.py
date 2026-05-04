from testsweet import test
from testsweet._tag_filter import make_tag_filter


@test
class MakeTagFilter:
    def empty_filters_keep_everything(self):
        keep = make_tag_filter(frozenset(), frozenset())
        assert keep(frozenset()) is True
        assert keep(frozenset({'slow'})) is True
        assert keep(frozenset({'a', 'b', 'c'})) is True

    def include_only_keeps_matching(self):
        keep = make_tag_filter(frozenset({'slow'}), frozenset())
        assert keep(frozenset({'slow'})) is True
        assert keep(frozenset({'slow', 'db'})) is True
        assert keep(frozenset({'fast'})) is False
        assert keep(frozenset()) is False

    def include_is_or(self):
        keep = make_tag_filter(
            frozenset({'slow', 'db'}), frozenset(),
        )
        assert keep(frozenset({'slow'})) is True
        assert keep(frozenset({'db'})) is True
        assert keep(frozenset({'fast'})) is False

    def exclude_only_drops_matching(self):
        keep = make_tag_filter(frozenset(), frozenset({'flaky'}))
        assert keep(frozenset({'flaky'})) is False
        assert keep(frozenset({'flaky', 'slow'})) is False
        assert keep(frozenset({'slow'})) is True
        assert keep(frozenset()) is True

    def exclude_is_a_hard_veto(self):
        # A test tagged with both an included AND an excluded tag is
        # excluded — exclude wins.
        keep = make_tag_filter(
            frozenset({'slow'}), frozenset({'flaky'}),
        )
        assert keep(frozenset({'slow', 'flaky'})) is False
        assert keep(frozenset({'slow'})) is True
        assert keep(frozenset({'flaky'})) is False

    def filter_is_order_independent(self):
        # Set algebra: rebuilding the predicate with reversed
        # construction order makes no difference.
        a = make_tag_filter(
            frozenset({'a', 'b'}), frozenset({'c', 'd'}),
        )
        b = make_tag_filter(
            frozenset({'b', 'a'}), frozenset({'d', 'c'}),
        )
        for tags in [
            frozenset(),
            frozenset({'a'}),
            frozenset({'a', 'c'}),
            frozenset({'b', 'c', 'd'}),
        ]:
            assert a(tags) == b(tags)
