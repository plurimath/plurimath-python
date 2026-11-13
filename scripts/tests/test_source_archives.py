import gzip
from hashlib import sha256
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("facade_preparation", Path(__file__).resolve().parents[1] / "prepare-facade.py")
preparation = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = preparation
spec.loader.exec_module(preparation)


class SourceArchives(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-b", "feat/source-provenance-fixture")
        (self.root / "source.txt").write_text("first\n")
        self.git("add", "--", "source.txt")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Fixture source")
        self.head = self.git("rev-parse", "HEAD").strip()
        self.tree = self.git("rev-parse", "HEAD^{tree}").strip()
        self.archive = self.root / "source.tar.gz"
        self.archive.write_bytes(gzip.compress(subprocess.check_output(["git", "archive", "--format=tar", self.head], cwd=self.root), mtime=0))

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True, stderr=subprocess.DEVNULL)

    def validate(self, tree=None):
        return preparation.validate_dependency_archive(self.root, self.head, tree or self.tree,
                                                       self.archive, sha256(self.archive.read_bytes()).hexdigest())

    def test_exact_git_archive_and_tree_are_accepted(self):
        self.validate()
        with self.assertRaisesRegex(RuntimeError, "tree differs"):
            self.validate("0" * 40)

    def test_changed_payload_is_rejected_even_with_matching_declared_checksum(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            member = tarfile.TarInfo("source.txt")
            payload = b"different\n"
            member.size = len(payload)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(payload))
        self.archive.write_bytes(gzip.compress(buffer.getvalue(), mtime=0))
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            self.validate()


if __name__ == "__main__":
    unittest.main()
