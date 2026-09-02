import socket
import json
import sys
from pathlib import Path

code = sys.stdin.read()
resolver_code = Path(__file__).with_name("resolver.py").read_text(encoding="utf-8")
code = (
    "exec(compile(" + repr(resolver_code) + ", '<hair_mcp_resolver>', 'exec'), globals())\n"
    "hmh = resolve_hair_mcp_helper()\n"
    + code
)

s = socket.socket()
s.settimeout(30)
s.connect(("127.0.0.1", 9876))

s.sendall(json.dumps({
    "type": "execute",
    "code": code,
    "strict_json": True
}).encode() + b"\0")

data = b""

while True:
    chunk = s.recv(65536)
    if not chunk:
        break
    data += chunk
    if b"\0" in data:
        break

print(data.decode(errors="replace"))
