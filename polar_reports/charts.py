"""Small inline-SVG chart builders.

Charts are plain SVG strings so the same HTML renders in the web app and in
the PDF (WeasyPrint) without JavaScript.
"""

from __future__ import annotations

import math
from html import escape

TEAL = "#2c6e6f"
GREY = "#b9c2c3"
TEXT = "#4a5459"
MUTED = "#8a9396"
HR_COLORS = ["#a7a9ac", "#5bc0de", "#7cb342", "#e0a82e", "#b8325a"]
SPEED_COLORS = ["#1f3b73", "#3b6fb6", "#4aa3d6", "#4cc1b0", "#7fe0b0"]
LOAD_COLOR = "#c8693a"
HR_COLOR = "#4a86c5"


def _fmt(v: float, unit: str) -> str:
    return f"{v:.0f} {unit}".strip()


def paired_bars(labels, mine, team, colors, unit, width=560, row_h=30) -> str:
    """Horizontal bars: player's value (colored) above team average (grey)."""
    left, right = 130, 70
    plot_w = width - left - right
    vmax = max([*mine, *team, 1])
    h = row_h * len(labels) + 8
    out = [f'<svg viewBox="0 0 {width} {h}" width="100%" xmlns="http://www.w3.org/2000/svg" '
           f'font-family="DejaVu Sans, Arial, sans-serif" font-size="10">']
    for i, (lab, a, b, c) in enumerate(zip(labels, mine, team, colors)):
        y = 4 + i * row_h
        wa, wb = plot_w * a / vmax, plot_w * b / vmax
        out.append(f'<text x="{left - 8}" y="{y + 13}" text-anchor="end" fill="{TEXT}">{escape(lab)}</text>')
        out.append(f'<rect x="{left}" y="{y}" width="{wa:.1f}" height="10" rx="1.5" fill="{c}"/>')
        out.append(f'<rect x="{left}" y="{y + 12}" width="{wb:.1f}" height="10" rx="1.5" fill="{GREY}"/>')
        out.append(f'<text x="{left + wa + 4:.1f}" y="{y + 9}" fill="{c}" font-weight="bold">Ty {_fmt(a, unit)}</text>')
        out.append(f'<text x="{left + wb + 4:.1f}" y="{y + 21}" fill="{MUTED}">tým {_fmt(b, unit)}</text>')
    out.append("</svg>")
    return "".join(out)


def radar(labels, values, size=260, color=TEAL) -> str:
    """Radar/spider chart for 0–100 percentile values."""
    cx = cy = size / 2
    r = size / 2 - 40
    n = len(labels)

    def pt(i, v):
        a = -math.pi / 2 + 2 * math.pi * i / n
        return cx + r * v / 100 * math.cos(a), cy + r * v / 100 * math.sin(a)

    pad = 30
    out = [f'<svg viewBox="{-pad} 0 {size + 2 * pad} {size}" width="100%" xmlns="http://www.w3.org/2000/svg" '
           f'font-family="DejaVu Sans, Arial, sans-serif" font-size="10">']
    for ring in (25, 50, 75, 100):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, ring) for i in range(n)))
        out.append(f'<polygon points="{pts}" fill="none" stroke="#d5dbdc" stroke-dasharray="2,2"/>')
    for i, lab in enumerate(labels):
        x, y = pt(i, 100)
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#d5dbdc"/>')
        lx, ly = pt(i, 122)
        anchor = "middle" if abs(lx - cx) < 5 else ("start" if lx > cx else "end")
        out.append(f'<text x="{lx:.1f}" y="{ly + 3:.1f}" text-anchor="{anchor}" fill="{TEXT}">{escape(lab)}</text>')
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, v) for i, v in enumerate(values)))
    out.append(f'<polygon points="{pts}" fill="{color}" fill-opacity="0.35" stroke="{color}" stroke-width="1.5"/>')
    for i, v in enumerate(values):
        x, y = pt(i, v)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{color}"/>')
        out.append(f'<text x="{x:.1f}" y="{y - 5:.1f}" text-anchor="middle" fill="{TEXT}" font-size="9">{v:.0f}</text>')
    out.append("</svg>")
    return "".join(out)


def ranked_bars(names, values, color, title, unit="", avg=None, width=560, highlight=None, columns=2,
                row_h=17) -> str:
    """Ranked horizontal bars split into columns (like the squad report)."""
    pairs = sorted(zip(names, values), key=lambda p: p[1], reverse=True)
    half = max(math.ceil(len(pairs) / columns), 1)
    cols = [pairs[i:i + half] for i in range(0, len(pairs), half)]
    top = 20
    col_w = width / columns
    name_w, val_w = 105, 34
    bar_w = col_w - name_w - val_w - 10
    vmax = max(values) if len(values) else 1
    h = top + row_h * half + 6
    out = [f'<svg viewBox="0 0 {width} {h}" width="100%" xmlns="http://www.w3.org/2000/svg" '
           f'font-family="DejaVu Sans, Arial, sans-serif" font-size="9">',
           f'<text x="{width / 2}" y="11" text-anchor="middle" fill="{TEXT}" font-size="10">{escape(title)}</text>']
    for c, items in enumerate(cols):
        x0 = c * col_w
        for i, (name, v) in enumerate(items):
            y = top + i * row_h
            w = bar_w * v / vmax if vmax else 0
            bold = ' font-weight="bold"' if highlight and name == highlight else ""
            out.append(f'<text x="{x0 + name_w - 5}" y="{y + 9}" text-anchor="end" fill="{TEXT}"{bold}>{escape(name)}</text>')
            out.append(f'<rect x="{x0 + name_w}" y="{y}" width="{w:.1f}" height="{row_h - 4}" fill="{color}"/>')
            out.append(f'<text x="{x0 + name_w + w + 3:.1f}" y="{y + 9}" fill="{MUTED}">{v:.0f}{unit}</text>')
        if avg is not None and vmax:
            ax = x0 + name_w + bar_w * avg / vmax
            out.append(f'<line x1="{ax:.1f}" y1="{top - 3}" x2="{ax:.1f}" y2="{top + len(items) * row_h}" '
                       f'stroke="{TEXT}" stroke-dasharray="3,2"/>')
    out.append("</svg>")
    return "".join(out)


