from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
SUPPORTED_AUDIO_SUFFIXES = {".mp3", ".wav", ".ogg", ".m4a"}
FPS = 30
DEFAULT_SCENE_FRAMES = 90

# CC0-licensed default background music from OpenGameArt
# Source: https://opengameart.org/content/our-expanse (CC0 license)
DEFAULT_BGM_URL = "https://opengameart.org/sites/default/files/our_expanse_-_loop.mp3"
DEFAULT_BGM_FILENAME = "default-bgm.mp3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Remotion promo workspace whose visuals are rendered from PPT layouts."
    )
    parser.add_argument("--workspace", required=True, help="Directory to create or update.")
    parser.add_argument(
        "--screenshots", required=True, help="Directory containing source screenshots."
    )
    parser.add_argument(
        "--storyboard",
        help=(
            "Optional JSON storyboard. Scenes may provide sectionHtml to use any PPT layout "
            "verbatim, or layoutId plus slots for built-in defaults."
        ),
    )
    parser.add_argument(
        "--ppt-skill",
        help=(
            "Path to guizang-ppt-skill. Defaults to the sibling extra/guizang-ppt-skill "
            "in this repository."
        ),
    )
    parser.add_argument(
        "--layout-style",
        choices=("editorial", "swiss"),
        default="editorial",
        help="PPT visual system used for generated default slides.",
    )
    parser.add_argument(
        "--skip-slide-render",
        action="store_true",
        help="Generate the PPT deck but skip Playwright rendering into public/slides.",
    )
    parser.add_argument(
        "--render-mode",
        choices=("ppt-dom", "slides"),
        default="ppt-dom",
        help=(
            "ppt-dom renders the PPT sections directly inside Remotion so Remotion can "
            "drive element-level DOM motion. slides keeps the older rendered-PNG path."
        ),
    )
    parser.add_argument(
        "--motion-detail",
        choices=("normal", "fine", "glyph", "max"),
        default="glyph",
        help=(
            "How finely PPT DOM is split for Remotion motion. normal keeps phrase and "
            "leaf-node units, fine adds more phrases, glyph animates titles/short text "
            "per character, max tries to split all text per character."
        ),
    )
    parser.add_argument(
        "--brief-file",
        help=(
            "Optional article, product brief, README, or script text. Default copy and "
            "voiceover lines are drawn from it before falling back to screenshot names."
        ),
    )
    parser.add_argument(
        "--scenario",
        default="product promo",
        help="Short scenario label used to keep generated copy grounded.",
    )
    parser.add_argument(
        "--copy-language",
        choices=("auto", "zh", "en"),
        default="auto",
        help="Language for generated fallback copy and narration.",
    )
    parser.add_argument(
        "--bgm-file",
        help="Background music file to copy into public/audio. "
        "When omitted, a CC0 default track is downloaded automatically.",
    )
    parser.add_argument(
        "--no-bgm",
        action="store_true",
        help="Explicitly skip background music entirely.",
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
    parser.add_argument("--shot-duration", type=int, default=DEFAULT_SCENE_FRAMES)
    return parser.parse_args()


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return normalized or "slide"


def humanize_filename(value: str) -> str:
    cleaned = re.sub(r"^\d+[-_. ]*", "", value).strip()
    if not cleaned:
        return "Key Screen"
    words = re.split(r"[-_. ]+", cleaned)
    return " ".join(word.capitalize() for word in words if word)


def contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def resolve_copy_language(args: argparse.Namespace, text: str = "") -> str:
    if args.copy_language != "auto":
        return args.copy_language
    combined = " ".join([args.project_name, args.tagline, args.closing_line, text])
    return "zh" if contains_cjk(combined) else "en"


def clean_brief_line(line: str) -> str:
    line = re.sub(r"```[\s\S]*?```", " ", line)
    line = re.sub(r"`([^`]*)`", r"\1", line)
    line = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", line)
    line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
    line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
    line = re.sub(r"^\s*[-*+]\s+", "", line)
    line = re.sub(r"^\s*\d+[.)]\s+", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def split_brief_points(text: str) -> List[str]:
    cleaned = clean_brief_line(text)
    if contains_cjk(cleaned):
        parts = re.split(r"(?<=[。！？；])\s*", cleaned)
    else:
        parts = re.split(r"(?<=[.!?;])\s+", cleaned)

    points = []
    for part in parts:
        item = clean_brief_line(part)
        if len(item) < 12:
            continue
        if len(item) > 96:
            item = item[:94].rstrip("，,。.;； ") + "..."
        points.append(item)
    return points


def load_copy_points(args: argparse.Namespace) -> List[str]:
    if not args.brief_file:
        return []

    brief_path = Path(args.brief_file).resolve()
    if not brief_path.exists():
        raise SystemExit("Brief file not found: %s" % brief_path)

    text = brief_path.read_text(encoding="utf-8")
    points = split_brief_points(text)
    return points[:12]


def pick_copy_point(points: List[str], index: int, fallback: str) -> str:
    if points:
        return points[index % len(points)]
    return fallback


def fallback_subtitle(title: str, language: str, scenario: str) -> str:
    if language == "zh":
        return "围绕「%s」展示真实界面、核心价值和可交付结果。" % title
    return "Show the real interface, core value, and final payoff for %s." % scenario


def scenario_title(
    original_title: str,
    index: int,
    language: str,
    copy_points: List[str],
) -> str:
    if not copy_points:
        return original_title

    if language == "zh":
        titles = [
            "真实界面作为证据",
            "PPT DOM 直接入镜",
            "Remotion 驱动元素",
            "配音贴合内容",
            "生成可复用视频",
            "交付完整流程",
        ]
    else:
        titles = [
            "Real Interface Proof",
            "PPT DOM On Screen",
            "Remotion Drives Elements",
            "Narration Matches Content",
            "Reusable Video Output",
            "Complete Delivery Flow",
        ]

    return titles[(index - 1) % len(titles)]


def split_voiceover_beats(text: str, title: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        cleaned = title

    if contains_cjk(cleaned):
        parts = re.split(r"(?<=[。！？；])\s*|(?<=[，、])\s*", cleaned)
    else:
        parts = re.split(r"(?<=[.!?;])\s+|,\s+", cleaned)

    beats: List[str] = []
    for part in parts:
        item = clean_brief_line(part)
        if len(item) < 4:
            continue
        beats.append(item)

    if not beats:
        beats = [title, cleaned]
    elif len(beats) == 1 and title and title not in beats[0]:
        beats.insert(0, title)

    return beats[:5]


def default_motion_plan(layout_id: str) -> List[Tuple[str, str]]:
    layout = layout_id.upper()
    if layout in {"S01", "SWISS-COVER-ASCII", "A01"}:
        return [
            ("title", "title-reveal"),
            ("body", "lead-reveal"),
            ("line", "rule-draw"),
        ]
    if layout in {"S10", "SWISS-CLOSING-ASCII", "A07"}:
        return [
            ("title", "split-left"),
            ("body", "split-right"),
            ("line", "closing-rule"),
        ]
    if layout == "S22":
        return [
            ("image", "image-parallax"),
            ("title", "title-block"),
            ("body", "copy-follow"),
            ("kpi", "kpi-build"),
        ]
    if layout == "S15":
        return [
            ("title", "title-reveal"),
            ("image", "proof-image"),
            ("cards", "card-cascade"),
            ("kpi", "matrix-proof"),
        ]
    if layout == "S17":
        return [
            ("title", "title-reveal"),
            ("diagram", "diagram-reveal"),
            ("cards", "system-cards"),
            ("body", "caption-follow"),
        ]
    if layout == "S21":
        return [
            ("title", "title-reveal"),
            ("kpi", "spec-kpis"),
            ("body", "motion-note"),
            ("bars", "bar-grow"),
        ]
    return [
        ("title", "title-reveal"),
        ("image", "image-parallax"),
        ("cards", "card-cascade"),
        ("body", "content-follow"),
    ]


def build_scene_beats(scene: Dict[str, object], text: str, title: str) -> List[Dict[str, object]]:
    custom_beats = scene.get("beats")
    if isinstance(custom_beats, list) and custom_beats:
        normalized = []
        for index, raw_beat in enumerate(custom_beats, start=1):
            if not isinstance(raw_beat, dict):
                continue
            normalized.append(
                {
                    "id": str(raw_beat.get("id") or "beat-%s" % index),
                    "text": str(raw_beat.get("text") or title),
                    "target": str(raw_beat.get("target") or "body"),
                    "motion": str(raw_beat.get("motion") or "content-follow"),
                    "weight": float(raw_beat.get("weight") or 1),
                }
            )
        if normalized:
            return normalized

    text_beats = split_voiceover_beats(text, title)
    plan = default_motion_plan(str(scene.get("layoutId", "")))
    beats = []
    for index, beat_text in enumerate(text_beats, start=1):
        target, motion = plan[(index - 1) % len(plan)]
        beats.append(
            {
                "id": "beat-%s" % index,
                "text": beat_text,
                "target": target,
                "motion": motion,
                "weight": max(1, len(beat_text)),
            }
        )
    return beats


def allocate_beat_frames(
    beats: List[Dict[str, object]],
    total_frames: int,
) -> List[Dict[str, object]]:
    if not beats:
        return []

    weights = [max(1.0, float(beat.get("weight") or len(str(beat.get("text", ""))) or 1)) for beat in beats]
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

        next_beat = dict(beat)
        next_beat["startFrame"] = cursor
        next_beat["durationInFrames"] = max(1, span)
        allocated.append(next_beat)
        cursor += span

    if allocated:
        allocated[-1]["durationInFrames"] = max(
            1,
            total_frames - int(allocated[-1]["startFrame"]),
        )
    return allocated


VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

SKIP_TEXT_TAGS = {"script", "style", "canvas", "svg"}
TEXT_CONTAINER_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "span", "figcaption"}
MOTION_CLASS_GROUPS = [
    ("title", ("h-hero", "h-xl", "title", "headline", "kicker")),
    ("body", ("lead", "body", "caption", "copy", "label", "t-meta", "img-cap")),
    ("image", ("frame-img", "image", "screenshot", "visual")),
    ("cards", ("sub-card", "card-fill", "card-accent", "card-ink", "callout")),
    ("kpi", ("kpi", "metric", "num", "stat", "ledger")),
    ("bars", ("bar", "row-fill", "vbar")),
    ("line", ("rule", "hairline", "hr-")),
    ("diagram", ("diagram", "node", "svg")),
]
PASSIVE_CONTAINER_CLASSES = (
    "slide",
    "canvas-card",
    "frame",
    "chrome",
    "chrome-min",
    "split-half",
    "half",
    "grid-",
)

GROUP_MOTIONS = {
    "title": "title-glyph",
    "body": "phrase-rise",
    "image": "image-mask",
    "cards": "card-pop",
    "kpi": "metric-pop",
    "bars": "bar-grow",
    "line": "rule-draw",
    "diagram": "diagram-node",
}


def attrs_to_dict(attrs: List[Tuple[str, Optional[str]]]) -> Dict[str, str]:
    return {name.lower(): "" if value is None else str(value) for name, value in attrs}


def render_attrs(attrs: List[Tuple[str, Optional[str]]]) -> str:
    parts = []
    for name, value in attrs:
        if value is None:
            parts.append(" %s" % name)
        else:
            parts.append(' %s="%s"' % (name, html_escape(value)))
    return "".join(parts)


def infer_motion_group(tag: str, attrs: List[Tuple[str, Optional[str]]]) -> str:
    tag = tag.lower()
    attr_map = attrs_to_dict(attrs)
    signal = " ".join(
        [
            attr_map.get("class", ""),
            attr_map.get("id", ""),
            attr_map.get("data-anim", ""),
            attr_map.get("data-layout", ""),
        ]
    ).lower()

    if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return "title"
    if tag == "img":
        return "image"
    if tag in {"svg", "circle", "path", "line", "polyline", "polygon", "rect"}:
        return "diagram"
    if tag in {"hr"}:
        return "line"
    data_anim = attr_map.get("data-anim", "").lower()
    if any(token in data_anim for token in ("img", "image", "visual")):
        return "image"
    if any(token in data_anim for token in ("title", "left", "headline")):
        return "title"
    if any(token in data_anim for token in ("kpi", "metric", "stat")):
        return "kpi"
    if any(token in data_anim for token in ("bar", "chart")):
        return "bars"
    if any(token in data_anim for token in ("line", "rule")):
        return "line"
    if any(token in data_anim for token in ("diagram", "svg", "node")):
        return "diagram"
    if any(token in data_anim for token in ("card", "matrix", "up")):
        return "cards"

    for group, needles in MOTION_CLASS_GROUPS:
        if any(needle in signal for needle in needles):
            return group

    if tag in {"p", "li", "figcaption"}:
        return "body"
    return "body"


def infer_motion_kind(tag: str, group: str, attrs: List[Tuple[str, Optional[str]]]) -> str:
    tag = tag.lower()
    attr_map = attrs_to_dict(attrs)
    classes = attr_map.get("class", "").lower()
    if tag == "img":
        return "image"
    if tag in {"circle", "path", "line", "polyline", "polygon", "rect", "svg"}:
        return "shape"
    if group == "line":
        return "line"
    if group == "bars":
        return "bar"
    if group == "cards" or "card" in classes or "callout" in classes:
        return "card"
    if group == "kpi":
        return "kpi"
    if tag in TEXT_CONTAINER_TAGS:
        return "text-block"
    return "container"


def should_annotate_tag(tag: str, attrs: List[Tuple[str, Optional[str]]]) -> bool:
    attr_map = attrs_to_dict(attrs)
    if "data-motion-id" in attr_map:
        return False
    classes = attr_map.get("class", "").lower()
    if tag.lower() in {"section", "div"} and any(name in classes for name in PASSIVE_CONTAINER_CLASSES):
        return False
    if tag.lower() in {"div", "figure", "img", "svg", "circle", "path", "line", "rect", "polyline", "polygon", "hr"}:
        signal = " ".join(
            [
                classes,
                attr_map.get("data-anim", ""),
                attr_map.get("data-animate", ""),
                attr_map.get("data-layout", ""),
            ]
        ).lower()
        if tag.lower() in {"img", "svg", "circle", "path", "line", "rect", "polyline", "polygon", "hr"}:
            return True
        if attr_map.get("data-anim") or attr_map.get("data-animate"):
            return True
        return any(needle in signal for _group, needles in MOTION_CLASS_GROUPS for needle in needles)
    return bool(attr_map.get("data-anim"))


def split_text_for_motion(text: str, detail: str, group: str, parent_tag: str) -> List[Tuple[str, str]]:
    if not text or not text.strip():
        return [("space", text)]

    if detail == "max" or (
        detail == "glyph"
        and contains_cjk(text)
        and (group == "title" or len(text.strip()) <= 18)
    ):
        units: List[Tuple[str, str]] = []
        for char in text:
            units.append(("space" if char.isspace() else "char", char))
        return units

    if contains_cjk(text):
        chunk_size = 3 if detail == "fine" else 6
        tokens = re.split(r"([，。！？；、,.!?;：:\s]+)", text)
        units = []
        for token in tokens:
            if not token:
                continue
            if token.isspace() or re.fullmatch(r"[，。！？；、,.!?;：:\s]+", token):
                units.append(("space", token))
                continue
            for start in range(0, len(token), chunk_size):
                units.append(("phrase", token[start : start + chunk_size]))
        return units

    tokens = re.split(r"(\s+)", text)
    units = []
    for token in tokens:
        if not token:
            continue
        units.append(("space" if token.isspace() else "word", token))
    return units


def should_wrap_text(stack: List[Dict[str, object]], text: str) -> bool:
    if not text.strip() or not stack:
        return False
    if any(str(item.get("tag", "")).lower() in SKIP_TEXT_TAGS for item in stack):
        return False
    parent = stack[-1]
    parent_tag = str(parent.get("tag", "")).lower()
    if parent_tag in {"span"} and parent.get("motionText"):
        return False
    if parent_tag in TEXT_CONTAINER_TAGS:
        return True
    attrs = parent.get("attrs", [])
    if not isinstance(attrs, list):
        return False
    attr_map = attrs_to_dict(attrs)
    signal = " ".join([attr_map.get("class", ""), attr_map.get("data-anim", "")]).lower()
    return any(needle in signal for _group, needles in MOTION_CLASS_GROUPS for needle in needles)


class MotionHtmlCompiler(HTMLParser):
    def __init__(self, scene_id: str, detail: str):
        super().__init__(convert_charrefs=True)
        self.scene_id = slugify(scene_id)
        self.detail = detail
        self.parts: List[str] = []
        self.stack: List[Dict[str, object]] = []
        self.units: List[Dict[str, object]] = []
        self.counter = 0

    def next_id(self, group: str, kind: str) -> str:
        self.counter += 1
        return "%s-%s-%s-%03d" % (self.scene_id, slugify(group), slugify(kind), self.counter)

    def add_unit(
        self,
        motion_id: str,
        *,
        kind: str,
        group: str,
        motion: Optional[str] = None,
        text: str = "",
    ) -> None:
        self.units.append(
            {
                "id": motion_id,
                "kind": kind,
                "group": group,
                "motion": motion or GROUP_MOTIONS.get(group, "unit-rise"),
                "text": text,
                "weight": max(1, len(text.strip()) if text.strip() else 1),
            }
        )

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        next_attrs = list(attrs)
        annotated = False
        if should_annotate_tag(tag_lower, next_attrs):
            group = infer_motion_group(tag_lower, next_attrs)
            kind = infer_motion_kind(tag_lower, group, next_attrs)
            motion_id = self.next_id(group, kind)
            next_attrs.extend(
                [
                    ("data-motion-id", motion_id),
                    ("data-motion-kind", kind),
                    ("data-motion-group", group),
                ]
            )
            self.add_unit(motion_id, kind=kind, group=group)
            annotated = True

        self.parts.append("<%s%s>" % (tag, render_attrs(next_attrs)))
        if tag_lower not in VOID_TAGS:
            self.stack.append(
                {
                    "tag": tag_lower,
                    "attrs": next_attrs,
                    "motionText": annotated,
                }
            )

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        next_attrs = list(attrs)
        if should_annotate_tag(tag_lower, next_attrs):
            group = infer_motion_group(tag_lower, next_attrs)
            kind = infer_motion_kind(tag_lower, group, next_attrs)
            motion_id = self.next_id(group, kind)
            next_attrs.extend(
                [
                    ("data-motion-id", motion_id),
                    ("data-motion-kind", kind),
                    ("data-motion-group", group),
                ]
            )
            self.add_unit(motion_id, kind=kind, group=group)
        self.parts.append("<%s%s/>" % (tag, render_attrs(next_attrs)))

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].get("tag") == tag_lower:
                del self.stack[index:]
                break
        self.parts.append("</%s>" % tag)

    def handle_data(self, data: str) -> None:
        if not should_wrap_text(self.stack, data):
            self.parts.append(html_escape(data))
            return

        parent = self.stack[-1]
        parent_tag = str(parent.get("tag", "")).lower()
        attrs = parent.get("attrs", [])
        group = infer_motion_group(parent_tag, attrs if isinstance(attrs, list) else [])
        for kind, text in split_text_for_motion(data, self.detail, group, parent_tag):
            if kind == "space":
                self.parts.append(html_escape(text))
                continue
            motion_id = self.next_id(group, "text-%s" % kind)
            self.add_unit(
                motion_id,
                kind="text-%s" % kind,
                group=group,
                motion="char-rise" if kind == "char" else "phrase-rise",
                text=text,
            )
            self.parts.append(
                '<span data-motion-id="%s" data-motion-kind="text-%s" data-motion-group="%s">%s</span>'
                % (motion_id, kind, group, html_escape(text))
            )

    def handle_comment(self, data: str) -> None:
        self.parts.append("<!--%s-->" % data)


def compile_motion_html(scene_id: str, section_html: str, detail: str) -> Tuple[str, List[Dict[str, object]]]:
    compiler = MotionHtmlCompiler(scene_id, detail)
    compiler.feed(section_html)
    compiler.close()
    return "".join(compiler.parts), compiler.units


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
    units: List[Dict[str, object]],
    beats: List[Dict[str, object]],
    total_frames: int,
) -> List[Dict[str, object]]:
    if not units:
        return []
    if not beats:
        beats = allocate_beat_frames(
            [
                {
                    "id": "beat-1",
                    "text": "",
                    "target": "body",
                    "motion": "content-follow",
                    "weight": 1,
                }
            ],
            total_frames,
        )

    allocated_beats = beats
    if "startFrame" not in allocated_beats[0]:
        allocated_beats = allocate_beat_frames(beats, total_frames)

    buckets: Dict[str, List[Dict[str, object]]] = {}
    beat_by_id: Dict[str, Dict[str, object]] = {}
    for index, beat in enumerate(allocated_beats):
        beat_id = str(beat.get("id", "beat-%s" % (index + 1)))
        beat_by_id[beat_id] = beat
        buckets[beat_id] = []

    for index, unit in enumerate(units):
        beat = pick_unit_beat(unit, allocated_beats, index % len(allocated_beats))
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

            next_unit = dict(unit)
            next_unit["beatId"] = beat_id
            next_unit["startFrame"] = unit_start
            next_unit["durationInFrames"] = max(1, unit_duration)
            next_unit["order"] = index
            allocated.append(next_unit)

    allocated.sort(key=lambda item: (int(item.get("startFrame", 0)), int(item.get("order", 0))))
    return allocated[:900]


