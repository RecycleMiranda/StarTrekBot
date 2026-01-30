import json
import random
import time
import os
import uuid
from typing import List, Dict, Optional

# Constants
SENSOR_LOG_PATH = os.path.join(os.path.dirname(__file__), "SENSOR_LOGS.md")

class SensorContact:
    def __init__(self, c_type, id_str, dist, bearing, velocity, metadata=None):
        self.uid = str(uuid.uuid4())[:8]
        self.type = c_type
        self.id_str = id_str
        self.distance = dist
        self.bearing = bearing
        self.velocity = velocity
        self.metadata = metadata or {}
        self.timestamp = time.time()

class InternalSensorManager:
    def __init__(self, bus):
        self.bus = bus
        self.decks = list(range(1, 41))
        self.security_alerts = []

    def scan_deck(self, deck_number):
        signals = []
        # Simulate Personnel
        for i in range(random.randint(5, 15)):
            u_id = f"CREW-{random.randint(1000,9999)}"
            signals.append({
                "uid": u_id,
                "type": "FEDERATION_COM_BADGE",
                "location": f"Deck {deck_number}, Section {random.randint(1,50)}"
            })
        # Simulate Intruder (Rare)
        if random.random() > 0.98:
            intruder_id = f"UNKNOWN-{random.randint(9000,9999)}"
            self.bus._log_event("INTRUDER_ALERT", intruder_id, f"Unauthorized bio-sign on Deck {deck_number}")
            signals.append({
                "uid": intruder_id,
                "type": "UNAUTHORIZED_BIO_SIGN",
                "location": f"Deck {deck_number}, Junction {random.randint(1,10)}",
                "alert": "RED"
            })
        return signals

    def get_transporter_lock(self, deck, section):
        is_safe = random.random() > 0.05
        if is_safe:
            return {
                "status": "SAFE",
                "coordinates": [random.uniform(0, 100), random.uniform(0, 100), deck * 3.5],
                "interference": "0.02%"
            }
        return {"status": "UNSAFE", "reason": "PLASMA_CONDUIT_INTERFERENCE"}

class ActiveTargetingSystem:
    def __init__(self, sensor_manager):
        self.sm = sensor_manager
        self.locked_target_uid = None
        self.lock_timestamp = 0
        self.tracking_quality = 0.0

    def engage_lock(self, target_uid):
        target = next((c for c in self.sm.active_contacts if c.uid == target_uid), None)
        if not target: return False, "TARGET_NOT_FOUND"
        self.locked_target_uid = target_uid
        self.lock_timestamp = time.time()
        self.tracking_quality = 0.95 + (random.random() * 0.05)
        self.sm._log_event("TACTICAL_LOCK", target.id_str, f"Hard Lock established. Quality: {self.tracking_quality:.1%}")
        return True, "LOCK_ESTABLISHED"

    def disengage(self):
        if self.locked_target_uid:
            self.sm._log_event("LOCK_RELEASE", self.locked_target_uid, "Targeting lock disengaged.")
            self.locked_target_uid = None
            self.tracking_quality = 0.0

    def get_firing_solution(self):
        if not self.locked_target_uid: return None
        target = next((c for c in self.sm.active_contacts if c.uid == self.locked_target_uid), None)
        if not target:
            self.disengage()
            return None
        return {
            "target_uid": target.uid,
            "target_identity": target.id_str,
            "lock_status": "LOCKED",
            "quality": f"{self.tracking_quality:.4f}",
            "vector": {
                "bearing_az": target.bearing[0],
                "bearing_el": target.bearing[1],
                "range_precise_m": target.distance * 1000,
                "velocity_vector": [target.velocity * 0.7, target.velocity * 0.2, target.velocity * 0.1]
            },
            "timestamp": time.time()
        }

class SensorManager:
    def __init__(self):
        self.active_contacts = []
        self.pallets = [] # Simplified for production core
        self.internal_sensors = InternalSensorManager(self)
        self.targeting_system = ActiveTargetingSystem(self)
        self._init_log()

    def _log_event(self, event_type, subject, details):
        timestamp = datetime.now().isoformat()
        entry = f"| {timestamp} | {event_type} | {subject} | {details} |\n"
        with open(SENSOR_LOG_PATH, "a") as f:
            f.write(entry)

    def _init_log(self):
        if not os.path.exists(SENSOR_LOG_PATH):
            with open(SENSOR_LOG_PATH, "w") as f:
                f.write("# StarTrekBot Sensor Logs\n\n| Timestamp | Event | Subject | Details |\n|---|---|---|---|\n")

    def tactical_feed(self):
        # In production, this would scan the 'Active Contacts' list
        feed = []
        for c in self.active_contacts:
            feed.append({
                "id": c.uid,
                "classification": c.type,
                "range_km": c.distance,
                "details": c.metadata
            })
        return feed

    def lock_target(self, uid): return self.targeting_system.engage_lock(uid)
    def get_target_solution(self): return self.targeting_system.get_firing_solution()

    def report_impact(self, target_uid, damage_data):
        target = next((c for c in self.active_contacts if c.uid == target_uid), None)
        if not target: return False, "TARGET_NOT_FOUND"
        damage_ndf = damage_data.get("ndf_yield", 0)
        damage_iso = damage_data.get("isotoness_yield", 0)
        current_shields = target.metadata.get("shields_pct", 1.0)
        reduction = (damage_ndf * 0.05) + (damage_iso * 0.01)
        new_shields = max(0.0, current_shields - reduction)
        target.metadata["shields_pct"] = new_shields
        status = "SHIELDS_OFFLINE" if new_shields <= 0 else "SHIELDS_DEGRADED"
        self._log_event("BDA_REPORT", target.id_str, f"Impact Registered. Shields: {new_shields:.1%}. Status: {status}")
        return True, status

    def _generate_traffic(self):
        # Simulation Logic for background activity
        if len(self.active_contacts) < 10:
            c = SensorContact("CIVILIAN", "SS-VALIANT", 50000, (45,0), 300, {"shields_pct": 1.0})
            self.active_contacts.append(c)
            self._log_event("ACQUISITION", c.id_str, "New contact detected via ESA.")

from datetime import datetime
