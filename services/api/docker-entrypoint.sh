#!/bin/sh
set -eu

case "${PROCESS_TYPE:-api}" in
  api)
    exec python -m loose_thread_api
    ;;
  worker)
    exec python -m loose_thread_api.orchestration
    ;;
  *)
    echo "Unknown PROCESS_TYPE: ${PROCESS_TYPE}" >&2
    exit 2
    ;;
esac
