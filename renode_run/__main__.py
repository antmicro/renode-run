#!/usr/bin/env python3

import os
import sys
import venv
from pathlib import Path
from pyfzf.pyfzf import FzfPrompt

dashboard_link = "https://zephyr-dashboard.renode.io"
default_renode_artifacts_dir = Path.home() / ".config" / "renode"

renode_target_dirname = "renode-run.download"
renode_run_config_filename = "renode-run.path"
renode_test_venv_dirname = "renode-run.venv"

download_progress_delay = 1


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


def parse_args():
    import argparse
    from types import SimpleNamespace
    command_parser = argparse.ArgumentParser()
    subparsers = command_parser.add_subparsers(title="commands", dest="command")

    dl_subparser = subparsers.add_parser("download", help="download Renode portable (Linux only!)")
    dl_subparser.add_argument('-p', '--path', dest='path', default=None, help="path for Renode download")
    dl_subparser.add_argument('-d', '--direct', dest='direct', action='store_true', help="do not create additional directories with Renode version")
    dl_subparser.add_argument('version', default='latest', nargs='?', help='specifies Renode version to download')

    exec_subparser = subparsers.add_parser("exec", help="execute Renode with arguments")
    exec_subparser.add_argument('renode_args', default=[], nargs=argparse.REMAINDER)

    test_subparser = subparsers.add_parser("test", help="execute renode-test with arguments")
    test_subparser.add_argument('--venv', dest='venv_path', help='path for virtualenv used by renode-test')
    test_subparser.add_argument('renode_args', default=[], nargs=argparse.REMAINDER)

    demo_subparser = subparsers.add_parser("demo", help="run a demo from precompiled binaries")
    demo_subparser.add_argument('-b', '--board', dest='board', help=f"board name, as listed on {dashboard_link}")
    demo_subparser.add_argument('-g', '--generate-repl', dest='generate_repl', action='store_true', help="whether to generate the repl from dts")
    demo_subparser.add_argument('binary', help="binary name, either local or remote")
    demo_subparser.add_argument('renode_arguments', default=[], nargs=argparse.REMAINDER, help="additional Renode arguments")

    registered_commands = set(subparsers.choices.keys())

    main_parser = argparse.ArgumentParser()
    main_parser.add_argument('-a', '--artifacts', dest='artifacts_path', default=str(default_renode_artifacts_dir), help='path for renode-run artifacts (e.g. config, Renode installations)')
    main_parser.add_argument('command', default=[], choices=registered_commands, nargs=argparse.REMAINDER)

    main_args = main_parser.parse_args()
    args = {arg: getattr(main_args, arg) for arg in vars(main_args) if arg != 'command'}

    if len(main_args.command) > 0 and main_args.command[0] in registered_commands:
        command_args = command_parser.parse_args(main_args.command)
        args.update({arg: getattr(command_args, arg) for arg in vars(command_args)})
    else:
        args.update({'command': None, 'renode_args': main_args.command})
    return SimpleNamespace(**args)


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

    target_dir = Path(target_dir_path)
    os.makedirs(target_dir, exist_ok=True)
    try:
        with tarfile.open(renode_package) as tar:
            if direct:
                # When the --direct argument is passed, we would like to
                # extract contents of the archive directly to the path given by the user,
                # and not into a new directory.
                # Therefore we iterate over all files (paths) in the archive,
                # and strip them from the first part, which is the renode_<version>
                # directory.
                final_path = target_dir
                renode_bin_path = final_path / 'renode'
                if Path.exists(renode_bin_path):
                    print(f"Renode is already present in {target_dir}")
                    return
                members = tar.getmembers()
                for member in members:
                    old_member_path = Path(member.path).parts[1:]
                    member.path = Path(*old_member_path)
                tar.extractall(target_dir, members=members)
            else:
                renode_version = tar.members[0].name
                final_path = target_dir / renode_version
                if Path.exists(final_path):
                    print(f"Renode {renode_version} is already available in {target_dir}, keeping the previous version")
                    return
                tar.extractall(target_dir)
            print(f"Renode stored in {final_path}")

        with open(config_path, mode="w") as config:
            config.write(str(final_path))
    finally:
        os.remove(renode_package)


