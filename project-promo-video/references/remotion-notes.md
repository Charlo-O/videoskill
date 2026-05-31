# Remotion Notes

Read this file when you need to tune the bundled template or explain why the skill uses Remotion in this way.

## Reference Repo

Reference: [andchir/remotion-animations](https://github.com/andchir/remotion-animations)

Useful takeaways from the reference project:
- It uses Remotion's composition registry pattern from `src/Root.tsx`.
- It renders with Remotion CLI commands such as `studio`, `render`, and multiple output formats.
- Most animations target `1920x1080` at `30fps`.
- The repo is strongest as a catalog of title, lower-third, and short UI animation ideas.

This skill borrows the overall approach, not the whole library. The visual page layout comes from Guizang PPT HTML sections. Remotion should host that PPT DOM directly whenever possible, then drive `[data-anim]` elements with frame-based timing, `spring`, and `interpolate`. Rendered slide images remain useful as QA/fallback assets, not the primary motion surface.

The current template also treats voiceover as the motion clock. `audio-config.ts`
stores per-scene `beats`; each beat has text, a target element family, a motion
recipe, a start frame, and a duration. `PptDomScene.tsx` uses those beats to
activate title, body, image, card, diagram, KPI, bar, and rule-line animations
throughout the whole scene instead of finishing all entrances at the beginning.

For the dense motion path, `bootstrap_promo_project.py` compiles PPT HTML into
`motionUnits`. Each visible unit gets a `data-motion-id`; title and short text
can be split into per-character spans with `--motion-detail glyph`. Remotion then
generates one frame-driven CSS rule per unit. When `motionUnits` are present,
they take priority over the older broad selector animation recipes.

## Render Defaults

Default for product trailers:
- `mp4`
- `h264`
- `yuv420p`

Use transparent video only when the user explicitly asks for overlays that will be composited elsewhere. In that case, switch to WebM with VP9 and alpha-friendly settings.

## Motion Guidelines

Use motion to frame the product, not overpower it:
- Enter quickly and let the screenshot remain readable
- Put the strongest screen first
- Keep titles short enough to read in under two seconds
- Favor element-level PPT DOM motion: beat-led title stagger, rule draw, card cascade, SVG reveal, image parallax, and chart growth
- Align visual reveals with narration clauses. If a spoken clause introduces a screenshot, KPI, card group, or diagram, assign that clause to the matching beat target.
- Keep `public/audio/motion-timeline.json` free of static tails; each scene's last beat should end at the scene duration.
- Prefer `--motion-detail glyph` for polished trailers. Use `max` only when the slide has little text; too many per-character units can slow Remotion renders and make body copy noisy.
- Do not add Remotion overlays that change the PPT layout. If text, cards, or image placement need to change, update the PPT section and regenerate the workspace assets.
- Keep transitions simple (`fade`, `push`, `cut`) so the PPT layout remains the primary visual system.

## Screenshot Selection

Choose screenshots that answer these questions:
- What is the product?
- What does the user do first?
- What proof of value is visible?
- What final feeling should the trailer end on?

If the source UI is weak, no amount of animation will fix the trailer. Improve capture quality before adjusting Remotion code.
