#!/bin/bash

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "GitHub CLI (gh) is not installed. Please install it first:"
    echo "https://cli.github.com/manual/installation"
    exit 1
fi

# Check if user is logged in
if ! gh auth status &> /dev/null; then
    echo "Please login to GitHub CLI first:"
    echo "gh auth login"
    exit 1
fi

# Function to set a secret
set_secret() {
    local secret_name=$1
    local secret_value=$2
    
    echo "Setting $secret_name..."
    gh secret set $secret_name -b "$secret_value"
    if [ $? -eq 0 ]; then
        echo "✅ Successfully set $secret_name"
    else
        echo "❌ Failed to set $secret_name"
    fi
}

# Get secret values from user
echo "Please enter your secret values:"
read -p "OpenAI API Key: " openai_key
read -p "Facebook Access Token: " facebook_token
read -p "AWS Access Key ID: " aws_key_id
read -p "AWS Secret Access Key: " aws_secret_key
read -p "S3 Bucket Name: " s3_bucket
read -p "AWS Region (e.g., us-east-1): " aws_region

# Set secrets
set_secret "OPENAI_API_KEY" "$openai_key"
set_secret "FACEBOOK_ACCESS_TOKEN" "$facebook_token"
set_secret "AWS_ACCESS_KEY_ID" "$aws_key_id"
set_secret "AWS_SECRET_ACCESS_KEY" "$aws_secret_key"
set_secret "S3_BUCKET_NAME" "$s3_bucket"
set_secret "AWS_REGION" "$aws_region"

echo "🎉 All secrets have been set!" 