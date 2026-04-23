"""
Elasticsearch 部署与初始化脚本

功能:
1. 通过 docker compose 启动 ES + Redis
2. 等待 ES 就绪
3. 通过 oxygent Config 注册 ES 配置
4. 创建中期记忆索引 (mid_term_memory)

用法:
    conda activate agent
    python setup_es.py
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def check_docker():
    """Check if docker compose is available."""
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            print("Error: docker compose not available")
            return False
        print(f"Docker Compose: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("Error: docker not found. Please install Docker Desktop.")
        return False


def start_services():
    """Start ES + Redis via docker compose."""
    compose_file = Path(__file__).parent / "docker-compose.yml"
    if not compose_file.exists():
        print(f"Error: docker-compose.yml not found at {compose_file}")
        return False

    print("\nStarting Elasticsearch + Redis...")
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        print(f"Error starting services: {result.stderr}")
        return False
    print("  Containers started")
    return True


def wait_for_es(host: str = "localhost", port: int = 9200, timeout: int = 120):
    """Wait for Elasticsearch to be ready."""
    import urllib.request
    import urllib.error

    url = f"http://{host}:{port}/_cluster/health"
    print(f"\nWaiting for ES at {host}:{port}...")

    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                import json
                data = json.loads(resp.read())
                status = data.get("status", "unknown")
                print(f"  ES status: {status}")
                if status in ("green", "yellow"):
                    return True
        except (urllib.error.URLError, Exception):
            pass
        time.sleep(3)

    print(f"  Timeout: ES not ready after {timeout}s")
    return False


def create_indices(host: str = "localhost", port: int = 9200):
    """Create required indices for oxygent + mid-term memory."""
    import urllib.request
    import json

    base_url = f"http://{host}:{port}"

    # Indices: oxygent internal + our mid_term_memory
    indices = {
        "app_trace": {
            "mappings": {
                "properties": {
                    "trace_id": {"type": "keyword"},
                    "request_id": {"type": "keyword"},
                    "input": {"type": "text"},
                    "output": {"type": "text"},
                    "create_time": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss.SSSSSSSSS"},
                }
            }
        },
        "app_node": {
            "mappings": {
                "properties": {
                    "node_id": {"type": "keyword"},
                    "trace_id": {"type": "keyword"},
                    "input": {"type": "text"},
                    "output": {"type": "text"},
                    "create_time": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss.SSSSSSSSS"},
                    "update_time": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss.SSSSSSSSS"},
                }
            }
        },
        "mid_term_memory": {
            "mappings": {
                "properties": {
                    "session_id": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "period": {"type": "keyword"},
                    "highlights": {
                        "type": "nested",
                        "properties": {
                            "text": {"type": "text"},
                            "tag": {"type": "keyword"},
                            "topic": {"type": "keyword"},
                        },
                    },
                    "persistent_errors": {
                        "type": "nested",
                        "properties": {
                            "pattern": {"type": "text"},
                            "tag": {"type": "keyword"},
                            "severity": {"type": "keyword"},
                        },
                    },
                    "interest_topics": {
                        "type": "nested",
                        "properties": {
                            "topic": {"type": "keyword"},
                            "engagement_score": {"type": "float"},
                        },
                    },
                    "created_at": {"type": "date"},
                }
            }
        },
    }

    created = 0
    for name, mapping in indices.items():
        url = f"{base_url}/{name}"
        req = urllib.request.Request(
            url,
            data=json.dumps(mapping).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get("acknowledged") or data.get("shards_acknowledged"):
                    print(f"  Index '{name}' created")
                    created += 1
                else:
                    print(f"  Index '{name}' may already exist")
        except urllib.error.HTTPError as e:
            if e.code == 400:
                print(f"  Index '{name}' already exists")
            else:
                print(f"  Error creating '{name}': {e}")

    print(f"\n  {created} new indices created")


def main():
    host = os.getenv("ES_HOST", "localhost")
    port = int(os.getenv("ES_PORT", "9200"))

    print("=" * 50)
    print("Elasticsearch 部署脚本")
    print("=" * 50)

    # Step 1: Check docker
    if not check_docker():
        print("\nPlease install Docker Desktop first:")
        print("  https://www.docker.com/products/docker-desktop/")
        sys.exit(1)

    # Step 2: Start services
    if not start_services():
        sys.exit(1)

    # Step 3: Wait for ES
    if not wait_for_es(host, port):
        sys.exit(1)

    # Step 4: Create indices
    print("\nCreating indices...")
    create_indices(host, port)

    print("\n" + "=" * 50)
    print("部署完成！")
    print(f"  ES: http://{host}:{port}")
    print("  请在 .env 中确认 ES_HOST 和 ES_PORT 配置")
    print("=" * 50)


if __name__ == "__main__":
    main()
