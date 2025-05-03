import discord
from discord.ext import commands
from discord.ui import View, Button
from discord.utils import get
from discord import Embed
from PIL import Image
import cv2
import numpy as np
import pytesseract
import os
import re
from datetime import datetime
from flask import Flask
import threading

# Initialize intents for the bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Initialize bot with intents
bot = commands.Bot(command_prefix="/", intents=intents)

# Flask app for keep-alive functionality
app = Flask('')


@app.route('/')
def home():
    return "Bot is running!"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = threading.Thread(target=run)
    t.start()


ALLIANCE_ROLE_MAPPING = {
    "EternalSpirit Legion": "E51S",
    "Eternal Oblivion God": "O51G",
    "ETERNAL BASTARDS": "E51B",
    "Eternal Gods Of War": "EGO#",
    "ETERNAL Flame": "E51F"
}


def extract_alliance_name(ocr_text):
    """Extract alliance name using regex from the OCR text."""
    match = re.search(r"\[[^\]]*\]\s*([\w\s]+?)(?=\s*Power|\s*$)", ocr_text)
    if match:
        return match.group(0).strip()
    return None


async def remove_old_alliance_roles(user, guild):
    """Remove all existing alliance roles from the user."""
    roles_to_remove = []
    for role in user.roles:
        if role.name in ALLIANCE_ROLE_MAPPING.values():
            roles_to_remove.append(role)

    for role in roles_to_remove:
        await user.remove_roles(role)


class RoleConfirmationView(View):

    def __init__(self, user, old_role, new_role, alliance_name, interaction):
        super().__init__(timeout=10)
        self.user = user
        self.old_role = old_role
        self.new_role = new_role
        self.alliance_name = alliance_name
        self.interaction = interaction
        self.confirmed = False

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction,
                             button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message(
                "You are not authorized to confirm this!", ephemeral=True)
            return

        self.confirmed = True
        await remove_old_alliance_roles(self.user, self.interaction.guild)
        await self.user.add_roles(self.new_role)

        success_embed = discord.Embed(
            title="✅ Role Updated Successfully!",
            description=
            (f"✨ **Your alliance role has been updated to** `{self.new_role.name}`.\n\n"
             f"⚔️ Welcome to the alliance **{self.alliance_name}**!\n\n"
             "🎯 **Prepare for battle and defend your kingdom!** 🛡️"),
            color=discord.Color.green())
        success_embed.set_thumbnail(url="https://i.imgur.com/SOJhGXT.png")
        # Updated footer
        success_embed.set_footer(
            text=
            "⚡ Powered by Lust Store ⚡ • ✨ Inquiries? Discord: @Lustyboy 🔥",
            icon_url="https://i.imgur.com/TrHnBz9.jpeg")
        await interaction.response.edit_message(embed=success_embed, view=None)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction,
                            button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message(
                "You are not authorized to confirm this!", ephemeral=True)
            return

        self.confirmed = True
        cancel_embed = discord.Embed(
            title="🔴 Role Update Cancelled!",
            description=
            (f"✨ **Your current role `{self.old_role.name}` remains unchanged.**\n\n"
             "🎯 **If this was a mistake, you can try verifying again.**"),
            color=discord.Color.red())
        cancel_embed.set_footer(
            text=
            "⚡ Powered by Lust Store ⚡ • ✨ Inquiries? Discord: @Lustyboy 🔥",
            icon_url="https://i.imgur.com/TrHnBz9.jpeg")
        await interaction.response.edit_message(embed=cancel_embed, view=None)

    async def on_timeout(self):
        if not self.confirmed:
            timeout_embed = discord.Embed(
                title="⏱️ Confirmation Timeout!",
                description=
                "❌ **You did not confirm in time. Please verify again if needed.**",
                color=discord.Color.red())
            timeout_embed.set_footer(
                text=
                "⚡ Powered by Lust Store ⚡ • ✨ Inquiries? Discord: @Lustyboy 🔥",
                icon_url="https://i.imgur.com/TrHnBz9.jpeg")
            await self.interaction.edit_original_response(embed=timeout_embed,
                                                          view=None)