def image_sort_key(path: Path) -> Tuple[int, str]:
    match = re.match(r"^(\d+)", path.stem)
    prefix = int(match.group(1)) if match else 10_000
    return prefix, path.name.lower()


def copy_template_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            copy_template_tree(item, target)
            continue
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
    screenshots_destination: Path,
    ppt_images_destination: Path,
    shot_duration: int,
) -> List[Dict[str, object]]:
    screenshots_destination.mkdir(parents=True, exist_ok=True)
    ppt_images_destination.mkdir(parents=True, exist_ok=True)

    for destination in (screenshots_destination, ppt_images_destination):
        for item in destination.iterdir():
            if item.is_file() and item.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
                item.unlink()

    prepared = []

    for index, image in enumerate(images, start=1):
        base_name = re.sub(r"^\d+[-_. ]*", "", image.stem)
        slug = slugify(base_name or "shot-%s" % index)
        file_name = "%02d-%s%s" % (index, slug, image.suffix.lower())
        screenshots_target = screenshots_destination / file_name
        ppt_target = ppt_images_destination / file_name
        shutil.copy2(image, screenshots_target)
        shutil.copy2(image, ppt_target)

        title = humanize_filename(base_name or file_name)
        prepared.append(
            {
                "id": slug,
                "src": "screenshots/%s" % file_name,
                "pptSrc": "images/%s" % file_name,
                "title": title,
                "subtitle": "Explain the user value visible in %s." % title.lower(),
                "durationInFrames": shot_duration,
            }
        )

    return prepared


