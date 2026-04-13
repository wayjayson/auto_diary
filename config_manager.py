#!/usr/bin/env python3
"""
配置管理工具 - 用于修改开发日记生成器的设置
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

CONFIG_FILE = Path(__file__).parent / "config.json"


def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    if not CONFIG_FILE.exists():
        # 创建默认配置
        default_config = {
            "obsidian_vault_path": "",
            "diary_folder_name": "日记",
            "auto_generate_time": "22:00",
            "claude_history_path": str(Path.home() / ".claude" / "history.jsonl"),
            "enable_auto_generate": True,
            "api_key_env_var": "OPENAI_API_KEY",
            "model": "deepseek-chat",
            "max_retries": 3,
            "retry_delay_seconds": 1
        }
        save_config(default_config)
        return default_config

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return {}


def save_config(config: Dict[str, Any]) -> None:
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"[成功] 配置已保存到: {CONFIG_FILE}")
    except Exception as e:
        print(f"保存配置文件失败: {e}")


def show_config(config: Dict[str, Any]) -> None:
    """显示当前配置"""
    print("\n" + "=" * 50)
    print("当前配置")
    print("=" * 50)

    for key, value in config.items():
        if "key" in key.lower() and value and len(str(value)) > 10:
            # 隐藏API密钥
            display_value = f"{str(value)[:8]}...{str(value)[-4:]}"
        else:
            display_value = value

        print(f"{key:25}: {display_value}")

    print("=" * 50)


def edit_config_interactive() -> None:
    """交互式编辑配置"""
    config = load_config()

    print("\n[编辑配置] (直接回车保持原值)")
    print("-" * 40)

    # 1. Obsidian vault路径
    current = config.get("obsidian_vault_path", "")
    new = input(f"Obsidian vault路径 [{current}]: ").strip()
    if new:
        config["obsidian_vault_path"] = new

    # 2. 日记文件夹名称
    current = config.get("diary_folder_name", "日记")
    new = input(f"日记文件夹名称 [{current}]: ").strip()
    if new:
        config["diary_folder_name"] = new

    # 3. 自动生成时间
    current = config.get("auto_generate_time", "22:00")
    new = input(f"自动生成时间 (HH:MM) [{current}]: ").strip()
    if new:
        # 验证时间格式
        try:
            hours, minutes = map(int, new.split(":"))
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                config["auto_generate_time"] = new
            else:
                print("[警告]  时间格式无效，保持原值")
        except ValueError:
            print("[警告]  时间格式无效，保持原值")

    # 4. Claude历史文件路径
    current = config.get("claude_history_path", "")
    new = input(f"Claude历史文件路径 [{current}]: ").strip()
    if new:
        config["claude_history_path"] = new

    # 5. 是否启用自动生成
    current = config.get("enable_auto_generate", True)
    enable_str = "是" if current else "否"
    new = input(f"启用自动生成日记? (是/否) [{enable_str}]: ").strip().lower()
    if new in ["是", "yes", "y", "true"]:
        config["enable_auto_generate"] = True
    elif new in ["否", "no", "n", "false"]:
        config["enable_auto_generate"] = False

    # 6. API密钥环境变量名
    current = config.get("api_key_env_var", "OPENAI_API_KEY")
    new = input(f"API密钥环境变量名 [{current}]: ").strip()
    if new:
        config["api_key_env_var"] = new

    # 保存配置
    save_config(config)
    show_config(config)


def setup_windows_task() -> None:
    """设置Windows定时任务（Windows用户）"""
    config = load_config()
    if not config.get("enable_auto_generate", True):
        print("自动生成已禁用，跳过定时任务设置")
        return

    generate_time = config.get("auto_generate_time", "22:00")
    script_path = Path(__file__).parent / "run_daily.py"

    print("\n[设置Windows定时任务]")
    print(f"计划时间: 每天 {generate_time}")
    print(f"执行脚本: {script_path}")

    print("\n请手动创建Windows任务计划程序任务:")
    print("1. 打开'任务计划程序'")
    print("2. 点击'创建基本任务'")
    print(f"3. 名称: '开发日记生成器'")
    print(f"4. 触发器: 每天 {generate_time}")
    print(f"5. 操作: 启动程序")
    print(f"6. 程序/脚本: {sys.executable}")
    print(f"7. 参数: '{script_path}'")
    print("8. 完成设置")

    # 创建批处理文件以简化
    bat_content = f"""@echo off
echo 正在生成开发日记...
"{sys.executable}" "{script_path}"
pause
"""
    bat_path = Path(__file__).parent / "generate_diary.bat"
    with open(bat_path, 'w', encoding='gbk') as f:
        f.write(bat_content)

    print(f"\n[成功] 已创建批处理文件: {bat_path}")
    print(f"您可以在任务计划程序中直接调用此批处理文件")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='配置管理工具')
    parser.add_argument('--show', action='store_true', help='显示当前配置')
    parser.add_argument('--edit', action='store_true', help='交互式编辑配置')
    parser.add_argument('--setup-task', action='store_true', help='设置定时任务')

    args = parser.parse_args()

    if args.show:
        config = load_config()
        show_config(config)

    elif args.edit:
        edit_config_interactive()

    elif args.setup_task:
        setup_windows_task()

    else:
        # 默认显示帮助
        print("开发日记生成器 - 配置管理工具")
        print("\n使用方法:")
        print("  python config_manager.py --show     显示当前配置")
        print("  python config_manager.py --edit     交互式编辑配置")
        print("  python config_manager.py --setup-task  设置定时任务")
        print("\n示例:")
        print("  # 编辑配置")
        print("  python config_manager.py --edit")
        print("\n  # 显示当前配置")
        print("  python config_manager.py --show")


if __name__ == "__main__":
    main()