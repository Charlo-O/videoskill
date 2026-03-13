from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
SUPPORTED_AUDIO_SUFFIXES = {".mp3", ".wav", ".ogg", ".m4a"}
FPS = 30
INTRO_FRAMES = 60
OUTRO_FRAMES = 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Remotion promo workspace from screenshots."
    )
    parser.add_argument("--workspace", required=True, help="Directory to create or update.")
    parser.add_argument(
        "--screenshots", required=True, help="Directory containing source screenshots."
    )
    parser.add_argument(
        "--bgm-file",
        help="Optional background music file to copy into public/audio.",
    )
    parser.add_argument("--project-name", default="Project Name")
    parser.add_argument(
        "--tagline", default="A clear one-line promise for the product."
    )
    parser.add_argument(
        "--closing-line", default="Show the product in motion and end on a clear promise."
    )
    parser.add_argument("--accent", default="#14b8a6")
    parser.add_argument("--background", default="#081226")
    parser.add_argument("--shot-duration", type=int, default=90)
    return parser.parse_args()


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return normalized or "shot"


def humanize_filename(value: str) -> str:
    cleaned = re.sub(r"^\d+[-_. ]*", "", value).strip()
    if not cleaned:
        return "Key Screen"
    words = re.split(r"[-_. ]+", cleaned)
    return " ".join(word.capitalize() for word in words if word)


def image_sort_key(path: Path) -> Tuple[int, str]:
    match = re.match(r"^(\d+)", path.stem)
    prefix = int(match.group(1)) if match else 10_000
    return prefix, path.name.lower()


def copy_missing_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            copy_missing_tree(item, target)
            continue
        if not target.exists():
            shutil.copy2(item, target)


def collect_images(screenshot_dir: Path) -> List[Path]:
    images = [
        path
        for path in screenshot_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
    ]
    return sorted(images, key=image_sort_key)


def prepare_public_screenshots(
    images: List[Path],
    destination: Path,
    shot_duration: int,
) -> List[Dict[str, object]]:
    destination.mkdir(parents=True, exist_ok=True)
    for item in destination.iterdir():
        if item.is_file() and item.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
            item.unlink()

    prepared = []
    alignments = ("left", "center", "right")

    for index, image in enumerate(images, start=1):
        base_name = re.sub(r"^\d+[-_. ]*", "", image.stem)
        slug = slugify(base_name or "shot-%s" % index)
        file_name = "%02d-%s%s" % (index, slug, image.suffix.lower())
        target = destination / file_name
        shutil.copy2(image, target)

        title = humanize_filename(base_name or file_name)
        prepared.append(
            {
                "id": slug,
                "src": "screenshots/%s" % file_name,
                "title": title,
                "subtitle": "Explain the user value visible in %s." % title.lower(),
                "durationInFrames": shot_duration,
                "align": alignments[(index - 1) % len(alignments)],
            }
        )

    return prepared


def copy_background_music(source: Optional[str], audio_dir: Path) -> Optional[str]:
    if not source:
        return None

    music_path = Path(source).resolve()
    if not music_path.exists():
        raise SystemExit("Background music file not found: %s" % music_path)
    if music_path.suffix.lower() not in SUPPORTED_AUDIO_SUFFIXES:
        raise SystemExit("Unsupported background music type: %s" % music_path.suffix)

    audio_dir.mkdir(parents=True, exist_ok=True)
    target_name = "bgm%s" % music_path.suffix.lower()
    shutil.copy2(music_path, audio_dir / target_name)
    return "audio/%s" % target_name


def write_manifest(path: Path, shots: List[Dict[str, object]]) -> None:
    path.write_text(json.dumps(shots, indent=2, ensure_ascii=False), encoding="utf-8")


def write_promo_data(
    path: Path,
    project_name: str,
    tagline: str,
    closing_line: str,
    accent: str,
    background: str,
    shots: List[Dict[str, object]],
    music_file: Optional[str],
) -> None:
    shot_blocks = []
    for shot in shots:
        shot_blocks.append(
            "\n".join(
                [
                    "  {",
                    "    id: %s," % json.dumps(shot["id"], ensure_ascii=False),
                    "    src: %s," % json.dumps(shot["src"], ensure_ascii=False),
                    "    title: %s," % json.dumps(shot["title"], ensure_ascii=False),
                    "    subtitle: %s," % json.dumps(shot["subtitle"], ensure_ascii=False),
                    "    durationInFrames: %s," % shot["durationInFrames"],
                    "    align: %s," % json.dumps(shot["align"], ensure_ascii=False),
                    "  },",
                ]
            )
        )

    content = "\n".join(
        [
            "export const FPS = 30;",
            "export const INTRO_FRAMES = %s;" % INTRO_FRAMES,
            "export const OUTRO_FRAMES = %s;" % OUTRO_FRAMES,
            "",
            "export type PromoShot = {",
            "  id: string;",
            "  src: string;",
            "  title: string;",
            "  subtitle: string;",
            "  durationInFrames: number;",
            '  align?: "left" | "center" | "right";',
            "};",
            "",
            "export const promoMeta = {",
            "  projectName: %s," % json.dumps(project_name, ensure_ascii=False),
            "  tagline: %s," % json.dumps(tagline, ensure_ascii=False),
            "  closingLine: %s," % json.dumps(closing_line, ensure_ascii=False),
            "  accent: %s," % json.dumps(accent, ensure_ascii=False),
            "  background: %s," % json.dumps(background, ensure_ascii=False),
            "  backgroundMusic: {",
            "    file: %s," % ("null" if music_file is None else json.dumps(music_file)),
            "    volume: 0.18,",
            "  },",
            "};",
            "",
            "export const shots: PromoShot[] = [",
            *shot_blocks,
            "];",
        ]
    )
    path.write_text("%s\n" % content, encoding="utf-8")


