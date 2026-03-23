import streamlit as st
import urllib.request
import json
from datetime import date
import os
import io
from reportlab.pdfgen import canvas as rl_canvas
from pypdf import PdfReader, PdfWriter

# ── 1. CONSTANTS & DATA STRUCURES (Defined first to avoid NameErrors) ──
# Moving these to the top ensures they are available to all functions[cite: 75, 78].
NWS_POINTS = {
    "SE Louisiana (New Orleans/Baton Rouge)": ("30.4515", "-91.1543"),
    "SW Louisiana (Lake Charles)":            ("30.2266", "-93.2174"),
    "NW Louisiana (Shreveport)":              ("32.5252", "-93.7502"),
    "NE Louisiana (Jackson, MS region)":      ("32.5093", "-92.1193"),
}

# PDF Dimensions
PDF_W = 784.62
PDF_H = 1015.38

# Coordinate Maps for Circles and Boxes
REASON_CENTERS = {"SITE PREP": (240.9, 238.9), "FUEL REDUCTION": (328.7, 238.9), "TSI": (400.2, 238.9), "WILDLIFE": (452.6, 238.9), "OTHER": (529.0, 238.9)}
FUEL_AMOUNT_CENTERS = {"LIGHT": (238.7, 255.7), "MEDIUM": (324.5, 255.7), "HEAVY": (417.1, 255.7)}
FUEL_TYPE_CENTERS = {"GRASSES": (246.5, 270.3), "BRUSH": (321.1, 270.3), "LOGGING DEBRIS": (437.8, 270.3), "OTHER": (261.2, 284.9)}
FIRING_CENTERS = {"HEAD": (262.8, 651.4), "FLANK": (327.0, 651.4), "BACKING": (398.7, 651.4), "OTHER": (470.6, 651.4)}
YES_CENTER, NO_CENTER = (537.6, 355.4), (622.0, 355.4)

CHK_KEYS = [
    "chk_plan_complete", "chk_adj_notified", "chk_fire_auth", "chk_smoke_map", "chk_burn_map", 
    "chk_equipment", "chk_signs", "chk_test_burn", "chk_briefing", "chk_objectives", 
    "chk_map_disc", "chk_hazards", "chk_assignments", "chk_ignition", "chk_comms", 
    "chk_equip_loc", "chk_assistance", "chk_questions"
]

CHK_CENTERS = [
    (160.0, 156.4), (160.0, 182.8), (160.0, 208.2), (160.0, 246.7), (160.0, 273.1),
    (160.0, 299.5), (160.0, 325.9), (160.0, 351.3), (160.0, 415.3), (160.0, 441.7),
    (160.0, 467.1), (160.0, 493.5), (160.0, 519.9), (160.0, 546.3), (160.0, 571.7),
    (160.0, 598.1), (160.0, 636.6)
]

# ── 2. WEATHER FETCHING ──
def fetch_nws_forecast(region: str) -> dict:
    lat, lon = NWS_POINTS[region] [cite: 3]
    headers = {"User-Agent": "PrescribedBurnPlanner/1.0 (la.burn.planner@example.com)"} [cite: 3]
    result = {"wind_speed": "", "wind_dir": "", "rh": "", "temp_max": "", "temp_min": "",
              "transport_wind": ">=8.8 mph", "mixing_height": ">=1640 ft", "category_day": "2"} [cite: 3]
    try:
        req = urllib.request.Request(f"https://api.weather.gov/points/{lat},{lon}", headers=headers) [cite: 4]
        with urllib.request.urlopen(req, timeout=10) as r:
            props = json.loads(r.read())["properties"] [cite: 4]
        
        # Hourly for current conditions
        req2 = urllib.request.Request(props["forecastHourly"], headers=headers) [cite: 4]
        with urllib.request.urlopen(req2, timeout=10) as r:
            periods = json.loads(r.read())["properties"]["periods"] [cite: 4]
        if periods:
            cur = periods[0] [cite: 5]
            result["wind_speed"] = cur.get("windSpeed", "") [cite: 5]
            result["wind_dir"] = cur.get("windDirection", "") [cite: 5]
            rh = cur.get("relativeHumidity", {}).get("value", "") [cite: 5]
            result["rh"] = f"{rh}%" if rh != "" else "" [cite: 5]
    except Exception as e:
        result["_error"] = str(e) [cite: 8]
    return result

# ── 3. PDF RENDERING LOGIC ──
def make_fields(data: dict) -> list:
    def y(top, offset=0): return PDF_H - top - offset [cite: 9]
    fs = data.get("_font_size", 9) [cite: 9]
    fields = []
    def add(page, x0, top, text, font=fs):
        if text: fields.append({"page": page, "x": x0, "y": y(top, -2), "text": str(text), "font": font}) [cite: 10]

    # Mapping your data keys to PDF coordinates [cite: 11, 12, 13, 14, 15]
    add(1, 325, 135, data.get("date_prepared", ""))
    add(1, 136, 160, data.get("landowner", ""))
    add(1, 290, 312, data.get("sect", ""))
    add(1, 430, 312, data.get("twn", ""))
    add(1, 570, 312, data.get("rng", ""))
    # ... add other fields as needed ...
    return fields

def _draw_overlay(c, data: dict, page: int):
    font_name = data.get("_font_name", "Helvetica-Bold") [cite: 21]
    font_size = data.get("_font_size", 9) [cite: 21]
    def py(top): return PDF_H - top [cite: 21]

    if page == 1:
        # Drawing circles based on selection [cite: 23, 24, 25, 26]
        reason = data.get("reason_for_burn", "").upper()
        if reason in REASON_CENTERS:
            cx, cy = REASON_CENTERS[reason]
            c.ellipse(cx-20, py(cy)-8, cx+20, py(cy)+8, stroke=1, fill=0) [cite: 21, 22]

        for f in make_fields(data):
            if f["page"] == 1:
                c.setFont(font_name, f.get("font", font_size))
                c.drawString(f["x"], f["y"], f["text"]) [cite: 27]
    
    elif page == 2:
        for key, (cx, cy) in zip(CHK_KEYS, CHK_CENTERS): [cite: 28]
            if data.get(key):
                c.line(cx-5, py(cy)-5, cx+5, py(cy)+5) [cite: 22]
                c.line(cx+5, py(cy)-5, cx-5, py(cy)+5) [cite: 22]

def fill_pdf(data: dict, output_target):
    # Search for the PDF in the current directory [cite: 29]
    src = "prescribed-burning-plan.pdf" 
    if not os.path.exists(src):
        raise FileNotFoundError("Place 'prescribed-burning-plan.pdf' in the repository.") [cite: 29]
    
    reader = PdfReader(src) [cite: 29]
    writer = PdfWriter() [cite: 29]
    
    for page_num in range(1, 3):
        buf = io.BytesIO() [cite: 30]
        c = rl_canvas.Canvas(buf, pagesize=(PDF_W, PDF_H)) [cite: 30]
        _draw_overlay(c, data, page_num)
        c.save()
        buf.seek(0)
        overlay_reader = PdfReader(buf)
        writer.add_page(reader.pages[page_num-1])
        writer.pages[page_num-1].merge_page(overlay_reader.pages[0]) [cite: 30]

    writer.write(output_target) [cite: 30]
