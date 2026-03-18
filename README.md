<p align="center">
  <img src="logo.png" alt="Unturned Servers Logo" width="200"/>
</p>

<h1 align="center">astrbot_plugin_unturned_servers</h1>

<p align="center">AstrBot 插件 —— 查询 Unturned 游戏服务器实时状态和在线玩家信息。</p>

## 功能

- `/status` — 查询所有配置服务器的状态（地图、在线人数、VAC、延迟）
- `/players` — 查询所有配置服务器的在线玩家列表（玩家名、在线时长）

## 安装

将本插件目录放入 AstrBot 的插件目录下，AstrBot 会自动安装 `requirements.txt` 中的依赖（`python-a2s`）。

## 配置

在 AstrBot 管理面板中进入本插件的配置页面，可设置以下选项：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `servers` | text | 空 | 服务器列表，每行一个 |
| `query_timeout` | int | `5` | A2S 查询超时秒数 |

### 服务器填写格式

在 `servers` 文本框中，**每行一个服务器**，格式为：

```
名称,IP地址,查询端口
```

示例：

```
我的服务器,123.45.67.89,27016
朋友的服务器,98.76.54.32,27016
```

也可以省略名称，只写 IP 和端口：

```
123.45.67.89,27016
```

> **关于端口**：这里填写的是 Steam **查询端口（Query Port）**，不是游戏端口。Unturned 的查询端口一般是游戏端口 +1。例如游戏端口 `27015`，查询端口就是 `27016`。如果不确定，可以在服务器配置或面板中查看 Query Port。

## 命令示例

### `/status`

```
🎮 Unturned 服务器状态

[1] 我的服务器
  地图: PEI | 在线: 12/24
  VAC: ✓ | 延迟: 45ms
  状态: 🟢 在线

[2] 第二个服务器
  状态: 🔴 离线（连接超时）
```

### `/players`

```
👥 Unturned 在线玩家

[1] 我的服务器 (12/24)
  1. PlayerName - 2h 15m
  2. AnotherPlayer - 45m

[2] 第二个服务器 (0/24)
  暂无在线玩家
```

## 技术细节

- 使用 [python-a2s](https://github.com/Yepoleb/python-a2s) 库通过 Valve A2S（Steam Query）协议进行 UDP 查询
- 多服务器并行查询（`asyncio.gather`），单个服务器超时不影响其他结果
- 玩家列表按在线时长降序排列

## 依赖

- Python 3.10+
- [python-a2s](https://github.com/Yepoleb/python-a2s) >= 1.3.0
