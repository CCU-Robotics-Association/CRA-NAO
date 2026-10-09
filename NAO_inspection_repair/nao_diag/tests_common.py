# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import unicode_literals
import math
import struct
import time
from array import array
from .compat import mean, safe_float, stddev, to_text
from .model import Stopwatch, make_result

def finish(timer, test_id, label, status, summary, metrics=None, details=None,
           artifacts=None):
    return make_result(
        test_id, label, status, summary, metrics=metrics, details=details,
        artifacts=artifacts, started_at=timer.started_at,
        duration_ms=timer.elapsed_ms(),
    )

def active_value(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    number = safe_float(value, None)
    if number is not None:
        return abs(number) > 1e-9
    return to_text(value).strip().lower() not in ("", "false", "none", "ok", "normal", "0")

def sample_memory(client, keys, count, interval_seconds):
    samples = dict((key, []) for key in keys)
    for index in range(int(count)):
        values = client.memory_values(keys)
        for key in keys:
            number = safe_float(values.get(key), None)
            if number is not None:
                samples[key].append(number)
        if index + 1 < int(count):
            time.sleep(float(interval_seconds))
    return samples

def statistics(values):
    values = [safe_float(value, None) for value in values]
    values = [value for value in values if value is not None]
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None, "stddev": None}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": mean(values),
        "stddev": stddev(values),
    }

def temperature_snapshot(client, joint_names):
    value_keys = ["Device/SubDeviceList/%s/Temperature/Sensor/Value" % name
                  for name in joint_names]
    status_keys = ["Device/SubDeviceList/%s/Temperature/Sensor/Status" % name
                   for name in joint_names]
    values = client.memory_values(value_keys + status_keys)
    rows = []
    for name, value_key, status_key in zip(joint_names, value_keys, status_keys):
        rows.append({
            "joint": to_text(name),
            "temperature_c": safe_float(values.get(value_key), None),
            "temperature_status": safe_float(values.get(status_key), None),
        })
    return rows

def image_bytes(value):
    if value is None:
        return bytearray()
    if isinstance(value, bytearray):
        return value
    if isinstance(value, bytes):
        return bytearray(value)
    try:
        return bytearray(value)
    except Exception:
        return bytearray(to_text(value).encode("latin1", "replace"))

def rgb_statistics(data, pixel_stride=53):
    raw = image_bytes(data)
    if len(raw) < 3:
        return {"mean": 0.0, "stddev": 0.0, "dark_fraction": 1.0,
                "bright_fraction": 0.0, "sample_pixels": 0}
    luminance = []
    step = max(1, int(pixel_stride)) * 3
    for index in range(0, len(raw) - 2, step):
        red, green, blue = raw[index], raw[index + 1], raw[index + 2]
        luminance.append(0.299 * red + 0.587 * green + 0.114 * blue)
    dark = len([item for item in luminance if item <= 5.0])
    bright = len([item for item in luminance if item >= 250.0])
    count = float(len(luminance) or 1)
    return {
        "mean": mean(luminance),
        "stddev": stddev(luminance),
        "dark_fraction": dark / count,
        "bright_fraction": bright / count,
        "sample_pixels": len(luminance),
    }

def write_rgb_bmp(path, width, height, data):
    raw = image_bytes(data)
    expected = int(width) * int(height) * 3
    if len(raw) < expected:
        raise ValueError("RGB frame 过短: %d < %d" % (len(raw), expected))
    width = int(width)
    height = int(height)
    row_bytes = width * 3
    padded_row_bytes = (row_bytes + 3) & ~3
    padding = [0] * (padded_row_bytes - row_bytes)
    pixels = array("B")
    for y_value in range(height - 1, -1, -1):
        offset = y_value * row_bytes
        for x_value in range(width):
            source = offset + x_value * 3
            pixels.extend([raw[source + 2], raw[source + 1], raw[source]])
        if padding:
            pixels.extend(padding)
    pixel_blob = pixels.tostring() if hasattr(pixels, "tostring") else pixels.tobytes()
    file_size = 54 + len(pixel_blob)
    header = b"BM" + struct.pack("<IHHI", file_size, 0, 0, 54)
    dib = struct.pack("<IIIHHIIIIII", 40, width, height, 1, 24, 0,
                      len(pixel_blob), 2835, 2835, 0, 0)
    with open(path, "wb") as handle:
        handle.write(header)
        handle.write(dib)
        handle.write(pixel_blob)

def clamp_target(current, low, high, amplitude, margin):
    safe_low = low + margin
    safe_high = high - margin
    if safe_low > safe_high:
        safe_low, safe_high = low, high
    positive = min(current + amplitude, safe_high)
    negative = max(current - amplitude, safe_low)
    if abs(positive - current) >= abs(negative - current):
        return positive
    return negative
