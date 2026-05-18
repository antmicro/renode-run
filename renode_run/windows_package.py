#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import os
import weakref
import zipfile

from renode_run.utils import PortableArchive, PortablePackage, RenodeVariant

RENODE_EXECUTABLE = "renode.exe"
RENODE_TEST = "renode-test.bat"


class ZipArchive(PortableArchive):
    def __init__(self, ar_path):
        self.ar = zipfile.ZipFile(ar_path)

    def close(self):
        self.ar.close()

    def get_root_dir_name(self):
        return self.ar.namelist()[0]
    
    @staticmethod
    def remove_parent_directory(tar_file):
        # Path cannot be used as it automatically canonicalizes paths,
        # but Zipfile requires directories to have a slash at the end.
        parts = tar_file.filename.split('/', 1)
        if len(parts) > 1 and parts[1]:
            tar_file.filename = parts[1]
            return True
        return False

    def extract_members(self, final_path):
        members = filter(self.remove_parent_directory, self.ar.infolist())
        self.ar.extractall(final_path, members=members)


class WindowsPackage(PortablePackage):
    def __init__(self, renode_variant, version):
        self.renode_variant = renode_variant
        self.package_path = self.download_package(renode_variant, version)
        self._finalizer = weakref.finalize(self, os.remove, self.package_path)

    def __enter__(self):
       self.ar = ZipArchive(self.package_path)
       return self.ar

    def __exit__(self, exc_type, exc_value, traceback):
        self.ar.close()

    @staticmethod
    def get_package_name(renode_variant, version):
        if renode_variant == RenodeVariant.MONO_PORTABLE:
            raise Exception("Mono packages are not available on Windows")
        elif renode_variant == RenodeVariant.DOTNET_PORTABLE:
            return f"renode-{version}.windows-portable.zip"

    @staticmethod
    def get_artifact_name():
        return RENODE_EXECUTABLE
