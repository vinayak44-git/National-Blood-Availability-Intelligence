from math import sqrt
from datetime import datetime, timezone

from fastapi import HTTPException

from app.database import get_connection
from app.audit import log_event


def calculate_distance(lat1, lng1, lat2, lng2):
    return sqrt(
        (lat1 - lat2) ** 2 +
        (lng1 - lng2) ** 2
    ) * 111


def get_compatible_blood_types(blood_type):
    compatibility = {
        "O-": ["O-"],
        "O+": ["O-", "O+"],
        "A-": ["A-"],
        "A+": ["A-", "A+"],
        "B-": ["B-"],
        "B+": ["B-", "B+"],
        "AB-": ["AB-", "A-", "B-", "O-"],
        "AB+": ["AB-", "AB+", "A-", "A+", "B-", "B+", "O-", "O+"]
    }

    return compatibility.get(blood_type, [blood_type])


def fulfill_request(request_id):
    conn = get_connection()

    request = conn.execute(
        """
        SELECT
            request_id,
            hospital_id,
            blood_type,
            units_needed,
            urgency,
            hospital_lat,
            hospital_lng,
            verified,
            status
        FROM blood_requests
        WHERE request_id = ?
        """,
        (request_id,)
    ).fetchone()

    if not request:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Blood request not found"
        )

    if not request["verified"]:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Request is not verified"
        )

    if request["status"] not in (
        "queued",
        "sent_to_fulfillment"
    ):
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Request cannot be fulfilled from status: {request['status']}"
        )

    compatible_types = get_compatible_blood_types(
        request["blood_type"]
    )

    placeholders = ",".join("?" for _ in compatible_types)

    inventory_rows = conn.execute(
        f"""
        SELECT
            bi.inventory_id,
            bi.bank_id,
            bi.blood_type,
            bi.units,
            bi.expiry_date,
            bb.name AS bank_name,
            bb.lat,
            bb.lng
        FROM blood_inventory bi
        JOIN blood_banks bb
            ON bi.bank_id = bb.bank_id
        WHERE bi.blood_type IN ({placeholders})
          AND bi.units > 0
          AND bi.expiry_date >= date('now')
          AND bb.is_active = 1
        ORDER BY bi.expiry_date ASC
        """,
        compatible_types
    ).fetchall()

    inventory = []

    for row in inventory_rows:
        distance = calculate_distance(
            request["hospital_lat"],
            request["hospital_lng"],
            row["lat"],
            row["lng"]
        )

        inventory.append({
            "inventory_id": row["inventory_id"],
            "bank_id": row["bank_id"],
            "bank_name": row["bank_name"],
            "blood_type": row["blood_type"],
            "units": row["units"],
            "expiry_date": row["expiry_date"],
            "lat": row["lat"],
            "lng": row["lng"],
            "distance_km": distance
        })

    inventory.sort(
        key=lambda item: (
            item["distance_km"],
            item["expiry_date"]
        )
    )

    remaining = request["units_needed"]
    allocations = []

    try:
        for item in inventory:
            if remaining <= 0:
                break

            allocated = min(
                remaining,
                item["units"]
            )

            new_units = item["units"] - allocated

            conn.execute(
                """
                UPDATE blood_inventory
                SET units = ?,
                    updated_at = ?
                WHERE inventory_id = ?
                  AND units >= ?
                """,
                (
                    new_units,
                    datetime.now(timezone.utc).isoformat(),
                    item["inventory_id"],
                    allocated
                )
            )

            if conn.execute("SELECT changes()").fetchone()[0] != 1:
                raise Exception(
                    f"Inventory update failed for {item['inventory_id']}"
                )

            allocations.append({
                "inventory_id": item["inventory_id"],
                "bank_id": item["bank_id"],
                "bank_name": item["bank_name"],
                "blood_type": item["blood_type"],
                "units": allocated,
                "remaining_stock": new_units,
                "distance_km": round(item["distance_km"], 2),
                "lat": item["lat"],
                "lng": item["lng"],
                "expiry_date": item["expiry_date"]
            })

            remaining -= allocated

        total_allocated = sum(
            allocation["units"]
            for allocation in allocations
        )
        now = datetime.now(timezone.utc).isoformat()

        import json

        if total_allocated > 0:
            new_status = "fulfilled" if remaining == 0 else "partially_fulfilled"
            conn.execute(
                """
                UPDATE blood_requests
                SET status = ?
                WHERE request_id = ?
                """,
                (new_status, request_id)
            )

            conn.commit()
            conn.close()

            log_event(
                request_id,
                "request_fulfilled" if remaining == 0 else "request_partially_fulfilled",
                f"Allocated {total_allocated}/{request['units_needed']} units across {len(allocations)} blood bank allocation(s)"
            )

            log_event(
                request_id,
                "allocation_details",
                json.dumps(allocations)
            )

            return {
                "request_id": request_id,
                "blood_type": request["blood_type"],
                "units_requested": request["units_needed"],
                "units_allocated": total_allocated,
                "status": new_status,
                "timestamp": now,
                "allocations": allocations
            }
        else:
            conn.execute(
                """
                UPDATE blood_requests
                SET status = 'queued_insufficient_stock'
                WHERE request_id = ?
                """,
                (request_id,)
            )

            conn.commit()
            conn.close()

            log_event(
                request_id,
                "insufficient_stock",
                f"Zero compatible inventory available across network for {request['blood_type']}"
            )

            return {
                "request_id": request_id,
                "blood_type": request["blood_type"],
                "units_requested": request["units_needed"],
                "units_allocated": 0,
                "status": "queued_insufficient_stock",
                "timestamp": now,
                "allocations": []
            }

    except HTTPException:
        raise

    except Exception:
        conn.rollback()
        conn.close()
        raise


