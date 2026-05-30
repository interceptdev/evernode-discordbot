import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import re
from typing import Optional, Literal
from utils.embed import create_agency_embed
import moderation_db
from config import Logger

def check_hierarchy(Moderator: discord.Member, Target: discord.Member) -> bool:
    if Target.guild.owner == Target:
        return False
    if Moderator == Target:
        return False
    if Moderator.guild.owner == Moderator:
        return True
    return Moderator.top_role > Target.top_role

def check_bot_hierarchy(Guild: discord.Guild, Target: discord.Member) -> bool:
    if Guild.owner == Target:
        return False
    return Guild.me.top_role > Target.top_role

def parse_duration(DurationStr: str) -> Optional[datetime.timedelta]:
    Match = re.match(r"^(\d+)([smhdw])$", DurationStr.lower().strip())
    if not Match:
        return None
    Val = int(Match.group(1))
    Unit = Match.group(2)
    if Unit == 's':
        return datetime.timedelta(seconds=Val)
    elif Unit == 'm':
        return datetime.timedelta(minutes=Val)
    elif Unit == 'h':
        return datetime.timedelta(hours=Val)
    elif Unit == 'd':
        return datetime.timedelta(days=Val)
    elif Unit == 'w':
        return datetime.timedelta(weeks=Val)
    return None

