"""Input and notice provenance checks only; no native runtime is mocked or claimed."""
import copy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from public_native import validate, relative, notice_inventory


class PublicNativeInputTests(unittest.TestCase):
    def recipe(self, root):
        sources = []
        components = {}
        for index, name in enumerate(("numeric", "facade")):
            revision = str(index + 1) * 40
            lock = str(index + 3) * 64
            sources.append({"id": name, "repository": "https://github.com/example/" + name,
                            "revision": revision, "tree": "a" * 40, "path": "sources/" + name})
            template = root / (name + ".json")
            template.write_text(json.dumps({"native_source_commit": revision, "cargo_lock_sha256": lock}))
            components[name] = {"source": name, "manifest_path": "Cargo.toml", "lock_path": "Cargo.lock",
                                "cargo_lock_sha256": lock, "features": [],
                                "receipt_template": template.name,
                                "receipt_template_sha256": sha256(template.read_bytes()).hexdigest()}
        return {"schema": "plurimath.python-public-native-build/1", "rust_toolchain": "1.95.0",
                "sources": sources, "components": components, "allowed_git_sources": []}

    def test_complete_exact_input_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(set(validate(self.recipe(root), root)), {"numeric", "facade"})

    def test_reject_mutable_credentials_paths_and_partial_component_sets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            good = self.recipe(root)
            for field, value in (("revision", "main"), ("tree", "short"),
                                 ("path", "../outside"), ("path", "C:/outside"),
                                 ("repository", "https://secret@github.com/example/repo")):
                candidate = copy.deepcopy(good)
                candidate["sources"][0][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    validate(candidate, root)
            candidate = copy.deepcopy(good)
            del candidate["components"]["numeric"]
            with self.assertRaises(ValueError):
                validate(candidate, root)
            candidate = copy.deepcopy(good)
            candidate["sources"][1]["path"] = candidate["sources"][0]["path"] + "/nested"
            with self.assertRaises(ValueError):
                validate(candidate, root)

    def test_source_receipt_and_lock_cannot_be_relabelled(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            good = self.recipe(root)
            candidate = copy.deepcopy(good)
            candidate["components"]["numeric"]["cargo_lock_sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "lock differs"):
                validate(candidate, root)
            (root / "facade.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "template digest"):
                validate(good, root)

    def test_actual_notices_and_spdx_only_preserve_source_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            source.mkdir()
            crate = source / "crate"
            crate.mkdir()
            (crate / "Cargo.toml").write_text('[package]\nname="bare"\n')
            metadata = {"packages": [{"name": "bare", "version": "1", "source": None,
                         "manifest_path": str(crate / "Cargo.toml"), "license": "BSD-2-Clause"}]}
            destination = root / "notices"
            destination.mkdir()
            notice_inventory(metadata, [(source, "a" * 40)], [], destination)
            entry = json.loads((destination / "manifest.json").read_text())[0]
            self.assertTrue(entry["spdx_only"])
            self.assertEqual(entry["source_revision"], "a" * 40)
            self.assertIn("bare-1/SOURCE-LICENSE.json", entry["notices"])
            metadata["packages"][0]["manifest_path"] = str(root / "unadmitted/Cargo.toml")
            with self.assertRaisesRegex(RuntimeError, "Unadmitted path"):
                notice_inventory(metadata, [(source, "a" * 40)], [], root / "unused")

    def test_admission_cli_can_validate_without_enabling_or_building(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            recipe = self.recipe(root)
            receipts = root / "ci/native-receipts"
            receipts.mkdir(parents=True)
            for name, component in recipe["components"].items():
                original = root / component["receipt_template"]
                target = receipts / (name + ".json")
                target.write_bytes(original.read_bytes())
                component["receipt_template"] = target.relative_to(root).as_posix()
            (root / "ci/native-build.json").write_text(json.dumps(recipe))
            script = Path(__file__).resolve().parents[1] / "enable-native-ci.py"
            result = subprocess.run([sys.executable, str(script), "--from-directory", str(root),
                                     "--check-only"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "valid_admission_inputs")
            self.assertFalse(json.loads(result.stdout)["native_executed"])
