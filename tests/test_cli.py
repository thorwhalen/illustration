"""Tests for the CLI wrappers and the ``cw`` dispatcher (offline, via a fake source).

The ``TestCliGrammar`` class at the bottom is a characterization suite: every
assertion in it was recorded from the pre-migration ``argh`` implementation, so the
published command line cannot drift silently.
"""

import argparse
import dataclasses
import json
import os
import subprocess
import sys

import pytest

import cw
from illustration import cli
from illustration.__main__ import main
from illustration.base import RetrievalSource
from illustration.registry import register_source, unregister_source
from illustration.schema import ImageResult


class _CliSource(RetrievalSource):
    name = "clisrc"

    def _items(self, response):  # pragma: no cover
        return []

    def _normalize(self, item, *, query):  # pragma: no cover
        ...

    def search(self, query, *, n=10, api_key=None, native_params=None, **canonical):
        return [
            ImageResult(provider="clisrc", id=str(i), url=f"u{i}", title=f"Title {i}",
                        license="cc0", query=query)
            for i in range(n)
        ]


def test_cli_sources_lists_builtins():
    out = cli.sources()
    assert "openverse" in out and "pexels" in out


def test_cli_info_returns_json():
    out = cli.info("openverse")
    data = json.loads(out)
    assert data["name"] == "openverse" and data["requires_key"] is False


def test_cli_search_text(monkeypatch, tmp_path):
    monkeypatch.setenv("ILLUSTRATION_CACHE_DIR", str(tmp_path))
    register_source(_CliSource())
    try:
        out = cli.search("harbour", n=2, source="clisrc")
    finally:
        unregister_source("clisrc")
    assert "[clisrc]" in out
    assert "Title 0" in out and "cc0" in out


def test_cli_search_json(monkeypatch, tmp_path):
    monkeypatch.setenv("ILLUSTRATION_CACHE_DIR", str(tmp_path))
    register_source(_CliSource())
    try:
        out = cli.search("harbour", n=1, source="clisrc", json=True)
    finally:
        unregister_source("clisrc")
    data = json.loads(out)
    assert data[0]["provider"] == "clisrc"


class _EmptyCliSource(RetrievalSource):
    name = "emptyclisrc"

    def _items(self, response):  # pragma: no cover
        return []

    def _normalize(self, item, *, query):  # pragma: no cover
        ...

    def search(self, query, *, n=10, api_key=None, native_params=None, **canonical):
        return []


def test_cli_search_no_results(monkeypatch, tmp_path):
    monkeypatch.setenv("ILLUSTRATION_CACHE_DIR", str(tmp_path))
    register_source(_EmptyCliSource())
    try:
        out = cli.search("nothing", source="emptyclisrc")
    finally:
        unregister_source("emptyclisrc")
    assert out == "(no results)"


def test_main_dispatch_sources(capsys):
    """Smoke-test the dispatcher end-to-end (python -m illustration sources)."""
    assert main(["sources"]) == 0
    out = capsys.readouterr().out
    assert "openverse" in out


COMMAND_NAMES = ("search", "curate", "curate-sequence", "sources", "info")


def _parser():
    """The very parser :func:`illustration.__main__.main` dispatches."""
    return cw.mk_parser(cli.COMMANDS, prog="illustration")


def _subparsers(parser):
    action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    return action.choices


def _run(*argv):
    """Run ``python -m illustration ARGV`` end to end."""
    env = {k: v for k, v in os.environ.items() if k != "COLUMNS"}
    return subprocess.run(
        [sys.executable, "-m", "illustration", *argv],
        capture_output=True,
        text=True,
        env={"COLUMNS": "80", **env},
    )


