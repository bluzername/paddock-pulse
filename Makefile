.PHONY: setup install lint clean run-images debug-keys help

# Create a virtualenv, install dependencies and copy .env.example to .env
setup:
	./setup.sh

# Install runtime dependencies into the active environment
install:
	pip install -r requirements.txt

# Same checks as CI: ruff (undefined names, syntax) plus byte-compilation
lint:
	ruff check .
	python -m compileall -q .

# Remove generated posts and images
clean:
	rm -rf output/f1_posts_*
	rm -f test_image.png

# Generate images for the most recent prompts (needs OPENAI_API_KEY in .env or the environment)
run-images:
	python run_all.py images

# Print masked API key diagnostics
debug-keys:
	python run_all.py --key-debug

help:
	@echo "Available commands:"
	@echo "  make setup      - Create venv, install dependencies, create .env"
	@echo "  make install    - Install dependencies only"
	@echo "  make lint       - Run ruff check and python -m compileall (same as CI)"
	@echo "  make clean      - Remove generated files"
	@echo "  make run-images - Generate images for existing prompts"
	@echo "  make debug-keys - Print masked API key diagnostics"
