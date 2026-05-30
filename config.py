import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
Logger = logging.getLogger("discord_bot")

DiscordToken = os.getenv("DISCORD_TOKEN")
GuildId = int(os.getenv("GUILD_ID", 1505693540804460656))
LogChannelId = int(os.getenv("LOG_CHANNEL_ID", 1507387151371735130))
ReviewsChannelId = int(os.getenv("REVIEWS_CHANNEL_ID", 1507172782117621761))

SupportModCategoryId = 1507173125266210926
HireUsCategoryId = 1507382459527073813
TicketPanelChannelId = 1507173146002849793

SupportRoleId = 1507382824427196598
OrderRoleId = 1507170793367539802
ModRoleId = 1507386959281258637

StaffRoleId = SupportRoleId
AlwaysSpeakRoles = [SupportRoleId, OrderRoleId, ModRoleId]
EscalateRoles = []

ModLogChannelId = 1509883419566276628
ServerLogChannelId = 1509883438851952731

LogoUrl = "https://cdn.discordapp.com/attachments/1202293162735837184/1509811386421743709/erasebg-transformed2.png?ex=6a1a88ed&is=6a19376d&hm=4968259f8889c71582f5c617809287cda6ba3315658ca99bd67e67ab398f11b8&"
ReviewRequiredRoleId = 1509812302839418891
