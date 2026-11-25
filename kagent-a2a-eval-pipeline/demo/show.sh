#!/usr/bin/env bash
# Code tour for the live demo: prints the real YAML or Python behind a scene, with the line to say. See demo/show.py.
#   demo/show.sh --list | <scene> [--step N] [--pause] | --markdown
exec python3 "$(cd "$(dirname "$0")" && pwd)/show.py" "$@"
