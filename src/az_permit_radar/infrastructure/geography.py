"""Configuration adapter for governed geography policy."""

from __future__ import annotations

import json
from decimal import Decimal

from az_permit_radar.application.geography import GeographyPolicy


def load_geography_policy(path: str) -> GeographyPolicy:
    with open(path, encoding="utf-8") as stream:
        values = json.load(stream)["geography_policy"]
    return GeographyPolicy(
        maximum_radius_km=Decimal(values["maximum_radius_km"]),
        maximum_postal_codes=values["maximum_postal_codes"],
        maximum_jurisdictions=values["maximum_jurisdictions"],
        maximum_cities=values["maximum_cities"],
    )
