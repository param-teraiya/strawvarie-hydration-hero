import glob
import hashlib
import os
import threading
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageTk


from hydration_hero.paths import get_cache_dir, get_frame_dir, resolve_frame_dir


def chroma_key(image: Image.Image, key_color: Tuple[int, int, int], tolerance: int = 55) -> Image.Image:
    rgba = np.array(image.convert("RGBA"))
    kr, kg, kb = key_color
    mask = (
        (np.abs(rgba[:, :, 0].astype(np.int16) - kr) <= tolerance)
        & (np.abs(rgba[:, :, 1].astype(np.int16) - kg) <= tolerance)
        & (np.abs(rgba[:, :, 2].astype(np.int16) - kb) <= tolerance)
    )
    rgba[mask, 3] = 0
    return Image.fromarray(rgba)


def crop_to_content(image: Image.Image) -> Image.Image:
    """Trim empty transparent margins so sprites don't smear when overlaid."""
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    bbox = image.getbbox()
    if bbox:
        return image.crop(bbox)
    return image


def load_frame(path: str, target_height: int = 220) -> Optional[Image.Image]:
    try:
        cache_dir = get_cache_dir()
        source_mtime = os.path.getmtime(path)
        cache_key = hashlib.md5(f"{path}:{source_mtime}:{target_height}:crop_v1".encode()).hexdigest()
        cache_path = os.path.join(cache_dir, f"{cache_key}.png")

        if os.path.exists(cache_path):
            return Image.open(cache_path).convert("RGBA")

        image = Image.open(path)
        key = image.convert("RGB").getpixel((0, 0))
        image = chroma_key(image, key)
        scale = target_height / image.height
        new_size = (int(image.width * scale), target_height)
        image = image.resize(new_size, Image.NEAREST)
        image = crop_to_content(image)
        image.save(cache_path, format="PNG")
        return image
    except OSError:
        return None


class AnimationLibrary:
    def __init__(self, asset_dir: Optional[str] = None, target_height: int = 220) -> None:
        self.asset_dir = asset_dir or resolve_frame_dir()
        self.target_height = target_height
        self.animations: Dict[str, List[Optional[Image.Image]]] = {}
        self.ready = False
        self._load_error: Optional[Exception] = None
        self._lock = threading.Lock()

        pattern = os.path.join(self.asset_dir, "frame_*.png")
        self._frame_paths = sorted(
            glob.glob(pattern),
            key=lambda path: int(os.path.basename(path).split("_")[1].split(".")[0]),
        )
        if not self._frame_paths:
            raise FileNotFoundError(f"No frame_*.png files found in {self.asset_dir}")

    def load_async(
        self,
        master,
        on_ready: Optional[Callable[[], None]] = None,
        *,
        batch_size: int = 12,
    ) -> None:
        """Load sprite frames on the Tk main thread (safe with tkinter + pyobjc)."""
        self.ready = False
        self._load_error = None
        self._load_generation = getattr(self, "_load_generation", 0) + 1
        generation = self._load_generation

        try:
            self.asset_dir = resolve_frame_dir()
            pattern = os.path.join(self.asset_dir, "frame_*.png")
            frame_paths = sorted(
                glob.glob(pattern),
                key=lambda path: int(os.path.basename(path).split("_")[1].split(".")[0]),
            )
            if not frame_paths:
                raise FileNotFoundError(f"No frame_*.png files found in {self.asset_dir}")
        except Exception as exc:
            with self._lock:
                self._load_error = exc
                self.ready = False
            if on_ready:
                on_ready()
            return

        loaded: List[Optional[Image.Image]] = []
        state = {"index": 0}

        def load_batch() -> None:
            if generation != self._load_generation:
                return

            batch_end = min(len(frame_paths), state["index"] + batch_size)
            while state["index"] < batch_end:
                path = frame_paths[state["index"]]
                loaded.append(load_frame(path, target_height=self.target_height))
                state["index"] += 1

            if state["index"] < len(frame_paths):
                master.after(1, load_batch)
                return

            try:
                animations = self._build_animations_from_paths(frame_paths, loaded)
                with self._lock:
                    self._frame_paths = frame_paths
                    self.animations = animations
                    self.ready = True
                    self._load_error = None
            except Exception as exc:
                with self._lock:
                    self._load_error = exc
                    self.ready = False
            if on_ready:
                on_ready()

        master.after(0, load_batch)

    def reload_async(
        self,
        master,
        on_ready: Optional[Callable[[], None]] = None,
    ) -> None:
        with self._lock:
            self.animations = {}
            self.ready = False
        self.load_async(master, on_ready=on_ready)

    def _build_animations(self) -> Dict[str, List[Optional[Image.Image]]]:
        return self._build_animations_from_paths(self._frame_paths)

    def _build_animations_from_paths(
        self,
        frame_paths: List[str],
        loaded_frames: Optional[List[Optional[Image.Image]]] = None,
    ) -> Dict[str, List[Optional[Image.Image]]]:
        count = len(frame_paths)
        segments = {
            "walk_in": frame_paths[0 : int(count * 0.25)],
            "stand": frame_paths[int(count * 0.25) : int(count * 0.30)],
            "drink": frame_paths[int(count * 0.30) : int(count * 0.80)],
            "walk_out": frame_paths[int(count * 0.80) :],
        }
        if loaded_frames is not None:
            by_path = dict(zip(frame_paths, loaded_frames))
            return {
                name: [by_path[path] for path in paths]
                for name, paths in segments.items()
            }
        return {
            name: [load_frame(path, target_height=self.target_height) for path in paths]
            for name, paths in segments.items()
        }

    def get(self, name: str) -> List[Optional[Image.Image]]:
        with self._lock:
            return self.animations.get(name, [])


