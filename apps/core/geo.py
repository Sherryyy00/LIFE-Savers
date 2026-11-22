"""
Small distance helpers.

We use plain latitude/longitude columns plus a bounding-box pre-filter in SQL
and an exact haversine distance in Python. For a town-sized dataset that's fast
and avoids needing PostGIS/GDAL on the free hosting tier. If the app grows to
many cities, switch these fields to PostGIS PointField.
"""

import math
from dataclasses import dataclass
from decimal import Decimal

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    lat1, lng1, lat2, lng2 = map(lambda v: math.radians(float(v)), (lat1, lng1, lat2, lng2))
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class BoundingBox:
    min_lat: Decimal
    max_lat: Decimal
    min_lng: Decimal
    max_lng: Decimal


def bounding_box(lat, lng, radius_km: float) -> BoundingBox:
    lat = float(lat)
    lng = float(lng)
    dlat = radius_km / 111.32
    # guard against the poles, irrelevant for Pakistan but keeps maths safe
    dlng = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.01))
    q = Decimal("0.000001")
    return BoundingBox(
        min_lat=Decimal(lat - dlat).quantize(q),
        max_lat=Decimal(lat + dlat).quantize(q),
        min_lng=Decimal(lng - dlng).quantize(q),
        max_lng=Decimal(lng + dlng).quantize(q),
    )
