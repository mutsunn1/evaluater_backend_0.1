import urllib.request
import json

BASE = "http://localhost:8000"

def post_json(url, data):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())

def get_json(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())

# Create session
sess = post_json(f"{BASE}/api/v1/sessions?user_id=conf-test2", {})
sid = sess["session_id"]
print(f"Session: {sid}")

# Answer 3 correct answers (need min 3 questions for stop check)
for i in range(5):
    # Get question via SSE stream
    stream_url = f"{BASE}/api/v1/sessions/{sid}/question"
    req = urllib.request.Request(stream_url)
    req.add_header("Accept", "text/event-stream")
    q_data = None
    with urllib.request.urlopen(req, timeout=120) as resp:
        buf = ""
        while True:
            ch = resp.read(1).decode("utf-8")
            if not ch:
                break
            buf += ch
            if buf.endswith("\n\n"):
                for line in buf.strip().split("\n"):
                    if line.startswith("data: ") and q_data is None:
                        try:
                            q_data = json.loads(line[6:])
                        except:
                            pass
                buf = ""
                if q_data and q_data.get("question"):
                    break

    if not q_data or "question" not in q_data:
        print(f"Q{i+1}: failed to get question")
        break

    q = q_data["question"]
    print(f"Q{i+1}: type={q.get('question_type')} text={q.get('question_text', '')[:40]}")

    # Answer correctly
    correct = q.get("correct_answer", True)
    if q.get("question_type") == "true_false":
        user_answer = "正确" if correct else "错误"
    else:
        user_answer = str(correct)

    resp = post_json(f"{BASE}/api/v1/sessions/{sid}/answer", {"answer": user_answer})
    print(f"  answer={resp.get('is_correct')} confidence={resp.get('confidence')} auto_stop={resp.get('auto_stop')}")

    if resp.get("auto_stop"):
        print(f"  STOP REASON: {resp.get('stop_reason')}")
        break

# Final confidence stats
stats = get_json(f"{BASE}/api/v1/sessions/{sid}/confidence")
print(f"\nFinal stats: accuracy={stats['accuracy']}%, confidence={stats['confidence']*100:.0f}%")
print(f"  should_stop={stats['should_stop']}, reason={stats.get('stop_reason','')}")
print(f"  sample={stats['sample_size']}, remaining={stats['remaining']}")
