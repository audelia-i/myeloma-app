"""
חילוץ ערכי מעבדה מתמונה באמצעות Claude Vision API.
"""

import base64
import json
import anthropic
import fitz  # PyMuPDF
from pydantic import BaseModel
from typing import Optional


class LabValues(BaseModel):
    # ספירת דם
    hb: Optional[float] = None          # המוגלובין g/dL
    plt: Optional[float] = None         # טסיות ×10⁹/L
    anc: Optional[float] = None         # נויטרופילים מוחלטים ×10⁹/L

    # כימיה
    creatinine: Optional[float] = None  # קריאטינין mg/dL

    # כבד
    ast: Optional[float] = None         # IU/L
    alt: Optional[float] = None         # IU/L
    bilirubin: Optional[float] = None   # בילירובין כולל mg/dL

    # פרופיל מיאלומה
    m_protein_serum: Optional[float] = None   # M-protein g/dL
    m_protein_urine: Optional[float] = None   # שתן mg/24h
    kappa_flc: Optional[float] = None         # mg/L
    lambda_flc: Optional[float] = None        # mg/L


EXTRACTION_PROMPT = """אתה מומחה לפענוח בדיקות מעבדה רפואיות.
לפניך תמונה של תוצאות בדיקות מעבדה של מטופל (בעברית או באנגלית).
המטרה: חילוץ ערכים מספריים מדויקים והחזרתם ביחידות הסטנדרטיות הנדרשות.

⚠️ כלל עליון: **אחרי שחילצת ערך — המר אותו ליחידות הנדרשות לפני שתחזיר.**

---

## ספירת דם

### המוגלובין → hb (יחידות: g/dL)
- שמות: המוגלובין / Hemoglobin / Hb / HGB
- g/dL → השאר כמו שהוא
- g/L → חלק ב-10
- mmol/L → כפל ב-1.611

### טסיות → plt (יחידות: ×10⁹/L)
- שמות: טסיות / Platelets / PLT / Thrombocytes
- ×10³/µL, K/µL, ×10³/mm³ → זה **אותו ערך**, השאר כמו שהוא (לדוגמה: 150 K/µL = 150 ×10⁹/L)
- ×10⁶/µL → כפל ב-1000 (נדיר)

### נויטרופילים → anc (יחידות: ×10⁹/L — **מוחלטים בלבד**)
- שמות: Neutrophils (Abs) / ANC / נויטרופילים מוחלטים / NEUT#
- **אם מוצג כ-# (מספר מוחלט):** ×10³/µL = ×10⁹/L → השאר כמו שהוא
- **אם מוצג כ-% בלבד (NEUT%):**
  - חפש גם WBC / כדוריות לבנות ×10³/µL
  - חשב: anc = WBC × (NEUT% / 100)
  - אם אין WBC → השאר null

---

## כימיה

### קריאטינין → creatinine (יחידות: mg/dL)
- שמות: Creatinine / קריאטינין / Cr / CREA
- mg/dL → השאר כמו שהוא
- µmol/L → חלק ב-88.4
- mmol/L → כפל ב-11.31

---

## תפקודי כבד (כולם IU/L = U/L — אותו ערך)

- AST / SGOT / אספרטט → ast
- ALT / SGPT / אלנין → alt

### בילירובין כולל → bilirubin (יחידות: mg/dL)
- שמות: Total Bilirubin / T.Bili / בילירובין כולל
- mg/dL → השאר כמו שהוא
- µmol/L → חלק ב-17.1

---

## פרופיל מיאלומה

### M-protein בסרום → m_protein_serum (יחידות: g/dL)
- שמות: M-protein / M-spike / חלבון M / SPE / Monoclonal protein / M-גרדיינט
- g/dL → השאר כמו שהוא
- g/L → חלק ב-10
- mg/dL → חלק ב-1000
- **% (אחוז מחלבון כולל) → אל תחלץ! השאר null** והוסף הערה "M-protein מוצג באחוזים"

### M-protein בשתן → m_protein_urine (יחידות: mg/24h)
- שמות: Urine M-protein / UPE / שתן 24 שעות M
- mg/24h → השאר כמו שהוא
- g/24h → כפל ב-1000

### Kappa FLC → kappa_flc (יחידות: mg/L)
- שמות: Free Kappa / κ-FLC / Kappa free light chain / שרשרת קלה חופשית קאפה
- mg/L → השאר כמו שהוא
- mg/dL → כפל ב-10

### Lambda FLC → lambda_flc (יחידות: mg/L)
- שמות: Free Lambda / λ-FLC / Lambda free light chain / שרשרת קלה חופשית למבדה
- mg/L → השאר כמו שהוא
- mg/dL → כפל ב-10

---

## כללים סופיים
1. אם ערך לא מופיע בתמונה → null (לא לנחש)
2. אם ערך לא קריא / מטושטש → null
3. **החזר תמיד את הערך הסופי לאחר ההמרה**, לא את הערך המקורי
4. אם יש ספק בזיהוי — null עדיף על ניחוש שגוי
"""


def pdf_to_images(pdf_bytes: bytes) -> list[bytes]:
    """ממיר PDF לרשימת תמונות PNG (דף אחד = תמונה אחת)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        images.append(pix.tobytes("png"))
    doc.close()
    return images


def extract_lab_values(image_bytes: bytes, api_key: str, mime_type: str = "image/jpeg") -> dict:
    """
    שולח תמונה ל-Claude ומחזיר ערכי מעבדה מחולצים.

    Returns:
        dict עם שדות מ-LabValues + שדה 'success' ו-'error'
    """
    client = anthropic.Anthropic(api_key=api_key)

    # המרה ל-base64
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    try:
        response = client.messages.parse(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": EXTRACTION_PROMPT
                    }
                ]
            }],
            output_format=LabValues
        )

        lab = response.parsed_output
        result = lab.model_dump()
        result["success"] = True
        result["error"] = None
        return result

    except anthropic.BadRequestError as e:
        return {"success": False, "error": f"התמונה לא נקראה כראוי: {str(e)}"}
    except anthropic.AuthenticationError:
        return {"success": False, "error": "מפתח API לא תקין. אנא בדקי את המפתח בהגדרות."}
    except Exception as e:
        return {"success": False, "error": f"שגיאה: {str(e)}"}
