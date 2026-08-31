#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import os
import weakref
import zipfile

from pathlib import Path

from renode_run.utils import PortableArchive, PortablePackage

RENODE_EXECUTABLE = "renode.exe"
RENODE_TEST = "renode-test.bat"


class ZipArchive(PortableArchive):
    def __init__(self, ar_path: Path) -> None:
        self.ar = zipfile.ZipFile(ar_path)

    def close(self) -> None:
        self.ar.close()

    def get_root_dir_name(self) -> str:
        return self.ar.namelist()[0]

    @staticmethod
    def remove_parent_directory(zip_file: zipfile.ZipInfo) -> bool:
        # Path cannot be used as it automatically canonicalizes paths,
        # but Zipfile requires directories to have a slash at the end.
        parts = zip_file.filename.split('/', 1)
        if len(parts) > 1 and parts[1]:
            zip_file.filename = parts[1]
            return True
        return False

    def extract_members(self, final_path: Path) -> None:
        members = filter(self.remove_parent_directory, self.ar.infolist())
        self.ar.extractall(final_path, members=members)


class WindowsPackage(PortablePackage):
    def __init__(self, package_info: str | Path, remove_after_use: bool = False) -> None:
        if isinstance(package_info, str):
            version = package_info
            self.package_path = self.download_package(version)
            self._finalizer = weakref.finalize(self, os.remove, self.package_path)
        else:
            local_package_path = package_info
            self.package_path = local_package_path
            if remove_after_use:
                self._finalizer = weakref.finalize(self, os.remove, self.package_path)

    def __enter__(self) -> PortableArchive:
       self.ar = ZipArchive(self.package_path)
       return self.ar

    def __exit__(self, exc_type, exc_value, traceback):
        self.ar.close()

    @staticmethod
    def get_package_name(version: str) -> str:
        return f"renode-{version}.windows-portable.zip"

    @staticmethod
    def get_artifact_name() -> str:
        return RENODE_EXECUTABLE
