"""Replay the pinned plurimath-testsuite corpus through the installed package.

The corpus is the one the Ruby gem replays (its submodules/plurimath-testsuite
commit). Each conversion row is checked per target, byte for byte, against the
Ruby producer's output; each rejection row must be refused. Rows that do not
match yet are listed by id, with a reason, in tests/testsuite-expected-fail.json.
The run fails on any unlisted mismatch and on any listed row that now matches,
so the list can only shrink.

Usage:
  python scripts/replay-testsuite.py CORPUS_CHECKOUT [--pin FILE]
      [--expected-fail FILE] [--report FILE] [--write-expected-fail REASON]
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

import yaml

import plurimath
from plurimath.facade import FacadeError

HERE = Path(__file__).resolve().parent.parent


class CorpusLoader(yaml.SafeLoader):
    """SafeLoader that resolves floats the way Ruby's Psych does.

    PyYAML follows YAML 1.1 and reads `1.123_456_789` as a float. Psych, which
    wrote and reads the corpus, allows no underscore after the point, so that
    scalar is the string a writer produced.
    """


CorpusLoader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:float"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
CorpusLoader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(r"^(?:[-+]?(?:[0-9][0-9_]*)?\.[0-9]*(?:[eE][-+][0-9]+)?"
               r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"),
    list("-+0123456789."))
TARGETS = ("asciimath", "latex", "mathml", "unicodemath", "omml", "html")


def git_head(checkout):
    try:
        return subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def check_pin(checkout, pin):
    """The checkout must be the pinned commit, with the pinned provenance bytes."""
    head = git_head(checkout)
    if head is not None and head != pin["commit"]:
        sys.exit(f"testsuite checkout is {head}, pin is {pin['commit']}")
    digest = sha256((checkout / "corpus" / "provenance.yaml").read_bytes()).hexdigest()
    if digest != pin["provenance_sha256"]:
        sys.exit(f"corpus/provenance.yaml sha256 {digest} does not match the pin")


def write_options(call):
    if not call:
        return {}
    args = call["args"]
    if call["method"] == "number_formatter":
        return {"formatterOptions": {"profile": "standard", "locale": args.get("locale"),
                                     "options": args.get("options") or {},
                                     "precision": args.get("precision"),
                                     "stringFormat": args.get("string_format")}}
    if call["method"] == "unitsml":
        return {"unitsml": args}
    raise ValueError(f"unsupported call {call['method']}")


def outcome(fn):
    try:
        return ("output", fn())
    except FacadeError as error:
        return ("refused", error.code, str(error))
    except Exception as error:  # a crash is a mismatch, recorded with its type
        return ("crash", f"{type(error).__name__}: {error}")


def replay(corpus):
    """Yield (row_id, ok, detail) for every target of every case."""
    for path in sorted((corpus / "corpus").glob("*/*.yaml")):
        payload = yaml.load(path.read_bytes(), Loader=CorpusLoader)
        rel = path.relative_to(corpus / "corpus").as_posix()
        rejection = payload["schema"] == "plurimath-corpus/rejections/1"
        targets = payload.get("targets", [])
        for case in payload["cases"]:
            base = f"{rel}#{case['id']}"
            parsed = outcome(lambda: plurimath.parse(case["input"], case["input_format"]))
            if rejection:
                ok = parsed[0] == "refused"
                yield f"{base}@refusal", ok, None if ok else parsed
                continue
            options = write_options(case.get("call"))
            for target in targets:
                expected = case["expected"][target]
                if not isinstance(expected, dict):
                    expected = {"output": expected}
                if parsed[0] != "output":
                    yield f"{base}@{target}", False, parsed
                    continue
                got = outcome(lambda: parsed[1].write(target, **options))
                if "output" in expected:
                    ok = got == ("output", expected["output"])
                else:
                    ok = got[0] == "refused"
                yield f"{base}@{target}", ok, None if ok else got


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--pin", type=Path, default=HERE / "tests" / "testsuite-pin.json")
    parser.add_argument("--expected-fail", type=Path,
                        default=HERE / "tests" / "testsuite-expected-fail.json")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--write-expected-fail", metavar="REASON",
                        help="rewrite the expected-fail list from this run (maintenance only)")
    args = parser.parse_args()

    pin = json.loads(args.pin.read_bytes())
    check_pin(args.corpus, pin)
    rows = list(replay(args.corpus))
    failed = {row_id: detail for row_id, ok, detail in rows if not ok}

    if args.write_expected_fail:
        doc = json.loads(args.expected_fail.read_bytes()) if args.expected_fail.exists() else {}
        old = doc.get("rows", {})
        doc["testsuite_commit"] = pin["commit"]
        doc["rows"] = {row_id: old.get(row_id, args.write_expected_fail) for row_id in sorted(failed)}
        args.expected_fail.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    listed = json.loads(args.expected_fail.read_bytes())
    if listed["testsuite_commit"] != pin["commit"]:
        sys.exit("expected-fail list was written for another testsuite commit")
    listed = listed["rows"]
    unexpected = sorted(set(failed) - set(listed))
    stale = sorted(set(listed) - set(failed))
    unknown = sorted(set(listed) - {row_id for row_id, _, _ in rows})

    summary = {"testsuite_commit": pin["commit"], "rows": len(rows),
               "passed": len(rows) - len(failed), "expected_fail": len(set(failed) & set(listed)),
               "unexpected_fail": unexpected, "now_passing": stale, "unknown_ids": unknown}
    if args.report:
        detail = {row_id: failed[row_id] for row_id in sorted(failed)}
        args.report.write_text(json.dumps({**summary, "failures": detail}, indent=1,
                                          ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: (v if not isinstance(v, list) else v[:20]) for k, v in summary.items()},
                     ensure_ascii=False))
    for row_id in unexpected[:20]:
        print(f"UNEXPECTED {row_id}: {str(failed[row_id])[:300]}")
    for row_id in stale[:20]:
        print(f"NOW PASSING (remove from list) {row_id}")
    return 1 if unexpected or stale or unknown else 0


if __name__ == "__main__":
    sys.exit(main())
