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

    return {
        "id": scene["id"],
        "title": scene["title"],
        "durationInFrames": frames,
        "audioFile": "audio/voiceover/%s.mp3" % scene["id"],
        "durationSeconds": round(duration, 2),
    }


def write_audio_config(path: Path, scenes: List[Dict[str, object]], fps: int) -> None:
    blocks = []
    for scene in scenes:
        blocks.append(
            "\n".join(
                [
                    "  {",
                    "    id: %s," % json.dumps(scene["id"], ensure_ascii=False),
                    "    title: %s," % json.dumps(scene["title"], ensure_ascii=False),
                    "    durationInFrames: %s," % scene["durationInFrames"],
                    "    audioFile: %s," % json.dumps(scene["audioFile"], ensure_ascii=False),
                    "  },",
                ]
            )
        )

    content = "\n".join(
        [
            "export interface SceneConfig {",
            "  id: string;",
            "  title: string;",
            "  durationInFrames: number;",
            "  audioFile: string | null;",
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


async def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).resolve()
    script_file = workspace / "public" / "audio" / "voiceover-script.json"
    output_dir = workspace / "public" / "audio" / "voiceover"
    config_file = workspace / "src" / "audio-config.ts"

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
    total_frames = sum(int(scene["durationInFrames"]) for scene in results)

    print("=" * 60)
    print("audio-config.ts updated: %s" % config_file)
    print("Total frames: %s" % total_frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
