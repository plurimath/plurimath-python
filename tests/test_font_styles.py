import json
from pathlib import Path
import unittest

import plurimath


class InstalledFontStyles(unittest.TestCase):
    def test_source_writer_outputs_and_refusal_classes(self):
        reference = json.loads(Path(__file__).with_name("font-styles-reference.json").read_bytes())
        kernel = plurimath.initialize_facade()
        outputs = refusals = 0
        self.assertEqual(len(reference["rows"]), 230)
        for row in reference["rows"]:
            formula = kernel.from_model(row["model"])
            for output_format, expected in row["writers"].items():
                with self.subTest(case=row["id"], output_format=output_format):
                    if "output" in expected:
                        self.assertEqual(formula.write(output_format), expected["output"])
                        outputs += 1
                    else:
                        with self.assertRaises(plurimath.FacadeError) as refusal:
                            formula.write(output_format)
                        self.assertEqual(refusal.exception.details.get("source_class"),
                                         expected["error"]["class"])
                        refusals += 1
        self.assertEqual((outputs, refusals), (1127, 253))
        self.assertEqual(kernel.parse("x", "asciimath").to_latex(), "x")
