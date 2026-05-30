import discord
import datetime
from typing import Optional
from utils.embed import create_agency_embed
from config import Logger, ReviewsChannelId, LogoUrl

class ReviewLogView(discord.ui.LayoutView):
    def __init__(self, Rating: int, CustomerId: int, ClaimerId: Optional[int], Topic: str, DurationStr: str, Comments: str):
        super().__init__(timeout=None)
        RatingStars = "⭐" * Rating + "☆" * (5 - Rating)
        ClaimedStaffVal = f"<@{ClaimerId}>" if ClaimerId else "Unclaimed"
        CommentsVal = Comments.strip() if Comments else "No comments provided."
        LogoUrlVal = LogoUrl
        
        Container = discord.ui.Container(
            discord.ui.Section(
                "**Evernode Review Portal**",
                "Customer feedback has been received and archived.",
                accessory=discord.ui.Thumbnail(LogoUrlVal)
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                f"> **Rating:** {RatingStars} ({Rating}/5)\n"
                f"> **Client:** <@{CustomerId}> (`{CustomerId}`)\n"
                f"> **Department:** {Topic}\n"
                f"> **Representative:** {ClaimedStaffVal}\n"
                f"> **Duration:** {DurationStr}"
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "**Client Comments:**\n"
                f"> {CommentsVal}"
            ),
            accent_color=0xff7f17
        )
        self.add_item(Container)

class AgencyReviewModal(discord.ui.Modal):
    def __init__(self, Bot, Rating: int, CustomerId: int, ClaimerId: Optional[int], Topic: str, DurationStr: str):
        super().__init__(title="Submit Your Ticket Review")
        self.Bot = Bot
        self.Rating = Rating
        self.CustomerId = CustomerId
        self.ClaimerId = ClaimerId
        self.Topic = Topic
        self.DurationStr = DurationStr

        self.Comments = discord.ui.TextInput(
            label="Additional Comments (Optional)",
            style=discord.TextStyle.paragraph,
            placeholder="Tell us about your experience...",
            required=False,
            max_length=1000
        )
        self.add_item(self.Comments)

    async def on_submit(self, Interaction: discord.Interaction):
        await Interaction.response.defer()
        CustomerName = Interaction.user.display_name
        CommentsVal = self.Comments.value.strip() if self.Comments.value else "No comments provided."
        
        LogView = ReviewLogView(
            Rating=self.Rating,
            CustomerId=self.CustomerId,
            ClaimerId=self.ClaimerId,
            Topic=self.Topic,
            DurationStr=self.DurationStr,
            Comments=CommentsVal
        )
        
        ReviewsChannel = self.Bot.get_channel(ReviewsChannelId)
        if not ReviewsChannel:
            try:
                ReviewsChannel = await self.Bot.fetch_channel(ReviewsChannelId)
            except Exception as E:
                Logger.error(f"Could not fetch reviews channel: {E}")
                
        if ReviewsChannel:
            try:
                if isinstance(ReviewsChannel, discord.ForumChannel):
                    PostName = f"{'⭐' * self.Rating} - {CustomerName}'s Review"
                    await ReviewsChannel.create_thread(name=PostName, view=LogView)
                else:
                    await ReviewsChannel.send(view=LogView)
            except Exception as E:
                Logger.error(f"Failed to send review to reviews channel: {E}", exc_info=True)
        else:
            Logger.error(f"Reviews channel {ReviewsChannelId} not found!")

        SuccessEmbed = create_agency_embed(
            Description="**Thank you for your feedback!** Your review has been submitted successfully.",
            IsOfficial=True
        )
        await Interaction.followup.send(embed=SuccessEmbed)

class AgencyReviewView(discord.ui.LayoutView):
    def __init__(self, Bot, CustomerId: int, ClaimerId: Optional[int], Topic: str, DurationStr: str, TicketNum: int, Reason: str):
        super().__init__(timeout=600)
        self.Bot = Bot
        self.CustomerId = CustomerId
        self.ClaimerId = ClaimerId
        self.Topic = Topic
        self.DurationStr = DurationStr
        self.TicketNum = TicketNum
        self.Reason = Reason
        self.setup_layout()

    def make_callback(self, Rating: int):
        async def callback(Interaction: discord.Interaction):
            Modal = AgencyReviewModal(
                Bot=self.Bot,
                Rating=Rating,
                CustomerId=self.CustomerId,
                ClaimerId=self.ClaimerId,
                Topic=self.Topic,
                DurationStr=self.DurationStr
            )
            for Btn in self.Buttons:
                Btn.disabled = True
                if Btn.custom_id == f"rate_{Rating}":
                    Btn.style = discord.ButtonStyle.success
                else:
                    Btn.style = discord.ButtonStyle.secondary
            await Interaction.response.send_modal(Modal)
            try:
                await Interaction.message.edit(view=self)
            except Exception as E:
                Logger.error(f"Failed to edit review view: {E}")
        return callback

    def setup_layout(self):
        HandledByVal = f"<@{self.ClaimerId}>" if self.ClaimerId else "Not claimed"
        LogoUrlVal = LogoUrl
        self.Buttons = []
        for I in range(1, 6):
            BtnStyle = discord.ButtonStyle.primary if I == 5 else discord.ButtonStyle.secondary
            Btn = discord.ui.Button(
                label=f"⭐ {I}",
                style=BtnStyle,
                custom_id=f"rate_{I}"
            )
            btn_callback = self.make_callback(I)
            Btn.callback = btn_callback
            self.Buttons.append(Btn)
            
        ActionRow = discord.ui.ActionRow()
        for Btn in self.Buttons:
            ActionRow.add_item(Btn)
            
        ClosedTime = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
        TicketIdVal = f"{self.Topic.split()[0].upper()}-{self.TicketNum}"
        
        Container = discord.ui.Container(
            discord.ui.Section(
                "**Evernode | Ticket Closed**",
                "Thank you for choosing Evernode Agency. Your ticket session has been closed. We would love to hear your feedback.",
                accessory=discord.ui.Thumbnail(LogoUrlVal)
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                f"> **Session ID:** `{TicketIdVal}`\n"
                f"> **Department:** {self.Topic}\n"
                f"> **Representative:** {HandledByVal}\n"
                f"> **Duration:** {self.DurationStr}\n"
                f"> **Closure Reason:** {self.Reason}"
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay("**What would you rate your overall experience?**"),
            discord.ui.TextDisplay("-# Please select the star rating below that best reflects your overall experience."),
            ActionRow,
            discord.ui.TextDisplay(f"-# Closed on {ClosedTime}"),
            accent_color=0xff7f17
        )
        self.add_item(Container)
