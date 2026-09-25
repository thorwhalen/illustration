// The offline guard: no vitest test ever reaches the network.
//
// `search()` and `searchSource()` default to `globalThis.fetch`, and Node has a real one,
// so a test that forgets to inject a fake would quietly hit a provider and still pass.
// The Python suite has `_no_outbound_network`; this is the TS equivalent.
import { beforeAll } from 'vitest';

beforeAll(() => {
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    throw new Error(`offline test tried to fetch ${String(input)} — inject a fake \`fetch\``);
  }) as typeof globalThis.fetch;
});
