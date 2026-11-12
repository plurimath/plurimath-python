"""Build sealed native inputs from an admitted public Git source recipe."""
import ctypes
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import sysconfig

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
GITHUB = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?\Z")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def relative(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("Expected a nonempty relative POSIX path")
    path = Path(value)
    if path.is_absolute() or any(x in ("..", ".") for x in value.split("/")):
        raise ValueError("Path must remain inside the build workspace")
    return path


def validate(recipe, package):
    if recipe.get("schema") != "plurimath.python-public-native-build/1":
        raise ValueError("Unsupported public native build recipe")
    if recipe.get("rust_toolchain") != "1.95.0":
        raise ValueError("The qualified Rust toolchain must be pinned")
    sources = recipe["sources"]
    if not sources or len({s["id"] for s in sources}) != len(sources):
        raise ValueError("Source identities must be unique and nonempty")
    paths = []
    by_id = {}
    for source in sources:
        if not GITHUB.fullmatch(source["repository"]):
            raise ValueError("Source must use a public GitHub HTTPS repository without credentials")
        if not HEX40.fullmatch(source["revision"]) or not HEX40.fullmatch(source["tree"]):
            raise ValueError("Source commit and tree must be immutable full Git identities")
        path = relative(source["path"])
        if any(path == p or path in p.parents or p in path.parents for p in paths):
            raise ValueError("Source checkout roots must be disjoint")
        paths.append(path)
        by_id[source["id"]] = source
    if set(recipe["components"]) != {"facade", "numeric"}:
        raise ValueError("Both canonical facade and numeric components are required")
    for component in recipe["components"].values():
        source = by_id[component["source"]]
        relative(component["manifest_path"])
        relative(component["lock_path"])
        if not HEX64.fullmatch(component["cargo_lock_sha256"]):
            raise ValueError("Missing qualified Cargo.lock digest")
        template = package / relative(component["receipt_template"])
        if not HEX64.fullmatch(component["receipt_template_sha256"]) or digest(template) != component["receipt_template_sha256"]:
            raise ValueError("Native receipt template digest disagrees")
        template_info = json.loads(template.read_bytes())
        if template_info["native_source_commit"] != source["revision"]:
            raise ValueError("Receipt template source differs from the admitted source")
        if template_info.get("cargo_lock_sha256") != component["cargo_lock_sha256"]:
            raise ValueError("Receipt template lock differs from the admitted source lock")
        if not isinstance(component.get("features"), list) or not all(re.fullmatch(r"[A-Za-z0-9_-]+", x) for x in component["features"]):
            raise ValueError("Explicit feature list is required")
    allowed = recipe.get("allowed_git_sources", [])
    if not isinstance(allowed, list) or any(not s.startswith("git+https://github.com/") or not HEX40.fullmatch(s.rsplit("#", 1)[-1]) for s in allowed):
        raise ValueError("Resolved Git dependencies require complete public immutable source IDs")
    return by_id


def run(command, log, **kwargs):
    with log.open("ab") as output:
        output.write(("$ " + " ".join(map(str, command)) + "\n").encode())
        subprocess.run(list(map(str, command)), stdout=output, stderr=subprocess.STDOUT, check=True, **kwargs)


def output(command, **kwargs):
    return subprocess.check_output(list(map(str, command)), **kwargs)


def identity(root):
    return {"revision": output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "tree": output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()}


def checkout(source, workspace, log):
    root = workspace / relative(source["path"])
    if not root.exists():
        root.mkdir(parents=True)
        run(["git", "init", "--quiet", root], log)
        run(["git", "-C", root, "fetch", "--depth", "1", source["repository"], source["revision"]], log)
        run(["git", "-C", root, "-c", "core.autocrlf=false", "checkout", "--detach", "FETCH_HEAD"], log)
    if identity(root) != {k: source[k] for k in ("revision", "tree")}:
        raise RuntimeError("Checkout identity differs from source recipe: " + source["id"])
    run(["git", "diff", "--exit-code", "HEAD", "--"], log, cwd=root)
    return root


