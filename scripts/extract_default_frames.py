#!/usr/bin/env python3
"""Extract default hero sprite frames from heroes/male/default_hero.mp4."""

import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from hydration_hero.video_processor import process_video_to_frames

HERO_DIR = os.path.join(ROOT, "heroes", "male")
VIDEO_PATH = os.path.join(HERO_DIR, "default_hero.mp4")
MIN_FRAMES = 40


def frame_count() -> int:
    return len(glob.glob(os.path.join(HERO_DIR, "frame_*.png")))


def extract(force: bool = False) -> int:
    if not force and frame_count() >= MIN_FRAMES:
        print(f"Default frames already present ({frame_count()}).")
        return frame_count()

    if not os.path.isfile(VIDEO_PATH):
        print(f"ERROR: Missing source video: {VIDEO_PATH}")
        raise SystemExit(1)

    os.makedirs(HERO_DIR, exist_ok=True)
    for path in glob.glob(os.path.join(HERO_DIR, "frame_*.png")):
        os.remove(path)

    count = process_video_to_frames(VIDEO_PATH, HERO_DIR)
    print(f"Extracted {count} frames to {HERO_DIR}")
    return count


def main() -> None:
    force = "--force" in sys.argv
    extract(force=force)


if __name__ == "__main__":
    main()
