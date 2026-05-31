from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List

try:
    import edge_tts
except ImportError:
    print("Please install edge-tts first: pip install edge-tts")
    raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate scene voiceover with Edge TTS and update audio-config.ts."
    )
    parser.add_argument("--workspace", required=True, help="Generated Remotion workspace.")
    parser.add_argument(
        "--voice",
        default="auto",
        help="Edge TTS voice. Use 'auto' to infer from the script.",
    )
    parser.add_argument("--force", action="store_true", help="Regenerate existing files.")
    return parser.parse_args()


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def resolve_voice(
    requested_voice: str,
    script_voice: object,
    scenes: List[Dict[str, object]],
) -> str:
    if requested_voice != "auto":
        return requested_voice

    if isinstance(script_voice, str) and script_voice and script_voice != "auto":
        return script_voice

    joined_text = " ".join(str(scene.get("text", "")) for scene in scenes)
    if contains_cjk(joined_text):
        return "zh-CN-YunyangNeural"

    return "en-US-GuyNeural"


def get_audio_duration(file_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ],
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    return float(value) if value else 0.0


def allocate_beat_frames(
    scene: Dict[str, object],
    total_frames: int,
) -> List[Dict[str, object]]:
    raw_beats = scene.get("beats")
    if not isinstance(raw_beats, list) or not raw_beats:
        raw_beats = [
            {
                "id": "beat-1",
                "text": scene.get("text") or scene.get("title") or "",
                "target": "body",
                "motion": "content-follow",
                "weight": len(str(scene.get("text", ""))) or 1,
            }
        ]

    beats = [beat for beat in raw_beats if isinstance(beat, dict)]
    if not beats:
        return []

    weights = [
        max(1.0, float(beat.get("weight") or len(str(beat.get("text", ""))) or 1))
        for beat in beats
    ]
    weight_sum = sum(weights) or 1.0
    cursor = 0
    allocated = []
    min_span = 18

    for index, beat in enumerate(beats):
        if index == len(beats) - 1:
            span = max(min_span, total_frames - cursor)
        else:
            span = max(min_span, round(total_frames * weights[index] / weight_sum))
            remaining_min = min_span * (len(beats) - index - 1)
            span = min(span, max(min_span, total_frames - cursor - remaining_min))

        allocated.append(
            {
                "id": str(beat.get("id") or "beat-%s" % (index + 1)),
                "text": str(beat.get("text") or ""),
                "target": str(beat.get("target") or "body"),
                "motion": str(beat.get("motion") or "content-follow"),
                "startFrame": cursor,
                "durationInFrames": max(1, span),
            }
        )
        cursor += span

    if allocated:
        allocated[-1]["durationInFrames"] = max(
            1,
            total_frames - int(allocated[-1]["startFrame"]),
        )
    return allocated


def beat_target_matches(value: str, target: str) -> bool:
    aliases = {
        "title": ("title", "headline", "hook", "left", "split-left"),
        "body": ("body", "copy", "lead", "caption", "voice", "audio", "right", "split-right"),
        "image": ("image", "screen", "visual", "proof"),
        "cards": ("cards", "card", "matrix", "system"),
        "diagram": ("diagram", "svg", "dom", "shape"),
        "kpi": ("kpi", "metric", "spec", "proof"),
        "bars": ("bar", "chart", "growth"),
        "line": ("line", "rule", "closing"),
    }
    normalized = value.lower()
    return any(alias in normalized for alias in aliases.get(target, (target,)))


def pick_unit_beat(unit: Dict[str, object], beats: List[Dict[str, object]], fallback_index: int) -> Dict[str, object]:
    group = str(unit.get("group", "body"))
    motion = str(unit.get("motion", ""))
    for beat in beats:
        target = str(beat.get("target", "body"))
        beat_motion = str(beat.get("motion", ""))
        if beat_target_matches(target, group) or beat_target_matches(beat_motion, group) or beat_target_matches(motion, target):
            return beat
    return beats[min(fallback_index, len(beats) - 1)]


