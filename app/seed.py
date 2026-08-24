from app.database import get_connection
from app.auth.security import hash_password


HOSPITALS = [
    ("H01", "City Care Hospital", 28.6139, 77.2090, 1),
    ("H02", "Metro General Hospital", 28.6280, 77.2180, 1),
    ("H03", "Shanti Medical Centre", 28.5355, 77.3910, 1),
    ("H04", "Apollo Demo Hospital", 28.5672, 77.2100, 1),
    ("H05", "LifeLine Hospital", 28.4595, 77.0266, 1),
    ("H06", "National Trauma Centre", 28.5672, 77.2430, 1),
    ("H07", "Green Valley Hospital", 28.7041, 77.1025, 1),
    ("H08", "Hope Medical Institute", 28.6692, 77.4538, 1),
    ("H09", "Sunrise Hospital", 28.4089, 77.3178, 1),
    ("H10", "CarePlus Hospital", 28.6130, 77.3100, 1),
]


DOCTORS = [
    ("D01", "Dr. Arjun Sharma", "H01", 1),
    ("D02", "Dr. Priya Verma", "H01", 1),

    ("D03", "Dr. Rahul Singh", "H02", 1),
    ("D04", "Dr. Neha Kapoor", "H02", 1),

    ("D05", "Dr. Amit Gupta", "H03", 1),

    ("D06", "Dr. Riya Mehta", "H04", 1),
    ("D07", "Dr. Karan Malhotra", "H05", 1),

    ("D08", "Dr. Simran Kaur", "H06", 1),
    ("D09", "Dr. Aditya Jain", "H07", 1),

    ("D10", "Dr. Ananya Rao", "H08", 1),

    # Unauthorized doctor for testing
    ("D11", "Dr. Test Unauthorized", "H01", 0),

    # Doctor belongs to another hospital
    ("D12", "Dr. Wrong Hospital", "H03", 1),
]

BLOOD_BANKS = [
    ("B01", "RaktSetu Central Blood Bank", 28.6200, 77.2100, "Central Delhi", "011-40000001", 1),
    ("B02", "LifeBlood Blood Bank", 28.6280, 77.2180, "North Delhi", "011-40000002", 1),
    ("B03", "National Blood Centre", 28.5672, 77.2430, "South Delhi", "011-40000003", 1),
    ("B04", "RedCare Blood Bank", 28.5355, 77.3910, "Noida", "011-40000004", 1),
    ("B05", "Hope Blood Services", 28.7041, 77.1025, "West Delhi", "011-40000005", 1),
]

BLOOD_INVENTORY = [
    ("B01", "O+", 18, "2026-08-28"),
    ("B01", "O-", 6, "2026-08-25"),
    ("B01", "A+", 14, "2026-08-27"),
    ("B01", "A-", 4, "2026-08-24"),
    ("B01", "B+", 12, "2026-08-29"),
    ("B01", "B-", 3, "2026-08-26"),
    ("B01", "AB+", 8, "2026-08-30"),
    ("B01", "AB-", 2, "2026-08-25"),

    ("B02", "O+", 10, "2026-08-27"),
    ("B02", "O-", 12, "2026-08-25"),
    ("B02", "A+", 16, "2026-08-29"),
    ("B02", "A-", 5, "2026-08-26"),
    ("B02", "B+", 9, "2026-08-28"),
    ("B02", "B-", 2, "2026-08-24"),
    ("B02", "AB+", 6, "2026-08-30"),
    ("B02", "AB-", 1, "2026-08-25"),

    ("B03", "O+", 20, "2026-08-29"),
    ("B03", "O-", 8, "2026-08-26"),
    ("B03", "A+", 11, "2026-08-27"),
    ("B03", "A-", 3, "2026-08-25"),
    ("B03", "B+", 15, "2026-08-30"),
    ("B03", "B-", 4, "2026-08-27"),
    ("B03", "AB+", 7, "2026-08-28"),
    ("B03", "AB-", 2, "2026-08-26"),

    ("B04", "O+", 9, "2026-08-27"),
    ("B04", "O-", 4, "2026-08-25"),
    ("B04", "A+", 13, "2026-08-29"),
    ("B04", "A-", 2, "2026-08-24"),
    ("B04", "B+", 8, "2026-08-28"),
    ("B04", "B-", 3, "2026-08-26"),
    ("B04", "AB+", 5, "2026-08-30"),
    ("B04", "AB-", 1, "2026-08-25"),

    ("B05", "O+", 15, "2026-08-28"),
    ("B05", "O-", 5, "2026-08-26"),
    ("B05", "A+", 10, "2026-08-29"),
    ("B05", "A-", 4, "2026-08-25"),
    ("B05", "B+", 11, "2026-08-30"),
    ("B05", "B-", 2, "2026-08-27"),
    ("B05", "AB+", 6, "2026-08-29"),
    ("B05", "AB-", 1, "2026-08-26"),
]

