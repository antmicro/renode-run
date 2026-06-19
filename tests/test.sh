#!/usr/bin/env bash

set -eu

DEFAULT_ARTIFACTS_PATH="$HOME/.config/renode"
DEFAULT_DOTNET_PORTABLE_PATH="$DEFAULT_ARTIFACTS_PATH/renode-run.download/dotnet-portable"
TEST_PLAYGROUND_PATH="$(pwd)/test_playground"
TEST_ARTIFACTS_PATH="$TEST_PLAYGROUND_PATH/test_artifacts"
TEST_DOWNLOAD_PATH="$TEST_PLAYGROUND_PATH/test_download"
TEST_VENV_PATH="$TEST_PLAYGROUND_PATH/test_venv"

BOARD=nrf52840dk_nrf52840
SAMPLE=hello_world
ELF_PATH="$(pwd)/bin.elf"
ELF_LINK=https://dl.antmicro.com/projects/renode/renode-nrf52840-zephyr_shell_module.elf-gf8d05cf-s_1310072-c00fbffd6b65c6238877c4fe52e8228c2a38bf1f

ROBOT_TEST="tests/example.robot"
ROBOT_TEST_ARTIFACTS="log.html report.html robot_output.xml"

PARAMS=""
case "$OSTYPE" in
  linux*)
    PARAMS="--console --disable-xwt --plain"
    ;;
  *)
    PARAMS="--disable-xwt --plain"
    ;;
esac

assert_artifact_exists()
{
  path="$1"
  artifact="$2"

  echo -n "Does $artifact exist in $path? "
  if find "$path" -name "$artifact" >/dev/null
  then
    echo "Yes"
  else
    echo "No"
    exit 1
  fi
}

delete_test_files()
{
  rm -rf "$DEFAULT_ARTIFACTS_PATH" \
         "$TEST_PLAYGROUND_PATH" \
         "$(pwd)/$BOARD".* \
         "$ELF_PATH" \
         $ROBOT_TEST_ARTIFACTS
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

test_default_behaviour_with_renode_dotnet_portable()
{
  renode-run download --renode-variant dotnet-portable
  renode-run --renode-variant dotnet-portable -- $PARAMS -e "q"
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH" "renode-*"
}

test_using_exec_command_explicitly()
{
  renode-run exec -- $PARAMS -e "q"
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH" "renode-*"
}

test_downloading_to_default_location()
{
  renode-run download
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH" "renode-*"
  renode-run -- $PARAMS -e "q"
}

test_downloading_to_selected_location()
{
  renode-run download --path "$TEST_DOWNLOAD_PATH"
  assert_artifact_exists "$TEST_DOWNLOAD_PATH/dotnet-portable" "renode-*"
  renode-run -- $PARAMS -e "q"
}

test_downloading_to_selected_location_directly()
{
  renode-run download --path $TEST_DOWNLOAD_PATH --direct
  assert_artifact_exists "$TEST_DOWNLOAD_PATH/renode" "renode"
  renode-run -- $PARAMS -e "q"
}

test_downloading_selected_renode_version()
{
  local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
  local RENODE_VERSION_COMMIT=${RENODE_VERSION: -9:8}
  local RENODE_VERSION_NUMBER=${RENODE_VERSION:0:6}
  renode-run download $RENODE_VERSION
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION" "renode"
  if ! [ $(renode-run -- --version | grep -c -e "Renode v$RENODE_VERSION_NUMBER" -e "build: $RENODE_VERSION_COMMIT") == 2 ]
  then
    echo "Downloaded renode version doesn't match"
    exit 1
  fi
}

test_downloading_without_creating_directories_for_versions()
{
  renode-run download -d
  case "$OSTYPE" in
    linux*)
      assert_artifact_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.download" "renode"
      assert_artifact_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.download" "renode-test"
      ;;
    *)
      assert_artifact_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.download" "renode.exe"
      assert_artifact_exists "$DEFAULT_ARTIFACTS_PATH/renode-run.download" "renode-test.bat"
      ;;
  esac
  renode-run -- $PARAMS -e "q"
}

