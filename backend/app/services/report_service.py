from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io
import os
from datetime import date, datetime
from typing import List, Dict, Optional

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "fonts")
_fonts_registered = False

def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    candidates = [
        (os.path.join(FONT_DIR, "DejaVuSans.ttf"),
         os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for reg, bold in candidates:
        if os.path.exists(reg):
            try:
                pdfmetrics.registerFont(TTFont("DejaVu", reg))
                if os.path.exists(bold):
                    pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold))
                else:
                    pdfmetrics.registerFont(TTFont("DejaVu-Bold", reg))
                pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold")
                _fonts_registered = True
                return
            except Exception as e:
                print(f"Font registration warning: {e}")
    _fonts_registered = True  # Fallback to Helvetica

def _f(bold=False):
    if _fonts_registered:
        return "DejaVu-Bold" if bold else "DejaVu"
    return "Helvetica-Bold" if bold else "Helvetica"

def generate_pdf_report(
    company_name: str,
    period_label: str,
    kpi: Dict,
    transactions: List[Dict],
    expense_by_category: List[Dict],
    partners_summary: List[Dict],
    ad_stats: Optional[Dict] = None,
) -> bytes:
    _register_fonts()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)

    PRIMARY = colors.HexColor("#534AB7")
    GRAY    = colors.HexColor("#888780")
    LIGHT   = colors.HexColor("#F1EFE8")
    WHITE   = colors.white

    def sty(name, **kw):
        return ParagraphStyle(name, **kw)

    title_sty = sty("t", fontName=_f(True),  fontSize=20, textColor=PRIMARY, spaceAfter=4)
    h2_sty    = sty("h", fontName=_f(True),  fontSize=13, textColor=PRIMARY, spaceBefore=16, spaceAfter=8)
    muted_sty = sty("m", fontName=_f(False), fontSize=9,  textColor=GRAY)
    foot_sty  = sty("f", fontName=_f(False), fontSize=8,  textColor=GRAY, alignment=1)

    def fmt(v):
        if v is None: return "—"
        return "{:,.2f} \u20bd".format(v).replace(",", " ")

    def tbl(data, widths):
        t = Table(data, colWidths=widths)
        t.setStyle(TableStyle([
            ("BACKGROUND",     (0,0),(-1,0),  PRIMARY),
            ("TEXTCOLOR",      (0,0),(-1,0),  WHITE),
            ("FONTNAME",       (0,0),(-1,0),  _f(True)),
            ("FONTNAME",       (0,1),(-1,-1), _f(False)),
            ("FONTSIZE",       (0,0),(-1,-1), 9),
            ("GRID",           (0,0),(-1,-1), 0.5, colors.HexColor("#D3D1C7")),
            ("PADDING",        (0,0),(-1,-1), 6),
            ("ROWBACKGROUNDS", (0,1),(-1,-1), [WHITE, LIGHT]),
            ("VALIGN",         (0,0),(-1,-1), "MIDDLE"),
        ]))
        return t

    story = []
    story.append(Paragraph(company_name, title_sty))
    story.append(Paragraph(f"Финансовый отчёт · {period_label}", muted_sty))
    story.append(Paragraph(f"Сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}", muted_sty))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceAfter=12))

    story.append(Paragraph("Ключевые показатели", h2_sty))
    kpi_rows = [["Показатель", "Значение"],
        ["Выручка",           fmt(kpi.get("income",0))],
        ["Расходы",           fmt(kpi.get("expense",0))],
        ["Чистая прибыль",    fmt(kpi.get("profit",0))],
        ["Среднее в день",    fmt(kpi.get("avg_per_day",0))],
    ]
    if kpi.get("best_day"):
        kpi_rows.append(["Лучший день", f"{kpi['best_day']} — {fmt(kpi.get('best_day_amount',0))}"])
    story.append(tbl(kpi_rows, [10*cm, 7*cm]))

    if expense_by_category:
        story.append(Paragraph("Расходы по категориям", h2_sty))
        total_exp = sum(c.get("amount",0) for c in expense_by_category) or 1
        rows = [["Категория","Сумма","% от расходов"]]
        for c in expense_by_category:
            rows.append([c["name"], fmt(c["amount"]), f"{round(c['amount']/total_exp*100,1)}%"])
        rows.append(["Итого", fmt(total_exp), "100%"])
        story.append(tbl(rows, [9*cm, 5*cm, 3*cm]))

    if partners_summary:
        story.append(Paragraph("Партнёры и дивиденды", h2_sty))
        rows = [["Участник","Роль","Последние ДВД","Остаток долга"]]
        for p in partners_summary:
            rows.append([p.get("name",""), p.get("role_label",""),
                fmt(p.get("last_dividend") or 0) if p.get("last_dividend") else "—",
                fmt(p.get("remaining_debt") or 0)])
        story.append(tbl(rows, [5*cm, 4*cm, 4.5*cm, 3.5*cm]))

    if transactions:
        story.append(Paragraph("Транзакции", h2_sty))
        rows = [["Дата","Тип","Категория","Описание","Сумма"]]
        for t in transactions[:200]:
            rows.append([
                str(t.get("date","")),
                "Доход" if t.get("type")=="income" else "Расход",
                (t.get("category") or {}).get("name","—"),
                (t.get("description") or "")[:40],
                fmt(t.get("amount",0)),
            ])
        story.append(tbl(rows, [2.5*cm, 2*cm, 3*cm, 7*cm, 2.5*cm]))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    story.append(Paragraph(f"Отчёт сформирован автоматически · {company_name}", foot_sty))

    doc.build(story)
    return buf.getvalue()


