from pathlib import Path

from app.rag.chunker import _py_chunks, _window_chunks


def test_py_chunks_function_and_class():
    src = (
        "def a():\n    return 1\n\n"
        "class C:\n    def m(self):\n        return 2\n"
    )
    chunks = _py_chunks("x.py", src)
    kinds = {c.kind for c in chunks}
    symbols = {c.symbol for c in chunks}
    assert "function" in kinds and "class" in kinds
    assert "a" in symbols and "C.m" in symbols
    assert all(c.start_line >= 1 and c.end_line >= c.start_line for c in chunks)


def test_window_fallback_overlaps():
    src = "\n".join(f"line {i}" for i in range(1, 300))
    chunks = _window_chunks("x.txt", "text", src, kind="block")
    assert len(chunks) >= 2
    assert chunks[0].start_line == 1
    assert chunks[-1].end_line == 299