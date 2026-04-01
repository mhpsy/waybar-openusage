# waybar-openusage

在 Waybar 上追踪你所有 AI 编程工具的订阅用量。适用于 Hyprland / Sway 等 Wayland 桌面环境。

> **项目来源**: 本项目移植自 [OpenUsage](https://github.com/robinebers/openusage) — 一个 macOS 菜单栏应用。由于原项目基于 Tauri（Rust + React），仅支持 macOS，本项目将其核心逻辑（插件系统、数据获取、HTTP API）用 Python 重写，使其能在 Linux 上通过 Waybar 自定义模块运行。

## 与原项目的关系

| | [OpenUsage](https://github.com/robinebers/openusage) | waybar-openusage |
|---|---|---|
| 平台 | macOS (Tauri) | Linux (Waybar) |
| 语言 | Rust + TypeScript + QuickJS | Python |
| 显示方式 | macOS 菜单栏 | Waybar 自定义模块 |
| 插件系统 | QuickJS 沙箱 | Python 模块 |
| HTTP API | `127.0.0.1:6736` | `127.0.0.1:6736` (兼容) |
| 凭据存储 | macOS Keychain + 文件 | 文件 + gh CLI |

所有 Provider 的 API 端点、认证逻辑、数据解析均参照原项目的插件实现移植，并适配了 Linux 下的文件路径和凭据获取方式。

## 功能

- **一目了然** — 所有 AI 工具用量显示在 Waybar 上
- **自动刷新** — 可配置刷新间隔（默认 15 分钟），支持点击立即刷新
- **丰富的 Tooltip** — 彩色进度条、重置倒计时、多行详情
- **本地 HTTP API** — 兼容 OpenUsage 的 API 格式，其他应用可读取用量数据
- **并发获取** — 多个 Provider 并行探测，速度快

## 支持的 Provider

| Provider | 数据 | 认证方式 |
|----------|------|----------|
| **Claude** | Session / Weekly / Sonnet / Extra usage | `~/.claude/.credentials.json` |
| **Cursor** | Credits / Total / Auto / API / On-demand | `~/.config/Cursor/` SQLite |
| **Copilot** | Premium / Chat / Completions | `gh auth token` |
| **Codex** | Session / Weekly / Credits | `~/.config/codex/auth.json` |
| **Windsurf** | Prompt credits / Flex credits | `~/.config/Windsurf/` SQLite |
| **Gemini** | Pro / Flash quota | `~/.gemini/oauth_creds.json` |
| **Amp** | Free balance / Bonus / Credits | `~/.local/share/amp/secrets.json` |
| **Kimi Code** | Session / Weekly | `~/.kimi/credentials/kimi-code.json` |
| **Z.ai** | Session / Weekly / Web searches | `ZAI_API_KEY` 环境变量 |
| **MiniMax** | Session prompts | `MINIMAX_API_KEY` 环境变量 |
| **JetBrains AI** | Quota / Remaining | `~/.config/JetBrains/` XML |
| **OpenCode Go** | 5h / Weekly / Monthly spend | `~/.local/share/opencode/` SQLite |
| **Factory/Droid** | Standard / Premium tokens | `~/.factory/auth.json` |

## 安装

### 依赖

- Python >= 3.11
- `requests` (自动安装)
- 可选: `cryptography` (Factory 加密认证支持)

### 安装步骤

```bash
git clone https://github.com/mhpsy/waybar-openusage.git
cd waybar-openusage
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

或者使用安装脚本:

```bash
chmod +x install.sh
./install.sh
```

### 验证安装

```bash
# 查看所有可用的 Provider
waybar-openusage --mode list

# 测试获取数据（以 Claude 为例）
waybar-openusage --mode once --plugins claude -v
```

## 配置 Waybar

### 1. 添加模块定义

在 `~/.config/waybar/config.jsonc` 中添加:

```jsonc
// 在 modules-right 中添加 "custom/openusage"
"modules-right": [
    // ... 其他模块 ...
    "custom/openusage",
    "custom/exit"
],

// 模块配置
"custom/openusage": {
    "exec": "/path/to/waybar-openusage/.venv/bin/waybar-openusage --mode continuous",
    "return-type": "json",
    "restart-interval": 5,
    "tooltip": true,
    "format": "{}",
    "max-length": 50,
    "on-click": "pkill -SIGUSR1 -f waybar-openusage || true"
}
```

> 注意: 将 `/path/to/` 替换为你的实际安装路径。

### 2. 添加样式

在 `~/.config/waybar/style.css` 中添加:

```css
#custom-openusage {
    background-color: @bg;       /* 或你自己的背景色 */
    color: @fg;
    border-radius: 15px;
    padding: 4px 12px;
    margin: 6px 4px;
}

#custom-openusage.warning {
    color: #f9e2af;
}

