"""Path guard: every file the heal agent's tools read goes through safe_read.

The agent may read only its failure bundle and its sandbox script. Ground truth and judges
(oracle, injector + catalog, policy, logs, results) are denied even if a path points there.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DENIED = [REPO / p for p in ("oracle", "failures", "policy.py", "logs", "results")]


def _under(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def check(path: Path, allowed_roots: list[Path]) -> Path:
    """Resolve symlinks and `..`, then refuse denied paths and anything outside allowed_roots."""
    real = Path(path).resolve()
    if any(_under(real, d) for d in DENIED):
        raise PermissionError(f"agent may not read {path}")
    if not any(_under(real, Path(r).resolve()) for r in allowed_roots):
        raise PermissionError(f"{path} is outside the agent's bundle and sandbox")
    return real


def safe_read(path: Path, allowed_roots: list[Path], binary: bool = False):
    real = check(path, allowed_roots)
    return real.read_bytes() if binary else real.read_text()
