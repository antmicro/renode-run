import datetime
import os
import sys
import tarfile
import time

from pathlib import Path
from shutil import which
from urllib import request, error

from renode_run.defaults import RENODE_RUN_CONFIG_FILENAME, RENODE_TARGET_DIRNAME


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


def download_renode(target_dir_path, config_path, version='latest', direct=False):
    if not sys.platform.startswith('linux'):
        raise Exception("Renode can only be automatically downloaded on Linux. On other OSes please visit https://builds.renode.io and install the latest package for your system.")

    print('Downloading Renode...')

    try:
        renode_package, _ = request.urlretrieve(f"https://builds.renode.io/renode-{version}.linux-portable.tar.gz", reporthook=_report_progress())
    except error.HTTPError:
        print("Renode could not be downloaded. Check if you have working internet connection and provided Renode version is correct (if specified)")
        sys.exit(1)

    print()
    print("Download finished!")

    os.makedirs(target_dir_path, exist_ok=True)
    try:
        with tarfile.open(renode_package) as tar:
            if direct:
                # When the --direct argument is passed, we would like to
                # extract contents of the archive directly to the path given by the user,
                # and not into a new directory.
                # Therefore we iterate over all files (paths) in the archive,
                # and strip them from the first part, which is the renode_<version>
                # directory.
                final_path = target_dir_path
                renode_bin_path = final_path / 'renode'
                if Path.exists(renode_bin_path):
                    print(f"Renode is already present in {target_dir_path}")
                    return
                members = tar.getmembers()
                for member in members:
                    old_member_path = Path(member.path).parts[1:]
                    member.path = Path(*old_member_path)
                tar.extractall(target_dir_path, members=members)
            else:
                renode_version = tar.members[0].name
                final_path = target_dir_path / renode_version
                if Path.exists(final_path):
                    print(f"Renode {renode_version} is already available in {target_dir_path}, keeping the previous version")
                    return
                tar.extractall(target_dir_path)
            print(f"Renode stored in {final_path}")

        with open(config_path, mode="w") as config:
            config.write(str(final_path))
    finally:
        os.remove(renode_package)


def get_renode(artifacts_dir, try_to_download=True):
    # First, we try <artifacts_dir>, then we look in $PATH
    renode_path = None
    renode_run_config = artifacts_dir / RENODE_RUN_CONFIG_FILENAME
    if Path.exists(renode_run_config):
        with open(renode_run_config, mode="r") as config:
            renode_path = Path(config.read()) / "renode"
            if Path.exists(renode_path):
                print(f"Renode found in {renode_path}")
                return str(renode_path)  # returning str to match the result of `which`
            else:
                print(f"Renode-run download listed in {renode_run_config}, but the target directory {renode_path} was not found. Looking in $PATH...")

    renode_path = which("renode")

    if renode_path is None:
        if try_to_download:
            print('Renode not found. Downloading...')
            renode_target_dir = artifacts_dir / RENODE_TARGET_DIRNAME
            renode_run_config_path = artifacts_dir / RENODE_RUN_CONFIG_FILENAME
            download_renode(renode_target_dir, renode_run_config_path)
            return get_renode(artifacts_dir, False)
        else:
            print("Renode not found, could not download. Please run `renode-run download` manually or visit https://builds.renode.io")

    else:
        print(f"Renode found in $PATH: {renode_path}. If you want to use the latest Renode version, consider running 'renode-run download'")

    return renode_path
