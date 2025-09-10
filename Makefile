.PHONY: setup install clean test run-images check-api

# Setup everything
setup:
	./setup.sh

# Install dependencies only
install:
	pip install -r requirements.txt

# Clean generated files
clean:
	rm -rf output/f1_posts_*
	rm -f test_image.png

# Run quick test of OpenAI integration
test:
	@echo "Running simple OpenAI DALL-E test..."
	@echo "Please provide your OpenAI API key when prompted."
	@read -p "OpenAI API key: " key; \
	export OPENAI_API_KEY="$$key"; \
	python simple_test.py --api-key "$$key"

# Generate images for existing prompts
run-images:
	@echo "Running image generation with OpenAI DALL-E..."
	@echo "Please provide your OpenAI API key when prompted."
	@read -p "OpenAI API key: " key; \
	export OPENAI_API_KEY="$$key"; \
	python run_all.py images

# Check OpenAI API key
check-api:
	@echo "Checking OpenAI API key..."
	@echo "Please provide your OpenAI API key when prompted."
	@read -p "OpenAI API key: " key; \
	export OPENAI_API_KEY="$$key"; \
	python check_openai_api.py

# Check using key-debug mode
debug-keys:
	@echo "Running key debug mode..."
	@echo "Please provide your OpenAI API key when prompted."
	@read -p "OpenAI API key: " key; \
	export OPENAI_API_KEY="$$key"; \
	python run_all.py --key-debug

# Help
help:
	@echo "Available commands:"
	@echo "  make setup      - Set up the project (create venv, install dependencies)"
	@echo "  make install    - Install dependencies only"
	@echo "  make clean      - Remove generated files"
	@echo "  make test       - Run a simple test of OpenAI DALL-E"
	@echo "  make run-images - Generate images for existing prompts"
	@echo "  make check-api  - Check if OpenAI API key is valid"
	@echo "  make debug-keys - Debug API key issues" 