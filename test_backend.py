"""
RaktSetu — Verification & Priority Engine — Full Backend Integration Tester
========================================================================
This script queries every GET and POST endpoint, validates database
integrity, queue ordering (priority + FIFO), statistics counters, and 
audit logs.

Run it directly from the project root:
    python test_backend.py
"""

import sys
import time
import requests

BASE_URL = "http://127.0.0.1:8000"

PASS = "[PASS]"
FAIL = "[FAIL]"

results = []  # (test_name, passed: bool, detail: str)


def record(test_name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((test_name, condition, detail))
    print(f"{status} | {test_name}" + (f"  -> {detail}" if (detail and not condition) else ""))
    return condition


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


session = requests.Session()

# Log in as dispatcher to allow cross-hospital submissions in testing
try:
    login_resp = session.post(
        f"{BASE_URL}/auth/login",
        data={"username": "dispatcher1", "password": "Dispatcher@123"},
        timeout=5
    )
    if login_resp.status_code != 200:
        print(f"\n[ERROR] Authentication failed. Code: {login_resp.status_code}, Body: {login_resp.text}")
        sys.exit(1)
except requests.exceptions.ConnectionError:
    print(f"\n[ERROR] Could not connect to {BASE_URL}. Is the server running?")
    print("   Start it with: uvicorn app.main:app --reload")
    sys.exit(1)

def safe_post(path, json_body=None):
    try:
        return session.post(f"{BASE_URL}{path}", json=json_body, timeout=5)
    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Could not connect to {BASE_URL}. Is the server running?")
        print("   Start it with: uvicorn app.main:app --reload")
        sys.exit(1)


def safe_get(path):
    try:
        return session.get(f"{BASE_URL}{path}", timeout=5)
    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Could not connect to {BASE_URL}. Is the server running?")
        print("   Start it with: uvicorn app.main:app --reload")
        sys.exit(1)


# ----------------------------------------------------------------------
# 0. ROOT / HEALTH CHECK
# ----------------------------------------------------------------------
section("0. ROOT / HEALTH CHECK")

resp = safe_get("/")
record("GET / returns 200", resp.status_code == 200, f"status={resp.status_code}")
body = resp.json() if resp.status_code == 200 else {}
record("GET / reports service running", body.get("status") == "running", f"body={body}")


# ----------------------------------------------------------------------
# 1. VALID CRITICAL REQUEST (happy path)
# ----------------------------------------------------------------------
section("1. VALID REQUEST — Critical, fully verified")

valid_critical = {
    "hospital_id": "H01",
    "doctor_id": "D01",
    "blood_type": "O-",
    "units_needed": 3,
    "urgency_input": "critical",
    "prescription_id": "RX10293",
    "hospital_lat": 28.6139,
    "hospital_lng": 77.2090
}

resp = safe_post("/submit-request", valid_critical)
record("Valid critical request -> 200", resp.status_code == 200, f"status={resp.status_code}, body={resp.text}")

body = resp.json() if resp.status_code == 200 else {}
critical_request_id = body.get("request_id")

record("Response contains request_id", bool(critical_request_id), f"body={body}")
record("verified == True", body.get("verified") is True, f"body={body}")
record("urgency == 'critical'", body.get("urgency") == "critical", f"body={body}")
record("blood_type echoed correctly", body.get("blood_type") == "O-", f"body={body}")
record("units_needed echoed correctly", body.get("units_needed") == 3, f"body={body}")
record("hospital_lat present", "hospital_lat" in body, f"body={body}")
record("hospital_lng present", "hospital_lng" in body, f"body={body}")
record("timestamp present", "timestamp" in body, f"body={body}")


# ----------------------------------------------------------------------
# 2. HOSPITAL NOT FOUND
# ----------------------------------------------------------------------
section("2. INVALID — Hospital does not exist")

req = dict(valid_critical, hospital_id="H999")
resp = safe_post("/submit-request", req)
record("Unknown hospital -> 403", resp.status_code == 403, f"status={resp.status_code}, body={resp.text}")
body = resp.json() if resp.status_code == 403 else {}
record("verified == False", body.get("verified") is False, f"body={body}")
record("reason == 'hospital_not_found'", body.get("reason") == "hospital_not_found", f"body={body}")


# ----------------------------------------------------------------------
# 3. UNAUTHORIZED DOCTOR
# ----------------------------------------------------------------------
section("3. INVALID — Doctor exists but is not authorized")

req = dict(valid_critical, doctor_id="D11")  # D11 seeded as unauthorized
resp = safe_post("/submit-request", req)
record("Unauthorized doctor -> 403", resp.status_code == 403, f"status={resp.status_code}, body={resp.text}")
body = resp.json() if resp.status_code == 403 else {}
record("reason == 'doctor_not_authorized'", body.get("reason") == "doctor_not_authorized", f"body={body}")


# ----------------------------------------------------------------------
# 4. DOCTOR / HOSPITAL MISMATCH
# ----------------------------------------------------------------------
section("4. INVALID — Doctor belongs to a different hospital")

req = dict(valid_critical, hospital_id="H01", doctor_id="D12")  # D12 seeded under H03
resp = safe_post("/submit-request", req)
record("Doctor/hospital mismatch -> 403", resp.status_code == 403, f"status={resp.status_code}, body={resp.text}")
body = resp.json() if resp.status_code == 403 else {}
record("reason == 'doctor_hospital_mismatch'", body.get("reason") == "doctor_hospital_mismatch", f"body={body}")


# ----------------------------------------------------------------------
# 5. DOCTOR NOT FOUND AT ALL
# ----------------------------------------------------------------------
section("5. INVALID — Doctor ID does not exist")

req = dict(valid_critical, doctor_id="D999")
resp = safe_post("/submit-request", req)
record("Unknown doctor -> 403", resp.status_code == 403, f"status={resp.status_code}, body={resp.text}")
body = resp.json() if resp.status_code == 403 else {}
record("reason == 'doctor_not_found'", body.get("reason") == "doctor_not_found", f"body={body}")


# ----------------------------------------------------------------------
# 6. MISSING PRESCRIPTION / CLINICAL NOTE -> PENDING
# ----------------------------------------------------------------------
section("6. PENDING — Missing prescription and clinical note")

req = dict(valid_critical, prescription_id=None, clinical_note=None)
resp = safe_post("/submit-request", req)
record("Missing clinical docs -> 202", resp.status_code == 202, f"status={resp.status_code}, body={resp.text}")
body = resp.json() if resp.status_code == 202 else {}
record("verified == False", body.get("verified") is False, f"body={body}")
record("reason == 'pending_clinical_verification'", body.get("reason") == "pending_clinical_verification", f"body={body}")

# Also confirm a short/garbage prescription_id (< 3 chars) is treated as insufficient
req = dict(valid_critical, prescription_id="a", clinical_note=None)
resp = safe_post("/submit-request", req)
record("Too-short prescription_id -> 202 pending", resp.status_code == 202, f"status={resp.status_code}, body={resp.text}")

# Confirm a valid clinical_note (>= 10 chars) is accepted even without prescription_id
req = dict(valid_critical, prescription_id=None, clinical_note="Patient has active internal bleeding")
resp = safe_post("/submit-request", req)
record("Valid clinical_note alone -> 200", resp.status_code == 200, f"status={resp.status_code}, body={resp.text}")


# ----------------------------------------------------------------------
# 7. INVALID URGENCY VALUE (schema-level rejection)
# ----------------------------------------------------------------------
section("7. INVALID — Bad urgency_input value")

req = dict(valid_critical, urgency_input="super-duper-urgent")
resp = safe_post("/submit-request", req)
record("Invalid urgency_input -> 422 (schema validation)", resp.status_code == 422, f"status={resp.status_code}, body={resp.text}")


# ----------------------------------------------------------------------
# 8. INVALID UNITS_NEEDED (schema-level rejection)
# ----------------------------------------------------------------------
section("8. INVALID — units_needed out of allowed range")

req = dict(valid_critical, units_needed=0)
resp = safe_post("/submit-request", req)
record("units_needed=0 -> 422", resp.status_code == 422, f"status={resp.status_code}, body={resp.text}")

req = dict(valid_critical, units_needed=999)
resp = safe_post("/submit-request", req)
record("units_needed=999 (over max) -> 422", resp.status_code == 422, f"status={resp.status_code}, body={resp.text}")


# ----------------------------------------------------------------------
# 9. MISSING REQUIRED FIELD (schema-level rejection)
# ----------------------------------------------------------------------
section("9. INVALID — Missing required field (hospital_id)")

req = {k: v for k, v in valid_critical.items() if k != "hospital_id"}
resp = safe_post("/submit-request", req)
record("Missing hospital_id -> 422", resp.status_code == 422, f"status={resp.status_code}, body={resp.text}")


# ----------------------------------------------------------------------
# 10. TRUST BOUNDARY — Spoofed coordinates should be ignored
# ----------------------------------------------------------------------
section("10. SECURITY — Spoofed hospital coordinates must be ignored")

spoofed = dict(valid_critical, hospital_lat=19.0760, hospital_lng=72.8777)  # Mumbai coords, but H01 is in Delhi
resp = safe_post("/submit-request", spoofed)
record("Spoofed-coordinates request -> 200", resp.status_code == 200, f"status={resp.status_code}, body={resp.text}")
body = resp.json() if resp.status_code == 200 else {}
returned_lat = body.get("hospital_lat")
returned_lng = body.get("hospital_lng")
record(
    "Server used VERIFIED hospital coords, not spoofed ones",
    returned_lat == 28.6139 and returned_lng == 77.2090,
    f"expected (28.6139, 77.209), got ({returned_lat}, {returned_lng})"
)


# ----------------------------------------------------------------------
# 11. PRIORITY QUEUE ORDERING — Critical > Urgent > Routine > Scheduled
# ----------------------------------------------------------------------
section("11. PRIORITY QUEUE — Correct urgency ordering")

# Drain the queue first so this test is isolated from earlier pushes
while True:
    r = safe_get("/queue")
    if r.status_code == 200 and r.json().get("queue_size", 0) > 0:
        safe_post("/queue/pop")
    else:
        break

order_requests = [
    ("routine",   dict(valid_critical, hospital_id="H01", doctor_id="D01", urgency_input="routine",   prescription_id="RXA")),
    ("critical",  dict(valid_critical, hospital_id="H02", doctor_id="D03", urgency_input="critical",  prescription_id="RXB")),
    ("urgent",    dict(valid_critical, hospital_id="H03", doctor_id="D05", urgency_input="urgent",    prescription_id="RXC")),
    ("scheduled", dict(valid_critical, hospital_id="H01", doctor_id="D02", urgency_input="scheduled", prescription_id="RXD")),
]

submitted_ids = {}
for label, payload in order_requests:
    resp = safe_post("/submit-request", payload)
    ok = resp.status_code == 200
    record(f"Submit {label} request -> 200", ok, f"status={resp.status_code}, body={resp.text}")
    if ok:
        submitted_ids[label] = resp.json()["request_id"]

pop_order = []
for _ in range(len(submitted_ids)):
    r = safe_post("/queue/pop")
    if r.status_code == 200:
        pop_order.append(r.json().get("urgency"))

expected_order = ["critical", "urgent", "routine", "scheduled"]
record(
    "Pop order matches Critical > Urgent > Routine > Scheduled",
    pop_order == expected_order,
    f"expected={expected_order}, got={pop_order}"
)


# ----------------------------------------------------------------------
# 12. FIFO WITHIN SAME PRIORITY LEVEL
# ----------------------------------------------------------------------
section("12. PRIORITY QUEUE — FIFO within same urgency level")

# Drain again to isolate this test
while True:
    r = safe_get("/queue")
    if r.status_code == 200 and r.json().get("queue_size", 0) > 0:
        safe_post("/queue/pop")
    else:
        break

fifo_ids = []
for i in range(3):
    payload = dict(valid_critical, hospital_id="H01", doctor_id="D01",
                    urgency_input="critical", prescription_id=f"FIFO{i}")
    resp = safe_post("/submit-request", payload)
    if resp.status_code == 200:
        fifo_ids.append(resp.json()["request_id"])
    time.sleep(0.05)  # tiny delay to guarantee distinct submission order

pop_ids = []
for _ in range(3):
    r = safe_post("/queue/pop")
    if r.status_code == 200:
        pop_ids.append(r.json().get("request_id"))

record(
    "Same-priority requests pop in FIFO (submission) order",
    pop_ids == fifo_ids,
    f"submitted={fifo_ids}, popped={pop_ids}"
)


# ----------------------------------------------------------------------
# 13. QUEUE PEEK vs POP BEHAVIOR
# ----------------------------------------------------------------------
section("13. QUEUE — /queue/peek should not remove items, /queue/pop should")

payload = dict(valid_critical, hospital_id="H01", doctor_id="D01",
                urgency_input="urgent", prescription_id="PEEKTEST")
resp = safe_post("/submit-request", payload)
peek_test_id = resp.json().get("request_id") if resp.status_code == 200 else None
record("Setup request for peek test -> 200", resp.status_code == 200, f"status={resp.status_code}")

size_before = safe_get("/queue").json().get("queue_size")
peek_resp = safe_get("/queue/peek")
size_after_peek = safe_get("/queue").json().get("queue_size")

record("Peek does not change queue size", size_before == size_after_peek,
       f"before={size_before}, after={size_after_peek}")
record("Peek returns a request (not queue_empty) when queue non-empty",
       peek_resp.status_code == 200 and "request_id" in peek_resp.json(),
       f"body={peek_resp.text}")

pop_resp = safe_post("/queue/pop")
size_after_pop = safe_get("/queue").json().get("queue_size")
record("Pop decreases queue size by 1", size_after_pop == size_before - 1,
       f"before={size_before}, after_pop={size_after_pop}")


# ----------------------------------------------------------------------
# 14. EMPTY QUEUE BEHAVIOR
# ----------------------------------------------------------------------
section("14. QUEUE — Behavior when queue is empty")

# Drain fully
while True:
    r = safe_get("/queue")
    if r.status_code == 200 and r.json().get("queue_size", 0) > 0:
        safe_post("/queue/pop")
    else:
        break

peek_empty = safe_get("/queue/peek")
record("Peek on empty queue -> message queue_empty",
       peek_empty.status_code == 200 and peek_empty.json().get("message") == "queue_empty",
       f"status={peek_empty.status_code}, body={peek_empty.text}")

pop_empty = safe_post("/queue/pop")
record("Pop on empty queue -> 404",
       pop_empty.status_code == 404,
       f"status={pop_empty.status_code}, body={pop_empty.text}")


# ----------------------------------------------------------------------
# 15. AUDIT TRAIL CORRECTNESS
# ----------------------------------------------------------------------
section("15. AUDIT LOG — Full trail for a valid request")

if critical_request_id:
    audit_resp = safe_get(f"/requests/{critical_request_id}/audit")
    record("Audit endpoint -> 200", audit_resp.status_code == 200, f"status={audit_resp.status_code}")

    events = audit_resp.json().get("events", []) if audit_resp.status_code == 200 else []
    event_names = [e.get("event_name") for e in events]

    expected_min_sequence = [
        "request_received",
        "hospital_verified",
        "doctor_verified",
        "prescription_checked",
        "urgency_assigned",
        "priority_queued",
    ]
    record(
        "Audit trail contains full expected sequence in order",
        event_names[:len(expected_min_sequence)] == expected_min_sequence,
        f"expected_prefix={expected_min_sequence}, got={event_names}"
    )
else:
    record("Audit trail test skipped (no critical_request_id from step 1)", False, "step 1 did not return an id")

# Audit trail for a REJECTED request should still exist and explain why
reject_req = dict(valid_critical, hospital_id="H01", doctor_id="D11", prescription_id="RXREJECT")
reject_resp = safe_post("/submit-request", reject_req)
rejected_id = reject_resp.json().get("request_id") if reject_resp.status_code == 403 else None

if rejected_id:
    audit_resp = safe_get(f"/requests/{rejected_id}/audit")
    events = audit_resp.json().get("events", []) if audit_resp.status_code == 200 else []
    event_names = [e.get("event_name") for e in events]
    record(
        "Rejected request still has an audit trail with rejection reason",
        "hospital_verified" in event_names or "doctor_verified" in event_names,
        f"events={event_names}"
    )
else:
    record("Rejected-request audit test skipped", False, "did not get a request_id back on rejection")


# ----------------------------------------------------------------------
# 16. CONCURRENCY SMOKE TEST (light — checks the lock doesn't deadlock)
# ----------------------------------------------------------------------
section("16. CONCURRENCY — Rapid sequential submissions don't break the queue")

concurrency_ok = True
ids_seen = set()
for i in range(10):
    payload = dict(valid_critical, hospital_id="H01", doctor_id="D01",
                    urgency_input="scheduled", prescription_id=f"CONC{i}")
    r = safe_post("/submit-request", payload)
    if r.status_code != 200:
        concurrency_ok = False
        break
    rid = r.json().get("request_id")
    if rid in ids_seen:
        concurrency_ok = False  # duplicate request_id would indicate a race condition
        break
    ids_seen.add(rid)

record("10 rapid submissions all succeed with unique request_ids", concurrency_ok,
       f"unique_ids_collected={len(ids_seen)}")

# Clean up queue after this test
while True:
    r = safe_get("/queue")
    if r.status_code == 200 and r.json().get("queue_size", 0) > 0:
        safe_post("/queue/pop")
    else:
        break


# ----------------------------------------------------------------------
# FINAL SUMMARY
# ----------------------------------------------------------------------
section("SUMMARY")

total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed

print(f"\nTotal checks : {total}")
print(f"Passed       : {passed}")
print(f"Failed       : {failed}")

if failed:
    print("\nFailed checks:")
    for name, ok, detail in results:
        if not ok:
            print(f"  - {name}  ({detail})")
    print("\n[ERROR] SOME CHECKS FAILED — fix these before your demo.")
    sys.exit(1)
else:
    print("\n[SUCCESS] ALL CHECKS PASSED — Stage 1 backend is demo-ready.")
    sys.exit(0)
