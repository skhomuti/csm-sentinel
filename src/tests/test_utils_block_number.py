import pytest

from csm_bot.utils import normalize_block_number


@pytest.mark.parametrize(
    "inp,expected",
    [
        (0, 0),
        (1, 1),
        (123456, 123456),
        ("0", 0),
        ("42", 42),
        ("  42  ", 42),
        (0x1a, 26),
        ("0x1a", 26),
        ("0X1A", 26),
    ],
)
def test_normalize_block_number_valid(inp, expected):
    assert normalize_block_number(inp) == expected


@pytest.mark.parametrize("inp", ["", "not-a-number", None])
def test_normalize_block_number_invalid(inp):
    with pytest.raises((TypeError, ValueError)):
        normalize_block_number(inp)

