"""
PDF Parser for Danish Ministry of Education Timetables (Folkeskolen)

Downloads and parses UVM's annual timetable overview PDF, converting yearly
60-min hour requirements into weekly 45-min lesson counts per grade.

Output separates:
  - mandatory_subjects: fixed curriculum subjects with DB seed metadata
  - electives: scheduling slots schools fill with chosen subjects
  - grade_totals: minimum/timebank/total rows (not subjects)
"""

import requests
import io
import re
from datetime import datetime
from typing import Optional
import pdfplumber


# ---------------------------------------------------------------------------
# Canonical subject metadata — doubles as DB seed data
# requires_special_room: True means the room type must match (gym, lab, etc.)
# ---------------------------------------------------------------------------
MANDATORY_SUBJECTS: dict[str, dict] = {
    "Dansk":               {"short_code": "DA", "category": "humanistisk"},
    "Engelsk":             {"short_code": "EN", "category": "humanistisk"},
    "Tysk/fransk":         {"short_code": "TY", "category": "humanistisk"},
    "Samfundsfag":         {"short_code": "SA", "category": "humanistisk"},
    "Kristendomskundskab": {"short_code": "KR", "category": "humanistisk"},
    "Historie":            {"short_code": "HI", "category": "humanistisk"},
    "Matematik":           {"short_code": "MA", "category": "naturfag"},
    "Natur/teknologi":     {"short_code": "NT", "category": "naturfag"},
    "Geografi":            {"short_code": "GE", "category": "naturfag"},
    "Biologi":             {"short_code": "BI", "category": "naturfag"},
    "Fysik/kemi":          {"short_code": "FK", "category": "naturfag",    "requires_special_room": True},
    "Idræt":               {"short_code": "ID", "category": "praktisk_musisk", "requires_special_room": True},
    "Musik":               {"short_code": "MU", "category": "praktisk_musisk"},
    "Billedkunst":         {"short_code": "BK", "category": "praktisk_musisk"},
    "Håndværk og design":  {"short_code": "HD", "category": "praktisk_musisk", "requires_special_room": True},
    "Madkundskab":         {"short_code": "MK", "category": "praktisk_musisk", "requires_special_room": True},
}

# Electives are scheduling *slots* — schools decide which specific subject fills each slot.
# has_exam: whether the ministry requires an exam for this slot.
ELECTIVE_SLOTS: dict[str, dict] = {
    "1. praktiske/musiske valgfag (prøve)": {
        "slot_key": "pm_valgfag_1",
        "category": "praktisk_musisk",
        "has_exam": True,
    },
    "2. praktiske/musiske valgfag": {
        "slot_key": "pm_valgfag_2",
        "category": "praktisk_musisk",
        "has_exam": False,
    },
    "Lokalt valgfag": {
        "slot_key": "lokalt_valgfag",
        "category": "valgfag",
        "has_exam": False,
    },
}

# These rows carry summary data, not subject hours.
# Matched by a fragment that avoids encoding-broken Danish chars.
_SUMMARY_FRAGMENTS: dict[str, str] = {
    "rligt minimumstimetal": "annual_minimum",   # "Årligt minimumstimetal pr. klassetrin"
    "Skolens timebank":       "timebank_and_breaks",
    "samlede":                "total_annual_time",  # "Den samlede årlige undervisningstid"
}

