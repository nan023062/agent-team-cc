from pathlib import Path as _Path
__version__ = (_Path(__file__).parent.parent / "VERSION").read_text(encoding="utf-8").strip()