def _download_default_bgm(audio_dir: Path) -> Optional[str]:
    audio_dir.mkdir(parents=True, exist_ok=True)
    target = audio_dir / DEFAULT_BGM_FILENAME
    if target.exists():
        print("Default BGM already cached: %s" % target)
        return "audio/%s" % DEFAULT_BGM_FILENAME

    print("Downloading default background music (CC0) ...")
    try:
        urllib.request.urlretrieve(DEFAULT_BGM_URL, target)
        print("Downloaded: %s" % target)
        return "audio/%s" % DEFAULT_BGM_FILENAME
    except Exception as exc:
        print("WARNING: Failed to download default BGM: %s" % exc)
        print("The video will be rendered without background music.")
        return None


def copy_background_music(
    source: Optional[str], audio_dir: Path, *, no_bgm: bool = False,
) -> Optional[str]:
    if no_bgm:
        return None

    if not source:
        return _download_default_bgm(audio_dir)

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


def html_escape(value: object) -> str:
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_default_storyboard(
    args: argparse.Namespace,
    shots: List[Dict[str, object]],
    copy_points: List[str],
) -> Dict[str, object]:
    if args.layout_style == "swiss":
        return build_swiss_storyboard(args, shots, copy_points)
    return build_editorial_storyboard(args, shots, copy_points)


def build_editorial_storyboard(
    args: argparse.Namespace,
    shots: List[Dict[str, object]],
    copy_points: List[str],
) -> Dict[str, object]:
    language = resolve_copy_language(args, " ".join(copy_points))
    intro = pick_copy_point(
        copy_points,
        0,
        "这支短片用真实界面讲清楚项目的场景、能力和最终价值。"
        if language == "zh"
        else "This trailer uses real interface states to explain the product scenario and value.",
    )
    scenes: List[Dict[str, object]] = [
        {
            "id": "cover",
            "layoutId": "A01",
            "title": args.project_name,
            "subtitle": args.tagline,
            "voiceover": "%s。%s" % (args.tagline, intro)
            if language == "zh"
            else "Introducing %s. %s %s" % (args.project_name, args.tagline, intro),
            "durationInFrames": max(args.shot_duration, 90),
            "transition": "fade",
        }
    ]

    for index, shot in enumerate(shots, start=1):
        layout = "A04" if index % 2 else "A10"
        title = scenario_title(str(shot["title"]), index, language, copy_points)
        point = pick_copy_point(
            copy_points,
            index,
            fallback_subtitle(title, language, args.scenario),
        )
        scenes.append(
            {
                "id": "shot-%s" % shot["id"],
                "layoutId": layout,
                "title": title,
                "subtitle": point,
                "image": shot["pptSrc"],
                "voiceover": "%s。%s" % (title, point)
                if language == "zh"
                else "%s. %s" % (title, point),
                "durationInFrames": shot["durationInFrames"],
                "transition": "push" if index % 2 else "fade",
            }
        )

    scenes.append(
        {
            "id": "closing",
            "layoutId": "A07",
            "title": args.closing_line,
            "subtitle": pick_copy_point(
                copy_points,
                len(shots) + 1,
                "把真实项目变成一条可发布、可复用、可解释的宣传视频。"
                if language == "zh"
                else "Turn the real project into a reusable, publishable promo video.",
            ),
            "voiceover": args.closing_line,
            "durationInFrames": max(args.shot_duration, 90),
            "transition": "fade",
        }
    )

    return {
        "style": "editorial",
        "title": args.project_name,
        "scenes": scenes,
    }


