. $(dirname "$0")/common.sh

BOARD=nrf52840dk_nrf52840
SAMPLE=hello_world
ELF_PATH="$(pwd)/bin.elf"
ELF_LINK=https://dl.antmicro.com/projects/renode/renode-nrf52840-zephyr_shell_module.elf-gf8d05cf-s_1310072-c00fbffd6b65c6238877c4fe52e8228c2a38bf1f

RENODE_LATEST_PACKAGE_PATH="$(cache_renode_package latest)"

RENODE_VERSION=1.16.1+20260302gita3bdf4a87
RENODE_VERSION_PACKAGE_PATH="$(cache_renode_package $RENODE_VERSION)"

#By default, renode-run should check if there is a renode in artifacts directory (default one here).
#If yes then run it, else download it to artifacts directory and then run it.
#This behaviour occurs for every command except download.
test_default_behaviour()
{
  renode-run -- $PARAMS -e "q"
  assert_artifact_exists "$DEFAULT_INSTALL_PATH" "renode-*"
}

#Setting custom artifacts path should work the same for all commands,
#so there is no need to test this option for all of them.
test_default_behaviour_with_custom_artifacts_path()
{
  renode-run install "$RENODE_LATEST_PACKAGE_PATH"
  renode-run -a "$TEST_ARTIFACTS_PATH" -- $PARAMS -e "q"
  assert_artifact_exists "$TEST_ARTIFACTS_PATH/renode-run.download" "renode-*"
}

test_using_exec_command_explicitly()
{
  renode-run install "$RENODE_LATEST_PACKAGE_PATH"
  renode-run exec -- $PARAMS -e "q"
  assert_artifact_exists "$DEFAULT_INSTALL_PATH" "renode-*"
}

test_using_exec_with_package_path()
{
  renode-run install "$RENODE_LATEST_PACKAGE_PATH" --path "$TEST_DOWNLOAD_PATH" --direct
  renode-run exec "$TEST_DOWNLOAD_PATH" -- $PARAMS -e "q"
}

test_using_exec_with_latest()
{
  renode-run download
  renode-run exec latest -- $PARAMS -e "q"
}

test_using_exec_with_custom_version()
{
  renode-run install "$RENODE_VERSION_PACKAGE_PATH"
  renode-run exec 1.16 -- $PARAMS -e "q"
}

test_implicit_exec_with_package_path()
{
  renode-run install "$RENODE_LATEST_PACKAGE_PATH" --path "$TEST_DOWNLOAD_PATH" --direct
  renode-run "$TEST_DOWNLOAD_PATH" -- $PARAMS -e "q"
}

test_implicit_exec_with_latest()
{
  renode-run download
  renode-run latest -- $PARAMS -e "q"
}

test_implicit_exec_with_custom_version()
{
  renode-run install "$RENODE_VERSION_PACKAGE_PATH"
  renode-run 1.16 -- $PARAMS -e "q"
}

test_running_renode-test()
{
  renode-run install "$RENODE_LATEST_PACKAGE_PATH"
  renode-run test -- "$DEFAULT_INSTALL_PATH/renode-"*"/$ROBOT_TEST"
  assert_artifact_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.venv" "pyvenv.cfg"
}

test_using_custom_venv_directory()
{
  renode-run install "$RENODE_LATEST_PACKAGE_PATH"
  renode-run test --venv "$TEST_VENV_PATH" -- "$DEFAULT_INSTALL_PATH/renode-"*"/$ROBOT_TEST"
  assert_artifact_exists "$TEST_VENV_PATH" "pyvenv.cfg"
}

test_running_dashboard_demo()
{
  renode-run install "$RENODE_LATEST_PACKAGE_PATH"
  #This is a simplified test which doesn't verify if Renode actually executes the demo.
  renode-run demo --board "$BOARD" --binary "$SAMPLE" -- $PARAMS -e "q"
}

test_saving_repl_and_dts()
{
  renode-run install "$RENODE_LATEST_PACKAGE_PATH"
  renode-run demo -g --board "$BOARD" --binary "$SAMPLE" -- $PARAMS -e "q"
  assert_artifact_exists "$(pwd)" "$BOARD.repl"
  assert_artifact_exists "$(pwd)" "$BOARD.dts"
}

test_running_local_elf()
{
  renode-run install "$RENODE_LATEST_PACKAGE_PATH"
  curl -o "$ELF_PATH" "$ELF_LINK"
  #This is a simplified test which doesn't verify if Renode actually executes the demo.
  renode-run demo --board "$BOARD" --binary "$ELF_PATH" -- $PARAMS -e "q"
}

test_running=(
  test_default_behaviour
  test_default_behaviour_with_custom_artifacts_path
  test_using_exec_command_explicitly
  test_using_exec_with_package_path
  test_using_exec_with_latest
  test_using_exec_with_custom_version
  test_implicit_exec_with_package_path
  test_implicit_exec_with_latest
  test_implicit_exec_with_custom_version
  test_running_renode-test
  test_using_custom_venv_directory
  test_running_dashboard_demo
  test_saving_repl_and_dts
  test_running_local_elf
)
