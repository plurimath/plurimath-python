# Serialized quantity evaluation

`plurimath.evaluate(request)` accepts a JSON-compatible Python mapping and returns
the native response mapping. `evaluate_json(request_text)` returns the native JSON
response string. Python forwards value tags, accuracy and result fields unchanged;
it performs no unit parsing, numeric conversion or arithmetic.

```python
import plurimath

response = plurimath.evaluate({
    "schema": "plurimath.evaluate.quantity/1",
    "ast": {"type": "variable", "name": "x"},
    "bindings": {"x": {"value": {"decimal": "2.5"}, "unit": "m"}},
})
if response["ok"]:
    quantity = response["result"]["value"]
    number = quantity["numeric_value"]
    accuracy = response["result"]["accuracy"]
else:
    error = response["error"]
```

The new native request contract adds these explicit binding values:

| Python value | Native source value |
| --- | --- |
| `"2.5"` | Exact rational, preserving the existing String API |
| `{"rational": ["5", "2"]}` | Exact rational |
| `{"decimal": "2.5"}` | Decimal with the source precision policy |
| `{"binary64": "4004000000000000"}` | IEEE 754 binary64 Float, hexadecimal big-endian bits |

Keep decimal text and binary64 bits as strings. Python `float`, `Decimal` and
`Fraction` instances are not implicit replacements for these tags. Supply the
explicit JSON value to retain the intended source type. The engine validates
malformed tags and returns its typed error envelope.

When any binding uses an explicit value tag, including an unused binding, the
native result adds `numeric_value` to each quantity snapshot. Its established
numeric wire is a rational (`kind`, `numerator`, `denominator`), decimal (`kind`,
`value`, `precision`), or float (`kind`, `bits`). A quantity Integer is represented
as a rational. This field describes that snapshot's magnitude in its resolved
terms, rather than `canonical_magnitude`. A converted snapshot, when requested,
also has its own `numeric_value`; source unit conversion rationalizes this value.
The original snapshot can retain a Float or Decimal result. A Decimal value can
have `limited_float` accuracy: value type and accuracy are separate source facts.

Requests containing only legacy String bindings retain their existing response
shape, without the new `numeric_value` field. The engine combines all bound
quantity accuracies, including unused bindings, and the result's own precision.
No Python-side coercion upgrades or normalizes these results.

The pending final native package must qualify the 36 frozen actual Ruby library
cases in `tests/fixtures/typed-quantity-accuracy-v1`. Their informational `ruby_wire`
records the older serialized Ruby entry point, which rejects these additive tags;
the expected typed values come from the Ruby library API. This document records
the new native contract, not a claim that the preserved earlier milestone wheels
already provide it. Final installed Linux and Windows qualification remains pending.

The installed reference check also compares the four actual source-resolved unit
maps (`m`, `m*s`, `m/s`, `km`), their ordered terms and dimensions, and exact
canonical magnitudes using the captured source factors and offsets. Reference
rational projection occurs only in tests. The binding contains no arithmetic.
These maps provide no `dimension_id` oracle; existing UnitsDB/F40 qualification
remains the separate reference for dimension identities.

Two additive source cases separately check Decimal `2.5 m` to `cm`, and Float
negative zero to `cm`. They require the original binary64 sign bit to remain in
`value.numeric_value` while the converted value is the source Rational zero.
These cases do not alter the original 36 source vectors.
