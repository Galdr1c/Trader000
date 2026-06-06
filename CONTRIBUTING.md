# Contributing to SVTR Bot

First off, thank you for considering contributing! 🎉

This project is a community-driven trading bot. Whether you're fixing a typo, improving documentation, adding a new feature, or reporting a bug — every contribution matters.

## 📋 Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## 🚀 How to Contribute

### 1. Reporting Bugs

Found a bug? Please open a [bug report](.github/ISSUE_TEMPLATE/bug_report.md) and include:

- Clear, descriptive title
- Steps to reproduce
- Expected vs actual behavior
- Environment info (OS, Python version, exchange, trading pair)
- Relevant logs (with secrets redacted!)

**Do NOT include** API keys, account numbers, or any sensitive information in bug reports.

### 2. Suggesting Features

Open a [feature request](.github/ISSUE_TEMPLATE/feature_request.md) describing:

- The problem your feature solves
- How it should work
- Any alternatives you considered
- Whether you're willing to implement it

### 3. Submitting Pull Requests

1. **Fork** the repository
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** following the [style guide](#code-style) below
4. **Add tests** for any new functionality
5. **Run the test suite** to ensure nothing broke
6. **Update docs** (README, ARCHITECTURE, CHANGELOG) as needed
7. **Commit** with a clear message:
   ```bash
   git commit -m "feat: add multi-symbol scanner"
   ```
8. **Push** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
9. **Open a Pull Request** with a clear description

## 🛠️ Development Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for integration tests)
- Git

### Local Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/Trader000.git
cd Trader000

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies (including dev tools)
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Edit .env with your test API keys (testnet!)

# Run tests
pytest

# Run linter
ruff check src/ tests/
ruff format src/ tests/
```

### Running Locally

```bash
# Start the bot in development mode
python -m src.main

# In another terminal, check health
curl http://localhost:8000/health
```

## 📐 Code Style

This project uses:

- **[ruff](https://github.com/astral-sh/ruff)** for linting and formatting
- **[black-compatible](https://black.readthedocs.io/)** formatting style
- **Type hints** for all public functions
- **Docstrings** (Google style) for modules, classes, and complex functions
- **Async-first** for I/O operations

### Style Rules

- Maximum line length: **100 characters**
- Use `from __future__ import annotations` in all modules
- Prefer composition over inheritance
- Functions should do one thing well
- Add tests alongside code (not as an afterthought)

### Example

```python
"""Module docstring — describe what this module does."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExampleConfig:
    """Configuration for example functionality."""

    threshold: float = 0.5
    enabled: bool = True


async def calculate_score(data: list[float], config: ExampleConfig) -> float:
    """Calculate a score from input data.

    Args:
        data: List of values to score.
        config: Configuration with threshold and toggle.

    Returns:
        Computed score in range [0.0, 1.0].

    Raises:
        ValueError: If data is empty.
    """
    if not data:
        raise ValueError("data cannot be empty")

    total = sum(data) / len(data)
    return total if total > config.threshold else 0.0
```

## 🧪 Testing Guidelines

- All new code must have tests
- Aim for **80%+ coverage** on new code
- Use **pytest** with the **pytest-asyncio** plugin
- Use **fixtures** for shared setup
- Mock external services (ccxt, Claude API, Telegram)

### Test Naming

- File: `test_<module>.py`
- Function: `test_<function>_<scenario>_<expected_result>`

```python
async def test_calculate_score_empty_data_raises_value_error():
    """Empty data should raise ValueError."""
    with pytest.raises(ValueError, match="data cannot be empty"):
        await calculate_score([], ExampleConfig())
```

## 📝 Commit Message Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `style:` — Code style (formatting, missing semicolons, etc.)
- `refactor:` — Code refactoring (no functional change)
- `perf:` — Performance improvement
- `test:` — Adding or correcting tests
- `chore:` — Build, CI, tooling changes
- `revert:` — Reverting a previous commit

Examples:
```
feat: add multi-symbol scanner
fix: circuit breaker not triggering on weekend
docs: update ARCHITECTURE.md with v1.0 details
test: add integration tests for decision engine
```

## 🔒 Security

If you discover a security vulnerability, **DO NOT** open a public issue. Please see [SECURITY.md](SECURITY.md) for responsible disclosure instructions.

## 📬 Getting Help

- 💬 **Discussions**: Use GitHub Discussions for questions
- 🐛 **Issues**: For bugs and feature requests
- 📖 **Docs**: Check [docs/](docs/) folder first

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

<p align="center">
  <sub>Happy trading! 🚀</sub>
</p>
