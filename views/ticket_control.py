import discord
import io
import datetime
from typing import Optional
from utils.embed import create_agency_embed
from utils.transcript import generate_channel_transcript_html
from views.review import AgencyReviewView
from config import Logger, LogChannelId, SupportRoleId, OrderRoleId, ModRoleId, LogoUrl
import database

def get_ticket_role(Guild: discord.Guild, Category: str):
    if Category == "support":
        RoleId = SupportRoleId
    elif Category == "moderation":
        RoleId = ModRoleId
    else:
        RoleId = OrderRoleId
    Role = Guild.get_role(RoleId)
    return Role, RoleId

class RenameTicketModal(discord.ui.Modal):
    def __init__(self, Channel: discord.TextChannel):
        super().__init__(title="Rename Ticket Channel")
        self.Channel = Channel
        self.NewName = discord.ui.TextInput(
            label="New Channel Name",
            placeholder="e.g. support-0012-website",
            required=True,
            max_length=50
        )
        self.add_item(self.NewName)

    async def on_submit(self, Interaction: discord.Interaction):
        await Interaction.response.defer(ephemeral=True)
        try:
            await self.Channel.edit(name=self.NewName.value.lower())
            await Interaction.followup.send(f"Channel renamed to **{self.NewName.value.lower()}**", ephemeral=True)
        except Exception as E:
            Logger.error(f"Failed to rename channel {self.Channel.id}: {E}")
            await Interaction.followup.send(f"Error: Failed to rename channel: {E}", ephemeral=True)

class CloseReasonModal(discord.ui.Modal):
    def __init__(self, Bot, ChannelId: int):
        super().__init__(title="Reason for Closure")
        self.Bot = Bot
        self.ChannelId = ChannelId
        self.Reason = discord.ui.TextInput(
            label="Reason for closing",
            style=discord.TextStyle.paragraph,
            placeholder="Please enter a reason for closing this ticket...",
            required=False,
            max_length=500
        )
        self.add_item(self.Reason)

    async def on_submit(self, Interaction: discord.Interaction):
        await Interaction.response.defer()
        ReasonVal = self.Reason.value.strip() or "No reason provided"
        await perform_ticket_closure(Interaction, self.Bot, self.ChannelId, ReasonVal)

class CloseConfirmView(discord.ui.View):
    def __init__(self, Bot, ChannelId: int):
        super().__init__(timeout=60)
        self.Bot = Bot
        self.ChannelId = ChannelId

    @discord.ui.button(label="Yes, Close", style=discord.ButtonStyle.danger)
    async def confirm(self, Interaction: discord.Interaction, Button: discord.ui.Button):
        await Interaction.response.send_modal(CloseReasonModal(self.Bot, self.ChannelId))
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, Interaction: discord.Interaction, Button: discord.ui.Button):
        await Interaction.response.edit_message(
            content=None,
            embed=create_agency_embed(Description="Error: Close cancelled.", Color=discord.Color.red()),
            view=None
        )
        self.stop()

