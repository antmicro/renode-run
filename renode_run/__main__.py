#!/usr/bin/env python3
#
# Copyright (c) 2022-2024 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import os
import sys
import venv
from pathlib import Path

import typer
from typing_extensions import Annotated

from renode_run.defaults import DASHBOARD_LINK, RENODE_TEST_VENV_DIRNAME, RENODE_RUN_CONFIG_FILENAME, RENODE_TARGET_DIRNAME
from renode_run.generate import generate_script
from renode_run.get import download_renode, get_renode
from renode_run.utils import choose_artifacts_path, fetch_renode_version, fetch_zephyr_version

renode_args = []

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


# For backward compatibility artifacts_path option can be passed both before and after specifying the command.
@app.command("download", help="download Renode portable (Linux only!)")
def download_command(artifacts_path: artifacts_path_annotation = None,
                     path: Annotated[Path, typer.Option("-p", "--path", help='path for Renode download')] = None,
                     direct: Annotated[bool, typer.Option("-d/ ", "--direct/ ", help='do not create additional directories with Renode version')] = False,
                     version: Annotated[str, typer.Argument(help='specifies Renode version to download')] = 'latest'):
    # Option passed after the command has higher priority.
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)
    os.makedirs(artifacts_path, exist_ok=True)
    renode_run_config_path = artifacts_path / RENODE_RUN_CONFIG_FILENAME
    target_dir_path = path
    if target_dir_path is None:
        target_dir_path = artifacts_path / RENODE_TARGET_DIRNAME
    download_renode(target_dir_path, renode_run_config_path, version, direct)


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

    zephyr_version = fetch_zephyr_version()
    renode_version = fetch_renode_version()
    url = requests.get(f"{DASHBOARD_LINK}/zephyr_sim/{zephyr_version}/{renode_version}/results-shell_module-all.json", "results.json")
    results = json.loads(url.text)
    boards = [r["platform"] for r in results]

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

    if venv_path is None:
        venv_path = artifacts_path / RENODE_TEST_VENV_DIRNAME

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


if __name__ == "__main__":
    main()
