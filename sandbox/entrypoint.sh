#!/bin/sh

# This script serves as the entry point for the Docker container.
# It can be used to set up the environment and start the application.

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

# Run the main application
python3 backend/main.py