def build_voiceover_scenes(
    project_name: str,
    tagline: str,
    closing_line: str,
    shots: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    scenes = [
        {
            "id": "intro",
            "title": "Intro",
            "text": "Introducing %s. %s" % (project_name, tagline),
            "minFrames": INTRO_FRAMES,
            "paddingFrames": 12,
        }
    ]

    for shot in shots:
        scenes.append(
            {
                "id": "shot-%s" % shot["id"],
                "title": shot["title"],
                "text": "%s. %s" % (shot["title"], shot["subtitle"]),
                "minFrames": shot["durationInFrames"],
                "paddingFrames": 18,
            }
        )

    scenes.append(
        {
            "id": "outro",
            "title": "Outro",
            "text": closing_line,
            "minFrames": OUTRO_FRAMES,
            "paddingFrames": 18,
        }
    )
    return scenes


def write_voiceover_script(path: Path, scenes: List[Dict[str, object]]) -> None:
    payload = {"fps": FPS, "voice": "auto", "scenes": scenes}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_audio_config(
    path: Path,
    scenes: List[Dict[str, object]],
    *,
    with_audio_files: bool,
) -> None:
    scene_blocks = []
    for scene in scenes:
        audio_file = None
        if with_audio_files:
            audio_file = "audio/voiceover/%s.mp3" % scene["id"]
        scene_blocks.append(
            "\n".join(
                [
                    "  {",
                    "    id: %s," % json.dumps(scene["id"], ensure_ascii=False),
                    "    title: %s," % json.dumps(scene["title"], ensure_ascii=False),
                    "    durationInFrames: %s," % scene["minFrames"],
                    "    audioFile: %s,"
                    % ("null" if audio_file is None else json.dumps(audio_file)),
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
            *scene_blocks,
            "];",
            "",
            "export const TOTAL_FRAMES = SCENES.reduce(",
            "  (sum, scene) => sum + scene.durationInFrames,",
            "  0,",
            ");",
            "",
            "export const FPS = %s;" % FPS,
        ]
    )
    path.write_text("%s\n" % content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    skill_dir = script_dir.parent
    template_dir = skill_dir / "assets" / "remotion-template"

    workspace = Path(args.workspace).resolve()
    screenshot_dir = Path(args.screenshots).resolve()

    if not template_dir.exists():
        raise SystemExit("Template not found: %s" % template_dir)

    if not screenshot_dir.exists():
        raise SystemExit("Screenshot directory not found: %s" % screenshot_dir)

    images = collect_images(screenshot_dir)
    if not images:
        raise SystemExit("No supported screenshots found in: %s" % screenshot_dir)

    copy_missing_tree(template_dir, workspace)

    screenshots_dir = workspace / "public" / "screenshots"
    audio_dir = workspace / "public" / "audio"
    voiceover_dir = audio_dir / "voiceover"
    voiceover_dir.mkdir(parents=True, exist_ok=True)

    shots = prepare_public_screenshots(images, screenshots_dir, args.shot_duration)
    write_manifest(screenshots_dir / "manifest.json", shots)

    music_file = copy_background_music(args.bgm_file, audio_dir)

    src_dir = workspace / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    write_promo_data(
        src_dir / "promo-data.ts",
        project_name=args.project_name,
        tagline=args.tagline,
        closing_line=args.closing_line,
        accent=args.accent,
        background=args.background,
        shots=shots,
        music_file=music_file,
    )

    voiceover_scenes = build_voiceover_scenes(
        args.project_name,
        args.tagline,
        args.closing_line,
        shots,
    )
    write_voiceover_script(audio_dir / "voiceover-script.json", voiceover_scenes)
    write_audio_config(src_dir / "audio-config.ts", voiceover_scenes, with_audio_files=False)

    total_frames = sum(int(scene["minFrames"]) for scene in voiceover_scenes)
    duration_seconds = round(float(total_frames) / FPS, 2)

    print("Workspace ready: %s" % workspace)
    print("Shots prepared: %s" % len(shots))
    print("Estimated duration: %ss at %sfps" % (duration_seconds, FPS))
    print("Manifest: %s" % (screenshots_dir / "manifest.json"))
    print("Promo data: %s" % (src_dir / "promo-data.ts"))
    print("Voiceover script: %s" % (audio_dir / "voiceover-script.json"))
    if music_file:
        print("Background music: %s" % music_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