def preview_fulfillment(request_id: str):
    conn = get_connection()
    request = conn.execute(
        """
        SELECT request_id, hospital_id, blood_type, units_needed, urgency, hospital_lat, hospital_lng, verified, status
        FROM blood_requests
        WHERE request_id = ?
        """,
        (request_id,)
    ).fetchone()

    if not request:
        conn.close()
        raise HTTPException(status_code=404, detail="Blood request not found")

    compatible_types = get_compatible_blood_types(request["blood_type"])
    placeholders = ",".join("?" for _ in compatible_types)

    inventory_rows = conn.execute(
        f"""
        SELECT bi.inventory_id, bi.bank_id, bi.blood_type, bi.units, bi.expiry_date, bb.name AS bank_name, bb.lat, bb.lng
        FROM blood_inventory bi
        JOIN blood_banks bb ON bi.bank_id = bb.bank_id
        WHERE bi.blood_type IN ({placeholders})
          AND bi.units > 0
          AND bi.expiry_date >= date('now')
          AND bb.is_active = 1
        ORDER BY bi.expiry_date ASC
        """,
        compatible_types
    ).fetchall()
    conn.close()

    inventory = []
    for row in inventory_rows:
        distance = calculate_distance(
            request["hospital_lat"],
            request["hospital_lng"],
            row["lat"],
            row["lng"]
        )
        inventory.append({
            "inventory_id": row["inventory_id"],
            "bank_id": row["bank_id"],
            "bank_name": row["bank_name"],
            "blood_type": row["blood_type"],
            "units": row["units"],
            "expiry_date": row["expiry_date"],
            "lat": row["lat"],
            "lng": row["lng"],
            "distance_km": distance
        })

    inventory.sort(key=lambda item: (item["distance_km"], item["expiry_date"]))

    remaining = request["units_needed"]
    allocations = []
    for item in inventory:
        if remaining <= 0:
            break
        allocated = min(remaining, item["units"])
        new_units = item["units"] - allocated
        allocations.append({
            "inventory_id": item["inventory_id"],
            "bank_id": item["bank_id"],
            "bank_name": item["bank_name"],
            "blood_type": item["blood_type"],
            "units": allocated,
            "remaining_stock": new_units,
            "distance_km": round(item["distance_km"], 2),
            "lat": item["lat"],
            "lng": item["lng"],
            "expiry_date": item["expiry_date"]
        })
        remaining -= allocated

    total_allocated = sum(a["units"] for a in allocations)
    return {
        "request_id": request_id,
        "blood_type": request["blood_type"],
        "units_requested": request["units_needed"],
        "units_allocated": total_allocated,
        "status": "fulfilled" if remaining == 0 else ("partially_fulfilled" if total_allocated > 0 else "queued_insufficient_stock"),
        "allocations": allocations
    }