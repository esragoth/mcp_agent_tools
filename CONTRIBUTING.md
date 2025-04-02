# Contributing to MCP Agent Tools

Thank you for your interest in contributing to MCP Agent Tools! We welcome contributions from the community to help make this project better.

## Code of Conduct

Please note that this project is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## How to Contribute

### Reporting Bugs

If you find a bug in the project, please create an issue on GitHub with the following information:

1. A clear, descriptive title
2. A detailed description of the issue
3. Steps to reproduce the problem
4. Expected behavior
5. Actual behavior
6. Environment information (OS, Python version, etc.)
7. Any additional context or screenshots

### Suggesting Enhancements

If you have an idea for a new feature or enhancement, please create an issue with:

1. A clear, descriptive title
2. A detailed description of the proposed feature
3. The rationale for adding this feature
4. Any additional context or examples

### Pull Requests

We welcome pull requests! To contribute code:

1. Fork the repository
2. Create a new branch for your feature or bugfix (`git checkout -b feature/your-feature-name`)
3. Make your changes
4. Add tests for your changes
5. Ensure all tests pass
6. Update documentation as needed
7. Submit a pull request

Please follow these guidelines for pull requests:

- Keep changes focused on a single issue or feature
- Follow the existing code style and conventions
- Include appropriate tests
- Update documentation as needed
- Write clear, descriptive commit messages

## Development Setup

To set up your development environment:

1. Clone the repository
   ```bash
   git clone https://github.com/esragoth/mcp_agent_tools.git
   cd mcp_agent_tools
   ```

2. Create a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -e ".[dev]"
   ```

## Testing

We use pytest for testing. To run tests:

```bash
pytest
```

## Code Style

We follow PEP 8 guidelines for Python code. Please make sure your code follows these standards.

## Documentation

We use docstrings for documentation. Please document your code following the existing style.

## License

By contributing to MCP Agent Tools, you agree that your contributions will be licensed under the project's MIT License. 