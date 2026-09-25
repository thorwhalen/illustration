import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Every test injects its own `fetch`; the guard makes forgetting that a failure
    // rather than a real request to a provider's anonymous tier (see src/test-setup.ts).
    setupFiles: ['src/test-setup.ts'],
  },
});
