import discord
from typing import Optional, Union
from config import LogoUrl

def create_agency_embed(
    *,
    Title: Optional[str] = None,
    Description: Optional[str] = None,
    Color: Optional[Union[discord.Color, int]] = None,
    IsOfficial: bool = False
) -> discord.Embed:
    EmbedColor = discord.Color(0xff7f17)
    EmbedDescription = Description or ""
    Embed = discord.Embed(title=Title, description=EmbedDescription, color=EmbedColor)
    if IsOfficial:
        Embed.set_thumbnail(url=LogoUrl)
    return Embed
