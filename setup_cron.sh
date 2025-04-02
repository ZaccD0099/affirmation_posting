#!/bin/bash
(crontab -l 2>/dev/null | grep -v "run_affirmation.py"; echo "0 12,14,16,18,20,22,0,2,4,6 * * * cd /opt/auto_social && source venv/bin/activate && python3 generate_affirmation_video.py >> /var/log/auto_social/cron.log 2>&1") | crontab -
