#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import json
import os

from pathlib import Path
from shutil import which

from renode_run.defaults import GLOBAL_ARTIFACTS_PATH, RENODE_RUN_CONFIG_FILENAME, RENODE_TARGET_DIRNAME
from renode_run.utils import RenodeVariant, choose_artifacts_path
from renode_run.package import package_type, RENODE_EXECUTABLE


def download_renode(target_dir_path, config_path, renode_variant, version='latest', direct=False):
    package_path = package_type().get_package_if_exists(target_dir_path, renode_variant, version, direct)
    if package_path is not None:
        print(f"Renode is already present in {package_path}")
        return

    print(f"Downloading Renode ({renode_variant.value})...")

    package = package_type()(renode_variant, version)

    print()
    print("Download finished!")

    os.makedirs(target_dir_path, exist_ok=True)

    (final_path, new_download) = package.extract(target_dir_path, direct)
    
    if not new_download:
        print(f"Renode is already present in {final_path}")
        return

    print(f"Renode stored in {final_path}")

    # If config file already exists, carefully change the path saved in it.
    # We must not disable the path for other variants of Renode.
    config = {}
    if config_path.exists():
        config = json.loads(config_path.read_text())

    config[renode_variant.value] = str(final_path)

    with open(config_path, mode="w") as f:
        json.dump(config, f)


def get_default_renode_path(artifacts_path=None, variant=RenodeVariant.default(), try_to_download=True, use_system_renode=True):
    artifacts_path = choose_artifacts_path(GLOBAL_ARTIFACTS_PATH, artifacts_path)
    return get_renode(
        artifacts_dir=artifacts_path,
        variant=variant,
        try_to_download=try_to_download,
        use_system_renode=use_system_renode,
    )


def get_renode(artifacts_dir, variant=RenodeVariant.default(), try_to_download=True, use_system_renode=True):
    # First, we try <artifacts_dir>, then we look in $PATH
    renode_path = None
    renode_run_config = artifacts_dir / RENODE_RUN_CONFIG_FILENAME
    if renode_run_config.exists():
        config = json.loads(renode_run_config.read_text())
        if renode_path := config.get(variant.value):
            renode_path = Path(renode_path) / RENODE_EXECUTABLE
            if renode_path.exists():
                print(f"Renode found in {renode_path}")
                return renode_path
            else:
                print(f"Renode-run download listed in {renode_run_config}, but the target directory {renode_path} was not found.")

    if use_system_renode:
        print("Looking in $PATH...")
        renode_path = which(RENODE_EXECUTABLE)

    if renode_path is None:
        if try_to_download:
            print('Renode not found. Downloading...')
            download_renode(
                target_dir_path=artifacts_dir / RENODE_TARGET_DIRNAME,
                config_path=artifacts_dir / RENODE_RUN_CONFIG_FILENAME,
                renode_variant=variant,
            )
            return get_renode(
                artifacts_dir=artifacts_dir,
                variant=variant,
                try_to_download=False,
                use_system_renode=use_system_renode,
            )
        else:
            print("Renode not found, could not download. Please run `renode-run download` manually or visit https://builds.renode.io")

    else:
        renode_path = Path(renode_path)
        print(f"Renode found in $PATH: {renode_path}. If you want to use the latest Renode version, consider running 'renode-run download'")

    return renode_path