#custom-openusage.critical {
    color: #f38ba8;
}

#custom-openusage.error {
    color: #a6adc8;
    font-style: italic;
}
```

### 3. 重启 Waybar

```bash
killall waybar && waybar &
```

## 应用配置

配置文件路径: `~/.config/waybar-openusage/config.json`

```json
{
  "enabled_plugins": ["claude", "cursor", "copilot"],
  "plugin_order": [
    "claude", "cursor", "copilot", "codex", "windsurf", "gemini",
    "amp", "kimi", "zai", "minimax", "jetbrains-ai-assistant",
    "opencode-go", "factory"
  ],
  "refresh_interval_minutes": 15,
  "display_mode": "used",
  "http_api_enabled": true,
  "http_api_port": 6736
}
```

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `enabled_plugins` | 启用的 Provider 列表 | `["claude", "cursor", "copilot"]` |
| `plugin_order` | 显示顺序 | 全部 Provider |
| `refresh_interval_minutes` | 自动刷新间隔（分钟） | `15` |
| `display_mode` | `"used"` 已用量 / `"left"` 剩余量 | `"used"` |
| `http_api_enabled` | 是否启用本地 HTTP API | `true` |
| `http_api_port` | HTTP API 端口 | `6736` |

## CLI 用法

```bash
# 单次输出（测试用）
waybar-openusage --mode once

# 持续模式（Waybar 使用）
waybar-openusage --mode continuous

# 列出所有可用 Provider
waybar-openusage --mode list

# 指定 Provider
waybar-openusage --mode once --plugins claude cursor

# 自定义刷新间隔
waybar-openusage --mode continuous --interval 5

# 禁用 HTTP API
waybar-openusage --mode once --no-api

# 详细日志输出到 stderr
waybar-openusage --mode once -v
```

## 本地 HTTP API

运行时在 `127.0.0.1:6736` 提供 REST API，格式与 OpenUsage 兼容:

```bash
# 获取所有已启用 Provider 的用量
curl http://127.0.0.1:6736/v1/usage

# 获取单个 Provider
curl http://127.0.0.1:6736/v1/usage/claude
```

响应示例:

```json
[
  {
    "providerId": "claude",
    "displayName": "Claude",
    "plan": "Max 20x",
    "lines": [
      {
        "type": "progress",
        "label": "Session",
        "used": 21.0,
        "limit": 100,
        "format": { "kind": "percent" },
        "resetsAt": "2026-04-01T11:00:01Z",
        "periodDurationMs": 18000000
      }
    ],
    "fetchedAt": "2026-04-01T10:12:46Z"
  }
]
```

## Waybar 交互

| 操作 | 行为 |
|------|------|
| **悬停** | 显示所有 Provider 的详细用量（进度条 + 重置倒计时） |
| **左键点击** | 立即刷新数据 |

## 项目结构

```
waybar-openusage/
├── waybar_openusage/
│   ├── __init__.py
│   ├── main.py           # 入口，CLI 参数，持续/单次模式
│   ├── config.py          # 配置管理（XDG 路径）
│   ├── plugin_base.py     # 插件基类，数据类型定义
│   ├── formatter.py       # Waybar JSON 输出，Tooltip 渲染
│   ├── http_api.py        # 本地 HTTP API 服务器
│   └── plugins/
│       ├── claude.py      # Anthropic Claude
│       ├── cursor.py      # Cursor IDE
│       ├── copilot.py     # GitHub Copilot
│       ├── codex.py       # OpenAI Codex
│       ├── windsurf.py    # Windsurf
│       ├── gemini.py      # Google Gemini
│       ├── amp.py         # Amp
│       ├── kimi.py        # Kimi Code
│       ├── zai.py         # Z.ai
│       ├── minimax.py     # MiniMax
│       ├── jetbrains.py   # JetBrains AI Assistant
│       ├── opencode_go.py # OpenCode Go
│       └── factory.py     # Factory / Droid
├── examples/
│   ├── waybar-config.jsonc  # Waybar 配置示例
│   └── style.css            # Waybar 样式示例
├── install.sh
├── pyproject.toml
└── LICENSE
```

## 致谢

- [OpenUsage](https://github.com/robinebers/openusage) by [@robinebers](https://github.com/robinebers) — 原项目，本项目的所有 Provider 逻辑均移植自此
- 灵感来自 [CodexBar](https://github.com/steipete/CodexBar) by [@steipete](https://github.com/steipete)

## License

[MIT](LICENSE)
