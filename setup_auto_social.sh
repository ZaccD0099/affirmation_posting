#!/bin/bash
apt-get update && apt-get install -y python3 python3-pip python3-venv ffmpeg git
mkdir -p /opt/auto_social && cd /opt/auto_social
git clone https://github.com/ZaccD0099/affirmation_posting.git .
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
mkdir -p /var/log/auto_social
