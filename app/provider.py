from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.routes import require_role
from app.database import get_connection


router = APIRouter(
    prefix="/provider",
    tags=["Provider"]
)


@router.get("/inventory")
def get_inventory(
    current_user=Depends(require_role("provider"))
):
    bank_id = current_user.get("bank_id")

    if not bank_id:
        raise HTTPException(
            status_code=400,
            detail="Provider account is not linked to a blood bank"
        )

    conn = get_connection()

    bank = conn.execute(
        """
        SELECT
            bank_id,
            name,
            lat,
            lng,
            address,
            contact_number,
            is_active
        FROM blood_banks
        WHERE bank_id = ?
        """,
        (bank_id,)
    ).fetchone()

    if not bank:
        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Blood bank not found"
        )

    inventory = conn.execute(
        """
        SELECT
            inventory_id,
            blood_type,
            units,
            expiry_date,
            updated_at
        FROM blood_inventory
        WHERE bank_id = ?
        ORDER BY blood_type
        """,
        (bank_id,)
    ).fetchall()

    conn.close()

    return {
        "bank": dict(bank),
        "inventory": [dict(item) for item in inventory]
    }
class InventoryUpdate(BaseModel):
    units: int


@router.put("/inventory/{inventory_id}")
def update_inventory(
    inventory_id: int,
    data: InventoryUpdate,
    current_user=Depends(require_role("provider"))
):
    if data.units < 0:
        raise HTTPException(
            status_code=400,
            detail="Units cannot be negative"
        )

    bank_id = current_user.get("bank_id")

    if not bank_id:
        raise HTTPException(
            status_code=400,
            detail="Provider account is not linked to a blood bank"
        )

    conn = get_connection()

    inventory = conn.execute(
        """
        SELECT inventory_id
        FROM blood_inventory
        WHERE inventory_id = ?
          AND bank_id = ?
        """,
        (inventory_id, bank_id)
    ).fetchone()

    if not inventory:
        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Inventory item not found for this blood bank"
        )

    conn.execute(
        """
        UPDATE blood_inventory
        SET units = ?,
            updated_at = ?
        WHERE inventory_id = ?
          AND bank_id = ?
        """,
        (
            data.units,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            inventory_id,
            bank_id
        )
    )

    conn.commit()
    conn.close()

    return {
        "message": "Inventory updated successfully",
        "inventory_id": inventory_id,
        "units": data.units
    }
@router.get("/requests")
def get_provider_requests(
    current_user=Depends(require_role("provider"))
):
    bank_id = current_user.get("bank_id")

    if not bank_id:
        raise HTTPException(
            status_code=400,
            detail="Provider account is not linked to a blood bank"
        )

    conn = get_connection()

    requests = conn.execute(
        """
        SELECT
            br.request_id,
            br.hospital_id,
            h.name AS hospital_name,
            br.doctor_id,
            d.name AS doctor_name,
            br.blood_type,
            br.units_needed,
            br.urgency,
            br.hospital_lat,
            br.hospital_lng,
            br.status,
            br.prescription_id,
            br.clinical_note,
            br.created_at
        FROM blood_requests br
        JOIN hospitals h
            ON br.hospital_id = h.hospital_id
        JOIN doctors d
            ON br.doctor_id = d.doctor_id
        WHERE br.verified = 1
            AND br.status IN ('verified', 'queued', 'accepted')
        ORDER BY
            CASE br.urgency
                WHEN 'critical' THEN 1
                WHEN 'urgent' THEN 2
                WHEN 'routine' THEN 3
                WHEN 'scheduled' THEN 4
                ELSE 5
            END,
            br.created_at ASC
        """
    ).fetchall()

    conn.close()

    return {
        "bank_id": bank_id,
        "requests": [dict(request) for request in requests]
    }
@router.post("/requests/{request_id}/accept")
def accept_provider_request(
    request_id: str,
    current_user=Depends(require_role("provider"))
):
    bank_id = current_user.get("bank_id")

    if not bank_id:
        raise HTTPException(
            status_code=400,
            detail="Provider account is not linked to a blood bank"
        )

    conn = get_connection()

    request = conn.execute(
        """
        SELECT
            request_id,
            blood_type,
            units_needed,
            urgency,
            status
        FROM blood_requests
        WHERE request_id = ?
          AND verified = 1
        """,
        (request_id,)
    ).fetchone()

    if not request:
        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Blood request not found"
        )

    if request["status"] != "queued":
        conn.close()

        raise HTTPException(
            status_code=400,
            detail=f"Request cannot be accepted. Current status: {request['status']}"
        )

    inventory = conn.execute(
        """
        SELECT
            inventory_id,
            units
        FROM blood_inventory
        WHERE bank_id = ?
          AND blood_type = ?
          AND expiry_date >= date('now')
        ORDER BY expiry_date ASC
        LIMIT 1
        """,
        (
            bank_id,
            request["blood_type"]
        )
    ).fetchone()

    if not inventory:
        conn.close()

        raise HTTPException(
            status_code=400,
            detail="No available inventory for this blood type"
        )

    if inventory["units"] < request["units_needed"]:
        conn.close()

        raise HTTPException(
            status_code=400,
            detail="Insufficient blood inventory"
        )

    new_units = inventory["units"] - request["units_needed"]

    conn.execute(
        """
        UPDATE blood_inventory
        SET units = ?,
            updated_at = ?
        WHERE inventory_id = ?
        """,
        (
            new_units,
            datetime.utcnow().isoformat(),
            inventory["inventory_id"]
        )
    )

    conn.execute(
        """
        UPDATE blood_requests
        SET status = 'accepted'
        WHERE request_id = ?
        """,
        (request_id,)
    )

    conn.commit()
    conn.close()

    return {
        "message": "Blood request accepted successfully",
        "request_id": request_id,
        "blood_type": request["blood_type"],
        "units_allocated": request["units_needed"],
        "remaining_units": new_units,
        "status": "accepted"
    }

@router.post("/requests/{request_id}/dispatch")
def dispatch_provider_request(
    request_id: str,
    current_user=Depends(require_role("provider"))
):
    bank_id = current_user.get("bank_id")

    if not bank_id:
        raise HTTPException(
            status_code=400,
            detail="Provider account is not linked to a blood bank"
        )

    conn = get_connection()

    request = conn.execute(
        """
        SELECT
            request_id,
            blood_type,
            units_needed,
            urgency,
            status
        FROM blood_requests
        WHERE request_id = ?
          AND verified = 1
        """,
        (request_id,)
    ).fetchone()

    if not request:
        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Blood request not found"
        )

    if request["status"] != "accepted":
        conn.close()

        raise HTTPException(
            status_code=400,
            detail=f"Request cannot be dispatched. Current status: {request['status']}"
        )

    now = datetime.utcnow().isoformat()

    conn.execute(
        """
        UPDATE blood_requests
        SET status = 'dispatched'
        WHERE request_id = ?
        """,
        (request_id,)
    )

    conn.execute(
        """
        INSERT INTO audit_log (
            request_id,
            event_name,
            timestamp,
            details
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            request_id,
            "request_dispatched",
            now,
            f"Dispatched by blood bank {bank_id}"
        )
    )

    conn.commit()
    conn.close()

    return {
        "message": "Blood request dispatched successfully",
        "request_id": request_id,
        "blood_type": request["blood_type"],
        "units": request["units_needed"],
        "status": "dispatched",
        "timestamp": now
    }