#!/usr/bin/env bash

set -eu

. $(dirname "$0")/test_download.sh
. $(dirname "$0")/test_install.sh
. $(dirname "$0")/test_running.sh
. $(dirname "$0")/test_management.sh

tests=(
  "${test_download[@]}"
  "${test_install[@]}"
  "${test_running[@]}"
  "${test_management[@]}"
)


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


trap "delete_test_files; exit 1" EXIT
for test in "${tests[@]}"
do
  run_test "$test"
  delete_test_files
done
trap - EXIT
