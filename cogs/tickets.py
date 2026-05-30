import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.embed import create_agency_embed
from views.panel import TicketPanelView
import database
from config import Logger, StaffRoleId, AlwaysSpeakRoles, ReviewsChannelId, ReviewRequiredRoleId, LogoUrl

class TicketsCog(commands.Cog):
    def __init__(self, Bot: commands.Bot):
        self.Bot = Bot

    @app_commands.command(name="add", description="Add a member to the current ticket channel.")
    @app_commands.describe(member="The member to add to this ticket")
    async def add_slash(self, Interaction: discord.Interaction, member: discord.Member) -> None:
        ChannelId = Interaction.channel.id
        Ticket = database.get_ticket(ChannelId)
        
        if not Ticket or Ticket["state"] != "ACTIVE":
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Error: This command can only be run inside an active ticket channel.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        IsClaimer = Ticket.get("claimed_by") == Interaction.user.id
        IsAdmin = Interaction.user.guild_permissions.administrator
        
        if not (IsClaimer or IsAdmin):
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Error: Only the claiming staff member (or an Administrator) can add users to this ticket.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        try:
            await Interaction.channel.set_permissions(member, view_channel=True, send_messages=True, embed_links=True, attach_files=True, read_message_history=True)
            await Interaction.response.send_message(
                embed=create_agency_embed(
                    Description=f"{member.mention} has been added to the ticket channel by {Interaction.user.mention}.",
                    IsOfficial=True
                )
            )
        except Exception as E:
            Logger.error(f"Failed to add member {member.id} to channel {ChannelId}: {E}")
            await Interaction.response.send_message(
                embed=create_agency_embed(Description=f"Error: Failed to add member: {E}", Color=discord.Color.red()),
                ephemeral=True
            )

    @app_commands.command(name="remove", description="Remove a member from the current ticket channel.")
    @app_commands.describe(member="The member to remove from this ticket")
    async def remove_slash(self, Interaction: discord.Interaction, member: discord.Member) -> None:
        ChannelId = Interaction.channel.id
        Ticket = database.get_ticket(ChannelId)
        
        if not Ticket or Ticket["state"] != "ACTIVE":
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Error: This command can only be run inside an active ticket channel.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        IsClaimer = Ticket.get("claimed_by") == Interaction.user.id
        IsAdmin = Interaction.user.guild_permissions.administrator
        
        if not (IsClaimer or IsAdmin):
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Error: Only the claiming staff member (or an Administrator) can remove users from this ticket.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        if member.id == Ticket["user_id"]:
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Error: You cannot remove the ticket owner from their own ticket.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        try:
            await Interaction.channel.set_permissions(member, overwrite=None)
            await Interaction.response.send_message(
                embed=create_agency_embed(
                    Description=f"{member.mention} has been removed from the ticket channel by {Interaction.user.mention}.",
                    IsOfficial=True
                )
            )
        except Exception as E:
            Logger.error(f"Failed to remove member {member.id} from channel {ChannelId}: {E}")
            await Interaction.response.send_message(
                embed=create_agency_embed(Description=f"Error: Failed to remove member: {E}", Color=discord.Color.red()),
                ephemeral=True
            )

    @app_commands.command(name="claim", description="Claim the current ticket.")
    async def claim_slash(self, Interaction: discord.Interaction) -> None:
        ChannelId = Interaction.channel.id
        Channel = Interaction.channel
        Guild = Interaction.guild
        
        Ticket = database.get_ticket(ChannelId)
        if not Ticket or Ticket["state"] != "ACTIVE":
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Error: This command can only be run inside an active ticket channel.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        if Ticket.get("claimed_by"):
            Claimer = Guild.get_member(Ticket["claimed_by"]) or self.Bot.get_user(Ticket["claimed_by"])
            ClaimerName = Claimer.name if Claimer else str(Ticket["claimed_by"])
            await Interaction.response.send_message(
                embed=create_agency_embed(Description=f"Warning: Ticket already claimed by {ClaimerName}.", Color=discord.Color.orange()),
                ephemeral=True
            )
            return

        from views.ticket_control import get_ticket_role
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
            Parts = Channel.name.split("-")
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

        database.claim_ticket(ChannelId, Interaction.user.id)

        try:
            from views.ticket_control import TicketStaffControlView
            View = TicketStaffControlView(self.Bot, ChannelId)
            await View.update_message_view(Channel)
        except Exception as E:
            Logger.error(f"Failed to update channel view: {E}")

        await Interaction.response.send_message(
            embed=create_agency_embed(
                Description=f"**Ticket claimed by {Interaction.user.mention}!** Only they and the customer can now speak in this ticket.",
                IsOfficial=True
            )
        )

    @app_commands.command(name="unclaim", description="Unclaim the current ticket.")
    async def unclaim_slash(self, Interaction: discord.Interaction) -> None:
        ChannelId = Interaction.channel.id
        Channel = Interaction.channel
        Guild = Interaction.guild
        
        Ticket = database.get_ticket(ChannelId)
        if not Ticket or Ticket["state"] != "ACTIVE":
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Error: This command can only be run inside an active ticket channel.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

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
                embed=create_agency_embed(Description=f"Error: Only the claiming staff member ({ClaimerName}) or an Administrator can unclaim this ticket.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        Overwrites = dict(Channel.overwrites)
        Opener = Guild.get_member(Ticket["user_id"])
        if Interaction.user != Opener:
            Overwrites[Interaction.user] = None
            
        from views.ticket_control import get_ticket_role
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

        database.unclaim_ticket_db(ChannelId)

        try:
            from views.ticket_control import TicketStaffControlView
            View = TicketStaffControlView(self.Bot, ChannelId)
            await View.update_message_view(Channel)
        except Exception as E:
            Logger.error(f"Failed to update channel view: {E}")

        await Interaction.response.send_message(
            embed=create_agency_embed(
                Description=f"**Ticket unclaimed by {Interaction.user.mention}!** It is now open for any staff member to claim.",
                IsOfficial=True
            )
        )

    @app_commands.command(name="close", description="Close the current ticket channel.")
    async def close_slash(self, Interaction: discord.Interaction) -> None:
        ChannelId = Interaction.channel.id
        Ticket = database.get_ticket(ChannelId)
        
        if not Ticket or Ticket["state"] != "ACTIVE":
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Error: This command can only be run inside an active ticket channel.", Color=discord.Color.red()),
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

        from views.ticket_control import CloseReasonModal
        await Interaction.response.send_modal(CloseReasonModal(self.Bot, ChannelId))

    @app_commands.command(name="review", description="Submit a review for the server and services.")
    @app_commands.describe(
        rating="Rate your experience from 1 to 5 stars",
        comments="Write your review comments"
    )
    @app_commands.choices(rating=[
        app_commands.Choice(name="⭐", value=1),
        app_commands.Choice(name="⭐⭐", value=2),
        app_commands.Choice(name="⭐⭐⭐", value=3),
        app_commands.Choice(name="⭐⭐⭐⭐", value=4),
        app_commands.Choice(name="⭐⭐⭐⭐⭐", value=5),
    ])
    async def review_slash(
        self,
        Interaction: discord.Interaction,
        rating: int,
        comments: str
    ) -> None:
        HasRole = any(role.id == ReviewRequiredRoleId for role in Interaction.user.roles)
        IsAdmin = Interaction.user.guild_permissions.administrator
        
        if not (HasRole or IsAdmin):
            RoleObj = Interaction.guild.get_role(ReviewRequiredRoleId)
            RoleName = f"@{RoleObj.name}" if RoleObj else f"Role ID {ReviewRequiredRoleId}"
            await Interaction.response.send_message(
                embed=create_agency_embed(
                    Description=f"Error: You do not have the required role ({RoleName}) to submit a review.",
                    Color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        ReviewsChannel = self.Bot.get_channel(ReviewsChannelId)
        if not ReviewsChannel:
            try:
                ReviewsChannel = await self.Bot.fetch_channel(ReviewsChannelId)
            except Exception as E:
                Logger.error(f"Could not fetch reviews channel {ReviewsChannelId}: {E}")
                
        if not ReviewsChannel:
            await Interaction.response.send_message(
                embed=create_agency_embed(Description="Error: The reviews channel could not be found.", Color=discord.Color.red()),
                ephemeral=True
            )
            return

        RatingStars = "⭐" * rating + "☆" * (5 - rating)
        Metadata = f"> **Rating:** {RatingStars} ({rating}/5)\n"
        Metadata += f"> **User:** {Interaction.user.mention} (`{Interaction.user.id}`)\n"

        Container = discord.ui.Container(
            discord.ui.Section(
                "**Evernode Service Review**",
                "A member has submitted feedback for the server and services.",
                accessory=discord.ui.Thumbnail(LogoUrl)
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(Metadata),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "**Review Comments:**\n"
                f"> {comments}"
            ),
            accent_color=0xff7f17
        )
        
        LogView = discord.ui.LayoutView()
        LogView.add_item(Container)
        
        try:
            if isinstance(ReviewsChannel, discord.ForumChannel):
                PostName = f"{'⭐' * rating} - {Interaction.user.display_name}'s Review"
                await ReviewsChannel.create_thread(name=PostName, view=LogView)
            else:
                await ReviewsChannel.send(view=LogView)
            await Interaction.response.send_message(
                embed=create_agency_embed(
                    Description="Thank you! Your review has been submitted successfully.",
                    IsOfficial=True
                ),
                ephemeral=True
            )
        except Exception as E:
            Logger.error(f"Failed to send review to reviews channel: {E}", exc_info=True)
            await Interaction.response.send_message(
                embed=create_agency_embed(Description=f"Error: Failed to submit review: {E}", Color=discord.Color.red()),
                ephemeral=True
            )

async def setup(Bot: commands.Bot):
    await Bot.add_cog(TicketsCog(Bot))
