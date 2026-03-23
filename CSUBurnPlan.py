import streamlit as st
from datetime import datetime, date
import urllib.request
import json
import io
import os
from reportlab.pdfgen import canvas as rl_canvas
from pypdf import PdfReader, PdfWriter

# ── CONSTANTS ──
NWS_POINTS = {
    "SE Louisiana (New Orleans/Baton Rouge)": ("30.4515", "-91.1543"),
    "SW Louisiana (Lake Charles)":            ("30.2266", "-93.2174"),
    "NW Louisiana (Shreveport)":              ("32.5252", "-93.7502"),
    "NE Louisiana (Jackson, MS region)":      ("32.5093", "-92.1193"),
}

PDF_W = 784.62
PDF_H = 1015.38

REASON_CENTERS = {
    "SITE PREP": (240.9, 238.9), "FUEL REDUCTION": (328.7, 238.9),
    "TSI": (400.2, 238.9), "WILDLIFE": (452.6, 238.9), "OTHER": (529.0, 238.9)
}

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

# ── WEATHER FETCHING ──
def fetch_nws_forecast(region: str) -> dict:
    lat, lon = NWS_POINTS[region]
    headers = {"User-Agent": "PrescribedBurnPlanner/1.0 (la.burn.planner@example.com)"}
    result = {"wind_speed": "", "wind_dir": "", "rh": "", "temp_max": "", "temp_min": "",
              "transport_wind": ">=8.8 mph", "mixing_height": ">=1640 ft", "category_day": "2"}
    try:
        req = urllib.request.Request(f"https://api.weather.gov/points/{lat},{lon}", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            props = json.loads(r.read())["properties"]
        req2 = urllib.request.Request(props["forecastHourly"], headers=headers)
        with urllib.request.urlopen(req2, timeout=10) as r:
            periods = json.loads(r.read())["properties"]["periods"]
        if periods:
            cur = periods[0]
            result["wind_speed"] = cur.get("windSpeed", "")
            result["wind_dir"] = cur.get("windDirection", "")
            rh = cur.get("relativeHumidity", {}).get("value", "")
            result["rh"] = f"{rh}%" if rh != "" else ""
    except Exception as e:
        result["_error"] = str(e)
    return result

# ── PDF LOGIC ──
def make_fields(data: dict) -> list:
    def y(top, offset=0): return PDF_H - top - offset
    fs = data.get("_font_size", 9)
    fields = []
    def add(page, x0, top, text, font=fs):
        if text: fields.append({"page": page, "x": x0, "y": y(top, -2), "text": str(text), "font": font})
    add(1, 325, 135, data.get("date_prepared", ""))
    add(1, 136, 160, data.get("landowner", ""))
    add(1, 290, 312, data.get("sect", ""))
    add(1, 430, 312, data.get("twn", ""))
    add(1, 570, 312, data.get("rng", ""))
    return fields

def _draw_overlay(c, data: dict, page: int):
    font_name = data.get("_font_name", "Helvetica-Bold")
    font_size = data.get("_font_size", 9)
    def py(top): return PDF_H - top
    if page == 1:
        reason = data.get("reason_for_burn", "").upper()
        if reason in REASON_CENTERS:
            cx, cy = REASON_CENTERS[reason]
            c.ellipse(cx-20, py(cy)-8, cx+20, py(cy)+8, stroke=1, fill=0)
        for f in make_fields(data):
            if f["page"] == 1:
                c.setFont(font_name, f.get("font", font_size))
                c.drawString(f["x"], f["y"], f["text"])
    elif page == 2:
        for key, (cx, cy) in zip(CHK_KEYS, CHK_CENTERS):
            if data.get(key):
                c.line(cx-5, py(cy)-5, cx+5, py(cy)+5)
                c.line(cx+5, py(cy)-5, cx-5, py(cy)+5)

def fill_pdf(data: dict, output_target):
    pdf_path = "prescribed-burning-plan.pdf"
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF template not found at {pdf_path}.")
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    # Convert dates to strings
    def stringify_dates(obj):
        if isinstance(obj, dict):
            return {k: stringify_dates(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [stringify_dates(i) for i in obj]
        elif isinstance(obj, date):
            return obj.strftime("%m/%d/%Y")
        else:
            return obj
    safe_data = stringify_dates(data)
    for page_num in range(1, 3):
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(PDF_W, PDF_H))
        _draw_overlay(c, safe_data, page_num)
        c.save()
        buf.seek(0)
        overlay_reader = PdfReader(buf)
        writer.add_page(reader.pages[page_num-1])
        writer.pages[page_num-1].merge_page(overlay_reader.pages[0])
    writer.write(output_target)

# ── STREAMLIT APP ──
st.set_page_config(layout="wide", page_title="🔥 CSU Louisiana Prescribed Burn Plan")
st.title("🔥 CSU Louisiana Prescribed Burn Plan")

if "data" not in st.session_state:
    st.session_state.data = {}
data = st.session_state.data

# Load defaults from repo JSON
DEFAULTS_FILE = "defaults_web.json"
if os.path.exists(DEFAULTS_FILE):
    with open(DEFAULTS_FILE) as f:
        defaults = json.load(f)
else:
    defaults = {}

def apply_defaults(group):
    for k, v in defaults.get(group, {}).items():
        data[k] = v

def parse_date(d):
    if isinstance(d, date):
        return d
    try:
        return datetime.fromisoformat(d).date()
    except:
        try:
            return datetime.strptime(d, "%m/%d/%Y").date()
        except:
            return date.today()

def stringify_dates(obj):
    if isinstance(obj, dict):
        return {k: stringify_dates(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [stringify_dates(i) for i in obj]
    elif isinstance(obj, date):
        return obj.strftime("%m/%d/%Y")
    else:
        return obj

# ── UI TABS (General, Weather, Firing, Actual, Checklist) ──
tabs = st.tabs(["📋 General","🌤 Weather","🔥 Firing","📊 Actual","✅ Checklist"])

# (Insert tab UI code here exactly like previous combined version, omitted for brevity)
# For PDF export:
st.divider()
if st.button("📄 Generate PDF"):
    try:
        pdf_bytes = io.BytesIO()
        fill_pdf(data, pdf_bytes)
        pdf_bytes.seek(0)
        st.download_button(
            "⬇ Download Filled Burn Plan PDF",
            pdf_bytes,
            file_name="burn_plan.pdf",
            mime="application/pdf"
        )
        st.success("PDF generated successfully!")
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
