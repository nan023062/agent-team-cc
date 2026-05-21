import os


def is_debug() -> bool:
    if os.environ.get("CBIM_DEBUG", "").lower() in ("1", "true", "yes"):
        return True
    from cbim_kernel.context import cbim_dir
    return (cbim_dir() / ".debug").exists()