def get_renode(artifacts_dir, try_to_download=True):
    # First, we try <artifacts_dir>, then we look in $PATH
    renode_path = None
    renode_run_config = Path(artifacts_dir) / renode_run_config_filename
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
            renode_target_dir = Path(artifacts_dir) / renode_target_dirname
            renode_run_config_path = Path(artifacts_dir) / renode_run_config_filename
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


def download_command(args):
    renode_run_config_path = Path(args.artifacts_path) / renode_run_config_filename
    target_dir_path = args.path
    if target_dir_path is None:
        target_dir_path = Path(args.artifacts_path) / renode_target_dirname
    download_renode(target_dir_path, renode_run_config_path, args.version, args.direct)

def get_fuzzy_or_none(alternatives: 'list[str]', query: 'str|None' = False, do_prints: bool = True) -> 'str|None':
    FZF_STYLE = "--height=80% --layout=reverse --info=inline --border --margin=1 --padding=1"
    FZF_DEFAULTS = "-i --cycle"

    opts = ' '.join([FZF_STYLE, FZF_DEFAULTS])
    if query:
        opts += f' --query="{query}" '
    try:
        fzf = FzfPrompt()
        sel = fzf.prompt(alternatives, opts)[0]
        if do_prints:
            print(f'Chosen: {sel}')
        return sel
    except IndexError: # this can fire when we hit Ctrl-C when matching
        if do_prints:
            print('Match canceled, exiting.')
        return None
    except Exception as e:
        if do_prints:
            print(f'Cannot use fuzzy matching, falling back to strict mode. Reason: "{e}"')
        return None

def demo_command(args):
    import json
    import requests
    import tempfile
    import subprocess

    try:
        url = requests.get(f"{dashboard_link}/results-shell_module_all.json", "results.json")
    except requests.exceptions.RequestException:
        print(f'Failed to download the board list. Check your internet connection.')
        sys.exit(1)

    if url.status_code != 200:
        print(f'The server returned {url.status_code}. Cannot download board list.')
        sys.exit(1)

    results = json.loads(url.text)
    boards = [r["board_name"] for r in results]

    if args.board is None:
        print('No board specified, select one from the list.')
        if (board := get_fuzzy_or_none(boards)):
            args.board = board
        else:
            print(f'Available platforms:{chr(10)}{chr(10).join(boards)}')
            print('Choose one of the platforms listed above and try again.')
            sys.exit(1)

    if args.board not in boards:
        print(f'Platform "{args.board}" not in Zephyr platforms list on server.')

        print(f'Falling back to fuzzy selection.')
        if (board := get_fuzzy_or_none(boards, args.board)):
            args.board = board
        else:
            print(f'Available platforms:{chr(10)}{chr(10).join(boards)}')
            print('Choose one of the platforms listed above and try again.')
            sys.exit(1)

    renode_path = get_renode(args.artifacts_path)

    if renode_path is None:
        sys.exit(1)

    script = generate_script(args.binary, args.board, args.generate_repl)

    with tempfile.NamedTemporaryFile() as temp:
        temp.write(script.encode("utf-8"))
        temp.flush()
        ret = subprocess.run([renode_path, temp.name] + args.renode_arguments)
    sys.exit(ret.returncode)


def exec_command(args):
    renode = get_renode(args.artifacts_path)
    if renode is None:
        sys.exit(1)

    import subprocess

    renode_args = list(arg for arg in getattr(args, 'renode_args', []) if arg != '--')
    sys.stdout.flush()
    ret = subprocess.run([renode] + renode_args)
    sys.exit(ret.returncode)


def test_command(args):
    renode = get_renode(args.artifacts_path)
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

    if args.venv_path is not None:
        venv_path = Path(args.venv_path)
    else:
        venv_path = Path(args.artifacts_path) / renode_test_venv_dirname

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

    renode_args = list(arg for arg in getattr(args, 'renode_args', []) if arg != '--')
    ret = subprocess.run([renode_test] + renode_args, env=env)
    sys.exit(ret.returncode)


def main():
    args = parse_args()
    ({
        'download': download_command,
        'demo': demo_command,
        'exec': exec_command,
        'test': test_command,
        None: exec_command,
    })[args.command](args)

if __name__ == "__main__":
    main()
