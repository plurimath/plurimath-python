# Native CI admission and platform proof

The public-source workflow builds both canonical Rust C ABI libraries on Linux
and Windows. It builds one platform wheel per OS, then installs that same wheel
in fresh offline environments for Python 3.9, 3.12 and 3.14. Windows tests use only
system directories in PATH. No runtime native-library environment override is
required. The wheel tags remain `linux_x86_64` and `win_amd64`; no manylinux or
universal-wheel claim is made.

`ci/native-build.json` is required. Until the final immutable native source seal
and all public dependency pins are admitted, its absence is a deliberate failing
CI prerequisite. Source-only/forwarding tests are not native completion evidence.
The workflow contains no registry publication or release step.

## Admit one final source checkpoint

Prepare a reviewed directory containing `ci/native-build.json` and the two
receipt templates named by it under `ci/native-receipts/`. Run:

```sh
python scripts/enable-native-ci.py --from-directory /path/to/admitted-source-recipe --check-only
python scripts/enable-native-ci.py --from-directory /path/to/admitted-source-recipe
python scripts/build-public-native.py --manifest ci/native-build.json --validate-only
git add -- ci/native-build.json ci/native-receipts/numeric.json ci/native-receipts/facade.json
git commit -m "Pin the sealed public native source closure"
git push org HEAD:refs/heads/feat/native-facade-pma
```

This is one coherent pin update, not an intermediate wheel build. Use the exact
receipt filenames recorded in the reviewed recipe when staging. Preserve older
qualified binaries and source receipts separately.

## Recipe contract

The recipe schema is `plurimath.python-public-native-build/1` and pins
`rust_toolchain` to `1.95.0`. `sources` is a nonempty array with unique `id`, a
public GitHub HTTPS `repository`, full 40-character `revision` and `tree`, and a
relative `path`. Paths are disjoint checkout roots. Lay them out exactly as the
source Cargo path dependencies require; do not rewrite producer manifests.
`allowed_git_sources` lists every complete Cargo Git source ID including its
40-character fragment. Other undeclared Git or path dependencies fail.

`components` has exactly `numeric` and `facade`. Each selects a source `id` via
`source`, plus relative `manifest_path` and `lock_path`, full
`cargo_lock_sha256`, explicit `features` array, and a `receipt_template` path
with `receipt_template_sha256`. Each template must contain the identical
`native_source_commit` and `cargo_lock_sha256`; remaining source/profile/fixture
metadata comes from the actual seal. There are no branch-name or missing-source
fallbacks. `scripts/tests/test_public_native.py` exercises accepted and rejected
contracts without simulating native runtime success.

Each build uses `--locked`, Rust 1.95, one job, release optimization level 1,
64 codegen units and a task-local Cargo home and one target per immutable source root. Sources and
locks are checked again afterward. The facade's library tests run on ordinary
Rust test threads with no stack environment override. Native ELF/PE architecture
and exported ABI version are tested on the actual build OS. Resolved Cargo
metadata and actual upstream license files are captured; SPDX-only upstream
limitations stay explicit. Notice identities include the complete Cargo package ID,
so equal name/version packages from different sources never overwrite one another. The resulting library, receipt and every notice byte
are sealed before packaging. Compiler-dependent binary hashes are measured from
this build rather than copied from another machine's artifact.

The installed checks retain original source bytes and IDs: all 2,928 writer
option rows (2,070 model + 858 parse-to-write), 870 current text-model writer
outputs, 1,349 parser cases, PMA's 98 actual Ruby cases and its six writers, typed
source/profile and formatter checks, numeric/quantity/GUM profiles, ownership and
free/reuse, initialized I/O guards, and isolated default-stack depths
16/64/128 plus the typed 256 resource refusal/reuse. Source exceptions are checked
by their recorded source class; an unported native refusal is a failure for a
valid-source output. Forwarding tests alone never establish these properties.

The installed matrix also covers the measured Ruby 0a1df68 writer correction for
one legacy row. It is applied only when the legacy row matches its recorded bytes,
and every correction must apply. It also covers the 65-case Ruby quantity packet
(the strict 38-case subset, three Float refusals and 24 scale transitions), the
87 residual LaTeX/UnicodeMath text shapes, and a warmed pass in which file,
process, network and library-load events are refused.

## Current pin

`ci/native-build.json` pins public plurimath-rs f9e6f9f, which integrates the
text follow-up. Its final source seal is still pending on the Rust side, so the
receipts keep `full_facade_complete` false. Readiness and merge need passing
installed Linux and Windows evidence on this exact source and branch head.
