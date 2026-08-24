import sqlite3

conn = sqlite3.connect('data/raktsetu.db')
conn.execute("UPDATE blood_requests SET status = 'queued', verified = 1 WHERE request_id LIKE 'R%'")
conn.execute("DELETE FROM audit_log WHERE event_name = 'allocation_details'")
conn.commit()
conn.close()

print("Database reset successfully! All requests are now in QUEUED status.")
