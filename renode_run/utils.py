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
from typing import NamedTuple
from pathlib import Path
from urllib import request, error
from shutil import rmtree

from renode_run.defaults import DASHBOARD_LINK, DEFAULT_RENODE_ARTIFACTS_DIR

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
            print(f"Downloaded {current:.2f}MB / {total:.2f}MB (time elapsed: {time_elapsed})...", end='\r')
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

    def extract(self, target_dir_path, direct, version_override=None):
        with self as ar:
            name = ar.get_root_dir_name()
            renode_version = version_override

            if renode_version is None:
                # This regex searches for "<semver>+<date>git<commit>".
                # - semver -- Semantic version (e.g. 0.0.0)
                # - data -- format YYYYMMDD
                # - commit -- consists of 8-9 first characters of commit SHA
                matched = re.search(r"[0-9]+\.[0-9]+\.[0-9]+\+[0-9]{8}git[0-9a-fA-F]{8,9}", name)
                if not matched:
                    raise self.UnableToFindVersion(f"Can't find proper renode version string in {name}")

                renode_version = matched.group(0)

            final_path = self.build_package_path(target_dir_path, renode_version, direct)

            ar.extract_members(final_path)
            return (final_path, renode_version)


def choose_artifacts_path(lower_priority_path, higher_priority_path):
    if higher_priority_path is not None:
        return higher_priority_path
    if lower_priority_path is not None:
        return lower_priority_path
    return DEFAULT_RENODE_ARTIFACTS_DIR


PackageInfo = NamedTuple('PackageInfo', [('package_path', Path), ('version', str), ('extra_tags', list[str])])

class ConfigFile:
    # Different major versions are not compatible.
    # Minor versions are backwards-compatible.
    CONFIG_VERSION = "2.1"

    RENODE_RUN_CONFIG_VERSION = 'version'
    RENODE_INSTALLS = 'installations'
    RENODE_INSTALL_VERSION = 'version'
    RENODE_INSTALL_VARIANT = 'variant'
    LATEST_DATE = 'latest_date'
    LATEST_VERSION = 'latest_version'
    DEFAULT_VERSION = 'default'
    DOTNET_PORTABLE = "dotnet-portable"

    @classmethod
    def expand_version(cls, version_string):
        (major, minor) = version_string.split(".")
        return (int(major), int(minor))

    @classmethod
    def _update_version(cls, config):
        config[cls.RENODE_RUN_CONFIG_VERSION] = cls.CONFIG_VERSION

    def __init__(self, config_path, portable_package):
        self.config_path = config_path
        self.portable_package = portable_package
        self.config = None

        should_save = False

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
                print(f"Renode-run config version ({config_version}) is not compatible with this renode-run ({self.CONFIG_VERSION}).")
                print(f"Please clear the config file located at '{self.config_path}' or change renode-run version.")
                exit(1)

            package_defaults = config[self.DEFAULT_VERSION]

            # Config version 2.1 drops Mono support; from this point there is one default version.
            if isinstance(package_defaults, dict):
                has_mono_default = any("mono" in default_version for default_version in package_defaults)
                if has_mono_default:
                    print("Renode-run has removed explicit support for Mono Renode packages.", file=sys.stderr)
                    print("Mono/Dotnet default has been replaced by global default initialized by current Dotnet default.", file=sys.stderr)

                dotnet_default = package_defaults.get(self.DOTNET_PORTABLE, None)
                config[self.DEFAULT_VERSION] = dotnet_default
                should_save = True

            self.config = config
        else:
            self.config = {}

        self._update_version(self.config)

        should_save |= self._filter_existing()

        if should_save:
            self.save_config()

    def save_config(self):
        if not self.config_path.parent.exists():
            os.makedirs(self.config_path.parent)

        with open(self.config_path, mode="w") as f:
            json.dump(self.config, f)

    def _check_default(self):
        default_path = self.get_default_path()
        if default_path is None:
            return

        if default_path not in self.get_renode_installs():
            self.config[self.DEFAULT_VERSION] = None

    def _filter_existing(self):
        def check_package(package):
            (path_str, _) = package
            return self.portable_package.path_contains_renode(Path(path_str))

        package_list = self.get_renode_installs().items()
        existing_packages = dict(filter(check_package, package_list))

        config_updated = len(package_list) != len(existing_packages)
        if config_updated:
            self.config[self.RENODE_INSTALLS] = existing_packages
            self._check_default()

        return config_updated

    def get_latest_data(self):
        latest_date = self.config.get(self.LATEST_DATE)
        latest_version = self.config.get(self.LATEST_VERSION)
        if latest_date is not None and latest_version is not None:
            if datetime.date.fromisoformat(latest_date) == datetime.date.today():
                return (datetime.date.fromisoformat(latest_date), latest_version)

        return (None, None)

    def get_renode_installs(self):
        return self.config.get(self.RENODE_INSTALLS, {})

    def get_renode_installs_info(self):
        def get_package_info(package):
            (package_path_str, info) = package
            version = info.get(self.RENODE_INSTALL_VERSION, None)

            tags = []

            # In previous renode-run releases 'variant' differentiated between Dotnet and Mono packages.
            if variant := info.get(self.RENODE_INSTALL_VARIANT, None):
                # DOTNET_PORTABLE was the default variant and now is implicit.
                if variant != self.DOTNET_PORTABLE:
                    tags.append(variant)

            return PackageInfo(Path(package_path_str), version, tags)

        return map(get_package_info, self.get_renode_installs().items())

    def get_default_path(self):
        return self.config.get(self.DEFAULT_VERSION, None)
    
    def update_default(self, path):
        self.config[self.DEFAULT_VERSION] = str(path)

    def get_package_version(self, path):
        if package_info := self.get_renode_installs().get(str(path), None):
            return package_info.get(self.RENODE_INSTALL_VERSION)

    def update_download(self, version, path, is_latest):
        self.config.setdefault(self.RENODE_INSTALLS, {})[str(path)] = {
            self.RENODE_INSTALL_VERSION: version,
        }
        self.update_default(path)
        if is_latest:
            self.config[self.LATEST_DATE] = datetime.date.today().isoformat()
            self.config[self.LATEST_VERSION] = version

    def remove_installation(self, path):
        if not self.portable_package.path_contains_renode(path):
            return
        
        rmtree(path)
        self.get_renode_installs().pop(str(path))
        self._check_default()
        print(f"Removed package from: {path}")


@functools.lru_cache
def fetch_zephyr_version():
    version = requests.get(f"{DASHBOARD_LINK}/zephyr_sim/latest")
    return version.text.strip()


@functools.lru_cache
def fetch_renode_version():
    version = requests.get(f"{DASHBOARD_LINK}/zephyr_sim/{fetch_zephyr_version()}/latest")
    return version.text.strip()