def notice_inventory(metadata, roots, allowed_git, destination):
    inventory = []
    for package in metadata["packages"]:
        base = Path(package["manifest_path"]).resolve().parent
        source = package.get("source")
        repository = None
        source_revision = None
        if source is None:
            owners = [(root, revision) for root, revision in roots if base == root or root in base.parents]
            if len(owners) != 1:
                raise RuntimeError("Unadmitted path dependency: " + package["name"])
            repository, source_revision = owners[0]
        elif source.startswith("git+"):
            if source not in allowed_git:
                raise RuntimeError("Unadmitted resolved Git dependency: " + package["name"])
            repository = Path(output(["git", "rev-parse", "--show-toplevel"], cwd=base, text=True).strip())
            source_revision = identity(repository)["revision"]
            if source_revision != source.rsplit("#", 1)[1]:
                raise RuntimeError("Git notice checkout differs from locked dependency")
        elif not source.startswith("registry+https://github.com/rust-lang/crates.io-index"):
            raise RuntimeError("Unadmitted dependency registry")
        texts = {}
        for prefix, root in (("", base), ("repository-", repository)):
            if root is None:
                continue
            for path in sorted(root.iterdir()):
                if path.is_file() and path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                    texts[prefix + path.name] = path.read_bytes()
        if package.get("license_file"):
            path = base / package["license_file"]
            texts[path.name] = path.read_bytes()
        spdx_only = not texts
        if spdx_only:
            if not package.get("license"):
                raise RuntimeError("Dependency has neither license text nor SPDX metadata")
            texts["Cargo.toml"] = (base / "Cargo.toml").read_bytes()
            texts["SOURCE-LICENSE.json"] = (json.dumps({"spdx": package["license"],
                "source": source, "source_revision": source_revision,
                "notice": "Upstream supplies SPDX metadata but no standalone license text; none synthesized."}, indent=2) + "\n").encode()
        folder = destination / (package["name"] + "-" + package["version"])
        folder.mkdir(parents=True)
        hashes = {}
        for name, data in texts.items():
            path = folder / name
            path.write_bytes(data)
            hashes[path.relative_to(destination).as_posix()] = sha256(data).hexdigest()
        inventory.append({"name": package["name"], "version": package["version"],
                          "license": package.get("license"), "notices": hashes,
                          "spdx_only": spdx_only, "source_revision": source_revision})
    (destination / "manifest.json").write_text(json.dumps(inventory, indent=2) + "\n")


