# Contributing to MiniMax Provider Verifier

Thank you for your interest in contributing! We welcome contributions from the community.

## How to Contribute

1. **Fork the Repository**
   - Click the "Fork" button at the top right of this repository

2. **Clone Your Fork**
   ```bash
   git clone https://github.com/MiniMax-AI/MiniMax-Provider-Verifier.git
   cd MiniMax-Provider-Verifier
   ```

3. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. **Make Your Changes**
   - Write clean, readable code
   - Follow the existing code style
   - Add tests if applicable
   - Update documentation as needed

5. **Test Your Changes**
   ```bash
   # Install dependencies
   uv sync
   
   # Run your tests
   python verify.py sample.jsonl --model "test-model" --base-url "https://api.example.com/v1"
   ```

6. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "Add: your descriptive commit message"
   ```

7. **Push to Your Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

8. **Open a Pull Request**
   - Go to the original repository
   - Click "New Pull Request"
   - Select your fork and branch
   - Describe your changes in detail

## Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings for classes and functions
- Keep functions focused and concise

## Adding New Validators

To add a new validator:

1. Create a new file in the `validator/` directory
2. Inherit from `BaseValidator`
3. Implement the required methods
4. Add your validator to `validator/__init__.py`
5. Register it in `VALIDATOR_REGISTRY` in `verify.py`
6. Update the README documentation


## Reporting Issues

- Use the GitHub issue tracker
- Clearly describe the issue, including steps to reproduce
- Include relevant logs and error messages
- Specify your environment (OS, Python version, etc.)

## Questions?

Feel free to open an issue for questions or discussions.

Thank you for contributing! 🎉

