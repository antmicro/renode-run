#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import datetime
import functools
import re
import requests
import sys
import time

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from urllib import request, error

from renode_run.defaults import DASHBOARD_LINK, DEFAULT_RENODE_ARTIFACTS_DIR

DOWNLOAD_PROGRESS_DELAY = 1


class RenodeVariant(str, Enum):
    DOTNET_PORTABLE = "dotnet-portable"
    MONO_PORTABLE = "mono-portable"

    @staticmethod
    def default():
        return RenodeVariant.DOTNET_PORTABLE


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
    def __init__(self, renode_variant, version):
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
            print(f"Downloaded {current:.2f}MB / {total:.2f}MB (time elapsed: {time_elapsed})...", end='\r')
        return aux

    @staticmethod
    @abstractmethod
    def get_package_name(renode_variant, version):
        pass

    @staticmethod
    def build_package_path(target_dir_path, renode_variant, version, direct):
        if direct:
            # When the --direct argument is passed, we would like to
            # extract contents of the archive directly to the path given by the user.
            return target_dir_path
        else:
            return target_dir_path / f"{renode_variant.value}/renode-{version}"

    @classmethod
    def get_package_if_exists(cls, target_dir_path, renode_variant, version, direct):
        package_path = cls.build_package_path(target_dir_path, renode_variant, version, direct)
        if Path.exists(package_path / cls.get_artifact_name()):
            return package_path
        else:
            return None

    def download_package(self, renode_variant, version):
        package_name = self.get_package_name(renode_variant, version)

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

    def extract(self, target_dir_path, direct):
        with self as ar:
            name = ar.get_root_dir_name()

            # This regex searches for "<semver>+<date>git<commit>".
            # - semver -- Semantic version (e.g. 0.0.0)
            # - data -- format YYYYMMDD
            # - commit -- consists of 8-9 first characters of commit SHA
            matched = re.search(r"[0-9]+\.[0-9]+\.[0-9]+\+[0-9]{8}git[0-9a-fA-F]{8,9}", name)
            if not matched:
                raise Exception(f"Can't find proper renode version string in {name}")

            renode_version = matched.group(0)

            final_path = self.build_package_path(target_dir_path, self.renode_variant, renode_version, direct)
            if Path.exists(final_path / self.get_artifact_name()):
                return (final_path, False)

            ar.extract_members(final_path)
            return (final_path, True)


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