test_downloading_present_renode_version()
{
  local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
  renode-run download $RENODE_VERSION
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH" "renode-$RENODE_VERSION"
  if ! [ $(renode-run download $RENODE_VERSION 2>&1 | grep -c "Downloading Renode") == 0 ]
  then
    echo "Present Renode version should not be downloaded again"
    exit 1
  fi
}

test_downloading_present_renode_version_in_custom_location()
{
  local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
  renode-run download $RENODE_VERSION --path "$TEST_DOWNLOAD_PATH"
  assert_artifact_exists "$TEST_DOWNLOAD_PATH/dotnet-portable" "renode-$RENODE_VERSION"
  if ! [ $(renode-run download $RENODE_VERSION --path "$TEST_DOWNLOAD_PATH" 2>&1 | grep -c "Downloading Renode") == 0 ]
  then
    echo "Present Renode version should not be downloaded again"
    exit 1
  fi
}

test_downloading_present_renode_version_in_custom_location_directly()
{
  local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
  renode-run download $RENODE_VERSION --path "$TEST_DOWNLOAD_PATH" --direct
  assert_artifact_exists "$TEST_DOWNLOAD_PATH/renode" "renode"
  if ! [ $(renode-run download $RENODE_VERSION --path "$TEST_DOWNLOAD_PATH" --direct 2>&1 | grep -c "Downloading Renode") == 0 ]
  then
    echo "Present Renode version should not be downloaded again"
    exit 1
  fi
}

test_downloading_present_renode_version_overriden_by_force()
{
  local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
  renode-run download $RENODE_VERSION
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION" "renode"
  if [ $(renode-run download $RENODE_VERSION --force 2>&1 | grep -c "Downloading Renode") == 0 ]
  then
    echo "With --force option Renode should be downloaded even when present"
    exit 1
  fi
}

test_downloading_present_renode_latest()
{
  renode-run download
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH" "renode-*"
  if ! [ $(renode-run download 2>&1 | grep -c "Downloading Renode") == 0 ]
  then
    echo "Present Renode version should not be downloaded again"
    exit 1
  fi
}

test_downloading_present_renode_latest_in_custom_location()
{
  renode-run download --path "$TEST_DOWNLOAD_PATH"
  assert_artifact_exists "$TEST_DOWNLOAD_PATH/dotnet-portable" "renode-*"
  if ! [ $(renode-run download --path "$TEST_DOWNLOAD_PATH" 2>&1 | grep -c "Downloading Renode") == 0 ]
  then
    echo "Present Renode version should not be downloaded again"
    exit 1
  fi
}

test_downloading_present_renode_latest_in_custom_location_directly()
{
  renode-run download --path "$TEST_DOWNLOAD_PATH" --direct
  assert_artifact_exists "$TEST_DOWNLOAD_PATH" "renode"
  if ! [ $(renode-run download --path "$TEST_DOWNLOAD_PATH" --direct 2>&1 | grep -c "Downloading Renode") == 0 ]
  then
    echo "Present Renode version should not be downloaded again"
    exit 1
  fi
}

test_downloading_present_renode_latest_overriden_by_force()
{
  renode-run download
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH" "renode-*"
  if [ $(renode-run download --force 2>&1 | grep -c "Downloading Renode") == 0 ]
  then
    echo "With --force option Renode should be downloaded even when present"
    exit 1
  fi
}

test_downloading_different_renode_version_in_custom_location_directly()
{
  local RENODE_VERSION1=1.16.1+20260302gita3bdf4a87
  local RENODE_VERSION2=1.16.1+20260515gitac6335d02
  renode-run download $RENODE_VERSION1 --path "$TEST_DOWNLOAD_PATH" --direct
  assert_artifact_exists "$TEST_DOWNLOAD_PATH" "renode"
  if [ $(renode-run download $RENODE_VERSION2 --path "$TEST_DOWNLOAD_PATH" --direct 2>&1 | grep -c "Downloading Renode") == 0 ]
  then
    echo "On version change Renode should be downloaded again"
    exit 1
  fi
}