def build_swiss_storyboard(
    args: argparse.Namespace,
    shots: List[Dict[str, object]],
    copy_points: List[str],
) -> Dict[str, object]:
    language = resolve_copy_language(args, " ".join(copy_points))
    intro = pick_copy_point(
        copy_points,
        0,
        "视频直接继承 PPT 的版式系统，再用 Remotion 驱动 DOM 元素级动效。"
        if language == "zh"
        else "The video keeps the PPT layout system while Remotion drives element-level DOM motion.",
    )
    scenes: List[Dict[str, object]] = [
        {
            "id": "cover",
            "layoutId": "SWISS-COVER-ASCII",
            "title": args.project_name,
            "subtitle": args.tagline,
            "voiceover": "%s。%s" % (args.tagline, intro)
            if language == "zh"
            else "Introducing %s. %s %s" % (args.project_name, args.tagline, intro),
            "durationInFrames": max(args.shot_duration, 90),
            "transition": "fade",
        }
    ]

    layout_cycle = ["S22", "S15", "S17", "S21"]
    for index, shot in enumerate(shots, start=1):
        layout_id = layout_cycle[(index - 1) % len(layout_cycle)]
        title = scenario_title(str(shot["title"]), index, language, copy_points)
        point = pick_copy_point(
            copy_points,
            index,
            fallback_subtitle(title, language, args.scenario),
        )
        scenes.append(
            {
                "id": "shot-%s" % shot["id"],
                "layoutId": layout_id,
                "title": title,
                "subtitle": point,
                "image": shot["pptSrc"],
                "voiceover": "%s。%s" % (title, point)
                if language == "zh"
                else "%s. %s" % (title, point),
                "durationInFrames": shot["durationInFrames"],
                "transition": "push" if index % 2 else "fade",
            }
        )

    scenes.append(
        {
            "id": "closing",
            "layoutId": "SWISS-CLOSING-ASCII",
            "title": args.closing_line,
            "subtitle": pick_copy_point(
                copy_points,
                len(shots) + 1,
                "PPT 版式负责结构，Remotion 负责节奏，旁白和音乐负责把场景讲清楚。"
                if language == "zh"
                else "PPT layouts own structure; Remotion owns pacing; narration explains the scenario.",
            ),
            "voiceover": args.closing_line,
            "durationInFrames": max(args.shot_duration, 90),
            "transition": "fade",
        }
    )

    return {
        "style": "swiss",
        "title": args.project_name,
        "scenes": scenes,
    }


def load_storyboard(
    args: argparse.Namespace,
    shots: List[Dict[str, object]],
    copy_points: List[str],
) -> Dict[str, object]:
    if not args.storyboard:
        return build_default_storyboard(args, shots, copy_points)

    storyboard_path = Path(args.storyboard).resolve()
    if not storyboard_path.exists():
        raise SystemExit("Storyboard not found: %s" % storyboard_path)

    data = json.loads(storyboard_path.read_text(encoding="utf-8"))
    if "scenes" not in data or not isinstance(data["scenes"], list):
        raise SystemExit("Storyboard must contain a scenes array: %s" % storyboard_path)
    if "style" not in data:
        data["style"] = args.layout_style
    if "title" not in data:
        data["title"] = args.project_name
    return data


def scene_attr(scene: Dict[str, object], key: str, fallback: str = "") -> str:
    value = scene.get(key)
    if value is None:
        return fallback
    return str(value)


def render_editorial_scene(scene: Dict[str, object], index: int, total: int) -> str:
    layout_id = scene_attr(scene, "layoutId", "A04")
    title = html_escape(scene_attr(scene, "title", "Key Screen"))
    subtitle = html_escape(scene_attr(scene, "subtitle", "Explain the user value visible here."))
    image = html_escape(scene_attr(scene, "image", "images/01-home.png"))
    scene_id = html_escape(scene_attr(scene, "id", "scene-%s" % index))
    page = "%02d / %02d" % (index, total)

    if layout_id == "A01":
        return f"""
<section class="slide hero dark" data-layout="A01" data-scene-id="{scene_id}" data-title="{title}">
  <div class="chrome"><div>Product Trailer</div><div>Vol.01</div></div>
  <div class="frame" style="display:grid; gap:4vh; align-content:center; min-height:80vh">
    <div class="kicker" data-anim>Project Promo</div>
    <h1 class="h-hero" data-anim>{title}</h1>
    <h2 class="h-sub" data-anim>{subtitle}</h2>
    <p class="lead" style="max-width:60vw" data-anim>Rendered through the same layout language as the reference PPT.</p>
  </div>
  <div class="foot"><div>Generated with PPT layouts</div><div>- 2026 -</div></div>
</section>
"""

    if layout_id == "A07":
        return f"""
<section class="slide hero dark" data-layout="A07" data-scene-id="{scene_id}" data-title="{title}">
  <div class="chrome"><div>Closing</div><div>{page}</div></div>
  <div class="frame" style="display:grid; gap:8vh; align-content:center; min-height:80vh">
    <div class="kicker" data-anim>The Promise</div>
    <h1 class="h-hero" style="font-size:7vw; line-height:1.15" data-anim>{title}</h1>
    <p class="lead" style="max-width:50vw" data-anim>{subtitle}</p>
  </div>
  <div class="foot"><div>Product trailer - closing</div><div>- - -</div></div>
</section>
"""

    if layout_id == "A05":
        images = scene.get("images")
        if not isinstance(images, list) or not images:
            images = [scene_attr(scene, "image", "images/01-home.png")]
        figures = []
        for img_index, img in enumerate(images[:6], start=1):
            figures.append(
                f"""<figure class="frame-img" style="height:26vh" data-anim>
        <img src="{html_escape(img)}" alt="{title} {img_index}">
        <figcaption class="img-cap">Evidence - {img_index:02d}</figcaption>
      </figure>"""
            )
        return f"""
<section class="slide light" data-layout="A05" data-scene-id="{scene_id}" data-title="{title}">
  <div class="chrome"><div>Visual Evidence</div><div>{page}</div></div>
  <div class="frame" style="padding-top:5vh">
    <div class="kicker" data-anim>Proof - Screens</div>
    <h2 class="h-xl" data-anim>{title}</h2>
    <div class="grid-3-3" style="margin-top:4vh">
      {''.join(figures)}
    </div>
  </div>
  <div class="foot"><div>{subtitle}</div><div>Image Grid</div></div>
</section>
"""

    if layout_id == "A10":
        return f"""
<section class="slide light" data-layout="A10" data-scene-id="{scene_id}" data-title="{title}">
  <div class="chrome"><div>Product Detail</div><div>{page}</div></div>
  <div class="frame grid-2-8-4" style="padding-top:6vh">
    <div>
      <div class="kicker" data-anim>Detail - Flow</div>
      <h2 class="h-xl" style="margin-top:1vh; margin-bottom:3vh" data-anim>{title}</h2>
      <p class="lead" style="margin-bottom:3vh" data-anim>{subtitle}</p>
      <div class="callout" style="margin-top:3vh" data-anim>
        "The product should stay readable while the video does the pacing."
        <div class="callout-src">- Project Promo Video</div>
      </div>
    </div>
    <figure class="frame-img r-3x4 fit-contain" data-anim>
      <img src="{image}" alt="{title}">
      <figcaption class="img-cap">{title}</figcaption>
    </figure>
  </div>
  <div class="foot"><div>Page {index:02d} - PPT layout A10</div><div>Lead Image + Side Text</div></div>
</section>
"""

    return f"""
<section class="slide light" data-layout="A04" data-scene-id="{scene_id}" data-title="{title}">
  <div class="chrome"><div>Product Proof</div><div>{page}</div></div>
  <div class="frame grid-2-7-5" style="padding-top:6vh">
    <div style="display:flex; flex-direction:column; justify-content:space-between; gap:3vh">
      <div>
        <div class="kicker" data-anim>Screen - Evidence</div>
        <h2 class="h-xl" style="white-space:nowrap; font-size:7.2vw" data-anim>{title}</h2>
        <p class="lead" style="margin-top:3vh" data-anim>{subtitle}</p>
      </div>
      <div class="callout" data-anim>
        "Use the real interface as the proof."
        <div class="callout-src">- Project Promo Video</div>
      </div>
    </div>
    <figure class="frame-img r-16x10 fit-contain" data-anim>
      <img src="{image}" alt="{title}">
      <figcaption class="img-cap">{title}</figcaption>
    </figure>
  </div>
  <div class="foot"><div>Page {index:02d} - PPT layout A04</div><div>Quote + Image</div></div>
</section>
"""


