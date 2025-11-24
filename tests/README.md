# NotaryTON Test Suite

Automated testing for the NotaryTON bot using pytest.

## Running Tests Locally

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run All Tests
```bash
pytest tests/ -v
```

### Run Only Unit Tests (Fast)
```bash
pytest tests/ -v -m unit
```

### Run Specific Test File
```bash
pytest tests/test_database.py -v
pytest tests/test_handlers.py -v
pytest tests/test_api.py -v
```

### Run Single Test Function
```bash
pytest tests/test_database.py::test_subscription_check_no_user -v
```

## Test Organization

### `conftest.py`
Shared pytest fixtures:
- `test_db` - Temporary SQLite database
- `temp_file` - Temporary test file
- `sample_user_id` - Sample Telegram user ID
- `sample_contract_address` - Sample TON contract address
- `mock_env` - Mock environment variables

### `test_database.py`
Tests for database operations:
- ✅ User subscription management
- ✅ Notarization logging
- ✅ Referral tracking
- ✅ Payment tracking

### `test_handlers.py`
Tests for bot logic:
- ✅ File hashing (SHA-256)
- ✅ Data hashing
- ✅ Comment formatting
- ✅ TX ID extraction from messages
- ✅ Payment amount validation

### `test_api.py`
Tests for API endpoints:
- ✅ Request/response format validation
- ✅ Batch operation limits
- ✅ Error handling
- ✅ Verification responses

## CI/CD with GitHub Actions

Every push/PR automatically runs all tests via `.github/workflows/test.yml`.

### View Test Results
1. Go to your GitHub repo
2. Click "Actions" tab
3. See test results for each commit

### Test Status Badge
Add to README.md:
```markdown
![Tests](https://github.com/cherishwins/notaryton-bot/actions/workflows/test.yml/badge.svg)
```

## Adding New Tests

1. Create test file: `tests/test_feature.py`
2. Import pytest: `import pytest`
3. Mark tests: `@pytest.mark.unit`
4. Use async: `@pytest.mark.asyncio` for async functions
5. Use fixtures from `conftest.py`

Example:
```python
import pytest

@pytest.mark.unit
@pytest.mark.asyncio
async def test_my_feature(test_db, sample_user_id):
    # Your test code here
    assert True
```

## Test Coverage

Current coverage:
- ✅ Database operations (100%)
- ✅ Hashing functions (100%)
- ✅ API validation (100%)
- ⚠️ TON blockchain integration (mocked)
- ⚠️ Telegram webhook handlers (mocked)

## Troubleshooting

### Import Errors
```bash
# Make sure you're in project root
cd /home/jesse/dev/projects/personal/ton/notaryton-bot

# Install dependencies
pip install -r requirements.txt
```

### Tests Fail
```bash
# Run with more verbose output
pytest tests/ -vv --tb=long

# Run single test to debug
pytest tests/test_database.py::test_subscription_check_no_user -vv
```

### Async Errors
Make sure test functions are marked with:
```python
@pytest.mark.asyncio
async def test_something():
    ...
```
