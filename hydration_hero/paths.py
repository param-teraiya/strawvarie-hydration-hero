import glob
import os
import sys

HERO_FOLDER_NAME = "Strawvarie Hydration Hero"
HERO_VIDEO_NAMES = ("hero.mp4", "hero.mov", "hero.webm", "video.mp4", "Hero.mp4")


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_bundle_dir() -> str:
    if is_frozen():
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_user_hero_root() -> str:
    return os.path.join(os.path.expanduser("~"), HERO_FOLDER_NAME)


def ensure_user_hero_root() -> str:
    root = get_user_hero_root()
    os.makedirs(root, exist_ok=True)
    return root


def get_processed_frames_dir() -> str:
    return os.path.join(get_user_hero_root(), "processed")


def get_hero_manifest_path() -> str:
    return os.path.join(get_processed_frames_dir(), "manifest.json")


def get_default_frame_dir() -> str:
    bundle = get_bundle_dir()
    male_dir = os.path.join(bundle, "heroes", "male")
    if _has_frames(male_dir):
        return male_dir
    if _has_frames(bundle):
        return bundle
    return bundle


def _has_frames(directory: str) -> bool:
    return len(glob.glob(os.path.join(directory, "frame_*.png"))) >= 40


def _is_custom_ready() -> bool:
    processed_dir = get_processed_frames_dir()
    if not _has_frames(processed_dir):
        return False

    manifest_path = get_hero_manifest_path()
    if not os.path.exists(manifest_path):
        return False

    try:
        import json

        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return False

    source_video = manifest.get("source_video")
    source_mtime = manifest.get("source_mtime")
    if not source_video or not os.path.isfile(source_video):
        return False
    if source_mtime != os.path.getmtime(source_video):
        return False
    return True


def resolve_frame_dir() -> str:
    if _is_custom_ready():
        return get_processed_frames_dir()
    return get_default_frame_dir()


def get_frame_dir() -> str:
    return resolve_frame_dir()


def get_logo_path() -> str:
    return os.path.join(get_bundle_dir(), "hydration_hero", "assets", "strawvarie_logo.png")


def get_guide_path() -> str:
    return os.path.join(get_bundle_dir(), "hydration_hero", "assets", "guide.html")


def get_cache_dir() -> str:
    if is_frozen():
        cache_dir = os.path.join(os.path.expanduser("~"), ".hydration_hero", "cache")
    else:
        cache_dir = os.path.join(get_bundle_dir(), ".hydration_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir
