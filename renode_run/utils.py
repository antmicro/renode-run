#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import datetime
import functools
import json
import re
import os
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
    def path_contains_renode(cls, path):
        return Path.exists(path / cls.get_artifact_name())

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

            ar.extract_members(final_path)
            return (final_path, renode_version)


def choose_artifacts_path(lower_priority_path, higher_priority_path):
    if higher_priority_path is not None:
        return higher_priority_path
    if lower_priority_path is not None:
        return lower_priority_path
    return DEFAULT_RENODE_ARTIFACTS_DIR


class ConfigFile:
    # Different major versions are not compatible.
    # Minor versions are backwards-compatible.
    CONFIG_VERSION = "2.0"

    RENODE_RUN_CONFIG_VERSION = 'version'
    RENODE_INSTALLS = 'installations'
    RENODE_INSTALL_VERSION = 'version'
    RENODE_INSTALL_VARIANT = 'variant'
    LATEST_DATE = 'latest_date'
    LATEST_VERSION = 'latest_version'
    DEFAULT_VERSION = 'default'

    @classmethod
    def expand_version(cls, version_string):
        (major, minor) = version_string.split(".")
        return (int(major), int(minor))

    @classmethod
    def _update_version(cls, config):
        config[cls.RENODE_RUN_CONFIG_VERSION] = cls.CONFIG_VERSION

    def __init__(self, config_path, portable_package=None):
        self.config_path = config_path
        self.config = None

        if config_path.exists():
            config = json.loads(config_path.read_text())
            config_version = config.get(self.RENODE_RUN_CONFIG_VERSION, None)
            if config_version is None:
                print(f"Renode-run config does not contain version information.")
                print(f"Please clear the config file located at '{self.config_path}' or revert to an older renode-run version.")
                exit(1)

            (major, minor) = self.expand_version(self.CONFIG_VERSION)
            (config_major, config_minor) = self.expand_version(config_version)
            if config_major != major or config_minor > minor:
                print(f"Renode-run config version ({config_major}.{minor}) is not compatible with this renode-run ({self.CONFIG_VERSION}).")
                print(f"Please clear the config file located at '{self.config_path}' or change renode-run version.")
                exit(1)
            else:
                self._update_version(config)
                self.config = config

        should_save = False

        if self.config is None:
            self.config = {}
            self._update_version(self.config)
            should_save = True
            
        if portable_package:
            should_save |= self._filter_existing(portable_package)

        if should_save:
            self.save_config()

    def save_config(self):
        if not self.config_path.parent.exists():
            os.makedirs(self.config_path.parent)

        with open(self.config_path, mode="w") as f:
            json.dump(self.config, f)

    def _filter_defaults(self):
        def default_present(default_entry):
            (variant, path_str) = default_entry
            (_, package_variant) = self.get_package_info(Path(path_str))
            return variant == package_variant

        defaults = self.config.get(self.DEFAULT_VERSION, {})
        self.config[self.DEFAULT_VERSION] = dict(filter(default_present, defaults))

    def _filter_existing(self, portable_package):
        def check_package(package):
            (path_str, _) = package
            return portable_package.path_contains_renode(Path(path_str))

        package_list = self.config.get(self.RENODE_INSTALLS, {}).items()
        existing_packages = dict(filter(check_package, package_list))

        config_updated = len(package_list) != len(existing_packages)
        if config_updated:
            self.config[self.RENODE_INSTALLS] = existing_packages
            self._filter_defaults()

        return config_updated

    def get_latest_data(self):
        latest_date = self.config.get(self.LATEST_DATE)
        latest_version = self.config.get(self.LATEST_VERSION)
        if latest_date is not None and latest_version is not None:
            if datetime.date.fromisoformat(latest_date) == datetime.date.today():
                return (datetime.date.fromisoformat(latest_date), latest_version)

        return (None, None)

    @classmethod
    def extract_info_from_package_data(cls, package_data):
        if package_data is not None:
            version = package_data.get(cls.RENODE_INSTALL_VERSION, None)
            variant = package_data.get(cls.RENODE_INSTALL_VARIANT, None)
            return (version, variant)
        else:
            return (None, None)

    def get_renode_installs(self):
        def expand_install_entry(package):
            (path_str, package_data) = package
            return (path_str, self.extract_info_from_package_data(package_data))

        return map(expand_install_entry, self.config.get(self.RENODE_INSTALLS, {}).items())

    def get_default_path(self, variant):
        default_version_dict = self.config.get(self.DEFAULT_VERSION, {})
        return default_version_dict.get(variant.value, None)

    def get_package_info(self, path):
        package_dict = self.config.get(self.RENODE_INSTALLS, {}).get(str(path), None)
        return self.extract_info_from_package_data(package_dict)
    
    def update_default(self, variant, path):
        self.config.setdefault(self.DEFAULT_VERSION, {})[variant.value] = str(path)

    def update_download(self, variant, version, path, is_latest):
        self.config.setdefault(self.RENODE_INSTALLS, {})[str(path)] = {
            self.RENODE_INSTALL_VERSION: version,
            self.RENODE_INSTALL_VARIANT: variant.value,
        }
        self.update_default(variant, path)
        if is_latest:
            self.config[self.LATEST_DATE] = datetime.date.today().isoformat()
            self.config[self.LATEST_VERSION] = version


@functools.lru_cache
def fetch_zephyr_version():
    version = requests.get(f"{DASHBOARD_LINK}/zephyr_sim/latest")
    return version.text.strip()


@functools.lru_cache
def fetch_renode_version():
    version = requests.get(f"{DASHBOARD_LINK}/zephyr_sim/{fetch_zephyr_version()}/latest")
    return version.text.strip()
