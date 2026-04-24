from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging
import os
from time import monotonic
from typing import Any

from app.discord_bridge.api_client import ApiClientError, HttpApiClient
from app.discord_bridge.config import BridgeConfig
from app.discord_bridge.policy import CommandContext
from app.discord_bridge.schedule_trigger_parser import ScheduleTriggerParser
from app.discord_bridge.service import BridgeService
from app.discord_bridge.state_store import DeliveryStateStore

LOGGER = logging.getLogger(__name__)


class DiscordTransport:
    def __init__(self, bot: Any) -> None:
        self._bot = bot

    async def send_channel_message(self, channel_id: int, content: str | None = None, embed: dict | None = None) -> None:
        channel = self._bot.get_channel(channel_id)
        if channel is None:
            channel = await self._bot.fetch_channel(channel_id)

        if embed is None:
            await channel.send(content or "")
            return

        discord_embed = _to_discord_embed(embed, self._bot.discord_module)
        await channel.send(content=content, embed=discord_embed)


class StockAgentDiscordBot:
    def __init__(self, config: BridgeConfig) -> None:
        try:
            import discord
            from discord import app_commands
            from discord.ext import commands
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "discord.py is required to run Discord bridge. Install optional dependencies first."
            ) from exc

        intents = discord.Intents.default()
        bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents, application_id=config.application_id)
        bot.discord_module = discord

        self._discord = discord
        self._app_commands = app_commands
        self._bot = bot
        self._config = config
        self._jobs: set[asyncio.Task] = set()
        self._watcher_task: asyncio.Task | None = None
        self._watcher_last_error_key: str | None = None
        self._watcher_last_error_at: float = 0.0

        api_client = HttpApiClient(config.api_base_url, timeout_seconds=config.http_timeout_seconds)
        state_store = DeliveryStateStore(config.delivery_state_path)
        transport = DiscordTransport(bot)
        self._service = BridgeService(config=config, api_client=api_client, transport=transport, state_store=state_store)
        self._schedule_trigger_parser = ScheduleTriggerParser(
            timezone_default=os.getenv("TIMEZONE", "America/New_York")
        )

        self._register_commands()

        @self._bot.event
        async def on_ready() -> None:
            await self._on_ready()

    def run(self) -> None:
        self._bot.run(self._config.bot_token)

    async def _on_ready(self) -> None:
        guild = self._discord.Object(id=self._config.guild_id)
        await self._bot.tree.sync(guild=guild)
        LOGGER.info("Discord command tree synced for guild=%s", self._config.guild_id)

        if self._watcher_task is None or self._watcher_task.done():
            self._watcher_task = asyncio.create_task(self._watch_schedule_results_loop())

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coro)
        self._jobs.add(task)
        task.add_done_callback(self._jobs.discard)

    def _context_from_interaction(self, interaction) -> CommandContext:
        role_ids: set[int] = set()
        user = interaction.user
        if hasattr(user, "roles"):
            role_ids = {int(role.id) for role in user.roles}
        return CommandContext(channel_id=int(interaction.channel_id), user_id=int(user.id), role_ids=role_ids)

    def _register_commands(self) -> None:
        guild = self._discord.Object(id=self._config.guild_id)

        @self._bot.tree.command(name="run", description="Run analysis prompt", guild=guild)
        async def run_command(interaction, prompt: str) -> None:
            context = self._context_from_interaction(interaction)
            try:
                allowed, reason = self._service.policy.authorize_run(context)
                if not allowed:
                    await interaction.response.send_message(f"Denied: {reason}")
                    return
                await interaction.response.send_message("ACK: run accepted, processing now...")
            except Exception as exc:
                await interaction.response.send_message(f"Failed to validate command: {exc}")
                return

            async def _task() -> None:
                try:
                    await self._service.execute_run(prompt=prompt, context=context)
                except Exception as exc:
                    await self._service.send_text_message(
                        self._config.result_channel_id,
                        _friendly_run_error_message(exc),
                    )

            self._spawn(_task())

        schedule_group = self._app_commands.Group(name="schedule", description="Manage schedules")

        @schedule_group.command(name="create", description="Create a schedule")
        async def schedule_create(
            interaction,
            name: str,
            task_input: str,
            trigger: str,
        ) -> None:
            context = self._context_from_interaction(interaction)
            deferred = False
            try:
                allowed, reason = self._service.policy.authorize_schedule(context)
                if not allowed:
                    await interaction.response.send_message(f"Denied: {reason}")
                    return
                await interaction.response.defer(thinking=True)
                deferred = True
                # Parser may call LLM provider; run in thread to avoid blocking bot event loop.
                parsed = await asyncio.to_thread(self._schedule_trigger_parser.parse, trigger)
                payload = {
                    "name": name,
                    "task_input": task_input,
                    **parsed.model_dump(),
                }
                schedule = await self._service.create_schedule(payload=payload, context=context)
                await interaction.followup.send(
                    (
                        f"Schedule created: id={schedule.get('id')} name={schedule.get('name')} "
                        f"trigger={schedule.get('trigger_type')} timezone={schedule.get('timezone')}"
                    )
                )
            except (PermissionError, ValueError, ApiClientError) as exc:
                message = f"Schedule create failed: {exc}"
                if deferred or interaction.response.is_done():
                    await interaction.followup.send(message)
                    return
                await interaction.response.send_message(message)

        @schedule_group.command(name="list", description="List schedules")
        async def schedule_list(interaction) -> None:
            context = self._context_from_interaction(interaction)
            try:
                items = await self._service.list_schedules(context=context)
                embed = self._service.build_schedule_list_embed(items)
                await interaction.response.send_message(embed=_to_discord_embed(embed, self._discord))
            except (PermissionError, ApiClientError) as exc:
                await interaction.response.send_message(f"Schedule list failed: {exc}")

        @schedule_group.command(name="cancel", description="Cancel schedule by id or name")
        async def schedule_cancel(interaction, target: str) -> None:
            context = self._context_from_interaction(interaction)
            try:
                result = await self._service.cancel_schedule(target=target, context=context)
                await interaction.response.send_message(f"Schedule cancel result: {result}")
            except (PermissionError, ValueError, ApiClientError) as exc:
                await interaction.response.send_message(f"Schedule cancel failed: {exc}")

        @schedule_group.command(name="pause", description="Pause schedule by id or name")
        async def schedule_pause(interaction, target: str) -> None:
            context = self._context_from_interaction(interaction)
            try:
                result = await self._service.pause_schedule(target=target, context=context)
                await interaction.response.send_message(f"Schedule paused: id={result.get('id')} enabled={result.get('enabled')}")
            except (PermissionError, ValueError, ApiClientError) as exc:
                await interaction.response.send_message(f"Schedule pause failed: {exc}")

        @schedule_group.command(name="resume", description="Resume schedule by id or name")
        async def schedule_resume(interaction, target: str) -> None:
            context = self._context_from_interaction(interaction)
            try:
                result = await self._service.resume_schedule(target=target, context=context)
                await interaction.response.send_message(f"Schedule resumed: id={result.get('id')} enabled={result.get('enabled')}")
            except (PermissionError, ValueError, ApiClientError) as exc:
                await interaction.response.send_message(f"Schedule resume failed: {exc}")

        @schedule_group.command(name="run-once", description="Run schedule once by id or name")
        async def schedule_run_once(interaction, target: str) -> None:
            context = self._context_from_interaction(interaction)
            try:
                allowed, reason = self._service.policy.authorize_schedule(context)
                if not allowed:
                    await interaction.response.send_message(f"Denied: {reason}")
                    return
                await interaction.response.send_message("ACK: run-once accepted, result will be posted to analyst channel.")
            except Exception as exc:
                await interaction.response.send_message(f"Failed to validate command: {exc}")
                return

            async def _task() -> None:
                try:
                    result = await self._service.run_schedule_once(target=target, context=context)
                    await self._service.send_text_message(
                        context.channel_id,
                        (
                            f"Schedule run-once completed: task_id={result.get('task_id')} "
                            f"status={result.get('status')} (analysis posted to analyst channel)"
                        ),
                    )
                except Exception as exc:
                    await self._service.send_text_message(context.channel_id, f"Schedule run-once failed: {exc}")

            self._spawn(_task())

        self._bot.tree.add_command(schedule_group, guild=guild)

    async def _watch_schedule_results_loop(self) -> None:
        while not self._bot.is_closed():
            try:
                delivered = await self._service.poll_scheduled_results()
                if delivered:
                    LOGGER.info("Delivered %s scheduled task result(s) to analyst channel", delivered)
                self._watcher_last_error_key = None
                self._watcher_last_error_at = 0.0
            except Exception as exc:
                self._log_watcher_error(exc)
            await asyncio.sleep(self._config.task_watch_interval_seconds)

    def _log_watcher_error(self, exc: Exception) -> None:
        # Avoid spamming same stack trace every poll interval when API is temporarily down.
        now = monotonic()
        error_key = f"{type(exc).__name__}:{exc}"
        if error_key == self._watcher_last_error_key and (now - self._watcher_last_error_at) < 60:
            return
        self._watcher_last_error_key = error_key
        self._watcher_last_error_at = now
        LOGGER.warning("Scheduled result polling failed: %s", error_key)

def _friendly_run_error_message(exc: Exception) -> str:
    if isinstance(exc, ApiClientError) and exc.status_code == 409:
        return (
            "Run failed: runner is busy. 当前已有任务在执行（单会话保护）。"
            "请稍后重试，或等待 analyst 频道结果回传后再发起新 run。"
        )
    return f"Run failed: {exc}"


def _to_discord_embed(embed_payload: dict, discord_module):
    embed = discord_module.Embed(
        title=embed_payload.get("title"),
        description=embed_payload.get("description"),
        color=int(embed_payload.get("color", 0x1F8B4C)),
    )
    for item in embed_payload.get("fields", []):
        embed.add_field(
            name=str(item.get("name", "-")),
            value=str(item.get("value", "-")),
            inline=bool(item.get("inline", False)),
        )
    return embed
