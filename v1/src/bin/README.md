# cbim launcher

Add this directory to your PATH, or symlink `cbim` to somewhere already on PATH.

- macOS/Linux: `ln -sf "$(pwd)/bin/cbim" /usr/local/bin/cbim`
- Windows: add this `bin/` directory to your PATH in System Settings

The installer (`python install.py`) writes the launcher into
`<install_root>/bin/`, which defaults to:

- Windows: `%LOCALAPPDATA%\Cbim-CC\bin\`
- POSIX:   `$XDG_DATA_HOME/Cbim-CC/bin/` (default `~/.local/share/Cbim-CC/bin`)

Override the install root with the `CBIM_INSTALL_ROOT` env var.

For development/testing without installing a kernel:
  export CBIM_KERNEL_OVERRIDE=/path/to/cbim-kernel/kernel
  export CBIM_PROJECT_ROOT=/path/to/your/project
  cbim skill list
