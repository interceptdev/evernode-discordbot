import discord
from discord.ext import commands
import datetime
from config import Logger, ModLogChannelId, ServerLogChannelId, LogoUrl
import moderation_db

class LogsCog(commands.Cog):
    def __init__(self, Bot: commands.Bot):
        self.Bot = Bot

    def _log_embed(
        self,
        *,
        Title: str,
        Description: str = "",
        Color: discord.Color = discord.Color(0xff7f17),
        Author: discord.User | discord.Member | None = None,
        Footer: str | None = None,
    ) -> discord.Embed:
        Embed = discord.Embed(
            title=Title,
            description=Description,
            color=Color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        if Author:
            Embed.set_author(name=str(Author), icon_url=Author.display_avatar.url)
        Embed.set_footer(text=Footer or "Evernode Logs", icon_url=LogoUrl)
        return Embed

    async def _send_mod_log(self, Guild: discord.Guild, Embed: discord.Embed):
        Channel = Guild.get_channel(ModLogChannelId)
        if Channel is None:
            try:
                Channel = await self.Bot.fetch_channel(ModLogChannelId)
            except Exception:
                return
        try:
            await Channel.send(embed=Embed)
        except Exception as E:
            Logger.error(f"Failed to send mod log: {E}")

    async def _send_server_log(self, Guild: discord.Guild, Embed: discord.Embed):
        Channel = Guild.get_channel(ServerLogChannelId)
        if Channel is None:
            try:
                Channel = await self.Bot.fetch_channel(ServerLogChannelId)
            except Exception:
                return
        try:
            await Channel.send(embed=Embed)
        except Exception as E:
            Logger.error(f"Failed to send server log: {E}")

    @commands.Cog.listener()
    async def on_member_ban(self, Guild: discord.Guild, User: discord.User):
        Moderator = None
        Reason = "No reason provided"
        try:
            async for Entry in Guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if Entry.target and Entry.target.id == User.id:
                    Moderator = Entry.user
                    Reason = Entry.reason or Reason
                    break
        except Exception:
            pass

        Embed = self._log_embed(
            Title="🔨 Member Banned",
            Description=(
                f"**User:** {User.mention} (`{User}` · `{User.id}`)\n"
                f"**Moderator:** {Moderator.mention if Moderator else 'Unknown'}\n"
                f"**Reason:** {Reason}"
            ),
            Color=discord.Color.red(),
            Author=Moderator,
        )
        Embed.set_thumbnail(url=User.display_avatar.url)
        moderation_db.log_mod_action(
            ActionType="BAN",
            GuildId=Guild.id,
            ModeratorId=Moderator.id if Moderator else None,
            TargetId=User.id,
            Reason=Reason
        )
        await self._send_mod_log(Guild, Embed)

    @commands.Cog.listener()
    async def on_member_unban(self, Guild: discord.Guild, User: discord.User):
        Moderator = None
        Reason = "No reason provided"
        try:
            async for Entry in Guild.audit_logs(limit=5, action=discord.AuditLogAction.unban):
                if Entry.target and Entry.target.id == User.id:
                    Moderator = Entry.user
                    Reason = Entry.reason or Reason
                    break
        except Exception:
            pass

        Embed = self._log_embed(
            Title="🔓 Member Unbanned",
            Description=(
                f"**User:** {User.mention} (`{User}` · `{User.id}`)\n"
                f"**Moderator:** {Moderator.mention if Moderator else 'Unknown'}\n"
                f"**Reason:** {Reason}"
            ),
            Color=discord.Color.green(),
            Author=Moderator,
        )
        Embed.set_thumbnail(url=User.display_avatar.url)
        moderation_db.log_mod_action(
            ActionType="UNBAN",
            GuildId=Guild.id,
            ModeratorId=Moderator.id if Moderator else None,
            TargetId=User.id,
            Reason=Reason
        )
        await self._send_mod_log(Guild, Embed)

    @commands.Cog.listener()
    async def on_member_remove(self, Member: discord.Member):
        Guild = Member.guild
        Moderator = None
        Reason = None
        try:
            async for Entry in Guild.audit_logs(limit=5, action=discord.AuditLogAction.kick):
                if (
                    Entry.target
                    and Entry.target.id == Member.id
                    and (discord.utils.utcnow() - Entry.created_at).total_seconds() < 10
                ):
                    Moderator = Entry.user
                    Reason = Entry.reason or "No reason provided"
                    break
        except Exception:
            pass

        if Moderator is None:
            return

        Embed = self._log_embed(
            Title="👢 Member Kicked",
            Description=(
                f"**User:** {Member.mention} (`{Member}` · `{Member.id}`)\n"
                f"**Moderator:** {Moderator.mention}\n"
                f"**Reason:** {Reason}"
            ),
            Color=discord.Color.orange(),
            Author=Moderator,
        )
        Embed.set_thumbnail(url=Member.display_avatar.url)
        moderation_db.log_mod_action(
            ActionType="KICK",
            GuildId=Guild.id,
            ModeratorId=Moderator.id,
            TargetId=Member.id,
            Reason=Reason
        )
        await self._send_mod_log(Guild, Embed)

    @commands.Cog.listener()
    async def on_member_update(self, Before: discord.Member, After: discord.Member):
        Guild = After.guild

        if Before.timed_out_until != After.timed_out_until:
            Moderator = None
            Reason = "No reason provided"
            try:
                async for Entry in Guild.audit_logs(limit=5, action=discord.AuditLogAction.member_update):
                    if Entry.target and Entry.target.id == After.id:
                        Moderator = Entry.user
                        Reason = Entry.reason or Reason
                        break
            except Exception:
                pass

            if After.timed_out_until and After.timed_out_until > discord.utils.utcnow():
                UntilTs = int(After.timed_out_until.timestamp())
                Embed = self._log_embed(
                    Title="🔇 Member Timed Out",
                    Description=(
                        f"**User:** {After.mention} (`{After}` · `{After.id}`)\n"
                        f"**Moderator:** {Moderator.mention if Moderator else 'Unknown'}\n"
                        f"**Until:** <t:{UntilTs}:F> (<t:{UntilTs}:R>)\n"
                        f"**Reason:** {Reason}"
                    ),
                    Color=discord.Color.orange(),
                    Author=Moderator,
                )
            else:
                Embed = self._log_embed(
                    Title="🔊 Timeout Removed",
                    Description=(
                        f"**User:** {After.mention} (`{After}` · `{After.id}`)\n"
                        f"**Moderator:** {Moderator.mention if Moderator else 'Unknown'}\n"
                        f"**Reason:** {Reason}"
                    ),
                    Color=discord.Color.green(),
                    Author=Moderator,
                )
            Embed.set_thumbnail(url=After.display_avatar.url)
            if After.timed_out_until and After.timed_out_until > discord.utils.utcnow():
                moderation_db.log_mod_action(
                    ActionType="TIMEOUT",
                    GuildId=Guild.id,
                    ModeratorId=Moderator.id if Moderator else None,
                    TargetId=After.id,
                    Reason=Reason,
                    Details=f"Until: {After.timed_out_until.isoformat()}"
                )
            else:
                moderation_db.log_mod_action(
                    ActionType="TIMEOUT_REMOVE",
                    GuildId=Guild.id,
                    ModeratorId=Moderator.id if Moderator else None,
                    TargetId=After.id,
                    Reason=Reason
                )
            await self._send_mod_log(Guild, Embed)

        if Before.nick != After.nick:
            Embed = self._log_embed(
                Title="✏️ Nickname Changed",
                Description=(
                    f"**Member:** {After.mention} (`{After}` · `{After.id}`)\n"
                    f"**Before:** {Before.nick or '*None*'}\n"
                    f"**After:** {After.nick or '*None*'}"
                ),
                Color=discord.Color.blue(),
                Author=After,
            )
            Embed.set_thumbnail(url=After.display_avatar.url)
            await self._send_server_log(Guild, Embed)

        if Before.roles != After.roles:
            Added = set(After.roles) - set(Before.roles)
            Removed = set(Before.roles) - set(After.roles)
            Parts = []
            if Added:
                Parts.append("**Added:** " + ", ".join(R.mention for R in Added))
            if Removed:
                Parts.append("**Removed:** " + ", ".join(R.mention for R in Removed))
            Embed = self._log_embed(
                Title="🏷️ Member Roles Updated",
                Description=(
                    f"**Member:** {After.mention} (`{After}` · `{After.id}`)\n"
                    + "\n".join(Parts)
                ),
                Color=discord.Color.blue(),
                Author=After,
            )
            Embed.set_thumbnail(url=After.display_avatar.url)
            await self._send_mod_log(Guild, Embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, Channel: discord.abc.GuildChannel):
        Creator = None
        try:
            async for Entry in Channel.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_create):
                if Entry.target and Entry.target.id == Channel.id:
                    Creator = Entry.user
                    break
        except Exception:
            pass

        Embed = self._log_embed(
            Title="📁 Channel Created",
            Description=(
                f"**Channel:** {Channel.mention} (`{Channel.name}` · `{Channel.id}`)\n"
                f"**Type:** {str(Channel.type).replace('_', ' ').title()}\n"
                f"**Created by:** {Creator.mention if Creator else 'Unknown'}"
            ),
            Color=discord.Color.green(),
            Author=Creator,
        )
        await self._send_server_log(Channel.guild, Embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, Channel: discord.abc.GuildChannel):
        Deleter = None
        try:
            async for Entry in Channel.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                if Entry.target and Entry.target.id == Channel.id:
                    Deleter = Entry.user
                    break
        except Exception:
            pass

        Embed = self._log_embed(
            Title="🗑️ Channel Deleted",
            Description=(
                f"**Channel:** `#{Channel.name}` (`{Channel.id}`)\n"
                f"**Type:** {str(Channel.type).replace('_', ' ').title()}\n"
                f"**Deleted by:** {Deleter.mention if Deleter else 'Unknown'}"
            ),
            Color=discord.Color.red(),
            Author=Deleter,
        )
        await self._send_server_log(Channel.guild, Embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, Before: discord.abc.GuildChannel, After: discord.abc.GuildChannel):
        Changes = []
        if Before.name != After.name:
            Changes.append(f"**Name:** `{Before.name}` → `{After.name}`")
        if hasattr(Before, "topic") and hasattr(After, "topic"):
            if Before.topic != After.topic:
                Changes.append(f"**Topic:** {Before.topic or '*None*'} → {After.topic or '*None*'}")
        if hasattr(Before, "slowmode_delay") and hasattr(After, "slowmode_delay"):
            if Before.slowmode_delay != After.slowmode_delay:
                Changes.append(f"**Slowmode:** {Before.slowmode_delay}s → {After.slowmode_delay}s")
        if hasattr(Before, "nsfw") and hasattr(After, "nsfw"):
            if Before.nsfw != After.nsfw:
                Changes.append(f"**NSFW:** {Before.nsfw} → {After.nsfw}")

        if not Changes:
            return

        Editor = None
        try:
            async for Entry in After.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_update):
                if Entry.target and Entry.target.id == After.id:
                    Editor = Entry.user
                    break
        except Exception:
            pass

        Embed = self._log_embed(
            Title="🔧 Channel Updated",
            Description=(
                f"**Channel:** {After.mention} (`{After.id}`)\n"
                + "\n".join(Changes)
                + f"\n**Updated by:** {Editor.mention if Editor else 'Unknown'}"
            ),
            Color=discord.Color.gold(),
            Author=Editor,
        )
        await self._send_server_log(After.guild, Embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, Role: discord.Role):
        Creator = None
        try:
            async for Entry in Role.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_create):
                if Entry.target and Entry.target.id == Role.id:
                    Creator = Entry.user
                    break
        except Exception:
            pass

        Embed = self._log_embed(
            Title="🎨 Role Created",
            Description=(
                f"**Role:** {Role.mention} (`{Role.name}` · `{Role.id}`)\n"
                f"**Color:** `{Role.color}`\n"
                f"**Created by:** {Creator.mention if Creator else 'Unknown'}"
            ),
            Color=discord.Color.green(),
            Author=Creator,
        )
        await self._send_mod_log(Role.guild, Embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, Role: discord.Role):
        Deleter = None
        try:
            async for Entry in Role.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_delete):
                if Entry.target and Entry.target.id == Role.id:
                    Deleter = Entry.user
                    break
        except Exception:
            pass

        Embed = self._log_embed(
            Title="🗑️ Role Deleted",
            Description=(
                f"**Role:** `{Role.name}` (`{Role.id}`)\n"
                f"**Deleted by:** {Deleter.mention if Deleter else 'Unknown'}"
            ),
            Color=discord.Color.red(),
            Author=Deleter,
        )
        await self._send_mod_log(Role.guild, Embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, Before: discord.Role, After: discord.Role):
        Changes = []
        if Before.name != After.name:
            Changes.append(f"**Name:** `{Before.name}` → `{After.name}`")
        if Before.color != After.color:
            Changes.append(f"**Color:** `{Before.color}` → `{After.color}`")
        if Before.hoist != After.hoist:
            Changes.append(f"**Hoisted:** {Before.hoist} → {After.hoist}")
        if Before.mentionable != After.mentionable:
            Changes.append(f"**Mentionable:** {Before.mentionable} → {After.mentionable}")
        if Before.permissions != After.permissions:
            Changes.append("**Permissions updated**")

        if not Changes:
            return

        Editor = None
        try:
            async for Entry in After.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_update):
                if Entry.target and Entry.target.id == After.id:
                    Editor = Entry.user
                    break
        except Exception:
            pass

        Embed = self._log_embed(
            Title="🔧 Role Updated",
            Description=(
                f"**Role:** {After.mention} (`{After.id}`)\n"
                + "\n".join(Changes)
                + f"\n**Updated by:** {Editor.mention if Editor else 'Unknown'}"
            ),
            Color=discord.Color.gold(),
            Author=Editor,
        )
        await self._send_mod_log(After.guild, Embed)

    @commands.Cog.listener()
    async def on_member_join(self, Member: discord.Member):
        AccountAge = discord.utils.utcnow() - Member.created_at
        AgeStr = f"{AccountAge.days}d" if AccountAge.days > 0 else f"{int(AccountAge.total_seconds() // 3600)}h"
        CreatedTs = int(Member.created_at.timestamp())

        Embed = self._log_embed(
            Title="📥 Member Joined",
            Description=(
                f"**Member:** {Member.mention} (`{Member}` · `{Member.id}`)\n"
                f"**Account Created:** <t:{CreatedTs}:F> (<t:{CreatedTs}:R>)\n"
                f"**Account Age:** {AgeStr}\n"
                f"**Member Count:** {Member.guild.member_count}"
            ),
            Color=discord.Color.green(),
            Author=Member,
        )
        Embed.set_thumbnail(url=Member.display_avatar.url)
        await self._send_server_log(Member.guild, Embed)

    @commands.Cog.listener()
    async def on_raw_member_remove(self, Payload: discord.RawMemberRemoveEvent):
        User = Payload.user
        Guild = self.Bot.get_guild(Payload.guild_id)
        if Guild is None:
            return

        try:
            async for Entry in Guild.audit_logs(limit=5, action=discord.AuditLogAction.kick):
                if (
                    Entry.target
                    and Entry.target.id == User.id
                    and (discord.utils.utcnow() - Entry.created_at).total_seconds() < 10
                ):
                    return
        except Exception:
            pass
        try:
            async for Entry in Guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if (
                    Entry.target
                    and Entry.target.id == User.id
                    and (discord.utils.utcnow() - Entry.created_at).total_seconds() < 10
                ):
                    return
        except Exception:
            pass

        RolesStr = ", ".join(R.mention for R in getattr(User, "roles", [])[1:]) or "*None*"

        Embed = self._log_embed(
            Title="📤 Member Left",
            Description=(
                f"**Member:** {User.mention} (`{User}` · `{User.id}`)\n"
                f"**Roles:** {RolesStr}\n"
                f"**Member Count:** {Guild.member_count}"
            ),
            Color=discord.Color.red(),
            Author=User,
        )
        Embed.set_thumbnail(url=User.display_avatar.url)
        await self._send_server_log(Guild, Embed)

    @commands.Cog.listener()
    async def on_message_delete(self, Message: discord.Message):
        if Message.author.bot or not Message.guild:
            return

        Content = Message.content[:1024] if Message.content else "*No text content*"

        Embed = self._log_embed(
            Title="🗑️ Message Deleted",
            Description=(
                f"**Author:** {Message.author.mention} (`{Message.author}` · `{Message.author.id}`)\n"
                f"**Channel:** {Message.channel.mention}\n"
                f"**Content:**\n>>> {Content}"
            ),
            Color=discord.Color.red(),
            Author=Message.author,
        )
        if Message.attachments:
            AttList = "\n".join(f"[{A.filename}]({A.url})" for A in Message.attachments)
            Embed.add_field(name="Attachments", value=AttList[:1024], inline=False)
        await self._send_server_log(Message.guild, Embed)

    @commands.Cog.listener()
    async def on_message_edit(self, Before: discord.Message, After: discord.Message):
        if Before.author.bot or not Before.guild:
            return
        if Before.content == After.content:
            return

        BeforeContent = Before.content[:512] if Before.content else "*Empty*"
        AfterContent = After.content[:512] if After.content else "*Empty*"

        Embed = self._log_embed(
            Title="✏️ Message Edited",
            Description=(
                f"**Author:** {After.author.mention} (`{After.author}` · `{After.author.id}`)\n"
                f"**Channel:** {After.channel.mention}\n"
                f"[Jump to message]({After.jump_url})"
            ),
            Color=discord.Color.gold(),
            Author=After.author,
        )
        Embed.add_field(name="Before", value=f">>> {BeforeContent}", inline=False)
        Embed.add_field(name="After", value=f">>> {AfterContent}", inline=False)
        await self._send_server_log(After.guild, Embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, Messages: list[discord.Message]):
        if not Messages or not Messages[0].guild:
            return

        Guild = Messages[0].guild
        Channel = Messages[0].channel

        Embed = self._log_embed(
            Title="🗑️ Bulk Messages Deleted",
            Description=(
                f"**Channel:** {Channel.mention}\n"
                f"**Messages Deleted:** {len(Messages)}"
            ),
            Color=discord.Color.red(),
        )
        await self._send_server_log(Guild, Embed)

    @commands.Cog.listener()
    async def on_guild_update(self, Before: discord.Guild, After: discord.Guild):
        Changes = []
        if Before.name != After.name:
            Changes.append(f"**Name:** `{Before.name}` → `{After.name}`")
        if Before.icon != After.icon:
            Changes.append("**Icon:** Updated")
        if Before.banner != After.banner:
            Changes.append("**Banner:** Updated")
        if Before.verification_level != After.verification_level:
            Changes.append(f"**Verification Level:** {Before.verification_level} → {After.verification_level}")

        if not Changes:
            return

        Embed = self._log_embed(
            Title="🏠 Server Updated",
            Description="\n".join(Changes),
            Color=discord.Color.gold(),
        )
        await self._send_server_log(After, Embed)

async def setup(Bot: commands.Bot):
    await Bot.add_cog(LogsCog(Bot))
