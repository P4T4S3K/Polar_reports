"""Metrics, percentiles and rankings computed from normalized session data.

Percentile method (matches the example reports): within one session every
player gets `rank(method="max") / n * 100` for each metric, so the best value
is 100 and with 20 players the steps are 5, 10, ... 100. The overall
percentile is the mean of the five metric percentiles and defines the ranking.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# metric -> (short label used in tables, long label used in text)
PERCENTILE_METRICS: dict[str, tuple[str, str]] = {
    "training_load": ("Zátěž", "zátěž"),
    "hr_avg_pct": ("TF%", "TF%"),
    "cardio_load": ("Kardio", "kardio zátěž"),
    "distance_per_min": ("D/min", "vzdálenost/min"),
    "sprints": ("Sprinty", "sprinty"),
}

HR_ZONE_LABELS = [
    "Zóna 1 (50–59%)", "Zóna 2 (60–69%)", "Zóna 3 (70–79%)", "Zóna 4 (80–89%)", "Zóna 5 (90–100%)",
]
SPEED_ZONE_LABELS = [
    "Zóna 1 (3–7 km/h)", "Zóna 2 (7–11 km/h)", "Zóna 3 (11–15 km/h)",
    "Zóna 4 (15–19 km/h)", "Zóna 5 (19+ km/h)",
]


# comparison scope: all players of the same session type on the same day (both groups),
# or only the players of the session itself (one group)
SCOPE_ALL = "all"
SCOPE_GROUP = "group"


def assign_pools(df: pd.DataFrame) -> pd.DataFrame:
    """Add a `pool` column: sessions of the same type on the same day are compared together."""
    df = df.copy()
    day = df["session_start"].dt.strftime("%d.%m.%Y").fillna("")
    df["pool"] = day + " · " + df["session_type"].astype(str)
    return df


def short_name(full: str) -> str:
    """'Dora Vavrochová' -> 'Dora V.'"""
    parts = full.split()
    return f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else full


def sessions(df: pd.DataFrame) -> pd.DataFrame:
    """One row per session, chronologically."""
    cols = ["session_id", "session", "session_start", "session_type", "group", "source_file"]
    out = df.groupby("session_id", sort=False)[cols[1:]].first()
    out["players"] = df.groupby("session_id", sort=False)["player"].nunique()
    if "duration_min" in df.columns:
        out["duration_min"] = df.groupby("session_id", sort=False)["duration_min"].max()
    return out.sort_values("session_start").reset_index()


def players(df: pd.DataFrame) -> list[str]:
    return sorted(df["player"].dropna().unique().tolist(), key=str.casefold)


def session_rows(df: pd.DataFrame, session_id: str) -> pd.DataFrame:
    rows = df[df["session_id"] == session_id]
    if "number" in rows.columns:
        rows = rows.sort_values("number")
    return rows


def comparison_rows(df: pd.DataFrame, session_id: str, scope: str = SCOPE_ALL) -> pd.DataFrame:
    """Players a session is compared against (one row per player)."""
    own = session_rows(df, session_id)
    if scope == SCOPE_GROUP:
        return own
    if "pool" not in df.columns:
        df = assign_pools(df)
    pool = df.loc[df["session_id"] == session_id, "pool"].iloc[0]
    others = df[(df["pool"] == pool) & (df["session_id"] != session_id)]
    # a player present in two sessions of the pool counts once (her own session wins)
    return pd.concat([own, others]).drop_duplicates(subset="player", keep="first")


def percentiles(session_df: pd.DataFrame) -> pd.DataFrame:
    """Per-player percentiles for one session, plus overall score and rank."""
    metrics = [m for m in PERCENTILE_METRICS if m in session_df.columns]
    pct = pd.DataFrame(index=session_df["player"].values)
    for m in metrics:
        values = session_df[m].fillna(0).values
        pct[m] = (pd.Series(values).rank(method="max", pct=True) * 100).round().astype(int).values
    pct["overall"] = pct[metrics].mean(axis=1).round().astype(int) if metrics else 0
    pct = pct.sort_values("overall", ascending=False, kind="stable")
    pct["rank"] = range(1, len(pct) + 1)
    return pct


@dataclass
class SessionStats:
    rows: pd.DataFrame          # players of this session (one group)
    comp: pd.DataFrame          # players compared against (all 40 or the group)
    pct: pd.DataFrame           # percentiles over `comp`, indexed by player
    team_avg: pd.Series         # mean of numeric metrics over `comp`
    group_avg: pd.Series        # mean of numeric metrics over `rows`


def session_stats(df: pd.DataFrame, session_id: str, scope: str = SCOPE_ALL) -> SessionStats:
    rows = session_rows(df, session_id)
    comp = comparison_rows(df, session_id, scope)
    return SessionStats(rows, comp, percentiles(comp), comp.mean(numeric_only=True),
                        rows.mean(numeric_only=True))


def zone_values(row: pd.Series, prefix: str) -> list[float]:
    return [float(row.get(f"{prefix}{i}", 0) or 0) for i in range(1, 6)]


def summary_text(pct_row: pd.Series, n_players: int, context: str = "v tomto zápase") -> str:
    metrics = [m for m in PERCENTILE_METRICS if m in pct_row.index]
    if not metrics:
        return ""
    values = pct_row[metrics].astype(int)
    best, worst = values.idxmax(), values.idxmin()
    return (
        f"Celkový percentil {int(pct_row['overall'])} — {int(pct_row['rank'])}. místo "
        f"z {n_players} hráček {context}. "
        f"Nejsilnější stránka: {PERCENTILE_METRICS[best][1]} ({values[best]}. percentil). "
        f"Prostor ke zlepšení: {PERCENTILE_METRICS[worst][1]} ({values[worst]}. percentil)."
    )


def player_history(df: pd.DataFrame, player: str, scope: str = SCOPE_ALL) -> pd.DataFrame:
    """Every session of one player with her values, team averages and percentiles."""
    out = []
    for sid, own in df.groupby("session_id", sort=False):
        if player not in own["player"].values:
            continue
        srows = comparison_rows(df, sid, scope)
        pct = percentiles(srows)
        me = own[own["player"] == player].iloc[0]
        rec = {
            "session_id": sid,
            "session": me["session"],
            "session_start": me["session_start"],
            "session_type": me["session_type"],
            "players": len(srows),
            "rank": int(pct.at[player, "rank"]),
            "overall": int(pct.at[player, "overall"]),
        }
        for col in ("duration_min", "distance", "distance_per_min", "speed_max", "sprints",
                    "hr_avg_pct", "training_load", "cardio_load"):
            if col in srows.columns:
                rec[col] = me[col]
                rec[f"team_{col}"] = srows[col].mean()
        for m in PERCENTILE_METRICS:
            if m in pct.columns:
                rec[f"pct_{m}"] = int(pct.at[player, m])
        out.append(rec)
    hist = pd.DataFrame(out)
    return hist.sort_values("session_start").reset_index(drop=True) if len(hist) else hist


def type_summary(history: pd.DataFrame) -> pd.DataFrame:
    """Averages of a player's history per session type (she vs team)."""
    if history.empty:
        return history
    cols = [c for c in history.columns if c not in ("session_id", "session", "session_start", "session_type")]
    agg = history.groupby("session_type")[cols].mean(numeric_only=True)
    agg.insert(0, "count", history.groupby("session_type").size())
    return agg
