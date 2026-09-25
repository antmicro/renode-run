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
import sys
import time

from abc import ABC, abstractmethod
from pathlib import Path
from collections.abc import Callable
from typing import Tuple

from renode_run.defaults import DASHBOARD_LINK
from renode_run.url_resources import download_to_file, fetch_text, URLResourceError

DOWNLOAD_PROGRESS_DELAY = 1


class PortableArchive(ABC):
    @abstractmethod
    def __init__(self, ar_path: Path) -> None:
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def get_root_dir_name(self) -> str:
        pass

    @abstractmethod
    def extract_members(self, final_path: Path):
        pass

class PortablePackage(ABC):
    @abstractmethod
    def __init__(self, package_info: str | Path) -> None:
        pass

    @abstractmethod
    def __enter__(self) -> PortableArchive:
       pass

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        pass

    @staticmethod
    def _report_progress() -> Callable[[int, int, int], None]:
        start_time = previous_time = time.time()

        def aux(count: int, size: int, filesize: int) -> None:
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
    def get_package_name(version: str) -> str:
        pass

    @staticmethod
    def build_package_path(target_dir_path: Path, version: str, direct: bool) -> Path:
        if direct:
            # When the --direct argument is passed, we would like to
            # extract contents of the archive directly to the path given by the user.
            return target_dir_path
        else:
            return target_dir_path / f"renode-{version}"

    @classmethod
    def path_contains_renode(cls, path: Path) -> bool:
        return Path.exists(path / cls.get_artifact_name())

    def download_package(self, version: str) -> Path:
        package_name = self.get_package_name(version)

        try:
            (renode_package, _) = download_to_file(f"https://builds.renode.io/{package_name}", reporthook=self._report_progress())
        except URLResourceError as e:
            sys.exit(f"Renode could not be downloaded. Check if you have working internet connection and provided Renode version is correct (if specified).\n{e}")

        return renode_package

    @staticmethod
    @abstractmethod
    def get_artifact_name() -> str:
        pass

    class UnableToFindVersion(Exception):
        pass

    def extract(self, target_dir_path: Path, direct: bool, force: bool, version_override: str | None = None) -> Tuple[Path, str]:
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
                sys.exit(f"Target directory '{target_dir_path}' is not empty!\n"
                          "Please clear the directory or use a '--force' option.")

            ar.extract_members(final_path)
            return (final_path, renode_version)


@functools.lru_cache
def fetch_zephyr_version() -> str:
    try:
        return fetch_text(f"{DASHBOARD_LINK}/zephyr_sim/latest").strip()
    except URLResourceError as e:
        sys.exit(f"Failed to fetch Zephyr Dashboard metadata. Please verify your connection and try again.\n{e}")


@functools.lru_cache
def fetch_renode_version() -> str:
    try:
        return fetch_text(f"{DASHBOARD_LINK}/zephyr_sim/{fetch_zephyr_version()}/latest").strip()
    except URLResourceError as e:
        sys.exit(f"Failed to fetch Zephyr Dashboard metadata. Please verify your connection and try again.\n{e}")
