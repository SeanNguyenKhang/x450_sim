"""Shared site constants for the X450 rice survey (used by the tools/ scripts).

World frame = ENU (x east, y north), origin = home point (worlds/rice.sdf).
"""
import math

HOME_LAT = 10.578723      # deg, = PX4_HOME_LAT and <spherical_coordinates>
HOME_LON = 106.416590     # deg
PLOT_CENTER = (-6.0, 2.5)  # survey plot centre in world ENU [m]
PLOT_SIZE = 50.0           # survey plot side [m]

_M_PER_DEG_LAT = 111320.0
_M_PER_DEG_LON = 111320.0 * math.cos(math.radians(HOME_LAT))


def enu_to_latlon(x, y):
    """Local ENU metres -> (lat, lon) degrees. Flat-earth, fine for < 1 km."""
    return HOME_LAT + y / _M_PER_DEG_LAT, HOME_LON + x / _M_PER_DEG_LON


def latlon_to_enu(lat, lon):
    return (lon - HOME_LON) * _M_PER_DEG_LON, (lat - HOME_LAT) * _M_PER_DEG_LAT
