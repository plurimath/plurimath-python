"""Actual installed native quantity API proof; no simulated numeric implementation."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import struct
import sys

import plurimath


def main():
    directory = Path(__file__).parent / "fixtures" / "typed-quantity-accuracy-v1"
    provenance = json.loads((directory / "source.json").read_bytes())
    for filename, expected in provenance["files"].items():
        assert hashlib.sha256((directory / filename).read_bytes()).hexdigest() == expected
    for filename, expected in provenance["supplements"].items():
        assert hashlib.sha256((directory / filename).read_bytes()).hexdigest() == expected
    unit_rows = json.loads((directory / "unit-maps.json").read_bytes())["units"]
    units = {row["unit"]: row for row in unit_rows}
    assert len(units) == 4
    payload = (directory / "vectors.json").read_bytes()
    rows = json.loads(payload)["cases"]
    encoded = (directory / "numeric-values.json").read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == provenance["supplements"]["numeric-values.json"]
    supplement = json.loads(encoded)
    assert supplement["source_vectors_sha256"] == hashlib.sha256(payload).hexdigest()
    numeric = {row["id"]: row["numeric_value"] for row in supplement["cases"]}
    assert len(rows) == len(numeric) == 36
    assert set(numeric) == set(provenance["expected_ids"])
    requests = [(row, json.loads(row["request_json"])) for row in rows]
    converted_rows = json.loads((directory / "converted-cases.json").read_bytes())["cases"]
    assert len(converted_rows) == 2
    converted_requests = [(row, json.loads(row["request_json"])) for row in converted_rows]
    package = plurimath.__file__
    plurimath.initialize()
    forbidden = ("open", "os.putenv", "os.unsetenv", "os.system", "subprocess.Popen",
                 "socket.connect", "socket.bind", "ctypes.dlopen")
    events = []

    def audit(event, args):
        if event in forbidden:
            events.append(event)
            raise RuntimeError("initialized quantity evaluation attempted " + event)

    sys.addaudithook(audit)
    tagged_count = 0
    legacy_count = 0
    for row, request in requests:
        expected = row["expected"]
        before = json.dumps(request, sort_keys=True)
        response = plurimath.evaluate(request)
        wire = plurimath.evaluate_json(row["request_json"])
        assert response == json.loads(wire), row["id"]
        assert json.dumps(request, sort_keys=True) == before, row["id"]
        assert response["ok"] is True, (row["id"], response)
        assert response["schema"] == "plurimath.evaluate.quantity/1", row["id"]
        assert response["engine"] == "plurimath.quantity/1", row["id"]
        assert response["result"]["accuracy"] == expected["accuracy"], row["id"]
        snapshot = response["result"]["value"]
        source_unit = units[expected["unit"]]
        assert snapshot["terms"] == source_unit["terms"], row["id"]
        assert snapshot["dimensions"] == source_unit["dimensions"], row["id"]
        source_value = expected["value"]
        # Reference-only exact rational projection, using source factors/offsets.
        # The production binding forwards native results without any arithmetic.
        if "rational" in source_value:
            magnitude = Fraction(*map(int, source_value["rational"]))
        elif "decimal" in source_value:
            magnitude = Fraction(source_value["decimal"])
        else:
            binary64 = struct.unpack(">d", bytes.fromhex(source_value["binary64"]))[0]
            magnitude = Fraction.from_float(binary64)
        canonical = magnitude * Fraction(source_unit["factor"]) + Fraction(source_unit["offset"])
        canonical_text = str(canonical.numerator) if canonical.denominator == 1 else str(canonical)
        assert snapshot["canonical_magnitude"] == canonical_text, (row["id"], snapshot)
        tagged = any(isinstance(binding["value"], dict)
                     for binding in request["bindings"].values())
        if tagged:
            assert snapshot["numeric_value"] == numeric[row["id"]], (row["id"], snapshot)
            tagged_count += 1
        else:
            assert "numeric_value" not in snapshot, row["id"]
            numerator, denominator = expected["value"]["rational"]
            assert snapshot["magnitude"] == (numerator if denominator == "1"
                                             else numerator + "/" + denominator), row["id"]
            legacy_count += 1
    for row, request in converted_requests:
        before = json.dumps(request, sort_keys=True)
        response = plurimath.evaluate(request)
        assert response == json.loads(plurimath.evaluate_json(row["request_json"])), row["id"]
        assert json.dumps(request, sort_keys=True) == before, row["id"]
        assert response["ok"] is True, (row["id"], response)
        result = response["result"]
        assert result["accuracy"] == row["expected"]["accuracy"], row["id"]
        for name in ("value", "converted"):
            expected = row["expected"][name]
            assert result[name]["numeric_value"] == expected["numeric_value"], (row["id"], name)
            assert result[name]["terms"] == expected["terms"], (row["id"], name)
    assert events == []
    print(json.dumps({"cases": len(rows), "converted_cases": len(converted_rows),
                      "native_calls": (len(rows) + len(converted_rows)) * 2,
                      "tagged": tagged_count, "legacy_strings": legacy_count,
                      "initialized_forbidden_events": events, "package": package,
                      "source_vector_sha256": hashlib.sha256(payload).hexdigest(),
                      "source_unit_maps": len(units)}))


if __name__ == "__main__":
    main()
