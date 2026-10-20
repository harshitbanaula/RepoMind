import ast
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings

EXT_LANG = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go", ".rs": "rust", ".java": "java",
    ".rb": "ruby", ".php": "php", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp",
    ".cs": "csharp", ".kt": "kotlin", ".swift": "swift",
    ".md": "markdown", ".mdx": "markdown", ".rst": "markdown",
    ".txt": "text", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".json": "json",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".ps1": "powershell",
    ".sql": "sql",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "css", ".sass": "css", ".less": "css",
    ".vue": "vue", ".svelte": "svelte",
    ".tf": "terraform", ".hcl": "terraform",
    ".proto": "protobuf",
    ".dockerfile": "dockerfile",
}

FILENAME_LANG = {
    "Dockerfile": "dockerfile",
    "Containerfile": "dockerfile",
    "Makefile": "makefile",
    "GNUmakefile": "makefile",
    "README": "markdown",
    "LICENSE": "text",
    "COPYING": "text",
    "CHANGELOG": "markdown",
    "CHANGES": "markdown",
    "Procfile": "text",
    "Rakefile": "ruby",
    "Gemfile": "ruby",
    "Vagrantfile": "ruby",
    ".gitignore": "text",
    ".dockerignore": "text",
    ".editorconfig": "text",
}

def detect_language(path: Path) -> str | None:
    if path.name in FILENAME_LANG:
        return FILENAME_LANG[path.name]
    return EXT_LANG.get(path.suffix.lower())


@dataclass
class Chunk:
    path: str
    language: str
    start_line: int
    end_line: int
    kind: str          # "function" | "class" | "module" | "doc" | "block"
    symbol: str        # e.g. "MyClass.method" or "README"
    text: str


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _py_chunks(rel: str, text: str) -> list[Chunk]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _window_chunks(rel, "python", text, kind="block")

    lines = text.splitlines()
    out: list[Chunk] = []
    maxl = get_settings().chunk_max_lines

    def emit(node, kind: str, symbol: str):
        start = node.lineno
        end = getattr(node, "end_lineno", start) or start
        body = "\n".join(lines[start - 1:end])
        if end - start + 1 <= maxl:
            out.append(Chunk(rel, "python", start, end, kind, symbol, body))
        else:
            # split long defs/classes into windows preserving header
            for i in range(start, end, maxl):
                j = min(i + maxl - 1, end)
                out.append(Chunk(rel, "python", i, j, kind, f"{symbol}#part", "\n".join(lines[i - 1:j])))

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            emit(node, "class", node.name)
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    emit(sub, "function", f"{node.name}.{sub.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            emit(node, "function", node.name)

    if not out:
        return _window_chunks(rel, "python", text, kind="module")
    return out


def _window_chunks(rel: str, lang: str, text: str, kind: str = "block") -> list[Chunk]:
    s = get_settings()
    lines = text.splitlines()
    if not lines:
        return []
    out: list[Chunk] = []
    step = s.chunk_max_lines - 20  # 20-line overlap
    for start in range(0, len(lines), step):
        end = min(start + s.chunk_max_lines, len(lines))
        body = "\n".join(lines[start:end])
        if len(lines[start:end]) < s.chunk_min_lines and out:
            # merge tiny tail into previous chunk
            prev = out[-1]
            prev.end_line = end
            prev.text = prev.text + "\n" + body
        else:
            out.append(Chunk(rel, lang, start + 1, end, kind, rel, body))
    return out


def chunk_file(root: Path, path: Path, language: str) -> list[Chunk]:
    rel = str(path.relative_to(root)).replace("\\", "/")
    text = _read(path)
    if not text:
        return []
    if language == "python":
        return _py_chunks(rel, text)
    if language in ("markdown", "text"):
        return _window_chunks(rel, language, text, kind="doc")
    # generic: tree-sitter optional, fall back to line windows
    return _window_chunks(rel, language, text, kind="block")