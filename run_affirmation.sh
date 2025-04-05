#!/bin/bash

# Change to the script directory
cd /Users/zach/Desktop/Affirmation_Posting

# Activate virtual environment
source venv/bin/activate

# Run the affirmation video generator
python3 generate_affirmation_video.py

# Deactivate virtual environment
deactivate 