def render_swiss_scene(scene: Dict[str, object], index: int, total: int) -> str:
    layout_id = scene_attr(scene, "layoutId", "S22")
    title = html_escape(scene_attr(scene, "title", "Key Screen"))
    subtitle = html_escape(scene_attr(scene, "subtitle", "Explain the user value visible here."))
    image = html_escape(scene_attr(scene, "image", "images/01-home.png"))
    scene_id = html_escape(scene_attr(scene, "id", "scene-%s" % index))
    page = "%02d / %02d" % (index, total)

    if layout_id in {"S01", "SWISS-COVER-ASCII"}:
        return f"""
<section class="slide accent" data-layout="SWISS-COVER-ASCII" data-animate="hero" data-scene-id="{scene_id}" data-title="{title}">
  <div class="canvas-card">
    <canvas class="ascii-bg" aria-hidden="true"></canvas>
    <div class="chrome-min"><div class="l">Product Trailer - Swiss Layout</div><div class="r">SS - {page}</div></div>
    <div style="flex:1;padding:0;display:grid;grid-template-rows:auto 1fr auto;gap:2.6vh">
      <div data-anim="kicker" class="t-meta" style="color:rgba(255,255,255,.78);letter-spacing:.22em">VIDEO FROM PPT LAYOUTS</div>
      <h1 data-anim="title" style="align-self:center;font-family:var(--sans),var(--sans-zh);font-weight:200;font-size:min(11.6vw,19vh);line-height:.94;letter-spacing:-.025em;color:#fff">{title}</h1>
      <div data-anim="bottom" style="display:grid;grid-template-rows:auto auto;gap:1.6vh;border-top:1px solid rgba(255,255,255,.22);padding-top:2vh">
        <div class="lead" style="max-width:52ch;color:rgba(255,255,255,.86);font-weight:300">{subtitle}</div>
        <div class="t-meta" style="color:rgba(255,255,255,.6)">Rendered by guizang PPT layout engine</div>
      </div>
    </div>
  </div>
</section>
"""

    if layout_id in {"S10", "SWISS-CLOSING-ASCII"}:
        return f"""
<section class="slide split" data-layout="SWISS-CLOSING-ASCII" data-animate="split-statement" data-scene-id="{scene_id}" data-title="{title}">
  <div class="canvas-card">
    <div class="split-half">
      <div class="half b-accent" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between;position:relative;overflow:hidden">
        <canvas class="ascii-bg" aria-hidden="true"></canvas>
        <div class="chrome-min"><div class="l">Closing</div><div class="r">{page}</div></div>
        <h2 data-anim="left" style="font-family:var(--sans),var(--sans-zh);font-weight:200;font-size:min(7.4vw,13vh);line-height:.94;letter-spacing:-.035em;color:#fff">{title}</h2>
      </div>
      <div class="half" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between">
        <div class="chrome-min"><div class="l">Next</div><div class="r">CTA</div></div>
        <div style="display:grid;gap:3vh;align-content:center;min-height:62vh">
          <div class="t-meta" data-anim="right">FINAL PROOF</div>
          <p class="lead" data-anim="right">{subtitle}</p>
          <div class="hr-hairline" data-anim="right"></div>
          <p class="body" data-anim="right">Keep video, voiceover and BGM simple. Let the PPT layout carry the visual system.</p>
        </div>
      </div>
    </div>
  </div>
</section>
"""

    if layout_id == "S11":
        return f"""
<section class="slide light" data-layout="S11" data-animate="timeline-walk" data-scene-id="{scene_id}" data-title="{title}">
  <div class="canvas-card" style="display:flex;flex-direction:column;gap:5.2vh">
    <div data-anim="line" style="display:grid;grid-template-columns:1fr auto;gap:3vw;align-items:end">
      <div>
        <div class="t-cat">Workflow</div>
        <h2 style="font-family:var(--sans),var(--sans-zh);font-size:min(6.2vw,10vh);font-weight:200;line-height:.98;letter-spacing:-.04em">{title}</h2>
      </div>
      <div class="t-meta">{page}</div>
    </div>
    <div class="timeline-h" data-anim="up" style="position:relative;flex:1;display:grid;grid-template-columns:repeat(5,1fr);align-items:center;border-top:1px solid var(--ink);border-bottom:1px solid var(--border-subtle)">
      <div class="th-node up"><div class="dot"></div><div class="label">01<br/>PPT Layout</div></div>
      <div class="th-node"><div class="dot"></div><div class="label">02<br/>DOM Slots</div></div>
      <div class="th-node up"><div class="dot"></div><div class="label">03<br/>Remotion Frame</div></div>
      <div class="th-node"><div class="dot"></div><div class="label">04<br/>Voiceover</div></div>
      <div class="th-node up"><div class="dot"></div><div class="label">05<br/>Final Video</div></div>
    </div>
    <div class="t-meta" data-anim="up">{subtitle}</div>
  </div>
</section>
"""

    if layout_id == "S15":
        card_titles = [
            ("Layout", "PPT 版式先行"),
            ("Motion", "元素级入场"),
            ("Voice", "旁白匹配内容"),
            ("BGM", "自动压低音乐"),
            ("Render", "Remotion 输出"),
            ("Reuse", "Skill 可复用"),
        ]
        cards = []
        for card_index, (label, body) in enumerate(card_titles, start=1):
            if card_index == 1:
                cards.append(
                    f"""<div class="sub-card" style="padding:1.4vh 1vw;border:1px solid var(--border-subtle);display:grid;gap:1vh">
        <div class="frame-img r-21x9" style="background:var(--grey-1);overflow:hidden"><img src="{image}" data-image-slot="s15-grid-21x9" alt="{title}" style="width:100%;height:100%;object-fit:cover"></div>
        <div class="t-meta">{label}</div><div class="body-sm">{body}</div>
      </div>"""
                )
            else:
                cards.append(
                    f"""<div class="sub-card" style="padding:1.8vh 1.2vw;border:1px solid var(--border-subtle);display:flex;flex-direction:column;justify-content:space-between;min-height:18vh">
        <div class="t-meta">{label}</div>
        <div style="font-family:var(--sans),var(--sans-zh);font-size:min(2.2vw,4vh);font-weight:300;line-height:1.08;letter-spacing:-.025em">{body}</div>
        <div class="hr-hairline"></div>
      </div>"""
                )
        return f"""
<section class="slide light" data-layout="S15" data-animate="matrix-fill" data-scene-id="{scene_id}" data-title="{title}">
  <div class="canvas-card" style="display:flex;flex-direction:column;gap:3.8vh">
    <div data-anim="line" style="display:grid;grid-template-columns:1fr auto;gap:3vw;align-items:end">
      <div>
        <div class="t-cat">Compatibility Matrix</div>
        <h2 style="font-family:var(--sans),var(--sans-zh);font-size:min(5.8vw,9.4vh);font-weight:200;line-height:.98;letter-spacing:-.04em">{title}</h2>
      </div>
      <div class="t-meta">{page}</div>
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:repeat(3,1fr);gap:1.4vh 1.2vw;flex:1">
      {''.join(cards)}
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:1.2fr 2fr;gap:2vw;align-items:end;border-top:1px solid var(--ink);padding-top:1.8vh">
      <div><div class="t-meta">Coverage</div><div style="font-family:var(--sans);font-size:min(5.2vw,8vh);font-weight:200;line-height:.9">A01-S22</div></div>
      <p class="body">{subtitle}</p>
    </div>
  </div>
</section>
"""

    if layout_id == "S17":
        return f"""
<section class="slide light" data-layout="S17" data-animate="system-diagram" data-scene-id="{scene_id}" data-title="{title}">
  <div class="canvas-card" style="display:flex;flex-direction:column;gap:4.4vh">
    <div data-anim="line" style="display:grid;grid-template-columns:1fr auto;gap:3vw;align-items:end">
      <div>
        <div class="t-cat">System Diagram</div>
        <h2 style="font-family:var(--sans),var(--sans-zh);font-size:min(6vw,9.6vh);font-weight:200;line-height:.98;letter-spacing:-.04em">{title}</h2>
      </div>
      <div class="t-meta">{page}</div>
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:2.2vw;flex:1;align-items:stretch">
      <div class="card-fill" style="border:1px solid var(--border-subtle);padding:3vh 2vw;display:grid;grid-template-rows:1fr auto;gap:2vh">
        <svg viewBox="0 0 220 180" aria-hidden="true"><circle cx="110" cy="90" r="72" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="110" cy="90" r="38" fill="var(--accent)" opacity=".18"/></svg>
        <div><div class="t-meta">PPT DOM</div><p class="body-sm">版式、网格、图片槽和文字层级保留在 HTML 中。</p></div>
      </div>
      <div class="card-fill" style="border:1px solid var(--ink);padding:3vh 2vw;display:grid;grid-template-rows:1fr auto;gap:2vh">
        <svg viewBox="0 0 220 180" aria-hidden="true"><circle cx="110" cy="90" r="78" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="110" cy="90" r="52" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="110" cy="90" r="22" fill="var(--ink)" opacity=".9"/></svg>
        <div><div class="t-meta">Remotion</div><p class="body-sm">useCurrentFrame、spring、interpolate 直接驱动 DOM 节点。</p></div>
      </div>
      <div class="card-fill" style="border:1px solid var(--border-subtle);padding:3vh 2vw;display:grid;grid-template-rows:1fr auto;gap:2vh">
        <svg viewBox="0 0 220 180" aria-hidden="true"><circle cx="70" cy="88" r="34" fill="var(--accent)" opacity=".18"/><circle cx="150" cy="88" r="34" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="104" y1="88" x2="116" y2="88" stroke="currentColor"/></svg>
        <div><div class="t-meta">Audio</div><p class="body-sm">旁白按场景生成，BGM 根据语音自动 ducking。</p></div>
      </div>
    </div>
    <p class="body" data-anim="up">{subtitle}</p>
  </div>
</section>
"""

    if layout_id == "S21":
        return f"""
<section class="slide light" data-layout="S21" data-animate="tech-spec" data-scene-id="{scene_id}" data-title="{title}">
  <div class="canvas-card" style="display:flex;flex-direction:column;gap:3.6vh">
    <div data-anim="line" style="display:grid;grid-template-columns:1fr auto;gap:3vw;align-items:end">
      <div>
        <div class="t-cat">Motion Spec</div>
        <h2 style="font-family:var(--sans),var(--sans-zh);font-size:min(5.8vw,9.2vh);font-weight:200;line-height:.98;letter-spacing:-.04em">{title}</h2>
      </div>
      <div class="t-meta">{page}</div>
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:1.35fr 1fr 1fr 1fr;gap:2vw;align-items:stretch">
      <div style="display:flex;flex-direction:column;justify-content:space-between;border-top:1px solid var(--ink);padding-top:2vh">
        <div style="font-family:var(--sans),var(--sans-zh);font-size:min(4.6vw,7.8vh);font-weight:200;line-height:.95;letter-spacing:-.04em">PPT DOM<br/>Motion</div>
        <p class="body-sm">{subtitle}</p>
      </div>
      <div><div style="height:1px;background:var(--ink)"></div><div class="t-meta">Spring</div><div class="kpi-num" style="font-family:var(--sans);font-size:min(4.2vw,7vh);font-weight:200">18</div><p class="body-sm">damping</p></div>
      <div><div style="height:1px;background:var(--ink)"></div><div class="t-meta">Frame</div><div class="kpi-num" style="font-family:var(--sans);font-size:min(4.2vw,7vh);font-weight:200">30</div><p class="body-sm">fps</p></div>
      <div><div style="height:1px;background:var(--accent)"></div><div class="t-meta">Mode</div><div class="kpi-num" style="font-family:var(--sans);font-size:min(4.2vw,7vh);font-weight:200;color:var(--accent)">DOM</div><p class="body-sm">not PNG only</p></div>
    </div>
    <div data-anim="hero" style="display:grid;grid-template-columns:1.4fr 1fr .8fr;gap:2vw;align-items:end;border-top:1px solid var(--border-subtle);padding-top:2.4vh">
      <div class="bottom-hero" style="font-family:var(--sans),var(--sans-zh);font-size:min(7.2vw,12vh);font-weight:200;line-height:.9;letter-spacing:-.05em">Frame<br/>Driven</div>
      <div><div style="height:1px;background:var(--ink);margin-bottom:1.2vh"></div><p class="body-sm">每一页保留 PPT 的布局骨架，动画只改变节点可见性、位移、缩放和图表生长。</p></div>
      <div data-anim="bars" style="height:22vh;display:flex;gap:.42vw;align-items:end">
        <div class="vbar" style="height:35%;background:var(--ink);width:100%"></div><div class="vbar" style="height:52%;background:var(--ink);width:100%"></div><div class="vbar" style="height:68%;background:var(--accent);width:100%"></div><div class="vbar" style="height:44%;background:var(--ink);width:100%"></div><div class="vbar" style="height:82%;background:var(--accent);width:100%"></div>
      </div>
    </div>
  </div>
</section>
"""

    return f"""
<section class="slide light" data-layout="S22" data-animate="image-hero" data-scene-id="{scene_id}" data-title="{title}">
  <div class="canvas-card" style="padding:0;display:flex;flex-direction:column;overflow:hidden">
    <div data-anim="img" style="position:relative;flex:0 0 60%;overflow:hidden;background:var(--grey-1)">
      <img src="{image}" alt="{title}" loading="eager" data-image-slot="s22-hero-21x9" style="position:absolute;inset:0;width:100%;height:100%;object-fit:contain;object-position:center center;background:var(--paper)">
      <div class="chrome-min" style="position:absolute;top:0;left:0;right:0;color:rgba(0,0,0,.72);padding:5.6vh 5vw 0">
        <div class="l">Section - Visual Evidence</div><div class="r">{page}</div>
      </div>
      <div data-anim="title-block" style="position:absolute;left:5vw;top:11vh;background:var(--paper);padding:3.2vh 3.2vw;max-width:40vw">
        <div style="font-family:var(--sans),var(--sans-zh);font-weight:200;font-size:min(5.2vw,9vh);line-height:1;letter-spacing:-.035em;color:var(--text-primary)">{title}</div>
      </div>
    </div>
    <div data-anim="kpi" class="image-hero-body">
      <div style="max-width:48ch;font-family:var(--sans),var(--sans-zh);font-size:max(15px,1.3vw);line-height:1.55;font-weight:300;color:var(--text-primary);letter-spacing:-.005em">{subtitle}</div>
      <div class="image-hero-stats" style="gap:4vw">
        <div style="display:flex;flex-direction:column;gap:.6vh"><div style="height:1px;background:var(--ink)"></div><div class="t-meta">Layout</div><div style="font-family:var(--sans);font-weight:200;font-size:min(4.6vw,7.6vh);line-height:.95;letter-spacing:-.04em">S22</div><div style="height:1px;background:var(--border-subtle);margin-top:auto"></div><p class="body-sm">Image hero slot</p></div>
        <div style="display:flex;flex-direction:column;gap:.6vh"><div style="height:1px;background:var(--ink)"></div><div class="t-meta">Mode</div><div style="font-family:var(--sans);font-weight:200;font-size:min(4.6vw,7.6vh);line-height:.95;letter-spacing:-.04em">PPT</div><div style="height:1px;background:var(--border-subtle);margin-top:auto"></div><p class="body-sm">Browser rendered</p></div>
        <div style="display:flex;flex-direction:column;gap:.6vh"><div style="height:1px;background:var(--ink)"></div><div class="t-meta">Video</div><div style="font-family:var(--sans);font-weight:200;font-size:min(4.6vw,7.6vh);line-height:.95;letter-spacing:-.04em;color:var(--accent)">30fps</div><div style="height:1px;background:var(--border-subtle);margin-top:auto"></div><p class="body-sm">Remotion timeline</p></div>
      </div>
    </div>
  </div>
</section>
"""


