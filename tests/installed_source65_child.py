"""Installed public API over the Ruby source65 quantity packet, then warmed facade calls.

After one warm-up pass, an audit hook forbids file, process, network and library-load
events while the same public calls run again. Runs in its own interpreter because
audit hooks cannot be removed.
"""
from hashlib import sha256
import json
from pathlib import Path
import sys

import plurimath
from plurimath import FacadeError

FORBIDDEN = ("open", "os.putenv", "os.unsetenv", "os.system", "subprocess.Popen",
             "socket.connect", "socket.bind", "ctypes.dlopen")


def tagged(request):
    return any(isinstance(binding.get("value"), dict) for binding in request["bindings"].values())


def quantity_pass(cases, strict):
    counts = {"accepted": 0, "refusals": 0, "tagged": 0, "legacy": 0, "float_bits": 0, "strict38": 0}
    for case in cases:
        request = json.loads(case["request_json"])
        before = json.dumps(request, sort_keys=True)
        wire = plurimath.evaluate_json(case["request_json"])
        response = plurimath.evaluate(request)
        assert response == json.loads(wire), case["id"]
        assert json.dumps(request, sort_keys=True) == before, case["id"]
        if "expected" in case:
            assert response == case["expected"], (case["id"], response)
            counts["accepted"] += 1
            for name in ("value", "converted"):
                snapshot = response["result"][name]
                if snapshot is None:
                    continue
                numeric = snapshot.get("numeric_value")
                if not tagged(request):
                    assert numeric is None, (case["id"], "legacy String gained numeric_value")
                elif numeric and numeric["kind"] == "float":
                    assert numeric["bits"] == case["expected"]["result"][name]["numeric_value"]["bits"]
                    counts["float_bits"] += 1
            counts["tagged" if tagged(request) else "legacy"] += 1
        else:
            source_class = case["source_error"]["class"].rsplit("::", 1)[-1]
            assert response["ok"] is False and response["error"]["code"] == source_class, (case["id"], response)
            counts["refusals"] += 1
        counts["strict38"] += case["id"] in strict
    return counts


def facade_pass():
    calls = 0
    for text, source_format in (("x^2 + 1", "asciimath"), ("\\frac{a}{b}", "latex")):
        formula = plurimath.parse(text, source_format)
        for output in ("asciimath", "latex", "mathml", "omml", "unicodemath"):
            assert isinstance(formula.write(output), str)
            calls += 1
    try:
        plurimath.parse("\\frac{", "latex")
    except FacadeError as refusal:
        assert refusal.code == "PARSE_ERROR"
    else:
        raise AssertionError("malformed LaTeX was accepted")
    return calls + 1


def main():
    folder = Path(__file__).parent / "fixtures" / "typed-quantity-source65"
    receipt = json.loads((folder / "source.json").read_bytes())
    payload = (folder / "cases.json").read_bytes()
    assert sha256(payload).hexdigest() == receipt["cases_sha256"]
    cases = json.loads(payload)["cases"]
    strict = set(receipt["strict38_ids"])
    assert len(cases) == 65 and len(strict) == 38 and strict <= {case["id"] for case in cases}
    plurimath.initialize()
    plurimath.initialize_facade()
    cold = quantity_pass(cases, strict)
    facade_calls = facade_pass()
    events = []

    def audit(event, args):
        if event in FORBIDDEN:
            events.append(event)
            raise RuntimeError("warmed public call attempted " + event)

    sys.addaudithook(audit)
    warm = quantity_pass(cases, strict)
    warm_facade_calls = facade_pass()
    assert cold == warm and facade_calls == warm_facade_calls
    print(json.dumps({"cases": len(cases), "counts": warm, "facade_calls": warm_facade_calls,
                      "warmed_forbidden_events": events}))


if __name__ == "__main__":
    main()
