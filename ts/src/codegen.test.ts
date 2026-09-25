// The committed src/generated/ must be what scripts/codegen.mjs produces from schema/.
// Python pins schema/ to its models (tests/test_schema_export.py); this pins the other hop.
import { describe, expect, it } from 'vitest';

// @ts-expect-error — plain ESM script, no declarations.
import { buildModules, committedModule } from '../scripts/codegen.mjs';

describe('codegen drift guard', () => {
  it('src/generated/ matches a fresh build from schema/', async () => {
    const fresh = (await buildModules()) as Record<string, string>;
    for (const [name, text] of Object.entries(fresh)) {
      expect(committedModule(name), `src/generated/${name} is stale — run \`npm run codegen\``).toBe(text);
    }
  });
});
