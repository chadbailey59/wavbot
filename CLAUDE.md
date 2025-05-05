# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup & Commands

- **Run locally**: `LOCAL_RUN=1 python bot.py`
- **Environment setup**: Copy `env.example` to `.env` and configure variables
- **Build Docker image**: `./build.sh`
- **Deploy to Pipecat Cloud**: Update `pcc-deploy.toml` as needed and run `pcc deploy`
- **Linting**: `black . && isort . && flake8`

## Code Style Guidelines

- **Imports**: Group standard library, third-party, then local imports with a blank line between groups
- **Formatting**: Follow PEP 8, max line length 100 characters
- **Types**: Use type hints for function parameters and return values
- **Error Handling**: Use try/except blocks with specific exception types, log errors with loguru
- **Logging**: Use loguru for all logging (`logger.debug`, `logger.info`, `logger.error`, etc.)
- **Async Code**: All bot interaction is async, never block the event loop
- **Comments**: Maintain docstrings for classes and functions using Google style
- **Naming**: Use snake_case for variables/functions and PascalCase for classes
