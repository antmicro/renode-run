. $(dirname "$0")/common.sh

test_default_behaviour_with_renode_dotnet_portable()
{
  renode-run download --renode-variant dotnet-portable
  renode-run --renode-variant dotnet-portable -- $PARAMS -e "q"
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

test_download=(
  test_default_behaviour_with_renode_dotnet_portable
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
)
