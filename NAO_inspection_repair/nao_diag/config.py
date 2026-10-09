# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import copy
import io
import json
import math


DEFAULT_CONFIG = {
    "thresholds": {
        "battery_warn_below_percent": 25.0,
        "joint_temperature_warn_c": 50.0,
        "joint_temperature_fail_c": 60.0,
        "motion_min_battery_percent": 50.0,
        "fsr_min_standing_weight_kg": 1.0,
        "fsr_min_each_foot_kg": 0.5,
        "fsr_standing_min_mass_fraction": 0.60,
        "fsr_standing_max_mass_fraction": 1.40,
        "fsr_each_foot_min_mass_fraction": 0.12,
        "walk_min_fsr_fraction": 0.25,
        "walk_max_tilt_rad": 0.35,
        "joint_static_error_warn_rad": 0.08,
        "joint_static_error_fail_rad": 0.15,
        "joint_motion_error_fail_rad": 0.12,
        "joint_motion_min_fraction": 0.45,
        "camera_mean_min": 5.0,
        "camera_mean_max": 250.0,
        "camera_stddev_min": 3.0,
        "audio_min_energy_rise": 150.0,
        "audio_min_ratio": 1.35,
        "sonar_min_m": 0.15,
        "sonar_max_m": 2.55,
        "board_observation_seconds": 1.0
    },
    "sampling": {
        "imu_samples": 20,
        "imu_interval_seconds": 0.05,
        "sonar_samples": 10,
        "sonar_interval_seconds": 0.10,
        "audio_samples": 14,
        "audio_interval_seconds": 0.08,
        "touch_timeout_seconds": 8.0,
        "camera_resolution": 1,
        "camera_color_space": 11,
        "camera_fps": 5
    },
    "motion": {
        "stiffness": 0.35,
        "duration_seconds": 0.9,
        "joint_amplitude_rad": 0.10,
        "hand_amplitude": 0.15,
        "limit_margin_rad": 0.15,
        "walk_distance_m": 0.08,
        "walk_speed_fraction": 0.25
    },
    "logging": {
        "remote_tail_lines": 3000,
        "max_samples_per_severity": 30
    }
}


def deep_merge(base, override):
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(path=None):
    if not path:
        result = copy.deepcopy(DEFAULT_CONFIG)
        validate_config(result)
        return result
    with io.open(path, "r", encoding="utf-8") as handle:
        custom = json.load(handle)
    result = deep_merge(DEFAULT_CONFIG, custom)
    validate_config(result)
    return result


def _bounded(config, section, key, minimum, maximum):
    value = config[section][key]
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s.%s 必须是数字" % (section, key))
    if math.isnan(number) or math.isinf(number) or number < minimum or number > maximum:
        raise ValueError(
            "%s.%s=%r 超出安全范围 [%s, %s]" %
            (section, key, value, minimum, maximum))
    config[section][key] = number
    return number


def validate_config(config):
    """Reject overrides that could turn an acceptance threshold into unsafe motion."""
    _bounded(config, "thresholds", "battery_warn_below_percent", 0.0, 100.0)
    motion_battery = _bounded(config, "thresholds", "motion_min_battery_percent", 40.0, 100.0)
    warn_temp = _bounded(config, "thresholds", "joint_temperature_warn_c", 35.0, 55.0)
    fail_temp = _bounded(config, "thresholds", "joint_temperature_fail_c", 45.0, 65.0)
    if warn_temp > fail_temp:
        raise ValueError("joint_temperature_warn_c 不能高于 joint_temperature_fail_c")
    _bounded(config, "thresholds", "fsr_min_standing_weight_kg", 0.5, 3.0)
    _bounded(config, "thresholds", "fsr_min_each_foot_kg", 0.2, 2.0)
    standing_min_fraction = _bounded(
        config, "thresholds", "fsr_standing_min_mass_fraction", 0.50, 0.80)
    standing_max_fraction = _bounded(
        config, "thresholds", "fsr_standing_max_mass_fraction", 1.20, 1.80)
    each_foot_fraction = _bounded(
        config, "thresholds", "fsr_each_foot_min_mass_fraction", 0.08, 0.25)
    if standing_min_fraction >= standing_max_fraction:
        raise ValueError("fsr_standing_min_mass_fraction 必须低于 fsr_standing_max_mass_fraction")
    if each_foot_fraction * 2.0 > standing_min_fraction:
        raise ValueError("双脚最低质量比例之和不能高于站立总重最低比例")
    _bounded(config, "thresholds", "walk_min_fsr_fraction", 0.10, 0.50)
    _bounded(config, "thresholds", "walk_max_tilt_rad", 0.20, 0.45)
    static_warn = _bounded(config, "thresholds", "joint_static_error_warn_rad", 0.02, 0.12)
    static_fail = _bounded(config, "thresholds", "joint_static_error_fail_rad", 0.05, 0.20)
    if static_warn > static_fail:
        raise ValueError("joint_static_error_warn_rad 不能高于 joint_static_error_fail_rad")
    _bounded(config, "thresholds", "joint_motion_error_fail_rad", 0.02, 0.20)
    _bounded(config, "thresholds", "joint_motion_min_fraction", 0.20, 0.90)
    _bounded(config, "sampling", "touch_timeout_seconds", 3.0, 30.0)
    _bounded(config, "sampling", "camera_fps", 1.0, 15.0)
    _bounded(config, "motion", "stiffness", 0.10, 0.50)
    _bounded(config, "motion", "duration_seconds", 0.50, 3.00)
    _bounded(config, "motion", "joint_amplitude_rad", 0.02, 0.15)
    _bounded(config, "motion", "hand_amplitude", 0.05, 0.25)
    _bounded(config, "motion", "limit_margin_rad", 0.05, 0.40)
    _bounded(config, "motion", "walk_distance_m", 0.03, 0.20)
    _bounded(config, "motion", "walk_speed_fraction", 0.05, 0.35)
    _bounded(config, "logging", "remote_tail_lines", 100.0, 10000.0)
    if motion_battery < config["thresholds"]["battery_warn_below_percent"]:
        raise ValueError("motion_min_battery_percent 不能低于 battery_warn_below_percent")
    return config

