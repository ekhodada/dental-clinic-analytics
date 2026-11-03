#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
python3 code/clean_and_refresh.py || exit 1
python3 code/build_dashboard_data.py || exit 1
echo "Local data and dashboard refreshed. Website publication is separate."
