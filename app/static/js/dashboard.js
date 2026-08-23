let mapInstance = null;
let hospitalMarker = null;
let bankMarkers = [];
let dispatchLines = [];
let activeRequestData = null;
let activeFulfillmentData = null;

const hospitalCoords = {
    "H01": { name: "City Care Hospital", lat: 28.6139, lng: 77.2090 },
    "H02": { name: "Metro General Hospital", lat: 28.6280, lng: 77.2180 },
    "H03": { name: "Shanti Medical Centre", lat: 28.5355, lng: 77.3910 },
    "H04": { name: "Apollo Demo Hospital", lat: 28.5672, lng: 77.2100 },
    "H05": { name: "LifeLine Hospital", lat: 28.4595, lng: 77.0266 },
    "H06": { name: "National Trauma Centre", lat: 28.5672, lng: 77.2430 },
    "H07": { name: "Green Valley Hospital", lat: 28.7041, lng: 77.1025 },
    "H08": { name: "Hope Medical Institute", lat: 28.6692, lng: 77.4538 },
    "H09": { name: "Sunrise Hospital", lat: 28.4089, lng: 77.3178 },
    "H10": { name: "CarePlus Hospital", lat: 28.6130, lng: 77.3100 }
};

document.addEventListener("DOMContentLoaded", () => {
    initDashboard();
    setupEventListeners();
});

function initDashboard() {
    initializeMap(28.6139, 77.2090);
    refreshStats();
    refreshQueue();
}

function setupEventListeners() {
    const popBtn = document.getElementById("popRequestBtn");

    if (popBtn) {
        popBtn.addEventListener("click", () => {
            popNextRequest();
        });
    }

    const simForm = document.getElementById("simulatorForm");

    if (simForm) {
        simForm.addEventListener("submit", (e) => {
            e.preventDefault();
            submitSimulatedRequest();
        });
    }

    const mobileMenu = document.getElementById("mobileMenu");
    const sidebar = document.getElementById("sidebar");

    if (mobileMenu && sidebar) {
        mobileMenu.addEventListener("click", () => {
            sidebar.classList.toggle("open");
        });
    }

    const simHospitalSelect = document.getElementById("simHospital");
    const simDoctorSelect = document.getElementById("simDoctor");

    if (simHospitalSelect && simDoctorSelect) {
        simHospitalSelect.addEventListener("change", () => {
            const hId = simHospitalSelect.value;

            if (hId === "H01") {
                simDoctorSelect.value = "D01";
            } else if (hId === "H02") {
                simDoctorSelect.value = "D03";
            } else if (hId === "H03") {
                simDoctorSelect.value = "D12";
            }
        });
    }
}

async function refreshStats() {
    try {
        const response = await fetch("/stats/verification");

        if (!response.ok) {
            return;
        }

        const stats = await response.json();

        const received = document.getElementById("statReceivedCount");
        const verified = document.getElementById("statVerifiedCount");
        const rejected = document.getElementById("statRejectedCount");
        const pending = document.getElementById("statPendingCount");

        if (received) {
            received.textContent = stats.requests_received || 0;
        }

        if (verified) {
            verified.textContent = stats.verified || 0;
        }

        if (rejected) {
            rejected.textContent = stats.rejected || 0;
        }

        if (pending) {
            pending.textContent = stats.pending_clinical || 0;
        }
    } catch (error) {
        console.error("Error fetching stats:", error);
    }
}

