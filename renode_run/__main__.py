#!/usr/bin/env python3
#
# Copyright (c) 2022-2023 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import os
import sys
import venv
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

import typer
from typing_extensions import Annotated
from typing import Optional

dashboard_link = "https://zephyr-dashboard.renode.io"
default_renode_artifacts_dir = Path.home() / ".config" / "renode"

renode_target_dirname = "renode-run.download"
renode_run_config_filename = "renode-run.path"
renode_test_venv_dirname = "renode-run.venv"

download_progress_delay = 1

renode_args = []
global_artifacts_path = None

artifacts_path_annotation = Annotated[Path, typer.Option("-a", "--artifacts_path", help='path for renode-run artifacts (e.g. config, Renode installations)')]

app = typer.Typer()

class EnvBuilderWithRequirements(venv.EnvBuilder):
    def __init__(self, *args, **kwargs):
        self.requirements_path = kwargs.pop('requirements_path', None)
        kwargs['with_pip'] = True
        super().__init__(*args, **kwargs)

    def post_setup(self, context):
        if self.requirements_path is None:
            return

        import subprocess

        args = [context.env_exe, '-m', 'pip', 'install', '-r', self.requirements_path]
        env = os.environ
        env['VIRTUAL_ENV'] = context.env_dir

        try:
            subprocess.check_call(args, env=env)
        except subprocess.CalledProcessError as err:
            print(f'Could not install given requirements: {err}')
            print('Requirements have to be installed manually, or the environment has to be deleted before running command again')
            print(f'Environment path: {context.env_dir}')
            exit(err.errorcode)


def report_progress():
    import time
    import datetime

    start_time = previous_time = time.time()

    def aux(count, size, filesize):
        nonlocal previous_time
        current_time = time.time()

        if previous_time + download_progress_delay > current_time and count != 0 and size * count < filesize:
            return

        previous_time = current_time
        total = filesize / (1024 * 1024.0)
        current = count * size * 1.0 / (1024 * 1024.0)
        current = min(current, total)

        time_elapsed = datetime.timedelta(seconds=current_time - start_time)
        print(f"Downloaded {current:.2f}MB / {total:.2f}MB (time elapsed: {time_elapsed})...", end='\r')
    return aux


def download_renode(target_dir_path, config_path, version='latest', direct=False):
    if not sys.platform.startswith('linux'):
        raise Exception("Renode can only be automatically downloaded on Linux. On other OSes please visit https://builds.renode.io and install the latest package for your system.")

    from urllib import request, error
    import tarfile

    print('Downloading Renode...')

    try:
        renode_package, _ = request.urlretrieve(f"https://builds.renode.io/renode-{version}.linux-portable.tar.gz", reporthook=report_progress())
    except error.URLError:
        print("Renode could not be downloaded. Check if you have working internet connection and provided Renode version is correct (if specified)")
        sys.exit(1)

    print()
    print("Download finished!")

    os.makedirs(target_dir_path, exist_ok=True)
    try:
        with tarfile.open(renode_package) as tar:
            if direct:
                # When the --direct argument is passed, we would like to
                # extract contents of the archive directly to the path given by the user,
                # and not into a new directory.
                # Therefore we iterate over all files (paths) in the archive,
                # and strip them from the first part, which is the renode_<version>
                # directory.
                final_path = target_dir_path
                renode_bin_path = final_path / 'renode'
                if Path.exists(renode_bin_path):
                    print(f"Renode is already present in {target_dir_path}")
                    return
                members = tar.getmembers()
                for member in members:
                    old_member_path = Path(member.path).parts[1:]
                    member.path = Path(*old_member_path)
                tar.extractall(target_dir_path, members=members)
            else:
                renode_version = tar.members[0].name
                final_path = target_dir_path / renode_version
                if Path.exists(final_path):
                    print(f"Renode {renode_version} is already available in {target_dir_path}, keeping the previous version")
                    return
                tar.extractall(target_dir_path)
            print(f"Renode stored in {final_path}")

        with open(config_path, mode="w") as config:
            config.write(str(final_path))
    finally:
        os.remove(renode_package)


def get_renode(artifacts_dir, try_to_download=True):
    # First, we try <artifacts_dir>, then we look in $PATH
    renode_path = None
    renode_run_config = artifacts_dir / renode_run_config_filename
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
            renode_target_dir = artifacts_dir / renode_target_dirname
            renode_run_config_path = artifacts_dir / renode_run_config_filename
            download_renode(renode_target_dir, renode_run_config_path)
            return get_renode(artifacts_dir, False)
        else:
            print("Renode not found, could not download. Please run `renode-run download` manually or visit https://builds.renode.io")

    else:
        print(f"Renode found in $PATH: {renode_path}. If you want to use the latest Renode version, consider running 'renode-run download'")

    return renode_path


