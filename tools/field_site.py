"""Shared site constants for the X450 rice survey (used by the tools/ scripts).

World frame = ENU (x east, y north), origin = home point (worlds/rice.sdf).
Home = SE corner of the surveyed paddy (Thu Thua, Long An).

Survey frame (origin = home):
  +v ("along")  = along the East (right) bank, bearing BANK_BEARING_DEG (to the NNW)
  +u ("right")  = perpendicular, to the ENE; the paddy lies at u <= 0 (to the left)
The bank directions were measured on the QGroundControl map (2026-11-09):
the user's Google NE corner gives 343.4 deg for the East bank, but both the
QGC map and the Google texture show ~348 deg, so the NE corner is likely off.

Lawn-mower lines: line k (k = 0, 1, ...) at u = -k * spacing, from
START_MARGIN inside the South bank, LINE_LENGTH long; line 1 starts at home.
"""
import math

HOME_LAT = 10.578681      # deg, = PX4_HOME_LAT and <spherical_coordinates>
HOME_LON = 106.416747     # deg

FIELD_CORNERS = {         # lat, lon from Google Maps right-click (reference only)
    "SE": (10.578681, 106.416747),
    "SW": (10.578613057140691, 106.41626497992594),
    "NW": (10.579258369698373, 106.41608393081952),
    "NE": (10.579284076707623, 106.41656404622385),
}

BANK_BEARING_DEG = 348.0        # East (right) bank, measured on the QGC map
SOUTH_BANK_BEARING_DEG = 265.8  # South bank through home, measured on the QGC map
START_MARGIN = 5.0              # line bottoms this far inside the South bank [m]
LINE_LENGTH = 50.0              # survey length of every line [m]
SURVEY_WIDTH = 50.0             # lines stay within u in [-SURVEY_WIDTH, 0] [m]

YAW = math.radians(360.0 - BANK_BEARING_DEG)   # ENU yaw of the survey frame (CCW)
# South bank rises (toward +v) when going left, by this angle:
SKEW = math.radians((SOUTH_BANK_BEARING_DEG - (BANK_BEARING_DEG - 90.0)) % 360.0)

_M_PER_DEG_LAT = 111320.0
_M_PER_DEG_LON = 111320.0 * math.cos(math.radians(HOME_LAT))


def enu_to_latlon(x, y):
    """Local ENU metres -> (lat, lon) degrees. Flat-earth, fine for < 1 km."""
    return HOME_LAT + y / _M_PER_DEG_LAT, HOME_LON + x / _M_PER_DEG_LON


def latlon_to_enu(lat, lon):
    return (lon - HOME_LON) * _M_PER_DEG_LON, (lat - HOME_LAT) * _M_PER_DEG_LAT


def survey_to_enu(u, v):
    """Survey frame (u right, v along the bank) -> world ENU."""
    c, s = math.cos(YAW), math.sin(YAW)
    return c * u - s * v, s * u + c * v


def south_bank_v(u):
    """Along-bank coordinate v of the South bank at lateral position u (u <= 0)."""
    return -u * math.tan(SKEW)
