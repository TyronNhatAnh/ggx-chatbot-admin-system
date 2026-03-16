"""Seed persona tags onto existing enum values in the knowledge store.

Persona mapping rules (based on domain knowledge):

  "customer" — OrderRequest is the customer-facing order lifecycle:
    - OrderRequestStatusCD / OrderRequestStatusName
      (Pending → Active → Transit → Completed / Cancelled)

  "driver" — Order/Driver statuses are driver-facing (assignment, delivery):
    - OrderDriverStatusCd / StatusCD / StatusName
      (Assigned → Released → Return)
    - WayPointStatusCd / WayPointStatusCdStr (waypoint delivery tracking)
    - GoodsStatusCd / GoodsStatusCdStr (goods delivery tracking)

  NO persona (actor type, not a viewing perspective):
    - OrderDriverCreatorTypeCD / OrderDriverUpdaterTypeCD — who created/updated
    - OrderHistTypeCd / OrderHistCreatorCD — history actor type
    - HandleOrderStatusName — internal processing result
    - PaymentStatusName — system-level payment state
    - DriverUserTypeCD / DriverType — driver classification
    - OrderEventName — system event names

Run:
  PYTHONPATH=. python scripts/seed_persona_tags.py
"""

import logging
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parents[1] / "data" / "knowledge" / "knowledge.db"

# Enum group name → persona for ALL values in that group
_GROUP_PERSONA: dict[str, str] = {
    # Customer-facing order request lifecycle
    "OrderRequestStatusCD": "customer",
    "OrderRequestStatusName": "customer",
    # Driver-facing assignment / delivery status
    "OrderDriverStatusCd": "driver",
    "StatusCD": "driver",
    "StatusName": "driver",
    # Driver waypoint / goods tracking
    "WayPointStatusCd": "driver",
    "WayPointStatusCdStr": "driver",
    "GoodsStatusCd": "driver",
    "GoodsStatusCdStr": "driver",
}

# Groups that should NOT have a persona (actor type / system-level, not a perspective).
# If they were previously tagged, clear them.
_CLEAR_PERSONA_GROUPS: list[str] = [
    "HandleOrderStatusName",
    "PaymentStatusName",
    "OrderDriverCreatorTypeCD",
    "OrderDriverUpdaterTypeCD",
    "DriverUserTypeCD",
    "DriverType",
    "OrderHistTypeCd",
    "OrderHistCreatorCD",
    "OrderEventName",
    "TypeCD",             # actor type (Admin/Driver/B2B/B2C), not a viewing perspective
    "OrderDriverTypeName",
]

# Individual value overrides: (enum_group_name, value_name) → persona
_VALUE_PERSONA: dict[tuple[str, str], str] = {
    ("OrderAmountTargetCd", "Customer"): "customer",
    ("OrderAmountTargetCd", "Driver"): "driver",
    # "All" intentionally left without persona — it's not a specific perspective
}


def seed() -> None:
    if not DB_PATH.exists():
        logger.error("Database not found at %s", DB_PATH)
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Ensure persona column exists
    cols = {r[1] for r in conn.execute("PRAGMA table_info(enum_values)").fetchall()}
    if "persona" not in cols:
        conn.execute("ALTER TABLE enum_values ADD COLUMN persona TEXT NOT NULL DEFAULT ''")
        conn.commit()
        logger.info("Added persona column to enum_values")

    updated = 0

    # Clear persona from groups that are actor-type, not a viewing perspective
    for group_name in _CLEAR_PERSONA_GROUPS:
        rows = conn.execute("SELECT id FROM enums WHERE name = ?", (group_name,)).fetchall()
        for row in rows:
            cur = conn.execute(
                "UPDATE enum_values SET persona = '' WHERE enum_id = ? AND persona != ''",
                (row["id"],),
            )
            if cur.rowcount:
                logger.info("  Cleared persona from %s (%d values)", group_name, cur.rowcount)

    # Apply group-level persona
    for group_name, persona in _GROUP_PERSONA.items():
        rows = conn.execute("SELECT id FROM enums WHERE name = ?", (group_name,)).fetchall()
        for row in rows:
            cur = conn.execute(
                "UPDATE enum_values SET persona = ? WHERE enum_id = ? AND persona = ''",
                (persona, row["id"]),
            )
            updated += cur.rowcount

    # Apply individual value overrides
    for (group_name, value_name), persona in _VALUE_PERSONA.items():
        rows = conn.execute("SELECT id FROM enums WHERE name = ?", (group_name,)).fetchall()
        for row in rows:
            cur = conn.execute(
                "UPDATE enum_values SET persona = ? WHERE enum_id = ? AND name = ?",
                (persona, row["id"], value_name),
            )
            updated += cur.rowcount

    conn.commit()
    logger.info("Updated %d enum values with persona tags", updated)

    # Verify
    result = conn.execute(
        "SELECT persona, COUNT(*) as cnt FROM enum_values "
        "WHERE persona != '' GROUP BY persona ORDER BY cnt DESC"
    ).fetchall()
    for r in result:
        logger.info("  persona=%s → %d values", r["persona"], r["cnt"])

    conn.close()


if __name__ == "__main__":
    seed()
