#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

for year in 2022 2023 2024 2025; do
    echo "=============================================="
    echo ">>> Running scraper for academic year ${year}/$((year + 1))"
    echo "=============================================="
    python -m src.main --year "${year}"
done

echo "All years completed."
