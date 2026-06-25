#!/usr/bin/env python3
#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

import json
import os
import requests
import subprocess
import sys
import tempfile
import typer
import venv

from pathlib import Path
from typing_extensions import Annotated
from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt
from urllib import request, error, parse

from renode_run.defaults import DASHBOARD_LINK, RENODE_TEST_VENV_DIRNAME, RENODE_RUN_CONFIG_FILENAME, RENODE_TARGET_DIRNAME
from renode_run.generate import generate_script
from renode_run.get import download_renode, get_renode, get_matching_installed_renode_instances
from renode_run.utils import RenodeVariant, ConfigFile, PortablePackage
from renode_run.utils import choose_artifacts_path, fetch_renode_version, fetch_zephyr_version
from renode_run.package import RENODE_TEST, package_type

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

        args = [context.env_exe, '-m', 'pip', 'install', '-r', self.requirements_path]
        env = os.environ
        env['VIRTUAL_ENV'] = context.env_dir

        try:
            subprocess.check_call(args, env=env)
        except subprocess.CalledProcessError as err:
            print(f'Could not install given requirements: {err}')
            print('Requirements have to be installed manually, or the environment has to be deleted before running command again')
            print(f'Environment path: {context.env_dir}')
            exit(err.returncode)


# For backward compatibility artifacts_path option can be passed both before and after specifying the command.
@app.command("download", help="download Renode portable (Linux and Windows only!)")
def download_command(artifacts_path: artifacts_path_annotation = None,
                     path: Annotated[Path, typer.Option("-p", "--path", help='path for Renode download')] = None,
                     direct: Annotated[bool, typer.Option("-d/ ", "--direct/ ", help='do not create additional directories with Renode version')] = False,
                     force: Annotated[bool, typer.Option("-f", "--force/ ", help='download renode even if it is already present')] = False,
                     renode_variant: RenodeVariant = RenodeVariant.default(),
                     version: Annotated[str, typer.Argument(help='specifies Renode version to download')] = 'latest'):
    # Option passed after the command has higher priority.
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)
    os.makedirs(artifacts_path, exist_ok=True)

    download_renode(
        target_dir_path=path or artifacts_path / RENODE_TARGET_DIRNAME,
        config_path=artifacts_path / RENODE_RUN_CONFIG_FILENAME,
        renode_variant=renode_variant,
        version=version,
        direct=direct,
        force=force,
    )

@app.command("install", help="install Renode from specified source (Linux and Windows only!)")
def install_command(source: Annotated[str, typer.Argument(help='specifies Renode package source (version, local archive or link to remote)')],
                    artifacts_path: artifacts_path_annotation = None,
                    path: Annotated[Path, typer.Option("-p", "--path", help='path for Renode install')] = None,
                    direct: Annotated[bool, typer.Option("-d/ ", "--direct/ ", help='do not create additional directories with Renode version')] = False,
                    renode_variant: RenodeVariant = RenodeVariant.default(),
                    version_override: Annotated[str, typer.Option("--version-override", help='override package version information')] = None):
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)
    target_dir_path = path or artifacts_path / RENODE_TARGET_DIRNAME
    config_path = artifacts_path / RENODE_RUN_CONFIG_FILENAME
    config = ConfigFile(config_path, package_type())

    local_package_path = None
    is_local_file = Path(source).is_file()
    url = parse.urlparse(source)
    if is_local_file:
        local_package_path = Path(source)
        print("Installing from local package...")
    elif url.scheme:
        print("Downloading package from remote...")

        # Do not auto-remove local resources, as urlretrieve doesn't copy local files.
        is_localhost = url.hostname == "localhost" or url.hostname is None
        is_local_file = url.scheme == "file" and is_localhost

        try:
            renode_package, _ = request.urlretrieve(source, reporthook=PortablePackage._report_progress())
        except error.HTTPError:
            print("Package could not be downloaded. Check if you have working internet connection and provided link is correct")
            sys.exit(1)

        if os.name == 'nt' and url.scheme == "file":
            # On Windows request.urlretrieve returns a malformed path for 'file' URI scheme.
            renode_package = request.url2pathname(url.path)

        local_package_path = Path(renode_package)
        print("Downloaded package to:", local_package_path)
    else:
        print("Interpreting source as Renode version string")
        download_command(artifacts_path, path, direct, True, renode_variant, source)
        return

    package = package_type()(renode_variant, None, local_package_path, not is_local_file)

    os.makedirs(target_dir_path, exist_ok=True)
    
    try:
        (final_path, version_str) = package.extract(target_dir_path, direct, version_override)
    except package_type().UnableToFindVersion:
        print("Package does not contain version information. Please provide the version name using '--version-override' option")
        sys.exit(1)
    except:
        print("Unable to extract package. Please make sure the provided source contains a Renode portable package for Your platform")
        sys.exit(1)

    print(f"Installed Renode({version_str}) to {final_path}")

    config.update_download(renode_variant, version_str, final_path, False)
    config.save_config()

