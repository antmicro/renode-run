. $(dirname "$0")/common.sh

RENODE_VERSION="1.16.1"

if [[ "$OSTYPE" == "linux"* ]]; then
  PORTABLE_LATEST="https://builds.renode.io/renode-latest.linux-portable.tar.gz"
  PORTABLE_NUMBERED="https://builds.renode.io/renode-$RENODE_VERSION.linux-portable-dotnet.tar.gz"
  PACKAGE_NAME="renode-portable.tar.gz"
  URI_PACKAGE_PATH="file://${TEST_PLAYGROUND_PATH}/$PACKAGE_NAME"
else
  PORTABLE_LATEST="https://builds.renode.io/renode-latest.windows-portable.zip"
  PORTABLE_NUMBERED="https://builds.renode.io/renode-$RENODE_VERSION.windows-portable-dotnet.zip"
  PACKAGE_NAME="renode-portable.zip"
  URI_PACKAGE_PATH="file:///$(cygpath -m ${TEST_PLAYGROUND_PATH})/$PACKAGE_NAME"
fi


test_install_latest_release()
{
  renode-run install "$PORTABLE_LATEST"
  renode-run -- $PARAMS -e "q"
}

test_install_latest_release_from_file()
{
  mkdir -p "$TEST_PLAYGROUND_PATH"
  curl -o "${TEST_PLAYGROUND_PATH}/$PACKAGE_NAME" "$PORTABLE_LATEST" 
  renode-run install "${TEST_PLAYGROUND_PATH}/$PACKAGE_NAME"
  renode-run -- $PARAMS -e "q"
  assert_artifact_exists "$TEST_PLAYGROUND_PATH" "$PACKAGE_NAME"
}

test_install_latest_release_override_name()
{
  renode-run install "$PORTABLE_LATEST" --version-override custom
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH/renode-custom" "renode"
}

test_install_numbered_release()
{
  renode-run install "$PORTABLE_NUMBERED" --version-override "$RENODE_VERSION"
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION" "renode"
}

test_install_numbered_release_from_file()
{
  mkdir -p "$TEST_PLAYGROUND_PATH"
  curl -o "${TEST_PLAYGROUND_PATH}/$PACKAGE_NAME" "$PORTABLE_NUMBERED"
  renode-run install "${TEST_PLAYGROUND_PATH}/$PACKAGE_NAME" --version-override "$RENODE_VERSION"
  assert_artifact_exists "$DEFAULT_DOTNET_PORTABLE_PATH/renode-$RENODE_VERSION" "renode"
  assert_artifact_exists "$TEST_PLAYGROUND_PATH" "$PACKAGE_NAME"
}

test_install_from_file_by_url()
{
  mkdir -p "$TEST_PLAYGROUND_PATH"
  curl -o "${TEST_PLAYGROUND_PATH}/$PACKAGE_NAME" "$PORTABLE_LATEST"
  renode-run install "$URI_PACKAGE_PATH"
  renode-run -- $PARAMS -e "q"
  assert_artifact_exists "$TEST_PLAYGROUND_PATH" "$PACKAGE_NAME"
}

test_installing_selected_renode_version()
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

test_install=(
  test_install_latest_release
  test_install_latest_release_from_file
  test_install_latest_release_override_name
  test_install_numbered_release
  test_install_numbered_release_from_file
  test_install_from_file_by_url
  test_installing_selected_renode_version
)