def render_scene(scene: Dict[str, object], style: str, index: int, total: int) -> str:
    section_html = scene.get("sectionHtml")
    if isinstance(section_html, str) and section_html.strip():
        return section_html.strip()
    if style == "swiss":
        return render_swiss_scene(scene, index, total)
    return render_editorial_scene(scene, index, total)


def copy_ppt_assets(ppt_skill_dir: Path, ppt_dir: Path) -> None:
    source_assets = ppt_skill_dir / "assets"
    target_assets = ppt_dir / "assets"
    target_assets.mkdir(parents=True, exist_ok=True)

    for item in source_assets.iterdir():
        if item.name in {"template.html", "template-swiss.html"}:
            continue
        target = target_assets / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def replace_deck_slides(deck: str, sections: str) -> str:
    deck_start_marker = '<div id="deck">'
    nav_marker = '<div id="nav">'
    deck_start = deck.find(deck_start_marker)
    nav_start = deck.find(nav_marker, deck_start)

    if deck_start != -1 and nav_start != -1:
        content_start = deck_start + len(deck_start_marker)
        return (
            deck[:content_start]
            + "\n\n"
            + sections
            + "\n\n</div>\n\n"
            + deck[nav_start:]
        )

    if "<!-- SLIDES_HERE -->" in deck:
        return deck.replace("<!-- SLIDES_HERE -->", sections)

    return re.sub(r"<!-- SLIDES_HERE[\s\S]*?-->", sections, deck, count=1)