def generate_excel_report(
    company_name: str,
    date_from: date,
    date_to: date,
    transactions: List[Dict],
    expense_by_category: List[Dict],
    inkas_records: List[Dict],
    ad_campaigns: List[Dict],
) -> bytes:
    wb = Workbook()
    hfill = PatternFill("solid", fgColor="534AB7")
    hfont = Font(color="FFFFFF", bold=True, size=11)
    ifill = PatternFill("solid", fgColor="EAF3DE")
    efill = PatternFill("solid", fgColor="FCEBEB")
    afill = PatternFill("solid", fgColor="F1EFE8")
    tfill = PatternFill("solid", fgColor="D3D1C7")
    tfont = Font(bold=True, size=11)
    thin  = Border(
        left=Side(style="thin", color="D3D1C7"), right=Side(style="thin", color="D3D1C7"),
        top=Side(style="thin", color="D3D1C7"),  bottom=Side(style="thin", color="D3D1C7"),
    )
    ra = Alignment(horizontal="right")
    ca = Alignment(horizontal="center", vertical="center")

    def hdr(ws, headers, widths=None):
        for i, h in enumerate(headers, 1):
            c = ws.cell(row=1, column=i, value=h)
            c.fill, c.font, c.alignment, c.border = hfill, hfont, ca, thin
        if widths:
            for i, w in enumerate(widths, 1):
                ws.column_dimensions[get_column_letter(i)].width = w

    def brd(ws, mr, mc):
        for row in ws.iter_rows(min_row=2, max_row=mr, max_col=mc):
            for cell in row:
                cell.border = thin

    ws1 = wb.active
    ws1.title = "Транзакции"
    ws1.freeze_panes = "A2"
    hdr(ws1, ["Дата","Тип","Категория","Описание","Сумма","Чек"], [14,10,16,40,14,50])
    row = 2
    for t in transactions:
        inc = t.get("type") == "income"
        for col, val in enumerate([
            t.get("date",""), "Доход" if inc else "Расход",
            (t.get("category") or {}).get("name",""),
            t.get("description","") or "", t.get("amount",0), t.get("receipt_url","") or "",
        ], 1):
            cell = ws1.cell(row=row, column=col, value=val)
            cell.fill = ifill if inc else efill
            if col == 5:
                cell.number_format = '#,##0.00'; cell.alignment = ra
        row += 1
    it = sum(t.get("amount",0) for t in transactions if t.get("type")=="income")
    et = sum(t.get("amount",0) for t in transactions if t.get("type")=="expense")
    for r, lbl, val in [(row,"Доход:",it),(row+1,"Расход:",et),(row+2,"Прибыль:",it-et)]:
        ws1.cell(row=r,column=4,value=lbl).font=tfont
        c = ws1.cell(row=r,column=5,value=val); c.font=tfont; c.number_format='#,##0.00'
    brd(ws1, row-1, 6)

    ws2 = wb.create_sheet("Расходы по категориям")
    hdr(ws2, ["Категория","Сумма","% от расходов"], [20,16,16])
    tot = sum(c.get("amount",0) for c in expense_by_category) or 1
    for i, c in enumerate(expense_by_category, 2):
        ws2.cell(row=i,column=1,value=c["name"])
        ws2.cell(row=i,column=2,value=c["amount"]).number_format='#,##0.00'
        ws2.cell(row=i,column=3,value=c["amount"]/tot).number_format="0.0%"
        if i%2==0:
            for col in range(1,4): ws2.cell(row=i,column=col).fill=afill
    r2 = len(expense_by_category)+2
    ws2.cell(row=r2,column=1,value="ИТОГО").fill=tfill; ws2.cell(row=r2,column=1).font=tfont
    ws2.cell(row=r2,column=2,value=tot).fill=tfill
    ws2.cell(row=r2,column=2).font=tfont; ws2.cell(row=r2,column=2).number_format='#,##0.00'
    brd(ws2, r2, 3)

    ws3 = wb.create_sheet("Инкас")
    hdr(ws3, ["Дата","Период","Тип","Партнёр","Сумма"], [14,14,16,16,14])
    tl = {"dividend":"ДВД","return_inv":"ВОЗВРИНВ","investment":"ВЛОЖЕНИЕ"}
    for i, r in enumerate(inkas_records, 2):
        ws3.cell(row=i,column=1,value=str(r.get("date","")))
        ws3.cell(row=i,column=2,value=r.get("month_label",""))
        ws3.cell(row=i,column=3,value=tl.get(r.get("type",""),r.get("type","")))
        ws3.cell(row=i,column=4,value=r.get("partner_name",""))
        ws3.cell(row=i,column=5,value=r.get("amount",0)).number_format='#,##0.00'
        if i%2==0:
            for col in range(1,6): ws3.cell(row=i,column=col).fill=afill
    brd(ws3, len(inkas_records)+1, 5)

    ws4 = wb.create_sheet("Реклама")
    hdr(ws4, ["Дата","Канал","Формат","Сумма","ПДП","₽/ПДП","Ссылка"], [14,30,12,14,10,10,50])
    for i, a in enumerate(ad_campaigns, 2):
        ws4.cell(row=i,column=1,value=str(a.get("date","")))
        ws4.cell(row=i,column=2,value=a.get("channel_name","") or "")
        ws4.cell(row=i,column=3,value=a.get("format","") or "")
        ws4.cell(row=i,column=4,value=a.get("amount",0)).number_format='#,##0.00'
        ws4.cell(row=i,column=5,value=a.get("subscribers_gained") or "")
        cps = a.get("cost_per_sub")
        ws4.cell(row=i,column=6,value=round(cps,2) if cps else "")
        ws4.cell(row=i,column=7,value=a.get("channel_url","") or "")
        if i%2==0:
            for col in range(1,8): ws4.cell(row=i,column=col).fill=afill
    brd(ws4, len(ad_campaigns)+1, 7)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
