# PMA measured and quantity input

This continuation prepares `plurimath.parse(text, "pma")` for the integrated
native PMA parser. Its native wheel qualification is pending; the preserved
2712 milestone is not relabelled as supporting this measured-input contract.

```python
formula = plurimath.parse("ustd(1.230, 0.004)", "pma")
latex = formula.to_latex()
```

The existing Python parse method forwards the format, text and options directly.
It has no format whitelist and adds no PMA grammar, arithmetic or constructor
logic. PMA version 1 accepts no parse options: locale and decimal controls are
rejected by the native engine with `PARSE_OPTION_ERROR`. Numbers use a full stop.
Writer options remain separate and use the ordinary `Formula.write` API.

The frozen Ruby core reference contains 98 inputs: 34 common models, 64 parse
refusals, and 204 writer outputs across all six formats. Four inputs labelled as
accepted stage intentions in that original file are refused by the Ruby core;
the file is preserved unchanged. The typed PMA stage's 38 accepted cases are a
separate contract. Protocol mocks only prove Python forwarding. Native parity
will be claimed only after the immutable integrated engine and installed wheels
replay these source cases. Additional native refusal categories and caller UTF-8
offsets are retained without inventing matching Ruby offsets where the source
reference supplies none. See `features/pma-v1.json` for exact source fingerprints.