def extract_template_css(template_path: Path) -> str:
    template = template_path.read_text(encoding="utf-8")
    blocks = re.findall(r"<style[^>]*>([\s\S]*?)</style>", template, flags=re.IGNORECASE)
    return "\n\n".join(block.strip() for block in blocks if block.strip())


def write_ppt_template_css(path: Path, ppt_skill_dir: Path, style: str) -> None:
    template_name = "template-swiss.html" if style == "swiss" else "template.html"
    template_path = ppt_skill_dir / "assets" / template_name
    css = extract_template_css(template_path)
    if not css:
        raise SystemExit("No PPT template CSS found in: %s" % template_path)
    header = "/* Generated from %s. Edit the PPT template or storyboard, not this file. */\n" % template_name
    path.write_text(header + css + "\n", encoding="utf-8")


def normalize_section_html_for_remotion(section_html: str) -> str:
    html = section_html
    html = re.sub(r'((?:src|href)=["\'])images/', r"\1/ppt/images/", html)
    html = re.sub(r'((?:src|href)=["\'])assets/', r"\1/ppt/assets/", html)
    return html


def build_ppt_deck(
    ppt_skill_dir: Path,
    ppt_dir: Path,
    storyboard: Dict[str, object],
    motion_detail: str,
) -> Tuple[Path, List[Dict[str, object]]]:
    style = str(storyboard.get("style", "editorial"))
    template_name = "template-swiss.html" if style == "swiss" else "template.html"
    template_path = ppt_skill_dir / "assets" / template_name
    if not template_path.exists():
        raise SystemExit("PPT template not found: %s" % template_path)

    scenes = storyboard.get("scenes", [])
    if not isinstance(scenes, list) or not scenes:
        raise SystemExit("Storyboard must have at least one scene.")

    copy_ppt_assets(ppt_skill_dir, ppt_dir)

    sections = []
    total = len(scenes)
    normalized_scenes: List[Dict[str, object]] = []
    for index, raw_scene in enumerate(scenes, start=1):
        if not isinstance(raw_scene, dict):
            raise SystemExit("Storyboard scene %s is not an object." % index)
        scene = dict(raw_scene)
        scene.setdefault("id", "scene-%s" % index)
        scene.setdefault("layoutId", "S22" if style == "swiss" else "A04")
        scene.setdefault("title", "Scene %s" % index)
        scene.setdefault("durationInFrames", DEFAULT_SCENE_FRAMES)
        scene.setdefault("transition", "fade")
        normalized_scenes.append(scene)
        section_html = render_scene(scene, style, index, total)
        compiled_html, motion_units = compile_motion_html(
            str(scene.get("id", "scene-%s" % index)),
            section_html,
            motion_detail,
        )
        scene["_sectionHtml"] = compiled_html
        scene["_motionUnits"] = motion_units
        scene["_motionDetail"] = motion_detail
        sections.append(compiled_html)

    deck = template_path.read_text(encoding="utf-8")
    deck = re.sub(
        r"<title>.*?</title>",
        "<title>%s</title>" % html_escape(storyboard.get("title", "Project Promo")),
        deck,
        flags=re.DOTALL,
    )
    deck = replace_deck_slides(deck, "\n\n".join(sections))

    ppt_dir.mkdir(parents=True, exist_ok=True)
    deck_path = ppt_dir / "index.html"
    deck_path.write_text(deck, encoding="utf-8")
    return deck_path, normalized_scenes


