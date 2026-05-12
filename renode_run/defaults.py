#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import os

from pathlib import Path

DASHBOARD_LINK = "https://zephyr-dashboard.renode.io"

DEFAULT_RENODE_ARTIFACTS_DIR = Path.home() / ".config" / "renode"

GLOBAL_ARTIFACTS_PATH = None

RENODE_RUN_CONFIG_FILENAME = "renode-run.json"
RENODE_TARGET_DIRNAME = "renode-run.download"
RENODE_TEST_VENV_DIRNAME = "renode-run.venv"

def get_venv_executable(venv_path):
    if os.name == 'posix':
        return venv_path / 'bin' / 'python'
    elif os.name == 'nt':
        return venv_path / 'Scripts' / 'python.exe'
    else:
        raise Exception("Unsupported platform, renode-run is supported only on Linux, Windows and MacOS")
