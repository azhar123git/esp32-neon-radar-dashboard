
import re
import time
import sys
import serial
import numpy as np
import matplotlib.pyplot as plt

from matplotlib.animation import FuncAnimation
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch

# ==========================================================
# ESP32 PROFESSIONAL RADAR DASHBOARD
# ==========================================================

PORT = "COM3"
BAUD_RATE = 115200
MAX_DISTANCE = 200
UPDATE_INTERVAL = 30
RECONNECT_INTERVAL = 2.0

# Neon HUD colors
BG = "#03090b"
PANEL = "#071518"
GREEN = "#00ff88"
GREEN_DIM = "#008f57"
CYAN = "#00eaff"
RED = "#ff4264"
WHITE = "#d9fff0"
MUTED = "#6d9e91"
AMBER = "#ffc857"

# ==========================================================
# SERIAL CONNECTION
# ==========================================================

esp32 = None
connection_status = "DISCONNECTED"
last_reconnect = 0.0
last_data_time = 0.0
last_message = "Waiting for ESP32..."
serial_error = ""

def connect_esp32():
    global esp32, connection_status, serial_error

    try:
        if esp32 is not None and esp32.is_open:
            esp32.close()

        esp32 = serial.Serial(
            PORT,
            BAUD_RATE,
            timeout=0.01
        )
        esp32.reset_input_buffer()

        connection_status = "CONNECTED"
        serial_error = ""
        print(f"Connected to ESP32: {PORT}")
        return True

    except (serial.SerialException, OSError) as error:
        esp32 = None
        connection_status = "DISCONNECTED"
        serial_error = str(error)
        return False


connect_esp32()

# ==========================================================
# RADAR DATA
# ==========================================================

current_angle = 90
current_distance = None
detections = {}
total_detections = 0
scan_direction = 1
scan_progress = 50.0

distance_pattern = re.compile(
    r"Angle:\s*(\d+)\s*deg\s*\|\s*"
    r"Distance:\s*(\d+)\s*cm",
    re.IGNORECASE
)

no_echo_pattern = re.compile(
    r"Angle:\s*(\d+)\s*deg\s*\|\s*No valid echo",
    re.IGNORECASE
)

# ==========================================================
# FIGURE / DASHBOARD LAYOUT
# ==========================================================

plt.rcParams["font.family"] = "DejaVu Sans"

fig = plt.figure(
    figsize=(15, 9),
    facecolor=BG
)

fig.canvas.manager.set_window_title(
    "NEON RADAR | ESP32 CONTROL CENTER"
)

gs = GridSpec(
    2, 2,
    figure=fig,
    width_ratios=[1.65, 1],
    height_ratios=[0.13, 0.87],
    left=0.055,
    right=0.965,
    top=0.94,
    bottom=0.075,
    wspace=0.12,
    hspace=0.08
)

# Header
header_ax = fig.add_subplot(gs[0, :])
header_ax.set_facecolor(BG)
header_ax.axis("off")

header_ax.text(
    0.0, 0.67,
    "N E O N   /   R A D A R",
    color=GREEN,
    fontsize=23,
    fontweight="bold",
    transform=header_ax.transAxes
)

header_ax.text(
    0.005, 0.13,
    "ULTRASONIC DETECTION SYSTEM  //  ESP32 TELEMETRY",
    color=MUTED,
    fontsize=9,
    transform=header_ax.transAxes
)

header_ax.text(
    1.0, 0.66,
    "LIVE MONITORING",
    color=CYAN,
    fontsize=11,
    fontweight="bold",
    ha="right",
    transform=header_ax.transAxes
)

header_ax.text(
    1.0, 0.15,
    f"SERIAL: {PORT}  |  {BAUD_RATE} BAUD",
    color=MUTED,
    fontsize=9,
    ha="right",
    transform=header_ax.transAxes
)

# ==========================================================
# RADAR DISPLAY
# ==========================================================

ax = fig.add_subplot(gs[1, 0], polar=True)
ax.set_facecolor(BG)

