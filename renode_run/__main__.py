#!/usr/bin/env python3

import os
import sys
from pathlib import Path

dashboard_link = "https://zephyr-dashboard.renode.io"
renode_config = Path.home() / ".config" / "renode"
renode_target_dir = renode_config / "renode-run.download"
renode_run_config = renode_config / "renode-run.path"


def parse_args():
    import argparse
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title="commands", dest="command")
    dl_subparser = subparsers.add_parser("download", help="Download Renode portable (Linux only!)")
    dl_subparser.add_argument('-p', '--path', dest='path', default=str(renode_target_dir), help="Path for Renode download")

    demo_subparser = subparsers.add_parser("demo", help="Run a demo from precompiled binaries")
    demo_subparser.add_argument('-b', '--binary', dest='binary', default="shell_module", help="Binary name, either local of remote")
    demo_subparser.add_argument('-g', '--generate-repl', dest='generate_repl', action='store_true', help="Whether to generate the repl from dts")
    demo_subparser.add_argument('platform', help="Platform name")
    args = parser.parse_args()
    return args


def report_progress(count, size, filesize):
    print(f"Downloaded {count * size * 1.0 / (1024 * 1024.0):.2f}MB / {filesize / (1024 * 1024.0):.2f}MB...", end='\r')


def download_renode(path):
    if not sys.platform.startswith('linux'):
        raise Exception("Renode can only be automatically downloaded on Linux. On other OSes please visit https://builds.renode.io and install the latest package for your system.")

    from urllib import request
    import tarfile

    print('Downloading Renode...')
    renode_package, _ = request.urlretrieve("https://builds.renode.io/renode-latest.linux-portable.tar.gz", reporthook=report_progress)
    print()
    print("Download finished!")

    target_dir = Path(path)
    os.makedirs(target_dir, exist_ok=True)
    try:
        with tarfile.open(renode_package) as tar:
            renode_version = tar.members[0].name
            final_path = target_dir / renode_version
            if Path.exists(final_path):
                print(f"Renode {renode_version} is already available in {target_dir}, keeping the previous version")
                return
            tar.extractall(target_dir)
            print(f"Renode stored in {final_path}")

        with open(renode_run_config, mode="w") as config:
            config.write(str(final_path))
    finally:
        os.remove(renode_package)


def get_renode(try_to_download=True):
    # First, we try ~/.config/renode, then we look in $PATH
    renode_path = None
    if Path.exists(renode_run_config):
        with open(renode_run_config, mode="r") as config:
            renode_path = Path(config.read()) / "renode"
            if Path.exists(renode_path):
                print(f"Renode found in {renode_path}")
                return str(renode_path)  # returning str to match the result of `which`
            else:
                print(f"Renode-run download listed in {renode_run_config}, but the target directory {renode_path} was not found. Looking in $PATH...")

    from shutil import which
    renode_path = which("renode")

    if renode_path is None:
        if try_to_download:
            print('Renode not found. Downloading...')
            download_renode(renode_target_dir)
            return get_renode(False)
        else:
            print("Renode not found, could not download. Please run `renode-run download` manually or visit https://builds.renode.io")

    else:
        print(f"Renode found in $PATH: {renode_path}. If you want to use the latest Renode version, consider running 'renode-run download'")

    return renode_path


def generate_script(binary, platform, generate_repl):

    if not os.path.exists(binary):
        print(f"Binary name `{binary}` is not a local file, trying remote.")
        if binary[0:4] != 'http':
            binary = f"{dashboard_link}/{platform}-zephyr-{binary}.elf"

    repl = f"{dashboard_link}/{platform}.repl"
    if generate_repl:
        import urllib.request
        urllib.request.urlretrieve(f"{dashboard_link}/{platform}.dts", platform + ".dts")
        with open(platform + ".repl", 'w') as repl_file:
            from argparse import Namespace
            fake_args = Namespace(filename=f"{os.getcwd()}/{platform}.dts")
            import dts2repl
            repl_file.write(dts2repl.main(fake_args))
        repl = platform + ".repl"

    script = f'''

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
echo "Use 'start' to run the demo"'''
    return script


def main():
    import json
    import requests

    url = requests.get(f"{dashboard_link}/results-shell_module_all.json", "results.json")
    results = json.loads(url.text)

    boards = [r["board_name"] for r in results]

    import tempfile
    import subprocess

    if len(sys.argv) == 1:
        renode_path = get_renode()
        if renode_path is None:
            sys.exit(1)
        subprocess.run(renode_path)
        return

    args = parse_args()
    if args.command == 'download':
        download_renode(args.path)

    else:
        renode_path = get_renode()
        if renode_path is None:
            sys.exit(1)
        if args.platform not in boards:
            print(f'Platform "{args.platform}" not in Zephyr platforms list on server.')
            print(f'Available platforms:{chr(10)}{chr(10).join(boards)}')
            print('Choose one of the platforms listed above and try again.')
            sys.exit(1)

        script = generate_script(args.binary, args.platform, args.generate_repl)

        with tempfile.NamedTemporaryFile() as temp:
            temp.write(script.encode("utf-8"))
            temp.flush()
            subprocess.run(f"{renode_path} {temp.name}".split())


if __name__ == "__main__":
    main()
