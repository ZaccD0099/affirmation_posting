#!/bin/bash

# Set the working directory to the script's location
cd "$(dirname "$0")"

# Load environment variables
source .env

# Function to log the execution
log_execution() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> cron.log
}

# Function to run the original affirmation script
run_original_script() {
    log_execution "Starting original affirmation script"
    python3 generate_affirmation_video.py
    log_execution "Completed original affirmation script"
}

# Function to run the swipeable post script
run_swipeable_script() {
    log_execution "Starting swipeable post script"
    python3 generate_swipeable_post.py
    log_execution "Completed swipeable post script"
}

# Get the current hour
current_hour=$(date +%H)

# Run scripts based on the current hour
case $current_hour in
    "06")  # 6 AM
        run_original_script
        ;;
    "07")  # 7 AM
        run_swipeable_script
        ;;
    "08")  # 8 AM
        run_original_script
        ;;
    "09")  # 9 AM
        run_swipeable_script
        ;;
    "10")  # 10 AM
        run_swipeable_script
        ;;
esac 