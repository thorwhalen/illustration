# illustration.translation

Canonical → native parameter translation (the `denote` `param_map` idiom).

Each source declares a `param_map` mapping a *canonical* façade parameter name
to how that source expresses it natively. [`make_param_translator()`](#illustration.translation.make_param_translator) turns a
`param_map` into a callable that rewrites a dict of canonical kwargs into the
provider’s native kwargs, degrading gracefully on parameters the source does not
support.

A `param_map` value may be:

- a `str` — straight rename to that native parameter name;
- a `dict` — `{"name": <native>, "coerce": <fn>, "choices": <set>}` where
  `coerce` transforms the value (e.g. vocabulary mapping) and `choices`
  validates it;
- `None` — the parameter is *explicitly unsupported* by this source (degrade);
-  *(a canonical key absent from the map is also treated as unsupported)*.

```pycon
>>> pmap = {
...     "orientation": {"name": "aspect_ratio",
...                     "coerce": lambda o: {"landscape": "wide"}.get(o, o)},
...     "size": "size",
...     "license_type": None,
... }
>>> translate = make_param_translator(pmap)
>>> native, dropped = translate({"orientation": "landscape", "size": "large",
...                              "license_type": "commercial"})
>>> native
{'aspect_ratio': 'wide', 'size': 'large'}
>>> dropped
['license_type']
```

### Module Attributes

| [`ParamTranslator`](#illustration.translation.ParamTranslator)   | A translator maps canonical kwargs -> (native kwargs, dropped canonical names).   |
|--------------------------------------------------------------------|-----------------------------------------------------------------------------------|

### Functions

| [`make_param_translator`](#illustration.translation.make_param_translator)(param_map, \*[, ...])   | Build a translator from a `param_map` (see module docstring).   |
|------------------------------------------------------------------------------------------------|-----------------------------------------------------------------|

### illustration.translation.ParamTranslator

A translator maps canonical kwargs -> (native kwargs, dropped canonical names).

alias of `Callable`[[[`Mapping`](https://docs.python.org/3/library/typing.html#typing.Mapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], `Tuple`[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)]]

### illustration.translation.make_param_translator(param_map, , on_unsupported='ignore', source_name='')

Build a translator from a `param_map` (see module docstring).

`on_unsupported` governs what happens when a canonical param has no native
equivalent: `'ignore'` (drop silently, the graceful default), `'warn'`
(drop + [`warnings.warn()`](https://docs.python.org/3/library/warnings.html#warnings.warn)), or `'raise'` (raise `ValueError`).
Parameters whose value is `None` are skipped entirely (an unset filter).

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`Mapping`](https://docs.python.org/3/library/typing.html#typing.Mapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], [`Tuple`](https://docs.python.org/3/library/typing.html#typing.Tuple)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)]]
