"""Turn Claude Code session transcripts (.jsonl) into readable Markdown.

Usage: python3 transcripts_to_markdown.py <sessions_dir> <output_dir>

One Markdown file is written per session folder. It keeps what was said: the
user's messages and Claude's replies, in order. Each tool call becomes a
one-line note; tool output, Claude's private reasoning and the app's
bookkeeping records are left out.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

UUID_FILE = re.compile(r"^[0-9a-f]{8}-[0-9a-f-]{27}\.jsonl$")
# Text the app adds to a user message; not something the user typed.
INJECTED = re.compile(
    r"<(system-reminder|local-command-stdout|local-command-caveat|command-name|"
    r"command-message|command-args|task-notification)>.*?</\1>",
    re.DOTALL,
)
NOTE_LIMIT = 160


def load(path):
    """Read one transcript file into a list of records, skipping broken lines."""
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def first_timestamp(records):
    return next((r["timestamp"] for r in records if r.get("timestamp")), "")


def when(record):
    """Local date and time of a record, e.g. '2026-10-11 15:02'."""
    stamp = record.get("timestamp")
    if not stamp:
        return ""
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")


def shorten(text):
    text = " ".join(str(text).split())
    return text if len(text) <= NOTE_LIMIT else text[: NOTE_LIMIT - 1] + "…"


def tool_note(block):
    """One line saying which tool Claude used and on what."""
    name, args = block.get("name", "tool"), block.get("input") or {}
    for key in ("description", "file_path", "command", "pattern", "query", "url", "skill", "prompt"):
        if args.get(key):
            return f"> *Tool:* `{name}` — {shorten(args[key])}"
    return f"> *Tool:* `{name}`"


def questions_asked(block):
    """The questions and options of an AskUserQuestion call, as a list."""
    lines = []
    for question in (block.get("input") or {}).get("questions", []):
        lines.append(f"> **Claude asked:** {question.get('question', '')}")
        lines += [f"> - {o.get('label', '')}: {o.get('description', '')}" for o in question.get("options", [])]
    return lines


def result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    return "\n".join(part.get("text", "") for part in content or [] if part.get("type") == "text")


def render(records):
    """Markdown lines for one transcript file."""
    out, speaker, ask_ids = [], None, set()

    def say(who, record):
        nonlocal speaker
        if speaker != who:
            stamp = when(record)
            out.extend(["", f"## {who}" + (f"  <sub>{stamp}</sub>" if stamp else ""), ""])
            speaker = who

    for record in records:
        kind, message = record.get("type"), record.get("message")
        if kind not in ("user", "assistant") or not message or record.get("isSidechain"):
            continue
        if record.get("isMeta") or record.get("isCompactSummary"):
            continue
        content = message.get("content")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content or []

        for block in blocks:
            btype = block.get("type")
            if kind == "user" and btype == "text":
                text = INJECTED.sub("", block.get("text", "")).strip()
                if text:
                    say("You", record)
                    out.extend([text, ""])
            elif kind == "user" and btype == "image":
                say("You", record)
                out.extend(["*[image attached]*", ""])
            elif kind == "user" and btype == "tool_result" and block.get("tool_use_id") in ask_ids:
                say("You", record)
                out.extend([f"*Answer:* {result_text(block).strip()}", ""])
            elif kind == "assistant" and btype == "text":
                text = block.get("text", "").strip()
                if text:
                    say("Claude", record)
                    out.extend([text, ""])
            elif kind == "assistant" and btype == "tool_use":
                say("Claude", record)
                if block.get("name") == "AskUserQuestion":
                    ask_ids.add(block.get("id"))
                    out.extend(questions_asked(block) + [""])
                else:
                    # Consecutive notes share one quote block.
                    if out and out[-1] == "" and len(out) > 1 and out[-2].startswith("> *Tool:*"):
                        out.pop()
                    out.extend([tool_note(block), ""])
    return out


def title_of(folder, records):
    for record in reversed(records):
        if record.get("type") == "custom-title" and record.get("customTitle"):
            return record["customTitle"]
    return folder.name


def convert(folder, output_dir):
    files = sorted(p for p in folder.iterdir() if UUID_FILE.match(p.name))
    parts = sorted((load(p) for p in files), key=first_timestamp)
    # A session resumed under a new id can leave a full copy of itself behind.
    seen, unique = set(), []
    for records in parts:
        ids = frozenset(r["uuid"] for r in records if r.get("uuid"))
        if ids and not ids <= seen:
            unique.append(records)
            seen |= ids
    if not unique:
        return None

    lines = [f"# {title_of(folder, unique[-1])}", ""]
    for number, records in enumerate(unique, start=1):
        if len(unique) > 1:
            lines.extend(["", "---", "", f"*Part {number} of {len(unique)}*"])
        lines.extend(render(records))
    target = output_dir / f"{folder.name}.md"
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return target


def main():
    sessions_dir, output_dir = Path(sys.argv[1]), Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)
    for folder in sorted(p for p in sessions_dir.iterdir() if p.is_dir()):
        target = convert(folder, output_dir)
        print(f"{folder.name}: " + (f"{target.name} ({target.stat().st_size // 1024} KB)" if target else "no transcript found"))


if __name__ == "__main__":
    main()
