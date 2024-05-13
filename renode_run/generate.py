# Copyright (c) 2024 Antmicro

import os
import urllib.request

from pathlib import Path
from dts2repl import dts2repl

from renode_run.defaults import DASHBOARD_LINK
from renode_run.utils import fetch_renode_version, fetch_zephyr_version


template_script = '''
using sysbus
mach create "{platform}"

machine LoadPlatformDescription @{repl}

python
"""
from Antmicro.Renode.Peripherals.UART import IUART
uarts = self.Machine.GetPeripheralsOfType[IUART]()

shown = dict()

def bind_function(uartName):
    def func(char):
        if uartName not in shown:
            monitor.Parse("showAnalyzer "+uartName)
        shown[uartName] = True
    return func

for uart in uarts:
    uartName = clr.Reference[str]()
    self.Machine.TryGetAnyName(uart, uartName)
    onReceived = bind_function(uartName.Value)
    uart.CharReceived += onReceived
"""

macro reset
"""
    sysbus LoadELF @{binary}
"""

runMacro $reset
echo "Use 'start' to run the demo"
'''


def generate_script(binary_name, platform, generate_repl):
    zephyr_version = fetch_zephyr_version()
    binary = binary_name
    if not os.path.exists(binary):
        print(f"Binary name `{binary}` is not a local file, trying remote.")
        if binary[0:4] != 'http':
            binary = f"{DASHBOARD_LINK}/zephyr/{zephyr_version}/{platform}/{binary}/{binary}.elf"
    else:
        # We don't need to fetch the binary, but we still need to fetch additional resources like repl or dts.
        # Let's use the hello_world sample, as it's the most vanilla one.
        binary_name = 'hello_world'

    if generate_repl:
        urllib.request.urlretrieve(f"{DASHBOARD_LINK}/zephyr/{zephyr_version}/{platform}/{binary_name}/{binary_name}.dts", platform + ".dts")
        with open(platform + ".repl", 'w') as repl_file:
            repl_file.write(dts2repl.generate(Path.cwd() / f"{platform}.dts"))
        repl = platform + ".repl"
    else:
        renode_version = fetch_renode_version()
        repl = f"{DASHBOARD_LINK}/zephyr_sim/{zephyr_version}/{renode_version}/{platform}/{binary_name}/{binary_name}.repl"

    script = template_script.format(platform=platform, repl=repl, binary=binary)

    return script
