"""
Tests for mock services used for external API testing.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import aiohttp
from datetime import datetime

from src.models.product_data import ProductData, StockStatus


class MockHttpClient:
    """Mock HTTP client for testing."""
    
    def __init__(self):
        """Initialize mock HTTP client."""
        self.responses = {}
        self.default_response = "<html><body>Default response</body></html>"
        self.call_count = 0
        self.last_url = None
        self.last_headers = None
        self.should_raise = False
        self.error_to_raise = None
    
    def set_response(self, url, html_content):
        """Set a response for a specific URL."""
        self.responses[url] = html_content
    
    def set_default_response(self, html_content):
        """Set the default response for any URL."""
        self.default_response = html_content
    
    def set_error(self, error):
        """Configure the client to raise an error."""
        self.should_raise = True
        self.error_to_raise = error
    
    def reset(self):
        """Reset the mock client state."""
        self.call_count = 0
        self.last_url = None
        self.last_headers = None
        self.should_raise = False
    
    async def get(self, url, headers=None, **kwargs):
        """Mock GET request."""
        self.call_count += 1
        self.last_url = url
        self.last_headers = headers
        
        if self.should_raise and self.error_to_raise:
            raise self.error_to_raise
        
        # Create mock response
        response = AsyncMock()
        response.status = 200
        response.text = AsyncMock(return_value=self.responses.get(url, self.default_response))
        response.raise_for_status = AsyncMock()
        
        return response
    
    async def close(self):
        """Mock close method."""
        pass


class MockDiscordClient:
    """Mock Discord client for testing."""
    
    def __init__(self):
        """Initialize mock Discord client."""
        self.sent_messages = []
        self.channels = {}
        self.should_fail = False
        self.rate_limited = False
    
    def add_channel(self, channel_id, name):
        """Add a mock channel."""
        self.channels[channel_id] = {
            "id": channel_id,
            "name": name,
            "messages": []
        }
    
    def set_should_fail(self, should_fail):
        """Configure the client to fail sending messages."""
        self.should_fail = should_fail
    
    def set_rate_limited(self, rate_limited):
        """Configure the client to simulate rate limiting."""
        self.rate_limited = rate_limited
    
    def get_channel(self, channel_id):
        """Get a channel by ID."""
        if channel_id not in self.channels:
            return None
            
        channel = MagicMock()
        channel.id = channel_id
        channel.name = self.channels[channel_id]["name"]
        
        async def mock_send(content=None, embed=None):
            if self.should_fail:
                raise Exception("Failed to send message")
                
            if self.rate_limited:
                response = MagicMock()
                response.status = 429
                raise discord.errors.HTTPException(response, "You are being rate limited")
                
            message = {
                "channel_id": channel_id,
                "content": content,
                "embed": embed,
                "timestamp": datetime.utcnow()
            }
            self.sent_messages.append(message)
            self.channels[channel_id]["messages"].append(message)
            
            return MagicMock()
            
        channel.send = mock_send
        return channel
    
    def reset(self):
        """Reset the mock client state."""
        self.sent_messages = []
        for channel_id in self.channels:
            self.channels[channel_id]["messages"] = []
        self.should_fail = False
        self.rate_limited = False


class TestMockHttpClient:
    """Test the mock HTTP client."""
    
    @pytest.mark.asyncio
    async def test_mock_http_client_basic(self):
        """Test basic functionality of mock HTTP client."""
        client = MockHttpClient()
        
        # Set a specific response
        client.set_response(
            "https://www.bol.com/product/123",
            "<html><body>Product 123</body></html>"
        )
        
        # Make a request
        response = await client.get("https://www.bol.com/product/123")
        
        # Verify response
        assert response.status == 200
        assert await response.text() == "<html><body>Product 123</body></html>"
        assert client.call_count == 1
        assert client.last_url == "https://www.bol.com/product/123"
    
    @pytest.mark.asyncio
    async def test_mock_http_client_default_response(self):
        """Test default response of mock HTTP client."""
        client = MockHttpClient()
        
        # Set default response
        client.set_default_response("<html><body>Default HTML</body></html>")
        
        # Make a request to a URL without specific response
        response = await client.get("https://www.bol.com/unknown")
        
        # Verify default response is returned
        assert await response.text() == "<html><body>Default HTML</body></html>"
    
    @pytest.mark.asyncio
    async def test_mock_http_client_error(self):
        """Test error handling in mock HTTP client."""
        client = MockHttpClient()
        
        # Configure client to raise an error
        client.set_error(aiohttp.ClientConnectionError("Connection refused"))
        
        # Make a request that should fail
        with pytest.raises(aiohttp.ClientConnectionError) as excinfo:
            await client.get("https://www.bol.com/product/123")
        
        # Verify error
        assert "Connection refused" in str(excinfo.value)
        assert client.call_count == 1
    
    @pytest.mark.asyncio
    async def test_mock_http_client_headers(self):
        """Test headers handling in mock HTTP client."""
        client = MockHttpClient()
        
        # Make a request with headers
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "nl-NL"
        }
        await client.get("https://www.bol.com/product/123", headers=headers)
        
        # Verify headers were captured
        assert client.last_headers == headers
    
    @pytest.mark.asyncio
    async def test_mock_http_client_reset(self):
        """Test resetting the mock HTTP client."""
        client = MockHttpClient()
        
        # Make some requests
        await client.get("https://www.bol.com/product/123")
        await client.get("https://www.bol.com/product/456")
        
        assert client.call_count == 2
        
        # Reset client
        client.reset()
        
        # Verify state was reset
        assert client.call_count == 0
        assert client.last_url is None
        assert client.last_headers is None


class TestMockDiscordClient:
    """Test the mock Discord client."""
    
    @pytest.mark.asyncio
    async def test_mock_discord_client_basic(self):
        """Test basic functionality of mock Discord client."""
        client = MockDiscordClient()
        
        # Add a channel
        client.add_channel(123456789, "pokemon-alerts")
        
        # Get the channel
        channel = client.get_channel(123456789)
        
        # Send a message
        await channel.send(content="Test message")
        
        # Verify message was sent
        assert len(client.sent_messages) == 1
        assert client.sent_messages[0]["content"] == "Test message"
        assert client.sent_messages[0]["channel_id"] == 123456789
    
    @pytest.mark.asyncio
    async def test_mock_discord_client_with_embed(self):
        """Test sending embeds with mock Discord client."""
        client = MockDiscordClient()
        
        # Add a channel
        client.add_channel(123456789, "pokemon-alerts")
        
        # Create a mock embed
        embed = MagicMock()
        embed.title = "Product Alert"
        embed.description = "Pokemon Scarlet is now in stock!"
        
        # Get the channel and send embed
        channel = client.get_channel(123456789)
        await channel.send(embed=embed)
        
        # Verify embed was sent
        assert len(client.sent_messages) == 1
        assert client.sent_messages[0]["embed"] == embed
        assert client.sent_messages[0]["embed"].title == "Product Alert"
    
    @pytest.mark.asyncio
    async def test_mock_discord_client_failure(self):
        """Test failure handling in mock Discord client."""
        client = MockDiscordClient()
        
        # Add a channel
        client.add_channel(123456789, "pokemon-alerts")
        
        # Configure client to fail
        client.set_should_fail(True)
        
        # Get the channel
        channel = client.get_channel(123456789)
        
        # Attempt to send a message
        with pytest.raises(Exception) as excinfo:
            await channel.send(content="Test message")
        
        # Verify error
        assert "Failed to send message" in str(excinfo.value)
        
        # Verify no messages were sent
        assert len(client.sent_messages) == 0
    
    @pytest.mark.asyncio
    async def test_mock_discord_client_rate_limit(self):
        """Test rate limit handling in mock Discord client."""
        client = MockDiscordClient()
        
        # Add a channel
        client.add_channel(123456789, "pokemon-alerts")
        
        # Configure client to be rate limited
        client.set_rate_limited(True)
        
        # Get the channel
        channel = client.get_channel(123456789)
        
        # Attempt to send a message
        with pytest.raises(Exception) as excinfo:
            await channel.send(content="Test message")
        
        # Verify rate limit error
        assert "rate limited" in str(excinfo.value).lower()
        
        # Verify no messages were sent
        assert len(client.sent_messages) == 0
    
    @pytest.mark.asyncio
    async def test_mock_discord_client_multiple_channels(self):
        """Test handling multiple channels in mock Discord client."""
        client = MockDiscordClient()
        
        # Add multiple channels
        client.add_channel(111111, "channel-1")
        client.add_channel(222222, "channel-2")
        client.add_channel(333333, "channel-3")
        
        # Send messages to different channels
        await client.get_channel(111111).send(content="Message 1")
        await client.get_channel(222222).send(content="Message 2")
        await client.get_channel(333333).send(content="Message 3")
        
        # Verify messages were sent to correct channels
        assert len(client.sent_messages) == 3
        
        # Check channel-specific messages
        assert len(client.channels[111111]["messages"]) == 1
        assert len(client.channels[222222]["messages"]) == 1
        assert len(client.channels[333333]["messages"]) == 1
        
        assert client.channels[111111]["messages"][0]["content"] == "Message 1"
        assert client.channels[222222]["messages"][0]["content"] == "Message 2"
        assert client.channels[333333]["messages"][0]["content"] == "Message 3"
    
    @pytest.mark.asyncio
    async def test_mock_discord_client_reset(self):
        """Test resetting the mock Discord client."""
        client = MockDiscordClient()
        
        # Add a channel and send messages
        client.add_channel(123456789, "pokemon-alerts")
        await client.get_channel(123456789).send(content="Test message")
        
        assert len(client.sent_messages) == 1
        
        # Reset client
        client.reset()
        
        # Verify state was reset
        assert len(client.sent_messages) == 0
        assert len(client.channels[123456789]["messages"]) == 0
        assert not client.should_fail
        assert not client.rate_limited


class TestIntegratedMockServices:
    """Test using mock services together for integration testing."""
    
    @pytest.mark.asyncio
    async def test_monitoring_to_notification_flow(self):
        """Test the flow from monitoring to notification using mock services."""
        # Create mock services
        http_client = MockHttpClient()
        discord_client = MockDiscordClient()
        
        # Add a Discord channel
        discord_client.add_channel(123456789, "pokemon-alerts")
        
        # Configure HTTP client with product data
        http_client.set_response(
            "https://www.bol.com/nl/nl/p/pokemon-scarlet/9300000096287/",
            """
            <html>
                <head><title>Pokemon Scarlet - bol.com</title></head>
                <body>
                    <div class="product-title">Pokemon Scarlet</div>
                    <div class="product-price">€59.99</div>
                    <div class="product-image"><img src="https://example.com/image.jpg"></div>
                    <div class="product-stock">Op voorraad</div>
                    <div class="product-delivery">Bezorging binnen 24 uur</div>
                </body>
            </html>
            """
        )
        
        # Create a simple monitoring function that uses the mock HTTP client
        async def monitor_product(url):
            response = await http_client.get(url)
            html = await response.text()
            
            # Simple parsing (in a real system this would be more sophisticated)
            product_data = ProductData(
                title="Pokemon Scarlet",
                price="€59.99",
                original_price="€69.99",
                image_url="https://example.com/image.jpg",
                product_url=url,
                uncached_url=url,
                stock_status=StockStatus.IN_STOCK.value,
                stock_level="Op voorraad",
                website="bol.com",
                delivery_info="Bezorging binnen 24 uur",
                sold_by_bol=True,
                last_checked=datetime.utcnow(),
                product_id="test-product-123"
            )
            
            return product_data
        
        # Create a simple notification function that uses the mock Discord client
        async def send_notification(product_data, channel_id):
            channel = discord_client.get_channel(channel_id)
            
            # Create a simple message
            message = f"ALERT: {product_data.title} is now in stock for {product_data.price}!"
            
            # Send the notification
            await channel.send(content=message)
            
            return True
        
        # Execute the monitoring-to-notification flow
        url = "https://www.bol.com/nl/nl/p/pokemon-scarlet/9300000096287/"
        channel_id = 123456789
        
        # Monitor the product
        product_data = await monitor_product(url)
        
        # Send notification
        success = await send_notification(product_data, channel_id)
        
        # Verify the flow worked correctly
        assert success is True
        assert http_client.call_count == 1
        assert len(discord_client.sent_messages) == 1
        
        # Verify notification content
        notification = discord_client.sent_messages[0]
        assert "Pokemon Scarlet" in notification["content"]
        assert "€59.99" in notification["content"]
        assert notification["channel_id"] == channel_id
"""