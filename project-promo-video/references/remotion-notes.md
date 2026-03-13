# Remotion Notes

Read this file when you need to tune the bundled template or explain why the skill uses Remotion in this way.

## Reference Repo

Reference: [andchir/remotion-animations](https://github.com/andchir/remotion-animations)

Useful takeaways from the reference project:
- It uses Remotion's composition registry pattern from `src/Root.tsx`.
- It renders with Remotion CLI commands such as `studio`, `render`, and multiple output formats.
- Most animations target `1920x1080` at `30fps`.
- The repo is strongest as a catalog of title, lower-third, and short UI animation ideas.

This skill borrows the overall approach, not the whole library. For promo videos assembled from screenshots, a single composition with reusable scene blocks is easier to maintain than dozens of tiny compositions.

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
- Favor lower-thirds, gradient wipes, and gentle zooms over aggressive camera moves

## Screenshot Selection

Choose screenshots that answer these questions:
- What is the product?
- What does the user do first?
- What proof of value is visible?
- What final feeling should the trailer end on?

If the source UI is weak, no amount of animation will fix the trailer. Improve capture quality before adjusting Remotion code.