# PDF font encoding sometimes replaces æ/ø/å with U+FFFD (replacement char).
# These corrections are specific to UVM's timetable PDFs.
_ENCODING_FIXES: dict[str, str] = {
    "Idr��t":                           "Idræt",
    "H�ndv��rk og design":          "Håndværk og design",
    "1. praktiske/musiske valgfag (pr�ve)":  "1. praktiske/musiske valgfag (prøve)",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fix_encoding(text: str) -> str:
    for broken, fixed in _ENCODING_FIXES.items():
        text = text.replace(broken, fixed)
    return text


def _parse_hours(value: str | None) -> float:
    """
    Convert a yearly 60-min hour count (årstimer) to weekly 45-min lessons.

    Formula: yearly_hours × (60/45) / 40_school_weeks = weekly_lektioner
    The PDF uses '.' as a thousands separator and '*' for footnotes.
    Returns 0.0 for missing or dash values.
    """
    if not value or value.strip() in ("-", ""):
        return 0.0
    cleaned = value.replace("*", "").replace(".", "").strip()
    if not cleaned.isdigit():
        return 0.0
    return round((int(cleaned) * 4 / 3) / 40, 2)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class MinistryPDFParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

    def download_pdf(self, url: str) -> Optional[bytes]:
        try:
            r = self.session.get(url, timeout=30)
            r.raise_for_status()
            return r.content
        except Exception as e:
            print(f"Download error: {e}")
            return None

    def _extract_raw_table(self, pdf_bytes: bytes) -> Optional[list[list[str]]]:
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                return pdf.pages[0].extract_table()
        except Exception as e:
            print(f"PDF extraction error: {e}")
            return None

    def _clean_table(self, raw_table: list[list[str]]) -> list[list[str]]:
        """Drop header and category-separator rows that carry no hour data."""
        skip = {
            "Klassetrin",
            "Humanistiske fag",
            "Naturfag",
            "Praktiske/musiske fag",
            "Valgfag",
            "(inkl. fagtimer, skolens timebank og pauser)",
        }
        return [row for row in raw_table if row and row[0] and row[0] not in skip]

    def parse_ministry_pdf(self, url: str) -> dict:
        """
        Main entry point. Returns a structured dict with:
          year, url, extraction_date,
          mandatory_subjects, electives, grade_totals
        """
        print(f"Downloading: {url}")
        pdf_bytes = self.download_pdf(url)
        if not pdf_bytes:
            return {"error": "Failed to download PDF"}

        raw_table = self._extract_raw_table(pdf_bytes)
        if not raw_table:
            return {"error": "Failed to extract table from PDF"}

        rows = self._clean_table(raw_table)

        # Table structure: col 0 = subject name, cols 1-10 = grades 0-9, col 11 = yearly total
        mandatory: dict[str, dict] = {}
        electives: dict[str, dict] = {}
        grade_totals: dict[str, dict] = {}

        for row in rows:
            raw_label = (row[0] or "").strip()
            label = _fix_encoding(raw_label)
            label = label.replace(" (minimumstimetal)", "")

            # Parse per-grade hours (grades 0–9)
            grade_hours: dict[int, float] = {}
            for grade in range(10):
                col = grade + 1
                grade_hours[grade] = _parse_hours(row[col] if col < len(row) else None)

            yearly_total = _parse_hours(row[11] if len(row) > 11 else None)

            # Classify the row
            if label in MANDATORY_SUBJECTS:
                mandatory[label] = {
                    **MANDATORY_SUBJECTS[label],
                    "grade_hours": grade_hours,
                    "yearly_total_lessons": yearly_total,
                    "requires_special_room": MANDATORY_SUBJECTS[label].get("requires_special_room", False),
                }
            elif label in ELECTIVE_SLOTS:
                electives[label] = {
                    **ELECTIVE_SLOTS[label],
                    "grade_hours": grade_hours,
                    "yearly_total_lessons": yearly_total,
                }
            else:
                # Check if it's a summary row by fragment matching
                for fragment, summary_key in _SUMMARY_FRAGMENTS.items():
                    if fragment in label:
                        grade_totals[summary_key] = grade_hours
                        break

        return {
            "year": _extract_year(url),
            "url": url,
            "extraction_date": datetime.now().isoformat(),
            "mandatory_subjects": mandatory,
            "electives": electives,
            "grade_totals": grade_totals,
        }


def _extract_year(url: str) -> int:
    m = re.search(r"(\d{4})-(\d{4})", url)
    return int(m.group(1)) if m else datetime.now().year


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = MinistryPDFParser()
    url = "https://uvm.dk/media/dfnbhhem/241218-timetalsoversigt-for-skoleaaret-2026-2027-pdf.pdf"
    result = parser.parse_ministry_pdf(url)

    yr = result["year"]
    print(f"\nSchool year: {yr}/{yr + 1}")

    print(f"\n=== MANDATORY SUBJECTS ({len(result['mandatory_subjects'])}) ===")
    for name, data in result["mandatory_subjects"].items():
        active = [f"{g}.kl:{h:.0f}" for g, h in data["grade_hours"].items() if h > 0]
        room = " [special room]" if data["requires_special_room"] else ""
        print(f"  [{data['short_code']}] {name}{room}")
        print(f"      {', '.join(active)}")

    print(f"\n=== ELECTIVE SLOTS ({len(result['electives'])}) ===")
    for name, data in result["electives"].items():
        active = [f"{g}.kl:{h:.0f}" for g, h in data["grade_hours"].items() if h > 0]
        exam = " [exam]" if data["has_exam"] else ""
        hours_str = ', '.join(active) if active else "no mandated hours (school timebank)"
        print(f"  [{data['slot_key']}]{exam} {name}")
        print(f"      {hours_str}")

    print(f"\n=== WEEKLY LESSONS PER GRADE (ministry minimum) ===")
    if "annual_minimum" in result["grade_totals"]:
        for grade, lessons in result["grade_totals"]["annual_minimum"].items():
            label = "Børnehaveklassen" if grade == 0 else f"{grade}. klasse"
            print(f"  {label}: {lessons:.1f} lektioner/uge")

    return result


if __name__ == "__main__":
    main()
