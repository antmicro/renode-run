DEFAULT_ARTIFACTS_PATH="$HOME/.config/renode"
DEFAULT_DOTNET_PORTABLE_PATH="$DEFAULT_ARTIFACTS_PATH/renode-run.download/dotnet-portable"
TEST_PLAYGROUND_PATH="$(pwd)/test_playground"
TEST_ARTIFACTS_PATH="$TEST_PLAYGROUND_PATH/test_artifacts"
TEST_DOWNLOAD_PATH="$TEST_PLAYGROUND_PATH/test_download"
TEST_VENV_PATH="$TEST_PLAYGROUND_PATH/test_venv"
PACKAGE_CACHE_PATH="$(pwd)/package_cache"

ROBOT_TEST="tests/example.robot"
ROBOT_TEST_ARTIFACTS="log.html report.html robot_output.xml"

PARAMS=""
PACKAGE_SUFIX=""
case "$OSTYPE" in
  linux*)
    PARAMS="--console --disable-xwt --plain"
    PACKAGE_SUFIX=".linux-portable.tar.gz"
    ;;
  *)
    PARAMS="--disable-xwt --plain"
    PACKAGE_SUFIX=".windows-portable.zip"
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

cache_renode_package()
{
  mkdir -p "$PACKAGE_CACHE_PATH"
  local PACKAGE_NAME="renode-${1}${PACKAGE_SUFIX}"

  if [ ! -f "${PACKAGE_CACHE_PATH}/${PACKAGE_NAME}" ]; then
    echo "Downloading ${PACKAGE_NAME} from builds.renode.io:" 1>&2
    curl "https://builds.renode.io/${PACKAGE_NAME}" -o "${PACKAGE_CACHE_PATH}/${PACKAGE_NAME}"
    echo "Saved downloaded package as: ${PACKAGE_CACHE_PATH}/${PACKAGE_NAME}" 1>&2
  else
    echo "Package ${PACKAGE_NAME} already in cache." 1>&2
  fi

  echo "${PACKAGE_CACHE_PATH}/${PACKAGE_NAME}"
}

clear_package_cache()
{
  rm -rf "${PACKAGE_CACHE_PATH}"
}