class TestCliGrammar:
    """Characterization of the published command line, recorded from ``argh``."""

    def test_the_commands_list_is_what_reaches_the_parser(self):
        assert tuple(_subparsers(_parser())) == COMMAND_NAMES
        assert _parser().format_usage() == (
            "usage: illustration [-h]"
            " {search,curate,curate-sequence,sources,info} ...\n"
        )

    @pytest.mark.parametrize(
        "command, usage",
        [
            (
                "search",
                "usage: illustration search [-h] [-n N] [--source SOURCE]"
                " [-o ORIENTATION] [--size SIZE] [--safe] [-l LICENSE_TYPE] [-j]"
                " query",
            ),
            (
                "curate",
                "usage: illustration curate [-h] [-s SOURCE] [-n N]"
                " [--max-iter MAX_ITER] [--model MODEL] [-j] beat",
            ),
            (
                "curate-sequence",
                "usage: illustration curate-sequence [-h] [-s SOURCE] [-n N] [-j]"
                " [beats ...]",
            ),
            ("sources", "usage: illustration sources [-h]"),
            ("info", "usage: illustration info [-h] name"),
        ],
    )
    def test_each_subcommand_keeps_its_recorded_usage_line(self, command, usage):
        """Flag spellings and short options, exactly as argh rendered them.

        Three details worth naming, because a rewrite loses them silently:
        ``--source`` and ``--size`` get **no** short flag under ``search`` (they
        collide on ``-s``), and neither does ``--max-iter`` under ``curate`` (it
        collides with ``--model`` on ``-m``) -- yet ``--source`` *does* get ``-s``
        under ``curate``, where nothing competes for it; and ``--safe`` is a bare flag
        (``safe=True`` becomes ``store_false``), not an option taking a value.
        """
        got = " ".join(_subparsers(_parser())[command].format_usage().split())
        assert got == usage

    def test_curate_sequence_takes_zero_or_more_beats(self):
        """``*beats`` is ``nargs='*'``: no beats is a valid invocation, not an error."""
        sub = _subparsers(_parser())["curate-sequence"]
        assert getattr(sub.parse_args([]), "beats") == []
        assert getattr(sub.parse_args(["a", "b"]), "beats") == ["a", "b"]

    def test_safe_is_a_flag_that_turns_the_default_off(self):
        sub = _subparsers(_parser())["search"]
        assert sub.parse_args(["q"]).safe is True
        assert sub.parse_args(["q", "--safe"]).safe is False

    def test_the_naming_policy_is_behaviourally_moot_for_these_signatures(self):
        """Pins the finding that justified keeping ``cw``'s default convention.

        The pre-migration code tried to select ``BY_NAME_IF_KWONLY`` but guarded it
        with ``getattr(argh, "NameMappingPolicy", None)``, which argh does not export
        at its top level -- so the guard always returned ``None`` and the CLI shipped
        on the **default** policy. That is what this migration preserved.

        It is safe precisely because every command here takes a bare positional and
        keyword-only options, a shape on which the two policies agree. Add a parameter
        that is positional *and* has a default and they diverge -- at which point this
        test goes red and the choice has to be made deliberately.
        """
        kwonly = dataclasses.replace(cw.ARGH, naming=cw.BY_NAME_IF_KWONLY)
        default_parser = _parser()
        kwonly_parser = cw.mk_parser(
            cli.COMMANDS, prog="illustration", convention=kwonly
        )

        def surface(parser):
            subs = _subparsers(parser)
            return [parser.format_help()] + [s.format_help() for s in subs.values()]

        assert surface(default_parser) == surface(kwonly_parser)

    # ------------------------------------------------------------------ exit codes

    def test_no_arguments_prints_usage_to_stdout_and_exits_zero(self):
        """argh's behaviour, which bare argparse does not reproduce."""
        done = _run()
        assert done.returncode == 0
        assert done.stdout.startswith("usage: illustration ")
        assert done.stderr == ""

    @pytest.mark.parametrize(
        "argv",
        [
            ("no-such-command",),
            ("search",),  # missing required positional
            ("info",),  # missing required positional
            ("search", "x", "--n"),  # option missing its value
            ("search", "x", "--n", "notanint"),  # wrong type
        ],
    )
    def test_bad_invocations_exit_two(self, argv):
        done = _run(*argv)
        assert done.returncode == 2
        assert done.stdout == ""
        assert done.stderr.startswith("usage: illustration ")

    def test_main_returns_the_exit_code_rather_than_swallowing_it(self):
        """``main()`` yields an int, so ``sys.exit(main())`` reports the failure.

        The console script wraps ``main`` in ``sys.exit``; the ``__main__`` guard
        raises it. Both need the value, and nothing else in this suite checks it.
        """
        assert main(["no-such-command"]) == 2
        assert main(["sources"]) == 0

    def test_prog_stays_pinned_to_illustration(self):
        """``prog=`` was pinned before the migration, so it stays pinned.

        Without it ``python -m illustration --help`` would start reporting
        ``__main__.py``.
        """
        done = _run("--help")
        assert done.returncode == 0
        assert done.stdout.startswith("usage: illustration ")
