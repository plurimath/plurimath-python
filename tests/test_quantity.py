from hashlib import sha256
import json
from pathlib import Path
import unittest

import plurimath


SCHEMA = "plurimath.evaluate.quantity/1"


def number(text):
    return {"type": "number", "text": text}


def variable(name):
    return {"type": "variable", "name": name}


def binary(operator, left, right):
    return {"type": "binary", "operator": operator, "left": left, "right": right}


def evaluate(ast, bindings=None, **options):
    return plurimath.evaluate({"schema": SCHEMA, "ast": ast, "bindings": bindings or {}, **options})


class InstalledQuantity(unittest.TestCase):
    def test_serialized_caller_register_wires(self):
        fixture = json.loads(Path(__file__).with_name("quantity-register-v1.json").read_bytes())
        self.assertEqual(len(fixture["cases"]), 35)
        # Source profiles record UnitsDB data and corrected scale semantics; each
        # pins the superseded legacy expectation byte for byte.
        folder = Path(__file__).parent / "fixtures" / "source-profile-numeric"
        receipt = json.loads((folder / "source.json").read_bytes())
        superseded = {}
        for name, digest in receipt["files"].items():
            payload = (folder / name).read_bytes()
            self.assertEqual(sha256(payload).hexdigest(), digest)
            for row in json.loads(payload)["superseded_legacy_rows"]:
                superseded[row["id"]] = row
        self.assertEqual(len(superseded), 3)
        applied = set()
        for row in fixture["cases"]:
            with self.subTest(case=row["id"]):
                expected = row["expected_wire"]
                source = superseded.get(row["id"])
                if source is not None:
                    self.assertEqual(source["legacy_expected_wire"], row["expected_wire"])
                    self.assertEqual(source["request_json"], row["request_json"])
                    expected = source["expected_wire"]
                    applied.add(row["id"])
                self.assertEqual(plurimath.evaluate_json(row["request_json"]), expected)
        self.assertEqual(applied, set(superseded))

    def test_frozen_f40_voltage_current_conversion(self):
        fixture = json.loads(Path(__file__).with_name("quantity-f40.json").read_bytes())
        request = fixture["request"]
        expected = fixture["expected"]
        response = plurimath.evaluate(request)
        self.assertEqual(response, json.loads(plurimath.evaluate_json(json.dumps(request))))
        self.assertEqual(response["schema"], SCHEMA)
        self.assertEqual(response["engine"], "plurimath.quantity/1")
        self.assertEqual(response["grammar"], "plurimath.numeric-ast/1")
        self.assertIs(response["ok"], True)
        result = response["result"]
        self.assertEqual(result["accuracy"], expected["outcome"]["accuracy"])
        dimensions = {key: str(value) for key, value in expected["outcome"]["dimensions"].items()}
        for name, reference in (("value", expected["outcome"]), ("converted", expected["converted"])):
            numerator, denominator = reference["magnitude"]["rational"]
            self.assertEqual(result[name]["magnitude"], numerator if denominator == "1" else f"{numerator}/{denominator}")
            self.assertEqual(result[name]["dimensions"], dimensions)

    def test_typed_quantity_refusals_and_reuse(self):
        syntax = evaluate(variable("x"), {"x": {"value": "1", "unit": "m^^2"}})
        self.assertIs(syntax["ok"], False)
        self.assertEqual(syntax["error"]["code"], "UnitSyntaxError")
        self.assertIsInstance(syntax["error"]["parser"]["byte_offset"], int)
        zero = evaluate(binary("/", number("1"), number("0")))
        self.assertEqual(zero["error"]["code"], "DivisionByZeroError")
        self.assertEqual(zero["error"]["class"], "indeterminate")
        temperature = evaluate(
            binary("-", variable("a"), variable("b")),
            {"a": {"value": "20", "unit": "degC"}, "b": {"value": "15", "unit": "degC"}},
            convert_to="K",
        )
        self.assertIs(temperature["ok"], True)
        self.assertEqual(temperature["result"]["converted"]["magnitude"], "5")
        self.assertEqual(temperature["result"]["converted"]["scale"], "difference")
