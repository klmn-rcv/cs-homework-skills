"""Task-owned checkpoints that keep the user's index and dirty files intact."""
from dataclasses import dataclass
from pathlib import Path
import subprocess


def git(directory, *args, check=True):
    result = subprocess.run(["git", "-C", str(directory), *args], capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result


@dataclass(frozen=True)
class TaskSnapshot:
    root: Path
    dirty_paths: frozenset


def begin_task(workspace, *, independent=False):
    """Call before task edits. New assignments get a local repository."""
    workspace = Path(workspace).resolve()
    root_result = git(workspace, "rev-parse", "--show-toplevel", check=False)
    if independent or root_result.returncode:
        git(workspace, "init", "-q")
        root = workspace
    else:
        root = Path(root_result.stdout.decode("utf-8").strip()).resolve()
    dirty = set()
    for args in [("diff", "--name-only", "--no-renames", "-z"),
                 ("diff", "--cached", "--name-only", "--no-renames", "-z"),
                 ("ls-files", "--others", "--exclude-standard", "-z")]:
        output = git(root, *args).stdout.decode("utf-8")
        dirty.update(path for path in output.split("\0") if path)
    return TaskSnapshot(root, frozenset(dirty))


def checkpoint(workspace, paths, snapshot, message):
    """Commit exact task paths only. Never include paths dirty before begin_task."""
    workspace = Path(workspace).resolve()
    accepted, skipped = [], []
    for name in paths:
        path = workspace / name
        if path.is_dir() or path.resolve() != path:
            raise ValueError("Checkpoint paths must be exact file paths without filesystem links")
        path = path.resolve()
        if not path.is_relative_to(workspace) or ".git" in path.relative_to(workspace).parts:
            raise ValueError("Checkpoint paths must remain inside the assignment and outside .git")
        relative = path.relative_to(snapshot.root).as_posix()
        if relative in snapshot.dirty_paths:
            skipped.append(relative)
        else:
            accepted.append(relative)
    if not accepted:
        return {"commit": None, "skipped_preexisting": skipped}
    literal = [":(literal)" + path for path in accepted]
    # --only uses a temporary commit index; unrelated staging is preserved by Git.
    identity = []
    for setting, fallback in [("user.name", "Coursework"), ("user.email", "coursework@local.invalid")]:
        if git(snapshot.root, "config", "--get", setting, check=False).returncode:
            identity.extend(["-c", setting + "=" + fallback])
    git(snapshot.root, "add", "--intent-to-add", "--", *literal)
    git(snapshot.root, *identity, "commit", "--only", "-m", message, "--", *literal)
    commit = git(snapshot.root, "rev-parse", "HEAD").stdout.decode("ascii").strip()
    return {"commit": commit, "skipped_preexisting": skipped}
