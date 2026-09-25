/**
 * The source registry, mirroring `illustration.registry`: the open-closed seam.
 *
 * The four built-in sources are registered at import. Adding a provider means
 * exporting it on the Python side (so its record and fixtures exist), writing its
 * hooks module under `providers/`, and calling `registerSource` — the façade is
 * untouched.
 */

import { UnknownSourceError } from './errors';
import { CONSTANTS } from './generated/constants';
import { openverse } from './providers/openverse';
import { pexels } from './providers/pexels';
import { pixabay } from './providers/pixabay';
import { wikimedia } from './providers/wikimedia';
import type { RetrievalSource } from './source';

const REGISTRY = new Map<string, RetrievalSource>();

export function registerSource(source: RetrievalSource): RetrievalSource {
  REGISTRY.set(source.name, source);
  return source;
}

export function getSource(name: string): RetrievalSource {
  const source = REGISTRY.get(name);
  if (!source) throw new UnknownSourceError(name, listSources());
  return source;
}

/** Registered source names, in registration order. */
export function listSources(): string[] {
  return Array.from(REGISTRY.keys());
}

/** The sources a bare `search(q)` fans out to (`DFLT_SOURCES` on the Python side). */
export function defaultSources(): string[] {
  return [...CONSTANTS.defaults.sources];
}

for (const source of [openverse, wikimedia, pexels, pixabay]) registerSource(source);
