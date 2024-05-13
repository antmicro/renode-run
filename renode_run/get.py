# Copyright (c) 2024 Antmicro

import datetime
import json
import os
import re
import sys
import tarfile
import time

from pathlib import Path
from shutil import which
from urllib import request, error

from renode_run.defaults import RENODE_RUN_CONFIG_FILENAME, RENODE_TARGET_DIRNAME
from renode_run.utils import RenodeVariant


DOWNLOAD_PROGRESS_DELAY = 1


def _report_progress():
    start_time = previous_time = time.time()

    def aux(count, size, filesize):
        nonlocal previous_time
        current_time = time.time()

        if previous_time + DOWNLOAD_PROGRESS_DELAY > current_time and count != 0 and size * count < filesize:
            return

        previous_time = current_time
        total = filesize / (1024 * 1024.0)
        current = count * size * 1.0 / (1024 * 1024.0)
        current = min(current, total)

        time_elapsed = datetime.timedelta(seconds=current_time - start_time)
        print(f"Downloaded {current:.2f}MB / {total:.2f}MB (time elapsed: {time_elapsed})...", end='\r')
    return aux


def download_renode(target_dir_path, config_path, renode_variant, version='latest', direct=False):
    if not sys.platform.startswith('linux'):
        raise Exception("Renode can only be automatically downloaded on Linux. On other OSes please visit https://builds.renode.io and install the latest package for your system.")

    print(f"Downloading Renode ({renode_variant.value})...")

    match renode_variant:
        case RenodeVariant.MONO_PORTABLE:
            package_name = f"renode-{version}.linux-portable.tar.gz"
        case RenodeVariant.DOTNET_PORTABLE:
            package_name = f"renode-{version}.linux-portable-dotnet.tar.gz"

    try:
        renode_package, _ = request.urlretrieve(f"https://builds.renode.io/{package_name}", reporthook=_report_progress())
    except error.HTTPError:
        print("Renode could not be downloaded. Check if you have working internet connection and provided Renode version is correct (if specified)")
        sys.exit(1)

    print()
    print("Download finished!")

    os.makedirs(target_dir_path, exist_ok=True)
    try:
        with tarfile.open(renode_package) as tar:
            name = tar.members[0].name

            # This regex searches for "<semver>+<date>git<commit>".
            # - semver -- Semantic version (e.g. 0.0.0)
            # - data -- format YYYYMMDD
            # - commit -- consists of 8-9 first characters of commit SHA
            matched = re.search(r"[0-9]+\.[0-9]+\.[0-9]+\+[0-9]{8}git[0-9a-fA-F]{8,9}", tar.members[0].name)
            if not matched:
                print(f"Can't find proper renode version string in {name}")
                return

            renode_version = matched.group(0)

            if direct:
                # When the --direct argument is passed, we would like to
                # extract contents of the archive directly to the path given by the user,
                # and not into a new directory.
                # Therefore we iterate over all files (paths) in the archive,
                # and strip them from the first part, which is the renode_<version>
                # directory.
                final_path = target_dir_path
            else:
                final_path = target_dir_path / f"{renode_variant.value}/renode-{renode_version}"

            if Path.exists(final_path / 'renode'):
                print(f"Renode is already present in {final_path}")
                return

            members = tar.getmembers()
            for member in members:
                old_member_path = Path(member.path).parts[1:]
                member.path = Path(*old_member_path)

            tar.extractall(final_path, members=members)
            print(f"Renode stored in {final_path}")

        # If config file already exists, carefully change the path saved in it.
        # We must not disable the path for other variants of Renode.
        config = {}
        if config_path.exists():
            config = json.loads(config_path.read_text())

        config[renode_variant.value] = str(final_path)

        with open(config_path, mode="w") as f:
            json.dump(config, f)

    finally:
        os.remove(renode_package)


def get_renode(artifacts_dir, variant=RenodeVariant.MONO_PORTABLE, try_to_download=True, use_system_renode=True):
    # First, we try <artifacts_dir>, then we look in $PATH
    renode_path = None
    renode_run_config = artifacts_dir / RENODE_RUN_CONFIG_FILENAME
    if renode_run_config.exists():
        config = json.loads(renode_run_config.read_text())
        if renode_path := config.get(variant.value):
            renode_path = Path(renode_path) / "renode"
            if renode_path.exists():
                print(f"Renode found in {renode_path}")
                return str(renode_path)  # returning str to match the result of `which`
            else:
                print(f"Renode-run download listed in {renode_run_config}, but the target directory {renode_path} was not found.")

    if use_system_renode:
        print("Looking in $PATH...")
        renode_path = which("renode")

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
        print(f"Renode found in $PATH: {renode_path}. If you want to use the latest Renode version, consider running 'renode-run download'")

    return renode_path
