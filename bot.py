import discord
from discord.ext import commands
import database
import moderation_db
from views.panel import TicketPanelView
from views.ticket_control import TicketStaffControlView
from config import Logger, GuildId

class AgencyBot(commands.Bot):
    def __init__(self) -> None:
        Intents = discord.Intents.default()
        Intents.message_content = True
        Intents.members = True
        
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=Intents,
            help_command=commands.DefaultHelpCommand(),
            activity=discord.Activity(type=discord.ActivityType.watching, name="Evernode Agency"),
            status=discord.Status.online
        )

    async def setup_hook(self) -> None:
        database.init_db()
        moderation_db.init_db()

        await self.load_extension("cogs.moderation")
        await self.load_extension("cogs.tickets")
        await self.load_extension("cogs.welcome")
        await self.load_extension("cogs.logs")

        try:
            GuildObj = discord.Object(id=GuildId)
            self.tree.copy_global_to(guild=GuildObj)
            await self.tree.sync(guild=GuildObj)
        except Exception as E:
            Logger.error(f"Failed to sync command tree to guild {GuildId}: {E}")

        self.add_view(TicketPanelView(self))

        try:
            with database.sqlite3.connect(database.DbPath) as Conn:
                Conn.row_factory = database.sqlite3.Row
                Cursor = Conn.cursor()
                Cursor.execute("SELECT channel_id FROM tickets WHERE state = 'ACTIVE'")
                ActiveRows = Cursor.fetchall()
                for Row in ActiveRows:
                    self.add_view(TicketStaffControlView(self, Row["channel_id"]))
        except Exception as E:
            Logger.error(f"Failed to reload persistent active ticket views: {E}")

    @commands.command(name="sync", hidden=True)
    @commands.is_owner()
    async def sync_prefix(self, Ctx: commands.Context, Scope: str = "guild") -> None:
        if Scope == "guild":
            GuildObj = discord.Object(id=GuildId)
            self.tree.copy_global_to(guild=GuildObj)
            Synced = await self.tree.sync(guild=GuildObj)
            await Ctx.send(f"Synced {len(Synced)} slash commands to guild `{GuildId}`.")
        elif Scope == "global":
            Synced = await self.tree.sync()
            await Ctx.send(f"Synced {len(Synced)} slash commands globally.")
        else:
            await Ctx.send("Invalid scope. Use `guild` or `global`.")
            
    @sync_prefix.error
    async def sync_prefix_error(self, Ctx: commands.Context, Error: commands.CommandError):
        if isinstance(Error, commands.NotOwner):
            await Ctx.send("Only the bot owner can execute this command.")
