"""Local install/update through the public CLI, preserving personal files."""
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / "scripts/install_skills.py"
NAMES = ["cs-homework", "cs-homework-plan", "cs-homework-code", "cs-homework-run",
         "cs-homework-analyze", "cs-homework-report", "cs-homework-report-review", "cs-homework-check"]


class PersonalInstallation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "package"
        self.dest = self.root / "personal-skills"
        for name in NAMES:
            folder = self.source / name
            folder.mkdir(parents=True)
            (folder / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: Test fixture.\n---\n\n# Fixture\n", encoding="utf-8")

    def install(self, *args, ok=True):
        result = subprocess.run([sys.executable, "-B", str(INSTALLER), "--source", str(self.source),
                                 "--dest", str(self.dest), *args], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0 if ok else 2, result.stderr or result.stdout)
        return json.loads(result.stdout if ok else result.stderr)

    def test_reviewable_copy_installs_eight_siblings_and_personal_overlay_without_changing_source_or_config(self):
        self.dest.mkdir()
        (self.dest / "unrelated-skill").mkdir()
        (self.dest / "unrelated-skill/SKILL.md").write_text("personal", encoding="utf-8")
        config = self.root / "config.toml"
        config.write_text("# student's settings\n", encoding="utf-8")
        hints = self.root / "hints.json"
        hints.write_text('{"kind":"coursework-local-tool-hints","python":{"executable":"local/python"}}', encoding="utf-8")
        proposal = self.install("--local-tools", str(hints))
        self.assertFalse((self.dest / "cs-homework").exists())
        self.assertEqual(len(proposal["source_skills"]), 8)
        installed = self.install("--local-tools", str(hints), "--apply")
        for name in NAMES:
            self.assertEqual((self.dest / name / "SKILL.md").read_bytes(),
                             (self.source / name / "SKILL.md").read_bytes())
        self.assertEqual((self.dest / "cs-homework/references/local-tools.json").read_bytes(), hints.read_bytes())
        self.assertFalse((self.source / "cs-homework/references/local-tools.json").exists())
        self.assertEqual(config.read_text(), "# student's settings\n")
        self.assertEqual((self.dest / "unrelated-skill/SKILL.md").read_text(), "personal")
        manifest = json.loads(Path(installed["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_package_sha256"], proposal["source_package_sha256"])
        self.assertEqual(len(manifest["source_files"]), 8)
        self.assertIn("cs-homework/references/local-tools.json", manifest["personal_files"])
        self.assertEqual(self.install("--apply")["changes"], [])

    def test_owned_updates_preserve_unknown_files_and_personal_edits_reject_the_entire_update(self):
        obsolete = self.source / "cs-homework/obsolete.txt"
        obsolete.write_text("owned old file", encoding="utf-8")
        self.install("--apply")
        unknown = self.dest / "cs-homework/student-notes.txt"
        unknown.write_text("keep my note", encoding="utf-8")
        obsolete.unlink()
        new_source = self.source / "cs-homework/new.txt"
        new_source.write_text("new owned file", encoding="utf-8")
        old_skill = (self.dest / "cs-homework-code/SKILL.md").read_bytes()
        (self.source / "cs-homework-code/SKILL.md").write_bytes(old_skill + b"\nNew version.\n")
        personal = self.dest / "cs-homework-report/SKILL.md"
        personal.write_text("personal edited instructions", encoding="utf-8")
        failure = self.install("--apply", ok=False)
        self.assertIn("Preserved personal edit", failure["error"])
        self.assertEqual((self.dest / "cs-homework-code/SKILL.md").read_bytes(), old_skill)
        self.assertTrue((self.dest / "cs-homework/obsolete.txt").exists())
        self.assertFalse((self.dest / "cs-homework/new.txt").exists())
        self.assertEqual(personal.read_text(), "personal edited instructions")
        personal.write_bytes((self.source / "cs-homework-report/SKILL.md").read_bytes())
        self.install("--apply")
        self.assertFalse((self.dest / "cs-homework/obsolete.txt").exists())
        self.assertEqual((self.dest / "cs-homework/new.txt").read_text(), "new owned file")
        self.assertEqual(unknown.read_text(), "keep my note")

    def test_unowned_existing_skill_folder_is_preserved_before_any_copy(self):
        existing = self.dest / "cs-homework-code"
        existing.mkdir(parents=True)
        (existing / "SKILL.md").write_text("unmanaged student Skill", encoding="utf-8")
        failure = self.install("--apply", ok=False)
        self.assertIn("unowned Skill directory", failure["error"])
        self.assertFalse((self.dest / "cs-homework").exists())
        self.assertEqual((existing / "SKILL.md").read_text(), "unmanaged student Skill")

    def test_legacy_names_migrate_without_losing_personal_files_or_overwriting_edits(self):
        legacy_files = {}
        for name in NAMES:
            legacy = name.replace("cs-homework", "coursework", 1)
            relative = f"{legacy}/SKILL.md"
            path = self.dest / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"---\nname: {legacy}\ndescription: Legacy fixture.\n---\n", encoding="utf-8")
            legacy_files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        hints = self.dest / "coursework/references/local-tools.json"
        hints.parent.mkdir(parents=True)
        hints.write_text('{"kind":"coursework-local-tool-hints","python":{"executable":"personal/python"}}', encoding="utf-8")
        hints_bytes = hints.read_bytes()
        note = self.dest / "coursework/personal-note.txt"
        note.write_text("keep my note", encoding="utf-8")
        manifest = self.dest / ".coursework-install.json"
        manifest.write_text(json.dumps({"kind": "coursework-personal-install", "schema_version": 1,
                                       "source_files": legacy_files,
                                       "personal_files": {"coursework/references/local-tools.json": hashlib.sha256(hints_bytes).hexdigest()}}), encoding="utf-8")
        before_manifest = manifest.read_bytes()
        proposal = self.install()
        self.assertEqual(proposal["source_skills"], NAMES)
        self.assertFalse((self.dest / "cs-homework").exists())
        self.assertEqual(manifest.read_bytes(), before_manifest)

        edited = self.dest / "coursework-code/SKILL.md"
        original = edited.read_bytes()
        edited.write_bytes(original + b"Personal edit.\n")
        failure = self.install("--apply", ok=False)
        self.assertIn("Preserved personal edit", failure["error"])
        self.assertFalse((self.dest / "cs-homework").exists())
        self.assertEqual(manifest.read_bytes(), before_manifest)
        edited.write_bytes(original)

        self.install("--apply")
        for name in NAMES:
            self.assertEqual((self.dest / name / "SKILL.md").read_bytes(),
                             (self.source / name / "SKILL.md").read_bytes())
            legacy = name.replace("cs-homework", "coursework", 1)
            self.assertFalse((self.dest / legacy / "SKILL.md").exists())
        self.assertEqual((self.dest / "cs-homework/references/local-tools.json").read_bytes(), hints_bytes)
        self.assertFalse(hints.exists())
        self.assertEqual(note.read_text(), "keep my note")
        self.assertEqual(self.install("--apply")["changes"], [])


if __name__ == "__main__":
    unittest.main()
