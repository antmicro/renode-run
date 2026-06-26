DEFAULT_ARTIFACTS_PATH="$HOME/.config/renode"
DEFAULT_DOTNET_PORTABLE_PATH="$DEFAULT_ARTIFACTS_PATH/renode-run.download/dotnet-portable"
TEST_PLAYGROUND_PATH="$(pwd)/test_playground"
TEST_ARTIFACTS_PATH="$TEST_PLAYGROUND_PATH/test_artifacts"
TEST_DOWNLOAD_PATH="$TEST_PLAYGROUND_PATH/test_download"
TEST_VENV_PATH="$TEST_PLAYGROUND_PATH/test_venv"

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