async def perform_ticket_closure(Interaction: discord.Interaction, Bot, ChannelId: int, Reason: str):
    Channel = Interaction.channel
    Guild = Interaction.guild
    TicketInfo = database.get_ticket(ChannelId)
    
    if not TicketInfo:
        await Interaction.followup.send(
            embed=create_agency_embed(Description="Error: Ticket info not found in database.", Color=discord.Color.red()),
            ephemeral=True
        )
        return

    database.close_ticket_db(ChannelId)

    CreatedAt = datetime.datetime.fromisoformat(TicketInfo["created_at"])
    Duration = datetime.datetime.now() - CreatedAt
    DurationStr = str(Duration).split(".")[0]

    try:
        HtmlContent = await generate_channel_transcript_html(Channel, TicketInfo)
    except Exception as E:
        Logger.error(f"Failed to generate transcript for ticket {ChannelId}: {E}", exc_info=True)
        HtmlContent = "Failed to generate transcript due to an internal error."

    Fp = io.BytesIO(HtmlContent.encode("utf-8"))
    DiscordFile = discord.File(Fp, filename=f"transcript-{TicketInfo['category']}-{TicketInfo['ticket_num']}.html")

    LogChannel = Bot.get_channel(LogChannelId)
    if not LogChannel:
        try:
            LogChannel = await Bot.fetch_channel(LogChannelId)
        except Exception as E:
            Logger.error(f"Failed to fetch logs channel {LogChannelId}: {E}")
            LogChannel = None

    if LogChannel:
        try:
            LogoUrlVal = LogoUrl
            CustomerMember = Guild.get_member(TicketInfo["user_id"])
            CustomerStr = f"{CustomerMember.name} ({TicketInfo['user_id']})" if CustomerMember else str(TicketInfo["user_id"])
            ClaimerMember = Guild.get_member(TicketInfo["claimed_by"]) if TicketInfo.get("claimed_by") else None
            ClaimedByStr = ClaimerMember.name if ClaimerMember else ("Unclaimed" if not TicketInfo.get("claimed_by") else str(TicketInfo['claimed_by']))
            ClosedByStr = Interaction.user.name
            
            LogContainer = discord.ui.Container(
                discord.ui.Section(
                    "**Ticket Closed & Logged**",
                    "A support ticket has been closed. An interactive HTML transcript has been generated and archived below.",
                    accessory=discord.ui.Thumbnail(LogoUrlVal)
                ),
                discord.ui.Separator(),
                discord.ui.TextDisplay(f"-# CUSTOMER\n{CustomerStr}"),
                discord.ui.TextDisplay(f"-# TICKET TYPE\n{TicketInfo['category'].capitalize()}"),
                discord.ui.TextDisplay(f"-# TICKET ID\n#{TicketInfo['ticket_num']:04d}"),
                discord.ui.TextDisplay(f"-# CLAIMED BY\n{ClaimedByStr}"),
                discord.ui.TextDisplay(f"-# DURATION\n{DurationStr}"),
                discord.ui.TextDisplay(f"-# CLOSED BY\n{ClosedByStr}"),
                discord.ui.Separator(),
                discord.ui.TextDisplay(f"-# CLOSURE REASON\n{Reason}"),
                accent_color=0xff7f17
            )
            
            LogView = discord.ui.LayoutView()
            LogView.add_item(LogContainer)
            
            await LogChannel.send(view=LogView)
            await LogChannel.send(file=DiscordFile)
        except Exception as E:
            Logger.error(f"Failed to send log message: {E}", exc_info=True)

    try:
        await Channel.delete(reason=f"Ticket closed by {Interaction.user.name}")
    except Exception as E:
        Logger.error(f"Failed to delete channel {Channel.id}: {E}")

