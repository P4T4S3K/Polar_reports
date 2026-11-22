"""Load Polar Team Pro exports (CSV or JSON) into one normalized DataFrame.

Every export file is one *session* (a training or a match of one group).
Column names differ between export languages (Czech / English) and versions,
so they are matched with regular expressions instead of exact names.
"""

from __future__ import annotations

import io
import json
import re
import unicodedata
from pathlib import Path
from typing import IO, Union

import pandas as pd

# canonical name -> regex matched against the lower-cased original column name
COLUMN_PATTERNS: dict[str, str] = {
    "number": r"^(číslo hráče|player number|number|#)$",
    "player": r"^(jméno hráče|player name|player|name|athlete)$",
    "session_name": r"^(název tréninku|session name|training name)$",
    "type": r"^(typ|type)$",
    "phase": r"^(název fáze|phase name)$",
    "duration": r"^(délka trvání|duration)",
    "start_time": r"^(čas zahájení|start time)$",
    "end_time": r"^(čas ukončení|end time)$",
    "hr_min": r"^(min\. tf|hr min) \[bpm\]",
    "hr_avg": r"^(prům\. tf|hr avg) \[bpm\]",
    "hr_max": r"^(max\. tf|hr max) \[bpm\]",
    "hr_min_pct": r"^(min\. tf|hr min) \[%\]",
    "hr_avg_pct": r"^(prům\. tf|hr avg) \[%\]",
    "hr_max_pct": r"^(max\. tf|hr max) \[%\]",
    "distance": r"^(celková vzdálenost|total distance) \[m\]",
    "distance_per_min": r"^(vzdálenost|distance) ?/ ?min",
    "speed_max": r"^(maximální rychlost|max(imum)? speed) \[km/h\]",
    "speed_avg": r"^(průměrná rychlost|av(era)?ge? speed) \[km/h\]",
    "sprints": r"^(sprinty|sprints)$",
    "calories": r"^(kalorie|calories)",
    "training_load": r"^(skóre tréninkové zátěže|training load( score)?)$",
    "cardio_load": r"^(kardio zátěž|cardio load)",
    "muscle_load": r"^(svalová zátěž|muscle load)$",
    "recovery_time": r"^(doba regenerace|recovery time)",
    "hrv_rmssd": r"rmssd",
}

HR_ZONE_RE = re.compile(r"^(doba v zóně tf|time in hr zone) (\d)", re.I)
SPEED_ZONE_RE = re.compile(r"^(vzdálenost v zóně rychlosti|distance in speed zone) (\d)", re.I)
ACC_RE = re.compile(
    r"^(počet zrychlení|number of accelerations) \((-?[\d.]+)\s*-\s*(-?[\d.]+)", re.I
)

NUMERIC_COLUMNS = [
    "number", "hr_min", "hr_avg", "hr_max", "hr_min_pct", "hr_avg_pct", "hr_max_pct",
    "distance", "distance_per_min", "speed_max", "speed_avg", "sprints", "calories",
    "training_load", "cardio_load", "muscle_load", "recovery_time", "hrv_rmssd",
]

WHOLE_SESSION_PHASES = {"celý trénink", "whole session", "celé utkání", "whole match"}

# session types used by the team
MATCH = "Zápas"
SKILLS = "Dovednostní trénink"
STANDARD = "Standardní trénink"
SESSION_TYPES = [STANDARD, SKILLS, MATCH]

Source = Union[str, Path, IO[bytes], IO[str], bytes]


