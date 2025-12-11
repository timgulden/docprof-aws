# Testing Guide

This directory contains tests at three levels: unit, integration, and E2E.

## Test Structure

```
tests/
├── unit/              # Unit tests (fast, local, no AWS)
│   ├── test_chat_logic.py
│   └── test_effects_adapter.py
├── integration/      # Integration tests (moderate speed, requires AWS)
│   └── test_lambda_imports.py
├── e2e/              # End-to-end tests (slow, full AWS stack)
│   └── test_chat_flow.py
└── conftest.py       # Shared pytest fixtures
```

## Running Tests

### Unit Tests (Fast - Run Often)

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_chat_logic.py -v

# Run with coverage
pytest tests/unit/ --cov=src/lambda/shared/logic --cov-report=html
```

**When to run:** On every code change, in pre-commit hooks, in CI/CD

### Integration Tests (Moderate Speed)

```bash
# Run integration tests (requires AWS credentials)
pytest tests/integration/ -v -m integration

# Run specific test
pytest tests/integration/test_lambda_imports.py -v
```

**When to run:** Before deployment, in CI/CD after infrastructure changes

### E2E Tests (Slow - Run Before Releases)

```bash
# Run E2E tests (requires full AWS stack)
pytest tests/e2e/ -v -m e2e

# Run specific test
pytest tests/e2e/test_chat_flow.py -v
```

**When to run:** Before releases, in staging environment, nightly

## Test Markers

Tests are marked with pytest markers:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests  
- `@pytest.mark.e2e` - End-to-end tests

Run specific types:

```bash
pytest -m unit          # Only unit tests
pytest -m integration  # Only integration tests
pytest -m e2e          # Only E2E tests
pytest -m "not e2e"    # Skip E2E tests
```

## Prerequisites

### Unit Tests
- Python 3.11+
- pytest
- No AWS credentials needed

### Integration Tests
- AWS credentials configured
- Infrastructure deployed (`terraform apply`)
- Lambda functions deployed

### E2E Tests
- Full AWS stack deployed
- API Gateway accessible
- Books ingested in Aurora (for some tests)

## CI/CD Integration

### GitHub Actions Example

```yaml
# Run unit tests on every push
- name: Unit Tests
  run: pytest tests/unit/ -v

# Run integration tests on PR
- name: Integration Tests
  run: pytest tests/integration/ -v -m integration
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}

# Run E2E tests before release
- name: E2E Tests
  run: pytest tests/e2e/ -v -m e2e
  if: github.event_name == 'release'
```

## Test Coverage Goals

- **Unit Tests**: >80% coverage of logic functions
- **Integration Tests**: Cover all Lambda functions
- **E2E Tests**: Cover critical user flows

## Best Practices

1. **Write unit tests first** - Fast feedback, catch bugs early
2. **Add integration tests** - Verify deployment works
3. **Add E2E tests** - Verify user flows work
4. **Run unit tests often** - On every commit
5. **Run integration tests before deployment**
6. **Run E2E tests before releases**

## Troubleshooting

### Unit Tests Fail

- Check imports use `shared.*` pattern
- Verify logic functions are pure (no side effects)
- Mock dependencies if needed

### Integration Tests Fail

- Verify AWS credentials are configured
- Check infrastructure is deployed
- Verify Lambda functions exist

### E2E Tests Fail

- Check API Gateway is accessible
- Verify DynamoDB table exists
- Check Aurora is accessible
- Verify books are ingested (for content tests)
