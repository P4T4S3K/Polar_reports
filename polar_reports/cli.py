"""Command line: build PDF reports for every player from export files.

    python -m polar_reports.cli data/*.csv --out reports/ --team "KTM - GU15"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import analysis as an
from . import ingest, report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build Polar Team Pro player reports")
    parser.add_argument("files", nargs="+", type=Path, help="CSV or JSON export files")
    parser.add_argument("--out", type=Path, default=Path("reports"), help="output directory")
    parser.add_argument("--team", default="", help="team name shown in the reports")
    parser.add_argument("--html", action="store_true", help="write HTML instead of PDF")
    args = parser.parse_args(argv)

    df = ingest.load_many([(p, p.name) for p in args.files])
    (args.out / "hracky").mkdir(parents=True, exist_ok=True)
    (args.out / "skupiny").mkdir(parents=True, exist_ok=True)

    def write(path: Path, html: str) -> None:
        if args.html:
            path.with_suffix(".html").write_text(html, encoding="utf-8")
        else:
            path.with_suffix(".pdf").write_bytes(report.to_pdf(html))

    players = an.players(df)
    for p in players:
        write(args.out / "hracky" / report.safe_filename(p), report.player_full_html(df, p, args.team))
    sessions = an.sessions(df)["session_id"]
    for s in sessions:
        write(args.out / "skupiny" / report.safe_filename(s), report.squad_html(df, s, args.team))
    print(f"Hotovo: {len(players)} reportů hráček, {len(sessions)} reportů skupin → {args.out}/")


if __name__ == "__main__":
    main()