ax.set_theta_zero_location("E")
ax.set_theta_direction(1)
ax.set_thetamin(0)
ax.set_thetamax(180)
ax.set_ylim(0, MAX_DISTANCE)

ax.set_rgrids(
    [40, 80, 120, 160, 200],
    angle=90,
    color=GREEN_DIM,
    fontsize=8
)

ax.set_thetagrids(
    range(0, 181, 30),
    labels=[f"{a}°" for a in range(0, 181, 30)],
    color=GREEN
)

ax.grid(color=GREEN_DIM, alpha=0.4, linewidth=0.8)
ax.spines["polar"].set_color(GREEN_DIM)
ax.spines["polar"].set_linewidth(1.5)
ax.tick_params(colors=GREEN, pad=8)

ax.set_title(
    "SCANNING FIELD  /  RANGE 200 CM",
    color=GREEN,
    fontsize=12,
    fontweight="bold",
    pad=22
)

# Concentric visual range rings
theta_ring = np.linspace(0, np.pi, 361)

for radius in [40, 80, 120, 160, 200]:
    ax.plot(
        theta_ring,
        np.full_like(theta_ring, radius),
        color=GREEN,
        alpha=0.10,
        linewidth=3,
        zorder=1
    )

# Fading sweep trail: broad glow -> narrow glow -> bright core
sweep_glow_outer, = ax.plot(
    [], [], color=GREEN, linewidth=13,
    alpha=0.045, solid_capstyle="round", zorder=3
)

sweep_glow_inner, = ax.plot(
    [], [], color=GREEN, linewidth=7,
    alpha=0.12, solid_capstyle="round", zorder=4
)

sweep_line, = ax.plot(
    [], [], color="#c5ffe5", linewidth=1.8,
    alpha=1.0, solid_capstyle="round", zorder=6
)

# Sweep origin
origin_point, = ax.plot(
    [0], [0],
    marker="o",
    markersize=5,
    color=GREEN,
    markeredgecolor=WHITE,
    zorder=8
)

# Target points
target_points, = ax.plot(
    [], [],
    linestyle="None",
    marker="o",
    markersize=9,
    markerfacecolor=RED,
    markeredgecolor="#ffffff",
    markeredgewidth=1,
    zorder=10
)

distance_labels = []

# ==========================================================
# RIGHT-SIDE HUD PANELS
# ==========================================================

panel_ax = fig.add_subplot(gs[1, 1])
panel_ax.set_facecolor(BG)
panel_ax.set_xlim(0, 1)
panel_ax.set_ylim(0, 1)
panel_ax.axis("off")


def draw_panel(x, y, w, h, title, value, unit="", accent=GREEN):
    """Create a rounded HUD metric card."""

    card = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.0,
        edgecolor=GREEN_DIM,
        facecolor=PANEL,
        alpha=0.98,
        transform=panel_ax.transAxes
    )
    panel_ax.add_patch(card)

    panel_ax.text(
        x + 0.06, y + h * 0.72,
        title.upper(),
        color=MUTED,
        fontsize=8,
        fontweight="bold",
        transform=panel_ax.transAxes
    )

    value_text = panel_ax.text(
        x + 0.06, y + h * 0.25,
        value,
        color=accent,
        fontsize=24,
        fontweight="bold",
        transform=panel_ax.transAxes
    )

    unit_text = panel_ax.text(
        x + w - 0.045, y + h * 0.28,
        unit,
        color=MUTED,
        fontsize=9,
        ha="right",
        transform=panel_ax.transAxes
    )

    return value_text, unit_text


angle_value, angle_unit = draw_panel(
    0.02, 0.76, 0.46, 0.17,
    "Current angle", "90", "DEG", GREEN
)

distance_value, distance_unit = draw_panel(
    0.52, 0.76, 0.46, 0.17,
    "Distance", "--", "CM", CYAN
)

progress_value, progress_unit = draw_panel(
    0.02, 0.55, 0.46, 0.17,
    "Scan progress", "50", "%", GREEN
)

count_value, count_unit = draw_panel(
    0.52, 0.55, 0.46, 0.17,
    "Detection count", "0", "TARGETS", RED
)

