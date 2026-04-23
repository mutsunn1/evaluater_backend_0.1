"""ES + Redis 部署脚本（支持国内镜像源）。"""
import os
import sys
import time
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 使用国内镜像
ES_IMAGE = "registry.docker-cn.com/library/elasticsearch:8.15.0"
REDIS_IMAGE = "registry.docker-cn.com/library/redis:7-alpine"
# 备选镜像源
ES_FALLBACK = "elasticsearch:8.15.0"
REDIS_FALLBACK = "redis:7-alpine"


def try_pull(image, fallback):
    """Try primary mirror, then fallback."""
    for img in [image, fallback]:
        print(f"  Pulling {img}...")
        result = subprocess.run(
            ["docker", "pull", img],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            print(f"  Pulled {img}")
            return img
        print(f"  Failed: {result.stderr[:200]}")
    return None


def start_es(image):
    """Start ES container."""
    # Stop existing
    subprocess.run(["docker", "stop", "evaluator_es"], capture_output=True)
    subprocess.run(["docker", "rm", "evaluator_es"], capture_output=True)

    cmd = [
        "docker", "run", "-d",
        "--name", "evaluator_es",
        "-p", "9200:9200",
        "-e", "discovery.type=single-node",
        "-e", "xpack.security.enabled=false",
        "-e", "ES_JAVA_OPTS=-Xms512m -Xmx512m",
        image,
    ]
    print(f"Starting ES from {image}...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    print(f"  Container: {result.stdout.strip()}")
    return True


def start_redis(image):
    """Start Redis container."""
    subprocess.run(["docker", "stop", "evaluator_redis"], capture_output=True)
    subprocess.run(["docker", "rm", "evaluator_redis"], capture_output=True)

    cmd = [
        "docker", "run", "-d",
        "--name", "evaluator_redis",
        "-p", "6379:6379",
        image,
        "redis-server", "--appendonly", "yes",
    ]
    print(f"Starting Redis from {image}...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    print(f"  Container: {result.stdout.strip()}")
    return True


def wait_for_es(timeout=120):
    """Wait for ES to be ready."""
    import urllib.request
    url = "http://localhost:9200/_cluster/health"
    print("\nWaiting for ES...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                import json
                data = json.loads(resp.read())
                status = data.get("status", "unknown")
                print(f"  ES status: {status}")
                if status in ("green", "yellow"):
                    return True
        except Exception:
            pass
        time.sleep(3)
    print(f"  Timeout after {timeout}s")
    return False


def create_indices():
    """Create required indices."""
    import urllib.request
    import json

    base_url = "http://localhost:9200"
    indices = {
        "app_trace": {"mappings": {"properties": {
            "trace_id": {"type": "keyword"},
            "input": {"type": "text"},
            "output": {"type": "text"},
        }}},
        "app_node": {"mappings": {"properties": {
            "node_id": {"type": "keyword"},
            "trace_id": {"type": "keyword"},
            "output": {"type": "text"},
        }}},
        "mid_term_memory": {"mappings": {"properties": {
            "session_id": {"type": "keyword"},
            "user_id": {"type": "keyword"},
            "period": {"type": "keyword"},
            "highlights": {"type": "nested"},
            "persistent_errors": {"type": "nested"},
            "interest_topics": {"type": "nested"},
            "created_at": {"type": "date"},
        }}},
    }

    for name, mapping in indices.items():
        req = urllib.request.Request(
            f"{base_url}/{name}",
            data=json.dumps(mapping).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get("acknowledged"):
                    print(f"  Index '{name}' created")
        except urllib.error.HTTPError as e:
            if e.code == 400:
                print(f"  Index '{name}' already exists")
            else:
                print(f"  Error: {e}")


def configure_oxygent(host="localhost", port=9200):
    """Generate oxygent ES config snippet."""
    config_snippet = f"""
# 在 app/main.py 的 main() 函数中，MAS 初始化前添加:
# Config.set_es_config({{
#     "hosts": ["{host}:{port}"],
#     "user": "",
#     "password": "",
# }})
"""
    print(f"\nOxygent ES 配置代码:")
    print(config_snippet)


def main():
    print("=" * 50)
    print("Elasticsearch + Redis 部署")
    print("=" * 50)

    # Try pull images
    es_image = try_pull(ES_IMAGE, ES_FALLBACK)
    redis_image = try_pull(REDIS_IMAGE, REDIS_FALLBACK)

    if not es_image or not redis_image:
        print("\nFailed to pull images. Check Docker network settings.")
        sys.exit(1)

    # Start containers
    start_es(es_image)
    start_redis(redis_image)

    # Wait for ES
    if not wait_for_es():
        sys.exit(1)

    # Create indices
    print("\nCreating indices...")
    create_indices()

    # Print config
    configure_oxygent()

    print("\n" + "=" * 50)
    print("部署完成!")
    print("  ES: http://localhost:9200")
    print("  Redis: localhost:6379")
    print("=" * 50)


if __name__ == "__main__":
    main()
