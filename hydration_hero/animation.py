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


def load_frame(path: str, target_height: int = 220) -> Optional[Image.Image]:
    try:
        cache_dir = get_cache_dir()
        source_mtime = os.path.getmtime(path)
        cache_key = hashlib.md5(f"{path}:{source_mtime}:{target_height}".encode()).hexdigest()
        cache_path = os.path.join(cache_dir, f"{cache_key}.png")

        if os.path.exists(cache_path):
            return Image.open(cache_path).convert("RGBA")

        image = Image.open(path)
        key = image.convert("RGB").getpixel((0, 0))
        image = chroma_key(image, key)
        scale = target_height / image.height
        new_size = (int(image.width * scale), target_height)
        image = image.resize(new_size, Image.NEAREST)
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

    def load_async(self, on_ready: Optional[Callable[[], None]] = None) -> None:
        def worker() -> None:
            try:
                self.asset_dir = resolve_frame_dir()
                pattern = os.path.join(self.asset_dir, "frame_*.png")
                frame_paths = sorted(
                    glob.glob(pattern),
                    key=lambda path: int(os.path.basename(path).split("_")[1].split(".")[0]),
                )
                if not frame_paths:
                    raise FileNotFoundError(f"No frame_*.png files found in {self.asset_dir}")

                animations = self._build_animations_from_paths(frame_paths)
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

        self.ready = False
        threading.Thread(target=worker, daemon=True).start()

    def reload_async(self, on_ready: Optional[Callable[[], None]] = None) -> None:
        with self._lock:
            self.animations = {}
            self.ready = False
        self.load_async(on_ready=on_ready)

    def _build_animations(self) -> Dict[str, List[Optional[Image.Image]]]:
        return self._build_animations_from_paths(self._frame_paths)

    def _build_animations_from_paths(
        self,
        frame_paths: List[str],
    ) -> Dict[str, List[Optional[Image.Image]]]:
        count = len(self._frame_paths)
        segments = {
            "walk_in": self._frame_paths[0 : int(count * 0.25)],
            "stand": self._frame_paths[int(count * 0.25) : int(count * 0.30)],
            "drink": self._frame_paths[int(count * 0.30) : int(count * 0.80)],
            "walk_out": self._frame_paths[int(count * 0.80) :],
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
        center: Tuple[int, int] = (150, 150),
    ) -> None:
        self.canvas = canvas
        self.animations = animations
        self.center = center
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
    ) -> None:
        frames = self.animations.get(name)
        if not frames:
            if on_complete:
                on_complete()
            return

        self._cancel_pending()
        self._running = True
        generation = self._generation

        def step(index: int) -> None:
            if not self._running or generation != self._generation:
                return

            if index < len(frames):
                frame = frames[index]
                self.canvas.delete("sprite")
                if frame is not None:
                    photo = self._to_photo(frame)
                    self.canvas.create_image(
                        self.center[0],
                        self.center[1],
                        image=photo,
                        tags="sprite",
                    )
                self._after_id = self.canvas.after(delay_ms, lambda idx=index: step(idx + 1))
                return

            if loop:
                self._after_id = self.canvas.after(delay_ms, lambda: step(0))
                return

            if on_complete:
                on_complete()

        step(0)
