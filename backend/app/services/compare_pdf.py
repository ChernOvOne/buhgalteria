"""
Генерация сравнительного PDF отчёта двух периодов.
Использует ReportLab для вёрстки + matplotlib для графиков.
"""
import io
import os
from datetime import datetime
from typing import Dict, Any, List

# Matplotlib без GUI
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import re as _re

def _strip_emoji(text: str) -> str:
    """Убирает emoji которые DejaVu не поддерживает."""
    emoji_pattern = _re.compile(
        "[😀-🙏"
        "🌀-🗿"
        "🚀-🧿"
        "☀-⛿"
        "✀-➿"
        "🨀-🪟"
        "✅❌➡️▲▼💸🔄💼💚❤️💰📊📢💳👤🏦📅]+",
        flags=_re.UNICODE
    )
    return emoji_pattern.sub('', text).strip()


# ── Шрифты ───────────────────────────────────────────────────────────────────
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "fonts")
_fonts_ok = False

def _reg_fonts():
    global _fonts_ok
    if _fonts_ok:
        return
    for reg, bold in [
        (os.path.join(FONT_DIR, "DejaVuSans.ttf"), os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]:
        if os.path.exists(reg):
            try:
                pdfmetrics.registerFont(TTFont("DV", reg))
                pdfmetrics.registerFont(TTFont("DV-B", bold if os.path.exists(bold) else reg))
                pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B")
                _fonts_ok = True
                return
            except Exception:
                pass
    _fonts_ok = True

def _fn(bold=False): return ("DV-B" if bold else "DV") if _fonts_ok else ("Helvetica-Bold" if bold else "Helvetica")


# ── Цвета ─────────────────────────────────────────────────────────────────────
COL_A     = "#534AB7"
COL_B     = "#F59E0B"
COL_GOOD  = "#1D9E75"
COL_BAD   = "#E24B4A"
COL_GRAY  = "#888780"
COL_LIGHT = "#F1EFE8"
COL_WHITE = "#FFFFFF"

def rl(hex_col):
    return colors.HexColor(hex_col)


# ── Форматирование ────────────────────────────────────────────────────────────
def fmt(v):
    if v is None: return "—"
    return "{:,.0f} ₽".format(v).replace(",", " ")

def pct_str(a, b):
    if a == 0: return "—"
    p = (b - a) / a * 100
    sign = "+" if p > 0 else ""
    return f"{sign}{p:.1f}%"

def delta_color(a, b, inverse=False):
    better = b < a if inverse else b > a
    worse  = b > a if inverse else b < a
    if better: return rl(COL_GOOD)
    if worse:  return rl(COL_BAD)
    return rl(COL_GRAY)


# ── Matplotlib графики → PNG → bytes ─────────────────────────────────────────
plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size': 9,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'figure.facecolor': 'white',
})


def _chart_to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def make_revenue_chart(
    chart_a: List[dict],
    chart_b: List[dict],
    label_a: str,
    label_b: str,
    width_cm: float = 16,
    height_cm: float = 6,
) -> bytes:
    fig, ax = plt.subplots(figsize=(width_cm / 2.54, height_cm / 2.54))

    dates_a = [d["date"] for d in chart_a]
    vals_a  = [d["amount"] for d in chart_a]
    dates_b = [d["date"] for d in chart_b]
    vals_b  = [d["amount"] for d in chart_b]

    ax.fill_between(range(len(dates_a)), vals_a, alpha=0.15, color=COL_A)
    ax.plot(range(len(dates_a)), vals_a, color=COL_A, linewidth=2, label=label_a)

    ax.fill_between(range(len(dates_b)), vals_b, alpha=0.15, color=COL_B)
    ax.plot(range(len(dates_b)), vals_b, color=COL_B, linewidth=2, label=label_b)

    # Подписи X — первое и последнее число
    if dates_a:
        ticks_a = [0, len(dates_a) - 1]
        ax.set_xticks(ticks_a)
        ax.set_xticklabels([dates_a[i][5:] if i < len(dates_a) else '' for i in ticks_a], fontsize=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/1000:.0f}к" if x >= 1000 else str(int(x))))
    ax.legend(fontsize=8)
    ax.set_title("Выручка по дням", fontsize=10, fontweight='bold', pad=8)
    fig.tight_layout()
    return _chart_to_bytes(fig)


