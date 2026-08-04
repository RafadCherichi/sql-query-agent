from src.eval.harness import rows_match


def test_exact_match_passes():
    assert rows_match([["Iron Maiden"]], [["Iron Maiden"]])


def test_extra_columns_still_pass():
    # agent selected extra columns (e.g. COUNT alongside the answer) —
    # this is the bug found during the Phase 5 eval run: it should still count.
    assert rows_match([["Iron Maiden", 21]], [["Iron Maiden"]])


def test_wrong_value_fails():
    assert not rows_match([["Metallica"]], [["Iron Maiden"]])


def test_row_order_independent():
    assert rows_match([["b"], ["a"]], [["a"], ["b"]])


def test_extra_rows_do_not_pass_via_containment():
    # agent dumping a whole table shouldn't "pass" just because the right
    # value happens to be in there somewhere — row counts must match.
    assert not rows_match([["Iron Maiden"], ["Metallica"]], [["Iron Maiden"]])


def test_none_agent_rows_fails():
    assert not rows_match(None, [["Iron Maiden"]])
