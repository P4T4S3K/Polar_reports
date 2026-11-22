from pathlib import Path

import pandas as pd
import pytest

from polar_reports import analysis as an
from polar_reports import ingest, report

FIX = Path(__file__).parent / "fixtures"
FILES = sorted(FIX.glob("*.csv"))


@pytest.fixture(scope="module")
def df():
    return ingest.load_many([(p, p.name) for p in FILES])


def test_parse_duration():
    assert ingest.parse_duration("01:30:00") == 90
    assert ingest.parse_duration("05:30") == 5.5
    assert ingest.parse_duration(120) == 2
    assert ingest.parse_duration("") is None


def test_czech_columns_normalized(df):
    # zone headers in real exports contain a non-breaking space ("v\xa0zóně")
    for col in ["number", "player", "start_time", "duration_min", "hr_avg_pct", "distance",
                "distance_per_min", "speed_max", "sprints", "training_load", "cardio_load",
                "hr_zone_1", "hr_zone_5", "speed_zone_1", "speed_zone_5", "accel_3_50", "decel_50_3",
                "hrv_rmssd"]:
        assert col in df.columns, col
    assert df["hr_zone_1"].between(0, 60).all()        # minutes
    assert df["session_start"].dt.month.eq(10).all()


def test_session_type_guess(df):
    types = an.sessions(df).set_index("source_file")["session_type"]
    assert types[FILES[0].name] == ingest.MATCH
    assert types[FILES[1].name] == ingest.STANDARD
    assert types[FILES[2].name] == ingest.SKILLS
    assert ingest.session_label_from_filename(FILES[0].name) == "TEST zapas 1 Florbal"


def test_english_semicolon_csv():
    data = "Player name;Total distance [m];Maximum speed [km/h];Training load score\nA;5000;28,5;120\n"
    d = ingest.load(data.encode(), "x.csv")
    assert d.loc[0, "speed_max"] == 28.5 and d.loc[0, "training_load"] == 120


def test_json_records():
    data = b'{"players": [{"Player name": "A", "Total distance [m]": 4000}, {"Player name": "B", "Total distance [m]": 5000}]}'
    d = ingest.load(data, "x.json")
    assert list(d["distance"]) == [4000, 5000]


def test_missing_player_column_raises():
    with pytest.raises(ValueError):
        ingest.load(b"foo,bar\n1,2\n", "x.csv")


def test_percentiles_rank_max_method():
    rows = pd.DataFrame({
        "player": list("ABCD"),
        "training_load": [10, 20, 20, 40],
        "hr_avg_pct": [1, 2, 3, 4],
        "cardio_load": [1, 2, 3, 4],
        "distance_per_min": [1, 2, 3, 4],
        "sprints": [0, 0, 0, 1],
    })
    pct = an.percentiles(rows)
    assert pct.loc["D", "training_load"] == 100
    assert pct.loc["B", "training_load"] == pct.loc["C", "training_load"] == 75   # ties share the max rank
    assert pct.loc["A", "sprints"] == 75
    assert pct.loc["D", "rank"] == 1 and pct.loc["D", "overall"] == 100


def test_summary_text(df):
    sid = an.sessions(df)["session_id"][0]
    stats = an.session_stats(df, sid)
    p = stats.pct.index[0]
    text = an.summary_text(stats.pct.loc[p], len(stats.pct))
    assert text.startswith(f"Celkový percentil {stats.pct.loc[p, 'overall']} — 1. místo z 6 hráček")


def test_player_history(df):
    hist = an.player_history(df, "Hráčka Dvě")
    assert len(hist) == 3
    assert set(hist["session_type"]) == {ingest.MATCH, ingest.STANDARD, ingest.SKILLS}
    assert len(an.type_summary(hist)) == 3
    assert len(an.player_history(df, "Hráčka Jedna")) == 2


def test_reports_render(df):
    sid = an.sessions(df)["session_id"][0]
    html = report.player_session_html(df, sid, "Hráčka Tři", "Test tým")
    assert "Hráčka Tři" in html and "Test tým" in html and "Tepová frekvence podle zón" in html
    assert "Report skupiny" in report.squad_html(df, sid)
    full = report.player_full_html(df, "Hráčka Dvě")
    assert full.count('class="page"') == 4                # overview + 3 sessions


def test_pdf(df):
    pytest.importorskip("weasyprint")
    sid = an.sessions(df)["session_id"][0]
    pdf = report.to_pdf(report.player_session_html(df, sid, "Hráčka Tři"))
    assert pdf[:4] == b"%PDF"


def _two_groups(df):
    """Same match day, second group with other players (like 2 x 20 players)."""
    a = df[df["session_type"] == ingest.MATCH].copy()
    b = a.copy()
    b["player"] = b["player"] + " B"
    b["session_id"] = b["session_id"] + "_B"
    b["session_start"] = b["session_start"] + pd.Timedelta(hours=2)
    b["training_load"] = b["training_load"] + 500          # group B much higher load
    return an.assign_pools(pd.concat([a, b], ignore_index=True))


def test_compare_with_all_groups(df):
    both = _two_groups(df)
    sid = an.sessions(both)["session_id"][0]
    all_stats = an.session_stats(both, sid, an.SCOPE_ALL)
    grp_stats = an.session_stats(both, sid, an.SCOPE_GROUP)
    assert len(all_stats.rows) == 6 and len(all_stats.pct) == 12
    assert len(grp_stats.pct) == 6
    # group B has the higher load, so group A players are at most 50th load percentile among all 12
    assert all_stats.pct.loc[all_stats.rows["player"], "training_load"].max() == 50
    assert grp_stats.pct["training_load"].max() == 100
    hist = an.player_history(both, "Hráčka Jedna", an.SCOPE_ALL)
    assert hist.loc[0, "players"] == 12


def test_report_with_all_groups(df):
    both = _two_groups(df)
    sid = an.sessions(both)["session_id"][0]
    html = report.player_session_html(both, sid, "Hráčka Jedna")
    assert "/12" in html and "všech 12 hráček" in html
    squad = report.squad_html(both, sid)
    assert "obě skupiny" in squad
