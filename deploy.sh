#!/bin/bash
# ARC Deploy Script - Push local changes to EC2
# Usage: ./deploy.sh [message]
#
# This script will:
# 1. Commit your local changes (if any)
# 2. Push to GitHub (for version control)
# 3. SCP code files directly to EC2 (works in airgapped environments)
# 4. Restart the ARC service
#
# Note: This uses SCP instead of git pull on EC2 to support
# airgapped/GovCloud environments without internet access.

set -e

# Configuration
EC2_HOST="3.238.136.56"
EC2_USER="ec2-user"
SSH_KEY="arc-app-key.pem"
APP_DIR="/opt/arc"
REPO_URL="https://github.com/saulpingerman/arc.git"

# Files/directories to deploy (code only - venv stays on server)
ROOT_FILES="app.py llm_clients.py requirements.txt local_config.py"
ARC_PACKAGE="arc"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory (where this script lives)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${GREEN}=== ARC Deployment Script ===${NC}"
echo ""

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}ERROR: SSH key not found at $SSH_KEY${NC}"
    exit 1
fi

# Step 1: Check for local changes
echo -e "${YELLOW}Step 1: Checking local changes...${NC}"
if [ -n "$(git status --porcelain)" ]; then
    echo "Local changes detected:"
    git status --short
    echo ""

    # Get commit message
    if [ -n "$1" ]; then
        COMMIT_MSG="$1"
    else
        read -p "Enter commit message (or press Enter for default): " COMMIT_MSG
        if [ -z "$COMMIT_MSG" ]; then
            COMMIT_MSG="Update ARC application"
        fi
    fi

    echo "Committing changes..."
    git add -A
    git commit -m "$COMMIT_MSG"
else
    echo "No local changes to commit."
fi

# Step 2: Push to GitHub
echo ""
echo -e "${YELLOW}Step 2: Pushing to GitHub...${NC}"
git push origin main 2>/dev/null || git push origin master 2>/dev/null || {
    echo -e "${RED}Failed to push. Make sure you've set up the remote.${NC}"
    echo "Run: git remote add origin https://github.com/saulpingerman/arc.git"
    exit 1
}
echo -e "${GREEN}Pushed to GitHub successfully.${NC}"

# Step 3: Deploy to EC2 via SCP (works in airgapped environments)
echo ""
echo -e "${YELLOW}Step 3: Deploying code to EC2 ($EC2_HOST)...${NC}"

# Copy root-level files
for file in $ROOT_FILES; do
    if [ -f "$file" ]; then
        echo "  Uploading $file..."
        scp -i "$SSH_KEY" -o StrictHostKeyChecking=no "$file" "$EC2_USER@$EC2_HOST:/tmp/"
    fi
done

# Copy the arc package directory (recursively)
echo "  Uploading arc/ package..."
scp -r -i "$SSH_KEY" -o StrictHostKeyChecking=no "$ARC_PACKAGE" "$EC2_USER@$EC2_HOST:/tmp/"

# Move files to app directory and restart service
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$EC2_USER@$EC2_HOST" << 'ENDSSH'
set -e

APP_DIR="/opt/arc"

echo "Moving files to app directory..."

# Move root-level files
for file in app.py llm_clients.py requirements.txt local_config.py; do
    if [ -f "/tmp/$file" ]; then
        sudo mv "/tmp/$file" "$APP_DIR/"
        sudo chown arc:arc "$APP_DIR/$file"
    fi
done

# Remove old arc package and move new one
if [ -d "/tmp/arc" ]; then
    sudo rm -rf "$APP_DIR/arc"
    sudo mv "/tmp/arc" "$APP_DIR/"
    sudo chown -R arc:arc "$APP_DIR/arc"
fi

# Remove old arc.py and arc_web.py if they exist
sudo rm -f "$APP_DIR/arc.py" "$APP_DIR/arc_web.py"

# Update systemd service to use app.py (in case it still references arc.py)
if grep -q "arc.py" /etc/systemd/system/arc.service; then
    echo "Updating systemd service to use app.py..."
    sudo sed -i 's/arc.py/app.py/g' /etc/systemd/system/arc.service
    sudo systemctl daemon-reload
fi

echo "Restarting ARC service..."
sudo systemctl restart arc

echo "Waiting for service to start..."
sleep 3

if sudo systemctl is-active --quiet arc; then
    echo "ARC service is running!"
else
    echo "WARNING: Service may not be running. Check logs with: sudo journalctl -u arc -f"
fi
ENDSSH

echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Access the app at: http://$EC2_HOST:8501"
echo ""
echo "Useful commands:"
echo "  Check status:  ssh -i $SSH_KEY $EC2_USER@$EC2_HOST 'sudo systemctl status arc'"
echo "  View logs:     ssh -i $SSH_KEY $EC2_USER@$EC2_HOST 'sudo journalctl -u arc -f'"
