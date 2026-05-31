#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
virtual_ais_clock_bitstring_websocket_sender.py

Generate virtual AIS clock targets and send AIS payload bitstrings to
Mictronics ais-simulator Websocket PDU block.

Target flow:
    This script
      -> ws://127.0.0.1:52002
      -> Websocket PDU block
      -> bitstring_to_frame block
      -> GMSK modulator

This script sends AIS payload bits only.
It does NOT generate NMEA !AIVDM sentences.
It does NOT transmit RF by itself.

Safety:
- Use for software simulation / closed lab testing only.
- Do not radiate AIS signals over the air.
"""

import math
import time
from datetime import datetime, timezone, timedelta

import websocket


# =========================================================
# WebSocket setting
# =========================================================

WS_URL = "ws://127.0.0.1:52002"

# =========================================================
# Clock setting
# =========================================================

CENTER_LAT = 0.0
CENTER_LON = 0.0

USE_MELBOURNE_TIME = True
MELBOURNE_TZ = timezone(timedelta(hours=11))  # simple fixed AEDT-style offset

# 5秒待つのではなく、全船を順番に200ms間隔で出し続ける
# 24船なら、1周は 24 x 0.2 = 約4.8秒。
UPDATE_INTERVAL = 0.0
STATIC_INFO_INTERVAL = 60.0

# 1船あたりの送信間隔
POSITION_MESSAGE_GAP = 0.2
STATIC_MESSAGE_GAP = 0.2

# 秒針なし
HOUR_HAND_LENGTH_NM = 4.0
MINUTE_HAND_LENGTH_NM = 7.0
MARKER_RING_RADIUS_NM = 9.8

HOUR_HAND_SHIPS = 4
MINUTE_HAND_SHIPS = 7

CENTER_MMSI = 999000001
HOUR_BASE_MMSI = 999001000
MINUTE_BASE_MMSI = 999002000
MARKER_BASE_MMSI = 999004000

SHIP_TYPE_CENTER = 37
SHIP_TYPE_HOUR = 36
SHIP_TYPE_MINUTE = 52
SHIP_TYPE_MARKER = 31

CENTER_SOG_KN = 0.0
HOUR_SOG_KN = 0.0
MINUTE_SOG_KN = 0.1
MARKER_SOG_KN = 0.0


# =========================================================
# AIS bit utility
# =========================================================

def twos_complement(value: int, bits: int) -> int:
    if value < 0:
        value = (1 << bits) + value
    return value


def int_to_bits(value: int, width: int) -> str:
    return format(value & ((1 << width) - 1), f"0{width}b")


def ais_char_to_sixbit(c: str) -> int:
    c = c.upper()
    table = "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_ !\"#$%&'()*+,-./0123456789:;<=>?"
    idx = table.find(c)
    if idx < 0:
        idx = table.find(" ")
    return idx


def ais_string_to_bits(text: str, length_chars: int) -> str:
    text = text[:length_chars].ljust(length_chars)
    return "".join(int_to_bits(ais_char_to_sixbit(ch), 6) for ch in text)


# =========================================================
# AIS Message 1 / 24 payload bit generation
# =========================================================

def encode_ais_position_report_bits(
    mmsi: int,
    lat_deg: float,
    lon_deg: float,
    sog_kn: float = 0.0,
    cog_deg: float = 0.0,
    heading_deg: int = 511,
    nav_status: int = 0,
    timestamp_sec: int | None = None,
    pos_acc: int = 0,
) -> str:
    """AIS Message 1 payload bits, usually 168 bits."""
    if timestamp_sec is None:
        timestamp_sec = datetime.utcnow().second

    lon_ais = int(round(lon_deg * 60 * 10000))
    lat_ais = int(round(lat_deg * 60 * 10000))

    lon_ais = twos_complement(lon_ais, 28)
    lat_ais = twos_complement(lat_ais, 27)

    sog_ais = int(round(sog_kn * 10))
    sog_ais = min(sog_ais, 1022)

    cog_ais = int(round(cog_deg * 10)) % 3600

    if heading_deg < 0 or heading_deg > 359:
        heading_deg = 511

    rot_ais = 128  # not available

    bits = ""
    bits += int_to_bits(1, 6)                    # message ID
    bits += int_to_bits(0, 2)                    # repeat indicator
    bits += int_to_bits(mmsi, 30)                # MMSI
    bits += int_to_bits(nav_status, 4)           # nav status
    bits += int_to_bits(rot_ais, 8)              # ROT
    bits += int_to_bits(sog_ais, 10)             # SOG
    bits += int_to_bits(pos_acc, 1)              # position accuracy
    bits += int_to_bits(lon_ais, 28)             # longitude
    bits += int_to_bits(lat_ais, 27)             # latitude
    bits += int_to_bits(cog_ais, 12)             # COG
    bits += int_to_bits(heading_deg, 9)          # heading
    bits += int_to_bits(timestamp_sec % 60, 6)   # timestamp
    bits += int_to_bits(0, 2)                    # maneuver indicator
    bits += int_to_bits(0, 3)                    # spare
    bits += int_to_bits(0, 1)                    # RAIM
    bits += int_to_bits(0, 19)                   # radio status
    return bits


def encode_ais_msg24_part_a_bits(mmsi: int, ship_name: str) -> str:
    """AIS Message 24 Part A payload bits, 160 bits."""
    bits = ""
    bits += int_to_bits(24, 6)
    bits += int_to_bits(0, 2)
    bits += int_to_bits(mmsi, 30)
    bits += int_to_bits(0, 2)                    # part A
    bits += ais_string_to_bits(ship_name, 20)
    return bits


def encode_ais_msg24_part_b_bits(
    mmsi: int,
    ship_type: int = 36,
    vendor_id: str = "CLK",
    callsign: str = "CLOCK",
    dim_bow: int = 1,
    dim_stern: int = 1,
    dim_port: int = 1,
    dim_starboard: int = 1,
) -> str:
    """AIS Message 24 Part B payload bits."""
    bits = ""
    bits += int_to_bits(24, 6)
    bits += int_to_bits(0, 2)
    bits += int_to_bits(mmsi, 30)
    bits += int_to_bits(1, 2)                    # part B
    bits += int_to_bits(ship_type, 8)
    bits += ais_string_to_bits(vendor_id, 3)
    bits += ais_string_to_bits("", 4)            # model/serial placeholder
    bits += ais_string_to_bits(callsign, 7)
    bits += int_to_bits(dim_bow, 9)
    bits += int_to_bits(dim_stern, 9)
    bits += int_to_bits(dim_port, 6)
    bits += int_to_bits(dim_starboard, 6)
    bits += int_to_bits(0, 6)
    return bits


# =========================================================
# Clock target generation
# =========================================================

def point_from_center_nm(center_lat: float, center_lon: float, radius_nm: float, bearing_deg: float):
    rad = math.radians(bearing_deg)
    dlat_deg = (radius_nm * math.cos(rad)) / 60.0

    cos_lat = math.cos(math.radians(center_lat))
    if abs(cos_lat) < 1e-9:
        cos_lat = 1e-9

    dlon_deg = (radius_nm * math.sin(rad)) / (60.0 * cos_lat)
    return center_lat + dlat_deg, center_lon + dlon_deg


def clock_angles(now: datetime):
    # 秒針は作らないが、分針・時針を滑らかにするため秒は使う
    sec = now.second + now.microsecond / 1_000_000.0
    minute = now.minute + sec / 60.0
    hour = (now.hour % 12) + minute / 60.0

    min_angle = minute * 6.0
    hour_angle = hour * 30.0
    return hour_angle, min_angle


def make_hand_ships(base_mmsi, prefix, count, max_radius_nm, angle_deg, inward, ship_type, sog_kn):
    ships = []
    for i in range(1, count + 1):
        r = max_radius_nm * i / count
        lat, lon = point_from_center_nm(CENTER_LAT, CENTER_LON, r, angle_deg)
        course = (angle_deg + 180.0) % 360.0 if inward else angle_deg % 360.0

        ships.append({
            "mmsi": base_mmsi + i,
            "name": f"{prefix}{i:02d}",
            "lat": lat,
            "lon": lon,
            "cog": course,
            "hdg": int(round(course)) % 360,
            "ship_type": ship_type,
            "sog_kn": sog_kn,
        })
    return ships


def make_hour_markers():
    ships = []
    for hour_index in range(12):
        angle_deg = hour_index * 30.0
        lat, lon = point_from_center_nm(CENTER_LAT, CENTER_LON, MARKER_RING_RADIUS_NM, angle_deg)
        course = (angle_deg + 180.0) % 360.0

        ships.append({
            "mmsi": MARKER_BASE_MMSI + hour_index,
            "name": f"M{hour_index:02d}",
            "lat": lat,
            "lon": lon,
            "cog": course,
            "hdg": int(round(course)) % 360,
            "ship_type": SHIP_TYPE_MARKER,
            "sog_kn": MARKER_SOG_KN,
        })
    return ships


def generate_clock_targets():
    now = datetime.now(MELBOURNE_TZ) if USE_MELBOURNE_TIME else datetime.utcnow()
    hour_angle, min_angle = clock_angles(now)

    targets = [{
        "mmsi": CENTER_MMSI,
        "name": "CENTER",
        "lat": CENTER_LAT,
        "lon": CENTER_LON,
        "cog": 0.0,
        "hdg": 0,
        "ship_type": SHIP_TYPE_CENTER,
        "sog_kn": CENTER_SOG_KN,
    }]

    targets.extend(make_hour_markers())

    targets.extend(make_hand_ships(
        HOUR_BASE_MMSI,
        "HOUR",
        HOUR_HAND_SHIPS,
        HOUR_HAND_LENGTH_NM,
        hour_angle,
        inward=True,
        ship_type=SHIP_TYPE_HOUR,
        sog_kn=HOUR_SOG_KN,
    ))

    targets.extend(make_hand_ships(
        MINUTE_BASE_MMSI,
        "MIN",
        MINUTE_HAND_SHIPS,
        MINUTE_HAND_LENGTH_NM,
        min_angle,
        inward=True,
        ship_type=SHIP_TYPE_MINUTE,
        sog_kn=MINUTE_SOG_KN,
    ))

    return targets, now


# =========================================================
# WebSocket sender
# =========================================================

def send_bitstring(ws, bits: str, label: str = ""):
    # Mictronics bitstring_to_frame accepts a string of 0/1 bits.
    ws.send(bits)
    if label:
        print(f"sent {label}: {len(bits)} bits")


def send_static_info(ws, targets):
    for t in targets:
        part_a = encode_ais_msg24_part_a_bits(t["mmsi"], t["name"])
        send_bitstring(ws, part_a, f"24A {t['name']} {t['mmsi']}")
        time.sleep(STATIC_MESSAGE_GAP)

        part_b = encode_ais_msg24_part_b_bits(
            t["mmsi"],
            ship_type=t["ship_type"],
            vendor_id="CLK",
            callsign=t["name"][:7],
            dim_bow=1,
            dim_stern=1,
            dim_port=1,
            dim_starboard=1,
        )
        send_bitstring(ws, part_b, f"24B {t['name']} {t['mmsi']}")
        time.sleep(STATIC_MESSAGE_GAP)


def send_position_reports(ws, targets, now):
    for t in targets:
        bits = encode_ais_position_report_bits(
            mmsi=t["mmsi"],
            lat_deg=t["lat"],
            lon_deg=t["lon"],
            sog_kn=t["sog_kn"],
            cog_deg=t["cog"],
            heading_deg=t["hdg"],
            nav_status=0,
            timestamp_sec=now.second,
        )
        send_bitstring(ws, bits, f"1 {t['name']} {t['mmsi']}")
        time.sleep(POSITION_MESSAGE_GAP)


def main():
    print(f"Connecting to {WS_URL} ...")
    ws = websocket.create_connection(WS_URL)
    print("Connected.")

    last_static_sent = 0.0

    try:
        while True:
            targets, now = generate_clock_targets()
            current_time = time.time()

            if current_time - last_static_sent >= STATIC_INFO_INTERVAL:
                print("Sending static info...")
                send_static_info(ws, targets)
                last_static_sent = current_time

            print(f"Sending position reports: {now.isoformat()}")
            send_position_reports(ws, targets, now)

            time.sleep(UPDATE_INTERVAL)

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        ws.close()


if __name__ == "__main__":
    main()
