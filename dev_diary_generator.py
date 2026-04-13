#!/usr/bin/env python3
"""
开发日记生成器 - 基于Claude Code对话日志自动生成开发日记
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DevDiaryGenerator:
    """开发日记生成器"""

    def __init__(
        self,
        claude_history_path: Optional[str] = None,
        obsidian_vault_path: Optional[str] = None,
        diary_folder_name: str = "日记",
        api_key: Optional[str] = None
    ):
        """
        初始化日记生成器

        Args:
            claude_history_path: Claude Code历史文件路径
            obsidian_vault_path: Obsidian vault路径
            diary_folder_name: 日记文件夹名称
            api_key: DeepSeek API密钥
        """
        # Claude Code历史文件路径
        if claude_history_path is None:
            self.claude_history_path = Path.home() / ".claude" / "history.jsonl"
        else:
            self.claude_history_path = Path(claude_history_path)

        # Obsidian路径
        self.obsidian_vault_path = Path(obsidian_vault_path) if obsidian_vault_path else None
        self.diary_folder_name = diary_folder_name

        # API配置
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("请设置OPENAI_API_KEY环境变量或直接提供API密钥")

        # 创建OpenAI客户端（指向DeepSeek）
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )

        # 常量配置
        self.model = "deepseek-chat"
        self.max_retries = 3
        self.retry_delay = 1  # 秒

        logger.info(f"Claude历史文件: {self.claude_history_path}")
        if self.obsidian_vault_path:
            logger.info(f"Obsidian vault路径: {self.obsidian_vault_path}")
            logger.info(f"日记文件夹: {self.diary_folder_name}")

    def find_conversation_files_for_date(self, date_filter: str) -> List[Path]:
        """
        查找指定日期的完整对话JSONL文件
        扫描文件中所有记录的日期，只要包含目标日期的记录，就返回该文件

        Args:
            date_filter: 日期字符串（YYYY-MM-DD格式）

        Returns:
            文件路径列表
        """
        projects_dir = Path.home() / ".claude" / "projects"
        if not projects_dir.exists():
            logger.warning(f"Claude projects目录不存在: {projects_dir}")
            return []

        conversation_files = []

        # 遍历所有项目目录
        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            # 查找项目目录下的所有JSONL文件
            for jsonl_file in project_dir.glob("*.jsonl"):
                file_contains_date = False

                try:
                    with open(jsonl_file, 'r', encoding='utf-8') as f:
                        # 逐行扫描文件，寻找目标日期的记录
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if not line:
                                continue

                            try:
                                entry = json.loads(line)
                                timestamp_str = entry.get('timestamp')
                                if not timestamp_str:
                                    continue

                                # 解析时间戳
                                dt = None
                                # 处理ISO格式时间戳
                                if 'T' in timestamp_str:
                                    try:
                                        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                    except:
                                        continue
                                else:
                                    # 可能是Unix时间戳（毫秒）
                                    try:
                                        timestamp_ms = float(timestamp_str)
                                        dt = datetime.fromtimestamp(timestamp_ms / 1000)
                                    except:
                                        continue

                                if dt:
                                    file_date = dt.strftime('%Y-%m-%d')
                                    if file_date == date_filter:
                                        file_contains_date = True
                                        break  # 找到一条记录就足够了

                            except json.JSONDecodeError:
                                # 跳过JSON解析错误的行
                                continue

                except Exception as e:
                    logger.warning(f"扫描文件 {jsonl_file} 失败: {e}")
                    continue

                if file_contains_date:
                    conversation_files.append(jsonl_file)
                    logger.debug(f"找到对话文件: {jsonl_file} (包含日期: {date_filter})")

        logger.info(f"为日期 {date_filter} 找到 {len(conversation_files)} 个完整对话文件")
        return conversation_files

    def load_complete_conversations(self, date_filter: str) -> List[Dict[str, Any]]:
        """
        加载指定日期的完整对话内容
        只加载日期匹配的记录，支持跨天会话的按日分割

        Args:
            date_filter: 日期字符串（YYYY-MM-DD格式）

        Returns:
            完整对话记录列表
        """
        conversation_files = self.find_conversation_files_for_date(date_filter)
        if not conversation_files:
            return []

        all_entries = []

        for file_path in conversation_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    session_entries = []
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            entry = json.loads(line)
                            entry['_file'] = str(file_path)
                            entry['_line'] = line_num

                            # 添加时间信息
                            if 'timestamp' in entry:
                                timestamp_str = entry['timestamp']
                                # 处理ISO格式时间戳
                                if 'T' in timestamp_str:
                                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                else:
                                    # 可能是Unix时间戳（毫秒）
                                    try:
                                        timestamp_ms = float(timestamp_str)
                                        dt = datetime.fromtimestamp(timestamp_ms / 1000)
                                    except:
                                        continue

                                entry['datetime'] = dt
                                entry['date_str'] = dt.strftime('%Y-%m-%d')
                                entry['time_str'] = dt.strftime('%H:%M:%S')

                                # 只添加日期匹配的记录
                                if entry['date_str'] == date_filter:
                                    session_entries.append(entry)
                            else:
                                # 没有时间戳的记录，默认添加（但通常不会发生）
                                session_entries.append(entry)

                        except json.JSONDecodeError as e:
                            logger.warning(f"文件 {file_path} 第{line_num}行JSON解析错误: {e}")
                            continue

                    if session_entries:
                        # 获取会话ID（从第一条记录或整个文件）
                        session_id = None
                        # 先尝试从当前记录中查找
                        for entry in session_entries:
                            if 'sessionId' in entry:
                                session_id = entry['sessionId']
                                break

                        # 如果当前记录中没有，尝试读取文件第一条记录
                        if not session_id:
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f2:
                                    first_line = f2.readline().strip()
                                    if first_line:
                                        first_entry = json.loads(first_line)
                                        session_id = first_entry.get('sessionId')
                            except:
                                pass

                        # 添加会话信息
                        for entry in session_entries:
                            entry['sessionId'] = session_id or 'unknown'
                            entry['project'] = file_path.parent.name

                        all_entries.extend(session_entries)

            except Exception as e:
                logger.error(f"加载对话文件 {file_path} 失败: {e}")
                continue

        logger.info(f"为日期 {date_filter} 加载了 {len(all_entries)} 条完整对话记录")
        return all_entries

    def load_claude_history(self, date_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        加载Claude Code历史记录

        Args:
            date_filter: 日期过滤（YYYY-MM-DD格式），如果为None则加载所有记录

        Returns:
            过滤后的历史记录列表
        """
        if not self.claude_history_path.exists():
            logger.warning(f"Claude历史文件不存在: {self.claude_history_path}")
            return []

        entries = []
        try:
            with open(self.claude_history_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)

                        # 添加行号以便调试
                        entry['_line'] = line_num

                        # 转换时间戳
                        if 'timestamp' in entry:
                            # 时间戳是毫秒
                            timestamp_ms = entry['timestamp']
                            dt = datetime.fromtimestamp(timestamp_ms / 1000)
                            entry['datetime'] = dt
                            entry['date_str'] = dt.strftime('%Y-%m-%d')
                            entry['time_str'] = dt.strftime('%H:%M:%S')

                        entries.append(entry)
                    except json.JSONDecodeError as e:
                        logger.warning(f"第{line_num}行JSON解析错误: {e}")
                        continue

            logger.info(f"从Claude历史文件加载了{len(entries)}条记录")

            # 按日期过滤
            if date_filter:
                filtered = [e for e in entries if e.get('date_str') == date_filter]
                logger.info(f"按日期{date_filter}过滤后剩余{len(filtered)}条记录")
                return filtered

            return entries

        except Exception as e:
            logger.error(f"加载Claude历史文件失败: {e}")
            return []

    def check_today_has_conversations(self, max_wait_minutes: int = 0) -> bool:
        """
        检查今天是否有Claude Code对话记录，可选等待新记录

        Args:
            max_wait_minutes: 最大等待时间（分钟），如果为0则不等待

        Returns:
            是否有今天对话记录
        """
        import time
        from datetime import datetime

        today = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"检查今天({today})是否有Claude Code对话记录...")

        # 检查文件是否存在
        if not self.claude_history_path.exists():
            logger.warning(f"Claude历史文件不存在: {self.claude_history_path}")
            return False

        # 检查文件修改时间
        file_mtime = datetime.fromtimestamp(self.claude_history_path.stat().st_mtime)
        file_mtime_str = file_mtime.strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"Claude历史文件最后修改时间: {file_mtime_str}")

        # 加载今天记录
        entries = self.load_claude_history(today)

        if entries:
            logger.info(f"今天已有{len(entries)}条对话记录")
            return True

        logger.warning(f"今天({today})还没有Claude Code对话记录")

        # 如果需要等待
        if max_wait_minutes > 0:
            logger.info(f"等待新对话记录，最多{max_wait_minutes}分钟...")
            wait_seconds = max_wait_minutes * 60
            check_interval = 30  # 每30秒检查一次

            for i in range(0, wait_seconds, check_interval):
                time.sleep(check_interval)
                entries = self.load_claude_history(today)
                if entries:
                    logger.info(f"等待{i//60}分{i%60}秒后检测到{len(entries)}条新对话记录")
                    return True

                if i % 60 == 0:  # 每分钟日志
                    logger.info(f"已等待{i//60}分钟，尚未检测到新对话记录")

            logger.warning(f"等待{max_wait_minutes}分钟后仍未检测到新对话记录")

        return False

    def format_conversations_for_ai(self, entries: List[Dict[str, Any]]) -> str:
        """
        格式化对话记录，准备给AI分析

        Args:
            entries: 对话记录列表

        Returns:
            格式化后的文本
        """
        if not entries:
            return "今天没有Claude Code对话记录。"

        # 按会话分组
        sessions = {}
        for entry in entries:
            session_id = entry.get('sessionId')
            if not session_id:
                continue

            if session_id not in sessions:
                sessions[session_id] = {
                    'project': entry.get('project', '未知项目'),
                    'entries': []
                }

            sessions[session_id]['entries'].append(entry)

        # 格式化输出
        formatted = []
        formatted.append(f"# Claude Code对话日志汇总\n")
        formatted.append(f"日期: {entries[0].get('date_str', '未知日期')}")
        formatted.append(f"总对话条数: {len(entries)}")
        formatted.append(f"会话数量: {len(sessions)}\n")

        for i, (session_id, session_data) in enumerate(sessions.items(), 1):
            formatted.append(f"## 会话 {i}")
            formatted.append(f"项目: {session_data['project']}")
            formatted.append(f"会话ID: {session_id[:8]}...")
            formatted.append(f"对话条数: {len(session_data['entries'])}")
            formatted.append("\n### 对话内容:")

            for j, entry in enumerate(session_data['entries'], 1):
                display = entry.get('display', '')
                time_str = entry.get('time_str', '未知时间')

                # 简化显示内容，避免过长
                if len(display) > 200:
                    display = display[:200] + "..."

                formatted.append(f"{j}. [{time_str}] {display}")

            formatted.append("")  # 空行分隔会话

        return "\n".join(formatted)

    def format_complete_conversations_for_ai(self, entries: List[Dict[str, Any]]) -> str:
        """
        格式化完整对话记录，准备给AI分析

        Args:
            entries: 完整对话记录列表（包含type字段）

        Returns:
            格式化后的文本
        """
        if not entries:
            return "今天没有Claude Code完整对话记录。"

        # 按会话分组
        sessions = {}
        for entry in entries:
            session_id = entry.get('sessionId', 'unknown')

            if session_id not in sessions:
                sessions[session_id] = {
                    'project': entry.get('project', '未知项目'),
                    'entries': []
                }

            sessions[session_id]['entries'].append(entry)

        # 格式化输出
        formatted = []
        formatted.append(f"# Claude Code完整对话日志汇总\n")
        formatted.append(f"日期: {entries[0].get('date_str', '未知日期')}")
        formatted.append(f"总记录条数: {len(entries)}")
        formatted.append(f"会话数量: {len(sessions)}\n")

        for i, (session_id, session_data) in enumerate(sessions.items(), 1):
            formatted.append(f"## 会话 {i}")
            formatted.append(f"项目: {session_data['project']}")
            formatted.append(f"会话ID: {session_id[:8]}...")
            formatted.append(f"记录条数: {len(session_data['entries'])}")
            formatted.append("\n### 完整对话内容:")

            # 按时间排序
            def get_sort_key(entry):
                dt = entry.get('datetime')
                if dt:
                    # 转换为timestamp进行比较，避免时区问题
                    return dt.timestamp()
                return datetime.now().timestamp()

            sorted_entries = sorted(session_data['entries'], key=get_sort_key)

            for j, entry in enumerate(sorted_entries, 1):
                entry_type = entry.get('type', 'unknown')
                time_str = entry.get('time_str', '未知时间')

                content_summary = ""

                if entry_type == 'user':
                    # 用户消息
                    message = entry.get('message', {})
                    if isinstance(message, dict):
                        content = message.get('content', [])
                        if isinstance(content, list):
                            text_parts = []
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get('type') == 'text':
                                        text_parts.append(item.get('text', ''))
                            if text_parts:
                                content_summary = " ".join(text_parts)
                            else:
                                content_summary = str(content)[:200]
                        else:
                            content_summary = str(content)[:200]
                    else:
                        content_summary = str(message)[:200]

                    content_summary = f"用户: {content_summary}"

                elif entry_type == 'assistant':
                    # AI回复
                    message = entry.get('message', {})
                    if isinstance(message, dict):
                        content = message.get('content', [])
                        if isinstance(content, list):
                            text_parts = []
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get('type') == 'text':
                                        text_parts.append(item.get('text', ''))
                                    elif item.get('type') == 'thinking':
                                        text_parts.append(f"[思考过程] {item.get('thinking', '')}")
                            if text_parts:
                                content_summary = " ".join(text_parts)
                            else:
                                content_summary = str(content)[:200]
                        else:
                            content_summary = str(content)[:200]
                    else:
                        content_summary = str(message)[:200]

                    content_summary = f"AI助手: {content_summary}"

                elif entry_type == 'tool_use':
                    # 工具使用
                    tool_name = entry.get('message', {}).get('content', [{}])[0].get('name', '未知工具')
                    content_summary = f"使用工具: {tool_name}"

                elif entry_type == 'tool_result':
                    # 工具结果
                    content_summary = "工具执行结果"

                elif entry_type == 'thinking':
                    # 思考过程
                    thinking = entry.get('message', {}).get('content', [{}])[0].get('thinking', '')
                    content_summary = f"AI思考: {thinking}"

                else:
                    content_summary = f"类型: {entry_type}"

                # 简化显示内容
                if len(content_summary) > 300:
                    content_summary = content_summary[:300] + "..."

                formatted.append(f"{j}. [{time_str}] [{entry_type}] {content_summary}")

            formatted.append("")  # 空行分隔会话

        return "\n".join(formatted)

    def generate_diary_summary(self, conversations_text: str, date_str: str, complete_format: bool = False) -> str:
        """
        使用AI生成日记总结

        Args:
            conversations_text: 格式化后的对话文本
            date_str: 日期字符串
            complete_format: 是否为完整对话格式

        Returns:
            AI生成的日记总结
        """
        if complete_format:
            prompt = f"""请根据以下Claude Code完整对话日志，为我生成一篇{date_str}的详细AI对话日记分析。

重要要求：
1. 严格基于提供的完整对话内容生成总结，不添加任何超出对话内容的想象或虚构
2. 分析对话的核心内容和过程，包括：
   - 用户提出了什么问题或需求
   - AI助手是如何分析和处理的
   - AI使用了哪些工具（如Bash、Read、Edit等）来解决问题
   - 思考过程和决策逻辑
   - 最终结果或解决方案
3. 如实反映对话的主题、内容和讨论过程
4. 如果对话涉及开发工作，详细记录开发内容、技术实现、问题解决过程
5. 如果对话涉及日常询问、安排计划或其他话题，如实记录
6. 格式为Markdown，包含标题、章节（如：概述、主要对话分析、技术要点、总结等）
7. 语言客观准确，忠实于原始对话，突出对话中的关键信息和学习点

对话日志：
{conversations_text}

请生成一篇详细、准确的AI对话日记分析，重点分析"用户提出了什么问题，模型是怎么处理的"："""
        else:
            prompt = f"""请根据以下Claude Code对话日志，为我生成一篇{date_str}的AI对话日记。

重要要求：
1. 严格基于提供的对话内容生成总结，不添加任何超出对话内容的想象或虚构
2. 如实反映对话的主题、内容和讨论过程
3. 如果对话涉及开发工作，记录开发内容；如果涉及日常询问、安排计划或其他话题，如实记录
4. 格式为Markdown，包含标题、章节
5. 语言客观准确，忠实于原始对话

对话日志：
{conversations_text}

请生成一篇忠实、准确的AI对话日记："""

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"生成日记尝试 {attempt + 1}/{self.max_retries}")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个严格的对话记录者，必须忠实于提供的对话内容。你的任务是基于Claude Code对话日志生成准确的日记总结，不添加任何想象、虚构或超出对话内容的信息。对话可能涉及开发工作、日常询问、计划安排等各种话题，你需要如实记录。"
                        },
                        {"role": "user", "content": prompt}
                    ],
                    stream=False
                )

                content = response.choices[0].message.content
                logger.info("AI日记生成成功")
                return content

            except Exception as e:
                error_msg = str(e)
                if "authentication" in error_msg.lower() or "401" in error_msg or "API key" in error_msg:
                    logger.error(f"API认证失败: {e}")
                    raise
                elif "rate limit" in error_msg.lower() or "429" in error_msg:
                    logger.warning(f"API限速，等待后重试: {e}")
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error(f"生成日记失败 (尝试 {attempt + 1}): {e}")
                    if attempt == self.max_retries - 1:
                        logger.error("达到最大重试次数")
                        raise
                    time.sleep(self.retry_delay)

        raise RuntimeError("生成日记失败，请检查网络和API配置")

    def save_to_markdown(self, content: str, date_str: str, custom_path: Optional[str] = None) -> str:
        """
        保存日记为Markdown文件

        Args:
            content: 日记内容
            date_str: 日期字符串
            custom_path: 自定义保存路径

        Returns:
            保存的文件路径
        """
        # 确定保存路径
        if custom_path:
            save_dir = Path(custom_path)
        elif self.obsidian_vault_path:
            save_dir = self.obsidian_vault_path / self.diary_folder_name
        else:
            # 保存到当前目录的diaries文件夹
            save_dir = Path.cwd() / "diaries"

        # 创建目录（如果不存在）
        save_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        filename = f"{date_str}_AI对话日记.md"
        filepath = save_dir / filename

        # 写入文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"日记已保存到: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"保存日记文件失败: {e}")
            raise

    def generate_for_date(self, date_str: Optional[str] = None, save_path: Optional[str] = None) -> str:
        """
        为指定日期生成日记

        Args:
            date_str: 日期字符串（YYYY-MM-DD格式），如果为None则使用今天
            save_path: 自定义保存路径

        Returns:
            保存的文件路径
        """
        # 确定日期
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')

        logger.info(f"开始为日期 {date_str} 生成AI对话日记...")

        # 1. 尝试加载完整对话记录
        entries = self.load_complete_conversations(date_str)
        use_complete_format = False

        if entries:
            # 检查是否是完整对话格式（有type字段）
            if entries and 'type' in entries[0]:
                use_complete_format = True
                logger.info(f"使用完整对话数据，共{len(entries)}条记录")
            else:
                logger.info(f"使用历史文件数据，共{len(entries)}条记录")
        else:
            # 如果没有完整对话记录，尝试加载历史文件
            logger.info(f"未找到完整对话记录，尝试加载历史文件...")
            entries = self.load_claude_history(date_str)

            if not entries:
                # 如果没有对话记录，生成简单的日记文件
                logger.warning(f"日期 {date_str} 没有Claude Code对话记录")
                simple_diary = f"""# {date_str} AI对话日记

## 概述
今天没有Claude Code对话记录。

## 说明
- 日记生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Claude历史文件: {self.claude_history_path}
- 文件最后修改: {datetime.fromtimestamp(self.claude_history_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S') if self.claude_history_path.exists() else '文件不存在'}

## 备注
当有Claude Code对话时，系统会自动记录并生成详细的对话日记。"""

                # 保存简单日记
                filepath = self.save_to_markdown(simple_diary, date_str, save_path)
                return filepath

        # 2. 格式化对话
        if use_complete_format:
            conversations_text = self.format_complete_conversations_for_ai(entries)
        else:
            conversations_text = self.format_conversations_for_ai(entries)

        # 3. 生成日记总结
        diary_content = self.generate_diary_summary(conversations_text, date_str, use_complete_format)

        # 4. 保存为Markdown
        filepath = self.save_to_markdown(diary_content, date_str, save_path)

        return filepath

    def generate_for_today(self, save_path: Optional[str] = None) -> str:
        """为今天生成日记"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.generate_for_date(today, save_path)

    def list_available_dates(self) -> List[str]:
        """列出有对话记录的所有日期"""
        entries = self.load_claude_history()
        dates = sorted(set(e.get('date_str') for e in entries if e.get('date_str')))
        return dates


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='开发日记生成器')
    parser.add_argument('--date', help='生成指定日期的日记（YYYY-MM-DD格式）')
    parser.add_argument('--today', action='store_true', help='生成今天的日记')
    parser.add_argument('--list-dates', action='store_true', help='列出有对话记录的日期')
    parser.add_argument('--output', help='自定义输出目录路径')
    parser.add_argument('--claude-history', help='Claude历史文件路径')
    parser.add_argument('--obsidian-vault', help='Obsidian vault路径')

    args = parser.parse_args()

    try:
        # 创建生成器实例
        generator = DevDiaryGenerator(
            claude_history_path=args.claude_history,
            obsidian_vault_path=args.obsidian_vault,
            api_key=os.getenv('OPENAI_API_KEY')
        )

        if args.list_dates:
            # 列出可用日期
            dates = generator.list_available_dates()
            if dates:
                print("有对话记录的日期:")
                for date in dates:
                    print(f"  {date}")
            else:
                print("没有找到对话记录")
            return

        # 确定保存路径
        save_path = args.output

        if args.date:
            # 生成指定日期的日记
            filepath = generator.generate_for_date(args.date, save_path)
            print(f"\n[成功] 日记已生成: {filepath}")

        elif args.today:
            # 生成今天的日记
            filepath = generator.generate_for_today(save_path)
            print(f"\n[成功] 今天的日记已生成: {filepath}")

        else:
            # 默认生成今天的日记
            filepath = generator.generate_for_today(save_path)
            print(f"\n[成功] 今天的日记已生成: {filepath}")
            print(f"\n使用 --help 查看所有选项")

    except Exception as e:
        logger.error(f"程序运行失败: {e}")
        print(f"[错误] 错误: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())