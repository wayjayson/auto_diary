# auto_dairy

> Windows 自动化日记生成器：每天自动收集 VSCode 中 Claude Code / Copilot 插件的对话记录，调用 DeepSeek API 总结成结构化 Markdown 日记，归档到 Obsidian 知识库。

---

## 功能特性

| 特性 | 说明 |
|------|------|
| 多源抓取 | 支持 Cline（Claude Dev）插件、官方 Claude Code CLI、GitHub Copilot Chat |
| 最小字数保护 | 当日对话总字符 < 50 时静默退出，不生成日记 |
| DeepSeek 总结 | 使用 `deepseek-chat` 模型，按主题自动分类，包含核心讨论、关键结论、行动项 |
| Obsidian 输出 | 写入 `<vault>/<DIARY_FOLDER>/<YYYY-MM-DD>.md`，含 YAML front-matter |
| 双触发方式 | 双击 `run_diary.bat` 立即执行；或通过 Windows 任务计划程序定时执行 |
| 集中配置 | 所有配置项（API Key、路径、时间）存放于 `.env` |

---

## 前置条件

- Windows 10 / 11
- Python 3.10 或更高版本（已加入 `PATH`）
- DeepSeek API Key（[申请地址](https://platform.deepseek.com/)）
- Obsidian 知识库（本地文件夹）

---

## 安装步骤

```powershell
# 1. 克隆仓库
git clone https://github.com/wayjayson/auto_dairy.git
cd auto_dairy

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 创建并编辑 .env 配置文件
copy .env.example .env
notepad .env
```

### `.env` 配置说明

```ini
# DeepSeek API Key
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Obsidian 库根目录（绝对路径）
OBSIDIAN_VAULT_PATH=C:\Users\YourName\Documents\ObsidianVault

# 日记存放子文件夹（相对于库根目录）
DIARY_FOLDER=Daily

# 定时执行时间（24 小时制 HH:MM）
SCHEDULE_TIME=23:00
```

---

## 使用方式

### 方式一：双击立即运行

双击项目目录下的 `run_diary.bat`，脚本将立即收集当天对话并生成日记。

### 方式二：Windows 任务计划程序（定时执行）

以**管理员身份**运行 PowerShell，执行：

```powershell
cd <项目目录>
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\setup_scheduler.ps1
```

脚本会读取 `.env` 中的 `SCHEDULE_TIME` 并注册名为 `auto_dairy_daily` 的定时任务。

> **修改执行时间**：编辑 `.env` 中的 `SCHEDULE_TIME`，然后重新运行 `setup_scheduler.ps1`。

> **取消定时任务**：
> ```powershell
> Unregister-ScheduledTask -TaskName "auto_dairy_daily" -Confirm:$false
> ```

### 方式三：脚本内置调度（--schedule 参数）

```powershell
python diary_generator.py --schedule
```

脚本会立即运行一次，然后在每天 `SCHEDULE_TIME` 时再次运行。进程必须持续运行（适合放入后台服务）。

---

## 对话数据来源

| 插件 / 工具 | 读取路径 |
|-------------|----------|
| **Cline (Claude Dev)** VS Code 扩展 | `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\tasks\` |
| **Claude Code CLI**（官方） | `%USERPROFILE%\.claude\projects\**\*.jsonl` |
| **GitHub Copilot Chat** VS Code 扩展 | `%APPDATA%\Code\User\globalStorage\github.copilot-chat\` |

脚本只读取**当日修改**的文件，不影响历史记录。

---

## 生成的日记格式示例

```markdown
---
date: 2024-01-15
tags: [diary, ai-conversation]
---

今天主要探讨了 Python 异步编程和 Obsidian 插件开发两个主题。

## Python 异步编程

**核心讨论**：讨论了 asyncio 的事件循环机制以及 async/await 语法。

**关键结论**：
- `asyncio.gather()` 可以并发运行多个协程
- 避免在协程中使用阻塞 I/O

**行动项**：将现有同步爬虫改写为异步版本。

## 总结

今天收获颇丰，深入理解了异步编程模型，为后续项目优化打下基础。
```

---

## 项目结构

```
auto_dairy/
├── diary_generator.py   # 主程序
├── .env.example         # 配置模板（复制为 .env 后填写）
├── requirements.txt     # Python 依赖
├── run_diary.bat        # 双击立即运行（Windows）
├── setup_scheduler.ps1  # 注册 Windows 定时任务
└── README.md
```

---

## 常见问题

**Q: 脚本运行后没有生成日记？**
A: 检查终端输出。如果显示 "Conversation text is too short"，说明当日对话字符数 < 50，脚本正常静默退出。

**Q: DeepSeek API 调用失败？**
A: 确认 `.env` 中的 `DEEPSEEK_API_KEY` 正确，且账户余额充足。

**Q: 找不到对话历史文件？**
A: 确认已在 VSCode 中使用过对应插件，且当日有实际对话。路径因插件版本不同可能有差异，可查看日志中的 `DEBUG` 信息。

**Q: 如何开启 DEBUG 日志？**
A: 修改 `diary_generator.py` 中的日志级别：`logging.basicConfig(level=logging.DEBUG, ...)`