# ==========================================================
# CONNECTION STATUS
# ==========================================================

status_card = FancyBboxPatch(
    (0.02, 0.405), 0.96, 0.105,
    boxstyle="round,pad=0.012,rounding_size=0.018",
    linewidth=1,
    edgecolor=GREEN_DIM,
    facecolor=PANEL,
    transform=panel_ax.transAxes
)
panel_ax.add_patch(status_card)

panel_ax.text(
    0.075, 0.47,
    "SENSOR CONNECTION",
    color=MUTED,
    fontsize=8,
    fontweight="bold",
    transform=panel_ax.transAxes
)

connection_value = panel_ax.text(
    0.075, 0.425,
    "● DISCONNECTED",
    color=RED,
    fontsize=12,
    fontweight="bold",
    transform=panel_ax.transAxes
)

# ==========================================================
# SCAN PROGRESS BAR
# ==========================================================

panel_ax.text(
    0.035, 0.355,
    "SWEEP COVERAGE",
    color=MUTED,
    fontsize=9,
    fontweight="bold",
    transform=panel_ax.transAxes
)

bar_x, bar_y, bar_w, bar_h = 0.035, 0.31, 0.93, 0.022

panel_ax.add_patch(
    FancyBboxPatch(
        (bar_x, bar_y), bar_w, bar_h,
        boxstyle="round,pad=0.002,rounding_size=0.008",
        facecolor="#102a24",
        edgecolor=GREEN_DIM,
        linewidth=0.7,
        transform=panel_ax.transAxes
    )
)

progress_bar = FancyBboxPatch(
    (bar_x, bar_y), bar_w * 0.5, bar_h,
    boxstyle="round,pad=0.002,rounding_size=0.008",
    facecolor=GREEN,
    edgecolor="none",
    transform=panel_ax.transAxes
)
panel_ax.add_patch(progress_bar)

# ==========================================================
# LIVE TELEMETRY LOG
# ==========================================================

panel_ax.text(
    0.035, 0.255,
    "TELEMETRY / SYSTEM LOG",
    color=CYAN,
    fontsize=9,
    fontweight="bold",
    transform=panel_ax.transAxes
)

log_text = panel_ax.text(
    0.035, 0.225,
    "Initializing radar system...",
    color=WHITE,
    fontsize=9,
    va="top",
    linespacing=1.8,
    transform=panel_ax.transAxes
)

panel_ax.text(
    0.035, 0.055,
    "PROTOCOL: ANGLE + ULTRASONIC RANGE\n"
    "MODE: CONTINUOUS SWEEP  |  UNITS: CM",
    color=MUTED,
    fontsize=8,
    linespacing=1.8,
    transform=panel_ax.transAxes
)

# ==========================================================
# SERIAL DATA READER
# ==========================================================

def read_sensor_data():
    global current_angle, current_distance
    global last_message, last_data_time, total_detections
    global connection_status, last_reconnect
    global esp32, scan_direction

    # Attempt to reconnect when disconnected.
    if esp32 is None or not esp32.is_open:
        connection_status = "DISCONNECTED"

        if time.monotonic() - last_reconnect >= RECONNECT_INTERVAL:
            last_reconnect = time.monotonic()
            connect_esp32()

        return

    try:
        for _ in range(100):
            if esp32.in_waiting == 0:
                break

            line = esp32.readline().decode(
                "utf-8", errors="ignore"
            ).strip()

            if not line:
                continue

            match = distance_pattern.search(line)

            if match:
                angle = int(match.group(1))
                distance = int(match.group(2))

                if not (0 <= angle <= 180):
                    continue

                current_angle = angle
                current_distance = None
                last_data_time = time.monotonic()
                connection_status = "CONNECTED"

                # Count an object only when its angle was not
                # already occupied by a valid detection.
                if 0 < distance <= MAX_DISTANCE:
                    if angle not in detections:
                        total_detections += 1

                    detections[angle] = distance
                    current_distance = distance

                    last_message = (
                        f"Target detected at {angle} deg, "
                        f"{distance} cm"
                    )
                else:
                    detections.pop(angle, None)
                    last_message = (
                        f"Out of range at {angle} deg"
                    )

            else:
                no_echo = no_echo_pattern.search(line)

                if no_echo:
                    angle = int(no_echo.group(1))

                    if 0 <= angle <= 180:
                        current_angle = angle
                        current_distance = None
                        last_data_time = time.monotonic()
                        connection_status = "CONNECTED"
                        detections.pop(angle, None)

                        last_message = (
                            f"No valid echo at {angle} deg"
                        )

    except (serial.SerialException, OSError) as error:
        connection_status = "DISCONNECTED"
        serial_error = str(error)

        try:
            if esp32 is not None:
                esp32.close()
        except (serial.SerialException, OSError):
            pass

        esp32 = None
        last_message = "Serial connection lost"


