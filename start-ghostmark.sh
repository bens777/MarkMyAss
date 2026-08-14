#!/usr/bin/env bash
# Deprecated name kept for compatibility -- the project is now MarkMyAss.
# This wrapper just runs start-markmyass.sh.
exec "$(dirname "$0")/start-markmyass.sh" "$@"
