# Autonomous RPA & DevOps Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the personal Robot Framework Amazon Wishlist project into an unattended, resilient, 24/7 autonomous platform featuring SQLite price persistence, decoupled Telegram HITL alerts, deterministic error classification with lightweight AI triage, and an end-to-end DevOps CI/CD pipeline.

**Architecture:** Layered modular architecture separating DOM scraping from state persistence. The Robot Framework tasks run headless in read-only mode to extract prices, persisting records and detecting price drops via an agnostic `PriceRepository`, while a Telegram notification service alerts the user of bargains and handles decoupled 2FA re-auth commands. Unhandled exceptions are categorized deterministically with an optional Gemini Flash sidecar, and changes are validated through GitHub Actions CI/CD workflows and containerized via Docker.

**Tech Stack:** Python 3.10+, Robot Framework, SeleniumLibrary / Playwright (Browser), SQLite3 / Turso, `python-telegram-bot` or direct Telegram Bot API requests, `robocop`, `robotidy`, `pytest`, Docker, GitHub Actions.

**Spec:** [docs/superpowers/specs/2026-10-26-autonomous-rpa-platform-design.md](file:///Users/jai/DevEnv/Automation/robotFramework/robotFramework/docs/superpowers/specs/2026-10-26-autonomous-rpa-platform-design.md)

## Global Constraints
- Target completion milestone: within 2 months (before year end).
- Target runtime environment: unattended 24/7 on remote runners, cheap VPS, or local Mini-PC with zero continuous high cloud cost.
- Browser mode: strictly headless (`--headless=new`) for container and remote runner compatibility.
- Interaction model: Telegram Bot as primary notification and HITL channel; decoupled asynchronous 2FA (`STATUS_NEEDS_2FA`), never blocking a headless runner in real time.
- Scraping approach: read-only extraction of wishlist items and prices; no writing to Amazon's web notes DOM.
- AI & MCP topology: routine execution is 100% deterministic code; AI acts strictly as an offline triage sidecar for unhandled error logs using structured JSON responses.

## Review Focus
- Database schema migration and concurrent SQLite writes from scheduled runners without locking errors.
- Wishlist items with no price (out of stock, coupon-only, or third-party sellers without standard buy box).
- Amazon bot-detection landing pages (CAPTCHA, robot check, 2FA challenge) correctly parsed as `STATUS_NEEDS_2FA` or `RATE_LIMITED` without throwing unhandled WebDriver exceptions.
- Telegram message delivery rate limits and HTML formatting escaping for product titles containing special characters (`<`, `>`, `&`).
- CI pipeline running clean in headless Ubuntu GitHub Actions runners without requiring real Amazon credentials.

---

### Task 1: SQLite Price Persistence Layer (`PriceRepository`)

**Files:**
- Create: `libraries/PriceRepository.py`
- Create: `tests/test_price_repository.py`

**Interfaces:**
- Consumes: Product records with fields `asin`, `title`, `url`, `current_price`, `currency`.
- Produces: `record_price(item: Dict) -> Dict` returning `{is_drop: bool, previous_price: float, current_price: float, lowest_price: float, drop_percentage: float}` and `get_tracked_items() -> List[Dict]`.

- [ ] **Step 1: Write the failing test for `PriceRepository`**

```python
# tests/test_price_repository.py
import os
import pytest
from libraries.PriceRepository import PriceRepository

@pytest.fixture
def repo(tmp_path):
    db_file = tmp_path / "test_prices.db"
    return PriceRepository(db_path=str(db_file))

def test_initial_price_insert_and_lowest_tracking(repo):
    item = {
        "asin": "B08N5WRWNW",
        "title": "Sample Item",
        "url": "https://amazon.com.mx/dp/B08N5WRWNW",
        "current_price": 500.00,
        "currency": "MXN"
    }
    result = repo.record_price(item)
    assert result["is_drop"] is False
    assert result["lowest_price"] == 500.00
    assert result["current_price"] == 500.00

def test_price_drop_detection(repo):
    item_initial = {
        "asin": "B08N5WRWNW",
        "title": "Sample Item",
        "url": "https://amazon.com.mx/dp/B08N5WRWNW",
        "current_price": 500.00,
        "currency": "MXN"
    }
    repo.record_price(item_initial)

    item_discounted = {
        "asin": "B08N5WRWNW",
        "title": "Sample Item",
        "url": "https://amazon.com.mx/dp/B08N5WRWNW",
        "current_price": 400.00,
        "currency": "MXN"
    }
    result = repo.record_price(item_discounted)
    assert result["is_drop"] is True
    assert result["previous_price"] == 500.00
    assert result["current_price"] == 400.00
    assert result["lowest_price"] == 400.00
    assert result["drop_percentage"] == 20.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_price_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'libraries.PriceRepository'`

- [ ] **Step 3: Implement `PriceRepository` in `libraries/PriceRepository.py`**

Implement SQLite initialization, table creation (`products` and `price_history`), `record_price`, and `get_tracked_items` using `sqlite3` with thread-safe connection context.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_price_repository.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libraries/PriceRepository.py tests/test_price_repository.py
git commit -m "feat(storage): implement SQLite PriceRepository with drop detection"
```

---

### Task 2: Read-Only Scraper Refactoring & Status Signaling

**Files:**
- Modify: `keywords/amazon/wishlist_price_processing.resource`
- Modify: `tasks/amazon/wishlist_amazon_price_updater.robot`
- Create: `tests/test_price_processing_signals.py`

**Interfaces:**
- Consumes: `PriceRepository.record_price`
- Produces: Execution status codes: `OK_UPDATED`, `PRICE_UNCHANGED`, `STATUS_NEEDS_2FA`, `RATE_LIMITED`.

- [ ] **Step 1: Write unit test for status code resolution and price parsing**

```python
# tests/test_price_processing_signals.py
from libraries.PriceTracker import PriceTracker

def test_status_code_definitions():
    STATUS_CODES = {"OK_UPDATED", "PRICE_UNCHANGED", "STATUS_NEEDS_2FA", "RATE_LIMITED", "ERROR_SELECTOR"}
    assert "STATUS_NEEDS_2FA" in STATUS_CODES

def test_extract_asin_and_normalize():
    tracker = PriceTracker()
    asin = tracker.extract_asin_from_url("https://www.amazon.com.mx/dp/B08N5WRWNW?psc=1")
    assert asin == "B08N5WRWNW"
    price_data = tracker.normalize_amazon_price("$ 1,299.50 MXN")
    assert price_data["price"] == "1299.50"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_price_processing_signals.py -v`
Expected: PASS

- [ ] **Step 3: Refactor `wishlist_price_processing.resource` and `wishlist_amazon_price_updater.robot`**

- Remove keywords that click `WLNOTES_Comment` or submit note modals on Amazon's DOM.
- Add direct integration with `PriceRepository.record_price` for each item found on the list.
- Return structured summary dictionary `{ "total_items": int, "drops_found": list, "status": str }`.
- In `Suite Teardown`, output the final status code cleanly to `results/status.json`.

- [ ] **Step 4: Verify Robot Framework syntax and dry-run with robocop**

Run: `python3 -m robocop keywords/amazon/wishlist_price_processing.resource tasks/amazon/wishlist_amazon_price_updater.robot`
Expected: 0 errors (clean linting or only informational hints).

- [ ] **Step 5: Commit**

```bash
git add keywords/amazon/wishlist_price_processing.resource tasks/amazon/wishlist_amazon_price_updater.robot tests/test_price_processing_signals.py
git commit -m "refactor(amazon): switch wishlist scraper to read-only mode with structured status codes"
```

---

### Task 3: Deterministic Error Classifier & Offline AI Triage Sidecar

**Files:**
- Create: `libraries/ErrorClassifier.py`
- Create: `tests/test_error_classifier.py`

**Interfaces:**
- Consumes: Exception message, page title, page source snippet, and log string.
- Produces: `classify_error(error_message: str, page_title: str) -> Dict` returning `{ "category": str, "action_code": str, "description": str }`.

- [ ] **Step 1: Write failing test for `ErrorClassifier`**

```python
# tests/test_error_classifier.py
import pytest
from libraries.ErrorClassifier import ErrorClassifier

def test_classify_2fa_challenge():
    classifier = ErrorClassifier()
    result = classifier.classify_error(
        error_message="Verification required",
        page_title="Amazon Sign-In Approval"
    )
    assert result["action_code"] == "STATUS_NEEDS_2FA"
    assert result["category"] == "AUTH_CHALLENGE"

def test_classify_captcha_challenge():
    classifier = ErrorClassifier()
    result = classifier.classify_error(
        error_message="Enter the characters you see below",
        page_title="Robot Check"
    )
    assert result["action_code"] == "RATE_LIMITED"
    assert result["category"] == "CAPTCHA"

def test_classify_generic_selector_failure():
    classifier = ErrorClassifier()
    result = classifier.classify_error(
        error_message="Element with locator '//div[@id=\"wl-item-list\"]' not found after 10s",
        page_title="Amazon.com.mx: Mi Lista de Deseos"
    )
    assert result["action_code"] == "ERROR_SELECTOR"
    assert result["category"] == "DOM_DRIFT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_error_classifier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'libraries.ErrorClassifier'`

- [ ] **Step 3: Implement `ErrorClassifier` in `libraries/ErrorClassifier.py`**

- Provide deterministic rule-based regex matching for fast, 0-token classification of common Amazon error states (`Robot Check`, `Sign-In Approval`, `Captcha`, `Element not found`).
- Include an optional method `triage_with_llm(log_text: str) -> Dict` that calls Gemini Flash with a JSON schema when an unknown error occurs.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_error_classifier.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libraries/ErrorClassifier.py tests/test_error_classifier.py
git commit -m "feat(triage): create ErrorClassifier with deterministic action mapping and AI sidecar"
```

---

### Task 4: Telegram Notifier & Interactive Bot Service

**Files:**
- Create: `libraries/TelegramNotifier.py`
- Create: `scripts/telegram_bot_service.py`
- Create: `tests/test_telegram_notifier.py`

**Interfaces:**
- Consumes: Price drop dicts, status codes, and configuration tokens (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).
- Produces: `format_price_drop_message(item: Dict) -> str`, `send_alert(item: Dict) -> bool`, and Telegram commands (`/run`, `/status`, `/login`).

- [ ] **Step 1: Write failing test for message formatting and payload generation**

```python
# tests/test_telegram_notifier.py
from libraries.TelegramNotifier import TelegramNotifier

def test_format_price_drop_message():
    notifier = TelegramNotifier(bot_token="dummy", chat_id="12345")
    item = {
        "title": "PlayStation 5 Console",
        "current_price": 9999.00,
        "previous_price": 11999.00,
        "lowest_price": 9999.00,
        "drop_percentage": 16.67,
        "currency": "MXN",
        "url": "https://amazon.com.mx/dp/B08N5WRWNW"
    }
    msg = notifier.format_price_drop_message(item)
    assert "🔥 *¡Bajada de precio detectada!*" in msg
    assert "PlayStation 5 Console" in msg
    assert "$9,999.00 MXN" in msg
    assert "16.7%" in msg
    assert "https://amazon.com.mx/dp/B08N5WRWNW" in msg

def test_format_needs_2fa_alert():
    notifier = TelegramNotifier(bot_token="dummy", chat_id="12345")
    msg = notifier.format_needs_2fa_alert()
    assert "/login" in msg
    assert "2FA" in msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_telegram_notifier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'libraries.TelegramNotifier'`

- [ ] **Step 3: Implement `TelegramNotifier` and `telegram_bot_service.py`**

- Implement `TelegramNotifier` using Python `urllib` or `requests` for zero-dependency HTTP calls to `api.telegram.org`.
- Add escape utility for MarkdownV2 / HTML special characters.
- Implement `scripts/telegram_bot_service.py` with handlers for `/status`, `/run`, and decoupled `/login` notification.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_telegram_notifier.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libraries/TelegramNotifier.py scripts/telegram_bot_service.py tests/test_telegram_notifier.py
git commit -m "feat(telegram): implement price drop notifier and bot daemon service"
```

---

### Task 5: DevOps CI Pipeline (GitHub Actions)

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `pyproject.toml` (or update `requirements.txt` with test & lint tools)

**Interfaces:**
- Consumes: Push and pull request events to any branch.
- Produces: GitHub Actions check runs verifying code style, types, and unit tests.

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

Configure GitHub Actions workflow:
1. Matrix setup with Python 3.10 and 3.11.
2. Install dependencies: `pip install -r requirements.txt pytest robocop robotidy`.
3. Step: `pytest tests/ -v`.
4. Step: `robotidy --check tasks/ keywords/`.
5. Step: `robocop tasks/ keywords/`.

- [ ] **Step 2: Verify lint and test commands locally**

Run:
```bash
pytest tests/ -v
robocop tasks/ keywords/ || true
```
Expected: All unit tests pass, linters exit with code 0 or acceptable warnings.

- [ ] **Step 3: Commit CI configuration**

```bash
git add .github/workflows/ci.yml requirements.txt
git commit -m "ci: add GitHub Actions workflow for linting, robot validation, and unit tests"
```

---

### Task 6: Headless Containerization & CD Pipeline

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `.github/workflows/cd.yml`

**Interfaces:**
- Consumes: Merges into `main` branch.
- Produces: Docker container image capable of running headless Chromium and Robot Framework suites.

- [ ] **Step 1: Create `Dockerfile` with headless Chromium support**

Use a slim Debian Python base (e.g., `python:3.11-slim`), install `chromium`, `chromium-driver`, and project dependencies. Add non-root user `appuser` and set entrypoint for running the automation tasks or daemon.

- [ ] **Step 2: Create `.dockerignore`**

Exclude `.venv`, `.git`, `.robocop_cache`, `results/`, `output.xml`, `log.html`, `report.html`, and temporary files.

- [ ] **Step 3: Create `.github/workflows/cd.yml`**

Configure workflow triggered on push to `main`:
1. Check out code.
2. Build Docker image: `docker build -t rpa-robot-framework:latest .`.
3. Run container smoke check: `docker run --rm rpa-robot-framework:latest python -c "import robot; print('Robot Framework installed')"`

- [ ] **Step 4: Commit Docker & CD configurations**

```bash
git add Dockerfile .dockerignore .github/workflows/cd.yml
git commit -m "cd: add Dockerfile and automated container build workflow on merge"
```

---

### Task 7: MCP Server Interface

**Files:**
- Create: `libraries/mcp_server.py`
- Create: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: JSON-RPC tool calls `run_wishlist`, `get_tracked_items`, `check_health`.
- Produces: Structured JSON responses formatted per Model Context Protocol standard.

- [ ] **Step 1: Write failing test for MCP tool definitions and execution**

```python
# tests/test_mcp_server.py
import pytest
from libraries.mcp_server import WishlistMCPServer

def test_mcp_list_tools():
    server = WishlistMCPServer()
    tools = server.list_tools()
    tool_names = [t["name"] for t in tools]
    assert "run_wishlist" in tool_names
    assert "get_tracked_items" in tool_names
    assert "check_health" in tool_names

def test_mcp_execute_check_health():
    server = WishlistMCPServer()
    result = server.call_tool("check_health", {})
    assert result["status"] == "HEALTHY"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mcp_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'libraries.mcp_server'`

- [ ] **Step 3: Implement `WishlistMCPServer` in `libraries/mcp_server.py`**

Implement lightweight MCP tool schema registry and dispatcher without external heavy server dependencies, allowing integration via stdio or API.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mcp_server.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libraries/mcp_server.py tests/test_mcp_server.py
git commit -m "feat(mcp): implement WishlistMCPServer with standardized tool schemas"
```
