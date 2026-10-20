import asyncio
import os
import shutil
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", ".next", ".nuxt",
    "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "target", ".gradle", ".idea", ".vscode", "coverage", ".terraform","env", "site-packages",
    ".tox", ".nox",
}
SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Pipfile.lock", "Cargo.lock", "composer.lock", "Gemfile.lock",
}
SKIP_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".pdf",
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".7z", ".rar",
    ".mp3", ".mp4", ".mov", ".avi", ".wav", ".flac",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".wasm",
    ".pyc", ".pyo", ".class", ".jar", ".lock", ".map",
}


def repo_path(user_id: int, repo_id: int) -> Path:
    return Path(get_settings().repos_root) / str(user_id) / str(repo_id)


async def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode, out, err


async def clone_or_fetch(full_name: str, token: str, user_id: int, repo_id: int) -> Path:
    dest = repo_path(user_id, repo_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://x-access-token:{token}@github.com/{full_name}.git"
    clean = f"https://github.com/{full_name}.git"

    if (dest / ".git").exists():
        rc, _, err = await _run(["git", "remote", "set-url", "origin", url], cwd=dest)
        if rc != 0:
            raise RuntimeError(f"git remote set-url failed: {err.decode(errors='ignore')[:200]}")
        rc, _, err = await _run(["git", "fetch", "--depth", "1", "origin"], cwd=dest)
        if rc != 0:
            raise RuntimeError(f"git fetch failed: {err.decode(errors='ignore')[:200]}")
        await _run(["git", "reset", "--hard", "FETCH_HEAD"], cwd=dest)
        log.info("repo_fetched", full_name=full_name, user_id=user_id, repo_id=repo_id)
    else:
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        rc, _, err = await _run(["git", "clone", "--depth", "1", "--single-branch", url, str(dest)])
        if rc != 0:
            raise RuntimeError(f"git clone failed: {err.decode(errors='ignore')[:200]}")
        log.info("repo_cloned", full_name=full_name, user_id=user_id, repo_id=repo_id)

    # scrub token from on-disk remote
    await _run(["git", "remote", "set-url", "origin", clean], cwd=dest)
    return dest


def is_skipped(path: Path) -> bool:
    if path.name in SKIP_FILES:
        return True
    if path.suffix.lower() in SKIP_EXTS:
        return True
    tail2 = "".join(path.suffixes[-2:]).lower()
    if tail2 in SKIP_EXTS or path.name.endswith(".min.js") or path.name.endswith(".min.css"):
        return True
    return False


def iter_source_files(root: Path):
    from app.rag.chunker import detect_language
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            p = Path(dirpath) / name
            if is_skipped(p):
                continue
            try:
                if p.stat().st_size > get_settings().max_file_bytes:
                    continue
            except OSError:
                continue
            lang = detect_language(p)
            if lang is None:
                continue
            yield p, lang