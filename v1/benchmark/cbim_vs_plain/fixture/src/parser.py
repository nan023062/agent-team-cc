"""Tiny expression parser. Supports + - * /."""


def parse_number(s: str) -> float:
    return float(s.strip())


def parse_binary(s: str) -> tuple[float, str, float]:
    """Parse 'a OP b' format. OP is one of +, -, *, /."""
    for op in ("+", "-", "*", "/"):
        if op in s:
            left, right = s.split(op, 1)
            return parse_number(left), op, parse_number(right)
    raise ValueError(f"no operator in: {s}")