def check_binary(path, component, platform):
    image = path.read_bytes()
    if platform == "win_amd64":
        offset = struct.unpack_from("<I", image, 0x3c)[0]
        if image[offset:offset+4] != b"PE\0\0" or struct.unpack_from("<H", image, offset+4)[0] != 0x8664:
            raise RuntimeError("Expected an AMD64 PE library")
    elif image[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", image, 18)[0] != 62:
        raise RuntimeError("Expected an x86-64 ELF library")
    library = ctypes.CDLL(str(path.resolve()))
    version = getattr(library, "plurimath_" + component + "_abi_version")
    version.argtypes = []
    version.restype = ctypes.c_uint32
    if version() != 1:
        raise RuntimeError("Unsupported native ABI")


def build(recipe_path, workspace, out, package):
    recipe_bytes = recipe_path.read_bytes()
    recipe = json.loads(recipe_bytes)
    by_id = validate(recipe, package)
    platform = sysconfig.get_platform().replace("-", "_").replace(".", "_")
    targets = {"linux_x86_64": "x86_64-unknown-linux-gnu", "win_amd64": "x86_64-pc-windows-msvc"}
    if platform not in targets:
        raise RuntimeError("Only actual Linux/Windows AMD64 build hosts are qualified")
    workspace.mkdir(parents=True, exist_ok=True)
    log = workspace / "build.log"
    roots = {key: checkout(source, workspace, log) for key, source in by_id.items()}
    rustc = output(["rustc", "+" + recipe["rust_toolchain"], "--version"], text=True).strip()
    evidence = {"schema": recipe["schema"], "recipe_sha256": sha256(recipe_bytes).hexdigest(),
                "rustc": rustc, "platform_tag": platform, "sources": recipe["sources"], "components": {}}
    environment = dict(os.environ, CARGO_HOME=str((workspace / "cargo-home").resolve()),
                       CARGO_BUILD_JOBS="1", CARGO_INCREMENTAL="0", CARGO_PROFILE_RELEASE_DEBUG="0",
                       CARGO_PROFILE_RELEASE_OPT_LEVEL="1", CARGO_PROFILE_RELEASE_CODEGEN_UNITS="64")
    for name, component in recipe["components"].items():
        source = roots[component["source"]]
        lock = source / relative(component["lock_path"])
        if digest(lock) != component["cargo_lock_sha256"]:
            raise RuntimeError("Source Cargo.lock differs from qualified input: " + name)
        target = workspace / "targets" / name
        cargo = ["cargo", "+" + recipe["rust_toolchain"]]
        flags = ["--locked", "--manifest-path", source / relative(component["manifest_path"]),
                 "--target-dir", target, "--target", targets[platform], "--release"]
        features = ["--features", ",".join(component["features"])] if component["features"] else []
        run(cargo + ["build", "--lib"] + flags + features, log, env=environment)
        metadata_bytes = output(cargo + ["metadata", "--locked", "--format-version", "1",
                                "--manifest-path", source / relative(component["manifest_path"]),
                                "--filter-platform", targets[platform]] + features, env=environment)
        metadata = json.loads(metadata_bytes)
        folder = workspace / "components" / name
        folder.mkdir(parents=True)
        (folder / "cargo-metadata.json").write_bytes(metadata_bytes)
        filename = ("plurimath_" + name + ".dll" if platform == "win_amd64" else "libplurimath_" + name + ".so")
        library = folder / filename
        shutil.copyfile(target / targets[platform] / "release" / filename, library)
        check_binary(library, name, platform)
        notices = folder / "licenses"
        notices.mkdir()
        notice_inventory(metadata, [(root.resolve(), by_id[key]["revision"]) for key, root in roots.items()],
                         recipe.get("allowed_git_sources", []), notices)
        info = json.loads((package / component["receipt_template"]).read_bytes())
        info.pop("library_sha256", None)  # A new compiler produces its own measured binary digest.
        info.update(abi_version=1, library=filename, sha256=digest(library), platform_tag=platform,
                    target=targets[platform], rustc=rustc, cargo_lock_sha256=digest(lock),
                    cargo_metadata_sha256=sha256(metadata_bytes).hexdigest(),
                    public_build_recipe_sha256=sha256(recipe_bytes).hexdigest(),
                    source_closure=recipe["sources"], build_profile="release-opt1-codegen64-jobs1")
        (folder / "build-info.json").write_text(json.dumps(info, indent=2) + "\n")
        if name == "facade":
            run(cargo + ["test", "--lib"] + flags + features + ["--", "--test-threads=1"], log, env=environment)
        if digest(lock) != component["cargo_lock_sha256"]:
            raise RuntimeError("Build changed the admitted lock")
        evidence["components"][name] = {"sha256": info["sha256"], "receipt_sha256": digest(folder / "build-info.json")}
    for key, root in roots.items():
        if identity(root) != {k: by_id[key][k] for k in ("revision", "tree")}:
            raise RuntimeError("Build changed a source identity")
        run(["git", "diff", "--exit-code", "HEAD", "--"], log, cwd=root)
    command = [sys.executable, package / "scripts/seal-native-inputs.py", "--out", out]
    for name in ("numeric", "facade"):
        folder = workspace / "components" / name
        info = json.loads((folder / "build-info.json").read_bytes())
        command += ["--" + name + "-library", folder / info["library"],
                    "--" + name + "-receipt", folder / "build-info.json"]
    run(command, log)
    (workspace / "result.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence
