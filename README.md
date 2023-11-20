# renode-run

Copyright (c) 2022-2023 [Antmicro](https://www.antmicro.com/)

## Usage

Install:

```
pip3 install --upgrade --user git+https://github.com/antmicro/renode-run
```

Download/upgrade Renode to the latest nightly build:

```
renode-run download
```

Run Renode interactively:

```
renode-run
```

Run Renode interactively with additional command line arguments:

```
renode-run -- --help
```

Run Robot tests in Renode:

```
renode-run test -- testname.robot
```

Run a demo from [Renodepedia](https://zephyr-dashboard.renode.io/renodepedia/):

```
renode-run demo --board 96b_nitrogen shell_module
```

You can also provide a name of your local ELF file with a similar syntax:

```
renode-run demo --board 96b_nitrogen my-software.elf
```
