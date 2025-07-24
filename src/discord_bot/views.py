"""
Discord UI components (Views, Buttons, etc.) for the bot.
"""
import discord
from discord import ui
from typing import Optional


class ProductNotificationView(ui.View):
    """View with buttons for product notifications."""
    
    def __init__(self, product_url: str, uncached_url: Optional[str] = None):
        super().__init__(timeout=None)  # Persistent view
        self.product_url = product_url
        self.uncached_url = uncached_url
        
        # Add uncached link button if available
        if uncached_url:
            self.add_uncached_button()
    
    def add_uncached_button(self):
        """Add the uncached link button."""
        button = ui.Button(
            label="Uncached Link",
            style=discord.ButtonStyle.secondary,
            emoji="🌐",
            url=self.uncached_url
        )
        self.add_item(button)