def allocate_motion_unit_frames(
    scene: Dict[str, object],
    beats: List[Dict[str, object]],
    total_frames: int,
) -> List[Dict[str, object]]:
    raw_units = scene.get("motionUnits")
    if not isinstance(raw_units, list) or not raw_units:
        return []

    units = [unit for unit in raw_units if isinstance(unit, dict)]
    if not units or not beats:
        return []

    buckets: Dict[str, List[Dict[str, object]]] = {}
    beat_by_id: Dict[str, Dict[str, object]] = {}
    for index, beat in enumerate(beats):
        beat_id = str(beat.get("id", "beat-%s" % (index + 1)))
        beat_by_id[beat_id] = beat
        buckets[beat_id] = []

    for index, unit in enumerate(units):
        beat = pick_unit_beat(unit, beats, index % len(beats))
        buckets[str(beat.get("id"))].append(unit)

    for beat_id, bucket in list(buckets.items()):
        if bucket:
            continue
        donor_id = max(buckets, key=lambda key: len(buckets[key]))
        donor = buckets[donor_id]
        if len(donor) <= 1:
            continue
        move_count = max(1, min(8, round(len(donor) * 0.12)))
        buckets[beat_id].extend(donor[-move_count:])
        del donor[-move_count:]

    allocated: List[Dict[str, object]] = []
    for beat_id, bucket in buckets.items():
        beat = beat_by_id[beat_id]
        start = int(beat.get("startFrame", 0))
        span = max(1, int(beat.get("durationInFrames", total_frames)))
        end = start + span
        if not bucket:
            continue
        def base_duration(kind: str) -> int:
            if kind.startswith("text-char"):
                return 8
            if kind.startswith("text"):
                return 12
            if kind in {"line", "bar", "shape"}:
                return 16
            return 14

        longest_base = max(base_duration(str(unit.get("kind", "container"))) for unit in bucket)
        available = max(0, span - longest_base)
        stagger = 0 if len(bucket) == 1 else max(1, round(available / max(1, len(bucket) - 1)))
        for index, unit in enumerate(bucket):
            kind = str(unit.get("kind", "container"))
            minimum = base_duration(kind)
            unit_start = min(max(start, end - minimum), start + index * stagger)
            unit_duration = max(1, end - unit_start)

            allocated.append(
                {
                    "id": str(unit.get("id", "unit-%s" % (len(allocated) + 1))),
                    "kind": str(unit.get("kind", "container")),
                    "group": str(unit.get("group", "body")),
                    "motion": str(unit.get("motion", "unit-rise")),
                    "text": str(unit.get("text", "")),
                    "beatId": beat_id,
                    "startFrame": unit_start,
                    "durationInFrames": max(1, unit_duration),
                    "order": index,
                }
            )

    allocated.sort(key=lambda item: (int(item.get("startFrame", 0)), int(item.get("order", 0))))
    return allocated[:900]


async def synthesize(
    scene: Dict[str, object],
    voice: str,
    output_dir: Path,
    fps: int,
    force: bool,
) -> Dict[str, object]:
    output_file = output_dir / ("%s.mp3" % scene["id"])
    if force or (not output_file.exists()) or output_file.stat().st_size == 0:
        communicate = edge_tts.Communicate(str(scene["text"]), voice)
        await communicate.save(str(output_file))

    duration = get_audio_duration(output_file)
    padding_frames = int(scene.get("paddingFrames", 18))
    min_frames = int(scene.get("minFrames", 0))
    frames = max(min_frames, round(duration * fps) + padding_frames)
    beats = allocate_beat_frames(scene, frames)
    motion_units = allocate_motion_unit_frames(scene, beats, frames)

    return {
        "id": scene["id"],
        "title": scene["title"],
        "durationInFrames": frames,
        "audioFile": "audio/voiceover/%s.mp3" % scene["id"],
        "durationSeconds": round(duration, 2),
        "beats": beats,
        "motionUnits": motion_units,
    }


def motion_unit_ts_block(unit: Dict[str, object], indent: str = "      ") -> str:
    return "\n".join(
        [
            "%s{" % indent,
            "%s  id: %s," % (indent, json.dumps(unit["id"], ensure_ascii=False)),
            "%s  kind: %s," % (indent, json.dumps(unit["kind"], ensure_ascii=False)),
            "%s  group: %s," % (indent, json.dumps(unit["group"], ensure_ascii=False)),
            "%s  motion: %s," % (indent, json.dumps(unit["motion"], ensure_ascii=False)),
            "%s  text: %s," % (indent, json.dumps(unit.get("text", ""), ensure_ascii=False)),
            "%s  beatId: %s," % (indent, json.dumps(unit.get("beatId", ""), ensure_ascii=False)),
            "%s  startFrame: %s," % (indent, int(unit["startFrame"])),
            "%s  durationInFrames: %s," % (indent, int(unit["durationInFrames"])),
            "%s}," % indent,
        ]
    )


