#!/usr/bin/env python3
"""
每日自动运行脚本 - 由定时任务调用，自动生成当天的开发日记
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from dev_diary_generator import DevDiaryGenerator


def load_config():
    """加载配置文件"""
    config_file = Path(__file__).parent / "config.json"
    if not config_file.exists():
        print(f"[错误] 配置文件不存在: {config_file}")
        return None

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[错误] 加载配置文件失败: {e}")
        return None


def main():
    """主函数"""
    print("=" * 60)
    print(f"[日期] 开发日记自动生成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 加载配置
    config = load_config()
    if not config:
        print("[错误] 无法加载配置，退出")
        return 1

    # 检查是否启用自动生成
    if not config.get("enable_auto_generate", True):
        print("[信息]  自动生成已禁用，退出")
        return 0

    # 获取API密钥
    api_key_env_var = config.get("api_key_env_var", "OPENAI_API_KEY")
    api_key = os.getenv(api_key_env_var)
    if not api_key:
        print(f"[错误] 环境变量 {api_key_env_var} 未设置")
        return 1

    try:
        # 创建生成器实例
        generator = DevDiaryGenerator(
            claude_history_path=config.get("claude_history_path"),
            obsidian_vault_path=config.get("obsidian_vault_path"),
            diary_folder_name=config.get("diary_folder_name", "日记"),
            api_key=api_key
        )

        # 生成今天的日记
        print("\n[处理] 正在生成今天的开发日记...")
        filepath = generator.generate_for_today()

        print(f"\n[成功] 日记生成完成!")
        print(f"[文件夹] 文件位置: {filepath}")
        print(f"[闹钟] 生成时间: {datetime.now().strftime('%H:%M:%S')}")

        return 0

    except Exception as e:
        print(f"\n[错误] 生成日记失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    print(f"\n程序退出代码: {exit_code}")
    sys.exit(exit_code)