@app.command("default", help="choose default Renode installation")
def default_command(renode_instance: Annotated[str, typer.Argument(help='Renode instance to set as default (indicated by version or path)')] = None,
                   artifacts_path: artifacts_path_annotation = None,
                   renode_variant: RenodeVariant = RenodeVariant.default()):
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)
    config_file_path = artifacts_path / RENODE_RUN_CONFIG_FILENAME

    config_file = ConfigFile(config_file_path, package_type())

    if renode_instance is None:
        default_path_str = config_file.get_default_path(renode_variant)
        if default_path_str is None:
            print(f"No default set for {renode_variant.value}")
            exit(1)
        else:
            print(default_path_str)

        return

    (default_candidates, unambiguos_match) = get_matching_installed_renode_instances(config_file, renode_variant, renode_instance)

    if not default_candidates:
        print(f"No package identifiable by '{renode_instance}' are installed, exiting")
        return

    package_id = 1
    if not unambiguos_match:
        choices = []
        for package_path in default_candidates:
            print(f"{package_id}. {str(package_path)}")
            choices.append(str(package_id))
            package_id += 1

        print()
        response = Prompt.ask(f"Enter number of the instance to set as default:\n", choices=choices)
        package_id = int(response)

    package_path = default_candidates[package_id - 1]
    config_file.update_default(renode_variant, package_path)
    config_file.save_config()
    print(f"Package located at {package_path} set as default for {renode_variant.value}")


@app.command("remove", help="remove Renode installation")
def remove_command(renode_instance: Annotated[str, typer.Argument(help='Renode instance to remove (indicated by version or path)')],
                   remove_all: Annotated[bool, typer.Option("--remove-all", help='remove all installations of the given version without a prompt', is_flag=True)] = False,
                   artifacts_path: artifacts_path_annotation = None):
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)
    config_file_path = artifacts_path / RENODE_RUN_CONFIG_FILENAME

    config_file = ConfigFile(config_file_path, package_type())

    (packages_to_remove, unambiguos_match) = get_matching_installed_renode_instances(config_file, None, renode_instance)

    if not packages_to_remove:
        print(f"No package with version '{renode_instance}' installed, exiting")
        return

    if unambiguos_match or remove_all:
        for package_path in packages_to_remove:
            config_file.remove_installation(package_type(), package_path)

        config_file.save_config()
        return

    REMOVE_NOTHING_OPTION = "N"
    REMOVE_ALL_OPTION = "a"

    print("Found multiple instances of given version:")
    package_id = 1
    choices = [REMOVE_NOTHING_OPTION, REMOVE_ALL_OPTION]
    for package_path in packages_to_remove:
        print(f"{package_id}. {str(package_path)}")
        choices.append(str(package_id))
        package_id += 1
    
    print()
    response = Prompt.ask(f"Enter number of the instance to remove: ({REMOVE_NOTHING_OPTION}=neither, {REMOVE_ALL_OPTION}=remove all)\n", choices=choices, default=REMOVE_NOTHING_OPTION, case_sensitive=False)

    if response == REMOVE_NOTHING_OPTION:
        return
    elif response == REMOVE_ALL_OPTION:
        for package_path in packages_to_remove:
            config_file.remove_installation(package_type(), package_path)
    else:
        package_id = int(response)
        path_to_remove = packages_to_remove[package_id - 1]
        config_file.remove_installation(package_type(), path_to_remove)

    config_file.save_config()


