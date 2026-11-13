"""Admit one complete, reviewed public source recipe and its exact receipt templates."""
import argparse
import json
from pathlib import Path
from public_native import relative, validate

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--from-directory", required=True, type=Path)
p.add_argument("--check-only", action="store_true")
a = p.parse_args()
source = a.from_directory.resolve()
package = Path(__file__).resolve().parents[1]
recipe_bytes = (source / "ci/native-build.json").read_bytes()
recipe = json.loads(recipe_bytes)
validate(recipe, source)
files = {Path("ci/native-build.json"): recipe_bytes}
for component in recipe["components"].values():
    path = relative(component["receipt_template"])
    if Path("ci/native-receipts") not in path.parents:
        raise ValueError("Admitted receipt templates must live in ci/native-receipts")
    files[path] = (source / path).read_bytes()
if not a.check_only:
    for path, data in files.items():
        destination = package / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    validate(recipe, package)
print(json.dumps({"status": "valid_admission_inputs" if a.check_only else "admitted", "files": [str(p) for p in files],
                  "sources": len(recipe["sources"]), "native_executed": False}))