# ==========================================================
# ANIMATION UPDATE
# ==========================================================

def update_dashboard(_frame):
    global scan_progress

    read_sensor_data()

    theta = np.deg2rad(current_angle)

    # Glowing radar beam.
    for line, width, alpha, offset in [
        (sweep_glow_outer, 13, 0.045, 0),
        (sweep_glow_inner, 7, 0.12, 0),
        (sweep_line, 1.8, 1.0, 0),
    ]:
        line.set_data(
            [theta, theta],
            [0, MAX_DISTANCE]
        )

    # Keep only recent targets in the visible scan.
    if detections:
        angles = np.deg2rad(list(detections.keys()))
        distances = list(detections.values())

        target_points.set_data(angles, distances)
    else:
        target_points.set_data([], [])

    # Refresh target labels.
    for label in distance_labels:
        label.remove()
    distance_labels.clear()

    for angle, distance in detections.items():
        label = ax.annotate(
            f"{distance} cm",
            xy=(np.deg2rad(angle), distance),
            xytext=(6, 6),
            textcoords="offset points",
            color="#ff8298",
            fontsize=8,
            fontweight="bold"
        )
        distance_labels.append(label)

    # Update live dashboard values.
    angle_value.set_text(str(current_angle))

    if current_distance is None:
        distance_value.set_text("--")
    else:
        distance_value.set_text(str(current_distance))

    scan_progress = (current_angle / 180.0) * 100.0
    progress_value.set_text(f"{scan_progress:.0f}")

    count_value.set_text(str(len(detections)))

    progress_bar.set_width(
        bar_w * (scan_progress / 100.0)
    )

    # Sensor status.
    if connection_status == "CONNECTED":
        connection_value.set_text("● CONNECTED")
        connection_value.set_color(GREEN)
    else:
        connection_value.set_text("● DISCONNECTED")
        connection_value.set_color(RED)

    # Telemetry log.
    if connection_status == "DISCONNECTED":
        message = (
            "Check USB cable / COM port\n"
            f"Port: {PORT}\n"
            "Auto-reconnect: ENABLED"
        )
    else:
        message = (
            f"ANGLE     : {current_angle:3d} deg\n"
            f"DISTANCE  : "
            f"{current_distance if current_distance is not None else '--'} cm\n"
            f"TARGETS   : {len(detections)}\n"
            f"LAST EVENT: {last_message}"
        )

    log_text.set_text(message)

    return (
        sweep_glow_outer,
        sweep_glow_inner,
        sweep_line,
        target_points,
        angle_value,
        distance_value,
        progress_value,
        count_value,
        connection_value,
        progress_bar,
        log_text,
        *distance_labels
    )


# ==========================================================
# RUN DASHBOARD
# ==========================================================

animation = FuncAnimation(
    fig,
    update_dashboard,
    interval=UPDATE_INTERVAL,
    blit=False,
    cache_frame_data=False
)

try:
    plt.show()

except KeyboardInterrupt:
    print("Radar stopped by user.")

finally:
    if esp32 is not None:
        try:
            if esp32.is_open:
                esp32.close()
        except (serial.SerialException, OSError):
            pass

    print("ESP32 serial connection closed.")
