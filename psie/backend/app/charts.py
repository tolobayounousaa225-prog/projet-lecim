"""Graphiques en SVG produits par le serveur : aucun script, lisibles par les lecteurs d'écran (titre + description),
couleurs prises dans la feuille de style (mode sombre compris). Tous les textes sont échappés."""

from markupsafe import Markup, escape

W = 520


def _fmt(v: float) -> str:
    return f"{v:,.1f}".replace(",", " ").rstrip("0").rstrip(".") if isinstance(v, float) and v != int(v) else f"{int(v):,}".replace(",", " ")


def _wrap(title: str, desc: str, height: int, body: str) -> Markup:
    return Markup(f'<figure class="chart"><svg viewBox="0 0 {W} {height}" role="img" aria-label="{escape(title)}" '
                  f'xmlns="http://www.w3.org/2000/svg"><title>{escape(title)}</title><desc>{escape(desc)}</desc>{body}</svg>'
                  f'<figcaption class="muted">{escape(title)}</figcaption></figure>')


def bars(items: list[tuple[str, float]], title: str, unit: str = "") -> Markup:
    """Barres horizontales : une par ligne, valeur écrite au bout."""
    items = [(str(l), float(v or 0)) for l, v in items]
    if not items:
        return Markup("")
    top = max(max(v for _, v in items), 1.0)
    row, label_w, bar_w = 28, 112, W - 112 - 70
    body = []
    for i, (label, v) in enumerate(items):
        y = i * row + 6
        w = max(2.0, bar_w * v / top) if v else 0
        bar = f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="18" rx="3" class="c1"/>' if v else ""
        body.append(f'<text x="{label_w - 8}" y="{y + 15}" text-anchor="end" class="ct">{escape(label[:22])}</text>{bar}'
                    f'<text x="{label_w + w + 6:.1f}" y="{y + 14}" class="ct">{_fmt(v)}{escape(unit)}</text>')
    desc = "; ".join(f"{l} : {_fmt(v)}{unit}" for l, v in items)
    return _wrap(title, desc, len(items) * row + 12, "".join(body))


def stacked(items: list[tuple[str, list[float]]], series: list[str], title: str) -> Markup:
    """Barres horizontales empilées (ex. francophones / arabisants) avec légende."""
    items = [(str(l), [float(x or 0) for x in vals]) for l, vals in items]
    if not items:
        return Markup("")
    top = max(max(sum(v) for _, v in items), 1.0)
    row, label_w, bar_w = 28, 112, W - 112 - 70
    body = []
    for i, (label, vals) in enumerate(items):
        y = i * row + 28
        x = float(label_w)
        body.append(f'<text x="{label_w - 8}" y="{y + 15}" text-anchor="end" class="ct">{escape(label[:22])}</text>')
        for j, v in enumerate(vals):
            w = bar_w * v / top
            if w > 0:
                body.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w, 2):.1f}" height="18" class="c{j + 1}"/>')
            x += w
        body.append(f'<text x="{x + 6:.1f}" y="{y + 14}" class="ct">{_fmt(sum(vals))}</text>')
    legend = "".join(f'<rect x="{label_w + k * 150}" y="4" width="12" height="12" class="c{k + 1}"/>'
                     f'<text x="{label_w + k * 150 + 18}" y="14" class="ct">{escape(s)}</text>' for k, s in enumerate(series))
    desc = "; ".join(f"{l} : " + ", ".join(f"{s} {_fmt(v)}" for s, v in zip(series, vals)) for l, vals in items)
    return _wrap(title, desc, len(items) * row + 40, legend + "".join(body))


def line(points: list[tuple[str, float | None]], title: str, unit: str = "") -> Markup:
    """Courbe simple (évolution par année). Les années sans valeur sont ignorées."""
    pts = [(str(l), float(v)) for l, v in points if v is not None]
    if len(pts) < 2:
        return Markup("")
    left, right, top_pad, height = 50, 24, 20, 220
    lo, hi = min(0.0, min(v for _, v in pts)), max(max(v for _, v in pts), 1.0)
    xs = [left + (W - left - right) * i / (len(pts) - 1) for i in range(len(pts))]
    ys = [top_pad + (height - top_pad - 30) * (1 - (v - lo) / (hi - lo)) for _, v in pts]
    path = " ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y) in enumerate(zip(xs, ys)))
    body = [f'<line x1="{left}" y1="{height - 30}" x2="{W - right}" y2="{height - 30}" class="axis"/>',
            f'<line x1="{left}" y1="{top_pad}" x2="{left}" y2="{height - 30}" class="axis"/>',
            f'<text x="{left - 6}" y="{height - 26}" text-anchor="end" class="ct">{_fmt(lo)}</text>',
            f'<path d="{path}" class="ln"/>']
    for (label, v), x, y in zip(pts, xs, ys):
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" class="c1"/><text x="{x:.1f}" y="{y - 9:.1f}" text-anchor="middle" class="ct">{_fmt(v)}</text>'
                    f'<text x="{x:.1f}" y="{height - 10}" text-anchor="middle" class="ct">{escape(label)}</text>')
    desc = "; ".join(f"{l} : {_fmt(v)}{unit}" for l, v in pts)
    return _wrap(title, desc, height, "".join(body))


# --- Variantes pour les gabarits (Jinja ne sait pas construire de liste par compréhension) -------------

def _get(row, key):
    return row[key] if isinstance(row, dict) else getattr(row, key)


def bars_from(rows, label_key: str, value_key: str, title: str, unit: str = "", skip_none: bool = False) -> Markup:
    return bars([(_get(r, label_key), _get(r, value_key)) for r in rows if not (skip_none and _get(r, value_key) is None)], title, unit)


def stacked_from(rows, label_key: str, value_keys: list[str], series: list[str], title: str) -> Markup:
    return stacked([(_get(r, label_key), [_get(r, k) for k in value_keys]) for r in rows], series, title)


def line_from(rows, label_key: str, value_key: str, title: str, unit: str = "") -> Markup:
    return line([(_get(r, label_key), _get(r, value_key)) for r in rows], title, unit)
