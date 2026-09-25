/**
 * Canonical → native parameter translation, mirroring `illustration.translation`.
 *
 * A `paramMap` value may be a string (rename), a spec object (`name`, optional
 * `choices` guard, optional `coerce`), a bare function (`coerce`, same name), or
 * `null` (explicitly unsupported: the parameter degrades). A canonical key
 * absent from the map is unsupported too. A `null`/`undefined` *value* is an
 * unset filter and is skipped, not dropped.
 */

export type Coerce = (value: unknown) => unknown;

export interface ParamSpec {
  readonly name?: string;
  readonly choices?: ReadonlySet<string> | readonly string[];
  readonly coerce?: Coerce;
}

export type ParamMapValue = string | ParamSpec | Coerce | null;
export type ParamMap = Readonly<Record<string, ParamMapValue>>;

export interface Translation {
  readonly native: Record<string, unknown>;
  readonly dropped: string[];
}

export type ParamTranslator = (canonical: Readonly<Record<string, unknown>>) => Translation;

/** Build a translator from a `paramMap`. Unsupported parameters are dropped
 *  silently (Python's `on_unsupported="ignore"`, the façade's setting). */
export function makeParamTranslator(paramMap: ParamMap): ParamTranslator {
  return (canonical) => {
    const native: Record<string, unknown> = {};
    const dropped: string[] = [];
    for (const [key, value] of Object.entries(canonical)) {
      if (value === null || value === undefined) continue;
      const spec = Object.hasOwn(paramMap, key) ? paramMap[key] : null;
      if (spec === null || spec === undefined) {
        dropped.push(key);
        continue;
      }
      const applied = applySpec(key, value, spec);
      if (applied === null) {
        dropped.push(key);
        continue;
      }
      native[applied.name] = applied.value;
    }
    return { native, dropped };
  };
}

function applySpec(
  key: string,
  value: unknown,
  spec: string | ParamSpec | Coerce,
): { name: string; value: unknown } | null {
  if (typeof spec === 'string') return { name: spec, value };
  if (typeof spec === 'function') return { name: key, value: spec(value) };
  const name = spec.name ?? key;
  if (spec.choices !== undefined) {
    const choices = spec.choices instanceof Set ? spec.choices : new Set(spec.choices);
    if (typeof value !== 'string' || !choices.has(value)) return null;
  }
  return { name, value: spec.coerce ? spec.coerce(value) : value };
}
