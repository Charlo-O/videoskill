# Screenshot Capture

Read this file when the user wants the skill to collect screenshots from a running local project instead of preparing them manually.

## When to use the bundled capture script

Use `scripts/capture_project_screenshots.mjs` when:
- the project is already running on a local URL
- the screens can be reached by URL plus a small amount of scripted interaction
- you want deterministic local screenshots written to disk

For flows that require complex auth, MFA, drag-and-drop, or highly dynamic UI state, switch to the separate `$playwright` skill and use it to drive the browser manually.

## Runtime setup

Install the screenshot runtime once:

```bash
cd project-promo-video/scripts
npm install
npx playwright install chromium
```

## Capture command

```bash
node capture_project_screenshots.mjs \
  --base-url http://127.0.0.1:3000 \
  --plan ../references/screenshot-plan.example.json \
  --output-dir F:\captures
```

Outputs:
- numbered screenshot files such as `01-home.png`
- `capture-manifest.json`

## Plan format

Top-level fields:
- `viewport`: viewport size when no device preset is used
- `waitUntil`: navigation wait mode, usually `networkidle`
- `waitAfterNavigationMs`: extra delay after each navigation
- `hideSelectors`: selectors to hide globally before screenshots
- `shots`: array of capture steps

Each shot supports:
- `name`: output file name, `.png` is added automatically if omitted
- `path`: route relative to `--base-url`
- `waitForSelector`: selector that must appear before capture
- `waitForState`: optional Playwright state, default `visible`
- `waitAfterNavigationMs`: per-shot override
- `waitBeforeScreenshotMs`: extra delay before capture
- `fullPage`: whether to capture the full page
- `selector`: capture one element instead of the whole page
- `hideSelectors`: selectors hidden only for that shot
- `actions`: optional array of simple interactions

Supported action types:
- `click`
- `fill`
- `press`
- `hover`
- `select`
- `wait`

## Recommended workflow

1. Start the user's project normally.
2. Draft or edit a capture plan based on the real routes.
3. Run the capture script and inspect the output directory.
4. Remove weak or redundant screenshots.
5. Feed the screenshot directory into `bootstrap_promo_project.py`.
