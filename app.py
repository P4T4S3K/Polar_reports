"""Polar Reports – web application.

Run with:  streamlit run app.py
Optional password: set APP_PASSWORD in .streamlit/secrets.toml (or in the
Streamlit Cloud "Secrets" settings) and only people who know it can use the app.
"""

from __future__ import annotations

import hmac
import io
import zipfile

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from polar_reports import analysis as an
from polar_reports import ingest, report

st.set_page_config(page_title="Polar Reports", page_icon="📊", layout="wide")

ALL_TYPES = "Všechny typy"


# ------------------------------------------------------------------ password (optional)
def _password() -> str | None:
    try:
        return st.secrets.get("APP_PASSWORD")
    except Exception:          # no secrets file at all
        return None


def check_password() -> None:
    secret = _password()
    if not secret or st.session_state.get("auth_ok"):
        return
    st.title("📊 Polar Reports")
    pw = st.text_input("Heslo pro trenéry", type="password")
    if pw:
        if hmac.compare_digest(pw, str(secret)):
            st.session_state["auth_ok"] = True
            st.rerun()
        st.error("Nesprávné heslo.")
    st.stop()


check_password()


@st.cache_data(show_spinner="Načítám data…")
def load_uploads(files: tuple[tuple[str, bytes], ...]) -> pd.DataFrame:
    return ingest.load_many([(data, name) for name, data in files])


@st.cache_data(show_spinner="Vytvářím PDF…")
def pdf(html: str) -> bytes:
    return report.to_pdf(html)


def preview(html: str, height: int = 1150) -> None:
    components.html(html, height=height, scrolling=True)


def slug(text: str) -> str:
    return report.safe_filename(text.replace(" ", "_"))


# ------------------------------------------------------------------ sidebar
st.sidebar.title("📊 Polar Reports")
team_name = st.sidebar.text_input("Název týmu", "KTM - GU15")
uploads = st.sidebar.file_uploader(
    "Exporty z Polar Team Pro (CSV nebo JSON)", type=["csv", "json"], accept_multiple_files=True
)
scope_label = st.sidebar.radio(
    "Porovnávat hráčku s",
    ["Všemi hráčkami (obě skupiny)", "Jen s vlastní skupinou"],
    help="Všemi hráčkami = všechny hráčky se stejným typem tréninku ve stejný den (např. 40 hráček ze dvou skupin).",
)
scope = an.SCOPE_ALL if scope_label.startswith("Všemi") else an.SCOPE_GROUP

if not uploads:
    st.title("Reporty hráček z Polar Team Pro")
    st.markdown(
        """
1. V Polar Team Pro exportujte trénink nebo zápas (CSV/JSON). Jeden soubor = jeden trénink jedné skupiny.
2. Nahrajte soubory vlevo – klidně obě skupiny a víc dní najednou.
3. V záložce **Tréninky** zkontrolujte typ tréninku a skupinu.
4. Nahoře vyberte **typ tréninku**, pro který chcete reporty.
5. V záložce **Export** stáhněte PDF pro všechny hráčky a pošlete je hráčkám.

Hráčka se porovnává se všemi hráčkami, které měly **stejný typ tréninku ve stejný den** (obě skupiny = 40 hráček).
        """
    )
    st.stop()

try:
    df = load_uploads(tuple((f.name, f.getvalue()) for f in uploads)).copy()
except Exception as exc:
    st.error(f"Soubory se nepodařilo načíst: {exc}")
    st.stop()

# ------------------------------------------------------------------ training type selector
chosen_type = st.radio("Typ tréninku", [ALL_TYPES, *ingest.SESSION_TYPES], horizontal=True)

tab_sessions, tab_player, tab_squad, tab_export = st.tabs(
    ["Tréninky", "Hráčka", "Trénink / zápas", "Export"]
)

# ------------------------------------------------------------------ sessions: type + group
with tab_sessions:
    st.subheader("Nahrané tréninky a zápasy")
    st.caption("Typ se odhaduje z názvu souboru (např. „zapas“ → Zápas). Upravte typ a skupinu, pokud je potřeba. "
               "Tréninky stejného typu ve stejný den se porovnávají spolu.")
    sess = an.sessions(df)
    editor_df = pd.DataFrame({
        "session_id": sess["session_id"],
        "Datum": sess["session_start"].dt.strftime("%d.%m.%Y %H:%M"),
        "Název": sess["session"],
        "Typ": sess["session_type"],
        "Skupina": sess["group"].replace("", None),
        "Hráček": sess["players"],
        "Soubor": sess["source_file"],
    })
    edited = st.data_editor(
        editor_df,
        hide_index=True,
        use_container_width=True,
        disabled=["Datum", "Hráček", "Soubor"],
        column_config={
            "session_id": None,
            "Typ": st.column_config.SelectboxColumn(options=ingest.SESSION_TYPES, required=True),
            "Skupina": st.column_config.TextColumn(help="např. Skupina A / Skupina B"),
        },
        key="sessions_editor",
    )
    meta = edited.set_index("session_id")
    df["session_type"] = df["session_id"].map(meta["Typ"])
    df["session"] = df["session_id"].map(meta["Název"])
    df["group"] = df["session_id"].map(meta["Skupina"]).fillna("")
    df = an.assign_pools(df)

    pools = df.groupby("pool").agg(skupin=("session_id", "nunique"), hracek=("player", "nunique"))
    st.caption("Porovnávané bloky: " + "; ".join(
        f"{p} – {r.skupin} skup., {r.hracek} hráček" for p, r in pools.iterrows()))

