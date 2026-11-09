"""Shared site constants for the X450 rice survey (used by the tools/ scripts).

World frame = ENU (x east, y north), origin = home point (worlds/rice.sdf).
Home = SE corner of the surveyed paddy (Thu Thua, Long An).
Field corners: Google Maps right-click, 2026-11-09.

The 50 x 50 m survey plot is aligned with the paddy's long banks (East bank
bearing 343.4 deg) and centred across the paddy width (>= 0.8 m from every
bank); it does not fit with true N-S sides. Plot frame: origin = plot centre,
+y = along the banks (to the NNW), +x = across (to the ENE).
"""
import math

HOME_LAT = 10.578681      # deg, = PX4_HOME_LAT and <spherical_coordinates>
HOME_LON = 106.416747     # deg

FIELD_CORNERS = {         # lat, lon (clockwise from home)
    "SE": (10.578681, 106.416747),
    "SW": (10.578613057140691, 106.41626497992594),
    "NW": (10.579258369698373, 106.41608393081952),
    "NE": (10.579284076707623, 106.41656404622385),
}

PLOT_SIZE = 50.0             # survey plot side [m]
PLOT_CENTER = (-34.29, 24.63)  # plot centre in world ENU [m]
PLOT_YAW_DEG = 16.61         # plot +y axis rotated CCW from North (= bearing 343.4 deg)

_M_PER_DEG_LAT = 111320.0
_M_PER_DEG_LON = 111320.0 * math.cos(math.radians(HOME_LAT))


def enu_to_latlon(x, y):
    """Local ENU metres -> (lat, lon) degrees. Flat-earth, fine for < 1 km."""
    return HOME_LAT + y / _M_PER_DEG_LAT, HOME_LON + x / _M_PER_DEG_LON


def latlon_to_enu(lat, lon):
    return (lon - HOME_LON) * _M_PER_DEG_LON, (lat - HOME_LAT) * _M_PER_DEG_LAT


def plot_to_enu(px, py):
    """Plot frame (metres from plot centre) -> world ENU."""
    c, s = math.cos(math.radians(PLOT_YAW_DEG)), math.sin(math.radians(PLOT_YAW_DEG))
    return PLOT_CENTER[0] + c * px - s * py, PLOT_CENTER[1] + s * px + c * py


def enu_to_plot(x, y):
    c, s = math.cos(math.radians(PLOT_YAW_DEG)), math.sin(math.radians(PLOT_YAW_DEG))
    dx, dy = x - PLOT_CENTER[0], y - PLOT_CENTER[1]
    return c * dx + s * dy, -s * dx + c * dy
