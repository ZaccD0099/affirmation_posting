#!/bin/bash

# Update system
echo "Updating system..."
apt-get update
apt-get upgrade -y

# Install required packages
echo "Installing required packages..."
apt-get install -y git python3 ffmpeg python3-pip python3-venv

# Create directory and set permissions
echo "Setting up directory..."
mkdir -p /opt/auto_social
chmod 755 /opt/auto_social

# Clone repository
echo "Cloning repository..."
cd /opt/auto_social
git clone git@github.com:ZaccD0099/affirmation_posting.git .

# Create and activate virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install requirements
echo "Installing Python requirements..."
pip install -r requirements.txt

# Create log directory
echo "Creating log directory..."
mkdir -p /var/log/auto_social
chmod 755 /var/log/auto_social

# Copy .env file
echo "Copying .env file..."
cp /root/.env .

echo "Setup complete!"
