# illustration.registry

The open-closed source registry and the `sources` view.

Providers register their [`RetrievalSource`](illustration.base.html.md#illustration.base.RetrievalSource) instance by
name into a module-level mapping; the façade dispatches through it. Adding a
provider never touches the façade. The [`sources`](#illustration.registry.sources) view offers both
dict-style (`sources["pexels"]`) and attribute-style (`sources.pexels`)
access — the `denote` idiom — and is a *live view* over the SSOT registry, so
“what providers exist” can never drift from what is queryable.

```pycon
>>> from illustration.registry import list_sources
>>> "openverse" in list_sources()
True
```

### Module Attributes

| [`sources`](#illustration.registry.sources)   | `illustration.sources["openverse"]` or `.openverse`.   |
|------------------------------------------------------------|--------------------------------------------------------|

### Functions

| [`register_source`](#illustration.registry.register_source)(source, \*[, name])   | Register a source instance under `name` (default `source.name`).        |
|----------------------------------------------------------------------------------------|-------------------------------------------------------------------------|
| [`unregister_source`](#illustration.registry.unregister_source)(name)               | Remove a source from the registry (no error if absent).                 |
| [`get_source`](#illustration.registry.get_source)(name)                      | Return the registered source named `name` (raises if unknown).          |
| [`list_sources`](#illustration.registry.list_sources)()                        | Sorted names of all registered sources.                                 |
| [`default_sources`](#illustration.registry.default_sources)()                     | The default source set (config `DFLT_SOURCES`), filtered to registered. |

### Classes

| [`SourcesView`](#illustration.registry.SourcesView)()   | A live `Mapping` over the registry with dict- *and* attribute-access.   |
|------------------------------------------------------------------|-------------------------------------------------------------------------|

### *class* illustration.registry.SourcesView

Bases: [`Mapping`](https://docs.python.org/3/library/typing.html#typing.Mapping)

A live `Mapping` over the registry with dict- *and* attribute-access.

Attribute access (`sources.openverse`) is a convenience; dict access
(`sources["openverse"]`) is the canonical form and the only one that works
for a source whose name collides with a `Mapping` method (`get`,
`keys`, `values`, …).

### illustration.registry.default_sources()

The default source set (config `DFLT_SOURCES`), filtered to registered.

Falls back to all registered sources if none of the configured defaults are
present, so the façade always has something to query.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### illustration.registry.get_source(name)

Return the registered source named `name` (raises if unknown).

* **Return type:**
  [`RetrievalSource`](illustration.base.html.md#illustration.base.RetrievalSource)

### illustration.registry.list_sources()

Sorted names of all registered sources.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### illustration.registry.register_source(source, , name=None)

Register a source instance under `name` (default `source.name`).

Returns the source, so it can be used as `SRC = register_source(MySource())`.

* **Return type:**
  [`RetrievalSource`](illustration.base.html.md#illustration.base.RetrievalSource)

### illustration.registry.sources *= SourcesView(['openverse', 'pexels', 'pixabay', 'wikimedia'])*

`illustration.sources["openverse"]` or `.openverse`.

* **Type:**
  Singleton view

### illustration.registry.unregister_source(name)

Remove a source from the registry (no error if absent).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)
