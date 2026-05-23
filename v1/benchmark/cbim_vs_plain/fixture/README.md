# mini-calc

A toy Python project used as a shared fixture for the CBIM-vs-plain benchmark.

## Modules

- **`src/calculator.py`** — four basic arithmetic functions: `add`, `subtract`,
  `multiply`, `divide`. Pure functions, no I/O.
- **`src/parser.py`** — string-to-expression parsing: `parse_number(s)` and
  `parse_binary(s)` (returns `(left, op, right)`). Supports operators `+ - * /`.
- **`tests/test_calculator.py`** — pytest tests covering `add` / `subtract` /
  `multiply`. Run with `pytest -q` from the project root.

## Module boundaries

- `calculator` owns numeric operations only — it knows nothing about strings.
- `parser` owns string-to-token conversion only — it knows nothing about
  evaluating an expression. The two are deliberately decoupled; an evaluator
  belongs in `parser` (calls into `calculator`) or in a new module.

## Known issues

1. **`divide` is missing zero-divisor handling.** Calling `divide(x, 0)` raises a
   raw `ZeroDivisionError`; the public contract should raise a domain-specific
   error instead.
2. **`parser.py` has no tests.** Only the calculator module has coverage.
3. **No expression-evaluator entry point.** `parse_binary` returns the tokens
   but nothing turns them into a result.
4. **Errors are all bare `ValueError`.** No common error hierarchy across
   modules, which makes downstream `except` clauses imprecise.
