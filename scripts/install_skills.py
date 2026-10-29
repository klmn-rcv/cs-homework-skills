#!/usr/bin/env python3
"""Review or apply a local eight-Skill copy; never modify host configuration."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

NAMES = ("cs-homework", "cs-homework-plan", "cs-homework-code", "cs-homework-run",
         "cs-homework-analyze", "cs-homework-report", "cs-homework-report-review", "cs-homework-check")
LEGACY_NAMES = tuple(name.replace("cs-homework", "coursework", 1) for name in NAMES)
MANIFEST = ".coursework-install.json"
PROFILE = "cs-homework/references/local-tools.json"
LEGACY_PROFILE = "coursework/references/local-tools.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def literal(path):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise ValueError(f"Preserve linked install paths: {path}")
    return path


def owned_path(root, name):
    relative = Path(name)
    if relative.is_absolute() or not relative.parts or relative.parts[0] not in (*NAMES, *LEGACY_NAMES) or any(
            part in {"..", ".git"} for part in relative.parts):
        raise ValueError(f"Invalid owned package path: {name}")
    path = literal(root / relative)
    if not path.is_relative_to(root):
        raise ValueError(f"Owned path escaped destination: {name}")
    return path


def write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def install(source, destination, *, profile=None, apply=False):
    source, destination = literal(source), literal(destination)
    if source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError("Package source and personal destination must be separate directories")
    contents = {}
    for name in NAMES:
        directory = literal(source / name)
        if not (directory / "SKILL.md").is_file():
            raise ValueError(f"Missing source Skill: {name}")
        for path in sorted(directory.rglob("*")):
            literal(path)
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                relative = path.relative_to(source).as_posix()
                if relative == PROFILE:
                    raise ValueError("Keep the personal tool overlay outside portable source")
                contents[relative] = path.read_bytes()
    source_files = {name: digest(data) for name, data in contents.items()}
    package_hash = digest(json.dumps(source_files, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    manifest_path = literal(destination / MANIFEST)
    old = {}
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if old.get("kind") != "coursework-personal-install" or old.get("schema_version") != 1:
            raise ValueError("Preserve the unrecognized existing installation manifest")
    previous = {**old.get("source_files", {}), **old.get("personal_files", {})}
    for name, expected in previous.items():
        path = owned_path(destination, name)
        if not path.is_file() or digest(path.read_bytes()) != expected:
            raise ValueError(f"Preserved personal edit or missing owned file: {name}")
    if not old:
        for name in NAMES:
            if (destination / name).exists():
                raise ValueError(f"Preserve existing unowned Skill directory: {destination / name}")
    personal_files = dict(old.get("personal_files", {}))
    if LEGACY_PROFILE in personal_files:
        if PROFILE in personal_files:
            raise ValueError("Preserve conflicting managed tool hints; review them before migration")
        contents[PROFILE] = owned_path(destination, LEGACY_PROFILE).read_bytes()
        personal_files[PROFILE] = personal_files.pop(LEGACY_PROFILE)
    if profile is not None:
        data = Path(profile).read_bytes()
        hints = json.loads(data.decode("utf-8-sig"))
        if not isinstance(hints, dict) or hints.get("kind") != "coursework-local-tool-hints":
            raise ValueError("Local tools must be an explicit coursework-local-tool-hints JSON object")
        contents[PROFILE] = data
        personal_files[PROFILE] = digest(data)
    expected_files = {**source_files, **personal_files}
    changes = []
    for name, expected in expected_files.items():
        path = owned_path(destination, name)
        if path.exists() and name not in previous:
            raise ValueError(f"Preserve existing unowned file: {name}")
        if previous.get(name) != expected:
            changes.append({"action": "copy", "path": name, "sha256": expected})
    for name in previous.keys() - expected_files.keys():
        changes.append({"action": "remove_owned", "path": name, "sha256": previous[name]})
    manifest = {"kind": "coursework-personal-install", "schema_version": 1,
                "source_package_sha256": package_hash, "source_files": source_files,
                "personal_files": personal_files}
    result = {"applied": apply, "destination": str(destination), "manifest": str(manifest_path),
              "source_skills": list(NAMES), "source_package_sha256": package_hash,
              "changes": changes, "personal_files": personal_files}
    if apply:
        for change in changes:
            path = owned_path(destination, change["path"])
            if change["action"] == "copy":
                write_bytes(path, contents[change["path"]])
            else:
                path.unlink()
        encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if not manifest_path.exists() or manifest_path.read_bytes() != encoded:
            write_bytes(manifest_path, encoded)
    return result


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "skills")
    parser.add_argument("--dest", type=Path, required=True, help="Explicit personal Skill discovery directory")
    parser.add_argument("--local-tools", type=Path, help="Optional personal tool hints; copied only to installed cs-homework")
    parser.add_argument("--apply", action="store_true", help="Apply the reviewed copy/update; default is read-only")
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.source, args.dest, profile=args.local_tools, apply=args.apply),
                         ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
