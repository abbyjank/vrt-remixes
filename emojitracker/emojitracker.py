import math
import sys
from collections import OrderedDict

import discord
import tabulate
from redbot.core import Config, commands
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu


class BoundedCache:
    """A simple FIFO cache to prevent unbounded memory growth."""
    def __init__(self, max_size: int = 50000):
        self.max_size = max_size
        self.cache = OrderedDict()

    def contains_and_add(self, uid: int, mid: int, emoji: str) -> bool:
        key = (uid, mid, emoji)
        if key in self.cache:
            # Move to end to refresh usage (LRU behavior)
            self.cache.move_to_end(key)
            return True
        self.cache[key] = True
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)  # Remove oldest entry
        return False


class EmojiTracker(commands.Cog):
    """
    Track custom emojis and view usage statistics.

    This cog tracks reactions added to other users' messages, 
    including reactions within Threads.
    """

    __author__ = "[vertyco](https://github.com/vertyco/vrt-cogs)"
    __version__ = "0.5.0"

    def format_help_for_context(self, ctx):
        helpcmd = super().format_help_for_context(ctx)
        return f"{helpcmd}\nCog Version: {self.__version__}\nAuthor: {self.__author__}"

    async def red_delete_data_for_user(self, *, requester, user_id: int):
        """No data to delete"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 117, force_registration=True)
        default_global = {"blacklist": []}
        default_guild = {
            "users": {},
            "self_count": False  # Default: Don't count self-reactions
        }
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        
        # Bounded cache to prevent memory leaks (Max 50k entries)
        self.reacted_cache = BoundedCache(max_size=50000)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # 1. Basic Filters
        if payload.user_id == self.bot.user.id or not payload.guild_id:
            return

        # 2. Custom Emoji Check
        if not payload.emoji.is_custom_emoji():
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild or guild.id in await self.config.blacklist():
            return

        user = payload.member
        if not user or user.bot:
            return

        # 3. Self-Reaction Check (Toggleable & Optimized)
        self_count = await self.config.guild(guild).self_count()
        if not self_count:
            # Check bot's message cache first to save API request
            message = discord.utils.get(self.bot.cached_messages, id=payload.message_id)
            if message:
                if message.author.id == payload.user_id:
                    return
            else:
                # Cache miss: Resolve channel and fetch message
                chan = guild.get_channel_or_thread(payload.channel_id)
                if not chan:
                    try:
                        chan = await self.bot.fetch_channel(payload.channel_id)
                    except (discord.NotFound, discord.Forbidden):
                        return
                try:
                    message = await chan.fetch_message(payload.message_id)
                    if message.author.id == payload.user_id:
                        return
                except (discord.HTTPException, discord.Forbidden):
                    return

        emoji = str(payload.emoji)
        uid = str(user.id)

        # 4. Anti-Spam Cache Logic (using bounded cache)
        if self.reacted_cache.contains_and_add(user.id, payload.message_id, emoji):
            return

        # 5. Save to Config
        async with self.config.guild(guild).users() as users:
            if uid not in users:
                users[uid] = {}
            users[uid][emoji] = users[uid].get(emoji, 0) + 1

    @commands.command(name="selfcount")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def toggle_self_count(self, ctx):
        """Toggle whether users reacting to their own messages increases the count"""
        current = await self.config.guild(ctx.guild).self_count()
        await self.config.guild(ctx.guild).self_count.set(not current)
        status = "now" if not current else "no longer"
        await ctx.send(f"Self-reactions are {status} being counted.")

    @commands.command(name="emojilb")
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def emoji_lb(self, ctx):
        """View the emoji leaderboard (includes unused emojis)"""
        users = await self.config.guild(ctx.guild).users()
        stored_counts = {}
        for user_data in users.values():
            for emoji_str, count in user_data.items():
                stored_counts[emoji_str] = stored_counts.get(emoji_str, 0) + count

        guild_emoji_data = []
        for emoji_obj in ctx.guild.emojis:
            count = stored_counts.get(str(emoji_obj), 0)
            guild_emoji_data.append((str(emoji_obj), count))

        # Sort by count descending (-x[1]), then by emoji string ascending (x[0])
        sorted_emojis = sorted(guild_emoji_data, key=lambda x: (-x[1], x[0]))
        if not sorted_emojis:
            return await ctx.send("This server has no custom emojis!")

        total_reactions = sum(count for _, count in guild_emoji_data)
        pages = math.ceil(len(sorted_emojis) / 10)
        embeds = []
        for p in range(pages):
            start, stop = p * 10, (p + 1) * 10
            chunk = sorted_emojis[start:stop]
            top = "\n".join([f"{e} — `{c}`" for e, c in chunk])
            embed = discord.Embed(
                title=f"Emoji Leaderboard: {ctx.guild.name}",
                description=f"Total Custom Reactions: `{total_reactions:,}`\n\n{top}",
                color=await ctx.embed_color()
            )
            embed.set_footer(text=f"Page {p + 1}/{pages}")
            embeds.append(embed)
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    @commands.command(name="emojipurge", aliases=["leastused"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def emoji_purge_list(self, ctx):
        """Find emojis with the lowest usage to free up slots"""
        users = await self.config.guild(ctx.guild).users()
        stored_counts = {}
        for user_data in users.values():
            for emoji_str, count in user_data.items():
                stored_counts[emoji_str] = stored_counts.get(emoji_str, 0) + count

        guild_emoji_data = []
        for emoji_obj in ctx.guild.emojis:
            count = stored_counts.get(str(emoji_obj), 0)
            guild_emoji_data.append((emoji_obj, count))

        sorted_emojis = sorted(guild_emoji_data, key=lambda x: (x[1], x[0].name))
        if not sorted_emojis:
            return await ctx.send("This server has no custom emojis.")

        pages = math.ceil(len(sorted_emojis) / 15)
        embeds = []
        for p in range(pages):
            start, stop = p * 15, (p + 1) * 15
            chunk = sorted_emojis[start:stop]
            list_text = "\n".join([f"{obj} `{obj.name}` — **{count}**" for obj, count in chunk])
            embed = discord.Embed(
                title="Least Used Emojis (Purge Candidates)",
                description=f"Sorted by lowest usage.\n\n{list_text}",
                color=discord.Color.red()
            )
            embed.set_footer(text=f"Page {p + 1}/{pages}")
            embeds.append(embed)
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    @commands.command(name="reactlb")
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def reaction_lb(self, ctx):
        """View user leaderboard for most custom emojis added"""
        users = await self.config.guild(ctx.guild).users()
        lb = {}
        total_reactions = 0
        for uid, data in users.items():
            user = ctx.guild.get_member(int(uid)) or self.bot.get_user(int(uid))
            name = user.name if user else f"Unknown({uid})"
            user_total = sum(data.values())
            lb[name] = user_total
            total_reactions += user_total

        sorted_reactions = sorted(lb.items(), key=lambda x: x[1], reverse=True)
        if not sorted_reactions:
            return await ctx.send("No reactions saved yet!")

        pages = math.ceil(len(sorted_reactions) / 10)
        embeds = []
        for p in range(pages):
            start, stop = p * 10, (p + 1) * 10
            table = [[count, name] for name, count in sorted_reactions[start:stop]]
            top = tabulate.tabulate(table, tablefmt="presto")
            embed = discord.Embed(
                title="User Reaction Leaderboard",
                description=f"Total Custom Reactions: `{total_reactions:,}`\n```py\n{top}\n```",
                color=await ctx.embed_color()
            )
            embed.set_footer(text=f"Page {p + 1}/{pages}")
            embeds.append(embed)
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    @commands.command(name="ignoreguild", aliases=["ignoreserver"])
    @commands.is_owner()
    async def blacklist_guild(self, ctx, guild_id: int):
        """Add/Remove a guild from the blacklist"""
        async with self.config.blacklist() as bl:
            if guild_id in bl:
                bl.remove(guild_id)
                await ctx.send(f"Guild {guild_id} removed from the blacklist")
            else:
                bl.append(guild_id)
                await ctx.send(f"Guild {guild_id} added to the blacklist")

    @commands.command(name="viewblacklist")
    @commands.is_owner()
    @commands.bot_has_permissions(embed_links=True)
    async def view_settings(self, ctx):
        """View EmojiTracker Blacklist"""
        bl = await self.config.blacklist()
        blacklist = ""
        for guild_id in bl:
            blacklist += f"{guild_id}\n"
        if not blacklist:
            return await ctx.send("No guild ID's have been added to the blacklist")
        embed = discord.Embed(title="Emoji Tracker Blacklist", description=f"```py\n{blacklist}\n```")
        await ctx.send(embed=embed)

    @commands.command(name="resetreacts")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def reset_reactions(self, ctx):
        """Reset reaction data for this guild"""
        await self.config.guild(ctx.guild).clear()
        await ctx.tick()

    @commands.command(name="emojitrackercache", aliases=["etc"])
    @commands.is_owner()
    async def get_reaction_cache(self, ctx):
        """Get the size of EmojiTracker cache"""
        size = sys.getsizeof(self.reacted_cache.cache)
        if size > 1000000:
            formatted, inc = round(size / 1000000, 2), "MB"
        elif size > 1000:
            formatted, inc = round(size / 1000, 2), "KB"
        else:
            formatted, inc = size, "Bytes"
        await ctx.send(f"EmojiTracker Cache Size: `{formatted} {inc}` (Max items: {self.reacted_cache.max_size})")
