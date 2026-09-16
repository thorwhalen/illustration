# illustration.errors

The package exception hierarchy.

Errors are informative by design: a [`MissingCredentialError`](#illustration.errors.MissingCredentialError) names *which*
key is missing, *how* to provide it, and *where* to obtain it — and never logs
the key value itself.

```pycon
>>> raise MissingCredentialError("pexels", env_var="PEXELS_API_KEY",
...     console_url="https://www.pexels.com/api/new/")
Traceback (most recent call last):
illustration.errors.MissingCredentialError: ...
```

### Exceptions

| [`IllustrationError`](#illustration.errors.IllustrationError)                                | Base class for every error raised by [`illustration`](illustration.html.md#module-illustration).   |
|---------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| [`UnknownSourceError`](#illustration.errors.UnknownSourceError)(name[, known])                | A source name was requested that is not in the registry.                                                                  |
| [`MissingCredentialError`](#illustration.errors.MissingCredentialError)(provider, \*[, ...])      | A source needs an API key that could not be resolved.                                                                     |
| [`ProviderError`](#illustration.errors.ProviderError)(provider, message, \*[, status])   | A provider's HTTP API returned an error or an unusable response.                                                          |
| [`RateLimitError`](#illustration.errors.RateLimitError)(provider, message, \*[, status])  | A provider returned HTTP 429 (rate limit exceeded).                                                                       |
| [`RerankDependencyError`](#illustration.errors.RerankDependencyError)([missing])                 | The optional local-rerank dependencies are not installed.                                                                 |
| [`CurateDependencyError`](#illustration.errors.CurateDependencyError)([missing, extra, purpose]) | An optional Layer-2 (agentic curation) dependency is not installed.                                                       |

### *exception* illustration.errors.CurateDependencyError(missing=None, , extra='curate', purpose='agentic curation')

Bases: [`IllustrationError`](#illustration.errors.IllustrationError), [`ImportError`](https://docs.python.org/3/builtins/exceptions.html#ImportError)

An optional Layer-2 (agentic curation) dependency is not installed.

The message names the missing packages and the extra that provides them,
so the failure is actionable (e.g. `pip install 'illustration[curate]'`).

### *exception* illustration.errors.IllustrationError

Bases: [`Exception`](https://docs.python.org/3/builtins/exceptions.html#Exception)

Base class for every error raised by [`illustration`](illustration.html.md#module-illustration).

### *exception* illustration.errors.MissingCredentialError(provider, , env_var=None, console_url=None)

Bases: [`IllustrationError`](#illustration.errors.IllustrationError)

A source needs an API key that could not be resolved.

The message tells the user exactly what to do; key values are never logged.

### *exception* illustration.errors.ProviderError(provider, message, , status=None)

Bases: [`IllustrationError`](#illustration.errors.IllustrationError)

A provider’s HTTP API returned an error or an unusable response.

### *exception* illustration.errors.RateLimitError(provider, message, , status=None)

Bases: [`ProviderError`](#illustration.errors.ProviderError)

A provider returned HTTP 429 (rate limit exceeded).

### *exception* illustration.errors.RerankDependencyError(missing=None)

Bases: [`IllustrationError`](#illustration.errors.IllustrationError), [`ImportError`](https://docs.python.org/3/builtins/exceptions.html#ImportError)

The optional local-rerank dependencies are not installed.

The message names the missing packages and the extra that provides them.

### *exception* illustration.errors.UnknownSourceError(name, known=None)

Bases: [`IllustrationError`](#illustration.errors.IllustrationError), [`KeyError`](https://docs.python.org/3/builtins/exceptions.html#KeyError)

A source name was requested that is not in the registry.