class TicketStaffControlView(discord.ui.LayoutView):
    def __init__(self, Bot, ChannelId: int, Owner: Optional[discord.Member] = None, Category: Optional[str] = None, TicketNum: Optional[int] = None, Fields: Optional[dict] = None):
        super().__init__(timeout=None)
        self.Bot = Bot
        self.ChannelId = ChannelId
        self.Owner = Owner
        self.Category = Category
        self.TicketNum = TicketNum
        self.Fields = Fields
        self.setup_layout()

    def get_buttons_row(self) -> discord.ui.ActionRow:
        return self.ActionRow

    def setup_layout(self):
        Ticket = database.get_ticket(self.ChannelId)
        IsClaimed = Ticket and Ticket.get("claimed_by") is not None
        
        ClaimLabel = "Claim Ticket"
        if IsClaimed:
            ClaimerId = Ticket["claimed_by"]
            Channel = self.Bot.get_channel(self.ChannelId)
            Guild = Channel.guild if Channel else None
            ClaimerUser = Guild.get_member(ClaimerId) if Guild else None
            if not ClaimerUser:
                ClaimerUser = self.Bot.get_user(ClaimerId)
            ClaimLabel = f"Claimed by {ClaimerUser.name if ClaimerUser else ClaimerId}"

        self.ClaimBtn = discord.ui.Button(
            label=ClaimLabel,
            style=discord.ButtonStyle.success,
            custom_id=f"ticket_claim_{self.ChannelId}",
            disabled=is_claimed if 'is_claimed' in locals() else IsClaimed
        )
        self.ClaimBtn.callback = self.claim_callback

        self.UnclaimBtn = discord.ui.Button(
            label="Unclaim",
            style=discord.ButtonStyle.secondary,
            custom_id=f"ticket_unclaim_{self.ChannelId}",
            disabled=not IsClaimed
        )
        self.UnclaimBtn.callback = self.unclaim_callback

        self.CloseBtn = discord.ui.Button(
            label="Close",
            style=discord.ButtonStyle.danger,
            custom_id=f"ticket_close_{self.ChannelId}"
        )
        self.CloseBtn.callback = self.close_callback

        self.ActionRow = discord.ui.ActionRow()
        self.ActionRow.add_item(self.ClaimBtn)
        if IsClaimed:
            self.ActionRow.add_item(self.UnclaimBtn)
        self.ActionRow.add_item(self.CloseBtn)

        if self.Owner is not None:
            ReadableCat = "Support"
            if self.Category == "moderation":
                ReadableCat = "Moderation"
            elif self.Category == "hire_us":
                ReadableCat = "Hire Us"
                
            QuotedFieldsStr = ""
            if self.Fields:
                Lines = []
                for K, V in self.Fields.items():
                    Lines.append(f"> **{K}**")
                    for Line in V.strip().split('\n'):
                        Lines.append(f"> • {Line}")
                    Lines.append("> ")
                if Lines and Lines[-1] == "> ":
                    Lines.pop()
                QuotedFieldsStr = "\n".join(Lines)

            Container = discord.ui.Container(
                discord.ui.Section(
                    f"**Evernode Agency | {ReadableCat} Ticket**",
                    f"Thank you for reaching out, {self.Owner.mention}! Our team has been notified and will assist you shortly. In the meantime, please review your details below.",
                    accessory=discord.ui.Thumbnail(LogoUrl)
                ),
                discord.ui.Separator(),
                discord.ui.TextDisplay(
                    "> **Ticket Owner**\n"
                    f"> {self.Owner.name} (`{self.Owner.id}`)"
                ),
                discord.ui.TextDisplay(
                    f"{QuotedFieldsStr}"
                ),
                discord.ui.Separator(),
                self.ActionRow,
                accent_color=0xff7f17
            )
            self.add_item(Container)
        else:
            self.add_item(self.ActionRow)

    async def update_message_view(self, Channel: discord.TextChannel) -> None:
        Guild = Channel.guild
        try:
            async for Message in Channel.history(limit=50, oldest_first=True):
                if Message.author == Guild.me and Message.components:
                    View = discord.ui.LayoutView.from_message(Message)
                    Container = None
                    for Child in View.children:
                        if isinstance(Child, discord.ui.Container):
                            Container = Child
                            break
                    
                    if Container:
                        self.clear_items()
                        self.setup_layout()
                        OldChildren = Container.children
                        Container.clear_items()
                        for Child in OldChildren:
                            if isinstance(Child, discord.ui.ActionRow):
                                Container.add_item(self.ActionRow)
                            else:
                                Container.add_item(Child)
                        await Message.edit(view=View)
                    break
        except Exception as E:
            Logger.error(f"Failed to update channel greeting message: {E}", exc_info=True)

    async def claim_callback(self, Interaction: discord.Interaction):
        Ticket = database.get_ticket(self.ChannelId)
        if not Ticket:
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Error: Ticket details not found.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        Guild = Interaction.guild
        Channel = Interaction.channel

        if Ticket.get("claimed_by"):
            Claimer = Guild.get_member(Ticket["claimed_by"]) or self.Bot.get_user(Ticket["claimed_by"])
            ClaimerName = Claimer.name if Claimer else str(Ticket["claimed_by"])
            await Interaction.response.send_message(
                embed=create_agency_embed(Description=f"Warning: Ticket already claimed by {ClaimerName}.", Color=discord.Color.orange()),
                ephemeral=True
            )
            return
        
        PingedRole, RoleId = get_ticket_role(Guild, Ticket["category"])
        
        HasRole = PingedRole in Interaction.user.roles if PingedRole else False
        IsAdmin = Interaction.user.guild_permissions.administrator
        if not (HasRole or IsAdmin):
            RoleName = f"@{PingedRole.name}" if PingedRole else f"Role ID {RoleId}"
            await Interaction.response.send_message(
                embed=create_agency_embed(Description=f"Error: Only members with the {RoleName} role (or Administrators) can claim this ticket.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        Overwrites = dict(Channel.overwrites)
        Opener = Guild.get_member(Ticket["user_id"])
        if Opener:
            Overwrites[Opener] = discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, attach_files=True, read_message_history=True)
            
        Overwrites[Interaction.user] = discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, attach_files=True, read_message_history=True)
        
        if PingedRole:
            Overwrites[PingedRole] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
            
        Overwrites[Guild.me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_permissions=True)

        try:
            CurrentName = Channel.name
            Parts = CurrentName.split("-")
            NamePrefix = Parts[0]
            NumPart = Parts[1] if len(Parts) > 1 else str(Ticket["ticket_num"])
            NewName = f"{NamePrefix}-{NumPart}-{Interaction.user.name}"
            await Channel.edit(name=NewName.lower(), overwrites=Overwrites)
        except Exception as E:
            Logger.error(f"Failed to claim ticket channel: {E}")
            await Interaction.response.send_message(
                embed=create_agency_embed(Description=f"Error: Failed to claim ticket: {E}", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        database.claim_ticket(self.ChannelId, Interaction.user.id)
        await self.update_message_view(Channel)

        await Interaction.response.send_message(
            embed=create_agency_embed(
                Description=f"**Ticket claimed by {Interaction.user.mention}!** Only they and the customer can now speak in this ticket.",
                IsOfficial=True
            )
        )

    async def unclaim_callback(self, Interaction: discord.Interaction):
        Ticket = database.get_ticket(self.ChannelId)
        if not Ticket:
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Error: Ticket details not found.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        Guild = Interaction.guild
        Channel = Interaction.channel

        if not Ticket.get("claimed_by"):
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Warning: This ticket is not claimed.", Color=discord.Color.orange()),
                ephemeral=True
            )
            return

        IsClaimer = Ticket["claimed_by"] == Interaction.user.id
        IsAdmin = Interaction.user.guild_permissions.administrator

        if not (IsClaimer or IsAdmin):
            Claimer = Guild.get_member(Ticket["claimed_by"]) or self.Bot.get_user(Ticket["claimed_by"])
            ClaimerName = Claimer.name if Claimer else str(Ticket["claimed_by"])
            await Interaction.response.send_message(
                embed=create_agency_embed(Description=f"Error: Only the claimant ({ClaimerName}) or an Administrator can unclaim this ticket.", Color=discord.Color.red()),
                ephemeral=True
            )
            return
        
        Overwrites = dict(Channel.overwrites)
        Opener = Guild.get_member(Ticket["user_id"])
        if Interaction.user != Opener:
            Overwrites[Interaction.user] = None
            
        PingedRole, RoleId = get_ticket_role(Guild, Ticket["category"])
        if PingedRole:
            Overwrites[PingedRole] = discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, attach_files=True, read_message_history=True)

        try:
            Parts = Channel.name.split("-")
            NamePrefix = Parts[0]
            NumPart = Parts[1] if len(Parts) > 1 else str(Ticket["ticket_num"])
            NewName = f"{NamePrefix}-{NumPart}"
            await Channel.edit(name=NewName.lower(), overwrites=Overwrites)
        except Exception as E:
            Logger.error(f"Failed to reset channel properties on unclaim: {E}")
            await Interaction.response.send_message(
                embed=create_agency_embed(Description=f"Error: Failed to unclaim ticket: {E}", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        database.unclaim_ticket_db(self.ChannelId)
        await self.update_message_view(Channel)

        await Interaction.response.send_message(
            embed=create_agency_embed(
                Description=f"**Ticket unclaimed by {Interaction.user.mention}!** It is now open for any staff member to claim.",
                IsOfficial=True
            )
        )

    async def rename_callback(self, Interaction: discord.Interaction):
        await Interaction.response.send_modal(RenameTicketModal(Interaction.channel))

    async def close_callback(self, Interaction: discord.Interaction):
        Ticket = database.get_ticket(self.ChannelId)
        if not Ticket:
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Error: Ticket details not found.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        IsCustomer = Ticket["user_id"] == Interaction.user.id
        IsClaimer = Ticket.get("claimed_by") == Interaction.user.id
        IsAdmin = Interaction.user.guild_permissions.administrator

        if not (IsCustomer or IsClaimer or IsAdmin):
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Error: Only the customer, the claiming staff, or an Administrator can close this ticket.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        ConfirmView = CloseConfirmView(self.Bot, self.ChannelId)
        await Interaction.response.send_message(
            embed=create_agency_embed(
                Description="**Are you sure you want to close this ticket?** This will archive the chat history and delete the channel.",
                Color=discord.Color.orange()
            ),
            view=ConfirmView,
            ephemeral=True
        )
