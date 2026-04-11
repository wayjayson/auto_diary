"""
auto_dairy – Automatic Daily Diary Generator
==============================================
Collects today's AI conversation history from:
  • Cline (Claude Dev) VS Code extension  – saoudrizwan.claude-dev
  • Official Anthropic Claude Code CLI    – ~/.claude/projects/
  • GitHub Copilot Chat VS Code extension – github.copilot-chat

Then calls DeepSeek API to produce a structured Markdown diary and writes
it to the configured Obsidian vault folder.

Usage
-----
  python diary_generator.py          # run once (now)
  python diary_generator.py --schedule   # run once then wait for daily schedule
"""

import argparse
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
OBSIDIAN_VAULT_PATH: str = os.getenv("OBSIDIAN_VAULT_PATH", "")
DIARY_FOLDER: str = os.getenv("DIARY_FOLDER", "Daily")
SCHEDULE_TIME: str = os.getenv("SCHEDULE_TIME", "23:00")  # HH:MM (24-hour)
MIN_CHARS: int = 50

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conversation collectors
# ---------------------------------------------------------------------------

def _today() -> datetime.date:
    return datetime.date.today()


def _modified_today(path: Path) -> bool:
    """Return True if *path* was last modified on today's date."""
    try:
        mtime = datetime.date.fromtimestamp(path.stat().st_mtime)
        return mtime == _today()
    except OSError:
        return False


def _read_json(path: Path) -> object:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return json.load(fh)
    except Exception as exc:
        logger.debug("Cannot read %s: %s", path, exc)
        return None


def collect_cline_conversations() -> list[dict]:
    """
    Cline (saoudrizwan.claude-dev) stores one folder per task:
      %APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/tasks/<id>/
        api_conversation_history.json   – raw API messages
        ui_messages.json               – user-visible messages (fallback)
    """
    appdata = os.environ.get("APPDATA", "")
    base = Path(appdata) / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "tasks"
    results: list[dict] = []

    if not base.exists():
        logger.debug("Cline tasks directory not found: %s", base)
        return results

    for task_dir in base.iterdir():
        if not task_dir.is_dir():
            continue
        for filename in ("api_conversation_history.json", "ui_messages.json"):
            candidate = task_dir / filename
            if candidate.exists() and _modified_today(candidate):
                data = _read_json(candidate)
                if data is not None:
                    results.append({"source": f"cline/{filename}", "data": data})
                break  # prefer api_conversation_history when both present

    logger.info("Cline: collected %d conversation file(s)", len(results))
    return results


