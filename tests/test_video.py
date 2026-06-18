"""Tests for illustration.video — the narration→Ken-Burns hook (offline).

The walkthru-document adapter is pure data (needs walkthru). The burns render
hook is tested with an injected render stub + image_loader stub, so no ffmpeg /
moviepy encode runs.
"""

import pytest

from illustration.schema import ImageResult
from illustration.sequence import BeatSelection, SequenceSelection


def _selection(ids_with_none):
    return SequenceSelection(
        selections=[
            BeatSelection(
                beat_index=i,
                chosen=None if x is None else ImageResult(provider="p", id=x, url=f"u{x}"),
            )
            for i, x in enumerate(ids_with_none)
        ]
    )


class TestRenderSequenceVideo:
    def test_builds_panels_and_calls_render(self):
        pytest.importorskip("burns")  # for ken_burns_path (pure-data, no encode)
        from illustration.video import render_sequence_video

        captured = {}

        def fake_render(panels, *, saveas, fps, audio_path):
            captured.update(panels=panels, saveas=saveas, fps=fps, audio_path=audio_path)
            return saveas

        out = render_sequence_video(
            _selection(["a", "b"]),
            saveas="film.mp4",
            durations=[3.0, 5.0],
            narration_audio="narr.mp3",
            image_loader=lambda img: f"PIL:{img.id}",
            render=fake_render,
        )
        assert out == "film.mp4"
        panels = captured["panels"]
        assert [p[0] for p in panels] == ["PIL:a", "PIL:b"]   # loaded images, in order
        assert [p[2] for p in panels] == [3.0, 5.0]            # per-beat durations
        assert captured["audio_path"] == "narr.mp3"
        # each panel carries a burns BurnsPath as its motion spec
        from burns import BurnsPath

        assert all(isinstance(p[1], BurnsPath) for p in panels)

    def test_skips_empty_beats(self):
        pytest.importorskip("burns")
        from illustration.video import render_sequence_video

        captured = {}
        render_sequence_video(
            _selection(["a", None, "c"]),
            saveas="film.mp4",
            image_loader=lambda img: f"PIL:{img.id}",
            render=lambda panels, **kw: captured.setdefault("panels", panels),
        )
        assert [p[0] for p in captured["panels"]] == ["PIL:a", "PIL:c"]

    def test_raises_when_nothing_to_render(self):
        pytest.importorskip("burns")
        from illustration.video import render_sequence_video

        with pytest.raises(ValueError, match="no chosen images"):
            render_sequence_video(_selection([None, None]), saveas="x.mp4")

    def test_raises_when_no_image_loads(self):
        pytest.importorskip("burns")
        from illustration.video import render_sequence_video

        with pytest.raises(ValueError, match="none of the chosen images"):
            render_sequence_video(
                _selection(["a", "b"]), saveas="x.mp4",
                image_loader=lambda img: None,  # every load fails
                render=lambda panels, **kw: "x",
            )

    def test_plain_list_input_and_durations_padding(self):
        pytest.importorskip("burns")
        from illustration.video import DFLT_PANEL_DURATION_S, render_sequence_video

        captured = {}
        images = [ImageResult(provider="p", id="a", url="ua"), ImageResult(provider="p", id="b", url="ub")]
        render_sequence_video(
            images, saveas="f.mp4", durations=[2.0],  # short list -> padded
            image_loader=lambda img: f"PIL:{img.id}",
            render=lambda panels, **kw: captured.setdefault("panels", panels),
        )
        panels = captured["panels"]
        assert [p[0] for p in panels] == ["PIL:a", "PIL:b"]  # plain list accepted
        assert panels[0][2] == 2.0 and panels[1][2] == DFLT_PANEL_DURATION_S  # padded


class TestToWalkthruDocument:
    def test_builds_broll_beats_with_posters_and_narration(self):
        pytest.importorskip("walkthru")
        from illustration.video import to_walkthru_document

        doc = to_walkthru_document(
            _selection(["a", "b"]),
            narration=["dawn breaks", "dusk settles"],
            durations=4.0,
            title="My storyboard",
        )
        steps = doc.sections[0].steps
        assert [s.beat_kind for s in steps] == ["broll", "broll"]
        assert [s.poster.uri for s in steps] == ["ua", "ub"]
        assert all(s.timing.duration_ms == 4000 for s in steps)
        narr = doc.tracks.narration
        assert [n.text for n in narr] == ["dawn breaks", "dusk settles"]
        assert narr[0].anchor.step_id == steps[0].id  # narration anchored to its beat

    def test_skips_empty_beats(self):
        pytest.importorskip("walkthru")
        from illustration.video import to_walkthru_document

        doc = to_walkthru_document(_selection(["a", None, "c"]))
        assert [s.poster.uri for s in doc.sections[0].steps] == ["ua", "uc"]
