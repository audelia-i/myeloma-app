import streamlit as st
import json
import math
from datetime import date, timedelta
from lab_extractor import extract_lab_values
import gspread
from google.oauth2.service_account import Credentials

SHEET_NAME = "myeloma-app.data"
SHEET_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def _save_to_sheet(patient: dict, eligible: list, maybe: list):
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SHEET_SCOPES)
        gc = gspread.authorize(creds)
        sh = gc.open(SHEET_NAME).sheet1

        # כותרות — רק אם הגיליון ריק
        if sh.row_count == 0 or not sh.row_values(1):
            sh.append_row([
                "תאריך", "גיל", "מין", "סיווג מחלה", "ECOG",
                "קווי טיפול", "מועמד להשתלה", "עבר השתלה",
                "מחקרים מתאימים", "מחקרים לבדיקה"
            ])

        eligible_titles = " | ".join(e["title"][:40] for e in eligible)
        maybe_titles    = " | ".join(e["title"][:40] for e in maybe)

        sh.append_row([
            date.today().strftime("%d/%m/%Y"),
            patient.get("age", ""),
            patient.get("gender", ""),
            patient.get("disease_class", ""),
            patient.get("ecog", ""),
            patient.get("lot_count", ""),
            patient.get("asct_candidate", ""),
            patient.get("asct_done", ""),
            eligible_titles,
            maybe_titles,
        ])
        return True
    except Exception as e:
        return str(e)


st.set_page_config(
    page_title="התאמת מחקרים קליניים — מיאלומה נפוצה",
    page_icon="🔬",
    layout="centered"
)

