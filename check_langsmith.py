# check_langsmith.py - finds out why LangSmith returns 403
import os
import requests
from dotenv import load_dotenv, dotenv_values

env_before = os.environ.get("LANGSMITH_API_KEY", "")
file_key = dotenv_values(".env").get("LANGSMITH_API_KEY", "")
print("Key already set in your terminal/Windows env:", bool(env_before))
if env_before and env_before != file_key:
    print("  -> WARNING: it DIFFERS from the key in .env, and it wins by default")

load_dotenv(override=True)  # now .env wins
key = os.getenv("LANGSMITH_API_KEY", "")
print("Key length:", len(key), "| starts with:", key[:8])
print("Has stray quote/space:", key != key.strip().strip('"\''))
print("LANGSMITH_ENDPOINT:", os.getenv("LANGSMITH_ENDPOINT", "(default = US)"))
print("LANGSMITH_WORKSPACE_ID set:", bool(os.getenv("LANGSMITH_WORKSPACE_ID")))
print("Old LANGCHAIN_* vars present:", [k for k in os.environ if k.startswith("LANGCHAIN_")])

headers = {"x-api-key": key}
if os.getenv("LANGSMITH_WORKSPACE_ID"):
    headers["x-tenant-id"] = os.getenv("LANGSMITH_WORKSPACE_ID")

for name, base in [("US", "https://api.smith.langchain.com"),
                   ("EU", "https://eu.api.smith.langchain.com"),
                   ("APAC", "https://apac.api.smith.langchain.com")]:
    r = requests.get(base + "/sessions?limit=1", headers=headers)
    print(name, "->", r.status_code, r.text[:80])