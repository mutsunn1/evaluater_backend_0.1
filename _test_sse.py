import urllib.request
import time

url = "http://localhost:8000/api/v1/sessions/sse-python-test/question"
req = urllib.request.Request(url)
req.add_header("Accept", "text/event-stream")

print("Connecting...")
with urllib.request.urlopen(req, timeout=120) as resp:
    while True:
        line = resp.readline().decode("utf-8")
        if not line:
            break
        print(line, end="")
        if line.strip().startswith("event: question"):
            break
print("\nDone!")
