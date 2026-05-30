import html
import datetime
import discord
from config import StaffRoleId, AlwaysSpeakRoles, EscalateRoles, LogoUrl

async def generate_channel_transcript_html(Channel: discord.TextChannel, TicketInfo: dict) -> str:
    Guild = Channel.guild
    OpenerId = TicketInfo["user_id"]
    Category = TicketInfo["category"]
    
    ClaimerName = "Unclaimed"
    if TicketInfo.get("claimed_by"):
        ClaimerMember = Guild.get_member(TicketInfo["claimed_by"])
        if ClaimerMember:
            ClaimerName = ClaimerMember.display_name
        else:
            ClaimerName = f"Staff ID: {TicketInfo['claimed_by']}"

    Messages = []
    async for Msg in Channel.history(limit=None, oldest_first=True):
        if Msg.author.bot:
            if Msg.author == Guild.me and (Msg.components or not Msg.content):
                continue
        Messages.append(Msg)

    MessagesHtml = ""
    for Msg in Messages:
        IsStaff = False
        if hasattr(Msg.author, "roles"):
            AuthorRoleIds = {R.id for R in Msg.author.roles}
            if StaffRoleId in AuthorRoleIds or any(RId in AuthorRoleIds for RId in AlwaysSpeakRoles) or any(RId in AuthorRoleIds for RId in EscalateRoles):
                IsStaff = True
        
        if Msg.author.id == OpenerId:
            IsStaff = False
            
        RoleClass = "staff" if IsStaff else "customer"
        RoleLabel = "Staff" if IsStaff else "Customer"
        RoleBadge = f'<span class="badge {RoleClass}">{RoleLabel}</span>'
        
        AttachmentsHtml = ""
        if Msg.attachments:
            AttachmentsHtml = '<div class="attachments">'
            for Attachment in Msg.attachments:
                Url = Attachment.url
                IsImage = any(Url.lower().split("?")[0].endswith(Ext) for Ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"])
                if IsImage:
                    AttachmentsHtml += f'<div class="attachment-item"><a href="{Url}" target="_blank"><img src="{Url}" alt="Attachment"></a></div>'
                else:
                    Filename = Attachment.filename
                    AttachmentsHtml += f'<a class="attachment-file" href="{Url}" target="_blank">{html.escape(Filename)}</a>'
            AttachmentsHtml += '</div>'
            
        Content = Msg.clean_content or ""
        EscapedContent = html.escape(Content)
        
        if "```" in EscapedContent:
            Parts = EscapedContent.split("```")
            for Idx in range(1, len(Parts), 2):
                CodeText = Parts[Idx]
                Lines = CodeText.split("\n", 1)
                Lang = ""
                CodeContent = CodeText
                if len(Lines) > 1 and len(Lines[0].strip()) < 10 and Lines[0].strip().isalnum():
                    Lang = Lines[0].strip()
                    CodeContent = Lines[1]
                Parts[Idx] = f'<pre class="code-block" data-lang="{Lang}"><code>{CodeContent.strip()}</code></pre>'
            EscapedContent = "".join(Parts)
        
        TimestampStr = Msg.created_at.strftime("%I:%M %p")
        AvatarUrl = Msg.author.display_avatar.url
        
        MessagesHtml += f"""
        <div class="message-card {RoleClass}">
            <img class="avatar" src="{AvatarUrl}" alt="Avatar">
            <div class="message-body">
                <div class="message-header">
                    <span class="username {RoleClass}">{html.escape(Msg.author.display_name)}</span>
                    {RoleBadge}
                    <span class="timestamp">{TimestampStr}</span>
                </div>
                <div class="text">{EscapedContent}</div>
                {AttachmentsHtml}
            </div>
        </div>
        """

    TicketIdVal = f"#{TicketInfo['ticket_num']:04d}"
    
    HtmlTemplate = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transcript - {html.escape(Category.capitalize())} {TicketIdVal}</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-main: #060709;
            --bg-card: #0c0e12;
            --bg-card-hover: #11141a;
            --border-muted: #1a1e26;
            --border-glow: rgba(255, 127, 23, 0.2);
            --accent-color: #ff7f17;
            --accent-glow: rgba(255, 127, 23, 0.4);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --text-muted-dark: #4b5563;
            
            --accent-customer: #ff7f17;
            --accent-staff: #38bdf8;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            background-color: var(--bg-main);
            color: var(--text-main);
            font-family: 'Plus Jakarta Sans', sans-serif;
            letter-spacing: -0.015em;
            display: flex;
            min-height: 100vh;
        }}

        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: var(--bg-main);
        }}
        ::-webkit-scrollbar-thumb {{
            background: var(--border-muted);
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: var(--accent-color);
        }}
        
        .wrapper {{
            display: flex;
            width: 100%;
            max-width: 1440px;
            margin: 0 auto;
            position: relative;
        }}
        
        .sidebar {{
            width: 320px;
            border-right: 1px solid var(--border-muted);
            background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-main) 100%);
            padding: 40px 30px;
            display: flex;
            flex-direction: column;
            gap: 32px;
            height: 100vh;
            position: sticky;
            top: 0;
            flex-shrink: 0;
        }}
        
        .logo-section {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .brand-logo {{
            width: 50px;
            height: 50px;
            border-radius: 12px;
            border: 2px solid var(--accent-color);
            box-shadow: 0 0 15px var(--border-glow);
            object-fit: cover;
        }}
        
        .logo-section h1 {{
            font-size: 18px;
            font-weight: 700;
            color: var(--text-main);
        }}
        
        .logo-section h1 span {{
            color: var(--accent-color);
        }}

        .ticket-badge-large {{
            background: linear-gradient(135deg, rgba(255, 127, 23, 0.1) 0%, rgba(255, 127, 23, 0.02) 100%);
            border: 1px solid var(--border-glow);
            border-radius: 16px;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        
        .ticket-badge-large .label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-muted);
            font-weight: 600;
        }}
        
        .ticket-badge-large .value {{
            font-size: 32px;
            font-weight: 800;
            color: var(--accent-color);
            text-shadow: 0 0 10px rgba(255, 127, 23, 0.3);
        }}
        
        .meta-list {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        
        .meta-item {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        
        .meta-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted-dark);
            font-weight: 700;
        }}
        
        .meta-value {{
            font-size: 14px;
            color: var(--text-main);
            font-weight: 500;
            word-break: break-all;
        }}
        
        .chat-area {{
            flex-grow: 1;
            padding: 40px 60px;
            background-color: var(--bg-main);
            display: flex;
            flex-direction: column;
            gap: 32px;
            max-width: calc(100% - 320px);
        }}
        
        .chat-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-muted);
            padding-bottom: 24px;
        }}
        
        .chat-title {{
            font-size: 24px;
            font-weight: 800;
            color: var(--text-main);
        }}
        
        .chat-subtitle {{
            font-size: 14px;
            color: var(--text-muted);
            margin-top: 4px;
        }}
        
        .messages-container {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        
        .message-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-muted);
            border-radius: 16px;
            padding: 20px;
            display: flex;
            gap: 16px;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }}
        
        .message-card:hover {{
            background: var(--bg-card-hover);
            border-color: rgba(255, 127, 23, 0.3);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            transform: translateY(-2px);
        }}
        
        .message-card.staff {{
            border-left: 3px solid var(--accent-staff);
        }}
        
        .message-card.customer {{
            border-left: 3px solid var(--accent-customer);
        }}
        
        .avatar {{
            width: 44px;
            height: 44px;
            border-radius: 12px;
            object-fit: cover;
            border: 1px solid var(--border-muted);
            flex-shrink: 0;
        }}
        
        .message-body {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            width: 100%;
        }}
        
        .message-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }}
        
        .username {{
            font-weight: 700;
            font-size: 15px;
            color: var(--text-main);
        }}
        
        .username.staff {{
            color: var(--accent-staff);
        }}
        
        .username.customer {{
            color: var(--accent-customer);
        }}
        
        .badge {{
            font-size: 9px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 6px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .badge.staff {{
            background-color: rgba(56, 189, 248, 0.1);
            color: var(--accent-staff);
            border: 1px solid rgba(56, 189, 248, 0.2);
        }}
        
        .badge.customer {{
            background-color: rgba(255, 127, 23, 0.1);
            color: var(--accent-customer);
            border: 1px solid rgba(255, 127, 23, 0.2);
        }}
        
        .timestamp {{
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 500;
            margin-left: auto;
        }}
        
        .text {{
            font-size: 14px;
            line-height: 1.6;
            color: var(--text-main);
            white-space: pre-wrap;
            word-break: break-word;
        }}
        
        .code-block {{
            background: #050608;
            border: 1px solid var(--border-muted);
            border-radius: 10px;
            padding: 16px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            overflow-x: auto;
            margin-top: 8px;
            position: relative;
        }}
        
        .code-block::before {{
            content: attr(data-lang);
            position: absolute;
            top: 4px;
            right: 12px;
            font-size: 10px;
            color: var(--text-muted-dark);
            text-transform: uppercase;
            font-weight: 700;
        }}
        
        .attachments {{
            margin-top: 12px;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }}
        
        .attachment-item {{
            max-width: 100%;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border-muted);
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            transition: transform 0.2s;
        }}
        
        .attachment-item:hover {{
            transform: scale(1.01);
        }}
        
        .attachment-item img {{
            max-width: 100%;
            max-height: 350px;
            display: block;
        }}
        
        .attachment-file {{
            background-color: #0d0e12;
            border: 1px solid var(--border-muted);
            padding: 12px 16px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
            color: var(--accent-color);
            text-decoration: none;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.2s;
        }}
        
        .attachment-file:hover {{
            background-color: var(--border-muted);
            box-shadow: 0 0 10px var(--border-glow);
        }}
        
        .transcript-footer {{
            text-align: center;
            font-size: 12px;
            color: var(--text-muted-dark);
            padding: 40px 0;
            border-top: 1px solid var(--border-muted);
            margin-top: 40px;
            font-weight: 600;
        }}
        
        @media (max-width: 900px) {{
            body {{
                flex-direction: column;
            }}
            .sidebar {{
                width: 100%;
                height: auto;
                position: relative;
                border-right: none;
                border-bottom: 1px solid var(--border-muted);
                padding: 30px;
            }}
            .chat-area {{
                max-width: 100%;
                padding: 30px 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="wrapper">
        <aside class="sidebar">
            <div class="logo-section">
                <img class="brand-logo" src="{LogoUrl}" alt="Logo">
                <h1>Evernode<span>.</span></h1>
            </div>
            
            <div class="ticket-badge-large">
                <span class="label">Ticket Reference</span>
                <span class="value">{TicketIdVal}</span>
            </div>
            
            <div class="meta-list">
                <div class="meta-item">
                    <span class="meta-label">Department</span>
                    <span class="meta-value">{html.escape(Category.capitalize())}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Customer Reference</span>
                    <span class="meta-value">User ID: {OpenerId}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Assigned Agent</span>
                    <span class="meta-value">{html.escape(ClaimerName)}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Export Timestamp</span>
                    <span class="meta-value">{datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p")}</span>
                </div>
            </div>
        </aside>
        
        <main class="chat-area">
            <header class="chat-header">
                <div>
                    <h2 class="chat-title">{html.escape(Category.capitalize())} Log</h2>
                    <p class="chat-subtitle">Permanent archives of the correspondence between client and staff.</p>
                </div>
            </header>
            
            <section class="messages-container">
                {MessagesHtml}
            </section>
            
            <footer class="transcript-footer">
                © {datetime.datetime.now().year} Evernode Agency • Support Logs Portal
            </footer>
        </main>
    </div>
</body>
</html>"""
    return HtmlTemplate
