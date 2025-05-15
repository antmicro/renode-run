# Copyright (c) 2024 Antmicro

import os
import sys
import requests
import urllib.request

from pathlib import Path
from dts2repl import dts2repl

from renode_run.defaults import DASHBOARD_LINK
from renode_run.utils import fetch_renode_version, fetch_zephyr_version


script_prepend = '''# renode-run prepend
$bin=@{binary}
$repl=@{repl}

'''

script_append = '''
echo "Use 'start' to run the demo"
'''


def generate_script(binary_name, platform, generate_repl):
    zephyr_version = fetch_zephyr_version()
    renode_version = fetch_renode_version()
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
        repl = f"{DASHBOARD_LINK}/zephyr_sim/{zephyr_version}/{renode_version}/{platform}/{binary_name}/{binary_name}.repl"

    resc_resp = requests.get(f"{DASHBOARD_LINK}/zephyr_sim/{zephyr_version}/{renode_version}/{platform}/{binary_name}/{binary_name}.resc")
    if resc_resp.status_code == 200:
        dash_script = resc_resp.content.decode("UTF-8")
    else:
        print(f"Error: Unable to retrieve the Renode script for sample '{binary_name}'.", file=sys.stderr)
        exit(1)

    script = f"{script_prepend.format(binary=binary, repl=repl)}{dash_script}{script_append}"

    return script