def trend(labels, mine, team, title, unit="", width=560, height=190, color=TEAL) -> str:
    """Bar per session (player) with team-average line."""
    left, bottom, top = 40, 34, 22
    pw, ph = width - left - 10, height - bottom - top
    n = max(len(labels), 1)
    vmax = max([*mine, *team, 1]) * 1.1
    step = pw / n
    bw = min(step * 0.6, 40)
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" xmlns="http://www.w3.org/2000/svg" '
           f'font-family="DejaVu Sans, Arial, sans-serif" font-size="9">',
           f'<text x="{left}" y="12" fill="{TEXT}" font-size="10">{escape(title)}</text>']
    for g in range(5):
        v = vmax * g / 4
        y = top + ph - ph * g / 4
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - 10}" y2="{y:.1f}" stroke="#e6eaeb"/>')
        out.append(f'<text x="{left - 4}" y="{y + 3:.1f}" text-anchor="end" fill="{MUTED}">{v:.0f}</text>')
    line = []
    for i, (lab, a, b) in enumerate(zip(labels, mine, team)):
        cx = left + step * (i + 0.5)
        hgt = ph * a / vmax
        out.append(f'<rect x="{cx - bw / 2:.1f}" y="{top + ph - hgt:.1f}" width="{bw:.1f}" height="{hgt:.1f}" fill="{color}"/>')
        out.append(f'<text x="{cx:.1f}" y="{top + ph - hgt - 3:.1f}" text-anchor="middle" fill="{TEXT}">{a:.0f}</text>')
        out.append(f'<text x="{cx:.1f}" y="{height - 20}" text-anchor="middle" fill="{MUTED}">{escape(lab)}</text>')
        line.append(f"{cx:.1f},{top + ph - ph * b / vmax:.1f}")
    if line:
        out.append(f'<polyline points="{" ".join(line)}" fill="none" stroke="{LOAD_COLOR}" stroke-width="1.5" stroke-dasharray="4,2"/>')
        for p in line:
            x, y = p.split(",")
            out.append(f'<circle cx="{x}" cy="{y}" r="2.5" fill="{LOAD_COLOR}"/>')
    lx = width - 170
    out.append(f'<rect x="{lx}" y="4" width="10" height="8" fill="{color}"/><text x="{lx + 14}" y="11" fill="{TEXT}">Ty</text>')
    out.append(f'<line x1="{lx + 40}" y1="8" x2="{lx + 56}" y2="8" stroke="{LOAD_COLOR}" stroke-dasharray="4,2" stroke-width="1.5"/>'
               f'<text x="{lx + 60}" y="11" fill="{TEXT}">průměr týmu</text>')
    out.append("</svg>")
    return "".join(out)


def heat(v: float) -> str:
    """Color for a 0-100 value: red (low) -> amber -> teal (high)."""
    stops = [(0, (184, 50, 90)), (50, (224, 168, 46)), (100, (44, 110, 111))]
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if v <= b:
            t = (v - a) / (b - a)
            return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ca, cb))
    return TEAL


def radar_multi(labels, series, size=300) -> str:
    """Overlay radar of many players; each polygon colored by its overall percentile.

    series: list of (name, values, overall)
    """
    cx = cy = size / 2
    r = size / 2 - 42
    n = len(labels)

    def pt(i, v):
        a = -math.pi / 2 + 2 * math.pi * i / n
        return cx + r * v / 100 * math.cos(a), cy + r * v / 100 * math.sin(a)

    pad = 30
    out = [f'<svg viewBox="{-pad} 0 {size + 2 * pad} {size}" width="100%" xmlns="http://www.w3.org/2000/svg" '
           f'font-family="DejaVu Sans, Arial, sans-serif" font-size="10">']
    for ring in (25, 50, 75, 100):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, ring) for i in range(n)))
        out.append(f'<polygon points="{pts}" fill="none" stroke="#d5dbdc" stroke-dasharray="2,2"/>')
    for i, lab in enumerate(labels):
        x, y = pt(i, 100)
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#d5dbdc"/>')
        lx, ly = pt(i, 120)
        anchor = "middle" if abs(lx - cx) < 5 else ("start" if lx > cx else "end")
        out.append(f'<text x="{lx:.1f}" y="{ly + 3:.1f}" text-anchor="{anchor}" fill="{TEXT}">{escape(lab)}</text>')
    for _, values, overall in sorted(series, key=lambda s: s[2]):
        c = heat(overall)
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, v) for i, v in enumerate(values)))
        out.append(f'<polygon points="{pts}" fill="{c}" fill-opacity="0.06" stroke="{c}" stroke-width="1.1" stroke-opacity="0.85"/>')
    out.append("</svg>")
    return "".join(out)
