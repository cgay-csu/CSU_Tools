import streamlit as st
import urllib.request
import json
from datetime import date
import os
import io
from reportlab.pdfgen import canvas as rl_canvas
from pypdf import PdfReader, PdfWriter

# --- 1. CONSTANTS & DATA STRUCTURES ---
NWS_POINTS = {
    "SE Louisiana (New Orleans/Baton Rouge)": ("30.4515", "-91.1543"),
    "SW Louisiana (Lake Charles)":            ("30.2266", "-93.2174"),
    "NW Louisiana (Shreveport)":              ("32.5252", "-93.7502"),
    "NE Louisiana (Jackson, MS region)":      ("32.5093", "-92.1193"),
}

PDF_W, PDF_H = 784.62, 1015.38

# Coordinates for drawing circles/selections
REASON_CENTERS = {"SITE PREP": (240.9, 238.9), "FUEL REDUCTION": (328.7, 238.9), "TSI": (400.2, 238.9), "WILDLIFE": (452.6, 238.9), "OTHER": (529.0, 238.9)}
FUEL_AMOUNT_CENTERS = {"LIGHT": (238.7, 255.7), "MEDIUM": (324.5, 255.7), "HEAVY": (417.1, 255.7)}
FUEL_TYPE_CENTERS = {"GRASSES": (246.5, 270.3), "BRUSH": (321.1, 270.3), "LOGGING DEBRIS": (437.8, 270.3), "OTHER": (261.2, 284.9)}
FIRING_CENTERS = {"HEAD": (262.8, 651.4), "FLANK": (327.0, 651.4), "BACKING": (398.7, 651.4), "OTHER": (470.6, 651.4)}

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

# --- 2. WEATHER FETCHING ---
def fetch_nws_forecast(region: str) -> dict:
    lat, lon = NWS_POINTS[region]
    headers = {"User-Agent": "BurnPlanTool/1.0"}
    result = {"wind_speed": "", "wind_dir": "", "rh": "", "temp_max": "", "temp_min": ""}
    try:
        req = urllib.request.Request(f"https://api.weather.gov/points/{lat},{lon}", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            props = json.loads(r.read())["properties"]
        
        req2 = urllib.request.Request(props["forecastHourly"], headers=headers)
        with urllib.request.urlopen(req2, timeout=10) as r:
            periods = json.loads(r.read())["properties"]["periods"]
        
        if periods:
            cur = periods[0]
            result.update({
                "wind_speed": cur.get("windSpeed", ""),
                "wind_dir": cur.get("windDirection", ""),
                "rh": f"{cur.get('relativeHumidity', {}).get('value', '')}%",
                "temp_max": f"{cur.get('temperature', '')}F"
            })
    except Exception as e:
        result["_error"] = str(e)
    return result

# --- 3. PDF RENDERING ---
def fill_pdf(data: dict, output_target):
    src = "prescribed-burning-plan.pdf" 
    if not os.path.exists(src):
        raise FileNotFoundError("Missing 'prescribed-burning-plan.pdf' template.")
    
    reader = PdfReader(src)
    writer = PdfWriter()

    for p_idx in range(len(reader.pages)):
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(PDF_W, PDF_H))
        
        # Draw dynamic text/circles
        _draw_page_content(c, data, p_idx + 1)
        
        c.save()
        buf.seek(0)
        overlay = PdfReader(buf)
        page = reader.pages[p_idx]
        page.merge_page(overlay.pages[0])
        writer.add_page(page)

    writer.write(output_target)

def _draw_page_content(c, data, page_num):
    def py(top): return PDF_H - top
    font_name = data.get("_font_name", "Helvetica-Bold")
    font_size = data.get("_font_size", 9)
    c.setFont(font_name, font_size)

    if page_num == 1:
        # Text fields
        c.drawString(325, py(135), str(data.get("date_prepared", "")))
        c.drawString(136, py(160), str(data.get("landowner", "")))
        
        # Circles
        reason = data.get("reason_for_burn", "").upper()
        if reason in REASON_CENTERS:
            cx, cy = REASON_CENTERS[reason]
            c.ellipse(cx-20, py(cy)-8, cx+20, py(cy)+8)

    elif page_num == 2:
        for key, (cx, cy) in zip(CHK_KEYS, CHK_CENTERS):
            if data.get(key):
                c.line(cx-5, py(cy)-5, cx+5, py(cy)+5)
                c.line(cx+5, py(cy)-5, cx-5, py(cy)+5)
