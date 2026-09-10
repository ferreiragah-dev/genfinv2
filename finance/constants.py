"""Shared vocabulary for vehicle expenses and their presentation."""

VEHICLE_COST_TYPES = (
    ("IPVA", "IPVA", "file-invoice-dollar"),
    ("Seguro veicular", "Seguro", "shield-halved"),
    ("Combustível", "Combustível", "gas-pump"),
)
VEHICLE_CATEGORIES = tuple(category for category, _, _ in VEHICLE_COST_TYPES)
