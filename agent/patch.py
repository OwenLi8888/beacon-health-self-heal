"""Apply a model-written unified diff by content, not line numbers (model hunk headers are often off)."""
import difflib


class PatchError(Exception):
    """The diff is malformed, or a hunk's context does not match the script exactly once."""


def _hunks(diff: str) -> list[tuple[list[str], list[str]]]:
    hunks, cur = [], None
    for line in diff.splitlines():
        if line.startswith(("---", "+++")) and cur is None:
            continue
        if line.startswith("@@"):
            cur = ([], [])
            hunks.append(cur)
        elif cur is None:
            continue  # prose before the first hunk
        elif line.startswith("\\"):
            continue  # "\ No newline at end of file"
        elif line.startswith("-"):
            cur[0].append(line[1:])
        elif line.startswith("+"):
            cur[1].append(line[1:])
        else:  # context; a blank context line often loses its leading space
            text = line[1:] if line.startswith(" ") else line
            cur[0].append(text)
            cur[1].append(text)
    if not hunks or not any(old != new for old, new in hunks):
        raise PatchError("diff has no hunks that change anything")
    return hunks


def apply(source: str, diff: str) -> str:
    lines = source.splitlines()
    for old, new in _hunks(diff):
        if not old:
            raise PatchError("hunk has no context or removed lines to anchor it")
        key = [l.rstrip() for l in old]
        at = [i for i in range(len(lines) - len(old) + 1)
              if [l.rstrip() for l in lines[i:i + len(old)]] == key]
        if len(at) != 1:
            raise PatchError(f"hunk starting {old[0].strip()!r} matches the script {len(at)} times, need exactly 1")
        lines[at[0]:at[0] + len(old)] = new
    return "\n".join(lines) + ("\n" if source.endswith("\n") else "")


def unified(original: str, patched: str, name: str) -> str:
    return "".join(difflib.unified_diff(original.splitlines(True), patched.splitlines(True),
                                        f"a/{name}", f"b/{name}"))


def changed_lines(original: str, patched: str) -> tuple[int, list[int]]:
    """(added + removed line count, 1-based original line numbers touched)."""
    sm = difflib.SequenceMatcher(None, original.splitlines(), patched.splitlines(), autojunk=False)
    count, touched = 0, []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        count += (i2 - i1) + (j2 - j1)
        touched += list(range(i1 + 1, i2 + 1)) or [max(i1, 1)]  # pure insert: the line it follows
    return count, touched
