#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import sys
from typing import NoReturn

if sys.platform == 'linux':
    from renode_run.linux_package import RENODE_EXECUTABLE, RENODE_TEST
    from renode_run.linux_package import LinuxPackage

    def package_type() -> type[LinuxPackage]:
        return LinuxPackage

elif sys.platform == 'win32':
    from renode_run.windows_package import RENODE_EXECUTABLE, RENODE_TEST
    from renode_run.windows_package import WindowsPackage

    def package_type() -> type[WindowsPackage]:
        return WindowsPackage

elif sys.platform == 'darwin':
    # MacOS executable names are compatible with the Linux ones.
    from renode_run.linux_package import RENODE_EXECUTABLE, RENODE_TEST

    def package_type() -> NoReturn:
        raise Exception("Package management is not supported on MacOS")

else:
    raise Exception("Unsupported platform, renode-run is supported only on Linux, Windows and MacOS")
