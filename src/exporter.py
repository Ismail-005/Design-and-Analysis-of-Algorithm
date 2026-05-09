"""
exporter.py
All output formats for the enhanced timetable scheduler.
  - CSV  : flat export, one row per entry (lectures + lab sessions)
  - HTML : interactive grid, tabbed by day, labs shown as merged amber blocks
  - PDF  : GIK-style landscape A3, one page per day, lab blocks visually distinct
"""

from __future__ import annotations
import csv
from collections import defaultdict
from pathlib import Path

from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, PageBreak,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from src.models import Assignment, LabSession, TimeSlot, Room, ScheduleResult
from src.utils  import slots_by_day, program_color, utilisation_stats, DAY_ORDER


# ─────────────────────────── CSV ──────────────────────────────────────────────

def export_csv(result: ScheduleResult, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "session_type", "code", "section", "title",
        "instructor", "program", "capacity", "credit_hours",
        "day", "start_time", "end_time",
        "room_name", "building", "slot_ids",
    ]
    rows = sorted(
        result.all_rows,
        key=lambda r: (
            DAY_ORDER.index(r["day"]) if r["day"] in DAY_ORDER else 9,
            r["start_time"],
            r["room_name"],
        ),
    )
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"[exporter] CSV  → {path}  ({len(rows)} rows)")


# ─────────────────────────── HTML ─────────────────────────────────────────────

