"""Narration → Ken-Burns video hook — the M4 integration seam.

illustration's job ends at *choosing* the images (see :mod:`illustration.sequence`);
turning an ordered set of stills + narration into a pan/zoom video is the
ecosystem's job. This module is the thin hook into it, in two flavours (both
opt-in, behind the ``[video]`` extra, both lazy-imported):

1. :func:`render_sequence_video` — the **direct convenience**: selections →
   ``[(image, ken_burns_path, duration)]`` → ``burns.ken_burns_film``. Uses
   ``burns`` directly (pure substrate, the same renderer ``walkthru`` uses) — it
   deliberately does **not** route through ``walkthru``'s reelee render target,
   which would risk an ``illustration → reelee → illustration`` cycle. Narration
   audio is supplied pre-built (e.g. from ``mixing`` or ``walkthru``).

2. :func:`to_walkthru_document` — the **pure-data adapter**: build a
   ``walkthru.DemoDocument`` (one b-roll beat per chosen image, poster slots
   filled, narration track populated) that a ``walkthru``-using consumer (reelee)
   can pace, TTS, caption, and render its own way. No rendering happens here.

>>> # the data adapter is pure (needs walkthru); the render hook needs burns+ffmpeg
>>> import importlib.util
>>> bool(importlib.util.find_spec("walkthru"))                    # doctest: +SKIP
True
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from illustration.schema import ImageResult

__all__ = [
    "render_sequence_video",
    "to_walkthru_document",
    "DFLT_PANEL_DURATION_S",
    "DFLT_FPS",
]

#: Default per-beat on-screen duration (seconds) when none is supplied.
DFLT_PANEL_DURATION_S = 4.0
#: Default frame rate for the rendered film.
DFLT_FPS = 30


def render_sequence_video(
    selections: Any,
    *,
    saveas: str,
    durations: "float | Sequence[float]" = DFLT_PANEL_DURATION_S,
    narration_audio: "str | None" = None,
    fps: int = DFLT_FPS,
    style: str = "push",
    output_aspect: "float | None" = None,
    image_loader: "Callable[[ImageResult], Any] | None" = None,
    render: "Callable[..., Any] | None" = None,
) -> Any:
    """Render chosen images into a single Ken-Burns film via ``burns``.

    ``selections`` may be a :class:`~illustration.sequence.SequenceResult`, a
    :class:`~illustration.sequence.SequenceSelection`, or a plain list of
    :class:`~illustration.schema.ImageResult`. Each image gets an auto motion
    path (``burns.ken_burns_path``, alternating push/pull for rhythm) and its
    ``durations`` slice; ``narration_audio`` (a pre-built track) is muxed in.
    Beats with no chosen image are skipped.

    Seams: ``image_loader`` fetches an image to a PIL image (default: the shared
    cached fetch — ``burns`` decodes PIL, not URLs); ``render`` is the renderer
    (default: ``burns.ken_burns_film``) — inject a stub to test without ffmpeg.
    Returns whatever ``render`` returns (the output path for the default).
    """
    images = _chosen_images(selections)
    if not any(img is not None for img in images):
        raise ValueError("no chosen images to render (every beat was empty)")
    durs = _durations(durations, len(images))
    load = image_loader if image_loader is not None else _default_image_loader()
    render_fn = render if render is not None else _default_render()

    from burns import ken_burns_path

    panels = []
    panel_index = 0
    for img, dur in zip(images, durs):
        if img is None:  # skip empty beats — the loader never sees a None
            continue
        loaded = load(img)
        if loaded is None:
            continue
        panel_index += 1  # 1-based position drives ken_burns_path's motion rhythm
        path = ken_burns_path(panel_index, style=style, output_aspect=output_aspect)
        panels.append((loaded, path, float(dur)))
    if not panels:
        raise ValueError("none of the chosen images could be loaded for rendering")
    return render_fn(panels, saveas=saveas, fps=fps, audio_path=narration_audio)


def to_walkthru_document(
    selections: Any,
    *,
    narration: "Sequence[str] | None" = None,
    durations: "float | Sequence[float]" = DFLT_PANEL_DURATION_S,
    doc_id: str = "illustration-storyboard",
    title: "str | None" = None,
) -> Any:
    """Build a ``walkthru.DemoDocument`` from the selections (pure data, no render).

    Emits one b-roll beat per chosen image (``poster`` = the image URL,
    ``timing`` from ``durations``) and, if ``narration`` is given (one string per
    beat), a narration track anchored to each beat. The consumer then runs
    ``walkthru.realize_narration`` / ``pace_steps_to_narration`` / its renderer.
    Beats with no chosen image are skipped. Needs the ``[video]`` extra.
    """
    from walkthru import (
        AssetRef, Beat, DemoDocument, Meta, NarrationAnchor, NarrationSegment,
        Section, Timing, Tracks,
    )

    images = _chosen_images(selections)
    beats_text = _beats_text(selections)
    durs_ms = [int(d * 1000) for d in _durations(durations, len(images))]

    steps = []
    narration_segs = []
    for i, (img, dur_ms) in enumerate(zip(images, durs_ms)):
        if img is None:
            continue
        beat_id = f"beat-{i}"
        text = beats_text[i] if i < len(beats_text) else None
        steps.append(
            Beat(
                id=beat_id, beat_kind="broll", timing=Timing(duration_ms=dur_ms),
                text=text, poster=AssetRef(uri=img.url, mime=_guess_mime(img.url)),
            )
        )
        if narration is not None and i < len(narration) and narration[i]:
            narration_segs.append(
                NarrationSegment(
                    id=f"narr-{i}", text=narration[i],
                    anchor=NarrationAnchor(step_id=beat_id, duration_ms=dur_ms),
                )
            )

    return DemoDocument(
        id=doc_id,
        meta=Meta(title=title or "Illustrated storyboard"),
        sections=[Section(id="main", steps=steps)],
        tracks=Tracks(narration=narration_segs),
    )


# --- internals --------------------------------------------------------------


def _chosen_images(selections: Any) -> "list[ImageResult | None]":
    """Coerce the supported input shapes to an ordered list of chosen images."""
    # SequenceResult -> .selection.chosen ; SequenceSelection -> .chosen
    sel = getattr(selections, "selection", selections)
    chosen = getattr(sel, "chosen", None)
    if chosen is not None:
        return list(chosen)
    return [_as_image(x) for x in selections]


def _beats_text(selections: Any) -> list[str]:
    beats = getattr(selections, "beats", None)
    return list(beats) if beats else []


def _as_image(x: Any) -> "ImageResult | None":
    if x is None or isinstance(x, ImageResult):
        return x
    return getattr(x, "chosen", None)  # a BeatSelection


def _durations(durations: "float | Sequence[float]", n: int) -> list[float]:
    if isinstance(durations, (int, float)):
        return [float(durations)] * n
    durs = list(durations)
    if len(durs) < n:
        durs = durs + [DFLT_PANEL_DURATION_S] * (n - len(durs))
    return durs[:n]


def _default_image_loader() -> "Callable[[ImageResult], Any]":
    from illustration._imageio import fetch_image

    def load(result: "ImageResult | None"):
        if result is None:
            return None
        return fetch_image(result.url or "") or (
            fetch_image(result.thumbnail_url) if result.thumbnail_url else None
        )

    return load


def _default_render() -> "Callable[..., Any]":
    from burns import ken_burns_film

    return ken_burns_film


def _guess_mime(url: str) -> "str | None":
    import mimetypes

    return mimetypes.guess_type(url or "")[0]