def run_slide_renderer(script_dir: Path, deck_path: Path, slides_dir: Path) -> List[Dict[str, object]]:
    manifest_path = slides_dir / "render-manifest.json"
    command = [
        "node",
        str(script_dir / "render_ppt_slides.mjs"),
        "--deck",
        str(deck_path),
        "--output-dir",
        str(slides_dir),
        "--manifest",
        str(manifest_path),
    ]
    subprocess.run(command, check=True, cwd=script_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    slides = manifest.get("slides", [])
    if not isinstance(slides, list) or not slides:
        raise SystemExit("Slide renderer did not produce slides: %s" % manifest_path)
    return slides


def expected_rendered_slides(scenes: List[Dict[str, object]]) -> List[Dict[str, object]]:
    slides = []
    for index, scene in enumerate(scenes, start=1):
        scene_id = str(scene.get("id", "scene-%s" % index))
        slides.append(
            {
                "id": scene_id,
                "layoutId": str(scene.get("layoutId", "PPT")),
                "title": str(scene.get("title", "Scene %s" % index)),
                "src": "slides/%03d-%s.png" % (index, slugify(scene_id)),
            }
        )
    return slides


def write_promo_data(
    path: Path,
    project_name: str,
    tagline: str,
    closing_line: str,
    accent: str,
    background: str,
    layout_style: str,
    rendered_slides: List[Dict[str, object]],
    scenes: List[Dict[str, object]],
    music_file: Optional[str],
    render_mode: str,
) -> None:
    slide_blocks = []
    ppt_scene_blocks = []
    for index, slide in enumerate(rendered_slides):
        scene = scenes[index] if index < len(scenes) else {}
        scene_id = str(scene.get("id", slide.get("id", "slide")))
        layout_id = str(scene.get("layoutId", slide.get("layoutId", "PPT")))
        title = str(scene.get("title", slide.get("title", "Scene")))
        subtitle = str(scene.get("subtitle", ""))
        duration = int(scene.get("durationInFrames", DEFAULT_SCENE_FRAMES))
        transition = str(scene.get("transition", "fade"))
        slide_blocks.append(
            "\n".join(
                [
                    "  {",
                    "    id: %s," % json.dumps(scene_id, ensure_ascii=False),
                    "    layoutId: %s," % json.dumps(layout_id, ensure_ascii=False),
                    "    src: %s," % json.dumps(str(slide["src"]), ensure_ascii=False),
                    "    title: %s," % json.dumps(title, ensure_ascii=False),
                    "    subtitle: %s," % json.dumps(subtitle, ensure_ascii=False),
                    "    durationInFrames: %s," % duration,
                    "    transition: %s," % json.dumps(transition, ensure_ascii=False),
                    "  },",
                ]
            )
        )
        section_html = normalize_section_html_for_remotion(str(scene.get("_sectionHtml", "")))
        ppt_scene_blocks.append(
            "\n".join(
                [
                    "  {",
                    "    id: %s," % json.dumps(scene_id, ensure_ascii=False),
                    "    layoutId: %s," % json.dumps(layout_id, ensure_ascii=False),
                    "    src: %s," % json.dumps(str(slide["src"]), ensure_ascii=False),
                    "    title: %s," % json.dumps(title, ensure_ascii=False),
                    "    subtitle: %s," % json.dumps(subtitle, ensure_ascii=False),
                    "    durationInFrames: %s," % duration,
                    "    transition: %s," % json.dumps(transition, ensure_ascii=False),
                    "    html: %s," % json.dumps(section_html, ensure_ascii=False),
                    "  },",
                ]
            )
        )

    content = "\n".join(
        [
            "export const FPS = 30;",
            "",
            "export type RenderedSlide = {",
            "  id: string;",
            "  layoutId: string;",
            "  src: string;",
            "  title: string;",
            "  subtitle?: string;",
            "  durationInFrames: number;",
            '  transition?: "fade" | "cut" | "push";',
            "};",
            "",
            "export type PptScene = RenderedSlide & {",
            "  html: string;",
            "};",
            "",
            "export const promoMeta = {",
            "  projectName: %s," % json.dumps(project_name, ensure_ascii=False),
            "  tagline: %s," % json.dumps(tagline, ensure_ascii=False),
            "  closingLine: %s," % json.dumps(closing_line, ensure_ascii=False),
            "  accent: %s," % json.dumps(accent, ensure_ascii=False),
            "  background: %s," % json.dumps(background, ensure_ascii=False),
            "  layoutStyle: %s," % json.dumps(layout_style, ensure_ascii=False),
            '  renderMode: %s as "ppt-dom" | "slides",'
            % json.dumps(render_mode, ensure_ascii=False),
            "  backgroundMusic: {",
            "    file: %s," % ("null" if music_file is None else json.dumps(music_file)),
            "    volume: 0.18,",
            "  },",
            "};",
            "",
            "export const renderedSlides: RenderedSlide[] = [",
            *slide_blocks,
            "];",
            "",
            "export const pptScenes: PptScene[] = [",
            *ppt_scene_blocks,
            "];",
        ]
    )
    path.write_text("%s\n" % content, encoding="utf-8")


def build_voiceover_scenes(scenes: List[Dict[str, object]]) -> List[Dict[str, object]]:
    voiceover_scenes = []
    for index, scene in enumerate(scenes, start=1):
        title = str(scene.get("title", "Scene %s" % index))
        text = str(scene.get("voiceover") or scene.get("subtitle") or title)
        beats = build_scene_beats(scene, text, title)
        allocated_beats = allocate_beat_frames(beats, int(scene.get("durationInFrames", DEFAULT_SCENE_FRAMES)))
        raw_motion_units = scene.get("_motionUnits")
        motion_units = allocate_motion_unit_frames(
            raw_motion_units if isinstance(raw_motion_units, list) else [],
            allocated_beats,
            int(scene.get("durationInFrames", DEFAULT_SCENE_FRAMES)),
        )
        voiceover_scenes.append(
            {
                "id": str(scene.get("id", "scene-%s" % index)),
                "title": title,
                "text": text,
                "beats": allocated_beats,
                "motionUnits": motion_units,
                "motionDetail": str(scene.get("_motionDetail", "glyph")),
                "minFrames": int(scene.get("durationInFrames", DEFAULT_SCENE_FRAMES)),
                "paddingFrames": int(scene.get("paddingFrames", 18)),
            }
        )
    return voiceover_scenes


def write_voiceover_script(path: Path, scenes: List[Dict[str, object]]) -> None:
    payload = {"fps": FPS, "voice": "auto", "scenes": scenes}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def motion_unit_ts_block(unit: Dict[str, object], indent: str = "      ") -> str:
    return "\n".join(
        [
            "%s{" % indent,
            "%s  id: %s," % (indent, json.dumps(str(unit.get("id", "unit")), ensure_ascii=False)),
            "%s  kind: %s," % (indent, json.dumps(str(unit.get("kind", "container")), ensure_ascii=False)),
            "%s  group: %s," % (indent, json.dumps(str(unit.get("group", "body")), ensure_ascii=False)),
            "%s  motion: %s," % (indent, json.dumps(str(unit.get("motion", "unit-rise")), ensure_ascii=False)),
            "%s  text: %s," % (indent, json.dumps(str(unit.get("text", "")), ensure_ascii=False)),
            "%s  beatId: %s," % (indent, json.dumps(str(unit.get("beatId", "")), ensure_ascii=False)),
            "%s  startFrame: %s," % (indent, int(unit.get("startFrame", 0))),
            "%s  durationInFrames: %s," % (indent, int(unit.get("durationInFrames", 18))),
            "%s}," % indent,
        ]
    )


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
        beats = scene.get("beats")
        if not isinstance(beats, list) or not beats:
            beats = [
                {
                    "id": "%s-beat-1" % scene["id"],
                    "text": scene["title"],
                    "target": "title",
                    "motion": "title-reveal",
                    "startFrame": 0,
                    "durationInFrames": scene["minFrames"],
                }
            ]
        beats = allocate_beat_frames(beats, int(scene["minFrames"]))
        beat_blocks = []
        for beat in beats:
            beat_blocks.append(
                "\n".join(
                    [
                        "      {",
                        "        id: %s," % json.dumps(str(beat.get("id", "beat")), ensure_ascii=False),
                        "        text: %s," % json.dumps(str(beat.get("text", "")), ensure_ascii=False),
                        "        target: %s," % json.dumps(str(beat.get("target", "body")), ensure_ascii=False),
                        "        motion: %s," % json.dumps(str(beat.get("motion", "content-follow")), ensure_ascii=False),
                        "        startFrame: %s," % int(beat.get("startFrame", 0)),
                        "        durationInFrames: %s," % int(beat.get("durationInFrames", scene["minFrames"])),
                        "      },",
                    ]
                )
            )
        motion_units = scene.get("motionUnits")
        if not isinstance(motion_units, list):
            motion_units = []
        if motion_units and "startFrame" not in motion_units[0]:
            motion_units = allocate_motion_unit_frames(motion_units, beats, int(scene["minFrames"]))
        unit_blocks = [motion_unit_ts_block(unit) for unit in motion_units]
        scene_blocks.append(
            "\n".join(
                [
                    "  {",
                    "    id: %s," % json.dumps(scene["id"], ensure_ascii=False),
                    "    title: %s," % json.dumps(scene["title"], ensure_ascii=False),
                    "    durationInFrames: %s," % scene["minFrames"],
                    "    audioFile: %s,"
                    % ("null" if audio_file is None else json.dumps(audio_file)),
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


def resolve_ppt_skill_dir(args: argparse.Namespace, script_dir: Path) -> Path:
    if args.ppt_skill:
        return Path(args.ppt_skill).resolve()
    repo_root = script_dir.parent.parent
    return (repo_root / "extra" / "guizang-ppt-skill").resolve()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    skill_dir = script_dir.parent
    template_dir = skill_dir / "assets" / "remotion-template"
    ppt_skill_dir = resolve_ppt_skill_dir(args, script_dir)

    workspace = Path(args.workspace).resolve()
    screenshot_dir = Path(args.screenshots).resolve()

    if not template_dir.exists():
        raise SystemExit("Template not found: %s" % template_dir)

    if not ppt_skill_dir.exists():
        raise SystemExit(
            "PPT skill not found: %s. Pass --ppt-skill <path> to use another copy."
            % ppt_skill_dir
        )

    if not screenshot_dir.exists():
        raise SystemExit("Screenshot directory not found: %s" % screenshot_dir)

    images = collect_images(screenshot_dir)
    if not images:
        raise SystemExit("No supported screenshots found in: %s" % screenshot_dir)

    copy_template_tree(template_dir, workspace)

    screenshots_dir = workspace / "public" / "screenshots"
    slides_dir = workspace / "public" / "slides"
    ppt_dir = workspace / "public" / "ppt"
    ppt_images_dir = ppt_dir / "images"
    audio_dir = workspace / "public" / "audio"
    voiceover_dir = audio_dir / "voiceover"
    voiceover_dir.mkdir(parents=True, exist_ok=True)
    slides_dir.mkdir(parents=True, exist_ok=True)

    shots = prepare_public_screenshots(
        images,
        screenshots_dir,
        ppt_images_dir,
        args.shot_duration,
    )
    write_manifest(screenshots_dir / "manifest.json", shots)

    copy_points = load_copy_points(args)
    storyboard = load_storyboard(args, shots, copy_points)
    deck_path, scenes = build_ppt_deck(ppt_skill_dir, ppt_dir, storyboard, args.motion_detail)

    if args.skip_slide_render:
        rendered_slides = expected_rendered_slides(scenes)
    else:
        rendered_slides = run_slide_renderer(script_dir, deck_path, slides_dir)

    music_file = copy_background_music(args.bgm_file, audio_dir, no_bgm=args.no_bgm)

    src_dir = workspace / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    write_ppt_template_css(
        src_dir / "ppt-template.css",
        ppt_skill_dir=ppt_skill_dir,
        style=str(storyboard.get("style", args.layout_style)),
    )
    write_promo_data(
        src_dir / "promo-data.ts",
        project_name=args.project_name,
        tagline=args.tagline,
        closing_line=args.closing_line,
        accent=args.accent,
        background=args.background,
        layout_style=str(storyboard.get("style", args.layout_style)),
        rendered_slides=rendered_slides,
        scenes=scenes,
        music_file=music_file,
        render_mode=args.render_mode,
    )

    voiceover_scenes = build_voiceover_scenes(scenes)
    write_voiceover_script(audio_dir / "voiceover-script.json", voiceover_scenes)
    write_audio_config(src_dir / "audio-config.ts", voiceover_scenes, with_audio_files=False)

    total_frames = sum(int(scene["minFrames"]) for scene in voiceover_scenes)
    duration_seconds = round(float(total_frames) / FPS, 2)

    print("Workspace ready: %s" % workspace)
    print("PPT deck: %s" % deck_path)
    print("Rendered slides: %s" % len(rendered_slides))
    print("Shots prepared: %s" % len(shots))
    print("Render mode: %s" % args.render_mode)
    if copy_points:
        print("Copy source points: %s" % len(copy_points))
    print("Estimated duration: %ss at %sfps" % (duration_seconds, FPS))
    print("Manifest: %s" % (screenshots_dir / "manifest.json"))
    print("Promo data: %s" % (src_dir / "promo-data.ts"))
    print("Voiceover script: %s" % (audio_dir / "voiceover-script.json"))
    if music_file:
        print("Background music: %s" % music_file)
    else:
        print("Background music: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
