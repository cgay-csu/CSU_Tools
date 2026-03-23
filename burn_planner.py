"""
Louisiana LDAF Prescribed Burning Plan PDF Filler
- GUI for all form fields with per-tab "Set Defaults" buttons
- Fetch current fire weather on the Actual Burn Eval tab
- Outputs a filled PDF
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import urllib.request
import json
from datetime import date
import os
import sys
import io

# ── PDF rendering ────────────────────────────────────────────────────────────
try:
    from reportlab.pdfgen import canvas as rl_canvas
    from pypdf import PdfReader, PdfWriter
except ImportError:
    import tkinter.messagebox as mb
    mb.showerror("Missing packages", "Please install: pip install pypdf reportlab")
    sys.exit(1)

#set absolute path for PDF
def resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.abspath("."), filename)


# ── NWS API ───────────────────────────────────────────────────────────────────
NWS_POINTS = {
    "SE Louisiana (New Orleans/Baton Rouge)": ("30.4515", "-91.1543"),
    "SW Louisiana (Lake Charles)":            ("30.2266", "-93.2174"),
    "NW Louisiana (Shreveport)":              ("32.5252", "-93.7502"),
    "NE Louisiana (Jackson, MS region)":      ("32.5093", "-92.1193"),
}

def fetch_nws_forecast(region: str) -> dict:
    lat, lon = NWS_POINTS[region]
    headers = {"User-Agent": "PrescribedBurnPlanner/1.0 (la.burn.planner@example.com)"}
    result = {
        "wind_speed": "", "wind_dir": "", "rh": "",
        "temp_max": "", "temp_min": "",
        "transport_wind": ">=8.8 mph (verify at weather.gov/fire)",
        "mixing_height":  ">=1640 ft (verify at weather.gov/fire)",
        "category_day":   "2 (verify - do NOT burn on Cat 1)",
    }
    try:
        req = urllib.request.Request(
            f"https://api.weather.gov/points/{lat},{lon}", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            props = json.loads(r.read())["properties"]

        req2 = urllib.request.Request(props["forecastHourly"], headers=headers)
        with urllib.request.urlopen(req2, timeout=10) as r:
            periods = json.loads(r.read())["properties"]["periods"]
        if periods:
            cur = periods[0]
            result["wind_speed"] = cur.get("windSpeed", "")
            result["wind_dir"]   = cur.get("windDirection", "")
            rh = cur.get("relativeHumidity", {}).get("value", "")
            result["rh"] = f"{rh}%" if rh != "" else ""
            tmp = cur.get("temperature", "")
            result["temp_max"] = f"{tmp}F" if tmp != "" else ""

        req3 = urllib.request.Request(props["forecast"], headers=headers)
        with urllib.request.urlopen(req3, timeout=10) as r:
            dperiods = json.loads(r.read())["properties"]["periods"]
        hi = lo = None
        for p in dperiods[:4]:
            t = p.get("temperature")
            if t is None:
                continue
            if p.get("isDaytime", True):
                hi = t if hi is None else max(hi, t)
            else:
                lo = t if lo is None else min(lo, t)
        if hi is not None:
            result["temp_max"] = f"{hi}F"
        if lo is not None:
            result["temp_min"] = f"{lo}F"
    except Exception as e:
        result["_error"] = str(e)
    return result


# ── PDF filling ───────────────────────────────────────────────────────────────
PDF_W = 784.62
PDF_H = 1015.38

def make_fields(data: dict) -> list:
    def y(top, offset=0):
        return PDF_H - top - offset

    fs  = data.get("_font_size", 9)
    fs9 = fs  # keep same size throughout; label was just "slightly bigger"
    fields = []

    def add(page, x0, top, text, font=fs):
        if not text:
            return
        fields.append({"page": page, "x": x0, "y": y(top, -2),
                        "text": str(text), "font": font})

    # Page 1 ───────────────────────────────────────────────────────────────────
    # x = label_x1 + 4pt gap (from form_structure.json), y = row top + 1
    add(1, 325, 135, data.get("date_prepared", ""))
    add(1, 136, 160, data.get("landowner", ""))
    add(1, 560, 160, data.get("phone", ""))
    add(1, 136, 178, data.get("address", ""))
    add(1, 200, 195, data.get("city_state_zip", ""))
    add(1, 350, 221, data.get("acreage", ""))
    add(1, 400, 236, data.get("reason_other", ""))
    add(1, 400, 251, data.get("fuel_type_other", ""))
    add(1, 290, 312, data.get("sect", ""))
    add(1, 430, 312, data.get("twn", ""))
    add(1, 570, 312, data.get("rng", ""))
    add(1, 290, 325, data.get("lat", ""))
    add(1, 480, 325, data.get("lon", ""))
    add(1, 220, 372, data.get("program_name", ""))
    add(1, 480, 372, data.get("application_num", ""))
    # Preburn factors
    add(1, 310, 410, data.get("smoke_sensitive", ""))
    add(1, 200, 425, data.get("special_precautions", ""))
    add(1, 310, 440, data.get("adj_landowners", ""))
    add(1, 310, 452, data.get("local_fire_dept", ""))
    add(1, 350, 470, data.get("ldaf_office", ""))
    add(1, 210, 498, data.get("one_call_locator", ""))
    # Weather factors DESIRED
    surface_w = f"{data.get('wind_speed', '')} {data.get('wind_dir', '')}".strip()
    add(1, 240, 530, surface_w)
    add(1, 430, 550, data.get("transport_wind", ""))
    add(1, 295, 564, data.get("mixing_height", ""))
    add(1, 320, 585, data.get("category_day", ""))
    add(1, 210, 600, data.get("rh", ""))
    add(1, 220, 615, f"{data.get('temp_max', '')} / {data.get('temp_min', '')}".strip(" /"))
    # Firing
    add(1, 560, 630, data.get("firing_other", ""))
    add(1, 250, 672, data.get("manpower_equipment", ""))
    # Prescribed Burn Evaluation ACTUAL
    add(1, 200, 720, data.get("actual_date", ""))
    surface_w2 = f"{data.get('actual_wind_speed', '')} {data.get('actual_wind_dir', '')}".strip()
    add(1, 310, 737, surface_w2)
    add(1, 420, 753, data.get("actual_transport", ""))
    add(1, 320, 770, data.get("actual_mixing", ""))
    add(1, 340, 787, data.get("actual_category", ""))
    add(1, 360, 804, data.get("actual_rh", ""))
    add(1, 310, 821, f"{data.get('actual_temp_max', '')} / {data.get('actual_temp_min', '')}".strip(" /"))
    add(1, 200, 837, data.get("start_time", ""))
    add(1, 500, 837, data.get("end_time", ""))
    add(1, 270, 848, data.get("deadout_time", ""))
    add(1, 310, 870, data.get("actual_acreage", ""))
    add(1, 150, 884, data.get("remarks", ""))
    add(1, 310, 920, data.get("plan_prepared_by", ""))
    add(1, 310, 940, data.get("fire_boss", ""))

    # Page 2 ───────────────────────────────────────────────────────────────────
    add(2, 310, 680, data.get("checklist_completed_by", ""))
    add(2, 310, 705, data.get("burn_manager_name", ""))
    add(2, 310, 730, data.get("burn_manager_contact", ""))
    add(2, 310, 755, data.get("checklist_date", ""))

    return fields


# ── Circle / checkbox coordinate maps ────────────────────────────────────────
# Each entry: option_value -> (center_x, center_y) in PDF points (top-of-page origin)
# rx/ry are the ellipse radii used when drawing circles

REASON_CENTERS = {
    "SITE PREP":      (240.9, 238.9),
    "FUEL REDUCTION": (328.7, 238.9),
    "TSI":            (400.2, 238.9),
    "WILDLIFE":       (452.6, 238.9),
    "OTHER":          (529.0, 238.9),
}
FUEL_AMOUNT_CENTERS = {
    "LIGHT":  (238.7, 255.7),
    "MEDIUM": (324.5, 255.7),
    "HEAVY":  (417.1, 255.7),
}
FUEL_TYPE_CENTERS = {
    "GRASSES":        (246.5, 270.3),
    "BRUSH":          (321.1, 270.3),
    "LOGGING DEBRIS": (437.8, 270.3),
    "OTHER":          (261.2, 284.9),
}
FIRING_CENTERS = {
    "HEAD":    (262.8, 651.4),
    "FLANK":   (327.0, 651.4),
    "BACKING": (398.7, 651.4),
    "OTHER":   (470.6, 651.4),
}
# YES/NO box centers (PDF top-origin)
YES_CENTER = (537.6, 355.4)
NO_CENTER  = (622.0, 355.4)

# Page 2 checklist checkbox centers (PDF top-origin x, top-origin y)
# Ordered to match the 17 checklist items in the form
CHK_CENTERS = [
    (160.0, 156.4),   # Page 1 of Plan completed
    (160.0, 182.8),   # Adjacent landowners notified
    (160.0, 208.2),   # Local Fire Authority contacted
    (160.0, 246.7),   # Smoke Sensitive Areas identified
    (160.0, 273.1),   # Map of burn compartment attached
    (160.0, 299.5),   # All equipment and personnel on scene
    (160.0, 325.9),   # Smoke Ahead signs
    (160.0, 351.3),   # Test burn performed
    (160.0, 415.3),   # Objectives discussed
    (160.0, 441.7),   # Map discussion
    (160.0, 467.1),   # Hazards discussed
    (160.0, 493.5),   # Crew assignments
    (160.0, 519.9),   # Ignition techniques
    (160.0, 546.3),   # Authority and comms
    (160.0, 571.7),   # On-site equipment locations
    (160.0, 598.1),   # Nearest assistance sources
    (160.0, 636.6),   # Questions answered
]

# Map GUI var keys to CHK_CENTERS index (same order as above)
CHK_KEYS = [
    "chk_plan_complete", "chk_adj_notified", "chk_fire_auth",
    "chk_smoke_map", "chk_burn_map", "chk_equipment",
    "chk_signs", "chk_test_burn", "chk_briefing",
    "chk_objectives", "chk_map_disc", "chk_hazards",
    "chk_assignments", "chk_ignition", "chk_comms",
    "chk_equip_loc", "chk_assistance", "chk_questions",
]


def _draw_overlay(c, data: dict, page: int):
    """Draw all circles, X-marks, and text for a given page onto canvas c."""

    font_name = data.get("_font_name", "Helvetica-Bold")
    font_size = data.get("_font_size", 9)

    def py(top_coord):
        """Convert top-of-page PDF coord to ReportLab bottom-of-page coord."""
        return PDF_H - top_coord

    c.setStrokeColorRGB(0, 0, 0)
    c.setFillColorRGB(0, 0, 0)

    def circle_option(cx, cy_top, rx=None, ry=8):
        """Draw an ellipse around an option word centred at (cx, cy_top)."""
        if rx is None:
            rx = ry * 3.8
        x1 = cx - rx
        y1 = py(cy_top) - ry
        x2 = cx + rx
        y2 = py(cy_top) + ry
        c.setLineWidth(1.2)
        c.ellipse(x1, y1, x2, y2, stroke=1, fill=0)

    def x_in_box(cx, cy_top, size=5):
        """Draw an X centred at (cx, cy_top)."""
        by = py(cy_top)
        c.setLineWidth(1.5)
        c.line(cx - size, by - size, cx + size, by + size)
        c.line(cx + size, by - size, cx - size, by + size)

    if page == 1:
        # ── Circles ───────────────────────────────────────────────────────────
        # Reason for burn
        reason = data.get("reason_for_burn", "").upper()
        if reason in REASON_CENTERS:
            cx, cy = REASON_CENTERS[reason]
            rx = 26 if reason == "FUEL REDUCTION" else (26 if reason == "SITE PREP" else 14)
            circle_option(cx, cy, rx=rx)

        # Fuel amount
        fuel_amt = data.get("fuel_amount", "").upper()
        if fuel_amt in FUEL_AMOUNT_CENTERS:
            cx, cy = FUEL_AMOUNT_CENTERS[fuel_amt]
            circle_option(cx, cy, rx=24)

        # Fuel type
        fuel_type = data.get("fuel_type", "").upper()
        if fuel_type in FUEL_TYPE_CENTERS:
            cx, cy = FUEL_TYPE_CENTERS[fuel_type]
            rx = 45 if fuel_type == "LOGGING DEBRIS" else 26
            circle_option(cx, cy, rx=rx)

        # Firing technique
        firing = data.get("firing_technique", "").upper()
        if firing in FIRING_CENTERS:
            cx, cy = FIRING_CENTERS[firing]
            rx = 26 if firing == "BACKING" else 18
            circle_option(cx, cy, rx=rx)

        # ── X in YES / NO cost-shared box ─────────────────────────────────────
        cost = data.get("cost_shared", "No")
        if cost == "Yes":
            x_in_box(*YES_CENTER)
        else:
            x_in_box(*NO_CENTER)

        # ── Text fields ───────────────────────────────────────────────────────
        for f in make_fields(data):
            if f["page"] == 1:
                c.setFont(font_name, f.get("font", font_size))
                c.drawString(f["x"], f["y"], f["text"])

    elif page == 2:
        # ── X marks in checklist boxes ────────────────────────────────────────
        for key, (cx, cy) in zip(CHK_KEYS, CHK_CENTERS):
            val = data.get(key, False)
            if val is True or str(val).lower() in ("true", "1", "yes"):
                x_in_box(cx, cy, size=5)

        # ── Text fields ───────────────────────────────────────────────────────
        for f in make_fields(data):
            if f["page"] == 2:
                c.setFont(font_name, f.get("font", font_size))
                c.drawString(f["x"], f["y"], f["text"])


def fill_pdf(data: dict, output_path: str):
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "prescribed-burning-plan.pdf")
    if not os.path.exists(src):
        raise FileNotFoundError(f"Source PDF not found: {src}")
    reader = PdfReader(src)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    for page_num in (1, 2):
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(PDF_W, PDF_H))
        _draw_overlay(c, data, page_num)
        c.save()
        buf.seek(0)
        writer.pages[page_num - 1].merge_page(PdfReader(buf).pages[0])

    with open(output_path, "wb") as out:
        writer.write(out)


# ── Persistent defaults ───────────────────────────────────────────────────────
DEFAULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "burn_plan_defaults.json")

def load_saved_defaults(base: dict) -> dict:
    """Merge any user-saved overrides on top of the built-in base defaults."""
    if not os.path.exists(DEFAULTS_FILE):
        return base
    try:
        with open(DEFAULTS_FILE, "r") as f:
            saved = json.load(f)
        merged = {}
        for group, values in base.items():
            merged[group] = {**values, **saved.get(group, {})}
        return merged
    except Exception:
        return base

def save_defaults(defaults: dict):
    """Write the current defaults dict to disk."""
    try:
        with open(DEFAULTS_FILE, "w") as f:
            json.dump(defaults, f, indent=2)
    except Exception as e:
        print(f"Warning: could not save defaults: {e}")


# ── Default value sets ────────────────────────────────────────────────────────
_BASE_DEFAULTS = {
    "general": {
        "date_prepared":      date.today().strftime("%m/%d/%Y"),
        "landowner":          "GOVT",
        "phone":              "",
        "address":            "7487 Georgia Ave.",
        "city_state_zip":     "Fort Polk, LA",
        "acreage":            "",
        "city_state_zip":     "Louisiana, LA",
        "reason_for_burn":    "FUEL REDUCTION",
        "fuel_amount":        "MEDIUM",
        "fuel_type":          "GRASSES",
        "sect":               "",
        "twn":                "",
        "rng":                "",
        "lat":                "",
        "lon":                "",
        "cost_shared":        "No",
        "program_name":       "ITAM",
        "application_num":    "",
        "adj_landowners":     "Yes - notified verbally",
        "smoke_sensitive":    "None identified within smoke drift area",
        "special_precautions":"Monitor wind shifts; have suppression resources staged",
        "local_fire_dept":    "",
        "ldaf_office":        "",
        "one_call_locator":   "",
    },
    "weather": {
        "wind_speed":     "5-15 mph",
        "wind_dir":       "SW",
        "transport_wind": ">=8.8 mph",
        "mixing_height":  ">=1640 ft",
        "category_day":   "2 or higher",
        "rh":             "30-50%",
        "temp_max":       "",
        "temp_min":       "",
    },
    "firing": {
        "firing_technique":   "BACKING",
        "manpower_equipment": "1 Fire Boss, 2 crew, 1 water tender (500 gal), hand tools",
        "plan_prepared_by":   "",
        "fire_boss":          "",
    },
    "actual": {
        "actual_date":     date.today().strftime("%m/%d/%Y"),
        "actual_transport":">=8.8 mph",
        "actual_mixing":   ">=1640 ft",
        "actual_category": "2",
        "start_time":      "07:00",
        "end_time":        "14:00",
        "deadout_time":    "16:00",
        "remarks":         "Burn proceeded within prescription. No escapes.",
    },
    "checklist": {
        "checklist_date":    date.today().strftime("%m/%d/%Y"),
        "chk_plan_complete": True,
        "chk_adj_notified":  True,
        "chk_fire_auth":     True,
        "chk_smoke_map":     True,
        "chk_burn_map":      True,
        "chk_equipment":     True,
        "chk_signs":         True,
        "chk_test_burn":     True,
        "chk_briefing":      True,
        "chk_objectives":    True,
        "chk_map_disc":      True,
        "chk_hazards":       True,
        "chk_assignments":   True,
        "chk_ignition":      True,
        "chk_comms":         True,
        "chk_equip_loc":     True,
        "chk_assistance":    True,
        "chk_questions":     True,
        "checklist_completed_by":   "Roy Cloud",
        "burn_manager_name":        "Roy Cloud",
        "burn_manager_contact":     "318-447-4025",
    },
}

# Merge built-in defaults with any user-saved overrides from disk
DEFAULTS = load_saved_defaults(_BASE_DEFAULTS)


# ── GUI ───────────────────────────────────────────────────────────────────────
class BurnPlanApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CSU Prescribed Burning Plan Filler")
        self.resizable(True, True)
        self.configure(bg="#1e3a1e")
        self._apply_styles()
        self.vars = {}
        self._build_ui()

    def _apply_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TNotebook",        background="#1e3a1e", borderwidth=0)
        s.configure("TNotebook.Tab",    background="#2d5a2d", foreground="white",
                    padding=[10, 4],    font=("Helvetica", 10, "bold"))
        s.map("TNotebook.Tab",
              background=[("selected", "#4a7c4a")],
              foreground=[("selected", "white")])
        s.configure("TFrame",           background="#f5f0e8")
        s.configure("TLabel",           background="#f5f0e8", font=("Helvetica", 9))
        s.configure("TEntry",           fieldbackground="white", font=("Helvetica", 9))
        s.configure("TCombobox",        fieldbackground="white", font=("Helvetica", 9))
        s.configure("Header.TLabel",    background="#2d5a2d", foreground="white",
                    font=("Helvetica", 10, "bold"), padding=4)
        s.configure("Green.TButton",    background="#4a7c4a", foreground="white",
                    font=("Helvetica", 10, "bold"), padding=6)
        s.configure("Orange.TButton",   background="#c06820", foreground="white",
                    font=("Helvetica", 10, "bold"), padding=6)
        s.configure("Default.TButton",  background="#5a6e8a", foreground="white",
                    font=("Helvetica", 9, "bold"), padding=4)

    # ── layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        banner = tk.Frame(self, bg="#1E4D2B", pady=10)
        banner.pack(fill="x")
        tk.Label(banner,
                 text="🔥 CSU Louisiana LDAF Prescribed Burning Plan",
                 bg="#1E4D2B", fg="white",
                 font=("Helvetica", 16, "bold")).pack()
        tk.Label(banner,
                 text="Complete all tabs — use Set Defaults on each tab to pre-fill common values",
                 bg="#1E4D2B", fg="#c8e6c8", font=("Helvetica", 9)).pack()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=8)
        self.tabs = {}
        for name in ["📋 General Info", "🌤 Weather Factors",
                     "🔥 Firing & Equipment", "📊 Actual Burn Eval", "✅ Checklist"]:
            frame = ttk.Frame(nb, padding=12)
            nb.add(frame, text=name)
            self.tabs[name] = frame

        self._tab_general()
        self._tab_weather()
        self._tab_firing()
        self._tab_actual()
        self._tab_checklist()

        # Bottom bar
        bar = tk.Frame(self, bg="#1e3a1e", pady=8)
        bar.pack(fill="x", side="bottom")
        ttk.Button(bar, text="💾  Export Filled PDF", style="Green.TButton",
                   command=self._export).pack(side="right", padx=12)

        # Font controls
        tk.Label(bar, text="PDF Font:", bg="#1e3a1e", fg="#c8e6c8",
                 font=("Helvetica", 9)).pack(side="right", padx=(12, 2))

        self.font_bold_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Bold",
                        variable=self.font_bold_var,
                        style="TCheckbutton"
                        ).pack(side="right", padx=(0, 6))

        self.font_size_var = tk.IntVar(value=9)
        tk.Label(bar, text="Size:", bg="#1e3a1e", fg="#c8e6c8",
                 font=("Helvetica", 9)).pack(side="right", padx=(0, 2))
        size_spin = tk.Spinbox(bar, from_=7, to=11, width=3,
                               textvariable=self.font_size_var,
                               font=("Helvetica", 9), relief="flat")
        size_spin.pack(side="right", padx=(0, 4))

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(bar, textvariable=self.status_var, bg="#1e3a1e", fg="#90ee90",
                 font=("Helvetica", 9, "italic")).pack(side="left", padx=12)

    # ── scrollable container ──────────────────────────────────────────────────
    def _scrollable(self, parent):
        canvas = tk.Canvas(parent, bg="#f5f0e8", highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(canvas)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        return inner

    # ── helpers ───────────────────────────────────────────────────────────────
    def _defaults_bar(self, parent, group_key):
        """A highlighted strip at the top of each tab with Set Defaults and Save as Defaults buttons."""
        bar = tk.Frame(parent, bg="#dde8dd", pady=5, padx=8)
        bar.pack(fill="x", pady=(0, 6))
        tk.Label(bar,
                 text="Quickly populate common values for this section:",
                 bg="#dde8dd", fg="#1e3a1e",
                 font=("Helvetica", 9, "italic")).pack(side="left", padx=(0, 10))
        ttk.Button(bar,
                   text="⚙  Get Defaults",
                   style="Default.TButton",
                   command=lambda k=group_key: self._apply_defaults(k)
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(bar,
                   text="💾  Save Current as Defaults",
                   style="Default.TButton",
                   command=lambda k=group_key: self._save_as_defaults(k)
                   ).pack(side="left")

    def _apply_defaults(self, group_key):
        for k, v in DEFAULTS.get(group_key, {}).items():
            if k in self.vars:
                try:
                    self.vars[k].set(v)
                except Exception:
                    pass
        self.status_var.set(f"Defaults applied to '{group_key}' tab  ✓")

    def _save_as_defaults(self, group_key):
        """Snapshot the current field values for this group and persist to disk."""
        group_defaults = DEFAULTS.get(group_key, {})
        updated = {}
        for k in group_defaults:
            if k in self.vars:
                try:
                    updated[k] = self.vars[k].get()
                except Exception:
                    updated[k] = group_defaults[k]
            else:
                updated[k] = group_defaults[k]
        DEFAULTS[group_key] = updated
        save_defaults(DEFAULTS)
        self.status_var.set(f"Defaults saved for '{group_key}' tab  ✓")

    def _section(self, parent, title):
        ttk.Label(parent, text=f"  {title}  ",
                  style="Header.TLabel").pack(fill="x", pady=(10, 4))

    def _field(self, parent, label, key, default="", width=40):
        var = tk.StringVar(value=default)
        self.vars[key] = var
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=2)
        ttk.Label(f, text=label, width=32, anchor="w").pack(side="left")
        ttk.Entry(f, textvariable=var, width=width).pack(
            side="left", fill="x", expand=True)
        return var

    def _radio_group(self, parent, label, key, options):
        var = tk.StringVar(value=options[0])
        self.vars[key] = var
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=2)
        ttk.Label(f, text=label, width=32, anchor="w").pack(side="left")
        for opt in options:
            ttk.Radiobutton(f, text=opt, variable=var,
                            value=opt).pack(side="left", padx=6)
        return var

    def _check(self, parent, label, key, default=False):
        var = tk.BooleanVar(value=default)
        self.vars[key] = var
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=1)
        ttk.Checkbutton(f, text=label, variable=var).pack(side="left", padx=4)
        return var

    # ── tab: General Info ─────────────────────────────────────────────────────
    def _tab_general(self):
        p = self.tabs["📋 General Info"]
        self._defaults_bar(p, "general")
        inner = self._scrollable(p)

        self._section(inner, "Basic Information")
        self._field(inner, "Date Prepared:", "date_prepared",
                    default=date.today().strftime("%m/%d/%Y"))
        self._field(inner, "Landowner Name:", "landowner")
        self._field(inner, "Phone # (w/ area code):", "phone")
        self._field(inner, "Address:", "address")
        self._field(inner, "City, State & ZIP:", "city_state_zip",
                    default="Louisiana, LA")

        self._section(inner, "Burn Description")
        self._field(inner, "Estimated Acreage to Burn:", "acreage")
        self._radio_group(inner, "Reason for Burn:", "reason_for_burn",
                          ["SITE PREP", "FUEL REDUCTION", "TSI", "WILDLIFE", "OTHER"])
        self._field(inner, "If OTHER, specify:", "reason_other")
        self._radio_group(inner, "Fuel Amount:", "fuel_amount",
                          ["LIGHT", "MEDIUM", "HEAVY"])
        self._radio_group(inner, "Fuel Type:", "fuel_type",
                          ["GRASSES", "BRUSH", "LOGGING DEBRIS", "OTHER"])
        self._field(inner, "If OTHER fuel, explain:", "fuel_type_other")

        self._section(inner, "Location")
        self._field(inner, "Section:", "sect", width=15)
        self._field(inner, "Township:", "twn", width=15)
        self._field(inner, "Range:", "rng", width=15)
        self._field(inner, "Latitude:", "lat")
        self._field(inner, "Longitude:", "lon")

        self._section(inner, "Cost-Share Program")
        self._radio_group(inner, "Cost-Shared?", "cost_shared", ["No", "Yes"])
        self._field(inner, "Program Name:", "program_name")
        self._field(inner, "Application #:", "application_num")

        self._section(inner, "Preburn Contacts & Notices")
        self._field(inner, "Smoke Sensitive Areas:", "smoke_sensitive")
        self._field(inner, "Special Precautions:", "special_precautions")
        self._field(inner, "Adjacent Landowners Notified:", "adj_landowners",
                    default="Yes - notified verbally")
        self._field(inner, "Local Fire Dept (name & phone):", "local_fire_dept")
        self._field(inner, "Local LDAF Forestry Office:", "ldaf_office")
        self._field(inner, "LA OneCall Locator #:", "one_call_locator")

    # ── tab: Weather Factors (DESIRED) ────────────────────────────────────────
    def _tab_weather(self):
        p = self.tabs["🌤 Weather Factors"]
        self._defaults_bar(p, "weather")
        inner = self._scrollable(p)

        self._section(inner, "DESIRED Weather Factors (pre-burn prescription)")
        tk.Label(inner,
                 text="Enter your target weather window for the planned burn date.\n"
                      "Visit weather.gov/fire for transport winds and mixing height data.",
                 bg="#f5f0e8", fg="#555", font=("Helvetica", 9, "italic"),
                 justify="left").pack(anchor="w", padx=4, pady=(0, 8))

        self._field(inner, "Surface Wind Speed:", "wind_speed",    default="5-15 mph")
        self._field(inner, "Surface Wind Direction:", "wind_dir",  default="SW")
        self._field(inner, "Transport Wind (speed & dir):", "transport_wind",
                    default=">=8.8 mph (verify at weather.gov/fire)")
        self._field(inner, "Mixing Height:", "mixing_height",
                    default=">=1640 ft (verify at weather.gov/fire)")
        self._field(inner, "Category Day:", "category_day",        default="2 or higher")
        self._field(inner, "Relative Humidity (%):", "rh",         default="30-50%")
        self._field(inner, "Temp Max (F):", "temp_max")
        self._field(inner, "Temp Min (F):", "temp_min")

    # ── tab: Firing & Equipment ───────────────────────────────────────────────
    def _tab_firing(self):
        p = self.tabs["🔥 Firing & Equipment"]
        self._defaults_bar(p, "firing")
        inner = self._scrollable(p)

        self._section(inner, "Firing Technique")
        self._radio_group(inner, "Technique:", "firing_technique",
                          ["HEAD", "FLANK", "BACKING", "OTHER"])
        self._field(inner, "If OTHER, specify:", "firing_other")

        self._section(inner, "Resources")
        self._field(inner, "Manpower & Equipment Needed:", "manpower_equipment", width=55)

        self._section(inner, "Plan Information")
        self._field(inner, "Plan Prepared By (name & phone):", "plan_prepared_by")
        self._field(inner, "Fire Boss (printed name):", "fire_boss")

    # ── tab: Actual Burn Evaluation ───────────────────────────────────────────
    def _tab_actual(self):
        p = self.tabs["📊 Actual Burn Eval"]
        self._defaults_bar(p, "actual")
        inner = self._scrollable(p)

        # ── Live weather fetch ────────────────────────────────────────────────
        self._section(inner, "Live Fire Weather — Fetch from NWS")

        region_row = ttk.Frame(inner)
        region_row.pack(fill="x", pady=2)
        ttk.Label(region_row, text="NWS Region:", width=32,
                  anchor="w").pack(side="left")
        self.region_var = tk.StringVar(value=list(NWS_POINTS.keys())[0])
        self.vars["region"] = self.region_var
        ttk.Combobox(region_row, textvariable=self.region_var,
                     values=list(NWS_POINTS.keys()),
                     state="readonly", width=42).pack(side="left")

        ttk.Button(inner,
                   text="🌐  Fetch Current Fire Weather",
                   style="Orange.TButton",
                   command=self._fetch_weather_thread
                   ).pack(anchor="w", pady=6)

        self.wx_status = tk.StringVar(
            value="Select your NWS region above, then click Fetch to auto-fill "
                  "actual conditions from the current hourly forecast.")
        tk.Label(inner, textvariable=self.wx_status,
                 bg="#f5f0e8", fg="#8b4513",
                 font=("Helvetica", 9, "italic"),
                 wraplength=560, justify="left").pack(anchor="w", pady=(0, 6))

        # ── Actual conditions ─────────────────────────────────────────────────
        self._section(inner, "Actual Burn Conditions")
        self._field(inner, "Date of Burn:", "actual_date",
                    default=date.today().strftime("%m/%d/%Y"))
        self._field(inner, "Surface Wind Speed:", "actual_wind_speed")
        self._field(inner, "Surface Wind Direction:", "actual_wind_dir")
        self._field(inner, "Transport Wind (speed & dir):", "actual_transport")
        self._field(inner, "Mixing Height:", "actual_mixing")
        self._field(inner, "Category Day:", "actual_category")
        self._field(inner, "Relative Humidity (%):", "actual_rh")
        self._field(inner, "Temp Max (F):", "actual_temp_max")
        self._field(inner, "Temp Min (F):", "actual_temp_min")

        self._section(inner, "Timing & Results")
        self._field(inner, "Starting Time (firing):", "start_time", default="09:00")
        self._field(inner, "Ending Time (firing):", "end_time",     default="14:00")
        self._field(inner, "Dead-Out Time:", "deadout_time",        default="16:00")
        self._field(inner, "Estimated Acreage Burned:", "actual_acreage")
        self._field(inner, "Remarks:", "remarks", width=55)

    # ── tab: Checklist ────────────────────────────────────────────────────────
    def _tab_checklist(self):
        p = self.tabs["✅ Checklist"]
        self._defaults_bar(p, "checklist")
        inner = self._scrollable(p)

        self._section(inner, "Burn Checklist (Page 2 — complete on-site, day of burn)")
        tk.Label(inner, text="Check each item to confirm compliance:",
                 bg="#f5f0e8", font=("Helvetica", 9, "italic"),
                 fg="#555").pack(anchor="w", pady=(0, 4))

        checks = [
            ("Page 1 of Plan completed and available on-site",   "chk_plan_complete"),
            ("Adjacent landowners notified of burn",             "chk_adj_notified"),
            ("Local Fire Authority contacted prior to ignition",  "chk_fire_auth"),
            ("Smoke Sensitive Areas identified (map attached)",   "chk_smoke_map"),
            ("Map of desired burn compartment attached",          "chk_burn_map"),
            ("All equipment and personnel on scene",              "chk_equipment"),
            ("'Smoke Ahead' or similar signs placed if needed",   "chk_signs"),
            ("Test burn performed; fire behavior within expectations", "chk_test_burn"),
            ("Crew briefing completed prior to firing",           "chk_briefing"),
            ("Objectives of burn discussed with crew",            "chk_objectives"),
            ("Map discussion — proposed burn area reviewed",      "chk_map_disc"),
            ("Hazards discussed (fuels, spotting, terrain)",      "chk_hazards"),
            ("Crew assignments made and reviewed",                "chk_assignments"),
            ("Ignition techniques and firing patterns reviewed",  "chk_ignition"),
            ("Authority and communications issues reviewed",      "chk_comms"),
            ("Location of on-site equipment shared with crew",    "chk_equip_loc"),
            ("Sources of nearest assistance shared (phone #s)",   "chk_assistance"),
            ("Crew questions and suggestions answered",           "chk_questions"),
        ]
        for label, key in checks:
            self._check(inner, label, key)

        self._section(inner, "Burn Manager Info (Page 2)")
        self._field(inner, "Checklist Completed By:", "checklist_completed_by")
        self._field(inner, "Burn Manager Name:", "burn_manager_name")
        self._field(inner, "Burn Manager Contact #:", "burn_manager_contact")
        self._field(inner, "Date:", "checklist_date",
                    default=date.today().strftime("%m/%d/%Y"))

    # ── weather fetch ─────────────────────────────────────────────────────────
    def _fetch_weather_thread(self):
        self.status_var.set("Fetching weather data from NWS…")
        self.wx_status.set("Connecting to api.weather.gov…")
        threading.Thread(target=self._fetch_weather, daemon=True).start()

    def _fetch_weather(self):
        region = self.region_var.get()
        result = fetch_nws_forecast(region)

        if "_error" in result:
            err = result["_error"]
            self.after(0, lambda: self.wx_status.set(
                f"Could not reach NWS API: {err}\n"
                "Check your internet connection or enter values manually."))
            self.after(0, lambda: self.status_var.set("Weather fetch failed."))
            return

        def _apply():
            mapping = {
                "actual_wind_speed": result.get("wind_speed", ""),
                "actual_wind_dir":   result.get("wind_dir", ""),
                "actual_rh":         result.get("rh", ""),
                "actual_temp_max":   result.get("temp_max", ""),
                "actual_temp_min":   result.get("temp_min", ""),
                "actual_transport":  result.get("transport_wind", ""),
                "actual_mixing":     result.get("mixing_height", ""),
                "actual_category":   result.get("category_day", ""),
            }
            for k, v in mapping.items():
                if v and k in self.vars:
                    self.vars[k].set(v)
            self.wx_status.set(
                f"Conditions loaded for {region}.  "
                "Transport wind and mixing height are estimated — verify the dedicated "
                "fire weather forecast at weather.gov/fire before burning.")
            self.status_var.set("Weather data applied to Actual Burn Eval  ✓")

        self.after(0, _apply)

    # ── export ────────────────────────────────────────────────────────────────
    def _export(self):
        out = filedialog.asksaveasfilename(
            title="Save Filled PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile="prescribed_burn_plan_filled.pdf",
        )
        if not out:
            return
        try:
            data = {k: (v.get() if hasattr(v, "get") else "")
                    for k, v in self.vars.items()}
            # Inject font settings
            size = self.font_size_var.get()
            bold = self.font_bold_var.get()
            data["_font_size"] = size
            data["_font_name"] = "Helvetica-Bold" if bold else "Helvetica"
            fill_pdf(data, out)
            self.status_var.set(f"Saved  →  {os.path.basename(out)}  ✓")
            messagebox.showinfo("Success", f"PDF saved to:\n{out}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status_var.set("Export failed.")


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src = resource_path("prescribed-burning-plan.pdf")
    if not os.path.exists(src):
        print(f"Source PDF not found at {src}")
        print("Place 'prescribed-burning-plan.pdf' in the same folder as this script.")
        sys.exit(1)
    app = BurnPlanApp()
    app.mainloop()
