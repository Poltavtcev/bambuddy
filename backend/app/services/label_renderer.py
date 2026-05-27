"""PDF spool label rendering.

Six fixed templates:

- ``ams_holder_74x33`` — 74×33 mm single label, matches the printable label
  STL bundled with the Makerworld AMS Filament Label Holder (model 752566).
  Smaller variant — the visible window in the holder. One label per page.
- ``ams_holder_75x55`` — 75×55 mm single label, fits the cardstock-insert
  variant of the same holder. Roomier — swatch + QR + full text column.
- ``box_40x30``  — 40×30 mm single label, common DK/Brother roll size. Spoolman-
  style layout: brand + material bar + colour name + print temps + QR.
- ``box_40x30_a4`` — A4 sheet, 40×30 mm × 36 per sheet. Same layout as
  ``box_40x30``; Avery L7160 margins (15.15 mm top, 7 mm left, 2.5 mm gap).
- ``box_62x29``  — 62×29 mm single label, sized for Brother PT/QL and Dymo
  generic small labels. One label per page.
- ``avery_5160`` — US Letter sheet, 25.4×66.7 mm × 30 per sheet.
- ``avery_l7160`` — A4 sheet, 38.1×63.5 mm × 21 per sheet.

The legacy ``ams_30x15`` preset (#809) was incorrect — the original 30×15 mm
dimension didn't fit any documented variant of model 752566. Replaced by the
two ``ams_holder_*`` presets above (#1426).

The renderer is decoupled from the Spool model: callers build a ``LabelData``
list from whatever source (local DB, Spoolman, future) so the same code path
works in both modes.

Layout principle (#809): on most templates the **spool ID** dominates; the
40×30 presets instead follow the Spoolman-style layout (brand, material bar,
colour name, print settings, QR) for bag/box labels.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Literal

import qrcode
from reportlab.lib.colors import Color, HexColor, black, white
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

TemplateName = Literal[
    "ams_holder_74x33",
    "ams_holder_75x55",
    "box_40x30",
    "box_40x30_a4",
    "box_62x29",
    "avery_5160",
    "avery_l7160",
]


@dataclass
class LabelData:
    """Per-spool data needed to render a label.

    Decoupled from the SQLAlchemy model so the same renderer serves the local
    inventory and the Spoolman-backed inventory.
    """

    spool_id: int
    name: str
    material: str
    brand: str | None = None
    subtype: str | None = None
    rgba: str | None = None  # "RRGGBB" or "RRGGBBAA"; None → neutral grey
    extra_colors: list[str] | None = None  # additional hex colours (no '#')
    storage_location: str | None = None
    deeplink_url: str = ""  # what the QR encodes; caller composes it
    # Spoolman-style 40×30 fields (optional — blank when unknown).
    color_name: str | None = None
    nozzle_temp_min: int | None = None
    nozzle_temp_max: int | None = None
    bed_temp_min: int | None = None
    bed_temp_max: int | None = None
    flow_ratio: str | None = None
    td: str | None = None


_SPOOLMAN_40x30_TEMPLATES = frozenset({"box_40x30", "box_40x30_a4"})


# ── Colour helpers ───────────────────────────────────────────────────────────


def _color_from_hex(hex_str: str | None, fallback: Color = HexColor(0x808080)) -> Color:
    """Parse an RRGGBB or RRGGBBAA string (no '#') into a ReportLab Color.

    Alpha is honoured so multi-colour spools with translucent overlays render
    correctly. Falls back to ``fallback`` for None / malformed input rather
    than raising — labels should always print.
    """
    if not hex_str:
        return fallback
    h = hex_str.lstrip("#").strip()
    if len(h) not in (6, 8):
        return fallback
    try:
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        a = int(h[6:8], 16) / 255.0 if len(h) == 8 else 1.0
        return Color(r, g, b, alpha=a)
    except ValueError:
        return fallback


def _luminance(color: Color) -> float:
    """Perceived luminance of a ReportLab Color (0–1, WCAG-style approximation)."""
    return 0.299 * color.red + 0.587 * color.green + 0.114 * color.blue


def _hex_code_label(rgba: str | None) -> str:
    """Format ``data.rgba`` as a printable ``#RRGGBB`` string for the label.

    Drops the alpha channel (printed labels can't show transparency) and
    upper-cases the hex digits to match the colour-picker convention used in
    the inventory UI. Returns an empty string for None / malformed input so
    the caller can ``if hex_code:`` skip drawing without an exception.
    """
    if not rgba:
        return ""
    h = rgba.lstrip("#").strip()
    if len(h) not in (6, 8):
        return ""
    rgb = h[:6]
    if not all(c in "0123456789abcdefABCDEF" for c in rgb):
        return ""
    return f"#{rgb.upper()}"


def _format_temp_range(min_t: int | None, max_t: int | None) -> str:
    """Render a nozzle/bed range like ``230-250°C`` for the 40×30 label."""
    if min_t is not None and max_t is not None:
        lo, hi = min(min_t, max_t), max(min_t, max_t)
        if lo == hi:
            return f"{lo}°C"
        return f"{lo}-{hi}°C"
    if min_t is not None:
        return f"{min_t}°C"
    if max_t is not None:
        return f"{max_t}°C"
    return ""


# ── QR generation ────────────────────────────────────────────────────────────


def _qr_png_bytes(payload: str, *, box_size: int = 4, border: int = 2) -> bytes:
    """Render ``payload`` as a tight QR PNG. Empty payload returns empty bytes
    so callers can skip drawing without checking ahead of time.
    """
    if not payload:
        return b""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Single-label drawing ─────────────────────────────────────────────────────


def _draw_swatch(c: rl_canvas.Canvas, x: float, y: float, w: float, h: float, data: LabelData) -> None:
    """Draw the colour swatch. Multi-colour spools use vertical stripes
    (matching the FilamentSwatch convention in the frontend)."""
    primary = _color_from_hex(data.rgba)
    extras = [_color_from_hex(h) for h in (data.extra_colors or []) if h]
    colors = [primary, *extras]

    if not colors:
        c.setFillColor(HexColor(0x808080))
        c.rect(x, y, w, h, stroke=0, fill=1)
        return

    stripe_w = w / len(colors)
    for i, col in enumerate(colors):
        c.setFillColor(col)
        c.rect(x + i * stripe_w, y, stripe_w, h, stroke=0, fill=1)

    # Thin black border so light-colour swatches stay visible on white labels.
    c.setStrokeColor(black)
    c.setLineWidth(0.3)
    c.rect(x, y, w, h, stroke=1, fill=0)


def _draw_qr(c: rl_canvas.Canvas, x: float, y: float, size: float, payload: str) -> None:
    """Embed a square QR at (x, y) with edge length ``size`` (in points)."""
    png = _qr_png_bytes(payload)
    if not png:
        return
    from reportlab.lib.utils import ImageReader

    img = ImageReader(io.BytesIO(png))
    c.drawImage(img, x, y, width=size, height=size, mask="auto")


def _truncate_to_width(c: rl_canvas.Canvas, text: str, font: str, size: float, max_w: float) -> str:
    """Truncate ``text`` with an ellipsis so it fits within ``max_w`` points."""
    if c.stringWidth(text, font, size) <= max_w:
        return text
    ell = "…"
    while text and c.stringWidth(text + ell, font, size) > max_w:
        text = text[:-1]
    return text + ell if text else ell


def _draw_label(
    c: rl_canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    data: LabelData,
    *,
    template: str | None = None,
) -> None:
    """Render one label inside the box (x, y, w, h). Origin is bottom-left."""
    if template in _SPOOLMAN_40x30_TEMPLATES:
        _draw_label_spoolman_40x30(c, x, y, w, h, data)
        return

    pad = 1.2 * mm
    inner_x, inner_y = x + pad, y + pad
    inner_w = w - 2 * pad
    inner_h = h - 2 * pad

    # Outer hairline border so labels are easy to cut out from blank stock.
    c.setStrokeColor(HexColor(0xCCCCCC))
    c.setLineWidth(0.4)
    c.rect(x, y, w, h, stroke=1, fill=0)

    is_tight = h < 20 * mm

    if is_tight:
        _draw_label_tight(c, x, y, w, h, inner_x, inner_y, inner_w, inner_h, pad, data)
    else:
        _draw_label_roomy(c, x, y, w, h, inner_x, inner_y, inner_w, inner_h, pad, data)


def _draw_label_tight(
    c: rl_canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    inner_x: float,
    inner_y: float,
    inner_w: float,
    inner_h: float,
    pad: float,
    data: LabelData,
) -> None:
    """Tight layout (h < 20 mm). Swatch + brand/material/hex/ID, no QR."""
    swatch_w = min(inner_h, inner_w * 0.35)
    swatch_y = inner_y + (inner_h - swatch_w) / 2
    _draw_swatch(c, inner_x, swatch_y, swatch_w, swatch_w, data)

    text_x = inner_x + swatch_w + pad
    text_w = inner_w - swatch_w - pad
    if text_w < 5 * mm:
        return  # Pathological — even the swatch barely fits.

    c.setFillColor(black)

    # Top: brand — bumped to bold + larger per the #809 follow-up so it's the
    # easiest thing to read on a small AMS holder at arm's length.
    brand_size = 6.5
    if data.brand:
        c.setFont("Helvetica-Bold", brand_size)
        brand = _truncate_to_width(c, data.brand, "Helvetica-Bold", brand_size, text_w)
        c.drawString(text_x, y + h - pad - brand_size, brand)

    # Second line: material + subtype, small
    sub_size = 5
    sub_line = " ".join(filter(None, [data.material, data.subtype]))
    sub_y_baseline = y + h - pad - brand_size - 0.6 - sub_size
    if sub_line:
        c.setFont("Helvetica", sub_size)
        sub_line = _truncate_to_width(c, sub_line, "Helvetica", sub_size, text_w)
        c.drawString(text_x, sub_y_baseline, sub_line)

    # Third line (when there's room): hex code, tiny — useful when the user
    # has multiple near-identical colours in the same material family.
    hex_code = _hex_code_label(data.rgba)
    if hex_code:
        hex_size = 4.5
        hex_y = sub_y_baseline - 0.4 - hex_size
        # Don't render if it'd collide with the spool ID at the bottom.
        if hex_y > inner_y + 13:
            c.setFont("Helvetica", hex_size)
            c.drawString(text_x, hex_y, hex_code)

    # Bottom: BIG spool ID — the killer field at-a-glance.
    id_size = 13
    c.setFont("Helvetica-Bold", id_size)
    id_text = _truncate_to_width(c, f"#{data.spool_id}", "Helvetica-Bold", id_size, text_w)
    c.drawString(text_x, inner_y + 0.5, id_text)


def _draw_label_roomy(
    c: rl_canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    inner_x: float,
    inner_y: float,
    inner_w: float,
    inner_h: float,
    pad: float,
    data: LabelData,
) -> None:
    """Box-label / Avery layout. Swatch left, QR right, text middle."""
    # Swatch: full inner height, ~18% of inner width but capped so we never
    # eat the text column on extreme aspect ratios.
    swatch_w = min(inner_w * 0.18, inner_h, 16 * mm)
    swatch_h = inner_h
    _draw_swatch(c, inner_x, inner_y, swatch_w, swatch_h, data)

    # QR: square, capped at the smaller of (a fraction of width, the inner
    # height, or 18 mm — beyond that the QR is overkill for the print size).
    qr_size = min(inner_w * 0.20, inner_h, 18 * mm)
    qr_x = x + w - pad - qr_size
    qr_y = inner_y + (inner_h - qr_size) / 2
    _draw_qr(c, qr_x, qr_y, qr_size, data.deeplink_url)

    text_x = inner_x + swatch_w + 1.5 * mm
    text_w = qr_x - text_x - 1.5 * mm
    if text_w < 8 * mm:
        return

    c.setFillColor(black)

    # Build the text rows we want to render, in top→bottom order.
    line1 = data.brand or ""
    line2 = " · ".join(filter(None, [data.material, data.subtype]))
    name = data.name or ""
    hex_code = _hex_code_label(data.rgba)

    # Layout from the top of the text column.
    cursor_y = y + h - pad

    # Brand — bumped to bold + larger per the #809 follow-up.
    if line1:
        size = 8
        c.setFont("Helvetica-Bold", size)
        text = _truncate_to_width(c, line1, "Helvetica-Bold", size, text_w)
        cursor_y -= size
        c.drawString(text_x, cursor_y, text)
        cursor_y -= 1.2

    if line2:
        size = 7
        c.setFont("Helvetica", size)
        text = _truncate_to_width(c, line2, "Helvetica", size, text_w)
        cursor_y -= size
        c.drawString(text_x, cursor_y, text)
        cursor_y -= 1.5

    # Hex colour code — useful for telling near-identical material+colour
    # spools apart when the swatch is small or the user is colour-blind.
    if hex_code:
        size = 6.5
        c.setFont("Helvetica", size)
        cursor_y -= size
        c.drawString(text_x, cursor_y, hex_code)
        cursor_y -= 1.2

    if name and name != line1:
        size = 9
        c.setFont("Helvetica-Bold", size)
        text = _truncate_to_width(c, name, "Helvetica-Bold", size, text_w)
        cursor_y -= size
        c.drawString(text_x, cursor_y, text)
        cursor_y -= 1.2

    if data.storage_location:
        size = 6.5
        c.setFont("Helvetica-Oblique", size)
        text = _truncate_to_width(c, data.storage_location, "Helvetica-Oblique", size, text_w)
        cursor_y -= size
        c.drawString(text_x, cursor_y, text)

    # Spool ID — anchored at the bottom of the text column, big and bold.
    id_size = 16
    c.setFont("Helvetica-Bold", id_size)
    id_text = _truncate_to_width(c, f"#{data.spool_id}", "Helvetica-Bold", id_size, text_w)
    c.drawString(text_x, inner_y + 0.5, id_text)


def _draw_label_spoolman_40x30(
    c: rl_canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    data: LabelData,
) -> None:
    """Spoolman-style 40×30 mm label: brand, material bar, colour, temps, QR."""
    pad = 1.0 * mm
    inner_x = x + pad
    inner_w = w - 2 * pad

    c.setStrokeColor(HexColor(0xCCCCCC))
    c.setLineWidth(0.4)
    c.rect(x, y, w, h, stroke=1, fill=0)

    cursor_top = y + h - pad

    # Brand (left) + hex code (right) on the top row.
    brand_size = 7.5
    if data.brand:
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", brand_size)
        brand = _truncate_to_width(c, data.brand, "Helvetica-Bold", brand_size, inner_w * 0.62)
        cursor_top -= brand_size
        c.drawString(inner_x, cursor_top, brand)

    hex_code = _hex_code_label(data.rgba)
    if hex_code:
        hex_size = 5.5
        c.setFont("Helvetica", hex_size)
        hex_w = c.stringWidth(hex_code, "Helvetica", hex_size)
        c.drawString(inner_x + inner_w - hex_w, y + h - pad - hex_size, hex_code)

    # Material + subtype on a full-width black bar (white text).
    bar_h = 4.0 * mm
    cursor_top -= 0.8 * mm
    bar_y = cursor_top - bar_h
    c.setFillColor(black)
    c.rect(inner_x, bar_y, inner_w, bar_h, stroke=0, fill=1)
    material_line = " ".join(filter(None, [data.material, data.subtype]))
    if material_line:
        bar_text_size = 7.5
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", bar_text_size)
        bar_text = _truncate_to_width(c, material_line, "Helvetica-Bold", bar_text_size, inner_w - 1.5 * mm)
        bar_text_w = c.stringWidth(bar_text, "Helvetica-Bold", bar_text_size)
        c.drawString(inner_x + (inner_w - bar_text_w) / 2, bar_y + (bar_h - bar_text_size) / 2 - 0.3, bar_text)

    # Colour name below the bar.
    color_name = data.color_name or data.name or ""
    if color_name:
        color_size = 10
        color_y = bar_y - 0.8 * mm - color_size
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", color_size)
        c.drawString(inner_x, color_y, _truncate_to_width(c, color_name, "Helvetica-Bold", color_size, inner_w))

    # Bottom row: print settings (left) + QR (right).
    qr_size = min(11.5 * mm, inner_w * 0.38, (h - 2 * pad) * 0.45)
    qr_x = x + w - pad - qr_size
    qr_y = y + pad
    _draw_qr(c, qr_x, qr_y, qr_size, data.deeplink_url)

    spec_x = inner_x
    spec_w = max(8 * mm, qr_x - spec_x - 0.8 * mm)
    spec_size = 5.2
    line_step = spec_size + 0.9
    spec_y = qr_y + qr_size - spec_size
    c.setFillColor(black)
    c.setFont("Helvetica", spec_size)
    spec_rows = [
        ("Nozzle:", _format_temp_range(data.nozzle_temp_min, data.nozzle_temp_max)),
        ("Bed Temp:", _format_temp_range(data.bed_temp_min, data.bed_temp_max)),
        ("Flow Ratio:", data.flow_ratio or ""),
        ("TD:", data.td or ""),
    ]
    for label, value in spec_rows:
        if value:
            line = f"{label} {value}"
            c.drawString(spec_x, spec_y, _truncate_to_width(c, line, "Helvetica", spec_size, spec_w))
        else:
            c.drawString(spec_x, spec_y, label)
        spec_y -= line_step


# ── Template entry points ────────────────────────────────────────────────────

# (label_w_mm, label_h_mm) for single-label-per-page templates.
_SINGLE_LABEL_SIZES_MM: dict[str, tuple[float, float]] = {
    "ams_holder_74x33": (74.0, 33.0),
    "ams_holder_75x55": (75.0, 55.0),
    "box_40x30": (40.0, 30.0),
    "box_62x29": (62.0, 29.0),
}

# Sheet template parameters: (page_size, label_w_mm, label_h_mm,
#                              cols, rows, top_margin_mm, left_margin_mm,
#                              col_gap_mm, row_gap_mm)
_SHEET_TEMPLATES: dict[str, tuple] = {
    "avery_5160": (letter, 66.675, 25.4, 3, 10, 12.7, 4.76, 3.175, 0.0),
    "avery_l7160": (A4, 63.5, 38.1, 3, 7, 15.15, 7.0, 2.5, 0.0),
    # Same A4 margins/gaps as avery_l7160; 4×9 grid fits 40×30 mm labels.
    "box_40x30_a4": (A4, 40.0, 30.0, 4, 9, 15.15, 7.0, 2.5, 0.0),
}


def _render_single_label_pdf(template: TemplateName, data_list: list[LabelData]) -> bytes:
    w_mm, h_mm = _SINGLE_LABEL_SIZES_MM[template]
    page_w, page_h = w_mm * mm, h_mm * mm

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(page_w, page_h))
    c.setTitle(f"Bambuddy spool labels ({template})")

    for data in data_list:
        _draw_label(c, 0, 0, page_w, page_h, data, template=template)
        c.showPage()

    c.save()
    return buf.getvalue()


def _render_sheet_pdf(template: TemplateName, data_list: list[LabelData]) -> bytes:
    page_size, w_mm, h_mm, cols, rows, top_mm, left_mm, col_gap_mm, row_gap_mm = _SHEET_TEMPLATES[template]
    page_w, page_h = page_size

    label_w = w_mm * mm
    label_h = h_mm * mm
    top_margin = top_mm * mm
    left_margin = left_mm * mm
    col_gap = col_gap_mm * mm
    row_gap = row_gap_mm * mm

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=page_size)
    c.setTitle(f"Bambuddy spool labels ({template})")

    per_page = cols * rows
    for page_start in range(0, len(data_list), per_page):
        chunk = data_list[page_start : page_start + per_page]
        for idx, data in enumerate(chunk):
            row = idx // cols
            col = idx % cols
            x = left_margin + col * (label_w + col_gap)
            y = page_h - top_margin - (row + 1) * label_h - row * row_gap
            _draw_label(c, x, y, label_w, label_h, data, template=template)
        c.showPage()

    c.save()
    return buf.getvalue()


def render_labels(template: TemplateName, data_list: list[LabelData]) -> bytes:
    """Render ``data_list`` to a PDF using the named template. Returns bytes.

    Empty ``data_list`` still produces a valid (empty) PDF — callers should
    short-circuit beforehand if that's not desired.
    """
    if template in _SINGLE_LABEL_SIZES_MM:
        return _render_single_label_pdf(template, data_list)
    if template in _SHEET_TEMPLATES:
        return _render_sheet_pdf(template, data_list)
    raise ValueError(f"Unknown label template: {template!r}")


__all__ = ["LabelData", "TemplateName", "render_labels"]
# white re-exported for completeness; future templates may need a paper-tone variant.
_ = white
