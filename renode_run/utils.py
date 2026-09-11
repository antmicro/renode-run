#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import datetime
import functools
import re
import os
import requests
import sys
import time

from abc import ABC, abstractmethod
from pathlib import Path
from urllib import request, error

from renode_run.defaults import DASHBOARD_LINK

DOWNLOAD_PROGRESS_DELAY = 1


class PortableArchive(ABC):
    @abstractmethod
    def __init__(self, ar_path):
        pass
    
    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def get_root_dir_name(self):
        pass
    
    @abstractmethod
    def extract_members(self, final_path):
        pass

class PortablePackage(ABC):
    @abstractmethod
    def __init__(self, version):
        pass

    @abstractmethod
    def __enter__(self):
       pass

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        pass

    @staticmethod
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
            total_seconds = time_elapsed.total_seconds()
            mins, secs = divmod(total_seconds, 60)
            hours, mins = divmod(mins, 60)

            if hours:
                elapsed_time_str = f"{int(hours):02}:{int(mins):02}:{secs:05.2f}"
            else:
                elapsed_time_str = f"{int(mins):02}:{secs:05.2f}"

            print(f"Downloaded {current:.2f}MB / {total:.2f}MB (time elapsed: {elapsed_time_str})...", end='\r')
        return aux

    @staticmethod
    @abstractmethod
    def get_package_name(version):
        pass

    @staticmethod
    def build_package_path(target_dir_path, version, direct):
        if direct:
            # When the --direct argument is passed, we would like to
            # extract contents of the archive directly to the path given by the user.
            return target_dir_path
        else:
            return target_dir_path / f"renode-{version}"

    @classmethod
    def path_contains_renode(cls, path):
        return Path.exists(path / cls.get_artifact_name())

    def download_package(self, version):
        package_name = self.get_package_name(version)

        try:
            renode_package, _ = request.urlretrieve(f"https://builds.renode.io/{package_name}", reporthook=self._report_progress())
        except error.HTTPError:
            print("Renode could not be downloaded. Check if you have working internet connection and provided Renode version is correct (if specified)")
            sys.exit(1)

        return renode_package

    @staticmethod
    @abstractmethod
    def get_artifact_name():
        pass

    class UnableToFindVersion(Exception):
        pass

    def extract(self, target_dir_path, direct, force, version_override=None):
        with self as ar:
            name = ar.get_root_dir_name()
            renode_version = version_override

            if renode_version is None:
                # This regex searches "<semver>" and "<semver>+<date>git<commit>" version formats
                # - semver -- Semantic version (e.g. 0.0.0)
                # - data -- format YYYYMMDD
                # - commit -- consists of 8-9 first characters of commit SHA
                matched = re.search(r"renode[-_](?P<version>[0-9]+\.[0-9]+\.[0-9]+(?:\+[0-9]{8}git[0-9a-fA-F]{8,9})?)", name)
                if not matched:
                    raise self.UnableToFindVersion(f"Can't find proper renode version string in {name}")

                renode_version = matched.group("version")

            final_path = self.build_package_path(target_dir_path, renode_version, direct)
            is_dir_dirty = final_path.exists() and len(os.listdir(final_path)) != 0
            if is_dir_dirty and not force:
                print(f"Target directory '{target_dir_path}' is not empty!", file=sys.stderr)
                print("Please clear the directory or use a '--force' option.", file=sys.stderr)
                exit(1)

            ar.extract_members(final_path)
            return (final_path, renode_version)


@functools.lru_cache
def fetch_zephyr_version():
    version = requests.get(f"{DASHBOARD_LINK}/zephyr_sim/latest")
    return version.text.strip()


@functools.lru_cache
def fetch_renode_version():
    version = requests.get(f"{DASHBOARD_LINK}/zephyr_sim/{fetch_zephyr_version()}/latest")
    return version.text.strip()
