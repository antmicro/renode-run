#!/usr/bin/env bash

set -eu

DEFAULT_ARTIFACTS_PATH=$HOME/.config/renode
TEST_ARTIFACTS_PATH=$(pwd)/test_artifacts
TEST_DOWNLOAD_PATH=$(pwd)/test_download
TEST_VENV_PATH=$(pwd)/test_venv

BOARD=nrf52840dk_nrf52840
SAMPLE=hello_world
ELF_PATH=$(pwd)/bin.elf
ELF_LINK=https://dl.antmicro.com/projects/renode/renode-nrf52840-zephyr_shell_module.elf-gf8d05cf-s_1310072-c00fbffd6b65c6238877c4fe52e8228c2a38bf1f

ROBOT_TEST="tests/example.robot"

assert_path_exists()
{
  path="$1"

  echo -n "Does $path exist? "
  if stat $path >/dev/null
  then
    echo "Yes"
  else
    echo "No"
    exit 1
  fi
}

delete_test_files()
{
  rm -rf $DEFAULT_ARTIFACTS_PATH \
         $TEST_ARTIFACTS_PATH \
         $TEST_DOWNLOAD_PATH \
         $TEST_VENV_PATH \
         $(pwd)/$BOARD.* \
         $ELF_PATH
}

run_test()
{
  echo "-----------------------------------------------------------------------"
  echo "$1 is running..."
  echo "-----------------------------------------------------------------------"
  $1
  echo "-----------------------------------------------------------------------"
  echo "Ok"
  echo "-----------------------------------------------------------------------"
}

#By default, renode-run should check if there is a renode in artifacts directory (default one here).
#If yes then run it, else download it to artifacts directory and then run it.
#This behaviour occurs for every command except download.
test_default_behaviour()
{
  renode-run -- --console --disable-xwt --plain -e "q"
  assert_path_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.download/mono-portable/renode-*"
  delete_test_files
}

#Setting custom artifacts path should work the same for all commands,
#so there is no need to test this option for all of them.
test_default_behaviour_with_custom_artifacts_path()
{
  renode-run -a $TEST_ARTIFACTS_PATH -- --console --disable-xwt --plain -e "q"
  assert_path_exists "$TEST_ARTIFACTS_PATH/renode-run.download/mono-portable/renode-*"
  delete_test_files
}

test_default_behaviour_with_renode_dotnet_portable()
{
  renode-run download --renode-variant dotnet-portable
  renode-run -- --console --disable-xwt --plain -e "q"
  assert_path_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.download/dotnet-portable/renode-*"
  delete_test_files
}

test_using_exec_command_explicitly()
{
  renode-run exec -- --console --disable-xwt --plain -e "q"
  assert_path_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.download/mono-portable/renode-*"
  delete_test_files
}

test_downloading_to_default_location()
{
  renode-run download
  assert_path_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.download/mono-portable/renode-*"
  renode-run -- --console --disable-xwt --plain -e "q"
  delete_test_files
}

test_downloadinng_to_selected_location()
{
  renode-run download --path $TEST_DOWNLOAD_PATH
  assert_path_exists "$TEST_DOWNLOAD_PATH/mono-portable/renode-*"
  #Renode installation is one directory above $TEST_DOWNLOAD_PATH so it has to be passed as artifacts path.
  renode-run -a $TEST_DOWNLOAD_PATH/.. -- --console --disable-xwt --plain -e "q"
  delete_test_files
}

test_downloading_selected_renode_version()
{
  local RENODE_VERSION=1.13.3+20230322git94d85c55 
  local RENODE_VERSION_COMMIT=${RENODE_VERSION: -8}
  local RENODE_VERSION_NUMBER=${RENODE_VERSION:0:6}
  renode-run download $RENODE_VERSION
  assert_path_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.download/mono-portable/renode-$RENODE_VERSION/renode"
  if ! renode-run -- --version | grep -q "Renode, version $RENODE_VERSION_NUMBER.*($RENODE_VERSION_COMMIT.*)"
  then
    echo "Downloaded renode version doesn't match"
    exit 1
  fi
  delete_test_files
}

test_downloading_without_creating_directories_for_versions()
{
  renode-run download -d
  assert_path_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.download/renode"
  assert_path_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.download/renode-test"
  renode-run -- --console --disable-xwt --plain -e "q"
  delete_test_files
}

test_running_renode-test()
{
  renode-run download
  local ROBOT_TEST_PATH="$DEFAULT_ARTIFACTS_PATH/renode-run.download/mono-portable/renode-*/$ROBOT_TEST"
  renode-run test -- $ROBOT_TEST_PATH
  assert_path_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.venv/pyvenv.cfg"
  delete_test_files
}

test_using_custom_venv_directory()
{
  renode-run download
  local ROBOT_TEST_PATH="$DEFAULT_ARTIFACTS_PATH/renode-run.download/mono-portable/renode-*/$ROBOT_TEST"
  renode-run test --venv $TEST_VENV_PATH -- $ROBOT_TEST_PATH
  assert_path_exists "$TEST_VENV_PATH/pyvenv.cfg"
  delete_test_files
}

test_running_dashboard_demo()
{
  #This is a simplified test which doesn't verify if Renode actually executes the demo.
  renode-run demo --board $BOARD $SAMPLE -- --console --disable-xwt --plain -e "q"
  delete_test_files
}

test_saving_repl_and_dts()
{
  renode-run demo -g --board $BOARD $SAMPLE -- --console --disable-xwt --plain -e "q"
  assert_path_exists "$(pwd)/$BOARD.repl"
  assert_path_exists "$(pwd)/$BOARD.dts"
  delete_test_files
}

test_running_local_elf()
{
  curl -o $ELF_PATH $ELF_LINK
  #This is a simplified test which doesn't verify if Renode actually executes the demo.
  renode-run demo --board $BOARD $ELF_PATH -- --console --disable-xwt --plain -e "q"
  delete_test_files
}

run_tests()
{
  run_test test_default_behaviour
  run_test test_default_behaviour_with_custom_artifacts_path
  run_test test_default_behaviour_with_renode_dotnet_portable
  run_test test_using_exec_command_explicitly
  run_test test_downloading_to_default_location
  run_test test_downloadinng_to_selected_location
  run_test test_downloading_selected_renode_version
  run_test test_downloading_without_creating_directories_for_versions
  run_test test_running_renode-test
  run_test test_using_custom_venv_directory
  #In all further tests renode will be downloaded implicitly to the default location.
  run_test test_running_dashboard_demo
  run_test test_running_local_elf
  run_test test_saving_repl_and_dts
}

run_tests
