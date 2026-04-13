# AI对话日记生成器

基于Claude Code对话日志自动生成忠实记录，保存到Obsidian。严格基于真实对话内容，不添加任何虚构或想象。

## 功能特性

- 📅 **自动收集**：自动读取Claude Code对话历史（`~/.claude/history.jsonl`）
- 📊 **完整对话分析**：使用Claude Code完整对话JSONL数据（包含用户消息、AI回复、思考过程和工具使用），生成详细的分析报告
- 🔍 **深度分析**：分析"用户提出了什么问题，模型是怎么处理的"，包括问题解决过程、工具使用、思考逻辑
- 🤖 **忠实记录**：使用DeepSeek API分析对话内容，生成忠实、准确的对话记录，不添加任何虚构内容
- 📁 **Obsidian集成**：自动保存到Obsidian vault的指定文件夹
- ⏰ **定时生成**：支持每日自动生成（通过Windows任务计划）
- 🎛️ **手动控制**：支持命令行手动生成任意日期日记
- ⚡ **实时总结**：支持实时总结当前对话会话，生成独立的对话总结文件
- ⚙️ **配置管理**：提供交互式配置界面

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置设置

```bash
# 显示当前配置
python dev_diary_cli.py config --show

# 交互式编辑配置
python dev_diary_cli.py config --edit
```

编辑配置时，需要设置：
- **Obsidian vault路径**：您的Obsidian仓库路径（如：`D:\桌面\学习\obsidian\learning`）
- **日记文件夹名称**：在Obsidian中存储日记的文件夹名（如：`日记`）
- **自动生成时间**：每天自动生成的时间（如：`00:00` 表示午夜）
- **Claude历史文件路径**：默认已自动检测

### 3. 生成日记

```bash
# 生成今天的日记
python dev_diary_cli.py generate

# 生成指定日期的日记
python dev_diary_cli.py generate --date 2024-01-01

# 列出有对话记录的日期
python dev_diary_cli.py list-dates

# 强制重新生成（覆盖已存在文件）
python dev_diary_cli.py generate --force
```

### 4. 实时总结当前对话

```bash
# 总结当前/最新的对话会话
python dev_diary_cli.py summarize-current

# 总结并保存到自定义路径
python dev_diary_cli.py summarize-current --output "D:\路径\文件名.md"

# 强制覆盖已存在的文件
python dev_diary_cli.py summarize-current --force
```

### 5. 设置定时任务（Windows）

```bash
# 打开配置向导
python dev_diary_cli.py setup-scheduler
```

按照提示在Windows任务计划程序中创建任务。

## 文件结构

```
auto_diary/
├── dev_diary_generator.py     # 核心生成器类
├── dev_diary_cli.py           # 主命令行界面
├── config_manager.py          # 配置管理工具
├── run_daily.py               # 每日自动运行脚本
├── config.json                # 配置文件
├── requirements.txt           # Python依赖
├── .env                       # 环境变量（API密钥）
└── diaries/                   # 本地日记存储（如果没有配置Obsidian）
```

## 配置说明

### 配置文件 (config.json)

```json
{
  "obsidian_vault_path": "D:\\桌面\\学习\\obsidian\\learning",
  "diary_folder_name": "日记",
  "auto_generate_time": "00:00",
  "claude_history_path": "C:\\Users\\10548\\.claude\\history.jsonl",
  "enable_auto_generate": true,
  "api_key_env_var": "OPENAI_API_KEY",
  "model": "deepseek-chat",
  "max_retries": 3,
  "retry_delay_seconds": 1
}
```

### 环境变量

在 `.env` 文件中设置DeepSeek API密钥：

```bash
OPENAI_API_KEY=
```

## 使用场景

### 场景0：实时对话总结
1. 完成一次Claude Code对话后
2. 运行 `python dev_diary_cli.py summarize-current`
3. 系统自动查找最新对话文件，生成详细总结
4. 总结文件保存在Obsidian的`日记/conversations/`目录下
5. 可在对话中直接要求Claude生成总结，或手动运行命令

### 场景1：每日自动生成
1. 设置好配置和API密钥
2. 创建Windows定时任务（每天00:00运行）
3. 每天自动生成前一天的开发日记

### 场景2：手动生成特定日期
```bash
# 生成昨天的日记
python dev_diary_cli.py generate --date $(date -d "yesterday" +%Y-%m-%d)

# 生成上周的日记
python dev_diary_cli.py generate --date 2024-01-01
```

### 场景3：仅收集对话日志（不调用AI）
```bash
# 查看某天的对话记录
python dev_diary_cli.py test --date 2024-01-01
```

## 高级功能

### 自定义输出路径
```bash
python dev_diary_cli.py generate --output "D:\自定义路径\日记"
```

### 测试模式
```bash
# 测试但不保存文件
python dev_diary_cli.py test --date 2024-01-01 --dry-run

# 测试今天的对话记录
python dev_diary_cli.py test
```

### 批量生成
可以编写脚本批量生成多日日记：
```bash
# 示例：生成最近7天的日记
for i in {0..6}; do
  date=$(date -d "$i days ago" +%Y-%m-%d)
  python dev_diary_cli.py generate --date $date
done
```

## 常见问题

### Q0: 完整对话数据是如何获取的？
系统会自动扫描`~/.claude/projects/`目录下的JSONL文件，这些文件包含完整的对话记录，包括用户消息、AI回复、思考过程和工具使用。相比`history.jsonl`只记录用户输入，完整对话数据提供了更详细的分析基础。

### Q1: 找不到Claude历史文件
确保Claude Code已使用过，历史文件默认位置：`C:\Users\<用户名>\.claude\history.jsonl`

### Q3: API调用失败
- 检查API密钥是否正确
- 确认DeepSeek账户有足够额度
- 检查网络连接

### Q4: 生成的日记内容不准确
可以修改`dev_diary_generator.py`中的提示词模板，优化AI生成效果。

### Q5: 如何添加其他日志源？
目前支持Claude Code日志，未来可以扩展支持：
- VSCode编辑历史
- Git提交记录
- Copilot对话日志

## 开发计划

- [ ] 图形用户界面（GUI）
- [ ] 支持更多日志源（Git、VSCode、Copilot）
- [ ] 自定义提示词模板
- [ ] 日记模板系统
- [ ] 搜索和统计功能

## 注意事项

1. **隐私安全**：对话日志包含您的开发内容，请妥善保管
2. **API费用**：使用API可能产生费用
3. **文件覆盖**：使用`--force`参数会覆盖已存在的日记文件
4. **时区设置**：确保系统时区正确，以便按日期正确过滤日志

## 技术支持

如有问题或建议，请检查：
1. 查看日志输出 `python dev_diary_cli.py test`
2. 检查配置文件 `python dev_diary_cli.py config --show`
3. 确保依赖已安装 `pip install -r requirements.txt`
