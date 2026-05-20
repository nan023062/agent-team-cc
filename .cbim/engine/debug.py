import os
from pathlib import Path


def is_debug() -> bool:
    if os.environ.get("CBIM_DEBUG", "").lower() in ("1", "true", "yes"):
        return True
    flag = Path(__file__).resolve().parent.parent / ".debug"
    return flag.exists()
