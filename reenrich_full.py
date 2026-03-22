"""
סקריפט עשרה מלא ומקיף של myeloma_trials_structured.json.

לכל מחקר:
  1. שולף טקסט Inclusion/Exclusion מלא מ-ClinicalTrials.gov API (חינם)
  2. שולח ל-Claude Haiku לחילוץ ALL קריטריונים לשדות מובנים
  3. שומר את השדות הקיימים (recruiting_status, is_interventional וכו')

הרצה:
    python reenrich_full.py

דרישות: pip install requests anthropic
"""

import json, os, sys, time, re, requests, anthropic

INPUT_FILE  = "myeloma_trials_structured.json"
OUTPUT_FILE = "myeloma_trials_structured.json"
CT_API      = "https://clinicaltrials.gov/api/v2/studies"

# ── פרומפט מקיף ─────────────────────────────────────────────────────────────

PARSE_PROMPT = """You are a clinical trial eligibility parser for multiple myeloma trials.
Given the full inclusion and exclusion criteria text below, extract ALL relevant fields.
Return ONLY a valid JSON object — no markdown, no explanation.

JSON schema:
{{
  "disease_status": [],
  "measurable_disease_required": null,
  "min_lot": null,
  "max_lot": null,
  "max_ecog": null,
  "required_refractory_classes": [],
  "required_exposed_classes": [],
  "excluded_prior_drugs": [],
  "bcma_allowed": null,
  "gprc5d_allowed": null,
  "cd38_allowed": null,
  "cart_allowed": null,
  "asct_required": null,
  "excluded_if_asct_candidate": false,
  "excluded_if_prior_asct": false,
  "min_hb": null,
  "min_plt": null,
  "min_anc": null,
  "min_egfr": null,
  "max_creatinine": null,
  "max_bilirubin_x_uln": null,
  "max_ast_alt_x_uln": null,
  "excluded_if_amyloidosis": false,
  "excluded_if_plasma_cell_leukemia": false,
  "excluded_if_poems": false,
  "excluded_if_waldenstrom": false,
  "excluded_if_active_infection": false,
  "excluded_if_active_malignancy": false,
  "excluded_if_active_autoimmune": false,
  "excluded_if_cns_involvement": false,
  "excluded_if_peripheral_neuropathy_g2": false,
  "excluded_if_renal_dialysis": false,
  "excluded_if_hepatitis": false,
  "excluded_if_hiv": false,
  "excluded_if_recent_cardiac_event": false,
  "min_washout_days": null,
  "min_age": null,
  "max_age": null,
  "notes": null
}}

Field rules:
- disease_status: ["RRMM","NDMM","SMM"] — RRMM=relapsed/refractory, NDMM=newly diagnosed, SMM=smoldering
- min_lot/max_lot: integer lines of prior therapy. "treatment naive"→min_lot=0,max_lot=0. "≥3 prior lines"→min_lot=3
- max_ecog: integer 0-4. Very important — check carefully for "ECOG PS ≤1" → max_ecog=1
- required_refractory_classes: MUST be refractory to these. Use exact labels: "PI","IMiD","anti-CD38","BCMA","GPRC5D","CELMoD"
- required_exposed_classes: prior exposure required (not necessarily refractory)
- excluded_prior_drugs: specific drug names that disqualify if used previously
- bcma_allowed: false ONLY if prior BCMA therapy explicitly prohibited
- gprc5d_allowed: false ONLY if prior GPRC5D therapy explicitly prohibited
- cd38_allowed: false ONLY if prior anti-CD38 therapy explicitly prohibited
- cart_allowed: false ONLY if prior CAR-T explicitly prohibited
- asct_required: true if prior ASCT is required for inclusion
- excluded_if_asct_candidate: TRUE if being eligible/candidate for autologous SCT is an EXCLUSION criterion
- excluded_if_prior_asct: true if having had prior ASCT is an exclusion criterion
- min_hb: minimum hemoglobin in g/dL
- min_plt: minimum platelets in ×10⁹/L
- min_anc: minimum ANC in ×10⁹/L
- min_egfr: minimum eGFR/creatinine clearance in mL/min
- max_creatinine: maximum creatinine in mg/dL (if specified)
- max_bilirubin_x_uln: max total bilirubin as X × ULN (e.g. 1.5)
- max_ast_alt_x_uln: max AST or ALT as X × ULN
- excluded_if_peripheral_neuropathy_g2: true if grade ≥2 peripheral neuropathy is exclusion
- excluded_if_renal_dialysis: true if renal dialysis is exclusion
- excluded_if_hepatitis: true if active/chronic hepatitis B or C is exclusion
- excluded_if_hiv: true if HIV positive is exclusion
- excluded_if_recent_cardiac_event: true if recent MI/cardiac event (within 6 months) is exclusion
- min_washout_days: minimum number of days required since last systemic therapy before enrollment. Look for phrases like "washout period", "at least X days/weeks since last treatment". Convert weeks to days (1 week=7 days). null if not specified.
- notes: 1-2 sentences for important criteria NOT captured in the fields above. null if nothing remains.

ELIGIBILITY TEXT:
{text}
"""

