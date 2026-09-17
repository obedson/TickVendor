"""Offline, versioned Nigeria state/LGA validation; city is not an LGA."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def nigeria_locations():
    return json.loads(Path(__file__).with_name("data").joinpath("nigeria_lgas.json").read_text(encoding="utf-8"))


def validate_nigeria_location(region, lga, country_code):
    if not lga:
        return  # Legacy unstructured region/city values remain valid.
    if country_code.upper() != "NG" or region not in nigeria_locations() or lga not in nigeria_locations()[region]:
        raise ValueError("Select an LGA belonging to the selected Nigerian state")
