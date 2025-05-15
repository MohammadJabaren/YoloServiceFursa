#!/bin/bash
set -e


PROJECT_DIR="$1"
VENV_DIR="$PROJECT_DIR/.venv"
SERVICE_FILE="yoloservice.service"

cd "$PROJECT_DIR"
sudo cp yoloservice.service /etc/systemd/system/

echo "Using project directory: $PROJECT_DIR"

# check Venv
if [ -d "$VENV_DIR" ]; then
    echo " Virtual environment exists."
else
    echo " Creating virtual environment"
    python3 -m venv "$VENV_DIR"
fi

# activate Venv
source "$VENV_DIR/bin/activate"


pip install --upgrade pip
pip install -r torch-requirements.txt
pip install -r requirements.txt

echo " Python torch-requirements & requirements installed."

# restart the service
if [ -f "$SERVICE_FILE" ]; then
    echo "  Installing systemd service"
    sudo systemctl daemon-reload
    sudo systemctl restart "$SERVICE_FILE"
    sudo systemctl enable "$SERVICE_FILE"
    echo " Service reloaded and restarted."
    if ! systemctl is-active --quiet polyservice.service; then
      echo "❌ polybot.service is not running Yet."
      sudo systemctl status polyservice.service --no-pager
      exit 1
    fi
fi