class AnimationPlayer:
    def __init__(
        self,
        canvas,
        animations: AnimationLibrary,
        position: Tuple[int, int] = (150, 150),
        *,
        image_anchor: str = "s",
    ) -> None:
        self.canvas = canvas
        self.animations = animations
        self.position = position
        self.image_anchor = image_anchor
        self._running = False
        self._generation = 0
        self._after_id: Optional[str] = None
        self._photo_refs: List[ImageTk.PhotoImage] = []

    def stop(self) -> None:
        self._running = False
        self._generation += 1
        self._cancel_pending()

    def _cancel_pending(self) -> None:
        if self._after_id is not None:
            try:
                self.canvas.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _to_photo(self, frame: Image.Image) -> ImageTk.PhotoImage:
        photo = ImageTk.PhotoImage(frame, master=self.canvas)
        self._photo_refs.append(photo)
        if len(self._photo_refs) > 4:
            self._photo_refs.pop(0)
        return photo

    def play(
        self,
        name: str,
        delay_ms: int,
        *,
        loop: bool = False,
        on_complete: Optional[Callable[[], None]] = None,
        motion_x: Optional[Tuple[int, int]] = None,
    ) -> None:
        frames = self.animations.get(name)
        if not frames:
            if on_complete:
                on_complete()
            return

        self._cancel_pending()
        self._running = True
        generation = self._generation
        frame_count = len(frames)

        def step(index: int) -> None:
            if not self._running or generation != self._generation:
                return

            if index < frame_count:
                frame = frames[index]
                self.canvas.delete("sprite")
                if frame is not None:
                    photo = self._to_photo(frame)
                    x = self.position[0]
                    if motion_x is not None and frame_count > 1:
                        start_x, end_x = motion_x
                        progress = index / (frame_count - 1)
                        x = int(start_x + (end_x - start_x) * progress)
                    self.canvas.create_image(
                        x,
                        self.position[1],
                        image=photo,
                        anchor=self.image_anchor,
                        tags="sprite",
                    )
                    try:
                        self.canvas.tag_lower("sprite")
                    except Exception:
                        pass
                self._after_id = self.canvas.after(delay_ms, lambda idx=index: step(idx + 1))
                return

            if loop:
                self._after_id = self.canvas.after(delay_ms, lambda: step(0))
                return

            if on_complete:
                on_complete()

        step(0)


class ScenePlayer:
    """Play sprite animations composited onto a static RGB scene (no Tk alpha needed)."""

    def __init__(
        self,
        canvas,
        animations: AnimationLibrary,
        scene: Image.Image,
        foot_y: int,
        foot_x: Optional[int] = None,
    ) -> None:
        self.canvas = canvas
        self.animations = animations
        self.scene = scene.convert("RGB")
        self.foot_y = foot_y
        self.foot_x = foot_x if foot_x is not None else scene.width // 2
        self._running = False
        self._generation = 0
        self._after_id: Optional[str] = None
        self._photo_refs: List[ImageTk.PhotoImage] = []

    def stop(self) -> None:
        self._running = False
        self._generation += 1
        self._cancel_pending()

    def _cancel_pending(self) -> None:
        if self._after_id is not None:
            try:
                self.canvas.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _composite(self, frame: Image.Image, foot_x: int) -> Image.Image:
        canvas = self.scene.copy()
        sprite = frame.convert("RGBA")
        paste_x = foot_x - sprite.width // 2
        paste_y = self.foot_y - sprite.height
        canvas.paste(sprite, (paste_x, paste_y), sprite.split()[3])
        return canvas

    def _to_photo(self, frame: Image.Image, foot_x: int) -> ImageTk.PhotoImage:
        photo = ImageTk.PhotoImage(self._composite(frame, foot_x), master=self.canvas)
        self._photo_refs.append(photo)
        if len(self._photo_refs) > 4:
            self._photo_refs.pop(0)
        return photo

    def play(
        self,
        name: str,
        delay_ms: int,
        *,
        loop: bool = False,
        on_complete: Optional[Callable[[], None]] = None,
        motion_x: Optional[Tuple[int, int]] = None,
    ) -> None:
        frames = self.animations.get(name)
        if not frames:
            if on_complete:
                on_complete()
            return

        self._cancel_pending()
        self._running = True
        generation = self._generation
        frame_count = len(frames)

        def step(index: int) -> None:
            if not self._running or generation != self._generation:
                return

            if index < frame_count:
                frame = frames[index]
                self.canvas.delete("scene")
                if frame is not None:
                    foot_x = self.foot_x
                    if motion_x is not None and frame_count > 1:
                        start_x, end_x = motion_x
                        progress = index / (frame_count - 1)
                        foot_x = int(start_x + (end_x - start_x) * progress)
                    photo = self._to_photo(frame, foot_x)
                    self.canvas.create_image(0, 0, image=photo, anchor="nw", tags="scene")
                self._after_id = self.canvas.after(delay_ms, lambda idx=index: step(idx + 1))
                return

            if loop:
                self._after_id = self.canvas.after(delay_ms, lambda: step(0))
                return

            if on_complete:
                on_complete()

        step(0)
