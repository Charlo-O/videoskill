# Audio Notes

Read this file when you need to extend narration or choose background music.

## Borrowed Workflow

Reference repo: [wshuyi/remotion-video-skill](https://github.com/wshuyi/remotion-video-skill)

The useful pattern from that repo is not the exact file layout. It is the workflow:
- Write narration per scene
- Generate one audio file per scene
- Measure real duration with `ffprobe`
- Rewrite `audio-config.ts`
- Let scene timing follow audio instead of hardcoded frame counts

This skill adopts the same idea with `scripts/generate_voiceover_edge.py` and `src/audio-config.ts`.

## Narration Choice

Default recommendation:
- Edge TTS
- Voice: `zh-CN-YunyangNeural`

Why:
- No API key required
- Good enough for fast iteration
- Easy to regenerate after copy edits

Current implementation detail:
- `scripts/generate_voiceover_edge.py` supports `--voice auto`
- If `voiceover-script.json` already specifies a voice, that wins
- Otherwise the script detects CJK text and picks Chinese or English voice automatically

## Music Sourcing

Do not bundle random internet music into the skill itself. Use tracks with a clear license and keep a note of the source.

Good options:
- OpenGameArt for CC0 or CC-BY tracks
- Free Music Archive when the exact license is acceptable for the user's distribution
- Public-domain classical sources for sober product videos

## Current Validation Track

For demo rendering, a good fit is [Our expanse](https://opengameart.org/content/our-expanse) from OpenGameArt.

Reasons:
- Tags and preview describe it as futuristic, upbeat, cinematic, and montage-friendly
- License is listed as `CC0`
- It has downloadable `mp3` and `ogg` files

Always record the music source and license in the delivery note when you render a final trailer for the user.

## Mixing Behavior

The bundled template now treats music as support, not the lead:
- BGM fades in over the first few frames
- BGM fades out near the end
- BGM volume is ducked automatically during any scene that has narration audio