async function refreshQueue() {
    try {
        const response = await fetch("/queue");

        if (!response.ok) {
            return;
        }

        const queueData = await response.json();

        const queueList = document.getElementById("queueListContainer");
        const queueSizeBadge = document.getElementById("queueSizeBadge");
        const navQueueCount = document.getElementById("navQueueCount");

        const size = queueData.queue_size || 0;

        if (queueSizeBadge) {
            queueSizeBadge.textContent = `${size} items`;
        }

        if (navQueueCount) {
            navQueueCount.textContent = size;
        }

        if (!queueList) {
            return;
        }

        queueList.innerHTML = "";

        if (size === 0) {
            queueList.innerHTML = `
                <div class="empty-state">
                    Queue is empty. Submit a request using the simulator.
                </div>
            `;
            return;
        }

        queueData.requests.forEach((req) => {
            const item = document.createElement("div");

            item.className = "queue-item";

            if (
                activeRequestData &&
                activeRequestData.request_id === req.request_id
            ) {
                item.className += " active";
            }

            const hospName =
                hospitalCoords[req.hospital_id]?.name ||
                `Hospital ${req.hospital_id}`;

            const urgency = req.urgency || req.urgency_input || "routine";

            item.innerHTML = `
                <div class="queue-item-header">
                    <span class="queue-item-id">
                        ${escapeHtml(req.request_id)}
                    </span>

                    <span class="queue-item-priority ${escapeHtml(
                urgency.toLowerCase()
            )}">
                        ${escapeHtml(urgency)}
                    </span>
                </div>

                <div class="queue-item-body">
                    <strong>${escapeHtml(hospName)}</strong>
                    <br>
                    Requires
                    <strong>${req.units_needed} units</strong>
                    of
                    <strong>${escapeHtml(req.blood_type)}</strong>
                </div>
            `;

            item.addEventListener("click", () => {
                document
                    .querySelectorAll(".queue-item")
                    .forEach((el) => el.classList.remove("active"));

                item.classList.add("active");

                req.status = req.status || "queued";
                req.verified = true;

                loadActiveRequest(req);
            });

            queueList.appendChild(item);
        });
    } catch (error) {
        console.error("Error fetching queue:", error);
    }
}

async function popNextRequest() {
    try {
        const response = await fetch("/queue/pop", {
            method: "POST"
        });

        if (!response.ok) {
            let errorData = {};

            try {
                errorData = await response.json();
            } catch (e) {
                errorData = {};
            }

            alert(
                `Queue is empty: ${errorData.message || "No requests to process."
                }`
            );

            return;
        }

        const poppedRequest = await response.json();

        poppedRequest.status = "sent_to_fulfillment";
        poppedRequest.verified = true;

        activeFulfillmentData = null;

        loadActiveRequest(poppedRequest);

        showNotification(
            `Processing request: ${poppedRequest.request_id}`
        );

        await refreshStats();
        await refreshQueue();

        await fetchFulfillment(poppedRequest);
    } catch (error) {
        console.error("Error processing request:", error);

        alert("Error connecting to backend server.");
    }
}

async function fetchFulfillment(request) {
    const container = document.getElementById("allocationContainer");

    if (!container) {
        return;
    }

    container.innerHTML = `
        <div class="empty-state">
            Finding the best blood inventory for
            ${escapeHtml(request.request_id)}...
        </div>
    `;

    try {
        const response = await fetch(
            `/fullfillment/${encodeURIComponent(request.request_id)}`,
            {
                method: "POST",
                headers: {
                    Accept: "application/json"
                }
            }
        );

        let data = {};

        try {
            data = await response.json();
        } catch (e) {
            throw new Error("Invalid response received from fulfillment API.");
        }

        if (!response.ok) {
            throw new Error(
                data.detail ||
                data.message ||
                "Fulfillment request failed"
            );
        }

        activeFulfillmentData = data;

        renderFulfillment(data);

        updateMapWithFulfillment(request, data);

        showNotification(
            `${data.units_allocated || 0} units allocated for ${data.request_id || request.request_id
            }`
        );
    } catch (error) {
        console.error("Fulfillment error:", error);

        container.innerHTML = `
            <div class="empty-state">
                Fulfillment failed:
                ${escapeHtml(error.message)}
            </div>
        `;

        showNotification(
            "Unable to complete fulfillment",
            "error"
        );
    }
}

