"""Build report pages (HTML) and PDFs.

Three report kinds, all in Czech:
  * player_session  – one page per player for one session (like the example PDF)
  * squad_session   – squad overview + percentile comparison for one session
  * player_overview – one player's statistics across all uploaded sessions
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import analysis as an
from . import charts
from .ingest import MATCH

TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))


def _num(v, digits=0, default="–"):
    if v is None or pd.isna(v):
        return default
    return f"{v:.{digits}f}"


_env.filters["num"] = _num


def _context_word(session_type: str) -> tuple[str, str]:
    """('v tomto zápase', 'zápase') or the training variant."""
    return ("v tomto zápase", "zápase") if session_type == MATCH else ("v tomto tréninku", "tréninku")


def _team_note(stats: an.SessionStats, word: str) -> str:
    groups = stats.comp["session_id"].nunique()
    if groups > 1:
        return f"„Tým“ = průměr všech {len(stats.comp)} hráček (všechny skupiny) v {word} tohoto dne."
    return f"„Tým“ = průměr všech hráček v {word}."


def _session_meta(rows: pd.DataFrame, team_name: str) -> dict:
    first = rows.iloc[0]
    start = first["session_start"]
    parts = [p for p in (team_name, first.get("group") or "", f"{start:%d.%m.%Y}" if pd.notna(start) else "") if p]
    return {
        "title_line": " · ".join(parts),
        "session": first["session"],
        "session_type": first["session_type"],
        "time": f"{start:%H:%M}" if pd.notna(start) else "",
        "date": f"{start:%d.%m.%Y}" if pd.notna(start) else "",
        "n": len(rows),
    }


# --------------------------------------------------------------------------- pages
def player_session_page(df: pd.DataFrame, session_id: str, player: str, team_name: str = "",
                        stats: an.SessionStats | None = None, scope: str = an.SCOPE_ALL) -> dict:
    stats = stats or an.session_stats(df, session_id, scope)
    rows, pct, team = stats.rows, stats.pct, stats.team_avg
    me = rows[rows["player"] == player].iloc[0]
    meta = _session_meta(rows, team_name)
    meta["n"] = len(pct)
    ctx, word = _context_word(meta["session_type"])
    p = pct.loc[player]
    radar_metrics = [m for m in an.PERCENTILE_METRICS if m in pct.columns]

    kpis = [
        ("Trvání", f"{_num(me.get('duration_min'))} min", f"tým {_num(team.get('duration_min'))} min"),
        ("Prům. TF", f"{_num(me.get('hr_avg_pct'))}%", f"tým {_num(team.get('hr_avg_pct'))}%"),
        ("Vzdálenost", f"{_num(me.get('distance', float('nan')) / 1000, 2)} km", f"tým {_num(team.get('distance'))} m"),
        ("Zátěž", _num(me.get("training_load")), f"tým {_num(team.get('training_load'))}"),
        ("Max rychlost", f"{_num(me.get('speed_max'), 1)} km/h", f"tým {_num(team.get('speed_max'), 1)} km/h"),
    ]
    return {
        "kind": "player_session",
        "name": player,
        "number": _num(me.get("number")),
        "rank": int(p["rank"]),
        "meta": meta,
        "kpis": kpis,
        "hr_chart": charts.paired_bars(
            an.HR_ZONE_LABELS, an.zone_values(me, "hr_zone_"), an.zone_values(team, "hr_zone_"),
            charts.HR_COLORS, "min"),
        "speed_chart": charts.paired_bars(
            an.SPEED_ZONE_LABELS, an.zone_values(me, "speed_zone_"), an.zone_values(team, "speed_zone_"),
            charts.SPEED_COLORS, "m"),
        "radar": charts.radar([an.PERCENTILE_METRICS[m][0] for m in radar_metrics],
                              [p[m] for m in radar_metrics]),
        "pct_rows": [(an.PERCENTILE_METRICS[m][0], int(p[m])) for m in radar_metrics],
        "summary": an.summary_text(p, meta["n"], ctx),
        "footer": f"Zdroj: export Polar Team Pro, {meta['date']}. {_team_note(stats, word)}",
    }


def squad_pages(df: pd.DataFrame, session_id: str, team_name: str = "",
                scope: str = an.SCOPE_ALL) -> list[dict]:
    stats = an.session_stats(df, session_id, scope)
    rows, pct, team = stats.rows, stats.pct, stats.group_avg
    meta = _session_meta(rows, team_name)
    names = [an.short_name(n) for n in rows["player"]]

    def top(col):
        return an.short_name(rows.loc[rows[col].idxmax(), "player"]) if col in rows and rows[col].notna().any() else "–"

    kpis = [
        ("Trvání", f"{_num(team.get('duration_min'))} min"),
        ("Prům. TF", f"{_num(team.get('hr_avg_pct'))}%"),
        ("Prům. vzdálenost", f"{_num(team.get('distance'))} m"),
        ("Prům. zátěž", _num(team.get("training_load"))),
        ("Nejvíc naběhala", top("distance")),
        ("Nejvyšší zátěž", top("training_load")),
    ]
    table = [
        {
            "number": _num(r.get("number")), "name": r["player"],
            "hr": f"{_num(r.get('hr_avg_pct'))}%", "dist": _num(r.get("distance")),
            "max": _num(r.get("speed_max"), 1), "sprints": _num(r.get("sprints")),
            "load": _num(r.get("training_load")),
        }
        for _, r in rows.iterrows()
    ]
    half = (len(table) + 1) // 2
    metrics = [m for m in an.PERCENTILE_METRICS if m in pct.columns]
    page1 = {
        "kind": "squad",
        "meta": meta,
        "kpis": kpis,
        "dist_chart": charts.ranked_bars(names, rows["distance"].fillna(0).tolist(), charts.TEAL,
                                         "Celková vzdálenost [m] — pořadí", avg=team.get("distance")),
        "load_chart": charts.ranked_bars(names, rows["training_load"].fillna(0).tolist(), charts.LOAD_COLOR,
                                         "Tréninková zátěž — pořadí", avg=team.get("training_load"),
                                         width=280, columns=1, row_h=13),
        "hr_chart": charts.ranked_bars(names, rows["hr_avg_pct"].fillna(0).tolist(), charts.HR_COLOR,
                                       "Průměrná TF [%] — pořadí", unit="%", avg=team.get("hr_avg_pct"),
                                       width=280, columns=1, row_h=13),
        "table_left": table[:half],
        "table_right": table[half:],
        "footer": f"Zdroj: export Polar Team Pro, {meta['date']}. Přerušovaná čára = průměr skupiny.",
    }
    own = set(rows["player"])
    page2 = {
        "kind": "squad_pct",
        "meta": {**meta, "n": len(pct)},
        "all_groups": stats.comp["session_id"].nunique() > 1,
        "radar": charts.radar_multi(
            [an.PERCENTILE_METRICS[m][0] for m in metrics],
            [(name, [r[m] for m in metrics], r["overall"]) for name, r in pct.iterrows()],
        ),
        "metric_labels": [an.PERCENTILE_METRICS[m][0] for m in metrics],
        "rows": [
            {"rank": int(r["rank"]), "name": name, "vals": [int(r[m]) for m in metrics],
             "overall": int(r["overall"]), "color": charts.heat(r["overall"]), "own": name in own}
            for name, r in pct.iterrows()
        ],
        "footer": f"Zdroj: export Polar Team Pro, {meta['date']}.",
    }
    return [page1, page2]


def player_overview_page(df: pd.DataFrame, player: str, team_name: str = "",
                         scope: str = an.SCOPE_ALL) -> dict:
    hist = an.player_history(df, player, scope)
    by_type = an.type_summary(hist)
    labels = [f"{s:%d.%m.}" if pd.notna(s) else str(i + 1) for i, s in enumerate(hist["session_start"])]
    number = df.loc[df["player"] == player, "number"].dropna()
    type_rows = [
        {
            "type": t, "count": int(r["count"]),
            "distance": _num(r.get("distance")), "team_distance": _num(r.get("team_distance")),
            "load": _num(r.get("training_load")), "team_load": _num(r.get("team_training_load")),
            "hr": _num(r.get("hr_avg_pct")), "team_hr": _num(r.get("team_hr_avg_pct")),
            "speed": _num(r.get("speed_max"), 1), "team_speed": _num(r.get("team_speed_max"), 1),
            "overall": _num(r.get("overall")),
        }
        for t, r in by_type.iterrows()
    ]
    sess_rows = [
        {
            "date": f"{r['session_start']:%d.%m.%Y %H:%M}" if pd.notna(r["session_start"]) else "",
            "session": r["session"], "type": r["session_type"],
            "dist": _num(r.get("distance")), "load": _num(r.get("training_load")),
            "hr": _num(r.get("hr_avg_pct")), "max": _num(r.get("speed_max"), 1),
            "sprints": _num(r.get("sprints")), "overall": int(r["overall"]),
            "rank": f"{int(r['rank'])}/{int(r['players'])}", "color": charts.heat(r["overall"]),
        }
        for _, r in hist.iterrows()
    ]
    metrics = [m for m in an.PERCENTILE_METRICS if f"pct_{m}" in hist.columns]
    avg_pct = [hist[f"pct_{m}"].mean() for m in metrics]
    dates = hist["session_start"].dropna()
    period = f"{dates.min():%d.%m.%Y} – {dates.max():%d.%m.%Y}" if len(dates) else ""
    return {
        "kind": "player_overview",
        "name": player,
        "number": _num(number.iloc[0]) if len(number) else "",
        "meta": {"title_line": " · ".join(p for p in (team_name, period) if p)},
        "kpis": [
            ("Tréninky / zápasy", str(len(hist))),
            ("Prům. percentil", _num(hist["overall"].mean())),
            ("Prům. vzdálenost", f"{_num(hist.get('distance', pd.Series(dtype=float)).mean())} m"),
            ("Prům. zátěž", _num(hist.get("training_load", pd.Series(dtype=float)).mean())),
            ("Max rychlost", f"{_num(hist.get('speed_max', pd.Series(dtype=float)).max(), 1)} km/h"),
        ],
        "type_rows": type_rows,
        "load_chart": charts.trend(labels, hist.get("training_load", pd.Series(dtype=float)).fillna(0).tolist(),
                                   hist.get("team_training_load", pd.Series(dtype=float)).fillna(0).tolist(),
                                   "Tréninková zátěž v jednotlivých trénincích"),
        "dist_chart": charts.trend(labels, hist.get("distance", pd.Series(dtype=float)).fillna(0).tolist(),
                                   hist.get("team_distance", pd.Series(dtype=float)).fillna(0).tolist(),
                                   "Celková vzdálenost [m]", color=charts.HR_COLOR),
        "radar": charts.radar([an.PERCENTILE_METRICS[m][0] for m in metrics], avg_pct),
        "sessions": sess_rows,
        "footer": "Percentil = postavení hráčky mezi hráčkami stejného tréninku/zápasu (100 = nejlepší). "
                  "„Tým“ = průměr hráček v daném tréninku.",
    }


# --------------------------------------------------------------------------- documents
def render(pages: list[dict], title: str) -> str:
    return _env.get_template("report.html").render(
        pages=pages, title=title, generated=date.today().strftime("%d.%m.%Y"))


def player_session_html(df, session_id, player, team_name="", scope=an.SCOPE_ALL) -> str:
    return render([player_session_page(df, session_id, player, team_name, scope=scope)], player)


def session_players_html(df, session_id, team_name="", scope=an.SCOPE_ALL) -> str:
    """All individual pages of one session in one document."""
    stats = an.session_stats(df, session_id, scope)
    pages = [player_session_page(df, session_id, p, team_name, stats) for p in stats.rows["player"]]
    return render(pages, "Individuální reporty")


def squad_html(df, session_id, team_name="", scope=an.SCOPE_ALL) -> str:
    return render(squad_pages(df, session_id, team_name, scope), "Report skupiny")


def player_full_html(df, player, team_name="", scope=an.SCOPE_ALL) -> str:
    """Overview across all sessions + one page per session for the player."""
    pages = [player_overview_page(df, player, team_name, scope)]
    for sid in an.player_history(df, player, scope)["session_id"]:
        pages.append(player_session_page(df, sid, player, team_name, scope=scope))
    return render(pages, player)


def to_pdf(html: str) -> bytes:
    from weasyprint import HTML  # imported lazily: heavy and needs system libraries
    return HTML(string=html, base_url=str(TEMPLATES)).write_pdf()


def safe_filename(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name).strip("_")
