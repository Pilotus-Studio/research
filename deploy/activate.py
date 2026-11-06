"""Activate locally prepared site releases; never build on the server."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request

import yaml


def run(*args):
    subprocess.run(args, check=True, timeout=30)


def write_mounted(path, content):
    # Traefik mounts this file directly: retain its inode during updates and rollback.
    with path.open("r+", encoding="utf-8") as stream:
        stream.seek(0)
        stream.write(content)
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())


def point(root, target):
    temporary = root / "current.next"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    temporary.replace(root / "current")


tag = sys.argv[1]
if not re.fullmatch(r"[0-9]{8}-[0-9]{6}", tag):
    raise SystemExit("Invalid release tag")
base = Path("/home/cheng/docker-projects")
index = base / "index"
research = base / "research"
dynamic = base / "traefik/dynamic.yml"
preview = index / "deploy/Caddyfile.preview"
original_dynamic = dynamic.read_text()
original_preview = preview.read_text()
config = yaml.safe_load(original_dynamic)
if "pilotus-research" in config["http"]["routers"]:
    raise SystemExit("Research route already exists; use the documented release-only update")
if config["http"]["services"]["pilotus-index"]["loadBalancer"]["servers"] != [{"url": "http://homepage"}]:
    raise SystemExit("Unexpected homepage route; review before activation")
for root in (index, research):
    assert (root / "releases" / tag / "index.html").is_file()
previous_index = os.readlink(index / "current")
assert not (research / "current").exists()
preview_new = original_preview.replace("http://127.0.0.1:8088 {", "http://:8088 {\n    bind 127.0.0.1 172.18.0.1")
assert preview_new != original_preview
preview_staged = index / "deploy/Caddyfile.preview.research-staged"
preview_staged.write_text(preview_new)
run("caddy", "validate", "--config", str(preview_staged), "--adapter", "caddyfile")
run("caddy", "validate", "--config", str(research / "deploy/Caddyfile"), "--adapter", "caddyfile")
updated = original_dynamic.replace("  routers:\n", "  routers:\n    pilotus-research:\n      rule: Host(`research.pilotus.studio`)\n      entryPoints: [websecure]\n      service: pilotus-research\n      tls:\n        certResolver: myresolver\n", 1)
updated = updated.replace("  services:\n", "  services:\n    pilotus-research:\n      loadBalancer:\n        servers:\n        - url: http://172.18.0.1:8891\n", 1)
updated = updated.replace("- url: http://homepage\n", "- url: http://172.18.0.1:8088\n", 1)
parsed = yaml.safe_load(updated)
assert len(parsed["http"]["routers"]) == len(config["http"]["routers"]) + 1
assert len(parsed["http"]["services"]) == len(config["http"]["services"]) + 1
# Prove all unrelated configuration remains identical.
comparison = json.loads(json.dumps(parsed))
del comparison["http"]["routers"]["pilotus-research"]
del comparison["http"]["services"]["pilotus-research"]
comparison["http"]["services"]["pilotus-index"] = config["http"]["services"]["pilotus-index"]
assert comparison == config
backup = dynamic.with_name("dynamic.yml.before-research-" + tag)
shutil.copy2(dynamic, backup)
shutil.copy2(preview, preview.with_name("Caddyfile.preview.before-research-" + tag))
(index / "previous-release.txt").write_text(previous_index + "\n")
unit = Path.home() / ".config/systemd/user/pilotus-research.service"
assert not unit.exists()
dynamic_write_started = False
try:
    point(index, "releases/" + tag)
    point(research, "releases/" + tag)
    preview.write_text(preview_new)
    shutil.copy2(research / "deploy/pilotus-research.service", unit)
    run("systemctl", "--user", "daemon-reload")
    run("systemctl", "--user", "restart", "pilotus-index-preview.service")
    run("systemctl", "--user", "enable", "--now", "pilotus-research.service")
    # Local static health checks, no public TLS or certificate dependency.
    import time
    for address, text in (("http://172.18.0.1:8088/", "PILOTUS"), ("http://172.18.0.1:8891/", "Pilotus Research")):
        for attempt in range(10):
            try:
                response = urllib.request.urlopen(address, timeout=3).read().decode()
                assert text in response
                break
            except Exception:
                if attempt == 9:
                    raise
                time.sleep(0.3)
    assert dynamic.read_text() == original_dynamic, "Concurrent Traefik update; abort"
    dynamic_write_started = True
    write_mounted(dynamic, updated)
except BaseException:
    if dynamic_write_started:
        write_mounted(dynamic, original_dynamic)
    point(index, previous_index)
    (research / "current").unlink(missing_ok=True)
    preview.write_text(original_preview)
    subprocess.run(["systemctl", "--user", "disable", "--now", "pilotus-research.service"], check=False)
    unit.unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "restart", "pilotus-index-preview.service"], check=False)
    raise
print("Activated both sites:", tag)
print("Traefik backup:", backup)
