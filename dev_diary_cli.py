#!/usr/bin/env python3
"""
开发日记生成器 - 命令行界面
主入口点，支持手动生成、配置管理和定时任务设置
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='AI对话日记生成器 - 基于Claude Code对话日志自动生成忠实记录',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 生成今天的日记
  python dev_diary_cli.py generate

  # 生成指定日期的日记
  python dev_diary_cli.py generate --date 2024-01-01

  # 列出有对话记录的日期
  python dev_diary_cli.py list-dates

  # 显示配置
  python dev_diary_cli.py config --show

  # 编辑配置
  python dev_diary_cli.py config --edit

  # 设置定时任务
  python dev_diary_cli.py setup-scheduler

  # 测试生成（不保存）
  python dev_diary_cli.py test --date 2024-01-01

  # 总结当前对话会话
  python dev_diary_cli.py summarize-current
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='命令')

    # generate 命令
    generate_parser = subparsers.add_parser('generate', help='生成AI对话日记')
    generate_parser.add_argument('--date', help='指定日期 (YYYY-MM-DD格式)')
    generate_parser.add_argument('--output', help='自定义输出目录')
    generate_parser.add_argument('--force', action='store_true', help='强制重新生成，覆盖已存在的文件')
    generate_parser.add_argument('--no-ai', action='store_true', help='仅收集对话日志，不调用AI生成总结')
    generate_parser.add_argument('--wait', type=int, default=0, help='等待新对话记录的时间（分钟），0表示不等待')

    # list-dates 命令
    subparsers.add_parser('list-dates', help='列出有对话记录的日期')

    # config 命令
    config_parser = subparsers.add_parser('config', help='配置管理')
    config_parser.add_argument('--show', action='store_true', help='显示当前配置')
    config_parser.add_argument('--edit', action='store_true', help='交互式编辑配置')
    config_parser.add_argument('--reset', action='store_true', help='重置为默认配置')

    # setup-scheduler 命令
    subparsers.add_parser('setup-scheduler', help='设置定时任务')

    # test 命令
    test_parser = subparsers.add_parser('test', help='测试功能')
    test_parser.add_argument('--date', help='测试指定日期')
    test_parser.add_argument('--dry-run', action='store_true', help='干运行，不实际生成文件')

    # summarize-current 命令
    summarize_parser = subparsers.add_parser('summarize-current', help='总结当前对话会话')
    summarize_parser.add_argument('--session-id', help='指定会话ID，如未指定则使用最新会话')
    summarize_parser.add_argument('--output', help='自定义输出路径')
    summarize_parser.add_argument('--force', action='store_true', help='强制覆盖已存在的文件')

    # 如果没有提供命令，显示帮助
    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()

    # 执行命令
    if args.command == 'generate':
        return handle_generate(args)
    elif args.command == 'list-dates':
        return handle_list_dates(args)
    elif args.command == 'config':
        return handle_config(args)
    elif args.command == 'setup-scheduler':
        return handle_setup_scheduler(args)
    elif args.command == 'test':
        return handle_test(args)
    elif args.command == 'summarize-current':
        return handle_summarize_current(args)
    else:
        parser.print_help()
        return 0


def handle_generate(args):
    """处理generate命令"""
    from dev_diary_generator import DevDiaryGenerator
    import json

    # 加载配置
    config_file = Path(__file__).parent / "config.json"
    config = {}
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

    # 获取API密钥
    api_key_env_var = config.get("api_key_env_var", "OPENAI_API_KEY")
    api_key = os.getenv(api_key_env_var)
    if not api_key:
        print(f"[错误] 错误: 环境变量 {api_key_env_var} 未设置")
        print(f"请设置环境变量或编辑配置使用不同的变量名")
        return 1

    try:
        # 创建生成器
        generator = DevDiaryGenerator(
            claude_history_path=config.get("claude_history_path"),
            obsidian_vault_path=config.get("obsidian_vault_path"),
            diary_folder_name=config.get("diary_folder_name", "日记"),
            api_key=api_key
        )

        # 确定日期
        date_str = args.date
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
            print(f"[日期] 生成今天的日记: {date_str}")

        # 等待新对话记录（仅对今天有效）
        if args.wait > 0 and date_str == datetime.now().strftime('%Y-%m-%d'):
            print(f"[信息] 等待新对话记录，最多{args.wait}分钟...")
            has_conversations = generator.check_today_has_conversations(args.wait)
            if not has_conversations:
                print(f"[警告] 等待{args.wait}分钟后仍未检测到新对话记录")
                print(f"[信息] 将继续生成日记，但可能没有新内容")
        elif args.wait > 0:
            print(f"[警告] --wait 参数仅对今天有效，已指定日期 {date_str}，跳过等待")

        # 检查是否已存在
        if not args.force:
            if config.get("obsidian_vault_path"):
                vault_path = Path(config["obsidian_vault_path"])
                diary_dir = vault_path / config.get("diary_folder_name", "日记")
                filepath = diary_dir / f"{date_str}_AI对话日记.md"
                if filepath.exists():
                    print(f"[警告]  日记文件已存在: {filepath}")
                    print("使用 --force 参数强制重新生成")
                    return 0

        # 生成日记
        print(f"[处理] 正在生成 {date_str} 的AI对话日记...")
        filepath = generator.generate_for_date(date_str, args.output)

        print(f"\n[成功] 日记生成完成!")
        print(f"[文件夹] 文件位置: {filepath}")
        print(f"[页面] 文件大小: {Path(filepath).stat().st_size} 字节")

        # 显示文件预览
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(500)  # 前500字符
                print(f"\n[笔记] 内容预览:")
                print("-" * 50)
                print(content)
                if len(content) == 500:
                    print("...")
                print("-" * 50)
        except:
            pass

        return 0

    except Exception as e:
        print(f"[错误] 生成日记失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


def handle_list_dates(args):
    """处理list-dates命令"""
    from dev_diary_generator import DevDiaryGenerator
    import json

    # 加载配置
    config_file = Path(__file__).parent / "config.json"
    config = {}
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

    try:
        # 创建生成器
        generator = DevDiaryGenerator(
            claude_history_path=config.get("claude_history_path"),
            api_key=os.getenv(config.get("api_key_env_var", "OPENAI_API_KEY"))
        )

        dates = generator.list_available_dates()

        if dates:
            print(f"[日期] 有对话记录的日期 ({len(dates)} 天):")
            print("-" * 40)
            for i, date in enumerate(dates, 1):
                print(f"{i:3}. {date}")
            print("-" * 40)

            # 统计信息
            today = datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

            today_count = sum(1 for d in dates if d == today)
            yesterday_count = sum(1 for d in dates if d == yesterday)

            print(f"今日({today})记录: {'有' if today_count else '无'}")
            print(f"昨日({yesterday})记录: {'有' if yesterday_count else '无'}")

        else:
            print("[错误] 没有找到对话记录")
            print("请检查Claude历史文件路径是否正确")

        return 0

    except Exception as e:
        print(f"[错误] 列出日期失败: {e}")
        return 1


def handle_config(args):
    """处理config命令"""
    if args.show:
        os.system(f'python "{Path(__file__).parent / "config_manager.py"}" --show')
    elif args.edit:
        os.system(f'python "{Path(__file__).parent / "config_manager.py"}" --edit')
    elif args.reset:
        # 删除配置文件
        config_file = Path(__file__).parent / "config.json"
        if config_file.exists():
            config_file.unlink()
            print("[成功] 配置文件已重置")
        else:
            print("[信息]  配置文件不存在")
    else:
        # 默认显示
        os.system(f'python "{Path(__file__).parent / "config_manager.py"}" --show')
    return 0


def handle_setup_scheduler(args):
    """处理setup-scheduler命令"""
    os.system(f'python "{Path(__file__).parent / "config_manager.py"}" --setup-task')
    return 0


def handle_test(args):
    """处理test命令"""
    from dev_diary_generator import DevDiaryGenerator
    import json

    print("[试管] 测试模式")
    print("-" * 40)

    # 加载配置
    config_file = Path(__file__).parent / "config.json"
    config = {}
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

    # 获取API密钥
    api_key_env_var = config.get("api_key_env_var", "OPENAI_API_KEY")
    api_key = os.getenv(api_key_env_var)

    if not api_key:
        print(f"[错误] API密钥未设置 ({api_key_env_var})")
        print("测试将在没有API的情况下进行")

    try:
        # 创建生成器
        generator = DevDiaryGenerator(
            claude_history_path=config.get("claude_history_path"),
            api_key=api_key
        )

        # 测试日期
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')

        print(f"[日期] 测试日期: {date_str}")
        print(f"[文件夹] Claude历史文件: {generator.claude_history_path}")
        print(f"[密钥] API密钥: {'已设置' if api_key else '未设置'}")

        # 加载对话记录
        print("\n[放大镜] 加载对话记录...")
        entries = generator.load_claude_history(date_str)

        if entries:
            print(f"[成功] 找到 {len(entries)} 条对话记录")

            # 显示示例
            print(f"\n[配置] 记录示例 (前3条):")
            for i, entry in enumerate(entries[:3], 1):
                display = entry.get('display', '')
                time_str = entry.get('time_str', '未知时间')
                project = entry.get('project', '未知项目')
                print(f"{i}. [{time_str}] [{project}] {display[:100]}...")

            # 格式化测试
            print(f"\n[笔记] 格式化对话内容...")
            formatted = generator.format_conversations_for_ai(entries)
            print(f"[成功] 格式化完成，长度: {len(formatted)} 字符")

            if args.dry_run:
                print(f"\n[试管] 干运行完成，未实际生成文件")
                return 0

            if api_key:
                print(f"\n[机器人] 调用AI生成总结...")
                try:
                    summary = generator.generate_diary_summary(formatted, date_str)
                    print(f"[成功] AI生成完成，长度: {len(summary)} 字符")

                    # 显示部分内容
                    print(f"\n[页面] AI生成内容预览 (前300字符):")
                    print("-" * 50)
                    print(summary[:300])
                    if len(summary) > 300:
                        print("...")
                    print("-" * 50)
                except Exception as e:
                    print(f"[错误] AI生成失败: {e}")
            else:
                print(f"\n[警告]  API密钥未设置，跳过AI生成")

        else:
            print(f"[错误] 没有找到 {date_str} 的对话记录")

        return 0

    except Exception as e:
        print(f"[错误] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


def handle_summarize_current(args):
    """处理summarize-current命令"""
    from dev_diary_generator import DevDiaryGenerator
    import json
    import os
    from pathlib import Path
    from datetime import datetime

    print("[实时总结] 开始总结当前对话会话...")

    # 加载配置
    config_file = Path(__file__).parent / "config.json"
    config = {}
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

    # 获取API密钥
    api_key_env_var = config.get("api_key_env_var", "OPENAI_API_KEY")
    api_key = os.getenv(api_key_env_var)
    if not api_key:
        print(f"[错误] 环境变量 {api_key_env_var} 未设置")
        print("请设置环境变量或编辑配置使用不同的变量名")
        return 1

    try:
        # 创建生成器
        generator = DevDiaryGenerator(
            claude_history_path=config.get("claude_history_path"),
            obsidian_vault_path=config.get("obsidian_vault_path"),
            diary_folder_name=config.get("diary_folder_name", "日记"),
            api_key=api_key
        )

        # 查找会话文件
        projects_dir = Path.home() / ".claude" / "projects"
        if not projects_dir.exists():
            print(f"[错误] Claude projects目录不存在: {projects_dir}")
            return 1

        # 查找所有JSONL文件
        jsonl_files = []
        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            for jsonl_file in project_dir.glob("*.jsonl"):
                jsonl_files.append(jsonl_file)

        if not jsonl_files:
            print("[错误] 未找到任何对话文件")
            return 1

        # 按修改时间排序，获取最新文件
        jsonl_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest_file = jsonl_files[0]

        print(f"[信息] 使用最新对话文件: {latest_file}")

        # 从文件名提取会话ID
        session_id = latest_file.stem
        print(f"[信息] 会话ID: {session_id}")

        # 加载文件内容
        entries = []
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        entry['_file'] = str(latest_file)
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

                        # 添加会话ID
                        if 'sessionId' not in entry:
                            entry['sessionId'] = session_id

                        # 添加项目信息
                        entry['project'] = latest_file.parent.name

                        entries.append(entry)

                    except json.JSONDecodeError as e:
                        print(f"[警告] 第{line_num}行JSON解析错误: {e}")
                        continue

        except Exception as e:
            print(f"[错误] 加载对话文件失败: {e}")
            return 1

        if not entries:
            print("[错误] 对话文件为空或解析失败")
            return 1

        print(f"[信息] 加载了 {len(entries)} 条对话记录")

        # 分析会话时间范围
        dates_in_session = set()
        datetime_objects = []

        for entry in entries:
            if 'datetime' in entry:
                dt = entry['datetime']
                dates_in_session.add(dt.strftime('%Y-%m-%d'))
                datetime_objects.append(dt)

        # 确定显示日期：使用当前日期（因为这是实时总结）
        date_str = datetime.now().strftime('%Y-%m-%d')

        # 计算会话时间范围
        time_range_info = ""
        if datetime_objects:
            min_dt = min(datetime_objects)
            max_dt = max(datetime_objects)
            date_range = sorted(list(dates_in_session))

            if len(date_range) == 1:
                time_range_info = f"此会话发生在{date_range[0]}，时间范围：{min_dt.strftime('%H:%M:%S')} - {max_dt.strftime('%H:%M:%S')}"
            else:
                time_range_info = f"此会话跨越多天：{', '.join(date_range)}，时间范围：{min_dt.strftime('%Y-%m-%d %H:%M:%S')} - {max_dt.strftime('%Y-%m-%d %H:%M:%S')}"

        print(f"[信息] 会话时间范围: {time_range_info}")
        print(f"[信息] 使用当前日期作为文件名: {date_str}")

        # 生成时间戳用于文件名
        timestamp_str = datetime.now().strftime('%H%M%S')

        # 格式化对话
        formatted = generator.format_complete_conversations_for_ai(entries)

        # 添加时间范围信息到格式化文本中
        if time_range_info:
            formatted = f"## 会话时间范围信息\n{time_range_info}\n\n" + formatted

        # 生成总结
        print("[AI] 调用AI生成对话总结...")
        summary = generator.generate_diary_summary(formatted, date_str, complete_format=True)

        # 确定保存路径
        if args.output:
            save_path = Path(args.output)
            if save_path.is_dir():
                # 如果是目录，生成文件名
                filename = f"{date_str}_{session_id}_{timestamp_str}_对话总结.md"
                filepath = save_path / filename
            else:
                # 直接使用提供的路径
                filepath = save_path
        elif config.get("obsidian_vault_path"):
            vault_path = Path(config["obsidian_vault_path"])
            diary_dir = vault_path / config.get("diary_folder_name", "日记")
            # 创建conversations子目录
            conversations_dir = diary_dir / "conversations"
            conversations_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{date_str}_{session_id}_{timestamp_str}_对话总结.md"
            filepath = conversations_dir / filename
        else:
            # 保存到当前目录
            save_dir = Path.cwd() / "conversations"
            save_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{date_str}_{session_id}_{timestamp_str}_对话总结.md"
            filepath = save_dir / filename

        # 检查文件是否已存在
        if filepath.exists() and not args.force:
            print(f"[警告] 文件已存在: {filepath}")
            print("使用 --force 参数强制覆盖")
            return 0

        # 保存文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(summary)

            print(f"[成功] 对话总结已保存到: {filepath}")
            print(f"[信息] 文件大小: {filepath.stat().st_size} 字节")

            # 显示预览
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(500)
                print(f"\n[预览] 内容预览:")
                print("-" * 50)
                print(content)
                if len(content) == 500:
                    print("...")
                print("-" * 50)

            return 0

        except Exception as e:
            print(f"[错误] 保存文件失败: {e}")
            return 1

    except Exception as e:
        print(f"[错误] 总结当前对话失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())