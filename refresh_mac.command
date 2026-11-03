#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
python3 -m dental_analytics.clean_and_refresh || exit 1
python3 -m dental_analytics.build_dashboard_data || exit 1
echo "Local data and dashboard refreshed. Website publication is separate."