def collect_claude_code_cli_conversations() -> list[dict]:
    """
    Official Anthropic Claude Code CLI stores JSONL session files under:
      ~/.claude/projects/<hash>/<session-id>.jsonl
    Each line is a JSON object with at least {"role": ..., "content": ...}.
    """
    home = Path.home()
    base = home / ".claude" / "projects"
    results: list[dict] = []

    if not base.exists():
        logger.debug("Claude Code CLI projects directory not found: %s", base)
        return results

    for project_dir in base.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            if not _modified_today(jsonl_file):
                continue
            messages = []
            try:
                with open(jsonl_file, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            try:
                                messages.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass
            except OSError as exc:
                logger.debug("Cannot read %s: %s", jsonl_file, exc)
                continue
            if messages:
                results.append({"source": f"claude-cli/{jsonl_file.name}", "data": messages})

    logger.info("Claude Code CLI: collected %d session file(s)", len(results))
    return results


def collect_copilot_conversations() -> list[dict]:
    """
    GitHub Copilot Chat (github.copilot-chat) may store conversation state in:
      %APPDATA%/Code/User/globalStorage/github.copilot-chat/
    The exact structure varies by extension version; we do a best-effort scan
    of all JSON files modified today.
    """
    appdata = os.environ.get("APPDATA", "")
    base = Path(appdata) / "Code" / "User" / "globalStorage" / "github.copilot-chat"
    results: list[dict] = []

    if not base.exists():
        logger.debug("Copilot Chat directory not found: %s", base)
        return results

    for json_file in base.rglob("*.json"):
        if not _modified_today(json_file):
            continue
        data = _read_json(json_file)
        if data is not None:
            results.append({"source": f"copilot/{json_file.name}", "data": data})

    logger.info("Copilot Chat: collected %d file(s)", len(results))
    return results


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _extract_from_message(msg: object) -> str:
    """Return a plain-text string from a message object (various shapes)."""
    if isinstance(msg, str):
        return msg
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content") or msg.get("text") or msg.get("message") or ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif "text" in item:
                    parts.append(str(item["text"]))
        return " ".join(parts)
    return ""


def extract_text(conversations: list[dict]) -> str:
    """Flatten all conversation records into a single string."""
    parts: list[str] = []

    for conv in conversations:
        data = conv.get("data")
        source = conv.get("source", "unknown")

        if isinstance(data, list):
            for item in data:
                text = _extract_from_message(item)
                if text.strip():
                    parts.append(text.strip())
        elif isinstance(data, dict):
            # Try common top-level keys that contain message lists
            for key in ("messages", "turns", "conversation", "history", "items"):
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        text = _extract_from_message(item)
                        if text.strip():
                            parts.append(text.strip())
                    break
            else:
                # Last-resort: stringify the whole dict
                parts.append(json.dumps(data, ensure_ascii=False))

        logger.debug("Source %s contributed %d text fragment(s)", source, len(parts))

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# DeepSeek API
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
你是一位专业的个人知识管理助手，擅长将 AI 对话记录整理成结构化日记。
"""

USER_PROMPT_TEMPLATE = """\
请将以下 AI 对话记录整理成一篇 {date} 的结构化 Markdown 日记。

要求：
1. 日记开头包含 YAML front-matter（date, tags: [diary, ai-conversation]）
2. 第一段是当天的一句话总结
3. 按照对话主题自动分类，每个主题作为二级标题（## 主题名称）
4. 每个主题段包含以下三个子节：
   - **核心讨论**：简述讨论了什么问题
   - **关键结论**：总结出的重要结论或知识点
   - **行动项**：需要跟进或执行的事项（如无则写"无"）
5. 最后添加 ## 总结 章节，整体回顾当天的收获
6. 语言简洁专业，使用中文

---
对话记录：

{conversation}
"""


def summarize_with_deepseek(text: str, date_str: str) -> str:
    """Call DeepSeek API and return the diary Markdown string."""
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY is not set in .env")

    prompt = USER_PROMPT_TEMPLATE.format(date=date_str, conversation=text)

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }

    logger.info("Calling DeepSeek API (model=%s) …", DEEPSEEK_MODEL)
    response = requests.post(
        DEEPSEEK_API_URL,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    result = response.json()
    diary_content: str = result["choices"][0]["message"]["content"]
    logger.info("DeepSeek API returned %d characters", len(diary_content))
    return diary_content


# ---------------------------------------------------------------------------
# Obsidian output
# ---------------------------------------------------------------------------

def write_diary(content: str, date_str: str) -> Path:
    """Write *content* to <vault>/<DIARY_FOLDER>/<date_str>.md."""
    if not OBSIDIAN_VAULT_PATH:
        raise ValueError("OBSIDIAN_VAULT_PATH is not set in .env")

    vault = Path(OBSIDIAN_VAULT_PATH)
    if not vault.exists():
        raise FileNotFoundError(f"Obsidian vault path does not exist: {vault}")

    diary_dir = vault / DIARY_FOLDER
    diary_dir.mkdir(parents=True, exist_ok=True)

    filepath = diary_dir / f"{date_str}.md"
    filepath.write_text(content, encoding="utf-8")
    logger.info("Diary written to: %s", filepath)
    return filepath


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def run_once() -> None:
    """Collect conversations, summarise, and write diary for today."""
    today = _today()
    date_str = today.strftime("%Y-%m-%d")

    logger.info("=== auto_dairy running for %s ===", date_str)

    # 1. Collect
    all_conversations: list[dict] = []
    all_conversations.extend(collect_cline_conversations())
    all_conversations.extend(collect_claude_code_cli_conversations())
    all_conversations.extend(collect_copilot_conversations())

    # 2. Extract text
    combined_text = extract_text(all_conversations)
    char_count = len(combined_text.strip())
    logger.info("Total conversation characters collected: %d", char_count)

    # 3. Minimum length guard
    if char_count < MIN_CHARS:
        logger.info(
            "Conversation text is too short (%d chars, minimum %d). Skipping diary generation.",
            char_count,
            MIN_CHARS,
        )
        return

    # 4. Summarise via DeepSeek
    diary_md = summarize_with_deepseek(combined_text, date_str)

    # 5. Write to Obsidian
    write_diary(diary_md, date_str)


# ---------------------------------------------------------------------------
# Scheduler (in-process)
# ---------------------------------------------------------------------------

def run_scheduled() -> None:
    """
    Run once immediately, then wait and run again every day at SCHEDULE_TIME.
    This loop is used when the script is kept running (e.g. via `--schedule`).
    For a more robust schedule, use the Windows Task Scheduler (setup_scheduler.ps1).
    """
    logger.info("Scheduler mode enabled. Daily trigger time: %s", SCHEDULE_TIME)

    try:
        hour, minute = (int(x) for x in SCHEDULE_TIME.split(":"))
    except ValueError:
        logger.error("Invalid SCHEDULE_TIME format '%s'. Expected HH:MM.", SCHEDULE_TIME)
        sys.exit(1)

    while True:
        now = datetime.datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        logger.info("Next run scheduled at %s (in %.0f seconds)", target.strftime("%Y-%m-%d %H:%M"), wait_seconds)

        time.sleep(wait_seconds)
        try:
            run_once()
        except Exception as exc:
            logger.error("Diary generation failed: %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="auto_dairy – AI conversation diary generator")
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Keep running and trigger daily at SCHEDULE_TIME (defined in .env)",
    )
    args = parser.parse_args()

    if args.schedule:
        run_scheduled()
    else:
        try:
            run_once()
        except Exception as exc:
            logger.error("Diary generation failed: %s", exc, exc_info=True)
            sys.exit(1)


if __name__ == "__main__":
    main()
