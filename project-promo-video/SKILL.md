---
name: project-promo-video
description: Use when a user wants Codex to run a finished local app, capture polished screenshots, and turn them into a short Remotion-based promo video or trailer that matches the product's UI and tone.
---

# Project Promo Video

## Overview

Use this skill when the user already has a working product and wants a short marketing trailer assembled from real project screenshots. The workflow assumes the app can be run locally, the UI can be captured cleanly, and the final deliverable is a shareable video such as `mp4`.

This skill is best for web apps, dashboards, SaaS tools, landing pages, admin panels, and desktop-style product UIs. If the user wants classic video editing from existing footage instead of screenshot-driven scenes, use a different workflow.

The visual layout source of truth is the Guizang PPT skill. Remotion is used for timeline, BGM, narration, ducking, transitions, codec, final rendering, and frame-driven DOM animation inside the PPT sections. The default path renders PPT HTML directly in Remotion so the video keeps the exact PPT layout while Remotion drives `[data-anim]` elements with `useCurrentFrame`, `spring`, and `interpolate`.

## Required Inputs

- A runnable project with a real start command
- Access to the app in a browser or desktop window
- Either a screenshot directory or a running local app that can be captured
- A destination directory for the promo workspace
- Optional brand inputs such as product name, tagline, accent color, CTA, or custom background music

## Workflow

### 1. Run the product before planning the trailer

Inspect the project first. Use the real commands from `package.json`, `README`, `docker-compose.yml`, or framework conventions instead of guessing.

Aim for a stable capture environment:
- Use realistic data, not empty placeholders
- Hide dev toolbars, mock banners, and browser chrome
- Prepare accounts or seed data so key flows work immediately

If the app will not run, stop and report the blocker. Do not invent screenshots or continue to the video phase with assumptions.

### 2. Capture screenshots that sell the product

Use the bundled screenshot capture script when the project is already running and the key screens can be reached by URL plus light interaction.

Install the screenshot runtime once:

```bash
cd scripts
npm install
npx playwright install chromium
```

Run the capture script against the running app:

```bash
node scripts/capture_project_screenshots.mjs \
  --base-url http://127.0.0.1:3000 \
  --plan references/screenshot-plan.example.json \
  --output-dir <screenshot-dir>
```

This writes screenshots and `capture-manifest.json` to the target directory.

If the flow requires complex authentication, modal choreography, drag-and-drop, or highly dynamic state, switch to the separate `$playwright` skill for manual browser driving and then continue with the captured screenshot directory.

Capture these categories when possible:
- Hero or home state
- One core workflow entry point
- A detail page, editor, or builder
- A results, analytics, or reporting view
- A closing screen that feels like payoff or CTA

Rules:
- Keep the viewport consistent, usually `1440x900` or `1920x1080`
- Prefer 5-8 screenshots; more than 10 usually slows the pacing
- Capture real filled states, not empty shells
- Name files in final order with numeric prefixes such as `01-home.png`

### 3. Build a narrative and choose PPT layouts

Write a simple three-part shot list:
- Hook: what the product is
- Proof: 3-6 scenes that show concrete value
- Close: a final message or CTA

Keep the copy grounded in what the screenshots actually show. Then choose the PPT layout style:
- `editorial`: uses the style A electronic magazine layout system from `guizang-ppt-skill`.
- `swiss`: uses the Swiss locked layout system from `guizang-ppt-skill`.

For quick product trailers, the bootstrap script can generate a default deck:
- Editorial defaults: `A01`, alternating `A04/A10`, then `A07`.
- Swiss defaults: `SWISS-COVER-ASCII`, a rotating set of `S22/S15/S17/S21`, then `SWISS-CLOSING-ASCII`.

For full fidelity or any specific PPT layout, write a storyboard JSON with `sectionHtml` scenes. A `sectionHtml` scene is inserted into the PPT template verbatim and can use any registered PPT layout: `A01-A10`, `S01-S22`, or `S08_MAP`. Experimental `P23/P24` should only be used when the user explicitly asks for experimental layouts.

When the trailer is based on an article, README, launch note, or product brief, pass that source with `--brief-file`. The generated narration scaffold must be grounded in that content. Do not let the final copy stay as screenshot filename filler; edit `voiceover-script.json` and `promo-data.ts` until the spoken line, visual claim, and project scenario agree.

### 4. Bootstrap the bundled Remotion workspace

