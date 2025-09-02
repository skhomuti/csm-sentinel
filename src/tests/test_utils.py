import random
import string

from csm_bot.utils import chunk_text


def test_chunk_text_empty_string():
    assert chunk_text("") == [""]


def test_chunk_text_under_limit_single_chunk():
    s = "hello world"
    chunks = chunk_text(s, limit=20)
    assert chunks == [s]


def test_chunk_text_exact_limit_single_chunk():
    s = "x" * 50
    chunks = chunk_text(s, limit=50)
    assert chunks == [s]


def test_chunk_text_single_line_over_limit_splits():
    s = "a" * 130
    chunks = chunk_text(s, limit=50)
    # Expect three chunks: 50, 50, 30
    assert [len(c) for c in chunks] == [50, 50, 30]
    # Reconstruct by concatenation (no newlines in original)
    assert "".join(chunks) == s


def test_chunk_text_multiline_crossing_limit_preserves_lines():
    # Create multiple lines whose cumulative length crosses limit
    lines = [
        "alpha",
        "beta",
        "gamma",
        "delta",
        "".join(["x" for _ in range(25)]),  # 25 x's
        "epsilon",
        "zeta",
    ]
    s = "\n".join(lines)
    limit = 30
    chunks = chunk_text(s, limit=limit)
    # All chunks must respect the limit
    assert all(len(c) <= limit for c in chunks)
    # Reconstruct original using newline between chunks (since splits are on line boundaries)
    # Note: This is valid here because no single line exceeds the limit
    assert "\n".join(chunks) == s


def test_chunk_text_long_line_followed_by_short_lines():
    long_line = "L" * 120
    rest = ["one", "two", "three"]
    s = "\n".join([long_line] + rest)
    limit = 50
    chunks = chunk_text(s, limit=limit)
    # Expect: two full chunks from long line (50, 50), remainder 20 merges with following lines
    assert len(chunks) >= 3
    assert chunks[0] == "L" * 50
    assert chunks[1] == "L" * 50
    # The remainder chunk starts with 20 L's and includes subsequent short lines joined with newlines
    assert chunks[2].startswith("L" * 20)
    # Validate no chunk exceeds limit
    assert all(len(c) <= limit for c in chunks)
    # Validate full reconstruction by simple concatenation since the first
    # split boundaries are within the long line
    assert "".join(chunks) == s


def test_chunk_text_boundary_with_newline_fit():
    # First line exactly fills the limit; next short line should go to next chunk
    first = "A" * 20
    second = "B"
    s = first + "\n" + second
    chunks = chunk_text(s, limit=20)
    assert chunks[0] == first
    assert chunks[1] == second


def test_chunk_text_randomized_no_chunk_exceeds_limit():
    # Fuzz a bit to ensure invariant holds
    random.seed(0)
    for _ in range(10):
        lines = []
        for __ in range(random.randint(5, 20)):
            # Some lines may be long
            length = random.randint(0, 150)
            line = "".join(random.choices(string.ascii_letters + string.digits, k=length))
            lines.append(line)
        s = "\n".join(lines)
        limit = random.randint(20, 80)
        chunks = chunk_text(s, limit=limit)
        assert all(len(c) <= limit for c in chunks)
