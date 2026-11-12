"""Validate an admitted recipe or build actual host-native sealed wheel inputs."""
import argparse
import json
from pathlib import Path
from public_native import build, validate

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--manifest", type=Path, required=True)
p.add_argument("--workspace", type=Path)
p.add_argument("--out", type=Path)
p.add_argument("--validate-only", action="store_true")
a = p.parse_args()
package = Path(__file__).resolve().parents[1]
if not a.manifest.is_file():
    p.error("Final immutable public native source recipe is not admitted: " + str(a.manifest))
if a.validate_only:
    recipe = json.loads(a.manifest.read_bytes())
    validate(recipe, package)
    print(json.dumps({"status": "valid_input_contract", "sources": len(recipe["sources"])}))
else:
    if a.workspace is None or a.out is None:
        p.error("--workspace and --out are required for a native build")
    result = build(a.manifest.resolve(), a.workspace.resolve(), a.out.resolve(), package)
    print(json.dumps({"platform_tag": result["platform_tag"], "components": result["components"]}))
