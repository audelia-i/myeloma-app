"""
עדכון myeloma_trials_structured.json עם נתונים מ-ClinicalTrials.gov API:
  - recruiting_status   : סטטוס גיוס (RECRUITING / COMPLETED / וכו')
  - is_interventional   : True אם מחקר התערבותי
  - is_drug_trial       : True אם ההתערבות היא תרופתית (לא אלטרנטיבית)
  - has_israel_site     : True אם יש אתר בישראל
  - max_ecog            : ממולא מהטקסט אם חסר ב-JSON הנוכחי (דרך Claude)

הרצה: python update_trials_status.py
דרישות: pip install requests anthropic
"""

import json
import time
import re
import os
import requests
import anthropic

INPUT_FILE  = "myeloma_trials_structured.json"
OUTPUT_FILE = "myeloma_trials_structured.json"  # מחליף את אותו הקובץ

CT_API_BASE = "https://clinicaltrials.gov/api/v2/studies"

DRUG_INTERVENTION_TYPES = {"DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT", "GENETIC"}

TREATMENT_PURPOSES = {"TREATMENT"}

# ── שליפה מ-ClinicalTrials.gov ───────────────────────────────────────────────

def fetch_ct_data(nct_id: str) -> dict | None:
    url = f"{CT_API_BASE}/{nct_id}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ⚠️  שגיאה בשליפת {nct_id}: {e}")
        return None


def parse_ct_fields(data: dict) -> dict:
    """מחלץ שדות רלוונטיים מה-JSON של ClinicalTrials.gov."""
    proto = data.get("protocolSection", {})

    # סטטוס
    status_module = proto.get("statusModule", {})
    overall_status = status_module.get("overallStatus", "UNKNOWN")

    # עיצוב מחקר
    design = proto.get("designModule", {})
    study_type = design.get("studyType", "")
    primary_purpose = design.get("designInfo", {}).get("primaryPurpose", "")

    # התערבויות
    arms = proto.get("armsInterventionsModule", {})
    interventions = arms.get("interventions", [])
    intervention_types = {iv.get("type", "").upper() for iv in interventions}

    # אתרים
    contacts = proto.get("contactsLocationsModule", {})
    locations = contacts.get("locations", [])
    countries = {loc.get("country", "") for loc in locations}

    # טקסט זכאות (לחילוץ ECOG)
    elig_module = proto.get("eligibilityModule", {})
    eligibility_text = elig_module.get("eligibilityCriteria", "")

    is_interventional = study_type.upper() == "INTERVENTIONAL"
    is_drug_trial = bool(intervention_types & DRUG_INTERVENTION_TYPES)
    # אם אין התערבויות רשומות אך זה התערבותי ומטרתו טיפול — נניח תרופתי
    if is_interventional and not intervention_types and primary_purpose.upper() in TREATMENT_PURPOSES:
        is_drug_trial = True

    has_israel = "Israel" in countries

    return {
        "recruiting_status": overall_status,
        "is_interventional": is_interventional,
        "is_drug_trial": is_drug_trial,
        "has_israel_site": has_israel,
        "_eligibility_text": eligibility_text,  # זמני — לא ייכנס ל-JSON הסופי
    }


# ── חילוץ ECOG מטקסט דרך Claude ─────────────────────────────────────────────

def extract_ecog_from_text(eligibility_text: str, client: anthropic.Anthropic) -> int | None:
    if not eligibility_text:
        return None

    prompt = f"""From the following clinical trial eligibility criteria, extract the maximum allowed ECOG Performance Status score.
Return ONLY a single integer (0, 1, 2, 3, or 4), or null if ECOG is not mentioned.

Eligibility criteria:
{eligibility_text[:3000]}

Answer with only a number or the word null."""

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )
        text = resp.content[0].text.strip()
        if text.lower() == "null":
            return None
        return int(text)
    except Exception:
        return None


# ── מנגנון ראשי ───────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        # נסה לקרוא מ-secrets.toml מקומי
        try:
            with open(".streamlit/secrets.toml") as f:
                for line in f:
                    if "ANTHROPIC_API_KEY" in line:
                        api_key = line.split("=")[1].strip().strip('"').strip("'")
        except Exception:
            pass

    claude = anthropic.Anthropic(api_key=api_key) if api_key else None

    with open(INPUT_FILE, encoding="utf-8") as f:
        trials = json.load(f)

    print(f"נטענו {len(trials)} מחקרים\n")

    for i, trial in enumerate(trials):
        nct_id = trial["nct_id"]
        print(f"[{i+1}/{len(trials)}] {nct_id} — {trial['title'][:60]}")

        data = fetch_ct_data(nct_id)
        if data is None:
            trial["recruiting_status"] = "UNKNOWN"
            trial["is_interventional"] = None
            trial["is_drug_trial"] = None
            trial["has_israel_site"] = None
            continue

        fields = parse_ct_fields(data)
        elig_text = fields.pop("_eligibility_text", "")

        trial["recruiting_status"] = fields["recruiting_status"]
        trial["is_interventional"] = fields["is_interventional"]
        trial["is_drug_trial"] = fields["is_drug_trial"]
        trial["has_israel_site"] = fields["has_israel_site"]

        # השלמת ECOG אם חסר
        current_ecog = trial.get("eligibility", {}).get("max_ecog")
        if current_ecog is None and claude and elig_text:
            ecog = extract_ecog_from_text(elig_text, claude)
            if ecog is not None:
                trial["eligibility"]["max_ecog"] = ecog
                print(f"    → ECOG חולץ: {ecog}")

        status_icon = "✅" if fields["recruiting_status"] == "RECRUITING" else "⏸"
        israel_icon = "🇮🇱" if fields["has_israel_site"] else "✗"
        drug_icon   = "💊" if fields["is_drug_trial"] else "🌿"
        print(f"    {status_icon} {fields['recruiting_status']}  {israel_icon}  {drug_icon}  ECOG={trial['eligibility'].get('max_ecog')}")

        time.sleep(0.3)  # כבד את ה-API

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(trials, f, ensure_ascii=False, indent=2)

    # סיכום
    recruiting   = sum(1 for t in trials if t.get("recruiting_status") == "RECRUITING")
    israel       = sum(1 for t in trials if t.get("has_israel_site"))
    drug         = sum(1 for t in trials if t.get("is_drug_trial"))
    interventional = sum(1 for t in trials if t.get("is_interventional"))

    print(f"\n✅ הסתיים — {OUTPUT_FILE} עודכן")
    print(f"   מגייסים:      {recruiting}/{len(trials)}")
    print(f"   התערבותיים:   {interventional}/{len(trials)}")
    print(f"   תרופתיים:     {drug}/{len(trials)}")
    print(f"   אתר בישראל:   {israel}/{len(trials)}")


if __name__ == "__main__":
    main()
