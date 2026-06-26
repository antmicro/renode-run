. $(dirname "$0")/common.sh

BOARD=nrf52840dk_nrf52840
SAMPLE=hello_world
ELF_PATH="$(pwd)/bin.elf"
ELF_LINK=https://dl.antmicro.com/projects/renode/renode-nrf52840-zephyr_shell_module.elf-gf8d05cf-s_1310072-c00fbffd6b65c6238877c4fe52e8228c2a38bf1f


#By default, renode-run should check if there is a renode in artifacts directory (default one here).
#If yes then run it, else download it to artifacts directory and then run it.
#This behaviour occurs for every command except download.
test_default_behaviour()
{
  renode-run -- $PARAMS -e "q"
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH" "renode-*"
}

#Setting custom artifacts path should work the same for all commands,
#so there is no need to test this option for all of them.
test_default_behaviour_with_custom_artifacts_path()
{
  renode-run -a "$TEST_ARTIFACTS_PATH" -- $PARAMS -e "q"
  assert_artifact_exists "$TEST_ARTIFACTS_PATH/renode-run.download/dotnet-portable" "renode-*"
}

test_using_exec_command_explicitly()
{
  renode-run exec -- $PARAMS -e "q"
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH" "renode-*"
}

test_running_renode-test()
{
  renode-run download
  renode-run test -- "$DEFAULT_DOTNET_PORTABLE_PATH/renode-"*"/$ROBOT_TEST"
  assert_artifact_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.venv" "pyvenv.cfg"
}

test_using_custom_venv_directory()
{
  renode-run download
  renode-run test --venv "$TEST_VENV_PATH" -- "$DEFAULT_DOTNET_PORTABLE_PATH/renode-"*"/$ROBOT_TEST"
  assert_artifact_exists "$TEST_VENV_PATH" "pyvenv.cfg"
}

test_running_dashboard_demo()
{
  #This is a simplified test which doesn't verify if Renode actually executes the demo.
  renode-run demo --board "$BOARD" "$SAMPLE" -- $PARAMS -e "q"
}

test_saving_repl_and_dts()
{
  renode-run demo -g --board "$BOARD" "$SAMPLE" -- $PARAMS -e "q"
  assert_artifact_exists "$(pwd)" "$BOARD.repl"
  assert_artifact_exists "$(pwd)" "$BOARD.dts"
}

test_running_local_elf()
{
  curl -o "$ELF_PATH" "$ELF_LINK"
  #This is a simplified test which doesn't verify if Renode actually executes the demo.
  renode-run demo --board "$BOARD" "$ELF_PATH" -- $PARAMS -e "q"
}

test_running=(
  test_default_behaviour
  test_default_behaviour_with_custom_artifacts_path
  test_using_exec_command_explicitly
  test_running_dashboard_demo
  test_saving_repl_and_dts
  test_running_local_elf
)

# renode-run test is supported only on Linux.
if [[ "$OSTYPE" == "linux"* ]]; then
  test_running+=(
    test_running_renode-test
    test_using_custom_venv_directory
  )
fi