def parse_duration(value) -> float | None:
    """Return minutes from 'HH:MM:SS', 'MM:SS', or a number of seconds."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value) / 60.0
    text = str(value).strip()
    if not text:
        return None
    try:
        nums = [float(p) for p in text.split(":")]
    except ValueError:
        return None
    if len(nums) == 3:
        h, m, s = nums
    elif len(nums) == 2:
        h, (m, s) = 0, nums
    else:
        return nums[0] / 60.0
    return h * 60 + m + s / 60.0


def guess_session_type(text: str) -> str:
    """Guess the session type from a file name or session name."""
    t = text.lower()
    if re.search(r"z[aá]pas|match|utk[aá]n|game", t):
        return MATCH
    if re.search(r"dovednost|skill|technik|herni[ -]?cinnost", t):
        return SKILLS
    return STANDARD


def session_label_from_filename(name: str) -> str:
    """'20261017_184858_KTM-GU15_zapas_2_Florbal_named_1.csv' -> 'KTM-GU15 zapas 2 Florbal'."""
    stem = Path(name).stem
    stem = re.sub(r"^[0-9a-f]{8}-", "", stem)              # upload prefixes
    stem = re.sub(r"^\d{8}_\d{6}_", "", stem)               # Polar timestamp prefix
    stem = re.sub(r"_named(_\d+)?$", "", stem)
    return stem.replace("_", " ").strip() or "Session"


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for col in df.columns:
        key = unicodedata.normalize("NFC", str(col)).replace("\xa0", " ").strip().lower()
        if m := HR_ZONE_RE.match(key):
            mapping[col] = f"hr_zone_{m.group(2)}"
            continue
        if m := SPEED_ZONE_RE.match(key):
            mapping[col] = f"speed_zone_{m.group(2)}"
            continue
        if m := ACC_RE.match(key):
            low, high = float(m.group(2)), float(m.group(3))
            kind = "decel" if high <= 0 else "accel"
            mapping[col] = f"{kind}_{abs(low):g}_{abs(high):g}"
            continue
        for canon, pattern in COLUMN_PATTERNS.items():
            if canon not in used and re.search(pattern, key):
                mapping[col] = canon
                used.add(canon)
                break
    return df.rename(columns=mapping)


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", ".", regex=False).str.strip(), errors="coerce"
    )


def normalize(df: pd.DataFrame, filename: str = "") -> pd.DataFrame:
    """Rename columns to canonical names, coerce types and add session metadata."""
    df = _rename_columns(df.copy())
    df.columns = [str(c) for c in df.columns]
    if "player" not in df.columns:
        raise ValueError("Nenalezen sloupec se jménem hráče. Sloupce: " + ", ".join(df.columns))

    df = df[df["player"].notna() & (df["player"].astype(str).str.strip() != "")].copy()
    df["player"] = df["player"].astype(str).str.strip()

    for col in ("start_time", "end_time"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed", dayfirst=True)

    if "duration" in df.columns:
        df["duration_min"] = df["duration"].map(parse_duration)
    for col in [c for c in df.columns if re.fullmatch(r"hr_zone_\d", c)]:
        df[col] = df[col].map(parse_duration)            # minutes

    numeric = NUMERIC_COLUMNS + [
        c for c in df.columns if c.startswith(("speed_zone_", "accel_", "decel_"))
    ]
    for col in numeric:
        if col in df.columns:
            df[col] = _to_number(df[col])

    # keep only the whole-session row when an export contains several phases
    if "phase" in df.columns:
        whole = df["phase"].astype(str).str.strip().str.lower().isin(WHOLE_SESSION_PHASES)
        if whole.any():
            df = df[whole]
    df = df.drop_duplicates(subset=["player"], keep="first")

    # session metadata (one export file == one session)
    name = ""
    if "session_name" in df.columns:
        names = df["session_name"].dropna().astype(str).str.strip()
        name = names[names != ""].iloc[0] if (names != "").any() else ""
    label = name or session_label_from_filename(filename)
    start = df["start_time"].min() if "start_time" in df.columns else pd.NaT
    df["session"] = label
    df["session_start"] = start
    df["session_id"] = f"{start:%Y%m%d_%H%M%S}_{label}" if pd.notna(start) else label
    df["session_type"] = guess_session_type(f"{filename} {label}")
    df["group"] = ""
    df["source_file"] = Path(filename).name if filename else ""
    return df.reset_index(drop=True)


def _read_raw(source: Source, filename: str) -> pd.DataFrame:
    if isinstance(source, (str, Path)):
        raw = Path(source).read_bytes()
    elif isinstance(source, bytes):
        raw = source
    else:
        raw = source.read()
        if isinstance(raw, str):
            raw = raw.encode("utf-8")

    if filename.lower().endswith(".json") or raw.lstrip(b"\xef\xbb\xbf \r\n\t")[:1] in (b"{", b"["):
        data = json.loads(raw.decode("utf-8-sig"))
        if isinstance(data, dict):
            for value in data.values():          # e.g. {"players": [...]}
                if isinstance(value, list):
                    data = value
                    break
            else:
                data = [data]
        return pd.json_normalize(data)

    text = raw.decode("utf-8-sig", errors="replace")
    first = text.splitlines()[0] if text else ""
    sep = ";" if first.count(";") > first.count(",") else ","
    return pd.read_csv(io.StringIO(text), sep=sep, dtype=str)


def load(source: Source, filename: str | None = None) -> pd.DataFrame:
    """Load one CSV/JSON export (one session) into a normalized DataFrame."""
    if filename is None:
        filename = str(source) if isinstance(source, (str, Path)) else getattr(source, "name", "")
    return normalize(_read_raw(source, filename), filename)


def load_many(sources: list[tuple[Source, str]]) -> pd.DataFrame:
    """Load several exports given as (source, filename) pairs."""
    frames = [load(src, name) for src, name in sources]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)