# For backward compatibility artifacts_path option can be passed both before and after specifying the command.
@app.command("demo", help="run a demo from precompiled binaries")
def demo_command(board: Annotated[str, typer.Option("-b", "--board", help='board name, as listed on https://zephyr-dashboard.renode.io')],
                 binary: Annotated[str, typer.Argument(help='binary name, either local or remote')],
                 artifacts_path: artifacts_path_annotation = None,
                 generate_repl: Annotated[bool, typer.Option("-g/ ", "--generate-repl/ ", help='whether to generate the repl from dts')] = False,
                 renode_variant: RenodeVariant = RenodeVariant.default()):
    # Option passed after the command has higher priority.
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)

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

    renode_path = get_renode(artifacts_path, renode_variant)

    if renode_path is None:
        sys.exit(1)

    script = generate_script(binary, board, generate_repl)

    with tempfile.NamedTemporaryFile(delete=False) as temp:
        temp.write(script.encode("utf-8"))
        temp.flush()
        temp.close()
        ret = subprocess.run([str(renode_path), temp.name] + renode_args)
    sys.exit(ret.returncode)


# For backward compatibility artifacts_path option can be passed both before and after specifying the command.
@app.command("exec", help="execute Renode with arguments")
def exec_command(artifacts_path: artifacts_path_annotation = None, 
                 renode_variant: RenodeVariant = RenodeVariant.default()):
    # Option passed after the command has higher priority.
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)
    renode = get_renode(artifacts_path, renode_variant)
    if renode is None:
        sys.exit(1)

    sys.stdout.flush()
    ret = subprocess.run([str(renode)] + renode_args)
    sys.exit(ret.returncode)


# For backward compatibility artifacts_path option can be passed both before and after specifying the command.
@app.command("test", help="execute renode-test with arguments")
def test_command(artifacts_path: artifacts_path_annotation = None,
                 venv_path: Annotated[Path, typer.Option("--venv", help='path for virtualenv used by renode-test')] = None,
                 renode_variant: RenodeVariant = RenodeVariant.default()):
    # Option passed after the command has higher priority.
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)
    renode_path = get_renode(artifacts_path, renode_variant)
    if renode_path is None:
        sys.exit(1)

    renode_dir = renode_path.parent
    renode_test = renode_dir / RENODE_TEST
    if not Path.exists(renode_test):
        print(f'Found Renode binary in {renode_dir}, but {RENODE_TEST} is missing; trying test.sh')
        renode_test = renode_dir / 'test.sh'

        if not Path.exists(renode_test):
            print('test.sh does not exist; corrupted package?')
            sys.exit(1)

        print('test.sh script found, using it instead of renode-test')

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


@app.command("list", help="list Renode installations")
def list_command(artifacts_path: artifacts_path_annotation = None):
    artifacts_path = choose_artifacts_path(global_artifacts_path, artifacts_path)
    config_file_path = artifacts_path / RENODE_RUN_CONFIG_FILENAME

    config_file = ConfigFile(config_file_path, package_type())

    default_dotnet_package_path = config_file.get_default_path(RenodeVariant.DOTNET_PORTABLE)
    default_mono_package_path = config_file.get_default_path(RenodeVariant.MONO_PORTABLE)

    (_, latest_version) = config_file.get_latest_data()

    release_table = Table(box=None, show_edge=False)
    release_table.add_column("Package Path")
    release_table.add_column("Version")
    release_table.add_column("Renode Variant")
    release_table.add_column("Tags")

    for (package_path_str, (version, variant)) in config_file.get_renode_installs():
        tags = []

        if package_path_str == default_dotnet_package_path:
            tags.append("default")
        elif package_path_str == default_mono_package_path:
            tags.append("default-mono")

        if version == latest_version:
            tags.append("latest")

        release_table.add_row(package_path_str, version, variant, " ".join(tags) if tags else "-")

    # If rich Console fails to deduce console width it defaults to 80,
    # which does not allow for full package-paths to be printed
    terminal_width = None if sys.stdout.isatty() else 10000
    console = Console(width=terminal_width)
    console.print(release_table)


# Calling renode-run without arguments runs renode from default path
@app.callback(invoke_without_command=True)
def parse_artifacts_path(ctx: typer.Context,
                         artifacts_path: artifacts_path_annotation = None,
                         renode_variant: RenodeVariant = RenodeVariant.default()):
    # For backward compatibility we're allowing to pass artifacts_path before specifying the command
    global global_artifacts_path
    global_artifacts_path = artifacts_path
    if ctx.invoked_subcommand is None:
        exec_command(artifacts_path, renode_variant)


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
