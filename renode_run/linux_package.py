#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import tarfile
import os
import weakref

from pathlib import Path

from renode_run.utils import PortableArchive, PortablePackage, RenodeVariant

RENODE_EXECUTABLE = "renode"
RENODE_TEST = "renode-test"


class TarArchive(PortableArchive):
    def __init__(self, ar_path):
        self.ar = tarfile.open(ar_path)

    def close(self):
        self.ar.close()

    def get_root_dir_name(self):
        return self.ar.getnames()[0]
    
    @staticmethod
    def remove_parent_directory(tar_file):
        new_path = Path(tar_file.path).parts[1:]
        if new_path != ():
            tar_file.path = Path(*new_path)
            return True
        return False

    def extract_members(self, final_path):
        members = filter(self.remove_parent_directory, self.ar.getmembers())
        self.ar.extractall(final_path, members=members)


class LinuxPackage(PortablePackage):
    def __init__(self, renode_variant, version):
        self.renove_variant = renode_variant
        self.package_path = self.download_package(renode_variant, version)
        self._finalizer = weakref.finalize(self, os.remove, self.package_path)

    def __enter__(self):
       self.ar = TarArchive(self.package_path)
       return self.ar

    def __exit__(self, exc_type, exc_value, traceback):
        self.ar.close()

    @staticmethod
    def get_package_name(renode_variant, version):
        if renode_variant == RenodeVariant.MONO_PORTABLE:
            return f"renode-{version}.linux-mono-portable.tar.gz"
        elif renode_variant == RenodeVariant.DOTNET_PORTABLE:
            return f"renode-{version}.linux-portable.tar.gz"
        
    @staticmethod
    def get_artifact_name():
        return RENODE_EXECUTABLE
