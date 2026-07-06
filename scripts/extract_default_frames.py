#!/usr/bin/env python3
"""Extract default hero sprite frames from heroes/male/default_hero.mp4."""

import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from hydration_hero.paths import get_default_frame_dir, get_default_hero_video_path
from hydration_hero.video_processor import process_video_to_frames

MIN_FRAMES = 40


def frame_count() -> int:
    frame_dir = get_default_frame_dir()
    count = len(glob.glob(os.path.join(frame_dir, "frame_*.png")))
    if count >= MIN_FRAMES:
        return count
    legacy_dir = os.path.join(os.path.dirname(frame_dir))
    return len(glob.glob(os.path.join(legacy_dir, "frame_*.png")))


def extract(force: bool = False) -> int:
    frame_dir = get_default_frame_dir()
    video_path = get_default_hero_video_path()

    if not force and frame_count() >= MIN_FRAMES:
        print(f"Default frames already present ({frame_count()}).")
        return frame_count()

    if not os.path.isfile(video_path):
        print(f"ERROR: Missing source video: {video_path}")
        raise SystemExit(1)

    os.makedirs(frame_dir, exist_ok=True)
    for directory in (frame_dir, os.path.dirname(frame_dir)):
        for path in glob.glob(os.path.join(directory, "frame_*.png")):
            os.remove(path)

    count = process_video_to_frames(video_path, frame_dir)
    print(f"Extracted {count} frames to {frame_dir}")
    return count


def main() -> None:
    force = "--force" in sys.argv
    extract(force=force)


if __name__ == "__main__":
    main()
