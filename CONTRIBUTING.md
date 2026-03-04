# Contributing to Aegis

Thanks for your interest in contributing to Aegis! Here's how to get started.

## Development Setup

1. **Clone the repo**

   ```bash
   git clone https://github.com/edycutjong/aegis.git
   cd aegis
   ```

2. **Backend**

   ```bash
   cd backend
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env  # Fill in your API keys
   ```

3. **Frontend**

   ```bash
   cd frontend
   npm install
   ```

4. **Run everything**

   ```bash
   docker compose up --build
   ```

## Running Tests

```bash
# Backend (100% coverage required)
cd backend
python -m pytest tests/ --cov=app --cov-fail-under=100

# Frontend
cd frontend
npm run test
npx vitest run --coverage
```

## Code Quality

- **Backend**: Code is linted with [Ruff](https://docs.astral.sh/ruff/). Run `ruff check .` before committing.
- **Frontend**: Code is linted with ESLint. Run `npm run lint` before committing.

## Pull Request Process

1. Fork the repository and create a feature branch from `main`
2. Make your changes with clear, descriptive commits
3. Ensure all tests pass and coverage remains at 100%
4. Run linting (`ruff check .` and `npm run lint`)
5. Open a PR with a clear description of the changes

## Reporting Issues

Open an issue with:
- A clear title and description
- Steps to reproduce (if applicable)
- Expected vs actual behavior
- Screenshots or logs (if helpful)

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
