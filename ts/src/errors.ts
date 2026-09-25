/**
 * The error tree, mirroring `illustration.errors`.
 *
 * Every error names the provider and, for a missing key, says how to supply one
 * and where to get one. Key *values* never appear in a message.
 */

export class IllustrationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}

export class UnknownSourceError extends IllustrationError {
  constructor(
    readonly source: string,
    known: readonly string[],
  ) {
    super(`Unknown source ${JSON.stringify(source)}. Registered sources: ${known.join(', ')}.`);
  }
}

export class MissingCredentialError extends IllustrationError {
  constructor(
    readonly provider: string,
    opts: { envVar?: string | null; consoleUrl?: string | null } = {},
  ) {
    const where = opts.consoleUrl ? ` Get one at ${opts.consoleUrl}.` : '';
    const env = opts.envVar ? ` (the Python side reads ${opts.envVar})` : '';
    super(
      `${provider} needs an API key: pass it as \`credentials: { ${provider}: "…" }\`${env}.${where}`,
    );
  }
}

export class ProviderError extends IllustrationError {
  constructor(
    readonly provider: string,
    message: string,
    readonly status: number | null = null,
  ) {
    super(`${provider}: ${message}${status !== null ? ` (HTTP ${status})` : ''}`);
  }
}

export class RateLimitError extends ProviderError {}
