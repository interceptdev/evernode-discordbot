import discord
import datetime
from utils.embed import create_agency_embed
import database
from config import Logger, SupportModCategoryId, HireUsCategoryId, LogoUrl

class SupportTicketModal(discord.ui.Modal):
    def __init__(self, Bot):
        super().__init__(title="Open a Support Ticket")
        self.Bot = Bot
        self.Details = discord.ui.TextInput(
            label="Describe your support request / issue",
            style=discord.TextStyle.paragraph,
            placeholder="Please provide details about what you need assistance with...",
            required=True,
            max_length=1000
        )
        self.add_item(self.Details)

    async def on_submit(self, Interaction: discord.Interaction):
        await handle_ticket_creation(Interaction, self.Bot, "support", {
            "Details": self.Details.value
        })

class ModerationTicketModal(discord.ui.Modal):
    def __init__(self, Bot):
        super().__init__(title="Open a Moderation Ticket")
        self.Bot = Bot
        self.TypeInput = discord.ui.TextInput(
            label="Is this a Report or an Appeal?",
            placeholder="Report / Appeal",
            required=True,
            max_length=100
        )
        self.Details = discord.ui.TextInput(
            label="Explain the situation in detail",
            style=discord.TextStyle.paragraph,
            placeholder="Provide context, names, and description...",
            required=True,
            max_length=1000
        )
        self.add_item(self.TypeInput)
        self.add_item(self.Details)

    async def on_submit(self, Interaction: discord.Interaction):
        await handle_ticket_creation(Interaction, self.Bot, "moderation", {
            "Type": self.TypeInput.value,
            "Details": self.Details.value
        })

class HireUsTicketModal(discord.ui.Modal):
    def __init__(self, Bot):
        super().__init__(title="Hire Us / Request a Project")
        self.Bot = Bot
        self.ProjectType = discord.ui.TextInput(
            label="Project Type",
            placeholder="e.g. Website, Discord Bot, both, or other",
            required=True,
            max_length=100
        )
        self.BudgetTimeline = discord.ui.TextInput(
            label="Estimated Budget & Timeline",
            placeholder="e.g. $150 budget, 2 weeks deadline",
            required=True,
            max_length=200
        )
        self.Details = discord.ui.TextInput(
            label="Project Description & Features",
            style=discord.TextStyle.paragraph,
            placeholder="Describe the functionality and features you want...",
            required=True,
            max_length=1000
        )
        self.add_item(self.ProjectType)
        self.add_item(self.BudgetTimeline)
        self.add_item(self.Details)

    async def on_submit(self, Interaction: discord.Interaction):
        await handle_ticket_creation(Interaction, self.Bot, "hire_us", {
            "Project Type": self.ProjectType.value,
            "Budget & Timeline": self.BudgetTimeline.value,
            "Description": self.Details.value
        })

async def handle_ticket_creation(Interaction: discord.Interaction, Bot, Category: str, Fields: dict):
    await Interaction.response.defer(ephemeral=True)
    Guild = Interaction.guild
    User = Interaction.user
    
    if Category in ("support", "moderation"):
        CategoryId = SupportModCategoryId
        NamePrefix = "support" if Category == "support" else "mod"
        ReadableCat = "Support" if Category == "support" else "Moderation"
    else:
        CategoryId = HireUsCategoryId
        NamePrefix = "hire"
        ReadableCat = "Hire Us"

    CategoryChannel = Guild.get_channel(CategoryId)
    if not CategoryChannel:
        try:
            CategoryChannel = await Guild.fetch_channel(CategoryId)
        except Exception as E:
            Logger.error(f"Failed to fetch parent category channel {CategoryId}: {E}")
            await Interaction.followup.send(
                embed=create_agency_embed(Description="Error: Ticket category channel not found on server.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

    TicketNum = database.get_next_ticket_number(Category)
    PaddedNum = f"{TicketNum:04d}"
    ChannelName = f"{NamePrefix}-{PaddedNum}"

    from config import SupportRoleId, OrderRoleId, ModRoleId
    
    if Category == "support":
        RoleId = SupportRoleId
    elif Category == "moderation":
        RoleId = ModRoleId
    else:
        RoleId = OrderRoleId
        
    PingedRole = Guild.get_role(RoleId)
    if not PingedRole:
        try:
            PingedRole = await Guild.fetch_role(RoleId)
        except Exception:
            PingedRole = None
            
    Overwrites = {
        Guild.default_role: discord.PermissionOverwrite(view_channel=False),
        Guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, attach_files=True, manage_channels=True, manage_permissions=True),
        User: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, attach_files=True, read_message_history=True)
    }

    if PingedRole:
        Overwrites[PingedRole] = discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, attach_files=True, read_message_history=True)

    try:
        TicketChannel = await Guild.create_text_channel(
            name=ChannelName,
            category=CategoryChannel,
            overwrites=Overwrites,
            reason=f"Ticket opened by {User.name} ({User.id})"
        )
    except Exception as E:
        Logger.error(f"Failed to create ticket channel: {E}")
        await Interaction.followup.send(
            embed=create_agency_embed(Description="Error: Failed to create ticket channel. Make sure the bot has permissions.", Color=discord.Color.red()),
            ephemeral=True
        )
        return

    database.create_ticket(TicketChannel.id, User.id, Category, "ACTIVE", TicketNum)

    QuotedFieldsStr = ""
    if Fields:
        Lines = []
        for K, V in Fields.items():
            Lines.append(f"> **{K}**")
            for Line in V.strip().split('\n'):
                Lines.append(f"> • {Line}")
            Lines.append("> ")
        if Lines and Lines[-1] == "> ":
            Lines.pop()
        QuotedFieldsStr = "\n".join(Lines)

    from views.ticket_control import TicketStaffControlView
    ControlView = TicketStaffControlView(Bot, TicketChannel.id, User, Category, TicketNum, Fields)
    Bot.add_view(ControlView)
    
    Pings = f"{User.mention}"
    if PingedRole:
        Pings += f" {PingedRole.mention}"
    await TicketChannel.send(content=Pings)
    await TicketChannel.send(view=ControlView)

    await Interaction.followup.send(
        embed=create_agency_embed(Description=f"Your ticket has been created: {TicketChannel.mention}", IsOfficial=True),
        ephemeral=True
    )

