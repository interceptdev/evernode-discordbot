import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.embed import create_agency_embed
from config import Logger, LogoUrl

WelcomeChannelId = 1507173077237108777
WelcomeBannerUrl = "https://cdn.discordapp.com/attachments/1202293162735837184/1509819718251577514/Untitled_design13.png?ex=6a1a90af&is=6a193f2f&hm=7314bc37096c4006ee5a454c8112c135845f9a50a2939afe0ce4a2309e2902c2&"

class WelcomeCog(commands.Cog):
    def __init__(self, Bot: commands.Bot):
        self.Bot = Bot

    async def send_welcome(self, Member: discord.Member):
        Channel = self.Bot.get_channel(WelcomeChannelId)
        if not Channel:
            try:
                Channel = await self.Bot.fetch_channel(WelcomeChannelId)
            except Exception as E:
                Logger.error(f"Failed to fetch welcome channel: {E}")
                return

        Guild = Member.guild
        MemberCount = len(Guild.members)
        
        Embed = create_agency_embed(
            Title="Welcome to Evernode Agency",
            Description="To get started, select one of the options in our ticket panel channel: <#1507172142452838401>.",
            IsOfficial=False
        )
        Embed.set_thumbnail(url=Member.display_avatar.url)
        Embed.set_image(url=WelcomeBannerUrl)
        
        try:
            await Channel.send(content=f"Welcome, {Member.mention}.", embed=Embed)
        except Exception as E:
            Logger.error(f"Failed to send welcome message: {E}", exc_info=True)

    @commands.Cog.listener()
    async def on_member_join(self, Member: discord.Member):
        await self.send_welcome(Member)

async def setup(Bot: commands.Bot):
    await Bot.add_cog(WelcomeCog(Bot))
