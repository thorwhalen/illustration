"""CLI entry point: ``python -m illustration`` / the ``illustration`` script.

Builds a ``cw`` dispatcher over :data:`illustration.cli.COMMANDS`. Each command's
signature *is* its grammar: the leading positional stays positional, and every
keyword-only parameter becomes an ``--option`` whose default is shown in ``--help``.

Two notes for anyone changing this file:

* ``cw.dispatch`` **returns** the exit code rather than raising it, which is why
  :func:`main` returns and the ``__main__`` guard below raises. Keeping ``main``
  non-raising is also what lets the tests call it in-process.
* the convention is ``cw``'s default (``cw.ARGH``, i.e. argh's own
  ``BY_NAME_IF_HAS_DEFAULT``). The pre-migration code *tried* to select
  ``BY_NAME_IF_KWONLY``, but guarded the attempt with
  ``getattr(argh, "NameMappingPolicy", None)`` — a name argh does not export at its
  top level — so the guard always returned ``None`` and the CLI has only ever run on
  the default. Every current command has a bare positional and keyword-only options,
  a shape on which the two policies produce identical grammar; the default is kept
  because it is what shipped. Adding a parameter that is positional *and* has a
  default is where the two would diverge — see ``tests/test_cli.py``.
"""

from __future__ import annotations


def main(argv=None) -> int:
    """Dispatch a CLI command (see :mod:`illustration.cli`) and return its exit code."""
    import cw

    from illustration.cli import COMMANDS

    return cw.dispatch(COMMANDS, argv, prog="illustration")


if __name__ == "__main__":
    raise SystemExit(main())
