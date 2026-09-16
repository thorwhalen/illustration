# illustration.credentials

API-key resolution (the `aix` credentials idiom + `falaw` BYO-key seam).

A source that needs a key (e.g. Pexels) resolves it with this precedence:

1. an explicit `api_key=` argument,
2. a per-request binding via [`using_credentials()`](#illustration.credentials.using_credentials) (a `ContextVar` — the
   “bring-your-own-key” seam a web backend uses without threading a credential
   argument through every call),
3. the provider’s environment variable (see [`PROVIDER_ENV_VARS`](#illustration.credentials.PROVIDER_ENV_VARS)),
4. a `config2py` config store keyed by the env-var name.

Missing keys raise an informative [`MissingCredentialError`](illustration.errors.html.md#illustration.errors.MissingCredentialError)
(naming *which* key, *how* to set it, *where* to get one) — values are never logged.

```pycon
>>> with using_credentials(pexels="secret-123"):
...     resolve_api_key("pexels")
'secret-123'
>>> resolve_api_key("openverse") is None      # no key needed; none configured
True
```

### Module Attributes

| [`PROVIDER_ENV_VARS`](#illustration.credentials.PROVIDER_ENV_VARS)     | Provider name -> the environment variable that holds its API key.             |
|------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| [`PROVIDER_CONSOLE_URLS`](#illustration.credentials.PROVIDER_CONSOLE_URLS) | Provider name -> where a user obtains a key (shown in the missing-key error). |

### Functions

| [`resolve_api_key`](#illustration.credentials.resolve_api_key)(provider, \*[, api_key])    | Resolve the API key for `provider` by precedence, or `None` if absent.                                              |
|----------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|
| [`check_requirements`](#illustration.credentials.check_requirements)(provider, \*[, api_key]) | Return the key for `provider`, raising if a *required* key is missing.                                              |
| [`requires_credentials`](#illustration.credentials.requires_credentials)(provider)              | Decorator separating credential-checking from a function's business logic.                                          |
| [`using_credentials`](#illustration.credentials.using_credentials)(\*\*provider_keys)        | Bind per-request provider API keys for the duration of the `with` block.                                            |
| [`current_credentials`](#illustration.credentials.current_credentials)()                       | The provider keys currently bound by [`using_credentials()`](#illustration.credentials.using_credentials) (a copy). |

### illustration.credentials.PROVIDER_CONSOLE_URLS *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [str](https://docs.python.org/3/builtins/stdtypes.html#str)]* *= {'pexels': 'https://www.pexels.com/api/new/', 'pixabay': 'https://pixabay.com/api/docs/'}*

Provider name -> where a user obtains a key (shown in the missing-key error).

### illustration.credentials.PROVIDER_ENV_VARS *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [str](https://docs.python.org/3/builtins/stdtypes.html#str)]* *= {'pexels': 'PEXELS_API_KEY', 'pixabay': 'PIXABAY_API_KEY'}*

Provider name -> the environment variable that holds its API key.
Appendable: add a row when a new keyed provider is registered.

### illustration.credentials.check_requirements(provider, , api_key=None)

Return the key for `provider`, raising if a *required* key is missing.

A provider with no entry in [`PROVIDER_ENV_VARS`](#illustration.credentials.PROVIDER_ENV_VARS) needs no key and
returns `None`. Otherwise a missing key raises
[`MissingCredentialError`](illustration.errors.html.md#illustration.errors.MissingCredentialError).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### illustration.credentials.current_credentials()

The provider keys currently bound by [`using_credentials()`](#illustration.credentials.using_credentials) (a copy).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### illustration.credentials.requires_credentials(provider)

Decorator separating credential-checking from a function’s business logic.

Runs [`check_requirements()`](#illustration.credentials.check_requirements) for `provider` before the wrapped function
body, so the function never inlines key handling. (The built-in sources call
[`check_requirements()`](#illustration.credentials.check_requirements) directly; this decorator is the functional-style
equivalent for Layer-2 helpers.)

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)

```pycon
>>> @requires_credentials("pexels")
... def fetch(): return "ok"
>>> with using_credentials(pexels="k"):
...     fetch()
'ok'
```

### illustration.credentials.resolve_api_key(provider, , api_key=None)

Resolve the API key for `provider` by precedence, or `None` if absent.

Does not raise — callers that *require* a key use [`check_requirements()`](#illustration.credentials.check_requirements).
Reads are non-interactive (never prompts).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### illustration.credentials.using_credentials(\*\*provider_keys)

Bind per-request provider API keys for the duration of the `with` block.

Falsy values are ignored (so an optional request header passes straight
through). Bindings nest: an inner block overlays the outer.

```pycon
>>> with using_credentials(pexels="k1"):
...     with using_credentials(pexels="k2"):
...         inner = resolve_api_key("pexels")
...     outer = resolve_api_key("pexels")
>>> inner, outer
('k2', 'k1')
```
