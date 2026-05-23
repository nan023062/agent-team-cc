"""Simple calculator with basic operations."""


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b


def multiply(a: float, b: float) -> float:
    return a * b


# Bug: divide by zero not handled
def divide(a: float, b: float) -> float:
    return a / b
