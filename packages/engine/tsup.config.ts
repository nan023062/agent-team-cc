import { defineConfig } from 'tsup'

export default defineConfig({
  entry: {
    index: 'src/index.ts',
    'knowledge/index': 'src/knowledge/index.ts',
    'memory/index': 'src/memory/index.ts',
    'dispatch/index': 'src/dispatch/index.ts',
    'migration/index': 'src/migration/index.ts',
    'tools/index': 'src/tools/index.ts',
  },
  format: ['esm'],
  dts: true,
  sourcemap: true,
  clean: true,
})