def make_category_chart(cat_compare: List[dict], width_cm: float = 16, height_cm: float = 7) -> bytes:
    top = cat_compare[:8]
    if not top:
        return None

    names = [c["name"][:12] for c in top]
    vals_a = [c["a"] for c in top]
    vals_b = [c["b"] for c in top]
    x = np.arange(len(names))
    w = 0.35

    fig, ax = plt.subplots(figsize=(width_cm / 2.54, height_cm / 2.54))
    ax.bar(x - w/2, vals_a, w, label="A", color=COL_A, alpha=0.85, radius=2)
    ax.bar(x + w/2, vals_b, w, label="B", color=COL_B, alpha=0.85, radius=2)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=20, ha='right', fontsize=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/1000:.0f}к" if x >= 1000 else str(int(x))))
    ax.legend(fontsize=8)
    ax.set_title("Расходы по категориям", fontsize=10, fontweight='bold', pad=8)
    fig.tight_layout()
    return _chart_to_bytes(fig)


def make_kpi_bar_chart(
    kpi_a: dict, kpi_b: dict,
    label_a: str, label_b: str,
    width_cm: float = 16, height_cm: float = 5,
) -> bytes:
    metrics = ['Доход', 'Расход', 'Прибыль']
    vals_a  = [kpi_a['income'], kpi_a['expense'], kpi_a['profit']]
    vals_b  = [kpi_b['income'], kpi_b['expense'], kpi_b['profit']]

    x = np.arange(len(metrics))
    w = 0.35

    fig, ax = plt.subplots(figsize=(width_cm / 2.54, height_cm / 2.54))
    bars_a = ax.bar(x - w/2, vals_a, w, label=label_a, color=COL_A, alpha=0.85)
    bars_b = ax.bar(x + w/2, vals_b, w, label=label_b, color=COL_B, alpha=0.85)

    # Подписи на барах
    for bar in list(bars_a) + list(bars_b):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2., h + h * 0.01,
                f"{h/1000:.0f}к" if h >= 1000 else str(int(h)),
                ha='center', va='bottom', fontsize=7)

    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/1000:.0f}к" if x >= 1000 else str(int(x))))
    ax.legend(fontsize=8)
    ax.set_title("KPI сравнение", fontsize=10, fontweight='bold', pad=8)
    fig.tight_layout()
    return _chart_to_bytes(fig)