def write_audio_config(path: Path, scenes: List[Dict[str, object]], fps: int) -> None:
    blocks = []
    for scene in scenes:
        beat_blocks = []
        for beat in scene.get("beats", []):
            beat_blocks.append(
                "\n".join(
                    [
                        "      {",
                        "        id: %s," % json.dumps(beat["id"], ensure_ascii=False),
                        "        text: %s," % json.dumps(beat["text"], ensure_ascii=False),
                        "        target: %s," % json.dumps(beat["target"], ensure_ascii=False),
                        "        motion: %s," % json.dumps(beat["motion"], ensure_ascii=False),
                        "        startFrame: %s," % int(beat["startFrame"]),
                        "        durationInFrames: %s," % int(beat["durationInFrames"]),
                        "      },",
                    ]
                )
            )
        unit_blocks = [
            motion_unit_ts_block(unit)
            for unit in scene.get("motionUnits", [])
            if isinstance(unit, dict)
        ]
        blocks.append(
            "\n".join(
                [
                    "  {",
                    "    id: %s," % json.dumps(scene["id"], ensure_ascii=False),
                    "    title: %s," % json.dumps(scene["title"], ensure_ascii=False),
                    "    durationInFrames: %s," % scene["durationInFrames"],
                    "    audioFile: %s," % json.dumps(scene["audioFile"], ensure_ascii=False),
                    "    beats: [",
                    *beat_blocks,
                    "    ],",
                    "    motionUnits: [",
                    *unit_blocks,
                    "    ],",
                    "  },",
                ]
            )
        )

    content = "\n".join(
        [
            "export interface BeatConfig {",
            "  id: string;",
            "  text: string;",
            "  target: string;",
            "  motion: string;",
            "  startFrame: number;",
            "  durationInFrames: number;",
            "}",
            "",
            "export interface MotionUnitConfig {",
            "  id: string;",
            "  kind: string;",
            "  group: string;",
            "  motion: string;",
            "  text?: string;",
            "  beatId?: string;",
            "  startFrame: number;",
            "  durationInFrames: number;",
            "}",
            "",
            "export interface SceneConfig {",
            "  id: string;",
            "  title: string;",
            "  durationInFrames: number;",
            "  audioFile: string | null;",
            "  beats: BeatConfig[];",
            "  motionUnits: MotionUnitConfig[];",
            "}",
            "",
            "export const SCENES: SceneConfig[] = [",
            *blocks,
            "];",
            "",
            "export const TOTAL_FRAMES = SCENES.reduce(",
            "  (sum, scene) => sum + scene.durationInFrames,",
            "  0,",
            ");",
            "",
            "export const FPS = %s;" % fps,
        ]
    )
    path.write_text("%s\n" % content, encoding="utf-8")


def write_motion_timeline(path: Path, scenes: List[Dict[str, object]], fps: int) -> None:
    payload = {
        "fps": fps,
        "maxStaticTailFrames": 0,
        "scenes": [
            {
                "id": scene["id"],
                "title": scene["title"],
                "durationInFrames": scene["durationInFrames"],
                "audioFile": scene["audioFile"],
                "beats": scene.get("beats", []),
                "motionUnits": scene.get("motionUnits", []),
            }
            for scene in scenes
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


async def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).resolve()
    script_file = workspace / "public" / "audio" / "voiceover-script.json"
    output_dir = workspace / "public" / "audio" / "voiceover"
    config_file = workspace / "src" / "audio-config.ts"
    timeline_file = workspace / "public" / "audio" / "motion-timeline.json"

    if not script_file.exists():
        raise SystemExit("Voiceover script not found: %s" % script_file)

    data = json.loads(script_file.read_text(encoding="utf-8"))
    fps = int(data.get("fps", 30))
    scenes = data.get("scenes", [])
    if not scenes:
        raise SystemExit("No scenes found in %s" % script_file)
    voice = resolve_voice(args.voice, data.get("voice"), scenes)

    output_dir.mkdir(parents=True, exist_ok=True)

    print("Edge TTS voice: %s" % voice)
    print("Workspace: %s" % workspace)
    print("=" * 60)

    results = []
    for index, scene in enumerate(scenes, start=1):
        print("[%s/%s] %s" % (index, len(scenes), scene["id"]))
        result = await synthesize(scene, voice, output_dir, fps, args.force)
        results.append(result)
        print(
            "  duration=%ss frames=%s file=%s"
            % (
                result["durationSeconds"],
                result["durationInFrames"],
                result["audioFile"],
            )
        )

    write_audio_config(config_file, results, fps)
    write_motion_timeline(timeline_file, results, fps)
    total_frames = sum(int(scene["durationInFrames"]) for scene in results)

    print("=" * 60)
    print("audio-config.ts updated: %s" % config_file)
    print("Motion timeline: %s" % timeline_file)
    print("Total frames: %s" % total_frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
