# Plurimath Python

The Plurimath wheel evaluates serialized AST requests using its bundled Rust
kernel. Call `plurimath.evaluate(request)` for a Python response envelope
or `plurimath.evaluate_json(request_text)` for the original JSON response.
The engine owns exact numeric semantics and typed result, refusal, and
indeterminate outcomes. The bundled kernel accepts three request profiles:

- `plurimath.evaluate.numeric/1` for numeric AST evaluation.
- `plurimath.evaluate.quantity/1` for exact quantity evaluation. Its bindings
  can carry exact value strings and unit expressions, for example
  `{"value":"2","unit":"kV"}`. Use `convert_to` to request a second quantity
  in a target unit. The optional `register` array supplies caller-declared
  conversion factors, offsets and dimensions through the UnitsML register decoder.
  Unit parsing and algebra run inside the same Rust library.

- `plurimath.evaluate.gum/1` for uncertainty propagation, series statistics,
  coverage factors, conformance decisions, and Monte Carlo propagation.
  The sealed corpus includes all 13 published Monte Carlo profiles, calibration,
  implicit propagation and the supported Annex H examples.

Call `plurimath.initialize()` once to verify and load the bundled library
before a strict request-processing loop. Initialization returns the reusable
kernel. Requests use that same kernel without reading the filesystem or
environment.

Install the matching platform wheel. The bundled library is checked against
its build receipt before loading. `NumericKernel(path)` is also available
for callers that manage an explicit ABI-v1 library. The API accepts AST
requests from a caller or parser and has no formula-text input.

Windows x86_64 wheels bundle `plurimath_numeric.dll` and use the separately sealed
`native-source.win_amd64.json`; Linux defaults remain in `native-source.json`.
To prepare Windows notices on a source-validation host, run `scripts/build-wheel.py`
with `--platform-tag win_amd64 --prepare-dir DIR --target-metadata WINDOWS_METADATA`
and the usual pinned source, library and source metadata arguments. This verifies
the AMD64 PE image, clean source pins, both metadata seals and target dependency
identities. Build the wheel on Windows with the prepared `build-info.json` as
`PLURIMATH_NATIVE_RECEIPT` and the DLL as `PLURIMATH_NATIVE`; neither variable is
needed by the installed runtime.

The `validate_coverage` GUM operation compares caller-supplied coverage metadata with the documented Ruby compatibility semantics. Its diagnostic result carries the source metadata trust boundary.

The native format facade is being implemented separately from serialized numeric
evaluation. `parse(text, input_format)` returns a `Formula` whose `model` is the
canonical native `{class, fields}` common-model wire; the six `to_*` methods call
the Rust writers. Python contains no parser, converter or writer implementation.
`FacadeKernel(library_path)` provides an explicit native context. Packaged format
calls use a separately pinned facade library and receipt, without environment
overrides. Build with both `PLURIMATH_FACADE_NATIVE` and
`PLURIMATH_FACADE_RECEIPT` to include that component.

This candidate is incomplete: the first source-backed AsciiMath slice and its
six writers are qualified, while the native core is expanding toward the promised
input formats, nodes and options. An `unported_capability` refusal is an incomplete
implementation, not accepted format compatibility. Numeric evaluation retains its
existing native component and wire behavior. The common wire container does not
claim generated Python classes or complete class-semantic validation.
