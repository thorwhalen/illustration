"""CLI entry point: ``python -m illustration`` / the ``illustration`` script.

Builds an ``argh`` dispatcher over :data:`illustration.cli.COMMANDS`. Keyword-only
parameters become ``--options`` (``NameMappingPolicy.BY_NAME_IF_KWONLY``), matching
the ecosystem's ``ir`` CLI idiom.
"""

from __future__ import annotations


def main(argv=None):
    """Dispatch a CLI command (see :mod:`illustration.cli`)."""
    import argh

    from illustration.cli import COMMANDS

    parser = argh.ArghParser(prog="illustration")
    try:
        parser.set_default_command(None)
    except Exception:  # pragma: no cover - argh version differences
        pass
    add_kwargs = {}
    policy = getattr(argh, "NameMappingPolicy", None)
    if policy is not None:
        add_kwargs["name_mapping_policy"] = policy.BY_NAME_IF_KWONLY
    argh.add_commands(parser, COMMANDS, **add_kwargs)
    argh.dispatch(parser, argv=argv)


if __name__ == "__main__":
    main()
