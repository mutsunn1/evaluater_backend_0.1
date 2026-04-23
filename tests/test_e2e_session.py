"""E2E test script: exercises the full session flow against a live server.

Run against a running server:
    python -m tests.test_e2e_session --base-url http://localhost:8000

Or with defaults (localhost:8000):
    python -m tests.test_e2e_session
"""

import argparse
import sys
import httpx


BASE_URL = "http://localhost:8000"


def test_health(base_url: str) -> bool:
    """Verify the server is alive."""
    try:
        resp = httpx.get(f"{base_url}/health", timeout=10)
        assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
        print("[PASS] Health check")
        return True
    except Exception as e:
        print(f"[FAIL] Health check: {e}")
        return False


def test_create_session(base_url: str) -> str | None:
    """Create a new session and return the session_id."""
    try:
        resp = httpx.post(
            f"{base_url}/api/v1/sessions",
            params={"user_id": "e2e-test-user"},
            timeout=30,
        )
        assert resp.status_code == 200, f"Create session failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "session_id" in data
        print(f"[PASS] Create session: {data['session_id']}")
        return data["session_id"]
    except Exception as e:
        print(f"[FAIL] Create session: {e}")
        return None


def test_get_events_empty(base_url: str, session_id: str) -> bool:
    """Verify events endpoint returns empty list for new session."""
    try:
        resp = httpx.get(f"{base_url}/api/v1/sessions/{session_id}/events", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"[PASS] Get events (empty): {len(data)} events")
        return True
    except Exception as e:
        print(f"[FAIL] Get events: {e}")
        return False


def test_get_summary(base_url: str, session_id: str) -> bool:
    """Verify summary endpoint works."""
    try:
        resp = httpx.get(f"{base_url}/api/v1/sessions/{session_id}/summary", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"[PASS] Get summary")
        return True
    except Exception as e:
        print(f"[FAIL] Get summary: {e}")
        return False


def run_all(base_url: str) -> bool:
    """Run all E2E tests in sequence."""
    print(f"\n{'='*60}")
    print(f"E2E Test Suite — targeting {base_url}")
    print(f"{'='*60}\n")

    results = []

    # 1. Health check (does not require MAS)
    results.append(test_health(base_url))

    # 2. Create session
    session_id = test_create_session(base_url)
    results.append(session_id is not None)

    if session_id:
        # 3. Get events (empty)
        results.append(test_get_events_empty(base_url, session_id))

        # 4. Get summary
        results.append(test_get_summary(base_url, session_id))

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed")
    print(f"{'='*60}")
    return passed == total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E2E test for evaluator backend")
    parser.add_argument("--base-url", default=BASE_URL, help="Server base URL")
    args = parser.parse_args()

    success = run_all(args.base_url)
    sys.exit(0 if success else 1)
