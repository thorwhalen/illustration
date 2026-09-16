# illustration.video

Narration → Ken-Burns video hook — the M4 integration seam.

illustration’s job ends at *choosing* the images (see [`illustration.sequence`](illustration.sequence.html.md#module-illustration.sequence));
turning an ordered set of stills + narration into a pan/zoom video is the
ecosystem’s job. This module is the thin hook into it, in two flavours (both
opt-in, behind the `[video]` extra, both lazy-imported):

1. [`render_sequence_video()`](#illustration.video.render_sequence_video) — the **direct convenience**: selections →
   `[(image, ken_burns_path, duration)]` → `burns.ken_burns_film`. Uses
   `burns` directly (pure substrate, the same renderer `walkthru` uses) — it
   deliberately does **not** route through `walkthru`’s reelee render target,
   which would risk an `illustration → reelee → illustration` cycle. Narration
   audio is supplied pre-built (e.g. from `mixing` or `walkthru`).
2. [`to_walkthru_document()`](#illustration.video.to_walkthru_document) — the **pure-data adapter**: build a
   `walkthru.DemoDocument` (one b-roll beat per chosen image, poster slots
   filled, narration track populated) that a `walkthru`-using consumer (reelee)
   can pace, TTS, caption, and render its own way. No rendering happens here.

```pycon
>>> # the data adapter is pure (needs walkthru); the render hook needs burns+ffmpeg
>>> import importlib.util
>>> bool(importlib.util.find_spec("walkthru"))
True
```

### Module Attributes

| [`DFLT_PANEL_DURATION_S`](#illustration.video.DFLT_PANEL_DURATION_S)   | Default per-beat on-screen duration (seconds) when none is supplied.   |
|--------------------------------------------------------------------------|------------------------------------------------------------------------|
| [`DFLT_FPS`](#illustration.video.DFLT_FPS)                | Default frame rate for the rendered film.                              |

### Functions

| [`render_sequence_video`](#illustration.video.render_sequence_video)(selections, \*, saveas)   | Render chosen images into a single Ken-Burns film via `burns`.              |
|--------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| [`to_walkthru_document`](#illustration.video.to_walkthru_document)(selections, \*[, ...])     | Build a `walkthru.DemoDocument` from the selections (pure data, no render). |

### illustration.video.DFLT_FPS *= 30*

Default frame rate for the rendered film.

### illustration.video.DFLT_PANEL_DURATION_S *= 4.0*

Default per-beat on-screen duration (seconds) when none is supplied.

### illustration.video.render_sequence_video(selections, , saveas, durations=4.0, narration_audio=None, fps=30, style='push', output_aspect=None, image_loader=None, render=None)

Render chosen images into a single Ken-Burns film via `burns`.

`selections` may be a [`SequenceResult`](illustration.sequence.html.md#illustration.sequence.SequenceResult), a
[`SequenceSelection`](illustration.sequence.html.md#illustration.sequence.SequenceSelection), or a plain list of
[`ImageResult`](illustration.schema.html.md#illustration.schema.ImageResult). Each image gets an auto motion
path (`burns.ken_burns_path`, alternating push/pull for rhythm) and its
`durations` slice; `narration_audio` (a pre-built track) is muxed in.
Beats with no chosen image are skipped.

Seams: `image_loader` fetches an image to a PIL image (default: the shared
cached fetch — `burns` decodes PIL, not URLs); `render` is the renderer
(default: `burns.ken_burns_film`) — inject a stub to test without ffmpeg.
Returns whatever `render` returns (the output path for the default).

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### illustration.video.to_walkthru_document(selections, , narration=None, durations=4.0, doc_id='illustration-storyboard', title=None)

Build a `walkthru.DemoDocument` from the selections (pure data, no render).

Emits one b-roll beat per chosen image (`poster` = the image URL,
`timing` from `durations`) and, if `narration` is given (one string per
beat), a narration track anchored to each beat. The consumer then runs
`walkthru.realize_narration` / `pace_steps_to_narration` / its renderer.
Beats with no chosen image are skipped. Needs the `[video]` extra.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)