class TicketDropdownSelect(discord.ui.Select):
    def __init__(self, Bot):
        self.Bot = Bot
        Options = [
            discord.SelectOption(
                label="Support Ticket",
                value="support",
                description="Have a question or need general help?",
                emoji="🎟️"
            ),
            discord.SelectOption(
                label="Hire Us",
                value="hire_us",
                description="Wish to hire us for a project?",
                emoji="📦"
            ),
            discord.SelectOption(
                label="Moderation Ticket",
                value="moderation",
                description="Report users or appeal punishments.",
                emoji="🔨"
            )
        ]
        super().__init__(
            placeholder="Make a selection",
            min_values=1,
            max_values=1,
            options=Options,
            custom_id="agency_ticket_select"
        )

    async def callback(self, Interaction: discord.Interaction):
        UserId = Interaction.user.id
        ActiveTicket = database.get_active_user_ticket(UserId)
        if ActiveTicket:
            Channel = Interaction.guild.get_channel(ActiveTicket["channel_id"])
            ChannelMention = Channel.mention if Channel else f"ID: {ActiveTicket['channel_id']}"
            await Interaction.response.send_message(
                embed=create_agency_embed(
                    Description=f"Error: You already have an active ticket open in {ChannelMention}.",
                    Color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        Choice = self.values[0]
        if Choice == "support":
            await Interaction.response.send_modal(SupportTicketModal(self.Bot))
        elif Choice == "moderation":
            await Interaction.response.send_modal(ModerationTicketModal(self.Bot))
        elif Choice == "hire_us":
            await Interaction.response.send_modal(HireUsTicketModal(self.Bot))

class TicketPanelView(discord.ui.LayoutView):
    def __init__(self, Bot):
        super().__init__(timeout=None)
        self.Bot = Bot
        self.setup_layout()

    def setup_layout(self):
        Select = TicketDropdownSelect(self.Bot)
        ActionRow = discord.ui.ActionRow()
        ActionRow.add_item(Select)
        
        Container = discord.ui.Container(
            discord.ui.Section(
                "**Evernode | Customer Support**",
                "Welcome to the Evernode ticket system. Please choose the appropriate category below so our team can assist you efficiently.",
                accessory=discord.ui.Thumbnail(LogoUrl)
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "> **IMPORTANT NOTES**\n"
                "> • **Describe your issue in detail** — do not wait for a response, specify your inquiry upfront.\n"
                "> • **Do not ping support staff** — tickets are handled in order of receipt."
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "> **🎟️ SUPPORT TICKET**\n"
                "> For general inquiries, questions, or community support.\n"
                "> \n"
                "> **📦 HIRE US**\n"
                "> For custom projects, custom websites, Discord bots, and services.\n"
                "> \n"
                "> **🔨 MODERATION TICKET**\n"
                "> For user reporting, appeals, leak reports, or moderation issues."
            ),
            discord.ui.Separator(),
            ActionRow,
            accent_color=0xff7f17
        )
        self.add_item(Container)
