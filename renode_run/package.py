#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import sys

if sys.platform.startswith('linux'):
    from renode_run.linux_package import RENODE_EXECUTABLE, RENODE_TEST
    from renode_run.linux_package import LinuxPackage

    def package_type():
        return LinuxPackage

elif sys.platform.startswith('win'):
    from renode_run.windows_package import RENODE_EXECUTABLE, RENODE_TEST
    from renode_run.windows_package import WindowsPackage

    def package_type():
        return WindowsPackage

elif sys.platform.startswith('darwin'):
    # MacOS executable names are compatible with the Linux ones.
    from renode_run.linux_package import RENODE_EXECUTABLE, RENODE_TEST

    def package_type():
        raise Exception("Package management is not supported on MacOS")

else:
    raise Exception("Unsupported platform, renode-run is supported only on Linux, Windows and MacOS")
