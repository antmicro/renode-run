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

Manage installed Renode versions:

```sh
renode-run list

renode-run remove 1.16.1+20260620gitdc52b24c1
```
