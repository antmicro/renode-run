# renode-run

Copyright (c) 2022-2026 [Antmicro](https://www.antmicro.com/)

## Install

```sh
pip3 install --upgrade --user git+https://github.com/antmicro/renode-run
```

## Usage

Download/upgrade Renode to the latest nightly build:

```sh
renode-run download
```

Run Renode interactively:

```sh
renode-run

# Run Renode interactively with additional command line arguments:
renode-run -- --help
```

Run Robot tests in Renode:

```sh
renode-run test -- testname.robot
```

Run a demo from [Antmicro Designer](https://designer.antmicro.com):

```sh
renode-run demo --board 96b_nitrogen shell_module

# You can also provide a name of your local ELF file with a similar syntax:
renode-run demo --board 96b_nitrogen my-software.elf
```

Install Renode from specified source (version, local file or remote):
```sh
# Install specified Renode version from builds.renode.io
renode-run install 1.16.1+20260620gitdc52b24c1

# Install from local package
renode-run install ~/Downloads/renode-1.16.1+20260708git9845e1cd8.linux.tar.gz

# Install renode from GitHub release
renode-run install https://github.com/renode/renode/releases/download/v1.16.1/renode-1.16.1.linux-portable-dotnet.tar.gz --version-override gh-1.16.1
```

> Note that using `install` command it is possible to install non-portable packages.  
> Those versions will be able to run provided runtime dependencies are available.

Manage installed Renode versions:

```sh
renode-run list

renode-run remove 1.16.1+20260620gitdc52b24c1

renode-run default 1.16.1
```
