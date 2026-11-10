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
