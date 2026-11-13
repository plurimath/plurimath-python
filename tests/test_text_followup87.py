"""Residual LaTeX/UnicodeMath text shapes against frozen Ruby 0a1df68 Math.parse outcomes."""
from hashlib import sha256
import json
from pathlib import Path
import unittest

from plurimath import FacadeError, parse

FOLDER = Path(__file__).parent / "fixtures" / "text-closure-followup-87"


class InstalledTextFollowup87(unittest.TestCase):
    def test_residual_text_shapes_match_ruby_source_outcomes(self):
        receipt = json.loads((FOLDER / "source.json").read_bytes())
        payload = (FOLDER / "residual-shapes.json").read_bytes()
        self.assertEqual(sha256(payload).hexdigest(), receipt["sha256"])
        rows = json.loads(payload)["rows"]
        self.assertEqual(len(rows), 87)
        outcomes = {}
        for row in rows:
            source = row["input"]
            outcomes[row["outcome"]] = outcomes.get(row["outcome"], 0) + 1
            with self.subTest(format=source["format"], text=source["text"]):
                if row["outcome"] == "model":
                    self.assertEqual(parse(source["text"], source["format"]).model, row["parsed_model"])
                    continue
                with self.assertRaises(FacadeError) as refusal:
                    parse(source["text"], source["format"])
                if row["outcome"] == "error":
                    self.assertEqual(refusal.exception.details.get("source_class"),
                                     row["parse_error"]["class"])
        self.assertEqual(outcomes, {"model": 67, "unbuilt": 11, "error": 9})


if __name__ == "__main__":
    unittest.main()