# filters
if chosen_type != ALL_TYPES:
    df = df[df["session_type"] == chosen_type]
if df["session_start"].notna().any() and not df.empty:
    lo, hi = df["session_start"].min().date(), df["session_start"].max().date()
    picked = st.sidebar.date_input("Období", (lo, hi), min_value=lo, max_value=hi)
    if isinstance(picked, tuple) and len(picked) == 2:
        df = df[df["session_start"].dt.date.between(*picked)]
if df.empty:
    st.warning(f"Pro typ „{chosen_type}“ a zvolené období nejsou žádná data.")
    st.stop()

sess = an.sessions(df)
session_options = dict(zip(
    sess["session_id"],
    [f"{s:%d.%m.%Y %H:%M} · {t} · {n}{' · ' + g if g else ''}"
     for s, t, n, g in zip(sess["session_start"], sess["session_type"], sess["session"], sess["group"])],
))
type_suffix = "" if chosen_type == ALL_TYPES else "_" + slug(chosen_type)

# ------------------------------------------------------------------ player
with tab_player:
    player = st.selectbox("Hráčka", an.players(df))
    hist = an.player_history(df, player, scope)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tréninky / zápasy", len(hist))
    c2.metric("Průměrný percentil", f"{hist['overall'].mean():.0f}")
    c3.metric("Nejlepší pořadí", f"{hist['rank'].min()}. z {hist.loc[hist['rank'].idxmin(), 'players']}")
    c4.metric("Max rychlost", f"{hist['speed_max'].max():.1f} km/h" if "speed_max" in hist else "–")

    view = st.radio("Zobrazit", ["Přehled za období", "Konkrétní trénink"], horizontal=True)
    if view == "Přehled za období":
        html = report.render([report.player_overview_page(df, player, team_name, scope)], player)
    else:
        sid = st.selectbox("Trénink / zápas", list(hist["session_id"]),
                           format_func=lambda s: session_options.get(s, s))
        html = report.player_session_html(df, sid, player, team_name, scope)
    preview(html)

    full = report.player_full_html(df, player, team_name, scope)
    st.download_button("⬇️ Stáhnout kompletní report hráčky (PDF)", pdf(full),
                       f"{slug(player)}{type_suffix}.pdf", "application/pdf")

# ------------------------------------------------------------------ squad
with tab_squad:
    sid = st.selectbox("Trénink / zápas", list(sess["session_id"]),
                       format_func=lambda s: session_options[s], key="squad_session")
    squad = report.squad_html(df, sid, team_name, scope)
    preview(squad, height=1200)
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Report skupiny (PDF)", pdf(squad), f"report_skupiny_{slug(sid)}.pdf",
                       "application/pdf")
    c2.download_button("⬇️ Individuální reporty této skupiny (PDF)",
                       pdf(report.session_players_html(df, sid, team_name, scope)),
                       f"individualni_reporty_{slug(sid)}.pdf", "application/pdf")

# ------------------------------------------------------------------ export
with tab_export:
    st.subheader("Hromadný export pro odeslání hráčkám")
    st.write(f"Typ tréninku: **{chosen_type}** · období a filtry podle levého panelu.")
    st.write("ZIP obsahuje složku `hracky/` s jedním PDF pro každou hráčku (přehled za období + stránka za každý "
             "trénink) a složku `skupiny/` s reportem skupiny pro každý trénink.")
    if st.button("Vytvořit ZIP"):
        buf = io.BytesIO()
        all_players = an.players(df)
        total = len(all_players) + len(sess)
        bar = st.progress(0.0)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, p in enumerate(all_players):
                zf.writestr(f"hracky/{slug(p)}{type_suffix}.pdf",
                            report.to_pdf(report.player_full_html(df, p, team_name, scope)))
                bar.progress((i + 1) / total)
            for j, s in enumerate(sess["session_id"]):
                zf.writestr(f"skupiny/{slug(s)}.pdf", report.to_pdf(report.squad_html(df, s, team_name, scope)))
                bar.progress((len(all_players) + j + 1) / total)
        st.download_button("⬇️ Stáhnout ZIP", buf.getvalue(), f"polar_reporty{type_suffix}.zip", "application/zip")