class ModerationCog(commands.Cog):
    def __init__(self, Bot: commands.Bot):
        self.Bot = Bot
        self.unban_loop.start()

    def cog_unload(self):
        self.unban_loop.cancel()

    @tasks.loop(seconds=10)
    async def unban_loop(self):
        try:
            Expired = moderation_db.get_expired_tempbans()
            for Ban in Expired:
                Guild = self.Bot.get_guild(Ban["guild_id"])
                if Guild:
                    try:
                        User = await self.Bot.fetch_user(Ban["user_id"])
                        await Guild.unban(User, reason="Tempban expired")
                    except discord.NotFound:
                        pass
                    except Exception as E:
                        Logger.error(f"Failed to auto-unban user {Ban['user_id']} in guild {Ban['guild_id']}: {E}")
                moderation_db.remove_tempban(Ban["user_id"], Ban["guild_id"])
        except Exception as E:
            Logger.error(f"Error in tempban unban loop: {E}", exc_info=True)

    @unban_loop.before_loop
    async def before_unban_loop(self):
        await self.Bot.wait_until_ready()

    @app_commands.command(name="ban", description="Ban a user from the server.")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member="The member to ban", reason="Reason for the ban", delete_messages_days="Days of message history to delete (0-7)")
    async def ban_slash(self, Interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = "No reason provided", delete_messages_days: Optional[int] = 0) -> None:
        if not check_hierarchy(Interaction.user, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ You cannot ban this user because they have a higher or equal role than you.", Color=discord.Color.red()), ephemeral=True)
            return
        if not check_bot_hierarchy(Interaction.guild, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ I cannot ban this user because they have a higher or equal role than me.", Color=discord.Color.red()), ephemeral=True)
            return

        DeleteSeconds = delete_messages_days * 86400 if delete_messages_days else 0
        try:
            DmEmbed = create_agency_embed(
                Title=f"You have been banned from {Interaction.guild.name}",
                Description=f"**Reason:** {reason}",
                Color=discord.Color.red()
            )
            await member.send(embed=DmEmbed)
        except Exception:
            pass

        try:
            await member.ban(reason=f"Banned by {Interaction.user.name}: {reason}", delete_message_seconds=DeleteSeconds)
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"✅ **{member.name}** was successfully banned.\n**Reason:** {reason}", Color=discord.Color.green()))
        except Exception as E:
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"❌ Failed to ban user: {E}", Color=discord.Color.red()), ephemeral=True)

    @app_commands.command(name="tempban", description="Temporarily ban a user from the server.")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member="The member to ban", duration="Duration (e.g. 30m, 12h, 3d)", reason="Reason for the ban")
    async def tempban_slash(self, Interaction: discord.Interaction, member: discord.Member, duration: str, reason: Optional[str] = "No reason provided") -> None:
        if not check_hierarchy(Interaction.user, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ You cannot ban this user because they have a higher or equal role than you.", Color=discord.Color.red()), ephemeral=True)
            return
        if not check_bot_hierarchy(Interaction.guild, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ I cannot ban this user because they have a higher or equal role than me.", Color=discord.Color.red()), ephemeral=True)
            return

        Td = parse_duration(duration)
        if not Td:
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ Invalid duration format. Use formats like `10m` (minutes), `1h` (hours), `5d` (days).", Color=discord.Color.red()), ephemeral=True)
            return

        UnbanTime = datetime.datetime.now() + Td
        try:
            DmEmbed = create_agency_embed(
                Title=f"You have been temporarily banned from {Interaction.guild.name}",
                Description=f"**Duration:** {duration}\n**Reason:** {reason}",
                Color=discord.Color.red()
            )
            await member.send(embed=DmEmbed)
        except Exception:
            pass

        try:
            await member.ban(reason=f"Tempban by {Interaction.user.name} for {duration}: {reason}", delete_message_seconds=0)
            moderation_db.add_tempban(member.id, Interaction.guild.id, UnbanTime)
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"✅ **{member.name}** was temporarily banned for **{duration}**.\n**Reason:** {reason}", Color=discord.Color.green()))
        except Exception as E:
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"❌ Failed to tempban user: {E}", Color=discord.Color.red()), ephemeral=True)

    @app_commands.command(name="unban", description="Unban a user by their user ID.")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(user_id="The unique Discord ID of the user", reason="Reason for the unban")
    async def unban_slash(self, Interaction: discord.Interaction, user_id: str, reason: Optional[str] = "No reason provided") -> None:
        try:
            Uid = int(user_id)
        except ValueError:
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ Invalid User ID. Must be a numeric ID.", Color=discord.Color.red()), ephemeral=True)
            return

        try:
            User = await self.Bot.fetch_user(Uid)
            await Interaction.guild.unban(User, reason=f"Unbanned by {Interaction.user.name}: {reason}")
            moderation_db.remove_tempban(Uid, Interaction.guild.id)
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"✅ **{User.name}** was successfully unbanned.\n**Reason:** {reason}", Color=discord.Color.green()))
        except discord.NotFound:
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ Banned user not found. Verify the ID is correct.", Color=discord.Color.red()), ephemeral=True)
        except Exception as E:
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"❌ Failed to unban user: {E}", Color=discord.Color.red()), ephemeral=True)

    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="The member to kick", reason="Reason for the kick")
    async def kick_slash(self, Interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = "No reason provided") -> None:
        if not check_hierarchy(Interaction.user, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ You cannot kick this user because they have a higher or equal role than you.", Color=discord.Color.red()), ephemeral=True)
            return
        if not check_bot_hierarchy(Interaction.guild, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ I cannot kick this user because they have a higher or equal role than me.", Color=discord.Color.red()), ephemeral=True)
            return

        try:
            DmEmbed = create_agency_embed(
                Title=f"You have been kicked from {Interaction.guild.name}",
                Description=f"**Reason:** {reason}",
                Color=discord.Color.red()
            )
            await member.send(embed=DmEmbed)
        except Exception:
            pass

        try:
            await member.kick(reason=f"Kicked by {Interaction.user.name}: {reason}")
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"✅ **{member.name}** was successfully kicked.\n**Reason:** {reason}", Color=discord.Color.green()))
        except Exception as E:
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"❌ Failed to kick user: {E}", Color=discord.Color.red()), ephemeral=True)

    @app_commands.command(name="timeout", description="Timeout/mute a member in the server.")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="The member to timeout", duration="Duration (e.g. 10m, 1h, 1d)", reason="Reason for the timeout")
    async def timeout_slash(self, Interaction: discord.Interaction, member: discord.Member, duration: str, reason: Optional[str] = "No reason provided") -> None:
        if not check_hierarchy(Interaction.user, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ You cannot moderate this user because they have a higher or equal role than you.", Color=discord.Color.red()), ephemeral=True)
            return
        if not check_bot_hierarchy(Interaction.guild, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ I cannot moderate this user because they have a higher or equal role than me.", Color=discord.Color.red()), ephemeral=True)
            return

        Td = parse_duration(duration)
        if not Td:
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ Invalid duration format. Use formats like `10m` (minutes), `1h` (hours), `1d` (days).", Color=discord.Color.red()), ephemeral=True)
            return

        try:
            DmEmbed = create_agency_embed(
                Title=f"You have been timed out in {Interaction.guild.name}",
                Description=f"**Duration:** {duration}\n**Reason:** {reason}",
                Color=discord.Color.orange()
            )
            await member.send(embed=DmEmbed)
        except Exception:
            pass

        try:
            await member.timeout(Td, reason=f"Timed out by {Interaction.user.name}: {reason}")
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"✅ **{member.name}** was timed out for **{duration}**.\n**Reason:** {reason}", Color=discord.Color.green()))
        except Exception as E:
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"❌ Failed to timeout user: {E}", Color=discord.Color.red()), ephemeral=True)

    @app_commands.command(name="untimeout", description="Remove timeout/mute from a member.")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="The member to untimeout", reason="Reason for untimeout")
    async def untimeout_slash(self, Interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = "No reason provided") -> None:
        if not check_hierarchy(Interaction.user, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ You cannot moderate this user because they have a higher or equal role than you.", Color=discord.Color.red()), ephemeral=True)
            return
        if not check_bot_hierarchy(Interaction.guild, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ I cannot moderate this user because they have a higher or equal role than me.", Color=discord.Color.red()), ephemeral=True)
            return

        try:
            await member.timeout(None, reason=f"Untimeout by {Interaction.user.name}: {reason}")
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"✅ Timeout removed from **{member.name}**.\n**Reason:** {reason}", Color=discord.Color.green()))
        except Exception as E:
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"❌ Failed to remove timeout: {E}", Color=discord.Color.red()), ephemeral=True)

    @app_commands.command(name="mute", description="Mute a member (alias for /timeout with default 1 hour).")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="The member to mute", duration="Duration (default 1h)", reason="Reason for the mute")
    async def mute_slash(self, Interaction: discord.Interaction, member: discord.Member, duration: Optional[str] = "1h", reason: Optional[str] = "No reason provided") -> None:
        await self.timeout_slash(Interaction, member, duration, reason)

    @app_commands.command(name="unmute", description="Unmute a member (alias for /untimeout).")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="The member to unmute", reason="Reason for the unmute")
    async def unmute_slash(self, Interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = "No reason provided") -> None:
        await self.untimeout_slash(Interaction, member, reason)

    @app_commands.command(name="warn", description="Issue a warning to a member.")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="The member to warn", reason="Reason for warning")
    async def warn_slash(self, Interaction: discord.Interaction, member: discord.Member, reason: str) -> None:
        if not check_hierarchy(Interaction.user, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ You cannot warn this user because they have a higher or equal role than you.", Color=discord.Color.red()), ephemeral=True)
            return
        if not check_bot_hierarchy(Interaction.guild, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ I cannot warn this user because they have a higher or equal role than me.", Color=discord.Color.red()), ephemeral=True)
            return

        WarnId = moderation_db.add_warning(member.id, Interaction.guild.id, Interaction.user.id, reason)
        moderation_db.log_mod_action(
            ActionType="WARN",
            GuildId=Interaction.guild.id,
            ModeratorId=Interaction.user.id,
            TargetId=member.id,
            Reason=reason,
            Details=f"Warning ID: {WarnId}"
        )

        try:
            DmEmbed = create_agency_embed(
                Title=f"⚠️ Warning issued in {Interaction.guild.name}",
                Description=f"**Reason:** {reason}\n**Warning ID:** {WarnId}",
                Color=discord.Color.yellow()
            )
            await member.send(embed=DmEmbed)
        except Exception:
            pass

        await Interaction.response.send_message(
            embed=create_agency_embed(
                Description=f"✅ **{member.name}** has been warned (Warning ID: `{WarnId}`).\n**Reason:** {reason}",
                Color=discord.Color.green()
            )
        )

    @app_commands.command(name="warnings", description="View warnings logged against a member.")
    @app_commands.describe(member="The member whose warnings you want to view")
    async def warnings_slash(self, Interaction: discord.Interaction, member: Optional[discord.Member] = None) -> None:
        Target = member or Interaction.user
        if Target != Interaction.user:
            AuthorPerms = Interaction.channel.permissions_for(Interaction.user)
            if not AuthorPerms.kick_members:
                await Interaction.response.send_message(embed=create_agency_embed(Description="❌ You do not have permission to view other users' warnings.", Color=discord.Color.red()), ephemeral=True)
                return

        WarningsList = moderation_db.get_warnings(Target.id, Interaction.guild.id)
        if not WarningsList:
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"🟢 **{Target.name}** has no active warnings.", Color=discord.Color.green()))
            return

        Embed = create_agency_embed(
            Title=f"Warnings for {Target.name} ({len(WarningsList)})",
            Color=discord.Color.yellow()
        )
        for Warn in WarningsList:
            Dt = datetime.datetime.fromisoformat(Warn["timestamp"]).strftime("%d/%m/%Y %I:%M %p")
            Embed.add_field(
                name=f"Warning ID: {Warn['id']}",
                value=f"**Moderator:** <@{Warn['moderator_id']}>\n**Reason:** {Warn['reason']}\n**Date:** {Dt}",
                inline=False
            )
        await Interaction.response.send_message(embed=Embed)

    @app_commands.command(name="clearwarns", description="Clear warnings for a user.")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="The member to clear warnings from", warning_id="The specific Warning ID to clear (leave empty to clear all)")
    async def clearwarns_slash(self, Interaction: discord.Interaction, member: discord.Member, warning_id: Optional[int] = None) -> None:
        if warning_id:
            Success = moderation_db.delete_warning(warning_id)
            if Success:
                moderation_db.log_mod_action(
                    ActionType="CLEARWARNS",
                    GuildId=Interaction.guild.id,
                    ModeratorId=Interaction.user.id,
                    TargetId=member.id,
                    Reason=f"Cleared warning ID: {warning_id}"
                )
                await Interaction.response.send_message(embed=create_agency_embed(Description=f"✅ Cleared warning ID `{warning_id}` for **{member.name}**.", Color=discord.Color.green()))
            else:
                await Interaction.response.send_message(embed=create_agency_embed(Description=f"❌ Warning ID `{warning_id}` not found for this user.", Color=discord.Color.red()), ephemeral=True)
        else:
            Count = moderation_db.clear_warnings(member.id, Interaction.guild.id)
            moderation_db.log_mod_action(
                ActionType="CLEARWARNS",
                GuildId=Interaction.guild.id,
                ModeratorId=Interaction.user.id,
                TargetId=member.id,
                Reason="Cleared all warnings"
            )
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"✅ Successfully cleared all **{Count}** warnings for **{member.name}**.", Color=discord.Color.green()))

    @app_commands.command(name="purge", description="Bulk delete messages in the current channel.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(amount="Number of messages to delete (1-100)")
    async def purge_slash(self, Interaction: discord.Interaction, amount: int) -> None:
        if amount < 1 or amount > 100:
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ You can only purge between 1 and 100 messages at a time.", Color=discord.Color.red()), ephemeral=True)
            return

        await Interaction.response.defer(ephemeral=True)
        try:
            Deleted = await Interaction.channel.purge(limit=amount)
            moderation_db.log_mod_action(
                ActionType="PURGE",
                GuildId=Interaction.guild.id,
                ModeratorId=Interaction.user.id,
                TargetId=None,
                Details=f"Purged {len(Deleted)} messages in channel {Interaction.channel.id}"
            )
            await Interaction.followup.send(embed=create_agency_embed(Description=f"🗑️ Successfully deleted **{len(Deleted)}** messages.", Color=discord.Color.green()), ephemeral=True)
        except Exception as E:
            await Interaction.followup.send(embed=create_agency_embed(Description=f"❌ Failed to purge messages: {E}", Color=discord.Color.red()), ephemeral=True)

    @app_commands.command(name="lock", description="Lock the current channel to prevent members from sending messages.")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock_slash(self, Interaction: discord.Interaction) -> None:
        Channel = Interaction.channel
        Guild = Interaction.guild
        try:
            await Channel.set_permissions(Guild.default_role, send_messages=False)
            moderation_db.log_mod_action(
                ActionType="LOCK",
                GuildId=Guild.id,
                ModeratorId=Interaction.user.id,
                TargetId=None,
                Details=f"Locked channel {Channel.id}"
            )
            await Interaction.response.send_message(embed=create_agency_embed(Description="🔒 **Channel locked successfully.** Everyone is restricted from sending messages.", Color=discord.Color.red()))
        except Exception as E:
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"❌ Failed to lock channel: {E}", Color=discord.Color.red()), ephemeral=True)

    @app_commands.command(name="unlock", description="Unlock the current channel to allow members to send messages.")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock_slash(self, Interaction: discord.Interaction) -> None:
        Channel = Interaction.channel
        Guild = Interaction.guild
        try:
            await Channel.set_permissions(Guild.default_role, send_messages=None)
            moderation_db.log_mod_action(
                ActionType="UNLOCK",
                GuildId=Guild.id,
                ModeratorId=Interaction.user.id,
                TargetId=None,
                Details=f"Unlocked channel {Channel.id}"
            )
            await Interaction.response.send_message(embed=create_agency_embed(Description="🔓 **Channel unlocked successfully.** Default messaging permissions restored.", Color=discord.Color.green()))
        except Exception as E:
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"❌ Failed to unlock channel: {E}", Color=discord.Color.red()), ephemeral=True)

    @app_commands.command(name="slowmode", description="Set a slowmode timer on the current channel.")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to turn off)")
    async def slowmode_slash(self, Interaction: discord.Interaction, seconds: int) -> None:
        if seconds < 0 or seconds > 21600:
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ Slowmode delay must be between 0 and 21600 seconds (6 hours).", Color=discord.Color.red()), ephemeral=True)
            return

        try:
            await Interaction.channel.edit(slowmode_delay=seconds)
            moderation_db.log_mod_action(
                ActionType="SLOWMODE",
                GuildId=Interaction.guild.id,
                ModeratorId=Interaction.user.id,
                TargetId=None,
                Details=f"Set slowmode to {seconds}s in channel {Interaction.channel.id}"
            )
            if seconds == 0:
                await Interaction.response.send_message(embed=create_agency_embed(Description="⏱️ **Slowmode has been disabled.**", Color=discord.Color.green()))
            else:
                await Interaction.response.send_message(embed=create_agency_embed(Description=f"⏱️ **Slowmode set to {seconds} seconds.**", Color=discord.Color.green()))
        except Exception as E:
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"❌ Failed to set slowmode: {E}", Color=discord.Color.red()), ephemeral=True)

    @app_commands.command(name="softban", description="Ban and immediately unban a user to clear their message history.")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member="The member to softban", reason="Reason for softban")
    async def softban_slash(self, Interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = "No reason provided") -> None:
        if not check_hierarchy(Interaction.user, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ You cannot softban this user because they have a higher or equal role than you.", Color=discord.Color.red()), ephemeral=True)
            return
        if not check_bot_hierarchy(Interaction.guild, member):
            await Interaction.response.send_message(embed=create_agency_embed(Description="❌ I cannot softban this user because they have a higher or equal role than me.", Color=discord.Color.red()), ephemeral=True)
            return

        try:
            DmEmbed = create_agency_embed(
                Title=f"You have been softbanned from {Interaction.guild.name}",
                Description=f"**Reason:** {reason} (Messages cleared)",
                Color=discord.Color.red()
            )
            await member.send(embed=DmEmbed)
        except Exception:
            pass

        try:
            await member.ban(reason=f"Softban by {Interaction.user.name}: {reason}", delete_message_seconds=604800)
            await Interaction.guild.unban(member, reason=f"Softban unban by {Interaction.user.name}")
            moderation_db.log_mod_action(
                ActionType="SOFTBAN",
                GuildId=Interaction.guild.id,
                ModeratorId=Interaction.user.id,
                TargetId=member.id,
                Reason=reason
            )
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"✅ **{member.name}** was softbanned. 7 days of message history cleared.", Color=discord.Color.green()))
        except Exception as E:
            await Interaction.response.send_message(embed=create_agency_embed(Description=f"❌ Failed to softban user: {E}", Color=discord.Color.red()), ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, Interaction: discord.Interaction, Error: app_commands.AppCommandError):
        if isinstance(Error, app_commands.MissingPermissions):
            Missing = ", ".join(Error.missing_permissions)
            await Interaction.response.send_message(
                embed=create_agency_embed(Description=f"❌ You do not have the required permissions to run this command: `{Missing}`", Color=discord.Color.red()),
                ephemeral=True
            )
        else:
            Logger.error(f"Moderation command error: {Error}", exc_info=True)
            if not Interaction.response.is_done():
                await Interaction.response.send_message(embed=create_agency_embed(Description="❌ An unexpected error occurred while executing this command.", Color=discord.Color.red()), ephemeral=True)

async def setup(Bot: commands.Bot):
    await Bot.add_cog(ModerationCog(Bot))
