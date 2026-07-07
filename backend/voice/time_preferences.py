"""
time_preferences.py — parse natural German time preference from caller text.

Extracts:
  - target_day: Which day does the caller want? (today, tomorrow, next week, specific weekday)
  - time_window: What time of day? (morning, afternoon, after lunch, or specific time)
  - requested_time: Exact time if given (e.g., "10:30")
  - urgency: ASAP, soon, or flexible?
  - flexibility: How flexible is the caller?

Used by scheduler_dialogue.py to ask smarter questions and select better slots.

Examples:
  "heute noch" → target_day=today, urgency=asap
  "morgen vormittags" → target_day=tomorrow, time_window=(08:00, 12:00)
  "Montag um 10:30" → target_day=monday, requested_time="10:30"
  "so früh wie möglich" → urgency=asap, flexibility=0.0 (no alternatives)
  "ich bin flexibel" → flexibility=1.0, urgency=flexible
  "nach der Mittagspause" → time_window=(13:00, 17:00)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TimePreference:
    """Parsed time preference from caller text"""
    target_day: Optional[str]  # "today", "tomorrow", "day_after", weekday name, or "next_week"
    days_offset: Optional[int]  # relative to today: 0=today, 1=tomorrow, etc.
    time_window: Optional[tuple[time, time]]  # (start, end) e.g. (8:00, 12:00) for morning
    requested_time: Optional[time]  # exact time if specified, e.g. 10:30
    urgency: str  # "asap", "soon", or "flexible"
    flexibility: float  # 0.0 (rigid, no alternatives) to 1.0 (very flexible)

    def __repr__(self) -> str:
        parts = []
        if self.target_day:
            parts.append(f"day={self.target_day}")
        if self.time_window:
            parts.append(f"window={self.time_window[0].strftime('%H:%M')}-{self.time_window[1].strftime('%H:%M')}")
        if self.requested_time:
            parts.append(f"time={self.requested_time.strftime('%H:%M')}")
        if self.urgency != "flexible":
            parts.append(f"urgency={self.urgency}")
        if self.flexibility != 0.5:
            parts.append(f"flex={self.flexibility:.1f}")
        return f"TimePreference({', '.join(parts) if parts else 'any'})"


def parse_time_preference(transcript: str, now: datetime) -> TimePreference:
    """
    Parse natural German time preference from caller text.

    Returns TimePreference with extracted information.
    If nothing matches, returns neutral preference (any time, flexible).

    Args:
        transcript: Caller's spoken text (STT output)
        now: Current time (for relative calculations)

    Returns:
        TimePreference with parsed values (all Optional, safe to pass to scheduler)
    """
    text = transcript.lower().strip()

    # Extract components
    target_day = _extract_target_day(text, now)
    days_offset = _day_to_offset(target_day, now.date()) if target_day else None
    time_window = _extract_time_window(text)
    requested_time = _extract_exact_time(text)
    urgency = _extract_urgency(text)
    flexibility = _extract_flexibility(text)

    return TimePreference(
        target_day=target_day,
        days_offset=days_offset,
        time_window=time_window,
        requested_time=requested_time,
        urgency=urgency,
        flexibility=flexibility,
    )


def _extract_target_day(text: str, now: datetime) -> Optional[str]:
    """Extract which day caller wants (today, tomorrow, next week, specific day)"""

    # Explicit "heute" / "today"
    if re.search(r'\bheute\b', text):
        return "today"

    # Explicit "morgen" / "tomorrow"
    if re.search(r'\bmorgen\b', text):
        return "tomorrow"

    # "übermorgen" / day after tomorrow
    if re.search(r'\b(übermorgen|uebermorgen)\b', text):
        return "day_after"

    # "nächste Woche" / "next week"
    if re.search(r'(nächste\s+woche|naechste\s+woche)', text):
        return "next_week"

    # "diese Woche" / "this week" (typically means next available day this week)
    if re.search(r'(diese\s+woche|diese\s+woche)', text):
        today_weekday = now.weekday()
        # If early in week, rest of this week is ok
        # If Friday/weekend, "diese Woche" is a bit vague, treat as next week
        if today_weekday < 4:  # Mon-Thu
            return "this_week"
        else:
            return "next_week"

    # Specific weekday names (Monday=0, Sunday=6)
    weekday_map = {
        "montag": "monday",
        "dienstag": "tuesday",
        "mittwoch": "wednesday",
        "donnerstag": "thursday",
        "freitag": "friday",
        "samstag": "saturday",
        "sonntag": "sunday",
    }

    for de_day, en_day in weekday_map.items():
        if re.search(rf'\b{de_day}\b', text):
            return en_day

    # No explicit day mentioned
    return None


def _day_to_offset(target_day: Optional[str], today_date: date) -> Optional[int]:
    """Convert target_day string to days_offset (0=today, 1=tomorrow, etc.)"""
    if not target_day:
        return None

    today_weekday = today_date.weekday()  # 0=Monday, 6=Sunday

    if target_day == "today":
        return 0
    if target_day == "tomorrow":
        return 1
    if target_day == "day_after":
        return 2

    weekday_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    if target_day in weekday_map:
        target_weekday = weekday_map[target_day]
        # Calculate days until target weekday
        days_ahead = target_weekday - today_weekday
        if days_ahead <= 0:  # Already happened this week, next week
            days_ahead += 7
        return days_ahead

    if target_day == "this_week":
        # Next 1-3 days (depending on today)
        if today_weekday < 4:  # Mon-Thu, can offer within same week
            return None  # Ambiguous, let scheduler decide
        else:
            return None  # Too vague

    if target_day == "next_week":
        # Sometime in next week (Monday onwards)
        return None  # Ambiguous, scheduler will search

    return None


def _extract_time_window(text: str) -> Optional[tuple[time, time]]:
    """Extract time preference window (morning, afternoon, after lunch, etc.)"""

    # Check afternoon FIRST to avoid "früh" matching inside "nachmittags"
    # Afternoon (nachmittags)
    if re.search(r'\b(nachmittags?|nacht)\b', text):
        return (time(13, 0), time(17, 0))

    # Morning (vor/früh/morgens)
    if re.search(r'\b(morgens?|früh|vormittags?)\b', text):
        return (time(8, 0), time(12, 0))

    # After lunch (nach Mittagspause, nach 12/13 Uhr)
    if re.search(r'(nach.*mittagspause|nach.*mittag|nach\s+12|nach\s+13)', text):
        return (time(13, 0), time(17, 0))

    # "ab 14 Uhr" / "from 2 PM onwards"
    ab_match = re.search(r'\bab\s+(\d{1,2})(?::00)?(?:\s+uhr)?\b', text)
    if ab_match:
        hour = int(ab_match.group(1))
        if 0 <= hour <= 23:
            return (time(hour, 0), time(17, 0))  # assume until end of business day

    # No time window specified
    return None


def _extract_exact_time(text: str) -> Optional[time]:
    """Extract exact time if specified (e.g., '10:30', 'gegen 10 Uhr')"""

    # "um 10:30" or "um 10 Uhr"
    um_match = re.search(r'\bum\s+(\d{1,2}):?(\d{0,2})\b', text)
    if um_match:
        hour = int(um_match.group(1))
        minute = int(um_match.group(2)) if um_match.group(2) else 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute)

    # "gegen 10" / "around 10" (less precise)
    gegen_match = re.search(r'\bgegen\s+(\d{1,2})\b', text)
    if gegen_match:
        hour = int(gegen_match.group(1))
        if 0 <= hour <= 23:
            return time(hour, 0)

    # No exact time specified
    return None


def _extract_urgency(text: str) -> str:
    """Extract urgency level (asap, soon, or flexible)"""

    # ASAP / as soon as possible
    if re.search(r'(so früh|so\s+schnell|schnellst|schnellstens?|schnellstmöglich|asap|sofort|dringend)', text):
        return "asap"

    # Flexible / not urgent
    if re.search(r'\b(flexibel|ganz\s+flexibel|beliebig|egal|jederzeit)\b', text):
        return "flexible"

    # Default: neutral
    return "flexible"


def _extract_flexibility(text: str) -> float:
    """
    Extract how flexible the caller is (0.0=rigid, 1.0=very flexible).

    Rigid: "Ich brauche Montag um 10 Uhr" (exact time, no alternatives)
    Flexible: "Ich bin total flexibel" (any day, any time ok)
    """

    # Explicitly flexible
    if re.search(r'\b(flexibel|ganz\s+flexibel|sehr\s+flexibel|egal)\b', text):
        return 1.0

    # Explicitly rigid (exact time requested)
    if re.search(r'\b(genau|exakt|pünktlich)\b', text):
        return 0.0

    # If exact time specified with no flexibility markers, slightly rigid
    if _extract_exact_time(text):
        return 0.3  # Has preference but might accept alternatives

    # Default: neutral flexibility
    return 0.5


def format_preference_for_display(pref: TimePreference) -> str:
    """
    Format TimePreference for debug logging or display.

    Example: "Tomorrow afternoon, flexible"
    """
    parts = []

    if pref.target_day:
        day_labels = {
            "today": "Heute",
            "tomorrow": "Morgen",
            "day_after": "Übermorgen",
            "monday": "Montag",
            "tuesday": "Dienstag",
            "wednesday": "Mittwoch",
            "thursday": "Donnerstag",
            "friday": "Freitag",
            "saturday": "Samstag",
            "sunday": "Sonntag",
            "this_week": "Diese Woche",
            "next_week": "Nächste Woche",
        }
        parts.append(day_labels.get(pref.target_day, pref.target_day))

    if pref.requested_time:
        parts.append(f"um {pref.requested_time.strftime('%H:%M')}")
    elif pref.time_window:
        parts.append(f"{pref.time_window[0].strftime('%H:%M')}-{pref.time_window[1].strftime('%H:%M')}")

    if pref.urgency == "asap":
        parts.append("(dringend)")
    elif pref.flexibility == 1.0:
        parts.append("(flexibel)")

    return ", ".join(parts) if parts else "beliebiger Zeitpunkt"
