#!/bin/sh
# Debug instrumentation (2026-09-04): the scheduled sends hang inside signal-cli
# with no trace, because the daemon logs nothing per request. Shadow the binary
# via PATH so supervisor starts the daemon with --verbose, which also adds
# timestamps to the log.
exec /usr/bin/signal-cli-native --verbose "$@"
