#!/usr/bin/env python3
#
# Copyright (c) 2022-2023 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#
import io
import logging
import os
import pathlib
import sys
import tarfile
import venv
from abc import ABC, abstractmethod

from tqdm import tqdm

import requests
from pathlib import Path

import typer
from typing_extensions import Annotated

logger = logging.getLogger(__name__)

dashboard_link = "https://zephyr-dashboard.renode.io"
default_renode_artifacts_dir = Path.home() / ".config" / "renode"

renode_test_venv_dirname = "renode-run.venv"

download_progress_delay = 1

renode_args = []
global_artifacts_path = None

artifacts_path_annotation = Annotated[Path, typer.Option("-a", "--artifacts_path", help='path for renode-run artifacts (e.g. config, Renode installations)')]

app = typer.Typer()


class Build(ABC):
    def __init__(self, path):
        self.path = pathlib.Path(path)
        if not self.path.exists():
            msg = f"Could not find file: {path}"
            raise FileNotFoundError(msg)

    @classmethod
    @abstractmethod
    def download(cls, target_dir, version=None, progress=None, *args, **kwargs):
        ...

    @classmethod
    def _download_file(cls, address, progress=None):
        r = requests.get(address, stream=progress is not None)
        r.raise_for_status()

        if progress is None:
            return r.content

        total_size = int(r.headers.get('content-length', 0))
        block_size = 1024
        progress_bar = progress(total_size)

        chunks = []

        for data in r.iter_content(block_size):
            progress_bar.update(len(data))
            chunks.append(data)

        return b''.join(chunks)


class ArchBuild(Build):
    @classmethod
    def download(cls, target_dir, version=None, progress=None, *args, **kwargs):
        target_dir = pathlib.Path(target_dir)
        to_download = "renode-latest.pkg.tar.xz" if version is None else f"renode-{version}-1-x86_64.pkg.tar.xz"
        content = cls._download_file(f"https://builds.renode.io/{to_download}", progress)

        pkgversion = cls.__extract_version(io.BytesIO(content))

        target_dir.mkdir(parents=True, exist_ok=True)

        file_name = f"renode_{pkgversion}-x86_64.pkg.tar.xz"
        final_path = target_dir / file_name

        final_path.write_bytes(content)

        logger.info(f"Renode stored in {final_path}.")

        return cls(final_path)

    @classmethod
    def __extract_version(cls, fileobj):
        with tarfile.open(fileobj=fileobj) as tar:
            # extract version from .PKGINFO
            pkginfo = [tuple(map(str.strip, x.decode().split("="))) for x in list(tar.extractfile(".PKGINFO")) if
                       x[0] != '#']
            pkgversion = next((x for x in pkginfo if x[0] == 'pkgver'))[1]

        return pkgversion.partition("-")[0]


class PortableBuild(Build):
    def __init__(self, path):
        super().__init__(path)
        if not (self.path / "renode").exists():
            msg = f"Renode not found in {path}"
            raise FileNotFoundError(msg)

    @classmethod
    def download(cls, target_dir, version=None, progress=None, direct=False, *args, **kwargs):
        target_dir = pathlib.Path(target_dir)
        to_download = "renode-latest.linux-portable.tar.gz" if version is None else f"renode-{version}.linux-portable.tar.gz"
        content = cls._download_file(f"https://builds.renode.io/{to_download}", progress)

        with tarfile.open(fileobj=io.BytesIO(content)) as tar:
            dir_name = tar.getmembers()[0].name
            final_path = target_dir if direct else target_dir / dir_name

            try:
                build = cls(final_path)
                logger.info(f"Renode {dir_name} is already available in {final_path}, keeping the previous version.")
                return build
            except FileNotFoundError:
                pass

            if direct:
                cls.__direct_extract(target_dir, tar)
            else:
                cls.__extract(target_dir, tar)

            logger.info(f"Renode stored in {final_path}.")

            return cls(final_path)

    @classmethod
    def __direct_extract(cls, path, tar):
        members = tar.getmembers()
        for member in members:
            member.path = Path(*Path(member.path).parts[1:])

        tar.extractall(path, members=members)

    @classmethod
    def __extract(cls, path, tar):
        tar.extractall(path)


