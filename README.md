# Plurimath Python

The Plurimath wheel evaluates serialized AST requests using its bundled Rust
kernel. Call `plurimath.evaluate(request)` for a Python response envelope
or `plurimath.evaluate_json(request_text)` for the original JSON response.
The engine owns exact numeric semantics and typed result, refusal, and
indeterminate outcomes. Use the `plurimath.evaluate.numeric/1` schema.

Install the matching platform wheel. The bundled library is checked against
its build receipt before loading. `NumericKernel(path)` is also available
for callers that manage an explicit ABI-v1 library. The API accepts AST
requests from a caller or parser and has no formula-text input.
