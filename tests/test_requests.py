import unittest
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

class TestRaktSetuVerification(unittest.TestCase):

    def setUp(self):
        self.session = requests.Session()
        try:
            r = self.session.get(f"{BASE_URL}/")
            self.assertEqual(r.status_code, 200)
            login_resp = self.session.post(
                f"{BASE_URL}/auth/login",
                json={"username": "dispatcher1", "password": "Dispatcher@123"},
                timeout=5
            )
            self.assertEqual(login_resp.status_code, 200)
        except requests.exceptions.ConnectionError:
            self.fail("FastAPI server is not running on http://127.0.0.1:8000. Please start it using: uvicorn app.main:app --reload")

    def test_01_valid_critical_request(self):
        payload = {
            "hospital_id": "H01",
            "doctor_id": "D01",
            "blood_type": "O-",
            "units_needed": 3,
            "urgency_input": "critical",
            "prescription_id": "RX10293",
            "hospital_lat": 28.6139,
            "hospital_lng": 77.2090
        }
        response = self.session.post(f"{BASE_URL}/submit-request", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["verified"])
        self.assertEqual(data["urgency"], "critical")
        self.assertIn("request_id", data)
        req_id = data["request_id"]
        
        # Verify Audit Trail
        audit_resp = self.session.get(f"{BASE_URL}/requests/{req_id}/audit")
        self.assertEqual(audit_resp.status_code, 200)
        audit_data = audit_resp.json()
        events = [e["event_name"] for e in audit_data["events"]]
        self.assertIn("request_received", events)
        self.assertIn("hospital_verified", events)
        self.assertIn("doctor_verified", events)
        self.assertIn("prescription_checked", events)
        self.assertIn("urgency_assigned", events)
        self.assertIn("priority_queued", events)

    def test_02_hospital_not_found(self):
        payload = {
            "hospital_id": "H999",
            "doctor_id": "D01",
            "blood_type": "O-",
            "units_needed": 3,
            "urgency_input": "critical",
            "prescription_id": "RX10293",
            "hospital_lat": 28.6139,
            "hospital_lng": 77.2090
        }
        response = self.session.post(f"{BASE_URL}/submit-request", json=payload)
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data["verified"])
        self.assertEqual(data["reason"], "hospital_not_found")

    def test_03_doctor_not_authorized(self):
        payload = {
            "hospital_id": "H01",
            "doctor_id": "D11",
            "blood_type": "O-",
            "units_needed": 3,
            "urgency_input": "critical",
            "prescription_id": "RX10293",
            "hospital_lat": 28.6139,
            "hospital_lng": 77.2090
        }
        response = self.session.post(f"{BASE_URL}/submit-request", json=payload)
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data["verified"])
        self.assertEqual(data["reason"], "doctor_not_authorized")

    def test_04_doctor_hospital_mismatch(self):
        payload = {
            "hospital_id": "H01",
            "doctor_id": "D12",
            "blood_type": "O-",
            "units_needed": 3,
            "urgency_input": "critical",
            "prescription_id": "RX10293",
            "hospital_lat": 28.6139,
            "hospital_lng": 77.2090
        }
        response = self.session.post(f"{BASE_URL}/submit-request", json=payload)
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data["verified"])
        self.assertEqual(data["reason"], "doctor_hospital_mismatch")

    def test_05_missing_prescription(self):
        payload = {
            "hospital_id": "H01",
            "doctor_id": "D01",
            "blood_type": "O-",
            "units_needed": 3,
            "urgency_input": "critical",
            "prescription_id": None,
            "clinical_note": None,
            "hospital_lat": 28.6139,
            "hospital_lng": 77.2090
        }
        response = self.session.post(f"{BASE_URL}/submit-request", json=payload)
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertFalse(data["verified"])
        self.assertEqual(data["reason"], "pending_clinical_verification")

    def test_06_priority_queue_and_fifo(self):
        # Empty queue first by popping everything
        while True:
            pop_resp = self.session.post(f"{BASE_URL}/queue/pop")
            if pop_resp.status_code == 404:
                break
        
        # Submit:
        # 1. Routine
        req_a = {
            "hospital_id": "H01",
            "doctor_id": "D01",
            "blood_type": "O-",
            "units_needed": 2,
            "urgency_input": "routine",
            "prescription_id": "RX001",
            "hospital_lat": 28.6139,
            "hospital_lng": 77.2090
        }
        # 2. Critical
        req_b = {
            "hospital_id": "H02",
            "doctor_id": "D03",
            "blood_type": "A+",
            "units_needed": 1,
            "urgency_input": "critical",
            "prescription_id": "RX002",
            "hospital_lat": 28.6280,
            "hospital_lng": 77.2180
        }
        # 3. Urgent
        req_c = {
            "hospital_id": "H03",
            "doctor_id": "D05",
            "blood_type": "B+",
            "units_needed": 2,
            "urgency_input": "urgent",
            "prescription_id": "RX003",
            "hospital_lat": 28.5355,
            "hospital_lng": 77.3910
        }
        # 4. Critical (FIFO check)
        req_d = {
            "hospital_id": "H01",
            "doctor_id": "D02",
            "blood_type": "O-",
            "units_needed": 1,
            "urgency_input": "critical",
            "prescription_id": "RX004",
            "hospital_lat": 28.6139,
            "hospital_lng": 77.2090
        }

        resp_a = self.session.post(f"{BASE_URL}/submit-request", json=req_a).json()
        resp_b = self.session.post(f"{BASE_URL}/submit-request", json=req_b).json()
        resp_c = self.session.post(f"{BASE_URL}/submit-request", json=req_c).json()
        resp_d = self.session.post(f"{BASE_URL}/submit-request", json=req_d).json()

        # Pop 1 -> should be Critical req_b (submitted first)
        pop1 = self.session.post(f"{BASE_URL}/queue/pop").json()
        self.assertEqual(pop1["request_id"], resp_b["request_id"])

        # Pop 2 -> should be Critical req_d (submitted second)
        pop2 = self.session.post(f"{BASE_URL}/queue/pop").json()
        self.assertEqual(pop2["request_id"], resp_d["request_id"])

        # Pop 3 -> should be Urgent req_c
        pop3 = self.session.post(f"{BASE_URL}/queue/pop").json()
        self.assertEqual(pop3["request_id"], resp_c["request_id"])

        # Pop 4 -> should be Routine req_a
        pop4 = self.session.post(f"{BASE_URL}/queue/pop").json()
        self.assertEqual(pop4["request_id"], resp_a["request_id"])

    def test_07_stats_endpoints(self):
        # Verify stats/queue
        q_stats = self.session.get(f"{BASE_URL}/stats/queue").json()
        self.assertIn("critical", q_stats)
        self.assertIn("urgent", q_stats)
        self.assertIn("routine", q_stats)
        
        # Verify stats/verification
        v_stats = self.session.get(f"{BASE_URL}/stats/verification").json()
        self.assertIn("requests_received", v_stats)
        self.assertIn("verified", v_stats)
        self.assertIn("rejected", v_stats)
        self.assertIn("pending_clinical", v_stats)
        
        # Verify stats/rejections
        r_stats = self.session.get(f"{BASE_URL}/stats/rejections").json()
        self.assertIn("doctor_not_authorized", r_stats)
        self.assertIn("hospital_not_found", r_stats)

if __name__ == "__main__":
    unittest.main()
