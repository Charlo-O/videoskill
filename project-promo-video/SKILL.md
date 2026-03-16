---
name: project-promo-video
description: Use when a user wants Codex to run a finished local app, capture polished screenshots, and turn them into a short Remotion-based promo video or trailer that matches the product's UI and tone.
---

# Project Promo Video

## Overview

Use this skill when the user already has a working product and wants a short marketing trailer assembled from real project screenshots. The workflow assumes the app can be run locally, the UI can be captured cleanly, and the final deliverable is a shareable video such as `mp4`.

This skill is best for web apps, dashboards, SaaS tools, landing pages, admin panels, and desktop-style product UIs. If the user wants classic video editing from existing footage instead of screenshot-driven scenes, use a different workflow.

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

### 3. Build a narrative before touching animation

Write a simple three-part shot list:
- Hook: what the product is
- Proof: 3-6 scenes that show concrete value
- Close: a final message or CTA

Keep the copy grounded in what the screenshots actually show. Match the motion style to the product:
- Enterprise or data products: clean transitions, restrained typography, direct copy
- Creative or consumer products: stronger color, faster pacing, more expressive motion

### 4. Bootstrap the bundled Remotion workspace

This skill ships with `assets/remotion-template`, a minimal trailer template inspired by the composition-driven structure used in [andchir/remotion-animations](https://github.com/andchir/remotion-animations).

Create a working copy and prepare the promo data with:

```bash
python scripts/bootstrap_promo_project.py \
  --workspace <output-dir> \
  --screenshots <screenshot-dir> \
  --project-name "Acme" \
  --tagline "Close work faster" \
  --accent "#14b8a6"
```

Background music is **added automatically** using a CC0-licensed default track (downloaded on first run). To use a custom track instead, pass `--bgm-file <path-to-music>`. To explicitly skip background music, pass `--no-bgm`.

The bootstrap script:
- Copies `assets/remotion-template` into the target workspace without overwriting existing user edits
- Copies screenshots into `public/screenshots`
- Downloads and wires default background music (or copies a custom file)
- Generates `src/promo-data.ts`
- Generates `src/audio-config.ts`
- Generates `public/audio/voiceover-script.json`
- Generates `public/screenshots/manifest.json`

After it runs, always review `src/promo-data.ts`. The generated titles come from file names and are only a starting point.

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
- `src/promo-data.ts` for copy, accent, screenshot text, and BGM settings
- `src/audio-config.ts` for scene-level timing
- `src/components/ProductPromo.tsx` for layout or transitions
- `remotion.config.ts` for codec defaults

Built-in audio behavior:
- Background music fades in at the start and out at the end
- Background music ducks automatically during voiceover scenes
- Scene timing follows `src/audio-config.ts`, not fixed shot defaults, once narration is generated

### 7. Final QA

Check the render for:
- Cropped UI or unreadable text
- Claims in the copy that the screenshots do not support
- Scene order that does not match the real user journey
- Shots that linger too long before revealing value
- Voiceover that ends too early or too late for the visual scene
- Background music that competes with narration

If the result feels generic, fix the copy first, then pacing, then motion polish.

## Output Contract

Successful use of this skill should produce:
- A runnable Remotion promo workspace
- A rendered `mp4`
- A screenshot manifest plus edited scene copy
- A short summary of what was captured and what source screens still need improvement

## Failure Handling

- If the app cannot start, report the exact command and error and stop there.
- If screenshots are low quality or incomplete, capture better states before refining animation.
- If Remotion is missing, use the bundled template instead of switching stacks.
- If the user wants transparent overlays instead of a standard promo video, switch the render target to WebM/VP9 rather than the default MP4 settings.

## Resources

- `scripts/bootstrap_promo_project.py`
  Creates a working Remotion promo project with automatic BGM and voiceover scaffolding.
- `scripts/capture_project_screenshots.mjs`
  Collects screenshots from a running local app into a local directory using Playwright.
- `scripts/generate_voiceover_edge.py`
  Generates per-scene narration with Edge TTS and rewrites `src/audio-config.ts`.
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
