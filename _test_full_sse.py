import urllib.request
import time

url = "http://localhost:8000/api/v1/sessions/test-full2/question"
req = urllib.request.Request(url)
req.add_header("Accept", "text/event-stream")

print("Connecting...")
start = time.time()
with urllib.request.urlopen(req, timeout=180) as resp:
    while True:
        line = resp.readline().decode("utf-8")
        if not line:
            break
        line = line.strip()
        elapsed = time.time() - start
        if line.startswith("data: "):
            data = line[6:]
            print(f"  [{elapsed:.1f}s] data: {data[:120]}...")
        elif line.startswith("event: "):
            print(f"  [{elapsed:.1f}s] event: {line[7:]}")
        elif line.startswith(":"):
            print(f"  [{elapsed:.1f}s] flush ping")
print("Done!")
