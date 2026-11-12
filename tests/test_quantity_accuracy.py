"""Final-wheel typed quantity check against frozen actual Ruby library values."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class InstalledTypedQuantityAccuracy(unittest.TestCase):
    def test_source36_public_api_and_initialized_no_io(self):
        helper = Path(__file__).with_name("quantity_accuracy_child.py").resolve()
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-I", str(helper)], cwd=directory,
                                    capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["cases"], 36)
        self.assertEqual(report["native_calls"], 72)
        self.assertEqual(report["source_unit_maps"], 4)
        self.assertEqual(report["tagged"] + report["legacy_strings"], 36)
        self.assertEqual(report["initialized_forbidden_events"], [])
