import json
import os
import shutil
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from hydration_hero.paths import (
    HERO_VIDEO_NAMES,
    ensure_user_hero_root,
    get_default_frame_dir,
    get_hero_manifest_path,
    get_processed_frames_dir,
    get_user_hero_root,
    resolve_frame_dir,
)
from hydration_hero.video_processor import process_video_to_frames


class HeroStatus(str, Enum):
    DEFAULT = "default"
    VIDEO_WAITING = "video_waiting"
    NEEDS_PROCESSING = "needs_processing"
    PROCESSING = "processing"
    CUSTOM_READY = "custom_ready"
    ERROR = "error"


@dataclass
class HeroState:
    status: HeroStatus
    message: str
    video_path: Optional[str] = None
    frame_dir: Optional[str] = None


def _write_readme() -> None:
    root = ensure_user_hero_root()
    readme_path = os.path.join(root, "README.txt")
    if os.path.exists(readme_path):
        return
    with open(readme_path, "w", encoding="utf-8") as handle:
        handle.write(
            "Strawvarie Hydration Hero — custom character\n"
            "============================================\n\n"
            "1. Save your video in this folder as: hero.mp4\n"
            "   (also accepts hero.mov or video.mp4)\n\n"
            "2. Open the Hydration Hero app and click \"Create my hero\".\n\n"
            "Video tips:\n"
            "- Plain pink, green, or solid-color background works best\n"
            "- 10–30 seconds: walk in, drink from tumbler, walk away\n"
            "- Face the camera, good lighting\n\n"
            "We process everything for you — no editing needed.\n"
        )


def find_hero_video() -> Optional[str]:
    root = get_user_hero_root()
    for name in HERO_VIDEO_NAMES:
        path = os.path.join(root, name)
        if os.path.isfile(path):
            return path
    return None


def get_hero_state() -> HeroState:
    ensure_user_hero_root()
    _write_readme()
    video_path = find_hero_video()
    frame_dir = resolve_frame_dir()
    default_dir = get_default_frame_dir()
    using_custom = os.path.normpath(frame_dir) != os.path.normpath(default_dir)

    if using_custom:
        return HeroState(
            status=HeroStatus.CUSTOM_READY,
            message="Your custom hero is ready.",
            video_path=video_path,
            frame_dir=frame_dir,
        )

    if video_path:
        return HeroState(
            status=HeroStatus.NEEDS_PROCESSING,
            message="Video found. Click Create my hero — we handle the rest.",
            video_path=video_path,
            frame_dir=default_dir,
        )

    return HeroState(
        status=HeroStatus.DEFAULT,
        message="Follow the setup guide, then drop hero.mp4 in your hero folder.",
        frame_dir=default_dir,
    )


def process_hero_video(
    on_progress: Optional[Callable[[str], None]] = None,
    on_complete: Optional[Callable[[HeroState], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
) -> None:
    def worker() -> None:
        try:
            video_path = find_hero_video()
            if not video_path:
                if on_error:
                    on_error("No hero.mp4 found. Save your video in the Strawvarie Hydration Hero folder.")
                return

            if on_progress:
                on_progress("Extracting frames from your video...")

            processed_dir = get_processed_frames_dir()
            if os.path.isdir(processed_dir):
                shutil.rmtree(processed_dir)
            os.makedirs(processed_dir, exist_ok=True)

            frame_count = process_video_to_frames(video_path, processed_dir)

            if on_progress:
                on_progress("Saving your custom hero...")

            manifest = {
                "source_video": video_path,
                "source_mtime": os.path.getmtime(video_path),
                "frame_count": frame_count,
            }
            with open(get_hero_manifest_path(), "w", encoding="utf-8") as handle:
                json.dump(manifest, handle, indent=2)

            state = get_hero_state()
            if on_complete:
                on_complete(state)
        except Exception as exc:
            if on_error:
                on_error(str(exc))

    import threading

    threading.Thread(target=worker, daemon=True).start()
