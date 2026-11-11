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
  in a target unit. Unit parsing and algebra run inside the same Rust library.

- `plurimath.evaluate.gum/1` for uncertainty propagation, series statistics,
  coverage factors, conformance decisions, and Monte Carlo propagation.
  The sealed corpus includes all 13 published Monte Carlo profiles.

Call `plurimath.initialize()` once to verify and load the bundled library
before a strict request-processing loop. Initialization returns the reusable
kernel. Requests use that same kernel without reading the filesystem or
environment.

Install the matching platform wheel. The bundled library is checked against
its build receipt before loading. `NumericKernel(path)` is also available
for callers that manage an explicit ABI-v1 library. The API accepts AST
requests from a caller or parser and has no formula-text input.