# ── Основная функция генерации PDF ────────────────────────────────────────────
def generate_compare_pdf(
    company: str,
    a: Dict[str, Any],
    b: Dict[str, Any],
    deltas: Dict[str, Any],
    cat_compare: List[dict],
    label_a: str = "Период A",
    label_b: str = "Период B",
) -> bytes:
    _reg_fonts()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm)

    F  = _fn(False)
    FB = _fn(True)

    # Стили
    def sty(name, **kw):
        return ParagraphStyle(name, **kw)

    title_sty = sty("T", fontName=FB, fontSize=18, textColor=rl(COL_A), spaceAfter=4)
    h2_sty    = sty("H2", fontName=FB, fontSize=12, textColor=rl(COL_A), spaceBefore=14, spaceAfter=6)
    h3_sty    = sty("H3", fontName=FB, fontSize=10, textColor=rl("#2C2C2A"), spaceBefore=8, spaceAfter=4)
    norm_sty  = sty("N", fontName=F, fontSize=9, textColor=rl("#2C2C2A"))
    muted_sty = sty("M", fontName=F, fontSize=8, textColor=rl(COL_GRAY))
    foot_sty  = sty("FT", fontName=F, fontSize=7, textColor=rl(COL_GRAY), alignment=1)

    story = []

    # ── Заголовок
    story.append(Paragraph(f"{company}", title_sty))
    story.append(Paragraph("Сравнительный отчёт периодов", h2_sty))
    story.append(Paragraph(
        f"<b style='color:{COL_A}'>{label_a}:</b> {a['meta']['date_from']} — {a['meta']['date_to']} ({a['meta']['days']} дн.)   "
        f"<b style='color:{COL_B}'>{label_b}:</b> {b['meta']['date_from']} — {b['meta']['date_to']} ({b['meta']['days']} дн.)",
        norm_sty
    ))
    story.append(Paragraph(f"Сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}", muted_sty))
    story.append(HRFlowable(width="100%", thickness=1.5, color=rl(COL_A), spaceAfter=10))

    # ── KPI таблица
    story.append(Paragraph("Ключевые показатели", h2_sty))

    def delta_cell(a_val, b_val, inverse=False):
        if a_val == 0: return "—"
        p = (b_val - a_val) / a_val * 100
        sign = "(+)" if p > 0 else "(-)"
        is_good = (p > 0 and not inverse) or (p < 0 and inverse)
        col = COL_GOOD if is_good else COL_BAD
        return f"<font color='{col}'>{sign} {abs(p):.1f}%</font>"

    kpi_data = [
        ["Показатель", f"A: {a['meta']['date_from'][:7]}", f"B: {b['meta']['date_from'][:7]}", "Изменение"],
        ["Доход",
         fmt(a['kpi']['income']), fmt(b['kpi']['income']),
         Paragraph(delta_cell(a['kpi']['income'], b['kpi']['income']), norm_sty)],
        ["Расход",
         fmt(a['kpi']['expense']), fmt(b['kpi']['expense']),
         Paragraph(delta_cell(a['kpi']['expense'], b['kpi']['expense'], inverse=True), norm_sty)],
        ["Прибыль",
         fmt(a['kpi']['profit']), fmt(b['kpi']['profit']),
         Paragraph(delta_cell(a['kpi']['profit'], b['kpi']['profit']), norm_sty)],
        ["Среднее/день",
         fmt(a['kpi']['avg_per_day']), fmt(b['kpi']['avg_per_day']),
         Paragraph(delta_cell(a['kpi']['avg_per_day'], b['kpi']['avg_per_day']), norm_sty)],
    ]

    kpi_t = Table(kpi_data, colWidths=[5*cm, 4*cm, 4*cm, 4*cm])
    kpi_t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), rl(COL_A)),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), FB),
        ("FONTNAME",    (0, 1), (-1, -1), F),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("GRID",        (0, 0), (-1, -1), 0.5, rl("#D3D1C7")),
        ("PADDING",     (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, rl(COL_LIGHT)]),
        ("ALIGN",       (1, 0), (-1, -1), "RIGHT"),
        # Цвет A
        ("TEXTCOLOR",   (1, 1), (1, -1), rl(COL_A)),
        # Цвет B
        ("TEXTCOLOR",   (2, 1), (2, -1), rl(COL_B)),
    ]))
    story.append(kpi_t)
    story.append(Paragraph("Визуальное сравнение KPI", h2_sty))
    kpi_png = make_kpi_bar_chart(a['kpi'], b['kpi'], label_a, label_b)
    story.append(RLImage(io.BytesIO(kpi_png), width=16*cm, height=5*cm))

    # ── График выручки по дням
    if a['chart'] or b['chart']:
        story.append(Paragraph("Динамика выручки", h2_sty))
        rev_png = make_revenue_chart(a['chart'], b['chart'], label_a, label_b)
        story.append(RLImage(io.BytesIO(rev_png), width=16*cm, height=6*cm))
    # ── Расходы по категориям
    if cat_compare:
        story.append(Paragraph("Расходы по категориям", h2_sty))
        cat_png = make_category_chart(cat_compare)
        if cat_png:
            story.append(RLImage(io.BytesIO(cat_png), width=16*cm, height=7*cm))

        cat_data = [["Категория", f"A", f"B", "Δ%"]]
        for c in cat_compare[:10]:
            p_str = pct_str(c['a'], c['b'])
            cat_data.append([c['name'], fmt(c['a']), fmt(c['b']), p_str])

        cat_t = Table(cat_data, colWidths=[7*cm, 3*cm, 3*cm, 4*cm])
        cat_t.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), rl(COL_A)),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), FB),
            ("FONTNAME",    (0, 1), (-1, -1), F),
            ("FONTSIZE",    (0, 0), (-1, -1), 9),
            ("GRID",        (0, 0), (-1, -1), 0.5, rl("#D3D1C7")),
            ("PADDING",     (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, rl(COL_LIGHT)]),
            ("ALIGN",       (1, 0), (-1, -1), "RIGHT"),
            ("TEXTCOLOR",   (1, 1), (1, -1), rl(COL_A)),
            ("TEXTCOLOR",   (2, 1), (2, -1), rl(COL_B)),
        ]))
        story.append(cat_t)
    story.append(Paragraph("Платежи VPN", h2_sty))
    pay_data = [
        ["Показатель", "A", "B", "Δ%"],
        ["Выручка",    fmt(a['payments']['amount']), fmt(b['payments']['amount']),
         pct_str(a['payments']['amount'], b['payments']['amount'])],
        ["Кол-во",     str(a['payments']['count']), str(b['payments']['count']),
         pct_str(a['payments']['count'], b['payments']['count'])],
    ]
    # По тарифам
    all_tags = list({t['plan'] or t['tag'] for t in (a['payments']['by_tag'] + b['payments']['by_tag'])})
    a_tag_map = {t['plan'] or t['tag']: t for t in a['payments']['by_tag']}
    b_tag_map = {t['plan'] or t['tag']: t for t in b['payments']['by_tag']}
    for tag in all_tags:
        a_c = a_tag_map.get(tag, {}).get('count', 0)
        b_c = b_tag_map.get(tag, {}).get('count', 0)
        pay_data.append([f"  {tag}", str(a_c), str(b_c), pct_str(a_c, b_c)])

    pay_t = Table(pay_data, colWidths=[7*cm, 3*cm, 3*cm, 4*cm])
    pay_t.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,0), rl(COL_A)),
        ("TEXTCOLOR",  (0,0),(-1,0), colors.white),
        ("FONTNAME",   (0,0),(-1,0), FB),
        ("FONTNAME",   (0,1),(-1,-1), F),
        ("FONTSIZE",   (0,0),(-1,-1), 9),
        ("GRID",       (0,0),(-1,-1), 0.5, rl("#D3D1C7")),
        ("PADDING",    (0,0),(-1,-1), 6),
        ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, rl(COL_LIGHT)]),
        ("ALIGN",      (1,0),(-1,-1), "RIGHT"),
        ("TEXTCOLOR",  (1,1),(1,-1), rl(COL_A)),
        ("TEXTCOLOR",  (2,1),(2,-1), rl(COL_B)),
    ]))
    story.append(pay_t)

    story.append(Paragraph("Инкас и Реклама", h2_sty))
    other_data = [
        ["Показатель",         "A",                             "B",                             "Δ%"],
        ["Дивиденды",       fmt(a['inkas']['total_dvd']),    fmt(b['inkas']['total_dvd']),
         pct_str(a['inkas']['total_dvd'], b['inkas']['total_dvd'])],
        ["Возврат инвест.", fmt(a['inkas']['total_ret']),    fmt(b['inkas']['total_ret']),
         pct_str(a['inkas']['total_ret'], b['inkas']['total_ret'])],
        ["Реклама (потрачено)",   fmt(a['ads']['spend']),          fmt(b['ads']['spend']),
         pct_str(a['ads']['spend'], b['ads']['spend'])],
        ["Привлечено ПДП", str(a['ads']['subscribers']),   str(b['ads']['subscribers']),
         pct_str(a['ads']['subscribers'], b['ads']['subscribers'])],
        ["Цена 1 ПДП",        fmt(a['ads']['cost_per_sub']) if a['ads']['cost_per_sub'] else "—",
                               fmt(b['ads']['cost_per_sub']) if b['ads']['cost_per_sub'] else "—", "—"],
    ]
    other_t = Table(other_data, colWidths=[7*cm, 3*cm, 3*cm, 4*cm])
    other_t.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,0), rl(COL_A)),
        ("TEXTCOLOR",  (0,0),(-1,0), colors.white),
        ("FONTNAME",   (0,0),(-1,0), FB),
        ("FONTNAME",   (0,1),(-1,-1), F),
        ("FONTSIZE",   (0,0),(-1,-1), 9),
        ("GRID",       (0,0),(-1,-1), 0.5, rl("#D3D1C7")),
        ("PADDING",    (0,0),(-1,-1), 6),
        ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, rl(COL_LIGHT)]),
        ("ALIGN",      (1,0),(-1,-1), "RIGHT"),
        ("TEXTCOLOR",  (1,1),(1,-1), rl(COL_A)),
        ("TEXTCOLOR",  (2,1),(2,-1), rl(COL_B)),
    ]))
    story.append(other_t)
    story.append(Paragraph("Итоговая оценка", h2_sty))
    checks = [
        ("Доход",        a['kpi']['income'],      b['kpi']['income'],      False),
        ("Расход",       a['kpi']['expense'],      b['kpi']['expense'],     True),
        ("Прибыль",      a['kpi']['profit'],       b['kpi']['profit'],      False),
        ("Платежи VPN",  a['payments']['amount'],  b['payments']['amount'], False),
        ("Реклама eff.", a['ads']['cost_per_sub'] or 0,
                         b['ads']['cost_per_sub'] or 0,                     True),
    ]
    summary_rows = [["Показатель", "A", "B", "Результат"]]
    for label, av, bv, inv in checks:
        better = bv < av if inv else bv > av
        worse  = bv > av if inv else bv < av
        res = "[+] B лучше" if better else ("[-] B хуже" if worse else "= Без изменений")
        summary_rows.append([label, fmt(av) if isinstance(av, float) else str(av),
                             fmt(bv) if isinstance(bv, float) else str(bv), res])

    sum_t = Table(summary_rows, colWidths=[5*cm, 3.5*cm, 3.5*cm, 5*cm])
    sum_t.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,0), rl(COL_A)),
        ("TEXTCOLOR",  (0,0),(-1,0), colors.white),
        ("FONTNAME",   (0,0),(-1,0), FB),
        ("FONTNAME",   (0,1),(-1,-1), F),
        ("FONTSIZE",   (0,0),(-1,-1), 9),
        ("GRID",       (0,0),(-1,-1), 0.5, rl("#D3D1C7")),
        ("PADDING",    (0,0),(-1,-1), 7),
        ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, rl(COL_LIGHT)]),
        ("ALIGN",      (1,0),(2,-1), "RIGHT"),
        ("FONTNAME",   (3,1),(-1,-1), FB),
    ]))
    story.append(sum_t)

    # ── Футер
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=0.5, color=rl(COL_GRAY)))
    story.append(Paragraph(
        f"Сравнительный отчёт · {company} · {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        foot_sty
    ))

    doc.build(story)
    return buf.getvalue()