def export_html(result: ScheduleResult, slots: list[TimeSlot],
                rooms: list[Room], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    # Build cell map: (day, slot_index, room_id) → list of (label_html, is_lab)
    cell_map: dict[tuple, list[tuple[str, bool]]] = defaultdict(list)

    for a in result.assignments:
        sec = f" {a.course.section}" if a.course.section else ""
        color = program_color(a.course.program)
        html = (f'<div class="cell-entry" style="background:{color}">'
                f'<b>{a.course.code}{sec}</b><br/>'
                f'<span class="inst">{a.course.instructor}</span><br/>'
                f'<span class="loc">{a.room.room_name}</span>'
                f'</div>')
        cell_map[(a.slot.day, a.slot.slot_index, a.room.room_id)].append((html, False))

    for ls in result.lab_sessions:
        sec = f" {ls.course.section}" if ls.course.section else ""
        for slot in ls.slots:
            html = (f'<div class="cell-entry lab-entry">'
                    f'<b>{ls.course.code}{sec}</b> <span class="lab-tag">LAB 3h</span><br/>'
                    f'<span class="inst">{ls.course.instructor}</span><br/>'
                    f'<span class="loc">{ls.room.room_name}</span>'
                    f'</div>')
            cell_map[(ls.day, slot.slot_index, ls.room.room_id)].append((html, True))

    by_day        = slots_by_day(slots)
    display_rooms = [r for r in rooms if r.room_id != "TBA_ROOM"]
    stats         = utilisation_stats(result, rooms, slots)

    tab_buttons = ""
    tab_panels  = ""

    for di, day in enumerate(DAY_ORDER):
        day_slots = by_day.get(day, [])
        if not day_slots:
            continue
        active = "active" if di == 0 else ""
        tab_buttons += (f'<button class="tab-btn {active}" '
                        f'onclick="showDay(\'{day}\')" id="btn-{day}">{day}</button>\n')

        time_headers = "".join(
            f'<th>{s.start_time}<br/>{s.end_time}</th>' for s in day_slots
        )
        rows_html = ""
        for r in display_rooms:
            cells_html = ""
            for s in day_slots:
                entries = cell_map.get((day, s.slot_index, r.room_id), [])
                content = "".join(e[0] for e in entries)
                is_lab  = any(e[1] for e in entries)
                cls     = "lab-cell" if is_lab else ("occupied" if content else "empty")
                cells_html += f'<td class="{cls}">{content}</td>'
            rows_html += (f'<tr>'
                          f'<td class="room-name">{r.room_name}'
                          f'<br/><small>{r.building}</small></td>'
                          f'{cells_html}</tr>\n')

        display = "block" if di == 0 else "none"
        tab_panels += f"""
        <div id="panel-{day}" class="tab-panel" style="display:{display}">
          <div class="table-wrap">
            <table>
              <thead><tr>
                <th class="room-col">Room / Hall</th>{time_headers}
              </tr></thead>
              <tbody>{rows_html}</tbody>
            </table>
          </div>
        </div>"""

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>GIK Timetable – Spring 2026</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:Arial,sans-serif;font-size:12px;background:#f4f6fb;color:#1a2a4a}}
    header{{background:#0f2550;color:#fff;padding:14px 20px;display:flex;align-items:center;justify-content:space-between}}
    header h1{{font-size:17px}} header p{{font-size:11px;opacity:.8;margin-top:3px}}
    .stats-bar{{background:#1b3a6b;color:#ccd9f0;font-size:11px;padding:6px 20px;display:flex;gap:24px;flex-wrap:wrap}}
    .stats-bar span b{{color:#7ecbff}}
    .legend{{background:#fff;border-bottom:1px solid #dde;padding:6px 16px;font-size:11px;display:flex;gap:20px;align-items:center}}
    .leg-box{{width:14px;height:14px;border-radius:3px;display:inline-block;margin-right:5px;vertical-align:middle}}
    .tabs{{background:#fff;border-bottom:2px solid #1b3a6b;padding:0 16px}}
    .tab-btn{{background:none;border:none;padding:10px 18px;font-size:13px;cursor:pointer;color:#444;border-bottom:3px solid transparent;transition:all .15s}}
    .tab-btn.active,.tab-btn:hover{{color:#0f2550;border-bottom-color:#1b3a6b;font-weight:bold}}
    .tab-panel{{padding:12px 16px}}
    .table-wrap{{overflow-x:auto;border-radius:6px;box-shadow:0 1px 6px #00000018}}
    table{{border-collapse:collapse;min-width:100%;background:#fff}}
    thead th{{background:#1b3a6b;color:#fff;font-size:11px;padding:7px 5px;text-align:center;white-space:nowrap;border:1px solid #3a5a9b}}
    thead th.room-col{{width:110px;background:#142040}}
    tbody tr:nth-child(even){{background:#f0f4fb}}
    tbody tr:hover{{background:#dce8f8}}
    td{{border:1px solid #c8d4e8;padding:3px 4px;vertical-align:top;min-width:80px}}
    td.room-name{{font-weight:bold;font-size:10px;background:#e8edf5;color:#1b3a6b;width:110px;white-space:nowrap}}
    td.room-name small{{font-weight:normal;color:#5a7aaa;display:block}}
    td.empty{{background:#fbfcff}}
    td.occupied{{background:#f8faff}}
    td.lab-cell{{background:#fff8e1;border-left:3px solid #f59e0b}}
    .cell-entry{{border-radius:4px;padding:3px 5px;margin-bottom:2px;border-left:3px solid #1b3a6b33;font-size:10px;line-height:1.35}}
    .lab-entry{{background:#fff3cd!important;border-left:3px solid #f59e0b!important}}
    .lab-tag{{background:#f59e0b;color:#fff;border-radius:3px;font-size:8px;padding:1px 4px;font-weight:bold}}
    .cell-entry b{{font-size:10.5px;color:#0f2550}}
    .inst{{color:#4a6080;font-size:9.5px}}
    .loc{{color:#1b6a3b;font-size:9px;font-style:italic}}
    footer{{text-align:center;font-size:10px;color:#888;padding:14px}}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>GIK Institute – Timetable Spring 2026</h1>
      <p>Effective from February 02, 2026 &nbsp;|&nbsp; Intelligent Room Allocation</p>
    </div>
  </header>
  <div class="stats-bar">
    <span>Lectures: <b>{stats["lectures_placed"]}</b></span>
    <span>Lab sessions: <b>{stats["labs_placed"]}</b></span>
    <span>Unscheduled: <b>{stats["unscheduled"]}</b></span>
    <span>Success: <b>{stats["success_rate"]}%</b></span>
    <span>Busiest room: <b>{stats["busiest_room"][0]}</b> ({stats["busiest_room"][1]})</span>
    <span>Busiest day: <b>{stats["busiest_day"][0]}</b> ({stats["busiest_day"][1]})</span>
  </div>
  <div class="legend">
    <span><span class="leg-box" style="background:#f8faff;border:1px solid #c8d4e8"></span>Lecture</span>
    <span><span class="leg-box" style="background:#fff3cd;border:1px solid #f59e0b"></span>Lab (3h continuous)</span>
  </div>
  <div class="tabs">{tab_buttons}</div>
  {tab_panels}
  <footer>Director (Admissions and Examinations) &nbsp;|&nbsp; GIK Timetable Scheduler &nbsp;|&nbsp; Spring 2026</footer>
  <script>
    function showDay(day){{
      document.querySelectorAll('.tab-panel').forEach(p=>p.style.display='none');
      document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
      document.getElementById('panel-'+day).style.display='block';
      document.getElementById('btn-'+day).classList.add('active');
    }}
  </script>
</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"[exporter] HTML → {path}")


# ─────────────────────────── PDF ──────────────────────────────────────────────

HDR_BG    = colors.HexColor("#1B3A6B")
HDR_FG    = colors.white
DAY_BG    = colors.HexColor("#2E5FA3")
DAY_FG    = colors.white
ROOM_BG   = colors.HexColor("#E8EDF5")
ALT1      = colors.HexColor("#FFFFFF")
ALT2      = colors.HexColor("#F0F4FB")
LAB_BG    = colors.HexColor("#FFF3CD")
LAB_BDR   = colors.HexColor("#F59E0B")
BORDER    = colors.HexColor("#A0AABF")
TITLE_BG  = colors.HexColor("#0F2550")


def _cell_para(entries: list[tuple[str, bool, str, str]], style: ParagraphStyle,
               lab_style: ParagraphStyle) -> Paragraph:
    """Build a Paragraph for a PDF cell from (text, is_lab, room, instructor) tuples."""
    if not entries:
        return Paragraph("", style)
    lines = []
    for text, is_lab, _, instructor in entries:
        tag = " <font color='#b45309' size='5'>[LAB]</font>" if is_lab else ""
        inst_str = (f"<br/><font size='4.5' color='#4a6080'>{instructor}</font>"
                    if instructor and instructor.upper().strip() not in ("TBA", "TBD", "")
                    else "")
        lines.append(f"<b>{text}</b>{tag}{inst_str}")
    return Paragraph("<br/>".join(lines), lab_style if entries[0][1] else style)


def export_pdf(result: ScheduleResult, slots: list[TimeSlot],
               rooms: list[Room], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    page_w, _ = landscape(A3)

    doc = SimpleDocTemplate(
        str(path), pagesize=landscape(A3),
        leftMargin=1*cm, rightMargin=1*cm,
        topMargin=1.2*cm, bottomMargin=1*cm,
    )

    hdr_style  = ParagraphStyle("hdr",  fontName="Helvetica-Bold",   fontSize=7,
                                 textColor=HDR_FG,  alignment=TA_CENTER)
    room_style = ParagraphStyle("rm",   fontName="Helvetica-Bold",   fontSize=6.5,
                                 textColor=colors.HexColor("#1B3A6B"), alignment=TA_LEFT)
    cell_style = ParagraphStyle("cell", fontName="Helvetica-Bold",   fontSize=5.5,
                                 textColor=colors.HexColor("#1B2B50"),
                                 alignment=TA_CENTER, leading=7)
    lab_style  = ParagraphStyle("lab",  fontName="Helvetica-Bold",   fontSize=5.5,
                                 textColor=colors.HexColor("#92400E"),
                                 alignment=TA_CENTER, leading=7)
    title_style= ParagraphStyle("ttl",  fontName="Helvetica-Bold",   fontSize=13,
                                 textColor=HDR_FG,  alignment=TA_CENTER)
    foot_style = ParagraphStyle("ft",   fontName="Helvetica-Oblique",fontSize=7,
                                 textColor=colors.HexColor("#555555"), alignment=TA_CENTER)

    # ── Cell lookup ───────────────────────────────────────────────────────────
    # (day, slot_index, room_id) → [(display_text, is_lab, room_name, instructor)]
    cell_map: dict[tuple, list[tuple[str, bool, str, str]]] = defaultdict(list)

    for a in result.assignments:
        sec  = f" {a.course.section}" if a.course.section else ""
        cell_map[(a.slot.day, a.slot.slot_index, a.room.room_id)].append(
            (f"{a.course.code}{sec}", False, a.room.room_name, a.course.instructor)
        )

    for ls in result.lab_sessions:
        sec = f" {ls.course.section}" if ls.course.section else ""
        for slot in ls.slots:
            cell_map[(ls.day, slot.slot_index, ls.room.room_id)].append(
                (f"{ls.course.code}{sec}", True, ls.room.room_name, ls.course.instructor)
            )

    by_day        = slots_by_day(slots)
    display_rooms = [r for r in rooms if r.room_id != "TBA_ROOM"]

    story = []

    # ── Cover header ──────────────────────────────────────────────────────────
    hdr_tbl = Table(
        [[Paragraph(
            "GIK Institute of Engineering Sciences and Technology<br/>"
            "<font size='10'>Timetable Spring 2026 &nbsp;|&nbsp; "
            "Effective from February 02, 2026 &nbsp;|&nbsp; "
            "Intelligent Room Allocation</font>",
            title_style,
        )]],
        colWidths=[page_w - 2*cm],
    )
    hdr_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), TITLE_BG),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
    ]))
    story.append(hdr_tbl)
    story.append(Spacer(1, 0.3*cm))

    # ── One page per day ──────────────────────────────────────────────────────
    for day_idx, day in enumerate(DAY_ORDER):
        day_slots = by_day.get(day, [])
        if not day_slots:
            continue

        n_slots    = len(day_slots)
        avail_w    = page_w - 2*cm
        room_col_w = 2.5*cm
        slot_col_w = (avail_w - room_col_w) / n_slots
        col_widths = [room_col_w] + [slot_col_w] * n_slots

        # Row 0: day banner
        day_row  = [Paragraph(f"<b>{day.upper()}</b>", hdr_style)] + \
                   [Paragraph("", hdr_style)] * n_slots
        # Row 1: time labels
        time_row = [Paragraph("Room / Hall", hdr_style)] + \
                   [Paragraph(f"{s.start_time}<br/>{s.end_time}", hdr_style)
                    for s in day_slots]

        table_data = [day_row, time_row]
        DATA_OFFSET = 2

        # Track which (row, col) cells contain lab entries for coloring
        lab_cells: list[tuple[int, int]] = []

        for row_i, r in enumerate(display_rooms):
            cells = [Paragraph(r.room_name, room_style)]
            for col_i, s in enumerate(day_slots):
                entries = cell_map.get((day, s.slot_index, r.room_id), [])
                para    = _cell_para(entries, cell_style, lab_style)
                cells.append(para)
                if entries and entries[0][1]:   # is_lab
                    lab_cells.append((DATA_OFFSET + row_i, col_i + 1))
            table_data.append(cells)

        n_rows = len(table_data)

        base_styles = [
            ("SPAN",            (0,0), (-1,0)),
            ("BACKGROUND",      (0,0), (-1,0),  DAY_BG),
            ("TEXTCOLOR",       (0,0), (-1,0),  DAY_FG),
            ("ALIGN",           (0,0), (-1,0),  "CENTER"),
            ("TOPPADDING",      (0,0), (-1,0),  4),
            ("BOTTOMPADDING",   (0,0), (-1,0),  4),
            ("BACKGROUND",      (0,1), (-1,1),  HDR_BG),
            ("TEXTCOLOR",       (0,1), (-1,1),  HDR_FG),
            ("TOPPADDING",      (0,1), (-1,1),  3),
            ("BOTTOMPADDING",   (0,1), (-1,1),  3),
            ("BACKGROUND",      (0,DATA_OFFSET),(0,n_rows-1), ROOM_BG),
            ("LEFTPADDING",     (0,DATA_OFFSET),(0,n_rows-1), 3),
            ("ROWBACKGROUNDS",  (0,DATA_OFFSET),(-1,n_rows-1), [ALT1, ALT2]),
            ("TOPPADDING",      (0,DATA_OFFSET),(-1,n_rows-1), 2),
            ("BOTTOMPADDING",   (0,DATA_OFFSET),(-1,n_rows-1), 2),
            ("GRID",            (0,0),(-1,n_rows-1), 0.4, BORDER),
            ("ALIGN",           (0,0),(-1,n_rows-1), "CENTER"),
            ("VALIGN",          (0,0),(-1,n_rows-1), "MIDDLE"),
            ("FONTSIZE",        (0,0),(-1,n_rows-1), 6),
        ]

        # Highlight lab cells amber
        lab_styles = []
        for (row, col) in lab_cells:
            lab_styles += [
                ("BACKGROUND", (col, row), (col, row), LAB_BG),
                ("BOX",        (col, row), (col, row), 1.0, LAB_BDR),
            ]

        tbl = Table(table_data, colWidths=col_widths, repeatRows=2)
        tbl.setStyle(TableStyle(base_styles + lab_styles))
        story.append(tbl)

        if day_idx < len(DAY_ORDER) - 1:
            story.append(PageBreak())

    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(
        "■ Amber cells = Lab sessions (3h continuous) &nbsp;|&nbsp; "
        "Director (Admissions and Examinations) &nbsp;|&nbsp; Spring 2026",
        foot_style,
    ))

    doc.build(story)
    print(f"[exporter] PDF  → {path}")


# ─────────────────────────── All-in-one ───────────────────────────────────────

def export_all(result: ScheduleResult, slots: list[TimeSlot],
               rooms: list[Room], output_dir: str | Path = "output") -> dict[str, Path]:
    d = Path(output_dir)
    d.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv":  d / "timetable_spring_2026.csv",
        "html": d / "timetable_spring_2026.html",
        "pdf":  d / "timetable_spring_2026.pdf",
    }
    export_csv(result,                paths["csv"])
    export_html(result, slots, rooms, paths["html"])
    export_pdf(result,  slots, rooms, paths["pdf"])
    return paths
