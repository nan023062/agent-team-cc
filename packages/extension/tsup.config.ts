import { defineConfig } from 'tsup'

export default defineConfig({
  entry: {
    activation: 'src/activation.ts',
  },
  format: ['cjs'],
  dts: false,
  sourcemap: true,
  clean: true,
  external: ['vscode'],
})