def generate_script(binary_name, platform, generate_repl):

    binary = binary_name
    if not os.path.exists(binary):
        print(f"Binary name `{binary}` is not a local file, trying remote.")
        if binary[0:4] != 'http':
            binary = f"{dashboard_link}/{platform}-{binary}/{platform}-zephyr-{binary}.elf"
    else:
        # We don't need to fetch the binary, but we still need to fetch additional resources like repl or dts.
        # Let's use the hello_world sample, as it's the most vanilla one.
        binary_name = 'hello_world'

    repl = f"{dashboard_link}/{platform}-{binary_name}/{platform}-{binary_name}.repl"
    if generate_repl:
        import urllib.request, urllib.error
        try:
            urllib.request.urlretrieve(f"{dashboard_link}/{platform}-{binary_name}/{platform}-{binary_name}.dts", platform + ".dts")
        except urllib.error.HTTPError:
            print(f"Configuration could not be downloaded. Check if you specified the correct demo name.")
            sys.exit(1)
        except urllib.error.URLError:
            print(f"Configuration could not be downloaded. Check if you have working internet connection.")
            sys.exit(1)

        with open(platform + ".repl", 'w') as repl_file:
            from argparse import Namespace
            fake_args = Namespace(filename=f"{os.getcwd()}/{platform}.dts", overlays = "")
            from dts2repl import dts2repl
            repl_file.write(dts2repl.generate(fake_args))
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


def choose_artifacts_path(lower_priority_path, higher_priority_path):
    if higher_priority_path is not None:
        return higher_priority_path
    if lower_priority_path is not None:
        return lower_priority_path
    return default_renode_artifacts_dir


# For backward compatibility artifacts_path option can be passed both before and after specifying the command.
@app.command("download", help="download Renode portable (Linux only!)")
def download_command(artifacts_path: artifacts_path_annotation = None,
                     path: Annotated[Path, typer.Option("-p", "--path", help='path for Renode download')] = None,
                     direct: Annotated[bool, typer.Option("-d/ ", "--direct/ ", help='do not create additional directories with Renode version')] = False,
                     version: Annotated[str, typer.Argument(help='specifies Renode version to download')] = 'latest'):
    # Option passed after the command has higher priority.
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)
    os.makedirs(artifacts_path, exist_ok=True)
    renode_run_config_path = artifacts_path / renode_run_config_filename
    target_dir_path = path
    if target_dir_path is None:
        target_dir_path = artifacts_path / renode_target_dirname
    download_renode(target_dir_path, renode_run_config_path, version, direct)

def get_fuzzy_or_none(alternatives: 'list[str]', query: 'str|None' = None) -> 'str|None':
    try:
        from pyfzf.pyfzf import FzfPrompt
    except ImportError:
        logging.debug('Could not import pyfzf, fuzzy matching disabled')
        return None

    FZF_STYLE = "--height=80% --layout=reverse --info=inline --border --margin=1 --padding=1 --scroll-off=3"
    FZF_DEFAULTS = "-i --cycle"

    opts = ' '.join([FZF_STYLE, FZF_DEFAULTS])
    if query:
        opts += f' --query="{query}" '
    try:
        fzf = FzfPrompt()
        sel = fzf.prompt(alternatives, opts)[0]
        logging.info(f'Chosen: {sel}')
        return sel
    except IndexError: # this can fire when we hit Ctrl-C when matching
        logging.debug('Match canceled, exiting.')
        return None
    except Exception as e:
        logging.debug(f'Cannot use fuzzy matching, falling back to strict mode. Reason: "{e}"')
        return None

