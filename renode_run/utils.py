# Copyright (c) 2024 Antmicro

import functools
import requests

from enum import Enum

from renode_run.defaults import DASHBOARD_LINK, DEFAULT_RENODE_ARTIFACTS_DIR


class RenodeVariant(str, Enum):
    DOTNET_PORTABLE = "dotnet-portable"
    MONO_PORTABLE = "mono-portable"


def choose_artifacts_path(lower_priority_path, higher_priority_path):
    if higher_priority_path is not None:
        return higher_priority_path
    if lower_priority_path is not None:
        return lower_priority_path
    return DEFAULT_RENODE_ARTIFACTS_DIR


@functools.lru_cache
def fetch_zephyr_version():
    version = requests.get(f"{DASHBOARD_LINK}/zephyr_sim/latest")
    return version.text.strip()


@functools.lru_cache
def fetch_renode_version():
    version = requests.get(f"{DASHBOARD_LINK}/zephyr_sim/{fetch_zephyr_version()}/latest")
    return version.text.strip()
