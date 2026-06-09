"""
Converts a multi-line RSA PEM private key in your .env file into the
single-line format that python-dotenv can load correctly.

Usage:
    python scripts/format_kalshi_key.py

The script reads .env, finds the KALSHI_PRIVATE_KEY block, collapses it
to a single quoted line with literal \\n separators, and writes it back.
"""
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
content = env_path.read_text()

start = content.find("-----BEGIN RSA PRIVATE KEY-----")
end = content.find("-----END RSA PRIVATE KEY-----") + len("-----END RSA PRIVATE KEY-----")

if start == -1 or end == -1:
    print("No RSA private key block found in .env — nothing to do.")
    raise SystemExit(0)

pem = content[start:end]
pem_single = pem.replace("\r\n", "\n").replace("\n", "\\n")

key_start = content.rfind("KALSHI_PRIVATE_KEY=", 0, start)
old_block = content[key_start:end]
new_block = f'KALSHI_PRIVATE_KEY="{pem_single}"'

fixed = content.replace(old_block, new_block)
env_path.write_text(fixed)

print("Done. KALSHI_PRIVATE_KEY reformatted to single line.")
for line in fixed.splitlines():
    if line.startswith("KALSHI_PRIVATE_KEY"):
        print(line[:100] + "...")
        break
