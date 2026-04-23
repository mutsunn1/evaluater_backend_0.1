import urllib.request
import json
import time

BASE = "http://localhost:8000"
SID = "5a8085ac-2da9-4c7a-a588-3db0526e1665"

def post_json(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())

def get_json(url):
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())

# Stream question
print("Getting question...")
req = urllib.request.Request(f"{BASE}/api/v1/sessions/{SID}/question")
req.add_header("Accept", "text/event-stream")
q_data = None
with urllib.request.urlopen(req, timeout=120) as resp:
    buf = ""
    while True:
        ch = resp.read(1).decode("utf-8")
        if not ch: break
        buf += ch
        if buf.endswith("\n\n"):
            for line in buf.strip().split("\n"):
                if line.startswith("data: ") and q_data is None:
                    try: q_data = json.loads(line[6:])
                    except: pass
            buf = ""
            if q_data and q_data.get("question"): break

q = q_data["question"]
print(f"Question type: {q.get('question_type')}, correct: {q.get('correct_answer')}")

# Answer correctly
correct = q.get('correct_answer', True)
if q.get('question_type') == 'true_false':
    user_ans = "正确" if correct else "错误"
else:
    user_ans = str(correct)

print(f"Answering: {user_ans}")
resp = post_json(f"{BASE}/api/v1/sessions/{SID}/answer", {"answer": user_ans})
print(f"Result: correct={resp.get('is_correct')}, confidence={resp.get('confidence')}")

# Wait for async profile update
time.sleep(3)

# Check profile
profile = get_json(f"{BASE}/api/v1/users/profile-test/profile")
print(f"\nProfile after 1 answer:")
print(f"  HSK level: {profile['hsk_level']}")
print(f"  Skills: {json.dumps(profile.get('skill_levels', {}), ensure_ascii=False)}")
