import json
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Dict, Optional, Union

DATA_DIR = os.path.join(os.path.expanduser("~"), ".hydration_hero")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")


@dataclass
class AppSettings:
    daily_goal_ml: int = 2000
    reminder_interval_mins: float = 45
    snooze_mins: int = 15
    default_drink_ml: int = 250
    last_reset_date: str = ""
    today_ml: int = 0
    history: Dict[str, int] = field(default_factory=dict)
    onboarding_complete: bool = False

    def reset_if_new_day(self) -> None:
        today = date.today().isoformat()
        if self.last_reset_date != today:
            if self.last_reset_date and self.today_ml > 0:
                self.history[self.last_reset_date] = self.today_ml
            self.last_reset_date = today
            self.today_ml = 0

    @property
    def progress(self) -> float:
        if self.daily_goal_ml <= 0:
            return 0.0
        return min(self.today_ml / self.daily_goal_ml, 1.0)

    def add_water(self, amount_ml: int) -> None:
        self.reset_if_new_day()
        self.today_ml = max(0, self.today_ml + amount_ml)


class SettingsStore:
    def __init__(self, on_change: Optional[Callable[[], None]] = None) -> None:
        self._on_change = on_change
        self.settings = self._load()

    def _load(self) -> AppSettings:
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(SETTINGS_PATH):
            settings = AppSettings()
            settings.reset_if_new_day()
            self._save(settings)
            return settings

        with open(SETTINGS_PATH, encoding="utf-8") as handle:
            raw = json.load(handle)
        settings = AppSettings(**raw)
        settings.reset_if_new_day()
        return settings

    def _save(self, settings: AppSettings) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "daily_goal_ml": settings.daily_goal_ml,
                    "reminder_interval_mins": settings.reminder_interval_mins,
                    "snooze_mins": settings.snooze_mins,
                    "default_drink_ml": settings.default_drink_ml,
                    "last_reset_date": settings.last_reset_date,
                    "today_ml": settings.today_ml,
                    "history": settings.history,
                    "onboarding_complete": settings.onboarding_complete,
                },
                handle,
                indent=2,
            )

    def save(self) -> None:
        self._save(self.settings)
        if self._on_change:
            self._on_change()

    def add_water(self, amount_ml: int) -> None:
        self.settings.add_water(amount_ml)
        self.save()

    def update(self, **kwargs: Union[int, float]) -> None:
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save()