class BuildFetcher:
    BUILD_TYPES = {
        "arch": ArchBuild,
        "portable": PortableBuild,
    }

    def __init__(self, artifacts_dir, progress=None):
        self.artifacts_dir = pathlib.Path(artifacts_dir)
        self._progress = progress

    def download(self, build_type='portable', target_dir=None, version=None, direct=False):
        build_cls, config = self.__build_type_info(build_type)
        target_dir = target_dir if target_dir else self.artifacts_dir / "renode-run.download"

        try:
            build = build_cls.download(target_dir.resolve(), version, self._progress, direct=direct)
        except Exception as e:
            logger.error("Renode could not be downloaded. Check if you have working internet connection and provided Renode version is correct (if specified)")
            raise e

        config.write_text(str(build.path))

        return build

    def fetch(self, build_type='portable', try_to_download=True):
        build_cls, config = self.__build_type_info(build_type)

        if config.exists():
            build_path = pathlib.Path(config.read_text())

            try:
                build = build_cls(build_path)
                logger.info(f"Renode found in {build_path}")
                return build
            except FileNotFoundError:
                logger.warning(f"Renode-run download listed in {config}, but the target directory {build_path} was not found.")

        if try_to_download:
            logger.info(f"Downloading Renode...")
            return self.download(build_type)

    def __build_type_info(self, build_type):
        return self.BUILD_TYPES[build_type], self.__get_config(build_type)

    def __get_config(self, build_type):
        return self.artifacts_dir / f"renode-run.{build_type}.path"


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


def get_renode(artifacts_dir, try_to_download=True):
    # First, we try <artifacts_dir>, then we look in $PATH
    from shutil import which
    renode_path = which("renode")

    fetcher = BuildFetcher(artifacts_dir, lambda x: tqdm(total=x, unit='iB', unit_scale=True))

    if (build := fetcher.fetch(try_to_download=False)) is not None:
        return build.path / "renode"

    if renode_path is not None:
        return renode_path

    if try_to_download and (build := fetcher.download()) is not None:
        return build.path / "renode"

    print("Renode not found, could not download. Please run `renode-run download` manually or visit https://builds.renode.io")

    return None


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
        import urllib.request
        urllib.request.urlretrieve(f"{dashboard_link}/{platform}-{binary_name}/{platform}-{binary_name}.dts", platform + ".dts")
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
                     version: Annotated[str, typer.Argument(help='specifies Renode version to download')] = 'latest',
                     arch: Annotated[bool, typer.Option("--arch-pkg", help='whether Arch package should be installed')] = False):
    # Option passed after the command has higher priority.
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)
    os.makedirs(artifacts_path, exist_ok=True)
    target_dir_path = path
    fetcher = BuildFetcher(artifacts_path, lambda x: tqdm(total=x, unit='iB', unit_scale=True))

    fetcher.download(
        build_type='arch' if arch else 'portable',
        target_dir=target_dir_path,
        version=None if version == 'latest' else version,
        direct=direct
    )


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

    url = requests.get(f"{dashboard_link}/results-shell_module-all.json", "results.json")
    results = json.loads(url.text)
    boards = [r["board_name"] for r in results]

    if board not in boards:
        print(f'Platform "{board}" not in Zephyr platforms list on server.')
        print(f'Available platforms:{chr(10)}{chr(10).join(boards)}')
        print('Choose one of the platforms listed above and try again.')
        sys.exit(1)

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
    import venv

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
    logging.basicConfig(level=logging.INFO)
    global renode_args
    if "--" in sys.argv:
        index = sys.argv.index("--")
        renode_args = sys.argv[index+1:]
        sys.argv = sys.argv[:index]
    app()