test_downloading_different_renode_version()
{
  local RENODE_VERSION1=1.16.1+20260302gita3bdf4a87
  local RENODE_VERSION2=1.16.1+20260515gitac6335d02
  renode-run download $RENODE_VERSION1
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH" "renode-$RENODE_VERSION1"
  # Presence of one version should not prevent downloading another.
  renode-run download $RENODE_VERSION2
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH" "renode-$RENODE_VERSION2"
}

test_behavior_on_external_install_delete()
{
  local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
  renode-run download $RENODE_VERSION
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION" "renode"
  rm -rf "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION"
  if [ $(renode-run download $RENODE_VERSION | grep -c "Downloading Renode") == 0 ]
  then
    echo "Missing install should be downloaded again"
    exit 1
  fi
}

test_reinstall_updates_default_version()
{
  local RENODE_VERSION1=1.16.1+20260302gita3bdf4a87
  local RENODE_VERSION1_COMMIT=${RENODE_VERSION1: -9:8}
  local RENODE_VERSION2=1.16.1+20260515gitac6335d02
  renode-run download $RENODE_VERSION1
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION1" "renode"
  renode-run download $RENODE_VERSION2
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION2" "renode"
  renode-run download $RENODE_VERSION1
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION1" "renode"
  if ! [ $(renode-run -- --version | grep -c -e "build: $RENODE_VERSION1_COMMIT") == 1 ]
  then
    echo "Reinstalling should update the default version to the reinstalled one"
    exit 1
  fi
}

test_list_command_output()
{
  local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
  renode-run download
  renode-run download $RENODE_VERSION
  if ! [ $(renode-run list 2>&1 | grep "renode-$RENODE_VERSION" | grep -c "default") == 1 ]
  then
    echo "Last downloaded Renode should be listed and marked as default"
    exit 1
  fi
  if ! [ $(renode-run list 2>&1 | grep -v -e "renode-$RENODE_VERSION" | grep -c "latest") == 1 ]
  then
    echo "Latest Renode should be marked as 'latest'"
    exit 1
  fi
}

test_filter_clears_non_existent_installations()
{
  local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
  renode-run download $RENODE_VERSION --path "$TEST_DOWNLOAD_PATH" --direct
  if ! [ $(renode-run list 2>&1 | grep -c "$RENODE_VERSION") == 1 ]
  then
    echo "List command should list directly downloaded Renode"
    exit 1
  fi
  
  rm -rf $TEST_DOWNLOAD_PATH
  if ! [ $(renode-run list 2>&1 | grep -c "$RENODE_VERSION") == 0 ]
  then
    echo "List command should not show deleted Renode installs"
    exit 1
  fi
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

tests=(
  test_default_behaviour
  test_default_behaviour_with_custom_artifacts_path
  test_using_exec_command_explicitly
  test_downloading_to_default_location
  test_downloading_to_selected_location
  test_downloading_to_selected_location_directly
  test_downloading_selected_renode_version
  test_downloading_without_creating_directories_for_versions
  test_downloading_present_renode_version
  test_downloading_present_renode_version_in_custom_location
  test_downloading_present_renode_version_in_custom_location_directly
  test_downloading_present_renode_version_overriden_by_force
  test_downloading_present_renode_latest
  test_downloading_present_renode_latest_in_custom_location
  test_downloading_present_renode_latest_in_custom_location_directly
  test_downloading_present_renode_latest_overriden_by_force
  test_downloading_different_renode_version_in_custom_location_directly
  test_downloading_different_renode_version
  test_behavior_on_external_install_delete
  test_reinstall_updates_default_version
  test_list_command_output
  test_filter_clears_non_existent_installations
  test_running_dashboard_demo
  test_running_local_elf
  test_saving_repl_and_dts
)

# renode-run test is supported only on Linux.
if [[ "$OSTYPE" == "linux"* ]]; then
  tests+=(
    test_running_renode-test
    test_using_custom_venv_directory
  )
fi


trap "delete_test_files; exit 1" EXIT
for test in "${tests[@]}"
do
  run_test "$test"
  delete_test_files
done
trap - EXIT