This skill ships with `assets/remotion-template`, a minimal trailer template inspired by the composition-driven structure used in [andchir/remotion-animations](https://github.com/andchir/remotion-animations). The template consumes PPT sections directly by default. Rendered slide images are still produced for QA and fallback, but the primary render mode is PPT DOM inside Remotion.

Create a working copy and prepare the promo data with:

```bash
python scripts/bootstrap_promo_project.py \
  --workspace <output-dir> \
  --screenshots <screenshot-dir> \
  --project-name "Acme" \
  --tagline "Close work faster" \
  --accent "#14b8a6"
```

Use the Swiss PPT layout system when the user asks for Swiss Style, grid-heavy data storytelling, or strict PPT-layout fidelity:

```bash
python scripts/bootstrap_promo_project.py \
  --workspace <output-dir> \
  --screenshots <screenshot-dir> \
  --layout-style swiss \
  --project-name "Acme" \
  --tagline "Close work faster"
```

Use a storyboard when the video must use specific PPT layouts:

```bash
python scripts/bootstrap_promo_project.py \
  --workspace <output-dir> \
  --screenshots <screenshot-dir> \
  --storyboard storyboard.json
```

Control how finely the PPT DOM is split for animation:

```bash
python scripts/bootstrap_promo_project.py \
  --workspace <output-dir> \
  --screenshots <screenshot-dir> \
  --motion-detail glyph
```

Motion detail options:
- `normal`: visible leaf nodes and readable text phrases.
- `fine`: more phrase-level text units.
- `glyph`: title and short text are split per character; body copy stays readable.
- `max`: attempts character-level splitting for all text. Use only for short, low-text slides.

Use an article, README, or brief to ground the copy and voiceover:

```bash
python scripts/bootstrap_promo_project.py \
  --workspace <output-dir> \
  --screenshots <screenshot-dir> \
  --layout-style swiss \
  --brief-file project-article.md \
  --scenario "project launch video" \
  --copy-language zh
```

Background music is **added automatically** using a CC0-licensed default track (downloaded on first run). To use a custom track instead, pass `--bgm-file <path-to-music>`. To explicitly skip background music, pass `--no-bgm`.

The bootstrap script:
- Copies `assets/remotion-template` into the target workspace without overwriting existing user edits
- Copies screenshots into `public/screenshots`
- Builds `public/ppt/index.html` from the Guizang PPT template
- Extracts the selected PPT template CSS into `src/ppt-template.css`
- Writes each PPT section into `src/promo-data.ts` as `pptScenes[].html`
- Renders each PPT page into `public/slides/*.png` with Playwright for QA/fallback
- Downloads and wires default background music (or copies a custom file)
- Generates `src/promo-data.ts`
- Generates `src/audio-config.ts`
- Generates `public/audio/voiceover-script.json`
- Generates initial per-scene `beats` so motion has a narration-aligned timeline
- Compiles PPT HTML into `motionUnits` with `data-motion-id` attributes for fine-grained DOM animation
- Generates `public/screenshots/manifest.json`
- Generates `public/slides/render-manifest.json`

After it runs, always review `public/ppt/index.html`, `src/ppt-template.css`, `public/slides/render-manifest.json`, and `src/promo-data.ts`. The generated titles and subtitles are only a starting point unless they were supplied by a curated storyboard.

### 5. Generate voiceover when the trailer needs narration

This skill includes an Edge TTS workflow inspired by the scene-based timing approach used in `wshuyi/remotion-video-skill`.

Install the dependency once:

```bash
pip install edge-tts
```

Then generate narration for the prepared workspace:

```bash
python scripts/generate_voiceover_edge.py \
  --workspace <output-dir>
```

What it does:
- Reads `public/audio/voiceover-script.json`
- Generates one `mp3` per scene into `public/audio/voiceover/`
- Uses `ffprobe` to measure duration
- Rewrites `src/audio-config.ts` so scene length follows the spoken audio
- Reallocates each scene's `beats` across the measured narration duration so visual motion continues until the voiceover ends
- Reallocates `motionUnits` across the measured beats so individual DOM nodes and title glyphs keep moving with narration
- Writes `public/audio/motion-timeline.json` for QA, including scene durations, audio files, and beat start/end frames
- Uses the script's voice setting when present, otherwise auto-selects a Chinese or English Edge voice from the scene text

### 6. Refine motion and render

From the generated Remotion workspace:

```bash
npm install
npm run start
npm run render
```

Default output:
- `out/product-promo.mp4`

Edit these files when the first pass is too generic:
- `public/ppt/index.html` for layout-level changes when using raw PPT sections
- `src/promo-data.ts` for PPT DOM sections, rendered slide fallback order, transition choice, and BGM settings
- `src/audio-config.ts` for scene-level timing
- `public/audio/motion-timeline.json` for checking whether beats cover the whole voiceover scene
- `src/components/PptDomScene.tsx` for Remotion-driven PPT DOM motion recipes
- `src/ppt-video-motion.css` for persistent PPT DOM motion overrides
- `remotion.config.ts` for codec defaults

Built-in audio behavior:
- Background music fades in at the start and out at the end
- Background music ducks automatically during voiceover scenes
- Scene timing follows `src/audio-config.ts`, not fixed shot defaults, once narration is generated

Built-in motion behavior:
- `ppt-dom` mode keeps the PPT section DOM live inside Remotion
- `[data-anim]` elements receive deterministic staggered spring entrances driven by the scene's narration beats
- `motionUnits` drive per-node animation through `data-motion-id`; in `glyph` mode, titles and short labels are split into character spans
- Each beat targets a PPT element family such as title, body, image, cards, diagram, KPI, bars, or rule lines
- The last beat is stretched to the scene end so the visual layer does not become static while narration is still playing
- Known PPT recipes such as `image-hero`, `matrix-fill`, `system-diagram`, `timeline-walk`, and `tech-spec` get extra line draw, card cascade, SVG reveal, chart growth, and image parallax
- `--render-mode slides` is available only as a fallback when a browser-only PPT section cannot be safely embedded in Remotion

### 7. Final QA

Check the render for:
- Cropped UI or unreadable text
- Claims in the copy that the screenshots do not support
- Scene order that does not match the real user journey
- PPT layout fidelity: correct registered layout, grid alignment, image ratios, and safe areas
- Shots that linger too long before revealing value
- Voiceover that ends too early or too late for the visual scene
- Background music that competes with narration
- Remotion motion happening inside the PPT layout, not only as a post-process over a flat screenshot

For Swiss decks, also run the PPT validator against `public/ppt/index.html` when the validator is available:

```bash
node <guizang-ppt-skill>/scripts/validate-swiss-deck.mjs <output-dir>/public/ppt/index.html
```

If the result feels generic, fix the PPT section layout first, then copy, then pacing, then motion polish.

## Output Contract

Successful use of this skill should produce:
- A runnable Remotion promo workspace
- A rendered `mp4`
- A PPT deck at `public/ppt/index.html`
- Rendered slide assets at `public/slides/*.png`
- PPT DOM scene data at `src/promo-data.ts`
- Extracted PPT CSS at `src/ppt-template.css`
- A screenshot manifest plus edited scene copy
- A short summary of what was captured and what source screens still need improvement

## Failure Handling

- If the app cannot start, report the exact command and error and stop there.
- If screenshots are low quality or incomplete, capture better states before refining animation.
- If slide rendering fails, open `public/ppt/index.html` first and fix invalid PPT section HTML before changing Remotion.
- If Remotion is missing, use the bundled template instead of switching stacks.
- If the user wants transparent overlays instead of a standard promo video, switch the render target to WebM/VP9 rather than the default MP4 settings.

## Resources

- `scripts/bootstrap_promo_project.py`
  Creates a working Remotion promo project, PPT deck, PPT DOM scene data, rendered slide QA assets, automatic BGM, and voiceover scaffolding.
- `scripts/capture_project_screenshots.mjs`
  Collects screenshots from a running local app into a local directory using Playwright.
- `scripts/generate_voiceover_edge.py`
  Generates per-scene narration with Edge TTS, rewrites `src/audio-config.ts`, and writes `public/audio/motion-timeline.json`.
- `scripts/render_ppt_slides.mjs`
  Renders PPT HTML slides into `public/slides/*.png` for Remotion playback.
- `references/ppt-layout-video.md`
  Explains the PPT layout compatibility pipeline and storyboard format.
- `references/ppt-layout-manifest.json`
  Lists supported PPT layout IDs and their source files.
- `references/screenshot-capture.md`
  Describes when to use the built-in capture script and the JSON plan format.
- `references/screenshot-plan.example.json`
  Example capture plan for a running local app.
- `references/remotion-notes.md`
  Notes about the reference repo and when to use MP4 vs transparent output.
- `references/audio-notes.md`
  Notes about the borrowed scene-audio workflow and open-license music sourcing.
- `assets/remotion-template/`
  Minimal Remotion template for screenshot-based promo videos.
