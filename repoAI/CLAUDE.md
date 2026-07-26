# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This repository contains an application with machine learning models and configurations. Based on the recent commit (835111e), the project has been set up with application code, ML models, and configuration files.

## Common Development Commands

### Code Management
- Use git for version control (`git status`, `git diff`, `git log`)
- Make single-purpose commits with descriptive messages
- Review changes before committing

### Code Quality
- Follow existing code patterns and style
- Write unit tests for new utilities
- Write integration tests for workflows
- Ensure code passes existing test suite

## Architecture and Structure

### Code Organization
The project appears to be organized around:
- Application source files
- Machine learning model files
- Configuration files
- Documentation and static assets

### ML Model Pipeline
The architecture suggests a machine learning workflow with:
1. Model storage (PyTorch format)
2. Tokenizer configuration files
3. Application configuration (likely JSON-based)
4. Web interface components (HTML files)

### Technology Stack
- Python for application logic
- PyTorch for machine learning models
- JSON-based configuration system
- Web interface (HTML files)

## Development Workflow

### Setup
1. Install required Python packages
2. Verify model file existence and compatibility
3. Check configuration files for required settings
4. Run tests to ensure baseline functionality

### Testing
- Run full test suite (`pytest`)
- Run individual tests for specific functionality
- Test model loading and prediction capabilities
- Validate configuration files

### Code Changes
1. Make changes to source files
2. Run relevant tests to validate changes
3. Check code quality standards
4. Commit changes with descriptive messages
5. Push to appropriate branch

## Important Files to Examine

### Configuration Files
- JSON configuration files for application settings
- Tokenizer configuration files
- Model format files

### Application Files
- Source code files (examination needed to identify entry points)
- Configuration files for application behavior
- Documentation files (README if exists)

### Model Files
- PyTorch model files
- Tokenizer files
- Special tokens mapping files

## Next Steps for Onboarding

1. **Review README.md** - If exists, it contains project overview and setup instructions
2. **Examine config.json** - Understand configuration structure and requirements
3. **Explore source code** - Find main entry points and application flow
4. **Review model files** - Understand model format and loading mechanisms
5. **Set up environment** - Install dependencies and validate model loading
6. **Run tests** - Understand existing test suite and patterns

## Best Practices

1. **Model Management**: Ensure model files are compatible with application code
2. **Configuration**: Validate JSON syntax and required fields
3. **Testing**: Test both code and model functionality
4. **Code Style**: Follow existing patterns and conventions
5. **Documentation**: Maintain README with current setup instructions

## Common Issues to Watch For

1. **Model Loading Errors** - Check tokenizer, vocab, and config compatibility
2. **Configuration Errors** - Validate JSON syntax and required fields
3. **Path Issues** - Ensure correct file paths for model and config files
4. **Version Compatibility** - Match model versions with code requirements