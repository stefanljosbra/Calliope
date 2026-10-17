# Calliope 1.6.0 — continue a clip from the previous clip's H3 latent

Release **v1.6.0**, 2026-10-16. Together with the [CLI authoring bridge](./2026-10-06-cli-authoring-bridge.md). Includes merged [PR #97](https://github.com/benjiyaya/Calliope/pull/97) by @Pendair (merge `3bc456c`).

A clip can continue the clip before it when the workflow uses [ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context). Calliope pins the previous clip's saved audio-video latent at the head of the new clip, so motion and sound carry across the join. Workflows without that Load/Save latent pair render and export exactly as they do today.

The pack must include the Load Latent `folder` widget and Save Latent reporting `ui.latents` ([ComfyUI-H3-Motion-Context#53](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context/pull/53)). An older pack makes a continuing job fail with a message that names the update. A workflow that does not use the nodes is left alone.

## What you do

- Tag the pack's Load Latent node `(Input:latent)` and its Save Latent node `(Output:latent)`. Calliope also recognizes those two classes with no tag. Neither slot is a file picker. The form says the chain fills it.
- The first clip always starts a chain. Any later clip continues the one immediately before it in playback order, including across scenes, unless you tick **Start a new chain here**. That checkbox appears only on a workflow that has a Load Latent slot.
- **Generate all** queues the later clip and waits until the previous clip has finished. If the previous clip has no saved latent, the job fails and names both clips.
- After each render, Calliope downloads the Save node's latent over ComfyUI's HTTP API into `assets/<project>/latent/`. Before a continuing render, it uploads that file and points Load Latent at ComfyUI's input folder. Calliope still does not read or write ComfyUI's own folders.
- Re-rendering a clip leaves the clips that continued it in place and marks them stale, so you can re-render those too. Choosing an older render from a clip's history restores that render's latent.
- Film export uses a hard cut on a join where the second clip continued the first. Every other join keeps the 0.5 s crossfade. A film with no continuations keeps the previous crossfade timing.

## Also in the pull request

- New `latent` input and output roles.
- Example workflows under `example_ComfyUI_workflows/MiniMaxH3-Singularity-Continuity-*` (1–5 reference images, with and without a Load Latent slot). They name the author's Singularity model files, so import one only if those models are installed.
- `Continuation-example.mp4` at the repo root, a short film exported from a chained project.
- Agent skill `skills_builtin/h3-continuation-prompt/` for prompt rules on a continuing clip (same subject labels, open mid-action, no new scenery in the first moments, timestamps shifted for the pinned frames).
- No schema migration. Chain state lives in the existing `clips.video_settings_json`.

## Limits

- Both clips of a join must be the same resolution. The pack refuses a mismatch, and the job shows that error.
- The chain follows playback order only. Reordering clips changes what continues what, and the UI marks the affected clips stale.
- Turn Spectrum (`SpectrumApplyMiniMaxH3`) off in continuation workflows. The Motion Context pack says pinned frames should not go through it.
- Moving the data folder rebases paths stored in `input_values`. It does not yet rebase `latent_path` inside the same clip settings, so a moved install needs those clips rendered again before the next one can continue them.
