"""StupidClaw Benchmark — Real workflow replay"""
import requests, time, json, sys
from datetime import datetime

BRIDGE = "http://127.0.0.1:18800"
AUTH = {"Authorization": "Bearer X_K6rjUFN1YGNUHXWxRWlA1iCNwrD1sGoYD_OMQNMKM"}
BOT = 7724219783

TESTS = [
    ("Greeting", "Hi, what can you do?"),
    ("Math", "Calculate (45*67) + sqrt(256)"),
    ("Time", "What time is it?"),
    ("Web Search", "Search for latest Anthropic Claude news"),
    ("Web Fetch", "Fetch and summarize https://example.com"),
    ("File Write", "Write a file called benchmark.txt with content: test passed"),
    ("File Read", "Read the file benchmark.txt"),
    ("Memory Store", "Remember: my favorite food is beshbarmak"),
    ("Memory Recall", "What is my favorite food?"),
    ("HTTP Tool", "Use the http tool to GET https://httpbin.org/ip"),
    ("Docker", "List running docker containers using the docker tool"),
    ("Hard Question", "Explain the CAP theorem in distributed systems with examples"),
    ("Multi-step", "Search for Python 3.13 new features and summarize the top 3"),
    ("Self-awareness", "What tools do you have available?"),
    ("Cron", "/cron list"),
]

def get_last_bot_msg():
    r = requests.get(f"{BRIDGE}/messages?chat_id={BOT}&limit=1", headers=AUTH)
    msgs = r.json()
    if msgs and msgs[0]["sender_id"] == BOT:
        return msgs[0]["text"]
    return None

def send(text):
    requests.post(f"{BRIDGE}/send", headers={**AUTH, "Content-Type": "application/json"},
                  json={"chat_id": BOT, "text": text})

results = []
print(f"Running {len(TESTS)} benchmarks...\n")

for name, query in TESTS:
    # Get baseline
    before = get_last_bot_msg()
    
    start = time.time()
    send(query)
    
    # Wait for response (max 30s)
    response = None
    for _ in range(30):
        time.sleep(1)
        after = get_last_bot_msg()
        if after and after != before:
            response = after
            break
    
    elapsed = round(time.time() - start, 1)
    
    if response:
        has_error = any(w in response.lower() for w in ["error", "unable to", "could not", "failed"])
        status = "⚠️ PARTIAL" if has_error else "✅ PASS"
    else:
        status = "❌ TIMEOUT"
        response = "(no response in 30s)"
    
    results.append({"name": name, "status": status, "time": elapsed, "response": response[:150]})
    print(f"  {status} {name} ({elapsed}s): {response[:80]}")

# Summary
passed = sum(1 for r in results if "PASS" in r["status"])
partial = sum(1 for r in results if "PARTIAL" in r["status"])
failed = sum(1 for r in results if "TIMEOUT" in r["status"])
avg_time = round(sum(r["time"] for r in results) / len(results), 1)

print(f"\n{'='*60}")
print(f"RESULTS: {passed}/{len(TESTS)} pass, {partial} partial, {failed} fail")
print(f"AVG RESPONSE TIME: {avg_time}s")
print(f"COST: $0.00 (Groq free tier)")

# Save JSON
with open("/home/aid/workspace/stupidclaw/data/benchmark-results.json", "w") as f:
    json.dump({"timestamp": datetime.now().isoformat(), "results": results, 
               "summary": {"passed": passed, "partial": partial, "failed": failed, "avg_time": avg_time}}, f, indent=2)

print(f"\nSaved to benchmark-results.json")
