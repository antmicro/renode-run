. $(dirname "$0")/common.sh

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

test_remove_command()
{
  local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
  renode-run download $RENODE_VERSION
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION" "renode"

  renode-run remove $RENODE_VERSION
  if ! [ $(renode-run list 2>&1 | grep -c "$RENODE_VERSION") == 0 ]
  then
    echo "Remove command should remove Renode installation"
    exit 1
  fi
}

test_remove_by_path()
{
  local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
  renode-run download $RENODE_VERSION
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION" "renode"

  renode-run remove "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION"
    if ! [ $(renode-run list 2>&1 | grep -c "$RENODE_VERSION") == 0 ]
  then
    echo "Remove command should remove Renode installation"
    exit 1
  fi
}

test_remove_all_command()
{
  local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
  renode-run download $RENODE_VERSION
  renode-run download $RENODE_VERSION --path "$TEST_DOWNLOAD_PATH" --direct
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION" "renode"
  assert_artifact_exists "$TEST_DOWNLOAD_PATH" "renode"

  renode-run remove $RENODE_VERSION --remove-all
  if ! [ $(renode-run list 2>&1 | grep -c "$RENODE_VERSION") == 0 ]
  then
    echo "Remove with '--remove-all' option should remove all Renode installation with a given version"
    exit 1
  fi
}

test_remove_does_not_affect_other_versions()
{
  local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
  renode-run download
  renode-run download $RENODE_VERSION

  renode-run remove $RENODE_VERSION
  if ! [ $(renode-run list 2>&1 | grep -c "latest") == 1 ]
  then
    echo "Remove command should not affect other installed versions"
    exit 1
  fi
}

test_default()
{
  local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
  renode-run download $RENODE_VERSION
  renode-run download
  if ! [ $(renode-run list 2>&1 | grep "renode-$RENODE_VERSION" | grep -c "default") == 0 ]
  then
    echo "Last downloaded Renode should be listed and marked as default"
    exit 1
  fi

  renode-run default $RENODE_VERSION

  if ! [ $(renode-run list 2>&1 | grep "renode-$RENODE_VERSION" | grep -c "default") == 1 ]
  then
    echo "Default command should mark specified version as default"
    exit 1
  fi
}

test_default_output()
{
    local RENODE_VERSION=1.16.1+20260302gita3bdf4a87
    if [[ "$OSTYPE" == "linux"* ]]; then
        local INSTALL_PATH="$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION"
    else
        local INSTALL_PATH="$(cygpath -w "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION")"
    fi

    renode-run download $RENODE_VERSION
    if ! [ $(renode-run default) == "$INSTALL_PATH" ]
    then
        echo "Default command without parameters should print the path to default instance"
        exit 1
    fi
}

test_management=(
  test_list_command_output
  test_filter_clears_non_existent_installations
  test_remove_command
  test_remove_by_path
  test_remove_all_command
  test_remove_does_not_affect_other_versions
  test_default
  test_default_output
)
