# cbim launcher

Add this directory to your PATH, or symlink `cbim` to somewhere already on PATH.

- macOS/Linux: `ln -sf "$(pwd)/bin/cbim" /usr/local/bin/cbim`
- Windows: add this `bin/` directory to your PATH in System Settings

For development/testing without installing a kernel to ~/.cbim/:
  export CBIM_KERNEL_OVERRIDE=/path/to/cbim-kernel/kernel
  export CBIM_PROJECT_ROOT=/path/to/your/project
  cbim skill list
