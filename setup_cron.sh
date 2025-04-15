#!/bin/bash

# Remove any existing cron jobs
crontab -r

# Get the full path to the Python executable in the virtual environment
PYTHON_PATH="/Users/zach/Desktop/Affirmation_Posting/venv/bin/python3"

# Add new cron jobs with the specified schedule
(crontab -l 2>/dev/null; echo "# Dark Sunset 5sec videos at 6pm, 8pm, 10pm
0 18,20,22 * * * cd /Users/zach/Desktop/Affirmation_Posting && $PYTHON_PATH generate_darkSunset_5sec.py >> cron.log 2>&1

# Dark Sunset 12sec videos at 7pm, 9pm
0 19,21 * * * cd /Users/zach/Desktop/Affirmation_Posting && $PYTHON_PATH generate_darkSunset_12sec.py >> cron.log 2>&1

# Original affirmations at 7am, 9am
0 7,9 * * * cd /Users/zach/Desktop/Affirmation_Posting && $PYTHON_PATH generate_original.py >> cron.log 2>&1

# Swipeable posts at 6am, 8am, 10am
0 6,8,10 * * * cd /Users/zach/Desktop/Affirmation_Posting && $PYTHON_PATH generate_swipeable_post.py >> cron.log 2>&1") | crontab -

echo "Cron jobs have been set up with the following schedule:"
echo "- Dark Sunset 5sec: 6pm, 8pm, 10pm"
echo "- Dark Sunset 12sec: 7pm, 9pm"
echo "- Original affirmations: 7am, 9am"
echo "- Swipeable posts: 6am, 8am, 10am"
