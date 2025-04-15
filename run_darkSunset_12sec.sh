#!/bin/bash

# Set environment variables
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export HOME="/Users/zach"
export SHELL="/bin/bash"

# Change to the script directory
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Run the script
python3 generate_darkSunset_12sec.py

# Deactivate virtual environment
deactivate 