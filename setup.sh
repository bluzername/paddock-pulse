#!/bin/bash
# PaddockPulse Setup Script (MacOS)

echo "Setting up PaddockPulse for MacOS..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists, if not create from example
if [ ! -f ".env" ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "Please edit .env file to add your API keys."
fi

# Create output and data directories if they don't exist
mkdir -p output data

echo "Setup complete! PaddockPulse is ready to use."
echo ""
echo "To generate images, use one of the following commands:"
echo "  python run_all.py images --openai-api-key YOUR_OPENAI_API_KEY"
echo "  python run_all.py full-with-images --openai-api-key YOUR_OPENAI_API_KEY"
echo ""
echo "To test the image generation with a sample post:"
echo "  python example_images.py --api-key YOUR_OPENAI_API_KEY" 