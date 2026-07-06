import os
from typing import Optional

import cv2
from PIL import Image

MAX_FRAMES = 240
MIN_FRAMES = 40


def process_video_to_frames(video_path: str, output_dir: str) -> int:
    os.makedirs(output_dir, exist_ok=True)

    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    if total_frames < MIN_FRAMES:
        capture.release()
        raise RuntimeError(
            f"Video is too short ({total_frames} frames). Use at least 2–3 seconds of footage."
        )

    step = max(1, total_frames // MAX_FRAMES)
    saved = 0
    index = 0
    frame_number = 0

    while True:
        ret, frame = capture.read()
        if not ret:
            break

        if index % step == 0:
            saved += 1
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            filename = f"frame_{saved}.png"
            image.save(os.path.join(output_dir, filename), format="PNG")
            frame_number = saved
            if saved >= MAX_FRAMES:
                break
        index += 1

    capture.release()

    if frame_number < MIN_FRAMES:
        raise RuntimeError(
            f"Not enough usable frames ({frame_number}). Try a longer or smoother video."
        )

    return frame_number
