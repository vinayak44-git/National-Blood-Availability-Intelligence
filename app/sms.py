"""
SMS / IVR Rural Access Layer
Parses structured SMS requests and formats responses
for the rural low-connectivity access channel.

SMS Request Format:
  REQ <blood_type> <units> <hospital_code>
  e.g.  REQ O- 3 H02
  e.g.  REQ B+ 2 H01

STATUS Request Format:
  STATUS <request_id>
  e.g.  STATUS R1245
"""

import re
from typing import Optional

BLOOD_TYPES = {"O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"}

# Pincode → Hospital ID mapping (simulated for prototype)
PINCODE_TO_HOSPITAL = {
    "110001": "H01",
    "110002": "H02",
    "110003": "H03",
    "110004": "H04",
    "110005": "H05",
    "110006": "H06",
    "110007": "H07",
    "110008": "H08",
    "110009": "H09",
    "110010": "H10",
}

# Hospital code → default authorized doctor (for SMS auto-assignment)
HOSPITAL_DEFAULT_DOCTOR = {
    "H01": "D01",
    "H02": "D03",
    "H03": "D05",
    "H04": "D06",
    "H05": "D07",
    "H06": "D08",
    "H07": "D09",
    "H08": "D10",
    "H09": "D01",
    "H10": "D03",
}


class SMSParseError(Exception):
    pass


def parse_sms_request(text: str) -> dict:
    """
    Parse an inbound SMS request text into a structured request dict.
    
    Supported formats:
      REQ O- 3 H02
      REQ O- 3 110001
      STATUS R1245
    
    Returns dict with:
      - type: "request" | "status"
      - blood_type, units, hospital_id, doctor_id  (for "request")
      - request_id  (for "status")
    """
    text = text.strip().upper()

    # STATUS check
    status_match = re.match(r"^STATUS\s+(R\d+)$", text)
    if status_match:
        return {
            "type": "status",
            "request_id": status_match.group(1)
        }

    # REQ command
    req_match = re.match(
        r"^REQ\s+([A-Z]{1,2}[+-])\s+(\d+)\s+([A-Z0-9]+)$",
        text
    )
    if not req_match:
        raise SMSParseError(
            "Invalid format. Use: REQ <blood_type> <units> <hospital_code>\n"
            "Example: REQ O- 3 H02\nOr status: STATUS R1245"
        )

    blood_type = req_match.group(1)
    units_str = req_match.group(2)
    location_code = req_match.group(3)

    if blood_type not in BLOOD_TYPES:
        raise SMSParseError(
            f"Unknown blood type '{blood_type}'.\n"
            f"Valid types: O-, O+, A-, A+, B-, B+, AB-, AB+"
        )

    units = int(units_str)
    if units < 1 or units > 20:
        raise SMSParseError("Units must be between 1 and 20.")

    # Resolve hospital
    hospital_id: Optional[str] = None

    if location_code in HOSPITAL_DEFAULT_DOCTOR:
        hospital_id = location_code
    elif location_code in PINCODE_TO_HOSPITAL:
        hospital_id = PINCODE_TO_HOSPITAL[location_code]
    else:
        raise SMSParseError(
            f"Unknown hospital code or pincode: '{location_code}'.\n"
            "Use your hospital ID (e.g. H02) or 6-digit pincode."
        )

    doctor_id = HOSPITAL_DEFAULT_DOCTOR.get(hospital_id, "D01")

    return {
        "type": "request",
        "blood_type": blood_type,
        "units": units,
        "hospital_id": hospital_id,
        "doctor_id": doctor_id,
    }


def format_sms_response(result: dict, request_id: str, blood_type: str, units_requested: int) -> str:
    """
    Format a fulfillment result into a concise SMS response string.
    """
    allocations = result.get("allocations", [])
    units_allocated = result.get("units_allocated", 0)

    lines = [
        f"RAKTSETU ALERT",
        f"Req ID: {request_id}",
        f"Blood: {blood_type} | Needed: {units_requested} units",
        "",
    ]

    if units_allocated >= units_requested:
        lines.append("STATUS: MATCH FOUND")
        lines.append("")
        for alloc in allocations:
            dist = alloc.get("distance_km", 0)
            lines.append(
                f"{alloc['bank_name']}: {alloc['units']} units ({dist:.1f} km)"
            )
        lines.append("")
        lines.append("Dispatcher will confirm. Keep phone on.")
    else:
        available = units_allocated
        lines.append(f"STATUS: PARTIAL - only {available}/{units_requested} available")
        lines.append("Dispatcher has been alerted.")

    return "\n".join(lines)


def format_sms_error(error_msg: str, request_id: str = None) -> str:
    lines = ["RAKTSETU SYSTEM"]
    if request_id:
        lines.append(f"Req ID: {request_id}")
    lines.append(f"ERROR: {error_msg}")
    lines.append("Contact: 1800-XXX-XXXX")
    return "\n".join(lines)


def format_sms_rejection(reason: str, request_id: str) -> str:
    reason_map = {
        "hospital_not_found": "Hospital not registered.",
        "hospital_inactive": "Hospital account inactive.",
        "doctor_not_authorized": "Doctor not authorized.",
        "doctor_hospital_mismatch": "Doctor/hospital mismatch.",
        "doctor_not_found": "Doctor not found.",
    }
    human_reason = reason_map.get(reason, reason)
    return (
        f"RAKTSETU ALERT\n"
        f"Req ID: {request_id}\n"
        f"STATUS: REJECTED\n"
        f"Reason: {human_reason}\n"
        f"Contact your hospital admin."
    )


def format_status_response(request: dict, audit_events: list) -> str:
    """Format a STATUS query response as SMS."""
    status = request.get("status", "unknown").replace("_", " ").upper()
    blood = request.get("blood_type", "?")
    units = request.get("units_needed", "?")
    urgency = request.get("urgency", "routine").upper()

    lines = [
        f"RAKTSETU STATUS",
        f"Req: {request['request_id']}",
        f"Blood: {blood} | Units: {units}",
        f"Urgency: {urgency}",
        f"Status: {status}",
    ]

    if audit_events:
        last = audit_events[-1]
        lines.append(f"Last update: {last.get('event_name','').replace('_',' ')}")

    return "\n".join(lines)
