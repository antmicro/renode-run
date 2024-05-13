# Copyright (c) 2024 Antmicro

from pathlib import Path

DASHBOARD_LINK = "https://new-zephyr-dashboard.renode.io"

DEFAULT_RENODE_ARTIFACTS_DIR = Path.home() / ".config" / "renode"

GLOBAL_ARTIFACTS_PATH = None

RENODE_RUN_CONFIG_FILENAME = "renode-run.json"
RENODE_TARGET_DIRNAME = "renode-run.download"
RENODE_TEST_VENV_DIRNAME = "renode-run.venv"