def load_css():
    with open("style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# ── עיצוב RTL ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        direction: rtl; text-align: right;
    }
    .stSelectbox, .stMultiSelect, .stNumberInput, .stDateInput,
    .stRadio, .stCheckbox, .stTextInput, .stTextArea, .stFileUploader,
    .stTabs, .stTab, .stMetric, .stAlert, .stExpander, p, li, span, div {
        direction: rtl; text-align: right;
    }
    .stSelectbox label, .stMultiSelect label, .stNumberInput label,
    .stDateInput label, .stRadio label, .stCheckbox label { direction: rtl; }
    .stDateInput input { direction: rtl; text-align: right; }
    .stRadio > div { flex-direction: column; }
    h1, h2, h3, h4, h5, h6 { direction: rtl; text-align: right; }
    [data-testid="stSidebar"] { direction: rtl; }
    /* לשוניות RTL */
    .stTabs [data-baseweb="tab-list"] {
        flex-direction: row-reverse !important;
        justify-content: flex-end !important;
    }
    .stTabs [data-baseweb="tab"] { direction: rtl !important; }

    /* שדות תאריך RTL */
    [data-testid="stDateInput"] input {
        direction: rtl !important;
        text-align: right !important;
    }
    [data-testid="stDateInput"] > div > div {
        flex-direction: row-reverse !important;
    }

    /* צ'קבוקס - יישור */
    .stCheckbox { text-align: right !important; direction: rtl !important; }
    .stCheckbox label { flex-direction: row-reverse !important; gap: 8px !important; }
    /* ── רקע ── */
    [data-testid="stAppViewContainer"] { background-color: #eef1f7 !important; }
    section[data-testid="stMain"] > div:first-child {
        background-color: #ffffff !important;
        border-radius: 14px !important;
        padding: 2rem 2.5rem !important;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08) !important;
        margin-top: 1rem !important;
    }

    /* ── כותרות ── */
    h1 { color: #1a3567 !important; font-size: 1.9rem !important; font-weight: 700 !important; }
    h2 { color: #1a3567 !important; font-size: 1.2rem !important; font-weight: 600 !important;
         border-bottom: 2px solid #d4e1f7 !important;
         padding-bottom: 5px !important; margin-top: 1.8rem !important; }
    h3 { color: #1e5799 !important; font-size: 1rem !important; font-weight: 600 !important; }

    /* ── כפתורים ── */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        border: 1.5px solid #1a3567 !important;
        color: #1a3567 !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        background-color: #1a3567 !important;
        color: white !important;
    }
    [data-testid="baseButton-primary"] {
        background-color: #1a3567 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
    }
    [data-testid="baseButton-primary"]:hover { background-color: #1e5799 !important; }

    /* ── Metric cards ── */
    [data-testid="stMetric"] {
        background-color: #f0f5ff !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        border: 1px solid #c5d8f5 !important;
    }
    [data-testid="stMetricLabel"] { color: #1a3567 !important; font-weight: 600 !important; }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-highlight"] { background-color: #1a3567 !important; }
    .stTabs [aria-selected="true"] { color: #1a3567 !important; font-weight: 700 !important; }

    /* ── תיבות ── */
    .warning-box {
        background-color: #fff8e6; border: 1px solid #f0c040;
        border-right: 4px solid #f0c040; border-radius: 6px;
        padding: 10px 14px; margin: 10px 0;
    }
    .error-box {
        background-color: #fff0f0; border: 1px solid #e06060;
        border-right: 4px solid #e06060; border-radius: 6px;
        padding: 10px 14px; margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ── נתוני מחקרים ────────────────────────────────────────────────────────────
@st.cache_data
def load_trials():
    try:
        with open("myeloma_trials_structured.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

trials = load_trials()

# ── אתחול session_state לערכי מעבדה ─────────────────────────────────────────
LAB_FIELDS = ["hb", "plt", "anc", "creatinine",
              "ast", "alt", "bilirubin",
              "m_protein_serum", "m_protein_urine", "kappa_flc", "lambda_flc"]

for f in LAB_FIELDS:
    if f"lab_{f}" not in st.session_state:
        st.session_state[f"lab_{f}"] = None

# ── חישוב eGFR (CKD-EPI 2021) ───────────────────────────────────────────────
def calc_egfr(creatinine, age, gender):
    if not creatinine or not age:
        return None
    kappa = 0.7 if gender == "נקבה" else 0.9
    alpha = -0.241 if gender == "נקבה" else -0.302
    sex_factor = 1.012 if gender == "נקבה" else 1.0
    ratio = creatinine / kappa
    if ratio < 1:
        egfr = 142 * (ratio ** alpha) * (0.9938 ** age) * sex_factor
    else:
        egfr = 142 * (ratio ** -1.200) * (0.9938 ** age) * sex_factor
    return round(egfr, 1)

# ── כותרת ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 1.5rem 0 0.5rem;">
  <svg width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
    <!-- תא פלסמה מסוגנן — ייצוג מיאלומה -->
    <circle cx="36" cy="36" r="34" fill="#eef4ff" stroke="#1a3567" stroke-width="2"/>
    <!-- גרעין -->
    <circle cx="36" cy="36" r="16" fill="#1a3567" opacity="0.15"/>
    <circle cx="36" cy="36" r="10" fill="#1a3567" opacity="0.35"/>
    <circle cx="36" cy="36" r="5"  fill="#1a3567"/>
    <!-- נקודות מייצגות תאים בסביבה -->
    <circle cx="14" cy="24" r="4.5" fill="#1e5799" opacity="0.7"/>
    <circle cx="58" cy="24" r="4.5" fill="#1e5799" opacity="0.7"/>
    <circle cx="14" cy="48" r="4.5" fill="#1e5799" opacity="0.7"/>
    <circle cx="58" cy="48" r="4.5" fill="#1e5799" opacity="0.7"/>
    <circle cx="36" cy="10" r="4.5" fill="#1e5799" opacity="0.7"/>
    <circle cx="36" cy="62" r="4.5" fill="#1e5799" opacity="0.7"/>
    <!-- קווי חיבור -->
    <line x1="36" y1="26" x2="36" y2="14" stroke="#1a3567" stroke-width="1" opacity="0.4"/>
    <line x1="36" y1="46" x2="36" y2="58" stroke="#1a3567" stroke-width="1" opacity="0.4"/>
    <line x1="26" y1="36" x2="18" y2="26" stroke="#1a3567" stroke-width="1" opacity="0.4"/>
    <line x1="46" y1="36" x2="54" y2="26" stroke="#1a3567" stroke-width="1" opacity="0.4"/>
    <line x1="26" y1="36" x2="18" y2="46" stroke="#1a3567" stroke-width="1" opacity="0.4"/>
    <line x1="46" y1="36" x2="54" y2="46" stroke="#1a3567" stroke-width="1" opacity="0.4"/>
  </svg>
  <div style="margin-top:0.8rem;">
    <span style="font-size:1.8rem; font-weight:700; color:#1a3567;">התאמת מחקרים קליניים</span><br>
    <span style="font-size:1rem; color:#5a7ab5; font-weight:500; letter-spacing:0.03em;">מיאלומה נפוצה · Multiple Myeloma</span>
  </div>
</div>
<hr style="border:none; border-top:1px solid #d4e1f7; margin:1rem 0 1.5rem;">
""", unsafe_allow_html=True)
st.caption("כלי זה הינו כלי עזר בלבד ואינו מחליף ייעוץ רפואי. אין להעלות פרטים מזהים כגון שם, ת.ז, טלפון וכו'.")
st.divider()

# ════════════════════════════════════════════════════════════════════════════
# חלק א — פרטי בסיס
# ════════════════════════════════════════════════════════════════════════════
st.header("א — פרטי בסיס")

col1, col2 = st.columns(2)
with col1:
    age = st.number_input("גיל המטופל", min_value=18, max_value=120, step=1, value=None,
                          placeholder="גיל בשנים")
with col2:
    gender = st.selectbox("מין", ["", "זכר", "נקבה"])

disease_class = st.selectbox("סיווג המחלה", [
    "",
    "אבחנה חדשה — מיאלומה פעילה, טרם טיפול",
    "אבחנה לאחרונה עם מיאלומה זוחלת המצריכה טיפול (smoldering)",
    "תחת טיפול — מועמד להשתלה עצמית / לאחר השתלה לאחרונה",
    "הישנות / מחלה עמידה — דורשת טיפול",
    "בתגובה לטיפול — מחפש מחקר תחזוקה / העמקת תגובה"
])

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# חלק ב — סטטוס מחלה
# ════════════════════════════════════════════════════════════════════════════
st.header("ב — סטטוס מחלה")

# B1 — אישור הישנות (רק אם הישנות)
relapse_confirmation = []
if disease_class == "הישנות / מחלה עמידה — דורשת טיפול":
    relapse_confirmation = st.multiselect(
        "כיצד אושרה ההישנות?",
        ["בדיקות מעבדה", "ביופסיית מח עצם", "הדמיה (CT / PET-CT / MRI)"]
    )

# B2 — טיפול קודם
prior_treatment = None
if disease_class and disease_class != "אבחנה חדשה — מיאלומה פעילה, טרם טיפול":
    prior_treatment = st.radio(
        "האם המטופל קיבל טיפול כלשהו למיאלומה בעבר?",
        ["כן", "לא"], horizontal=True, index=None
    )

# B3 — מועמדות להשתלה
asct_candidate = st.selectbox("האם המטופל מועמד להשתלת מח עצם עצמית?",
                               ["", "כן", "לא", "לא ידוע"])

# B4+B5 — האם בוצעה השתלה
asct_done = st.radio("האם בוצעה השתלה עצמית בעבר?",
                     ["כן", "לא"], horizontal=True, index=None)

asct_date = None
if asct_done == "כן":
    asct_date = st.date_input(
        "תאריך ביצוע ההשתלה",
        max_value=date.today(),
        value=None
    )

# B6 — מחלה חוץ-מדולרית
extramedullary = st.selectbox(
    "האם יש מחלה חוץ-מדולרית (>2 ס\"מ)?",
    ["", "כן", "לא", "לא ידוע"]
)

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# חלק ג — תפקוד ותחלואה נלווית
# ════════════════════════════════════════════════════════════════════════════
st.header("ג — תפקוד ותחלואה נלווית")

ecog = st.selectbox("מהי רמת התפקוד היומיומי?", [
    "",
    "0 — יכול לבצע את כל הפעולות היומיומיות כרגיל",
    "1 — יכול לבצע פעילויות קלות, אך לא פעילויות פיזיות מאומצות",
    "2 — יכול לבצע פעילויות יומיומיות, אך לא יכול לעבוד",
    "3 — יכול לבצע רק חלק מהפעילויות היומיומיות, מבלה זמן ממושך במיטה או על כסא",
    "4 — אינו יכול לבצע כל פעילות לבד, מבלה כל הזמן במיטה או על כסא",
])

active_conditions = st.multiselect(
    "מצבים רפואיים פעילים (ניתן לסמן יותר מאחד)",
    [
        "זיהום פעיל",
        "ממאירות פעילה נוספת",
        "אירוע לב איסכמי ב-6 חודשים האחרונים",
        "מחלה אוטואימונית פעילה",
        "מצב רפואי אחר לא מאוזן",
        "אף אחד מהאמור"
    ]
)

hematologic_exclusions = st.multiselect(
    "הגדרות המטולוגיות (ניתן לסמן יותר מאחד)",
    [
        "לוקמיה של תאי פלסמה (Plasma Cell Leukemia)",
        "מחלת וולדנשטרום (Waldenström macroglobulinemia)",
        "עמילואידוזיס AL ראשוני (Light chain amyloidosis)",
        "תסמונת POEMS",
        "אף אחד מהאמור"
    ]
)

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# חלק ד — בדיקות מעבדה
# ════════════════════════════════════════════════════════════════════════════
st.header("ד — בדיקות מעבדה")
st.caption("כל הבדיקות חייבות להיות מ-42 הימים האחרונים. אין לכלול שם או ת\"ז בקובץ המועלה.")

lab_date = st.date_input(
    "תאריך הבדיקות",
    max_value=date.today(),
    value=None,
    format="DD/MM/YYYY"
)

# בדיקת תוקף הבדיקות
lab_date_warning = False
if lab_date:
    days_ago = (date.today() - lab_date).days
    if days_ago > 42:
        st.markdown(f'<div class="warning-box">⚠️ הבדיקות בנות {days_ago} ימים — ייתכן שההתאמה לא תהיה רלוונטית. מומלץ לבדיקות עדכניות.</div>', unsafe_allow_html=True)
        lab_date_warning = True

st.warning("⚠️ **שימו לב לפרטיות:** יש לוודא שהקובץ המועלה אינו מכיל שם מטופל, תעודת זהות או כל פרט מזהה אחר.")
lab_files = st.file_uploader(
    "העלאת קבצי בדיקות (JPG / PNG / PDF) — ניתן להעלות מספר קבצים",
    type=["jpg", "jpeg", "png", "pdf"],
    accept_multiple_files=True
)

if lab_files:
    st.info(f"📎 הועלו {len(lab_files)} קבצים")
    _api_key = st.secrets.get("ANTHROPIC_API_KEY", "")

    if st.button("חלץ ערכים", type="primary", use_container_width=True):
        if not _api_key:
            st.error("מפתח API לא מוגדר — פנה למנהל המערכת")
        else:
            merged = {}
            total_images = 0
            any_error = False

            for lab_file in lab_files:
                status_ph = st.empty()
                status_ph.info(f"⏳ מעבד: **{lab_file.name}**...")
                file_bytes = lab_file.read()

                if lab_file.type == "application/pdf":
                    from lab_extractor import pdf_to_images
                    images = [(img, "image/png") for img in pdf_to_images(file_bytes)]
                else:
                    images = [(file_bytes, lab_file.type)]

                file_notes = []
                file_errors = []
                before = len(merged)

                for img_bytes, mime in images:
                    total_images += 1
                    result = extract_lab_values(img_bytes, _api_key, mime)
                    if result["success"]:
                        for f in LAB_FIELDS:
                            if result.get(f) is not None and f not in merged:
                                merged[f] = float(result[f])
                        if result.get("notes"):
                            file_notes.append(result["notes"])
                    else:
                        file_errors.append(result["error"])

                found = len(merged) - before
                status_ph.empty()

                if file_errors:
                    any_error = True
                    for err in file_errors:
                        st.error(f"❌ **{lab_file.name}**: {err}")
                elif found == 0:
                    st.warning(f"⚠️ **{lab_file.name}**: לא זוהו ערכים בקובץ זה")
                else:
                    notes_str = f" · {' | '.join(file_notes)}" if file_notes else ""
                    st.success(f"✅ **{lab_file.name}**: נמצאו {found} ערכים{notes_str}")

            for f, val in merged.items():
                st.session_state[f"lab_{f}"] = val

            if merged:
                st.info(f"**סה״כ {len(merged)} ערכים מולאו אוטומטית בטופס למטה ↓**")

st.subheader("ספירת דם (CBC)")
col1, col2, col3 = st.columns(3)
with col1:
    hb = st.number_input("המוגלובין — Hb (g/dL)", min_value=0.0, max_value=20.0,
                         value=st.session_state.lab_hb, step=0.1, placeholder="g/dL", key="lab_hb")
with col2:
    plt_val = st.number_input("טסיות — PLT (×10⁹/L)", min_value=0.0, max_value=1000.0,
                              value=st.session_state.lab_plt, step=1.0, placeholder="×10⁹/L", key="lab_plt")
with col3:
    anc = st.number_input("נויטרופילים — ANC (×10⁹/L)", min_value=0.0, max_value=20.0,
                          value=st.session_state.lab_anc, step=0.1, placeholder="×10⁹/L", key="lab_anc")

st.subheader("כימיה")
creatinine = st.number_input("קריאטינין (mg/dL)", min_value=0.1, max_value=15.0,
                             value=st.session_state.lab_creatinine, step=0.1, placeholder="mg/dL", key="lab_creatinine")

# eGFR אוטומטי
egfr = None
if creatinine and age and gender and gender != "":
    egfr = calc_egfr(creatinine, age, gender)
    color = "green" if egfr >= 30 else "red"
    st.markdown(f"**eGFR מחושב (CKD-EPI 2021): <span style='color:{color}'>{egfr} mL/min/1.73m²</span>**",
                unsafe_allow_html=True)

st.subheader("תפקודי כבד")
col1, col2, col3 = st.columns(3)
with col1:
    ast = st.number_input("AST (IU/L)", min_value=0.0, max_value=500.0,
                          value=st.session_state.lab_ast, step=1.0, placeholder="IU/L", key="lab_ast")
with col2:
    alt = st.number_input("ALT (IU/L)", min_value=0.0, max_value=500.0,
                          value=st.session_state.lab_alt, step=1.0, placeholder="IU/L", key="lab_alt")
with col3:
    bilirubin = st.number_input("בילירובין כולל (mg/dL)", min_value=0.0, max_value=20.0,
                                value=st.session_state.lab_bilirubin, step=0.1, placeholder="mg/dL", key="lab_bilirubin")

st.subheader("פרופיל מיאלומה")
col1, col2 = st.columns(2)
with col1:
    m_protein_serum = st.number_input("M-protein בסרום / SPEP (g/dL)",
                                      min_value=0.0, max_value=10.0,
                                      value=st.session_state.lab_m_protein_serum,
                                      step=0.01, placeholder="g/dL — לא %", key="lab_m_protein_serum")
    st.caption("⚠️ אין להזין ערך באחוזים")
    kappa_flc = st.number_input("Free Light Chain — Kappa (mg/L)",
                                min_value=0.0, max_value=5000.0,
                                value=st.session_state.lab_kappa_flc,
                                step=0.1, placeholder="mg/L", key="lab_kappa_flc")
with col2:
    m_protein_urine = st.number_input("M-protein בשתן 24 שעות / UPEP (mg/24h)",
                                      min_value=0.0, max_value=50000.0,
                                      value=st.session_state.lab_m_protein_urine,
                                      step=1.0, placeholder="mg/24h (אופציונלי)", key="lab_m_protein_urine")
    lambda_flc = st.number_input("Free Light Chain — Lambda (mg/L)",
                                 min_value=0.0, max_value=5000.0,
                                 value=st.session_state.lab_lambda_flc,
                                 step=0.1, placeholder="mg/L", key="lab_lambda_flc")

# יחס FLC אוטומטי
flc_ratio = None
if kappa_flc and lambda_flc and lambda_flc > 0:
    flc_ratio = round(kappa_flc / lambda_flc, 2)
    ratio_normal = 0.26 <= flc_ratio <= 1.65
    ratio_color = "green" if ratio_normal else "orange"
    st.markdown(f"**יחס Kappa/Lambda: <span style='color:{ratio_color}'>{flc_ratio}</span>** {'(תקין)' if ratio_normal else '(חריג)'}",
                unsafe_allow_html=True)

# מחלה מדידה
measurable = False
if m_protein_serum and m_protein_serum >= 0.5:
    measurable = True
if m_protein_urine and m_protein_urine >= 200:
    measurable = True
if kappa_flc and lambda_flc and flc_ratio:
    involved_flc = max(kappa_flc, lambda_flc)
    if involved_flc >= 100 and not (0.26 <= flc_ratio <= 1.65):
        measurable = True

if m_protein_serum or kappa_flc or lambda_flc:
    status = "✅ מחלה מדידה" if measurable else "⚠️ מחלה לא מדידה לפי הנתונים שהוזנו"
    st.info(f"**{status}**")

st.subheader("ציטוגנטיקה")
t11_14 = st.selectbox("t(11;14) — FISH", ["", "חיובי", "שלילי", "לא בוצע"])

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# מסד נתוני תרופות
# ════════════════════════════════════════════════════════════════════════════
ALL_DRUGS_DB = {
    # name: (trade_name, drug_class)
    "Bortezomib":                        ("Velcade",          "PI"),
    "Carfilzomib":                       ("Kyprolis",         "PI"),
    "Ixazomib":                          ("Ninlaro",          "PI"),
    "Lenalidomide":                      ("Revlimid",         "IMiD"),
    "Thalidomide":                       ("Thalidomide",      "IMiD"),
    "Pomalidomide":                      ("Imnovid/Pomalyst", "IMiD"),
    "Mezigdomide":                       ("CC-92480",         "CELMoD"),
    "Iberdomide":                        ("CC-220",           "CELMoD"),
    "Daratumumab":                       ("Darzalex",         "anti-CD38"),
    "Isatuximab":                        ("Sarclisa",         "anti-CD38"),
    "Elotuzumab":                        ("Empliciti",        "anti-SLAMF7"),
    "Belantamab mafodotin":              ("Belamaf/Blenrep",  "ADC-BCMA"),
    "Teclistamab":                       ("Tecvayli",         "bispecific-BCMA"),
    "Elranatamab":                       ("Elrexfio",         "bispecific-BCMA"),
    "Cevostamab":                        ("—",               "bispecific-FcRH5"),
    "Talquetamab":                       ("Talvey",           "bispecific-GPRC5D"),
    "JNJ-76395322":                      ("—",               "trispecific"),
    "Ciltacabtagene autoleucel (CAR-T)": ("Carvykti",         "CAR-T-BCMA"),
    "Idecabtagene vicleucel (CAR-T)":    ("Abecma",           "CAR-T-BCMA"),
    "Arlocel (CAR-T)":                   ("—",               "CAR-T-GPRC5D"),
    "HBI101 (CAR-T)":                    ("—",               "CAR-T-BCMA"),
    "Selinexor":                         ("Xpovio",           "XPO1"),
    "Venetoclax":                        ("Venclexta",        "BCL-2"),
    "Cyclophosphamide":                  ("Endoxan",          "alkylating"),
    "Melphalan":                         ("Alkeran",          "alkylating"),
    "Melflufen":                         ("Melflufen",        "alkylating"),
    "Chemotherapy IV":                   ("כמותרפיה IV",       "Chemo"),
}

# אותו סוג → אפשר לחשב עמידות קבוצתית
DRUG_CLASS_GROUPS = {
    "PI":               ["Bortezomib", "Carfilzomib", "Ixazomib"],
    "IMiD":             ["Lenalidomide", "Thalidomide", "Pomalidomide"],
    "CELMoD":           ["Mezigdomide", "Iberdomide"],
    "anti-CD38":        ["Daratumumab", "Isatuximab"],
    "BCMA-directed":    ["Teclistamab", "Elranatamab", "Cevostamab",
                         "Belantamab mafodotin",
                         "Ciltacabtagene autoleucel (CAR-T)",
                         "Idecabtagene vicleucel (CAR-T)", "HBI101 (CAR-T)"],
    "GPRC5D-directed":  ["Talquetamab", "Arlocel (CAR-T)"],
}

CART_DRUGS = {
    "Ciltacabtagene autoleucel (CAR-T)", "Idecabtagene vicleucel (CAR-T)",
    "Arlocel (CAR-T)", "HBI101 (CAR-T)"
}

# ── מנוע התאמה למחקרים ───────────────────────────────────────────────────────

# מיפוי שם קבוצה בקריטריוני מחקר → שם קבוצה בבסיס הנתונים
_TRIAL_CLASS_MAP = {
    "PI":        "PI",
    "IMiD":      "IMiD",
    "CELMoD":    "CELMoD",
    "anti-CD38": "anti-CD38",
    "BCMA":      "BCMA-directed",
    "GPRC5D":    "GPRC5D-directed",
}

def _drugs_for_class(trial_class: str) -> list:
    app_class = _TRIAL_CLASS_MAP.get(trial_class, trial_class)
    return DRUG_CLASS_GROUPS.get(app_class, [])

def _map_disease(disease_class: str) -> str:
    if not disease_class:
        return ""
    if "אבחנה חדשה" in disease_class:
        return "NDMM"
    if "זוחלת" in disease_class or "smoldering" in disease_class.lower():
        return "SMM"
    if "הישנות" in disease_class or "עמידה" in disease_class:
        return "RRMM"
    if "תחת טיפול" in disease_class:
        return "NDMM"
    if "בתגובה" in disease_class:
        return "RRMM"
    return ""

def _ecog_num(ecog_str: str):
    if not ecog_str:
        return None
    for d in "01234":
        if ecog_str.startswith(d):
            return int(d)
    return None

ULN_BILI  = 1.2   # mg/dL
ULN_LIVER = 40.0  # IU/L

def _match_trial(trial: dict, patient: dict):
    """
    מחזיר (status, fails, warns):
      status: "eligible" | "maybe" | "ineligible"
    """
    e = trial.get("eligibility", {})
    if "error" in e:
        return "maybe", [], ["לא ניתן לנתח קריטריוני כניסה"]

    fails, warns = [], []
    labs       = patient.get("labs", {})
    drug_ref   = patient.get("refractory_status", {})
    heme_excl  = patient.get("hematologic_exclusions", [])
    act_cond   = patient.get("active_conditions", [])
    lot        = patient.get("lot_count", 0)

    # 0. גיל
    pt_age = patient.get("age")
    min_age = e.get("min_age")
    max_age = e.get("max_age")
    if pt_age and min_age is not None and pt_age < min_age:
        fails.append(f"גיל: נדרש לפחות {min_age}, המטופל בן {pt_age}")
    if pt_age and max_age is not None and pt_age > max_age:
        fails.append(f"גיל: מקסימום {max_age}, המטופל בן {pt_age}")

    # 1. סטטוס מחלה
    trial_ds = e.get("disease_status", [])
    if trial_ds:
        pt_ds = _map_disease(patient.get("disease_class", ""))
        if pt_ds and pt_ds not in trial_ds:
            fails.append(f"סטטוס מחלה: נדרש {'/'.join(trial_ds)}, המטופל: {pt_ds}")
        elif not pt_ds:
            warns.append("לא ניתן לאמת התאמת סטטוס מחלה")

    # 2. קווי טיפול
    min_lot = e.get("min_lot")
    max_lot = e.get("max_lot")
    if min_lot is not None and lot < min_lot:
        fails.append(f"קווי טיפול: נדרש לפחות {min_lot}, למטופל {lot}")
    if max_lot is not None and lot > max_lot:
        fails.append(f"קווי טיפול: מקסימום {max_lot}, למטופל {lot}")

    # 3. ECOG
    max_ecog  = e.get("max_ecog")
    pt_ecog   = _ecog_num(patient.get("ecog", ""))
    if max_ecog is not None:
        if pt_ecog is not None and pt_ecog > max_ecog:
            fails.append(f"ECOG: מקסימום {max_ecog}, למטופל ECOG {pt_ecog}")
        elif pt_ecog is None:
            warns.append("ECOG לא צוין — לא ניתן לאמת")

    # 4. עמידויות נדרשות
    for cls in e.get("required_refractory_classes", []):
        drugs = _drugs_for_class(cls)
        is_ref = any(drug_ref.get(d, {}).get("refractory", False) for d in drugs)
        if not is_ref:
            has_exp = any(d in drug_ref for d in drugs)
            if has_exp:
                fails.append(f"נדרש עמידות ל-{cls} — המטופל חשוף אך לא עמיד")
            else:
                fails.append(f"נדרש עמידות ל-{cls} — המטופל לא טופל בקבוצה זו")

    # 5. חשיפה נדרשת
    for cls in e.get("required_exposed_classes", []):
        drugs = _drugs_for_class(cls)
        if not any(d in drug_ref for d in drugs):
            fails.append(f"נדרש חשיפה ל-{cls} — המטופל לא טופל בקבוצה זו")

    # 6. הגבלות חשיפה קודמת
    if e.get("bcma_allowed") is False:
        if any(d in drug_ref for d in _drugs_for_class("BCMA")):
            fails.append("קיבל תרופה anti-BCMA בעבר — אסור במחקר זה")
    if e.get("gprc5d_allowed") is False:
        if any(d in drug_ref for d in _drugs_for_class("GPRC5D")):
            fails.append("קיבל תרופה anti-GPRC5D בעבר — אסור במחקר זה")
    if e.get("cd38_allowed") is False:
        if any(d in drug_ref for d in _drugs_for_class("anti-CD38")):
            fails.append("קיבל תרופה anti-CD38 בעבר — אסור במחקר זה")
    if e.get("cart_allowed") is False:
        if any(d in drug_ref for d in CART_DRUGS):
            fails.append("קיבל CAR-T בעבר — אסור במחקר זה")

    # 6b. תרופות מדירות ספציפיות
    excluded_drugs = e.get("excluded_prior_drugs", [])
    if excluded_drugs:
        patient_drugs_lower = {d.lower(): d for d in drug_ref}
        for excl in excluded_drugs:
            class_drugs = _drugs_for_class(excl)
            if class_drugs:
                if any(d in drug_ref for d in class_drugs):
                    fails.append(f"קיבל תרופה מקבוצת {excl} — תרופה מדירה במחקר זה")
            elif excl.lower() in patient_drugs_lower:
                orig = patient_drugs_lower[excl.lower()]
                fails.append(f"קיבל {orig} — תרופה מדירה במחקר זה")

    # 7. ערכי מעבדה
    checks = [
        ("min_hb",  "hb",  "Hb",      "g/dL",    "<"),
        ("min_plt", "plt", "טסיות",   "×10⁹/L",  "<"),
        ("min_anc", "anc", "ANC",      "×10⁹/L",  "<"),
        ("min_egfr","egfr","eGFR",     "mL/min",  "<"),
    ]
    for field, lab_key, label, unit, op in checks:
        threshold = e.get(field)
        val = labs.get(lab_key)
        if threshold is not None and val is not None and val < threshold:
            fails.append(f"{label} נמוך מדי: {val} {unit} (נדרש ≥{threshold})")

    max_bili = e.get("max_bilirubin_x_uln")
    if max_bili and labs.get("bilirubin") and labs["bilirubin"] > max_bili * ULN_BILI:
        fails.append(f"בילירובין גבוה: {labs['bilirubin']} mg/dL (מקסימום {max_bili}×ULN)")

    max_liver = e.get("max_ast_alt_x_uln")
    if max_liver:
        for key, lbl in [("ast", "AST"), ("alt", "ALT")]:
            v = labs.get(key)
            if v and v > max_liver * ULN_LIVER:
                fails.append(f"{lbl} גבוה: {v} IU/L (מקסימום {max_liver}×ULN)")

    # 8. מצבים רפואיים מדירים
    if e.get("excluded_if_amyloidosis") and any("עמילואידוזיס" in c for c in heme_excl):
        fails.append("עמילואידוזיס AL — מצב מדיר")
    if e.get("excluded_if_plasma_cell_leukemia") and any("לוקמיה" in c for c in heme_excl):
        fails.append("לוקמיה של תאי פלסמה — מצב מדיר")
    if e.get("excluded_if_poems") and any("POEMS" in c for c in heme_excl):
        fails.append("תסמונת POEMS — מצב מדיר")
    if e.get("excluded_if_waldenstrom") and any("וולדנשטרום" in c for c in heme_excl):
        fails.append("מחלת וולדנשטרום — מצב מדיר")
    if e.get("excluded_if_active_infection") and any("זיהום" in c for c in act_cond):
        fails.append("זיהום פעיל — מצב מדיר")
    if e.get("excluded_if_active_malignancy") and any("ממאירות" in c for c in act_cond):
        fails.append("ממאירות פעילה — מצב מדיר")
    if e.get("excluded_if_active_autoimmune") and any("אוטואימונית" in c for c in act_cond):
        fails.append("מחלה אוטואימונית פעילה — מצב מדיר")
    if e.get("excluded_if_recent_cardiac_event") and any("לב איסכמי" in c for c in act_cond):
        fails.append("אירוע לב איסכמי ב-6 חודשים האחרונים — מצב מדיר")

    # 9. מועמדות להשתלה עצמית
    asct_candidate = patient.get("asct_candidate", "")
    asct_done      = patient.get("asct_done", "לא")
    if e.get("excluded_if_asct_candidate") and asct_candidate == "כן":
        fails.append("מועמד להשתלה עצמית — מצב מדיר במחקר זה")
    if e.get("excluded_if_prior_asct") and asct_done == "כן":
        fails.append("בוצעה השתלה עצמית בעבר — מצב מדיר במחקר זה")
    if e.get("asct_required") and asct_done != "כן":
        fails.append("נדרשת השתלה עצמית קודמת — המטופל לא עבר השתלה")

    # 10. Washout
    min_washout = e.get("min_washout_days")
    days_since  = patient.get("days_since_last_treatment")
    if min_washout is not None:
        if days_since is None:
            warns.append(f"נדרש Washout של {min_washout} ימים — לא ניתן לאמת (אין תאריך סיום טיפול)")
        elif days_since < min_washout:
            fails.append(f"Washout קצר מדי: עברו {days_since} ימים, נדרש {min_washout} ימים")

    # 11. מחלה מדידה
    if e.get("measurable_disease_required") and not labs.get("measurable_disease"):
        warns.append("נדרשת מחלה מדידה — לא אושר בנתונים")

    if fails:
        return "ineligible", fails, warns
    elif warns:
        return "maybe", [], warns
    else:
        return "eligible", [], []

LINE_END_REASONS = [
    "תופעות לוואי",
    "התרופה הפסיקה לעבוד והמחלה התקדמה",
    "סיום תקופת הטיפול המתוכננת",
    "קושי בהשגת התרופה או בעיות אדמיניסטרטיביות",
    "אחר",
]

PROGRESSION_REASON = "התרופה הפסיקה לעבוד והמחלה התקדמה"

def drug_option(name):
    trade, cls = ALL_DRUGS_DB[name]
    return f"{name} ({trade})"

ALL_DRUG_OPTIONS = [drug_option(n) for n in ALL_DRUGS_DB]
LABEL_TO_DRUG   = {drug_option(n): n for n in ALL_DRUGS_DB}

# ════════════════════════════════════════════════════════════════════════════
# חלק ה — היסטוריית טיפולים (חישוב אוטומטי)
# ════════════════════════════════════════════════════════════════════════════
show_drug_section = (
    disease_class and
    disease_class != "אבחנה חדשה — מיאלומה פעילה, טרם טיפול" and
    prior_treatment == "כן"
)

# ── רשימות תרופות לפי קבוצה (מקביל לגליונות בקובץ תרופות.xlsx) ──────────────
DRUGS_GROUP1 = [
    "Bortezomib", "Carfilzomib", "Lenalidomide",
    "Thalidomide", "Pomalidomide", "Daratumumab",
]
DRUGS_GROUP2 = [
    "Ixazomib", "Isatuximab", "Belantamab mafodotin", "Elotuzumab",
    "Cyclophosphamide", "Melphalan", "Chemotherapy IV", "Melflufen",
    "Selinexor", "Teclistamab", "Elranatamab", "Talquetamab",
    "Ciltacabtagene autoleucel (CAR-T)", "Idecabtagene vicleucel (CAR-T)",
    "Venetoclax",
]
DRUGS_GROUP3 = [
    "Arlocel (CAR-T)", "HBI101 (CAR-T)",
    "Mezigdomide", "Iberdomide", "JNJ-76395322", "Cevostamab",
]

def _drug_key(name):
    """מפתח ייחודי לשימוש ב-session_state (ללא תווים מיוחדים)."""
    return name.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_").replace("/", "_")

# ── helper: הצגת שדות לתרופה אחת ─────────────────────────────────────────────
def _render_drug_fields(dk, drug_name, trade_name):
    """מציג שדות תאריך / עמידות לתרופה ומחזיר. dk = key prefix."""
    with st.container(border=True):
        st.markdown(f"**{drug_name}** · *{trade_name}*")

        if drug_name in CART_DRUGS:
            known = {"Ciltacabtagene autoleucel (CAR-T)": "BCMA",
                     "Idecabtagene vicleucel (CAR-T)": "BCMA"}.get(drug_name)
            if not known:
                st.selectbox("מטרה מולקולרית (CAR-T)", ["", "BCMA", "GPRC5D"],
                             key=f"dt_{dk}")

        col1, col2 = st.columns([3, 2])
        with col1:
            st.date_input("תאריך התחלה", key=f"ds_{dk}",
                          max_value=date.today(), value=None, format="DD/MM/YYYY")
        with col2:
            st.checkbox("נוטל כיום", key=f"do_{dk}")

        if not st.session_state.get(f"do_{dk}", False):
            col3, col4 = st.columns([3, 4])
            with col3:
                st.date_input("תאריך סיום", key=f"de_{dk}",
                              max_value=date.today(), value=None, format="DD/MM/YYYY")
            with col4:
                rv = st.selectbox("סיבת הפסקה", [""] + LINE_END_REASONS,
                                  key=f"dr_{dk}")
                if rv and rv != PROGRESSION_REASON:
                    st.radio("התקדמות תוך 60 יום?", ["כן", "לא", "לא ידוע"],
                             horizontal=True, key=f"dp_{dk}", index=None,
                             help="תרופה שהמחלה התקדמה תוך 60 יום ממנה = refractory")

            s_d = st.session_state.get(f"ds_{dk}")
            e_d = st.session_state.get(f"de_{dk}")
            if s_d and e_d and e_d < s_d:
                st.error("תאריך הסיום חייב להיות אחרי תאריך ההתחלה")

def _read_drug_entry(dk, drug_name):
    """קורא נתוני תרופה מה-session_state."""
    ongoing = st.session_state.get(f"do_{dk}", False)
    start   = st.session_state.get(f"ds_{dk}")
    end     = None if ongoing else st.session_state.get(f"de_{dk}")
    reason  = None if ongoing else (st.session_state.get(f"dr_{dk}") or None)
    p60     = st.session_state.get(f"dp_{dk}")
    cart_t  = st.session_state.get(f"dt_{dk}") or None
    return {
        "name": drug_name, "start_date": start, "end_date": end,
        "ongoing": ongoing, "stop_reason": reason,
        "progressed_within_60d": p60, "cart_target": cart_t,
    }

# ── חישוב אוטומטי של קווי טיפול ─────────────────────────────────────────────

def _compute_lot(entries):
    """
    מחשב קווי טיפול מרשימת תרופות.
    כלל מיזוג: פער ≤ 90 יום → אותו קו (אלא אם הקו הקודם הסתיים בהתקדמות).
    """
    today = date.today()
    valid = sorted(
        [e for e in entries if e.get("name") and e.get("start_date")],
        key=lambda e: e["start_date"]
    )
    if not valid:
        return []

    def ended_in_prog(group):
        return any(
            (e.get("stop_reason") == PROGRESSION_REASON or
             e.get("progressed_within_60d") == "כן")
            for e in group if not e.get("ongoing")
        )

    clusters, cur = [], [valid[0]]
    cur_end = valid[0].get("end_date") or today

    for e in valid[1:]:
        e_start = e["start_date"]
        e_end   = e.get("end_date") or today
        gap     = (e_start - cur_end).days
        if (ended_in_prog(cur) and gap > 0) or gap > 90:
            clusters.append(cur)
            cur, cur_end = [e], e_end
        else:
            cur.append(e)
            cur_end = max(cur_end, e_end)
    clusters.append(cur)

    lines = []
    for i, group in enumerate(clusters):
        is_ongoing = any(e.get("ongoing") for e in group)
        start = min(e["start_date"] for e in group)
        end   = None if is_ongoing else max(e.get("end_date") or today for e in group)
        lines.append({
            "line_number":          i + 1,
            "drugs":                [e["name"] for e in group],
            "start_date":           start,
            "end_date":             end,
            "ongoing":              is_ongoing,
            "ended_in_progression": ended_in_prog(group),
            "includes_asct":        (i == 0 and asct_done == "כן"),
        })
    return lines

def _compute_refractory(entries):
    """מחשב עמידות לפי כלל: התקדמות במהלך הטיפול או תוך 60 יום = refractory."""
    status = {}
    for e in entries:
        name = e.get("name")
        if not name:
            continue
        is_ref = (
            e.get("stop_reason") == PROGRESSION_REASON or
            e.get("progressed_within_60d") == "כן"
        )
        if name not in status:
            status[name] = {"refractory": False}
        if is_ref:
            status[name]["refractory"] = True
    return status

# ── ערכים ראשוניים ───────────────────────────────────────────────────────────
lines_of_therapy = []
drug_ref_status  = {}
valid_drugs      = []

# ── ממשק הזנת תרופות (מדורג) ─────────────────────────────────────────────────
if show_drug_section:
    st.header("ה — היסטוריית טיפולים")
    st.caption("סמן כל תרופה שהמטופל קיבל ומלא תאריכים. אין לכלול דקסמתזון / פרדניזון.")

    if asct_done == "כן":
        st.info("💡 הזן גם תרופות האינדוקציה וגם תחזוקה — המערכת תמזג אותן אוטומטית לקו 1.")

    all_drug_entries = []

    tab1, tab2, tab3 = st.tabs([
        "קבוצה 1 — עיקריות",
        "קבוצה 2 — נוספות",
        "קבוצה 3 — ניסיוניות",
    ])

    with tab1:
        for name in DRUGS_GROUP1:
            trade, _ = ALL_DRUGS_DB[name]
            dk = _drug_key(name)
            if st.checkbox(f"{name}  ({trade})", key=f"chk_{dk}"):
                _render_drug_fields(dk, name, trade)
                all_drug_entries.append(_read_drug_entry(dk, name))

    with tab2:
        for name in DRUGS_GROUP2:
            trade, _ = ALL_DRUGS_DB[name]
            dk = _drug_key(name)
            if st.checkbox(f"{name}  ({trade})", key=f"chk_{dk}"):
                _render_drug_fields(dk, name, trade)
                all_drug_entries.append(_read_drug_entry(dk, name))

    with tab3:
        for name in DRUGS_GROUP3:
            trade, _ = ALL_DRUGS_DB[name]
            dk = _drug_key(name)
            if st.checkbox(f"{name}  ({trade})", key=f"chk_{dk}"):
                _render_drug_fields(dk, name, trade)
                all_drug_entries.append(_read_drug_entry(dk, name))
        st.divider()
        st.caption("תרופה ניסיונית אחרת שאינה ברשימה:")
        custom = st.text_input("שם תרופה", key="l3_custom", placeholder="שם גנרי")
        if custom and custom.strip():
            _render_drug_fields("l3_other", custom.strip(), "ניסיוני")
            all_drug_entries.append(_read_drug_entry("l3_other", custom.strip()))

    # ── חישוב אוטומטי ─────────────────────────────────────────────────────────
    valid_drugs = [e for e in all_drug_entries if e.get("name")]

    if valid_drugs:
        lines_of_therapy = _compute_lot(valid_drugs)
        drug_ref_status  = _compute_refractory(valid_drugs)

        st.subheader("📊 קווי טיפול (חישוב אוטומטי)")
        for line in lines_of_therapy:
            drugs_str = " + ".join(line["drugs"])
            s_str     = line["start_date"].strftime("%m/%Y") if line["start_date"] else "?"
            e_str     = "נוכחי" if line["ongoing"] else (
                        line["end_date"].strftime("%m/%Y") if line["end_date"] else "?")
            badge     = ("✅ פעיל" if line["ongoing"]
                         else ("🔴 הסתיים בהתקדמות" if line["ended_in_progression"]
                               else "⚪ הסתיים"))
            asct_note = " · כולל ASCT" if line["includes_asct"] else ""
            st.markdown(
                f"**קו {line['line_number']}:** {drugs_str}{asct_note}  \n"
                f"📅 {s_str} → {e_str} &nbsp; {badge}"
            )

        col_lot, col_wash = st.columns(2)
        col_lot.metric("סך קווי טיפול", len(lines_of_therapy))

        on_tx = any(e.get("ongoing") for e in valid_drugs)
        if on_tx:
            col_wash.metric("סטטוס", "תחת טיפול פעיל 🟢")
        else:
            end_dates = [e["end_date"] for e in valid_drugs if e.get("end_date")]
            if end_dates:
                col_wash.metric("Washout", f"{(date.today() - max(end_dates)).days} ימים")

        # ── עמידות ────────────────────────────────────────────────────────────
        st.subheader("עמידות (Refractory Status)")

        def _grp_ref(g):
            return any(drug_ref_status.get(d, {}).get("refractory", False)
                       for d in DRUG_CLASS_GROUPS.get(g, []))

        pi_ref     = _grp_ref("PI")
        imid_ref   = _grp_ref("IMiD")
        cd38_ref   = _grp_ref("anti-CD38")
        bcma_ref   = _grp_ref("BCMA-directed")
        gprc5d_ref = _grp_ref("GPRC5D-directed")
        triple_ref = pi_ref and imid_ref and cd38_ref
        penta_ref  = all(drug_ref_status.get(d, {}).get("refractory", False)
                         for d in ["Bortezomib", "Carfilzomib",
                                   "Lenalidomide", "Pomalidomide", "Daratumumab"])

        c1, c2, c3 = st.columns(3)
        c1.metric("PI-refractory",        "כן 🔴" if pi_ref    else "לא")
        c2.metric("IMiD-refractory",      "כן 🔴" if imid_ref  else "לא")
        c3.metric("Anti-CD38-refractory", "כן 🔴" if cd38_ref  else "לא")
        c4, c5 = st.columns(2)
        c4.metric("BCMA-refractory",   "כן 🔴" if bcma_ref   else "לא")
        c5.metric("GPRC5D-refractory", "כן 🔴" if gprc5d_ref else "לא")

        if triple_ref:
            st.error("🔴 Triple-class refractory (PI + IMiD + anti-CD38)")
        if penta_ref:
            st.error("🔴 Penta-drug refractory (Bortezomib + Carfilzomib + Lenalidomide + Pomalidomide + Daratumumab)")

        with st.expander("פירוט לפי תרופה"):
            for dname, info in sorted(drug_ref_status.items()):
                icon = "🔴 עמיד (refractory)" if info["refractory"] else "🟡 חשוף (exposed)"
                st.write(f"**{dname}** — {icon}")

    st.divider()

elif disease_class and disease_class != "אבחנה חדשה — מיאלומה פעילה, טרם טיפול":
    st.header("ה — היסטוריית טיפולים")
    st.info("💊 כדי למלא את היסטוריית הטיפולים, יש לסמן **'כן'** בשאלה 'האם המטופל קיבל טיפול בעבר?' (חלק ב).")

# ════════════════════════════════════════════════════════════════════════════
# כפתור שליחה + בדיקות תקינות
# ════════════════════════════════════════════════════════════════════════════
st.header("סיכום והתאמה")

errors = []
if not age:
    errors.append("חסר: גיל המטופל")
if not gender or gender == "":
    errors.append("חסר: מין המטופל")
if not disease_class or disease_class == "":
    errors.append("חסר: סיווג המחלה")
if not lab_date:
    errors.append("חסר: תאריך בדיקות")

if errors:
    for e in errors:
        st.warning(f"⚠️ {e}")

submit = st.button("🔍 הרץ התאמה למחקרים קליניים",
                   disabled=len(errors) > 0,
                   type="primary",
                   use_container_width=True)

if submit:
    # ── בניית פרופיל מטופל ─────────────────────────────────────────────
    patient = {
        "age": age,
        "gender": gender,
        "disease_class": disease_class,
        "relapse_confirmation": relapse_confirmation,
        "prior_treatment": prior_treatment,
        "asct_candidate": asct_candidate,
        "asct_done": asct_done,
        "asct_date": str(asct_date) if asct_date else None,
        "extramedullary": extramedullary,
        "ecog": ecog,
        "active_conditions": active_conditions,
        "hematologic_exclusions": hematologic_exclusions,
        "labs": {
            "date": str(lab_date) if lab_date else None,
            "hb": hb, "plt": plt_val, "anc": anc,
            "creatinine": creatinine, "egfr": egfr,
            "ast": ast, "alt": alt, "bilirubin": bilirubin,
            "m_protein_serum": m_protein_serum,
            "m_protein_urine": m_protein_urine,
            "kappa_flc": kappa_flc,
            "lambda_flc": lambda_flc,
            "flc_ratio": flc_ratio,
            "measurable_disease": measurable,
            "t11_14": t11_14
        },
        "lines_of_therapy": lines_of_therapy,
        "lot_count":         len(lines_of_therapy),
        "refractory_status": drug_ref_status,
        "days_since_last_treatment": (
            (date.today() - max(e["end_date"] for e in valid_drugs if e.get("end_date"))).days
            if any(e.get("end_date") for e in valid_drugs) else None
        ) if valid_drugs else None,
    }

    # ── סיכום פרופיל ────────────────────────────────────────────────────
    st.success("✅ הנתונים התקבלו בהצלחה")

    st.subheader("סיכום פרופיל המטופל")

    col1, col2, col3 = st.columns(3)
    col1.metric("גיל", age)
    col2.metric("מין", gender)
    col3.metric("eGFR", f"{egfr} mL/min" if egfr else "לא מחושב")

    st.write(f"**סיווג מחלה:** {disease_class}")
    if lines_of_therapy:
        lot_n = len(lines_of_therapy)
        all_drugs = sorted({d for line in lines_of_therapy for d in line["drugs"]})
        st.write(f"**קווי טיפול:** {lot_n}")
        st.write(f"**תרופות שדווחו:** {', '.join(all_drugs)}")
    st.write(f"**מחלה מדידה:** {'כן ✅' if measurable else 'לא / לא ידוע'}")

    # ── התאמה למחקרים ───────────────────────────────────────────────────
    st.subheader("מחקרים קליניים מתאימים")

    if not trials:
        st.warning("קובץ המחקרים לא נמצא. יש לוודא ש-myeloma_trials_structured.json נמצא בתיקיית האפליקציה.")
    else:
        # סינון מחקרים בסיסי — חובה לעמוד בכל שלושת התנאים
        def _is_eligible_trial(t: dict) -> tuple[bool, str]:
            if t.get("recruiting_status") not in (None, "RECRUITING"):
                return False, "המחקר אינו מגייס כרגע"
            if t.get("is_interventional") is False:
                return False, "מחקר תצפיתי — לא רלוונטי"
            if t.get("is_drug_trial") is False:
                return False, "המחקר אינו תרופתי"
            if t.get("has_israel_site") is False:
                return False, "אין אתר בישראל"
            return True, ""

        eligible, maybe, ineligible = [], [], []
        skipped = 0
        for trial in trials:
            passes, skip_reason = _is_eligible_trial(trial)
            if not passes:
                skipped += 1
                continue
            status, fails, warns = _match_trial(trial, patient)
            entry = {
                "nct":   trial.get("nct_id", ""),
                "title": trial.get("title", "ללא כותרת"),
                "url":   trial.get("url", ""),
                "fails": fails,
                "warns": warns,
                "notes": trial.get("eligibility", {}).get("notes"),
            }
            if status == "eligible":
                eligible.append(entry)
            elif status == "maybe":
                maybe.append(entry)
            else:
                ineligible.append(entry)

        active_trials = len(trials) - skipped
        st.markdown(
            f"מתוך **{active_trials}** מחקרים פעילים בישראל: "
            f"✅ **{len(eligible)} מתאימים** · "
            f"⚠️ **{len(maybe)} לבדיקה** · "
            f"❌ **{len(ineligible)} לא מתאימים**"
        )

        # שמירה ל-Google Sheets
        save_result = _save_to_sheet(patient, eligible, maybe)
        if save_result is not True:
            st.caption(f"⚠️ לא ניתן לשמור ל-Google Sheets: {save_result}")

        def _show_trial(entry, show_fails=False, show_warns=False):
            nct, title, url = entry["nct"], entry["title"], entry["url"]
            with st.container(border=True):
                st.markdown(f"**{nct}** — {title}")
                if url:
                    st.markdown(f"[פתח ב-ClinicalTrials.gov]({url})")
                if show_fails and entry["fails"]:
                    for f in entry["fails"]:
                        st.markdown(f"  ❌ {f}")
                if show_warns and entry["warns"]:
                    for w in entry["warns"]:
                        st.markdown(f"  ⚠️ {w}")
                if entry.get("notes"):
                    st.caption(f"📝 {entry['notes']}")

        if eligible:
            st.markdown("### ✅ מתאים")
            for e in eligible:
                _show_trial(e, show_warns=True)

        if maybe:
            with st.expander(f"⚠️ לבדיקה נוספת ({len(maybe)})"):
                for e in maybe:
                    _show_trial(e, show_warns=True)

        if ineligible:
            with st.expander(f"❌ לא מתאים ({len(ineligible)})"):
                for e in ineligible:
                    _show_trial(e, show_fails=True)

st.markdown("""
<hr style="border:none; border-top:1px solid #d4e1f7; margin:2rem 0 1rem;">
<div style="text-align:center; color:#999; font-size:0.8rem; padding-bottom:1rem;">
    © 2025 · פותח על ידי פרופ' יעל כהן וד"ר אודליה אשל-פורר · כל הזכויות שמורות<br>
    <span style="font-style:italic;">כלי זה הינו כלי עזר בלבד ואינו מחליף ייעוץ רפואי. אין להעלות פרטים מזהים כגון שם, ת.ז, טלפון וכו'.</span>
</div>
""", unsafe_allow_html=True)
