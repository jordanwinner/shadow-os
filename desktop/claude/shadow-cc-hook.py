#!/usr/bin/env python3
"""
Hook Claude Code → shadow-desktop.
Reçoit le JSON d'un évènement de hook sur stdin, écrit un statut compact que
l'extension Dynamic Island surveille et affiche en direct, et — en option —
demande l'autorisation Allow/Deny directement dans l'îlot.

Appel : shadow-cc-hook.py <EVENT>
Règle d'or : ne JAMAIS planter/bloquer Claude Code par erreur. En cas de doute,
on sort en 0 sans décision → Claude reprend son comportement normal.
"""
import sys, os, json, time, uuid

BASE = os.path.expanduser("~/.local/share/shadow-desktop")
OUT = os.path.join(BASE, "claude-status.json")
FLAG = os.path.join(BASE, "approvals.flag")        # touché par l'îlot quand les approbations sont actives
REQ = os.path.join(BASE, "permission-request.json")
RESP = os.path.join(BASE, "permission-response.json")

SENSITIVE = {"Bash", "Write", "Edit", "MultiEdit", "NotebookEdit"}
STATE = {
    "UserPromptSubmit": "thinking", "PreToolUse": "running", "PostToolUse": "running",
    "Notification": "waiting", "Stop": "done", "SubagentStop": "running",
    "SessionStart": "idle", "SessionEnd": "ended",
}


def detail_for(tool, ti):
    if not isinstance(ti, dict):
        return ""
    if tool in ("Edit", "Write", "Read", "NotebookEdit", "MultiEdit"):
        return os.path.basename(ti.get("file_path", "") or "")
    if tool == "Bash":
        c = ti.get("command", "") or ""
        return c.strip().splitlines()[0][:48] if c.strip() else ""
    if tool in ("Grep", "Glob"):
        return (ti.get("pattern", "") or "")[:40]
    if tool == "Task":
        return (ti.get("description", "") or ti.get("subagent_type", ""))[:40]
    if tool in ("WebFetch", "WebSearch"):
        return (ti.get("query", "") or ti.get("url", ""))[:40]
    return ""


def diff_counts(tool, ti):
    """(+ lignes ajoutées, - lignes retirées) approximatif pour l'affichage."""
    if not isinstance(ti, dict):
        return (0, 0)
    def lines(s):
        return (s.count("\n") + 1) if s else 0
    if tool == "Edit":
        return (lines(ti.get("new_string", "")), lines(ti.get("old_string", "")))
    if tool == "MultiEdit":
        a = r = 0
        for e in ti.get("edits", []) or []:
            a += lines(e.get("new_string", "")); r += lines(e.get("old_string", ""))
        return (a, r)
    if tool == "Write":
        return (lines(ti.get("content", "")), 0)
    return (0, 0)


def tags_for(cwd):
    tags = []
    if not cwd or not os.path.isdir(cwd):
        return tags
    j = os.path.join
    try:
        if os.path.exists(j(cwd, "package.json")): tags.append("node")
        if os.path.exists(j(cwd, "vercel.json")): tags.append("vercel")
        if any(os.path.exists(j(cwd, f)) for f in ("docker-compose.yml", "docker-compose.yaml", "Dockerfile")): tags.append("docker")
        if any(os.path.exists(j(cwd, f)) for f in ("pyproject.toml", "requirements.txt")): tags.append("python")
        if os.path.exists(j(cwd, "Cargo.toml")): tags.append("rust")
        try:
            with open(j(cwd, ".git", "config"), "r", errors="ignore") as f:
                cfg = f.read()
            if "github.com" in cfg: tags.append("github")
            elif "gitlab" in cfg: tags.append("gitlab")
        except OSError:
            pass
    except Exception:
        pass
    return tags[:5]


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def island_alive():
    """L'îlot touche FLAG régulièrement quand les approbations sont actives."""
    try:
        return (time.time() - os.path.getmtime(FLAG)) < 12
    except OSError:
        return False


def ask_island(req):
    """Écrit la demande, attend la réponse de l'îlot (max 25 s). None = pas de décision."""
    if not island_alive():
        return None
    rid = req["id"]
    try:
        write_json(REQ, req)
    except Exception:
        return None
    deadline = time.time() + 25
    while time.time() < deadline:
        try:
            with open(RESP) as f:
                r = json.load(f)
            if r.get("id") == rid:
                return r.get("decision")
        except Exception:
            pass
        time.sleep(0.15)
    return None


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else "?"
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    cwd = data.get("cwd") or ""
    tool = data.get("tool_name", "") or ""
    ti = data.get("tool_input", {})
    added, removed = diff_counts(tool, ti)
    project = os.path.basename(cwd.rstrip("/")) if cwd else ""
    out = {
        "event": event, "state": STATE.get(event, "running"), "ts": int(time.time()),
        "cwd": cwd, "project": project, "session": (data.get("session_id", "") or "")[:8],
        "tool": tool, "detail": detail_for(tool, ti), "added": added, "removed": removed,
        "msg": (data.get("message", "") or "")[:80], "prompt": (data.get("prompt", "") or "")[:70],
        "tags": tags_for(cwd),
    }
    os.makedirs(BASE, exist_ok=True)
    try:
        write_json(OUT, out)
    except Exception:
        pass

    # --- Approbation depuis l'îlot (seulement si l'îlot l'a activée) ---
    if event == "PreToolUse" and tool in SENSITIVE and island_alive():
        req = {"id": uuid.uuid4().hex[:12], "tool": tool, "detail": out["detail"],
               "cwd": cwd, "project": project, "added": added, "removed": removed,
               "ts": time.time()}
        decision = ask_island(req)
        if decision == "allow":
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                  "permissionDecision": "allow", "permissionDecisionReason": "Autorisé depuis l'îlot Shadow"}}))
        elif decision == "deny":
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                  "permissionDecision": "deny", "permissionDecisionReason": "Refusé depuis l'îlot Shadow"}}))
        # sinon (timeout / pas de réponse) : aucune sortie → Claude reprend son flux normal


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