# For backward compatibility artifacts_path option can be passed both before and after specifying the command.
@app.command("demo", help="run a demo from precompiled binaries")
def demo_command(board: Annotated[str, typer.Option("-b", "--board", help='board name, as listed on https://zephyr-dashboard.renode.io')],
                 binary: Annotated[str, typer.Argument(help='binary name, either local or remote')],
                 artifacts_path: artifacts_path_annotation = None,
                 generate_repl: Annotated[bool, typer.Option("-g/ ", "--generate-repl/ ", help='whether to generate the repl from dts')] = False):
    # Option passed after the command has higher priority.
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)
    import json
    import requests
    import tempfile
    import subprocess

    try:
        url = requests.get(f"{dashboard_link}/results-shell_module-all.json", "results.json")
    except requests.exceptions.RequestException:
        print(f'Failed to download the board list. Check your internet connection.')
        sys.exit(1)

    if url.status_code != 200:
        print(f'The server returned {url.status_code}. Cannot download board list.')
        sys.exit(1)

    results = json.loads(url.text)
    boards_short_name = [r["board_name"] for r in results]
    boards_name_full = [r["board_full_name"] for r in results]

    names_map = dict()
    for full, short in zip (boards_name_full, boards_short_name):
        names_map[full] = short

    boards = boards_short_name + boards_name_full

    if board is None:
        print('No board specified, select one from the list.')
        if (foundBoard := get_fuzzy_or_none(boards)):
            board = foundBoard
        else:
            print(f'Available platforms:{chr(10)}{chr(10).join(boards)}')
            print('Choose one of the platforms listed above and try again.')
            sys.exit(1)

    if board not in boards:
        print(f'Platform "{board}" not in Zephyr platforms list on server.')

        print(f'Falling back to fuzzy selection.')
        if (foundBoard := get_fuzzy_or_none(boards, board)):
            board = foundBoard
        else:
            print(f'Available platforms:{chr(10)}{chr(10).join(boards)}')
            print('Choose one of the platforms listed above and try again.')
            sys.exit(1)

    # translate long name into short
    if board in names_map:
        board = names_map[board]

    renode_path = get_renode(artifacts_path)

    if renode_path is None:
        sys.exit(1)

    script = generate_script(binary, board, generate_repl)

    with tempfile.NamedTemporaryFile() as temp:
        temp.write(script.encode("utf-8"))
        temp.flush()
        ret = subprocess.run([renode_path, temp.name] + renode_args)
    sys.exit(ret.returncode)


# For backward compatibility artifacts_path option can be passed both before and after specifying the command.
@app.command("exec", help="execute Renode with arguments")
def exec_command(artifacts_path: artifacts_path_annotation = None):
    # Option passed after the command has higher priority.
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)
    renode = get_renode(artifacts_path)
    if renode is None:
        sys.exit(1)

    import subprocess

    sys.stdout.flush()
    ret = subprocess.run([renode] + renode_args)
    sys.exit(ret.returncode)


# For backward compatibility artifacts_path option can be passed both before and after specifying the command.
@app.command("test", help="execute renode-test with arguments")
def test_command(artifacts_path: artifacts_path_annotation = None,
                 venv_path: Annotated[Path, typer.Option("--venv", help='path for virtualenv used by renode-test')] = None):
    # Option passed after the command has higher priority.
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)
    renode = get_renode(artifacts_path)
    if renode is None:
        sys.exit(1)

    renode_dir = Path(renode).parent
    renode_test = renode_dir / 'renode-test'
    if not Path.exists(renode_test):
        print(f'Found Renode binary in {renode_dir}, but renode-test is missing; trying test.sh')
        renode_test = renode_dir / 'test.sh'

        if not Path.exists(renode_test):
            print('test.sh does not exist; corrupted package?')
            sys.exit(1)

        print('test.sh script found, using it instead of renode-test')

    import subprocess

    if venv_path is None:
        venv_path = artifacts_path / renode_test_venv_dirname

    python_bin = venv_path / 'bin'
    python_path = python_bin / 'python'
    if not Path.exists(python_path):
        print(f'Bootstraping new virtual env in {venv_path}')
        requirements_path = renode_dir / 'tests' / 'requirements.txt'
        env_builder = EnvBuilderWithRequirements(clear=True, requirements_path=requirements_path)
        env_builder.create(venv_path)
    else:
        print(f'Found python in {python_bin}')

    env = os.environ
    env['PATH'] = f'{python_bin}:' + (env['PATH'] or '')

    ret = subprocess.run([renode_test] + renode_args, env=env)
    sys.exit(ret.returncode)


# Calling renode-run without arguments runs renode from default path
@app.callback(invoke_without_command=True)
def parse_artifacts_path(ctx: typer.Context, artifacts_path: artifacts_path_annotation = None):
    # For backward compatibility we're allowing to pass artifacts_path before specifying the command
    global global_artifacts_path
    global_artifacts_path = artifacts_path
    if ctx.invoked_subcommand is None:
        exec_command()


def main():
    # Cut off renode arguments after "--" and keep globally
    global renode_args
    if "--" in sys.argv:
        index = sys.argv.index("--")
        renode_args = sys.argv[index+1:]
        sys.argv = sys.argv[:index]
    app()