@bot.tree.command(name="verify", description="Upload your game profile.")
async def verify(interaction: discord.Interaction,
                 attachment: discord.Attachment):
    await interaction.response.defer(thinking=True)
    embed_loading = discord.Embed(
        title="⚙️ Verifying Your Profile...",
        description=
        ("✨ **Commander, hold steady!**\n\n"
         "The system is analyzing your profile image to verify your alliance membership.\n\n"
         "🌟 **This won't take long!** ⏳"),
        color=discord.Color.gold())
    embed_loading.set_thumbnail(url="https://i.imgur.com/SOJhGXT.png")
    embed_loading.set_footer(
        text="⚡ Powered by Lust Store ⚡ • ✨ Inquiries? Discord: @Lustyboy 🔥",
        icon_url="https://i.imgur.com/TrHnBz9.jpeg")
    loading_message = await interaction.followup.send(embed=embed_loading,
                                                      wait=True)
    if not attachment:
        error_embed = discord.Embed(
            title="❌ Error: No Image Uploaded",
            description=
            "**Commander, I need your profile image to verify your alliance membership.**\n\n"
            "📂 **Please upload a valid image and try again.**",
            color=discord.Color.red())
        error_embed.set_footer(
            text=
            "⚡ Powered by Lust Store ⚡ • ✨ Inquiries? Discord: @Lustyboy 🔥",
            icon_url="https://i.imgur.com/TrHnBz9.jpeg")
        await loading_message.edit(embed=error_embed)
        return
    file_path = f"temp_{interaction.user.id}.png"
    await attachment.save(file_path)
    try:
        image = Image.open(file_path)
        ocr_result = pytesseract.image_to_string(image)
        alliance_name = extract_alliance_name(ocr_result)
        if alliance_name:
            role_name = ALLIANCE_ROLE_MAPPING.get(alliance_name)
            if role_name:
                new_role = get(interaction.guild.roles, name=role_name)
                for role in interaction.user.roles:
                    if role.name in ALLIANCE_ROLE_MAPPING.values(
                    ) and role != new_role:
                        confirmation_embed = discord.Embed(
                            title="⚠️ Role Confirmation Required!",
                            description=
                            (f"✨ **You already have the role** `{role.name}`.\n\n"
                             f"❓ **Do you want to switch your role to `{new_role.name}` for alliance `{alliance_name}`?**"
                             ),
                            color=discord.Color.orange())
                        confirmation_embed.set_footer(
                            text=
                            "⚡ Powered by Lust Store ⚡ • ✨ Inquiries? Discord: @Lustyboy 🔥",
                            icon_url="https://i.imgur.com/TrHnBz9.jpeg")
                        view = RoleConfirmationView(interaction.user, role,
                                                    new_role, alliance_name,
                                                    interaction)
                        await loading_message.edit(embed=confirmation_embed,
                                                   view=view)
                        return
                await interaction.user.add_roles(new_role)
                success_embed = discord.Embed(
                    title="✅ Verification Successful!",
                    description=
                    (f"✨ Welcome to the alliance **{alliance_name}**!\n\n"
                     f"⚔️ **You have been assigned the role** `{role_name}`.\n\n"
                     "🎯 **Prepare for battle and defend your kingdom!** 🛡️"),
                    color=discord.Color.green())
                success_embed.set_thumbnail(
                    url="https://i.imgur.com/SOJhGXT.png")
                success_embed.set_footer(
                    text=
                    "⚡ Powered by Lust Store ⚡ • ✨ Inquiries? Discord: @Lustyboy 🔥",
                    icon_url="https://i.imgur.com/TrHnBz9.jpeg")
                await loading_message.edit(embed=success_embed)
        else:
            error_embed = discord.Embed(
                title="⚠️ Verification Failed",
                description=
                "⚠️ **Alliance could not be detected or registered from the uploaded image.**\n\n"
                "📂 **Ensure the image is clear and shows your alliance name.**",
                color=discord.Color.orange())
            error_embed.set_footer(
                text=
                "⚡ Powered by Lust Store ⚡ • ✨ Inquiries? Discord: @Lustyboy 🔥",
                icon_url="https://i.imgur.com/TrHnBz9.jpeg")
            await loading_message.edit(embed=error_embed)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


if __name__ == "__main__":
    TOKEN = os.getenv("TOKEN")
    keep_alive()
    bot.run(TOKEN)