# ── שליפה מ-ClinicalTrials.gov ───────────────────────────────────────────────

def fetch_eligibility_text(nct_id: str) -> str | None:
    try:
        r = requests.get(f"{CT_API}/{nct_id}", timeout=15)
        r.raise_for_status()
        data = r.json()
        elig = (data.get("protocolSection", {})
                    .get("eligibilityModule", {})
                    .get("eligibilityCriteria", ""))
        return elig or None
    except Exception as e:
        print(f"  ⚠️  שגיאת API עבור {nct_id}: {e}")
        return None


# ── חילוץ עם Claude ──────────────────────────────────────────────────────────

def parse_eligibility(client: anthropic.Anthropic, text: str, retries: int = 3) -> dict:
    prompt = PARSE_PROMPT.format(text=text[:4000])
    for attempt in range(retries):
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            # נקה code fences אם יש
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except json.JSONDecodeError:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                return {"error": "JSON parse error"}
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
            else:
                return {"error": str(e)}
    return {"error": "max retries"}


# ── ראשי ─────────────────────────────────────────────────────────────────────

def main():
    # מפתח API
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        try:
            with open(".streamlit/secrets.toml") as f:
                for line in f:
                    if "ANTHROPIC_API_KEY" in line:
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    if not api_key:
        print("ERROR: לא נמצא ANTHROPIC_API_KEY")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    with open(INPUT_FILE, encoding="utf-8") as f:
        trials = json.load(f)

    print(f"מעבד {len(trials)} מחקרים...\n")
    ok_count = err_count = 0

    for i, trial in enumerate(trials):
        nct_id = trial["nct_id"]
        print(f"[{i+1}/{len(trials)}] {nct_id} — {trial.get('title','')[:55]}")

        # שליפת טקסט זכאות
        elig_text = fetch_eligibility_text(nct_id)
        if not elig_text:
            print("  ✗ לא נמצא טקסט זכאות")
            err_count += 1
            time.sleep(0.3)
            continue

        # חילוץ עם Claude
        structured = parse_eligibility(client, elig_text)
        if "error" in structured:
            print(f"  ✗ {structured['error']}")
            err_count += 1
        else:
            trial["eligibility"] = structured
            asct_excl = structured.get("excluded_if_asct_candidate", False)
            ecog      = structured.get("max_ecog")
            print(f"  ✓  ECOG={ecog}  ASCT_excl={asct_excl}")
            ok_count += 1

        time.sleep(0.4)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(trials, f, ensure_ascii=False, indent=2)

    print(f"\n✅ נשמר {OUTPUT_FILE}  ✓{ok_count}  ✗{err_count}")


if __name__ == "__main__":
    main()