USERS = [
    ("U0001", "dispatcher1", "Dispatcher@123", "dispatcher", None, None, None),
    ("U0002", "provider1", "Provider@123", "provider", None, None, "B01"),
    ("U0003", "provider2", "Provider@123", "provider", None, None, "B02"),
    ("U0004", "requester1", "Requester@123", "requester", "H01", "D01", None),
    ("U0005", "requester2", "Requester@123", "requester", "H02", "D03", None),
    ("U0006", "patient1", "Patient@123", "patient", None, None, None),
]

SAMPLE_REQUESTS = [
    ("R1001", "H01", "D01", "O-", 3, "critical", 28.6139, 77.2090, 1, "queued", "RX1001", "Trauma patient in ER with severe blood loss.", "2026-08-25 01:00:00"),
    ("R1002", "H02", "D03", "A+", 4, "critical", 28.6280, 77.2180, 1, "queued", "RX1002", "Emergency cardiac surgery required.", "2026-08-25 01:05:00"),
    ("R1003", "H03", "D05", "B-", 2, "urgent", 28.5355, 77.3910, 1, "queued", "RX1003", "Post-partum hemorrhage management.", "2026-08-25 01:10:00"),
    ("R1004", "H04", "D06", "O+", 5, "urgent", 28.5672, 77.2100, 1, "queued", "RX1004", "Major orthopedic surgery transfusion.", "2026-08-25 01:15:00"),
    ("R1005", "H05", "D07", "AB-", 1, "critical", 28.4595, 77.0266, 1, "queued", "RX1005", "Rare blood group trauma case.", "2026-08-25 01:20:00"),
    ("R1006", "H06", "D08", "A-", 3, "routine", 28.5672, 77.2430, 1, "queued", "RX1006", "Routine oncology maintenance transfusion.", "2026-08-25 01:25:00"),
    ("R1007", "H07", "D09", "B+", 4, "routine", 28.7041, 77.1025, 1, "queued", "RX1007", "Thalassemia routine replenishment.", "2026-08-25 01:30:00"),
    ("R1008", "H08", "D10", "AB+", 2, "scheduled", 28.6692, 77.4538, 1, "queued", "RX1008", "Elective vascular procedure scheduled.", "2026-08-25 01:35:00"),
    ("R1009", "H01", "D02", "O-", 2, "scheduled", 28.6139, 77.2090, 1, "queued", "RX1009", "Scheduled surgical buffer stock.", "2026-08-25 01:40:00"),
]


def seed_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executemany("""
        INSERT OR IGNORE INTO hospitals
        (hospital_id, name, lat, lng, is_active)
        VALUES (?, ?, ?, ?, ?)
    """, HOSPITALS)

    cursor.executemany("""
        INSERT OR IGNORE INTO doctors
        (doctor_id, name, hospital_id, is_authorized)
        VALUES (?, ?, ?, ?)
    """, DOCTORS)

    cursor.executemany("""
        INSERT OR IGNORE INTO blood_banks
        (bank_id, name, lat, lng, address, contact_number, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, BLOOD_BANKS)

    existing_inv = cursor.execute("SELECT COUNT(*) FROM blood_inventory").fetchone()[0]
    if existing_inv == 0:
        cursor.executemany("""
            INSERT INTO blood_inventory
            (bank_id, blood_type, units, expiry_date, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, BLOOD_INVENTORY)

    for user_id, username, password, role, hospital_id, doctor_id, bank_id in USERS:
        cursor.execute(
        """
        INSERT OR IGNORE INTO users
        (
            user_id,
            username,
            password_hash,
            role,
            hospital_id,
            doctor_id,
            bank_id,
            is_active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            user_id,
            username,
            hash_password(password),
            role,
            hospital_id,
            doctor_id,
            bank_id
        )
    )

    # Clean duplicate/excess requests
    cursor.execute("DELETE FROM blood_requests WHERE rowid NOT IN (SELECT MIN(rowid) FROM blood_requests GROUP BY blood_type, units_needed, urgency, hospital_id, doctor_id)")

    existing_reqs = cursor.execute("SELECT COUNT(*) FROM blood_requests WHERE status IN ('queued', 'verified')").fetchone()[0]
    if existing_reqs == 0:
        cursor.executemany("""
            INSERT OR IGNORE INTO blood_requests
            (request_id, hospital_id, doctor_id, blood_type, units_needed, urgency, hospital_lat, hospital_lng, verified, status, prescription_id, clinical_note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, SAMPLE_REQUESTS)

    conn.commit()
    conn.close()

    try:
        from app.priority_queue import load_queue_from_db
        load_queue_from_db()
    except Exception:
        pass


if __name__ == "__main__":
    from app.database import init_db

    init_db()
    seed_database()

    print("Database initialized and seeded.")