async function submitSimulatedRequest() {
    const hId = document.getElementById("simHospital").value;
    const dId = document.getElementById("simDoctor").value;
    const bloodType = document.getElementById("simBlood").value;
    const units = parseInt(
        document.getElementById("simUnits").value,
        10
    );
    const urgency = document.getElementById("simUrgency").value;
    const prescription =
        document.getElementById("simPrescription").value.trim();
    const notes =
        document.getElementById("simNotes").value.trim();

    const hCoords =
        hospitalCoords[hId] || {
            lat: 28.6139,
            lng: 77.2090
        };

    const payload = {
        hospital_id: hId,
        doctor_id: dId,
        blood_type: bloodType,
        units_needed: units,
        urgency_input: urgency,
        prescription_id: prescription || null,
        clinical_note: notes || null,
        hospital_lat: hCoords.lat,
        hospital_lng: hCoords.lng
    };

    try {
        const response = await fetch("/submit-request", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const responseBody = await response.json();

        if (response.status === 200) {
            showNotification(
                `Request ${responseBody.request_id} verified & queued!`
            );

            responseBody.verified = true;

            loadActiveRequest(responseBody);
        } else if (response.status === 202) {
            showNotification(
                `Request ${responseBody.request_id} registered. Pending clinical check.`,
                "warning"
            );

            responseBody.status =
                "pending_clinical_verification";

            responseBody.verified = false;

            loadActiveRequest(responseBody);
        } else if (response.status === 403) {
            showNotification(
                `Request rejected: ${responseBody.reason}`,
                "error"
            );

            responseBody.status = "rejected";
            responseBody.verified = false;

            loadActiveRequest(responseBody);
        } else if (response.status === 422) {
            alert(
                `Validation Error: ${JSON.stringify(
                    responseBody.detail
                )}`
            );
        } else {
            alert(
                `Unexpected response: ${response.status}`
            );
        }

        refreshStats();
        refreshQueue();
    } catch (error) {
        console.error(
            "Error submitting simulated request:",
            error
        );

        alert("Error connecting to backend server.");
    }
}

async function refreshAuditTrail(requestId) {
    try {
        const response = await fetch(
            `/requests/${encodeURIComponent(requestId)}/audit`
        );

        if (!response.ok) {
            return;
        }

        const data = await response.json();

        renderAuditTrail(data.events || []);

        updatePipelineStatus(
            data.events || [],
            requestId
        );
    } catch (error) {
        console.error(
            "Error fetching audit logs:",
            error
        );
    }
}

function loadActiveRequest(req) {
    activeRequestData = req;

    const detailsContainer =
        document.getElementById("activeRequestDetails");

    const activeRequestStatus =
        document.getElementById("activeRequestStatus");

    if (!detailsContainer) {
        return;
    }

    detailsContainer.classList.remove(
        "empty",
        "critical-alert"
    );

    const hospName =
        hospitalCoords[req.hospital_id]?.name ||
        `Hospital ${req.hospital_id}`;

    const lat =
        req.hospital_lat ||
        hospitalCoords[req.hospital_id]?.lat ||
        28.6139;

    const lng =
        req.hospital_lng ||
        hospitalCoords[req.hospital_id]?.lng ||
        77.2090;

    const urgency =
        req.urgency ||
        req.urgency_input ||
        "routine";

    if (urgency.toLowerCase() === "critical") {
        detailsContainer.classList.add(
            "critical-alert"
        );
    }

    if (activeRequestStatus) {
        activeRequestStatus.className =
            `badge ${urgency.toLowerCase()}`;

        activeRequestStatus.textContent =
            formatStatus(req.status);
    }

    const createdTimeStr = req.timestamp
        ? new Date(req.timestamp).toLocaleTimeString()
        : new Date().toLocaleTimeString();

    detailsContainer.innerHTML = `
        <div class="request-header">
            <div>
                <h3>${escapeHtml(hospName)}</h3>

                <span>
                    Request ID:
                    <strong>
                        ${escapeHtml(req.request_id)}
                    </strong>
                    |
                    Timestamp:
                    ${escapeHtml(createdTimeStr)}
                </span>
            </div>

            <div class="blood-badge">
                ${escapeHtml(req.blood_type)}

                <small>
                    ${req.units_needed} units
                </small>
            </div>
        </div>

        <div class="detail-grid">
            <div class="detail-item">
                <span>Doctor ID</span>
                <strong>
                    ${escapeHtml(req.doctor_id)}
                </strong>
            </div>

            <div class="detail-item">
                <span>Location Coords</span>
                <strong>
                    ${lat.toFixed(4)}, ${lng.toFixed(4)}
                </strong>
            </div>

            <div class="detail-item">
                <span>Prescription ID</span>
                <strong>
                    ${escapeHtml(
        req.prescription_id ||
        "None Provided"
    )}
                </strong>
            </div>

            <div class="detail-item">
                <span>Verification State</span>

                <strong style="color: ${req.verified
            ? "#15803d"
            : "#b81414"
        }">
                    ${req.verified
            ? "Verified & Authorized"
            : "Verification Failed/Pending"
        }
                </strong>
            </div>
        </div>

        <div class="notes-box">
            <strong>Clinical Note:</strong>
            "${escapeHtml(
            req.clinical_note ||
            "No notes provided."
        )}"
        </div>
    `;

    refreshAuditTrail(req.request_id);

    updateMapLocation(
        req.request_id,
        hospName,
        lat,
        lng,
        req.blood_type,
        req.units_needed
    );

    if (req.verified) {
        const container =
            document.getElementById(
                "allocationContainer"
            );

        if (container) {
            if (activeFulfillmentData) {
                renderFulfillment(
                    activeFulfillmentData
                );
            } else {
                container.innerHTML = `
                    <div class="empty-state">
                        Request verified.
                        Process the request to generate
                        live fulfillment recommendations.
                    </div>
                `;
            }
        }
    } else {
        const container =
            document.getElementById(
                "allocationContainer"
            );

        if (container) {
            container.innerHTML = `
                <div class="empty-state">
                    Verification failed or pending.
                    Cannot recommend allocations.
                </div>
            `;
        }
    }
}

function renderAuditTrail(events) {
    const container =
        document.getElementById(
            "auditTrailContainer"
        );

    if (!container) {
        return;
    }

    container.innerHTML = "";

    if (events.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                No audit logs logged yet.
            </div>
        `;

        return;
    }

    events.forEach((ev) => {
        const item =
            document.createElement("div");

        item.className = "audit-log-item";

        const details =
            ev.details || "";

        const lowerDetails =
            details.toLowerCase();

        if (
            lowerDetails.includes("rejected") ||
            lowerDetails.includes("failed")
        ) {
            item.className += " failed";
        } else if (
            lowerDetails.includes("pending")
        ) {
            item.className += " pending";
        } else {
            item.className += " success";
        }

        const timeStr = ev.timestamp
            ? new Date(
                ev.timestamp
            ).toLocaleTimeString()
            : "-";

        item.innerHTML = `
            <span class="audit-time">
                ${escapeHtml(timeStr)}
            </span>

            <div class="audit-text">
                <strong>
                    ${escapeHtml(
            formatEventName(
                ev.event_name
            )
        )}
                </strong>:

                ${escapeHtml(details)}
            </div>
        `;

        container.appendChild(item);
    });
}

function updatePipelineStatus(events, requestId) {
    const steps = {
        hospital:
            document.getElementById(
                "step-hospital"
            ),

        doctor:
            document.getElementById(
                "step-doctor"
            ),

        prescription:
            document.getElementById(
                "step-prescription"
            ),

        priority:
            document.getElementById(
                "step-priority"
            )
    };

    const statuses = {
        hospital:
            document.getElementById(
                "val-hospital-status"
            ),

        doctor:
            document.getElementById(
                "val-doctor-status"
            ),

        prescription:
            document.getElementById(
                "val-prescription-status"
            ),

        priority:
            document.getElementById(
                "val-priority-status"
            )
    };

    Object.keys(steps).forEach((key) => {
        if (steps[key]) {
            steps[key].className =
                "pipeline-step";
        }

        if (statuses[key]) {
            statuses[key].textContent = "-";
        }
    });

    events.forEach((ev) => {
        const eventName =
            ev.event_name || "";

        const details =
            ev.details || "";

        const lowerDetails =
            details.toLowerCase();

        if (
            eventName ===
            "hospital_verified"
        ) {
            if (
                lowerDetails.includes(
                    "rejected"
                )
            ) {
                if (steps.hospital) {
                    steps.hospital.className +=
                        " failed";
                }

                if (statuses.hospital) {
                    statuses.hospital.textContent =
                        "Rejected";
                }
            } else {
                if (steps.hospital) {
                    steps.hospital.className +=
                        " verified";
                }

                if (statuses.hospital) {
                    statuses.hospital.textContent =
                        "Verified";
                }
            }
        }

        if (
            eventName ===
            "doctor_verified"
        ) {
            if (
                lowerDetails.includes(
                    "rejected"
                )
            ) {
                if (steps.doctor) {
                    steps.doctor.className +=
                        " failed";
                }

                if (statuses.doctor) {
                    statuses.doctor.textContent =
                        "Rejected";
                }
            } else {
                if (steps.doctor) {
                    steps.doctor.className +=
                        " verified";
                }

                if (statuses.doctor) {
                    statuses.doctor.textContent =
                        "Verified";
                }
            }
        }

        if (
            eventName ===
            "prescription_checked"
        ) {
            if (
                lowerDetails.includes(
                    "pending"
                )
            ) {
                if (steps.prescription) {
                    steps.prescription.className +=
                        " pending";
                }

                if (statuses.prescription) {
                    statuses.prescription.textContent =
                        "Pending";
                }
            } else if (
                lowerDetails.includes(
                    "rejected"
                )
            ) {
                if (steps.prescription) {
                    steps.prescription.className +=
                        " failed";
                }

                if (statuses.prescription) {
                    statuses.prescription.textContent =
                        "Rejected";
                }
            } else {
                if (steps.prescription) {
                    steps.prescription.className +=
                        " verified";
                }

                if (statuses.prescription) {
                    statuses.prescription.textContent =
                        "Verified";
                }
            }
        }

        if (
            eventName ===
            "urgency_assigned"
        ) {
            if (steps.priority) {
                steps.priority.className +=
                    " verified";
            }

            if (statuses.priority) {
                const match =
                    details.match(
                        /priority[=:]\s*(\w+)/i
                    );

                statuses.priority.textContent =
                    match
                        ? match[1].toUpperCase()
                        : "Queued";
            }
        }
    });
}

function renderFulfillment(data) {
    const container =
        document.getElementById(
            "allocationContainer"
        );

    if (!container) {
        return;
    }

    container.innerHTML = "";

    const allocations =
        Array.isArray(data.allocations)
            ? data.allocations
            : [];

    const unitsRequested =
        Number(data.units_requested || 0);

    const unitsAllocated =
        Number(data.units_allocated || 0);

    const remaining =
        Math.max(
            unitsRequested -
            unitsAllocated,
            0
        );

    const status =
        data.status || "unknown";

    const summary =
        document.createElement("div");

    summary.className =
        "fulfillment-summary";

    summary.innerHTML = `
        <div class="fulfillment-summary-header">
            <div>
                <h3>Fulfillment Result</h3>

                <span>
                    Request ID:
                    <strong>
                        ${escapeHtml(
        data.request_id ||
        activeRequestData?.request_id ||
        "-"
    )}
                    </strong>
                </span>
            </div>

            <div class="fulfillment-status">
                ${escapeHtml(
        formatStatus(status)
    )}
            </div>
        </div>

        <div class="fulfillment-summary-grid">
            <div class="detail-item">
                <span>Blood Type</span>
                <strong>
                    ${escapeHtml(
        data.blood_type || "-"
    )}
                </strong>
            </div>

            <div class="detail-item">
                <span>Units Requested</span>
                <strong>
                    ${unitsRequested}
                </strong>
            </div>

            <div class="detail-item">
                <span>Units Allocated</span>
                <strong style="color:#15803d;">
                    ${unitsAllocated}
                </strong>
            </div>

            <div class="detail-item">
                <span>Remaining</span>
                <strong style="color:${remaining > 0
            ? "#b81414"
            : "#15803d"
        };">
                    ${remaining}
                </strong>
            </div>
        </div>
    `;

    container.appendChild(summary);

    if (allocations.length === 0) {
        const empty =
            document.createElement("div");

        empty.className =
            "empty-state";

        empty.textContent =
            "No compatible blood inventory was found.";

        container.appendChild(empty);

        return;
    }

    const heading =
        document.createElement("div");

    heading.className =
        "fulfillment-list-heading";

    heading.innerHTML = `
        <h3>Recommended Blood Inventory</h3>
        <span>
            ${allocations.length}
            source${allocations.length !== 1 ? "s" : ""}
        </span>
    `;

    container.appendChild(heading);

    allocations.forEach(
        (allocation, index) => {
            const card =
                document.createElement("div");

            card.className =
                "allocation-card" +
                (index === 0
                    ? " best-match"
                    : "");

            const units =
                Number(
                    allocation.units || 0
                );

            const remainingStock =
                Number(
                    allocation.remaining_stock ||
                    0
                );

            const distance =
                Number(
                    allocation.distance_km ||
                    0
                );

            const score =
                calculateMatchScore(
                    distance,
                    remainingStock,
                    units
                );

            const scorePct =
                Math.round(
                    score * 100
                );

            const expiry =
                allocation.expiry_date
                    ? formatDate(
                        allocation.expiry_date
                    )
                    : "N/A";

            card.innerHTML = `
                ${index === 0
                    ? `<div class="best-label">BEST MATCH</div>`
                    : ""
                }

                <div class="bank-header">
                    <div class="bank-info">
                        <div class="bank-icon">
                            🩸
                        </div>

                        <div>
                            <h3>
                                ${escapeHtml(
                    allocation.bank_name ||
                    "Blood Bank"
                )}
                            </h3>

                            <span>
                                Blood Bank ID:
                                ${escapeHtml(
                    allocation.bank_id ||
                    "-"
                )}
                            </span>
                        </div>
                    </div>

                    <div class="score-container">
                        <span class="score-label">
                            MATCH SCORE
                        </span>

                        <span class="score">
                            ${scorePct}%
                        </span>
                    </div>
                </div>

                <div class="allocation-details">
                    <div class="allocation-detail">
                        <span>Units Allocated</span>
                        <strong>
                            ${units} Units
                        </strong>
                    </div>

                    <div class="allocation-detail">
                        <span>Distance</span>
                        <strong>
                            ${distance.toFixed(2)} km
                        </strong>
                    </div>

                    <div class="allocation-detail">
                        <span>Remaining Stock</span>
                        <strong>
                            ${remainingStock} Units
                        </strong>
                    </div>

                    <div class="allocation-detail">
                        <span>Expiry Date</span>
                        <strong>
                            ${escapeHtml(expiry)}
                        </strong>
                    </div>
                </div>

                <div class="reason-box">
                    <span class="reason-icon">
                        💡
                    </span>

                    <p>
                        <strong>
                            Recommendation Basis:
                        </strong>

                        Compatible
                        ${escapeHtml(
                    allocation.blood_type ||
                    data.blood_type ||
                    ""
                )}
                        inventory located
                        ${distance.toFixed(2)}
                        km from the hospital.
                    </p>
                </div>

                <button
                    class="dispatch-btn"
                    data-bank-id="${escapeHtml(
                    allocation.bank_id || ""
                )}"
                    data-allocation-index="${index}"
                >
                    🚚 Confirm Dispatch
                </button>
            `;

            container.appendChild(card);

            const button =
                card.querySelector(
                    ".dispatch-btn"
                );

            if (button) {
                button.addEventListener(
                    "click",
                    () => {
                        confirmDispatch(
                            button,
                            allocation,
                            data
                        );
                    }
                );
            }
        }
    );

    if (remaining > 0) {
        const warning =
            document.createElement("div");

        warning.className =
            "empty-state";

        warning.style.marginTop =
            "12px";

        warning.innerHTML = `
            ⚠ Only
            <strong>
                ${unitsAllocated}
            </strong>
            of
            <strong>
                ${unitsRequested}
            </strong>
            requested units could be allocated.
        `;

        container.appendChild(warning);
    }
}

function calculateMatchScore(
    distance,
    remainingStock,
    units
) {
    const distancePenalty =
        Math.min(
            distance * 0.015,
            0.35
        );

    const stockBonus =
        Math.min(
            remainingStock * 0.01,
            0.2
        );

    const allocationPenalty =
        Math.min(
            units * 0.02,
            0.1
        );

    const score =
        1 -
        distancePenalty +
        stockBonus -
        allocationPenalty;

    return Math.max(
        0.4,
        Math.min(0.99, score)
    );
}

function confirmDispatch(
    button,
    allocation,
    fulfillmentData
) {
    if (!button || button.disabled) {
        return;
    }

    button.textContent =
        "✓ Dispatch Confirmed";

    button.classList.add(
        "confirmed"
    );

    button.disabled = true;

    const units =
        Number(
            allocation.units || 0
        );

    const bankName =
        allocation.bank_name ||
        allocation.bank_id ||
        "blood bank";

    const bloodType =
        fulfillmentData.blood_type ||
        activeRequestData?.blood_type ||
        "";

    showNotification(
        `Dispatch initialized: ${units} units of ${bloodType} from ${bankName}`
    );

    const hospitalLat =
        activeRequestData?.hospital_lat ||
        hospitalCoords[
            activeRequestData?.hospital_id
        ]?.lat ||
        28.6139;

    const hospitalLng =
        activeRequestData?.hospital_lng ||
        hospitalCoords[
            activeRequestData?.hospital_id
        ]?.lng ||
        77.2090;

    const bankLat =
        Number(allocation.lat);

    const bankLng =
        Number(allocation.lng);

    if (
        Number.isFinite(bankLat) &&
        Number.isFinite(bankLng)
    ) {
        drawDispatchLine(
            [bankLat, bankLng],
            [hospitalLat, hospitalLng]
        );
    }
}

function initializeMap(lat, lng) {
    if (mapInstance) {
        mapInstance.remove();
    }

    mapInstance = L.map("map", {
        zoomControl: true,
        scrollWheelZoom: false
    }).setView(
        [lat, lng],
        12
    );

    L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        {
            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains:
                "abcd",
            maxZoom: 20
        }
    ).addTo(mapInstance);
}

function updateMapLocation(
    requestId,
    hospitalName,
    lat,
    lng,
    bloodType,
    units
) {
    if (!mapInstance) {
        return;
    }

    mapInstance.setView(
        [lat, lng],
        13
    );

    clearMapMarkers();
    clearDispatchLines();

    const hospitalIcon =
        L.divIcon({
            className:
                "custom-map-marker",

            html: `
                <div style="
                    width: 32px;
                    height: 32px;
                    background: #b81414;
                    border: 2px solid #fff;
                    border-radius: 50% 50% 50% 0;
                    transform: rotate(-45deg);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    box-shadow: 0 4px 10px rgba(0,0,0,0.3);
                ">
                    <span style="
                        transform: rotate(45deg);
                        font-size: 14px;
                    ">
                        🏥
                    </span>
                </div>
            `,

            iconSize: [
                32,
                32
            ],

            iconAnchor: [
                16,
                32
            ]
        });

    hospitalMarker =
        L.marker(
            [lat, lng],
            {
                icon: hospitalIcon
            }
        )
            .addTo(mapInstance)
            .bindPopup(
                `
                <strong>
                    🏥
                    ${escapeHtml(
                    hospitalName
                )}
                </strong>
                <br>
                Request ID:
                ${escapeHtml(
                    requestId
                )}
                <br>
                Required:
                ${units}
                units of
                ${escapeHtml(
                    bloodType
                )}
                `
            )
            .openPopup();
}

function updateMapWithFulfillment(
    request,
    fulfillment
) {
    if (!mapInstance) {
        return;
    }

    const hospitalLat =
        request.hospital_lat ||
        hospitalCoords[
            request.hospital_id
        ]?.lat ||
        28.6139;

    const hospitalLng =
        request.hospital_lng ||
        hospitalCoords[
            request.hospital_id
        ]?.lng ||
        77.2090;

    updateMapLocation(
        request.request_id,
        hospitalCoords[
            request.hospital_id
        ]?.name ||
        `Hospital ${request.hospital_id}`,
        hospitalLat,
        hospitalLng,
        request.blood_type,
        request.units_needed
    );

    const allocations =
        Array.isArray(
            fulfillment.allocations
        )
            ? fulfillment.allocations
            : [];

    const boundsPoints = [
        [
            hospitalLat,
            hospitalLng
        ]
    ];

    allocations.forEach(
        (allocation) => {
            const lat =
                Number(
                    allocation.lat
                );

            const lng =
                Number(
                    allocation.lng
                );

            if (
                !Number.isFinite(lat) ||
                !Number.isFinite(lng)
            ) {
                return;
            }

            const bankIcon =
                L.divIcon({
                    className:
                        "custom-map-marker",

                    html: `
                        <div style="
                            width: 28px;
                            height: 28px;
                            background: #2563eb;
                            border: 2px solid #fff;
                            border-radius: 50% 50% 50% 0;
                            transform: rotate(-45deg);
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                        ">
                            <span style="
                                transform: rotate(45deg);
                                font-size: 11px;
                            ">
                                🩸
                            </span>
                        </div>
                    `,

                    iconSize: [
                        28,
                        28
                    ],

                    iconAnchor: [
                        14,
                        28
                    ]
                });

            const marker =
                L.marker(
                    [lat, lng],
                    {
                        icon: bankIcon
                    }
                )
                    .addTo(mapInstance)
                    .bindPopup(
                        `
                        <strong>
                            🩸
                            ${escapeHtml(
                            allocation.bank_name ||
                            allocation.bank_id ||
                            "Blood Bank"
                        )}
                        </strong>

                        <br>

                        Bank ID:
                        ${escapeHtml(
                            allocation.bank_id ||
                            "-"
                        )}

                        <br>

                        Blood Type:
                        ${escapeHtml(
                            allocation.blood_type ||
                            fulfillment.blood_type ||
                            "-"
                        )}

                        <br>

                        Allocated:
                        ${Number(
                            allocation.units ||
                            0
                        )}
                        units

                        <br>

                        Remaining Stock:
                        ${Number(
                            allocation.remaining_stock ||
                            0
                        )}
                        units

                        <br>

                        Distance:
                        ${Number(
                            allocation.distance_km ||
                            0
                        ).toFixed(2)}
                        km

                        <br>

                        Expiry:
                        ${escapeHtml(
                            allocation.expiry_date ||
                            "N/A"
                        )}
                        `
                    );

            bankMarkers.push(
                marker
            );

            boundsPoints.push([
                lat,
                lng
            ]);
        }
    );

    if (
        boundsPoints.length > 1
    ) {
        mapInstance.fitBounds(
            boundsPoints,
            {
                padding: [
                    50,
                    50
                ]
            }
        );
    }
}

function clearMapMarkers() {
    if (!mapInstance) {
        return;
    }

    if (hospitalMarker) {
        mapInstance.removeLayer(
            hospitalMarker
        );

        hospitalMarker = null;
    }

    bankMarkers.forEach(
        (marker) => {
            mapInstance.removeLayer(
                marker
            );
        }
    );

    bankMarkers = [];
}

function clearDispatchLines() {
    if (!mapInstance) {
        return;
    }

    dispatchLines.forEach(
        (line) => {
            mapInstance.removeLayer(
                line
            );
        }
    );

    dispatchLines = [];
}

function drawDispatchLine(
    bankCoords,
    hospitalCoords
) {
    if (!mapInstance) {
        return;
    }

    const line =
        L.polyline(
            [
                bankCoords,
                hospitalCoords
            ],
            {
                color: "#a81a29",
                weight: 3,
                opacity: 0.8,
                dashArray: "8, 8",
                lineCap: "round"
            }
        ).addTo(
            mapInstance
        );

    dispatchLines.push(
        line
    );

    mapInstance.fitBounds(
        line.getBounds(),
        {
            padding: [
                50,
                50
            ]
        }
    );
}

function formatStatus(status) {
    if (!status) {
        return "-";
    }

    return String(status)
        .replace(/_/g, " ")
        .toUpperCase();
}

function formatEventName(name) {
    if (!name) {
        return "";
    }

    return String(name)
        .split("_")
        .map(
            (word) =>
                word.charAt(0).toUpperCase() +
                word.slice(1)
        )
        .join(" ");
}

function formatDate(dateValue) {
    if (!dateValue) {
        return "N/A";
    }

    const date =
        new Date(dateValue);

    if (
        Number.isNaN(
            date.getTime()
        )
    ) {
        return String(
            dateValue
        );
    }

    return date.toLocaleDateString(
        "en-IN",
        {
            year: "numeric",
            month: "short",
            day: "numeric"
        }
    );
}

function escapeHtml(value) {
    if (
        value === undefined ||
        value === null
    ) {
        return "";
    }

    return String(value)
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );
}

function showNotification(
    message,
    type = "success"
) {
    const notification =
        document.createElement(
            "div"
        );

    notification.style.position =
        "fixed";

    notification.style.right =
        "25px";

    notification.style.bottom =
        "25px";

    let bg = "#241b1b";

    if (
        type === "warning"
    ) {
        bg = "#ca8a04";
    }

    if (
        type === "error"
    ) {
        bg = "#b81414";
    }

    notification.style.background =
        bg;

    notification.style.color =
        "#fcfbfa";

    notification.style.padding =
        "14px 20px";

    notification.style.borderRadius =
        "8px";

    notification.style.fontSize =
        "12px";

    notification.style.fontWeight =
        "600";

    notification.style.boxShadow =
        "0 8px 30px rgba(0,0,0,0.15)";

    notification.style.zIndex =
        "9999";

    notification.style.transition =
        "opacity 0.3s ease";

    let icon = "✓";

    if (
        type === "warning"
    ) {
        icon = "⚠";
    }

    if (
        type === "error"
    ) {
        icon = "✗";
    }

    notification.innerHTML =
        `${icon} ${escapeHtml(
            message
        )}`;

    document.body.appendChild(
        notification
    );

    setTimeout(() => {
        notification.style.opacity =
            "0";

        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 4000);
}