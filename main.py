import asyncio
import re

import a2s
from astrbot.api import star, logger, AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent


@star.register("astrbot_plugin_unturned_servers", "admin", "查询 Unturned 游戏服务器状态和在线玩家信息", "0.1.0")
class Main(star.Star):
    def __init__(self, context: star.Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    def _get_servers(self) -> list:
        """从插件配置中解析服务器列表

        配置格式为纯文本，每行一个服务器：名称,IP,端口
        例如：
            我的服务器,123.45.67.89,27015
            朋友的服务器,98.76.54.32,27015
        """
        raw = self.config.get("servers", "")
        if raw is None:
            return []
        if not isinstance(raw, str):
            raw = str(raw)
        raw = raw.strip()
        if not raw:
            return []
        # 兼容面板可能将换行转义为字面 \n
        # Support literal "\n" produced by some admin panels.
        result = []
        for line in self._split_server_lines(raw):
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 3:
                name, host, port_str = parts
            elif len(parts) == 2:
                # 省略名称时，用 host:port 作为名称
                host, port_str = parts
                name = f"{host}:{port_str}"
            else:
                logger.warning(f"跳过无法解析的服务器配置行: {line}")
                continue
            try:
                port = int(port_str)
            except ValueError:
                logger.warning(f"端口不是数字，跳过: {line}")
                continue
            result.append({"name": name, "host": host, "port": port})
        return result

    @staticmethod
    def _split_server_lines(raw: str) -> list[str]:
        """Split server config lines while preserving literal '\\n' in names."""
        if "\n" in raw or "\r" in raw:
            return raw.splitlines()
        if "\\n" not in raw and "\\r\\n" not in raw:
            return [raw]

        escaped = raw.replace("\\r\\n", "\\n")
        chunks = escaped.split("\\n")
        lines = []
        buffer = []

        for chunk in chunks:
            buffer.append(chunk)
            candidate = "\\n".join(buffer).strip()
            if Main._looks_like_server_line(candidate):
                lines.append(candidate)
                buffer = []

        if buffer:
            lines.append("\\n".join(buffer).strip())
        return lines

    @staticmethod
    def _looks_like_server_line(line: str) -> bool:
        """Check whether the buffered text already forms one server entry."""
        parts = [part.strip() for part in line.split(",")]
        if len(parts) not in (2, 3):
            return False
        return bool(re.fullmatch(r"\d+", parts[-1]))

    def _get_timeout(self) -> float:
        """从插件配置中读取超时秒数"""
        return self.config.get("query_timeout", 5)

    async def _query_server_info(self, host: str, port: int, timeout: float):
        """用 a2s.ainfo() 查询单个服务器信息

        Args:
            host: 服务器地址
            port: 查询端口（直接使用，不做偏移）
            timeout: 超时秒数

        Returns:
            a2s.SourceInfo 或 None（超时/失败时）
        """
        try:
            info = await a2s.ainfo(
                (host, port),
                timeout=timeout
            )
            return info
        except Exception as e:
            logger.warning(f"查询服务器 {host}:{port} 信息失败: {e}")
            return None

    async def _query_server_players(self, host: str, port: int, timeout: float):
        """用 a2s.aplayers() 查询单个服务器玩家列表

        Args:
            host: 服务器地址
            port: 查询端口（直接使用，不做偏移）
            timeout: 超时秒数

        Returns:
            list[a2s.Player] 或 None（超时/失败时）
        """
        try:
            players = await a2s.aplayers(
                (host, port),
                timeout=timeout
            )
            return players
        except Exception as e:
            logger.warning(f"查询服务器 {host}:{port} 玩家失败: {e}")
            return None

    async def _query_server_snapshot(self, host: str, port: int, timeout: float):
        """Query info first, then query players only when the server is online."""
        info = await self._query_server_info(host, port, timeout)
        if info is None:
            return None, None
        players = await self._query_server_players(host, port, timeout)
        return info, players

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """将秒数格式化为可读时间字符串"""
        total = int(seconds)
        if total < 0:
            return "未知"
        hours, remainder = divmod(total, 3600)
        minutes, _ = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    @filter.command("status")
    async def status(self, event: AstrMessageEvent):
        """查询所有配置服务器的状态"""
        servers = self._get_servers()
        timeout = self._get_timeout()

        if not servers:
            yield event.plain_result(
                "⚠ 未配置任何服务器，请在插件配置中添加服务器信息。"
            )
            return

        # 并行查询所有服务器
        tasks = [
            self._query_server_info(srv["host"], srv["port"], timeout)
            for srv in servers
        ]
        results = await asyncio.gather(*tasks)

        lines = ["🎮 Unturned 服务器状态", ""]
        for i, (srv, result) in enumerate(zip(servers, results), 1):
            name = srv["name"]
            if result is None:
                lines.append(f"[{i}] {name}")
                lines.append("  状态: 🔴 离线（连接超时）")
            else:
                vac = "✓" if result.vac_enabled else "✗"
                lines.append(f"[{i}] {name}")
                lines.append(
                    f"  地图: {result.map_name} | "
                    f"在线: {result.player_count}/{result.max_players}"
                )
                lines.append(f"  VAC: {vac} | 延迟: {int(result.ping * 1000)}ms")
                lines.append("  状态: 🟢 在线")
            lines.append("")

        yield event.plain_result("\n".join(lines).strip())

    @filter.command("players")
    async def players(self, event: AstrMessageEvent):
        """查询所有配置服务器的在线玩家"""
        servers = self._get_servers()
        timeout = self._get_timeout()

        if not servers:
            yield event.plain_result(
                "⚠ 未配置任何服务器，请在插件配置中添加服务器信息。"
            )
            return

        # Query servers in parallel, but keep info/players sequential per server.
        tasks = [
            self._query_server_snapshot(srv["host"], srv["port"], timeout)
            for srv in servers
        ]
        results = await asyncio.gather(*tasks)

        lines = ["👥 Unturned 在线玩家", ""]
        for i, (srv, (info, plist)) in enumerate(zip(servers, results), 1):
            name = srv["name"]

            if info is None:
                lines.append(f"[{i}] {name}")
                lines.append("  状态: 🔴 离线（连接超时）")
            else:
                count = info.player_count
                max_p = info.max_players
                lines.append(f"[{i}] {name} ({count}/{max_p})")

                if plist is None or not plist:
                    lines.append("  暂无在线玩家")
                else:
                    # 按在线时间降序排列
                    sorted_players = sorted(
                        plist, key=lambda p: p.duration, reverse=True
                    )
                    for j, player in enumerate(sorted_players, 1):
                        pname = player.name if player.name else "未知玩家"
                        duration = self._format_duration(player.duration)
                        lines.append(f"  {j}. {pname} - {duration}")

            lines.append("")

        yield event.plain_result("\n".join(lines).strip())
