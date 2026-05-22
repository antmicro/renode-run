#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import os

from pathlib import Path
from shutil import which, rmtree

from renode_run.defaults import GLOBAL_ARTIFACTS_PATH, RENODE_RUN_CONFIG_FILENAME, RENODE_TARGET_DIRNAME
from renode_run.utils import RenodeVariant, choose_artifacts_path, ConfigFile
from renode_run.package import package_type, RENODE_EXECUTABLE


def get_package_if_exists(config, target_dir_path, renode_variant, version, direct):
    package_path = package_type().build_package_path(target_dir_path, renode_variant, version, direct)
    (package_version, package_variant) = config.get_package_info(package_path)
    correct_version = (package_version == version) and (package_variant == renode_variant.value)
    if correct_version and package_type().path_contains_renode(package_path):
        return package_path
    else:
        return None


def download_renode(target_dir_path, config_path, renode_variant, version='latest', direct=False, force=False):
    config = ConfigFile(config_path)

    if force:
        if version == 'latest':
            _, latest_version = config.get_latest_data()
            if latest_version is not None:
                package_dir = package_type().build_package_path(target_dir_path, renode_variant, latest_version, direct)
                rmtree(package_dir)
        else:
            package_dir = package_type().build_package_path(target_dir_path, renode_variant, version, direct)
            rmtree(package_dir)
    else:
        if version == 'latest':
            latest_date, latest_version = config.get_latest_data()
            if latest_date is not None:
                print(f"Renode latest version ({latest_version}) was already downloaded today ({latest_date}).\nChecking if present in the target directory...")
                version = latest_version

        package_path = get_package_if_exists(config, target_dir_path, renode_variant, version, direct)
        if package_path is not None:
            print(f"Renode is already present in {package_path}")
            config.update_default(renode_variant, package_path)
            config.save_config()
            return

    print(f"Downloading Renode ({renode_variant.value})...")

    package = package_type()(renode_variant, version)

    print()
    print("Download finished!")

    os.makedirs(target_dir_path, exist_ok=True)

    (final_path, renode_version_str) = package.extract(target_dir_path, direct)

    print(f"Renode stored in {final_path}")

    config.update_download(renode_variant, renode_version_str, final_path, version == 'latest')
    config.save_config()


def get_default_renode_path(artifacts_path=None, variant=RenodeVariant.default(), try_to_download=True, use_system_renode=True):
    artifacts_path = choose_artifacts_path(GLOBAL_ARTIFACTS_PATH, artifacts_path)
    return get_renode(
        artifacts_dir=artifacts_path,
        variant=variant,
        try_to_download=try_to_download,
        use_system_renode=use_system_renode,
    )


def get_installed_renode(config, variant=RenodeVariant.default()):
    default_version_path_str = config.get_default_path(variant)
    if default_version_path_str is not None:
        default_version_path = Path(default_version_path_str)
        if package_type().path_contains_renode(default_version_path):
            return Path(default_version_path) / RENODE_EXECUTABLE

    for (path_str, (_, variant_str)) in config.get_renode_installs():
        path = Path(path_str)
        if variant_str == variant.value and package_type().path_contains_renode(path):
            return path / RENODE_EXECUTABLE


def get_renode(artifacts_dir, variant=RenodeVariant.default(), try_to_download=True, use_system_renode=True):
    config_path = artifacts_dir / RENODE_RUN_CONFIG_FILENAME
    config = ConfigFile(config_path)

    renode_path = None
    if renode_path := get_installed_renode(config, variant):
        return renode_path

    if use_system_renode:
        print("Looking in $PATH...")
        renode_path = which(RENODE_EXECUTABLE)

    if renode_path is None:
        if try_to_download:
            print('Renode not found. Downloading...')
            download_renode(
                target_dir_path=artifacts_dir / RENODE_TARGET_DIRNAME,
                config_path=config_path,
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
