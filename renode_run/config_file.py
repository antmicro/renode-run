#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import datetime
import json
import os
import sys

from typing import NamedTuple
from pathlib import Path
from shutil import rmtree

from renode_run.defaults import DEFAULT_RENODE_ARTIFACTS_DIR


PackageInfo = NamedTuple('PackageInfo', [('package_path', Path), ('version', str), ('extra_tags', list[str])])

def choose_artifacts_path(lower_priority_path, higher_priority_path):
    if higher_priority_path is not None:
        return higher_priority_path
    if lower_priority_path is not None:
        return lower_priority_path
    return DEFAULT_RENODE_ARTIFACTS_DIR


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
            try:
                config = json.loads(config_path.read_text())
            except json.JSONDecodeError:
                print(f"Configuration file located at '{config_path}' is malformed!", file=sys.stderr)
                print(f"Please ensure correct formatting or delete the file.", file=sys.stderr)
                exit(1)

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
        
        try:
            rmtree(path)
        except PermissionError:
            print("Administrative privilages are necessary to delete this installation.")
            print("Please run the application with admin privilages and try again.")
            exit(1)

        self.get_renode_installs().pop(str(path))
        self._check_default()
        print(f"Removed package from: {path}")
