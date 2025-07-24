"""
Tests for notification repository.
"""
import pytest
import json
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.database.notification_repository import NotificationRepository
from src.models.product_data import (
    NotificationStyle, NotificationDeliveryStatus, Notification
)


@pytest.fixture
def mock_db():
    """Create a mock database connection."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_db.execute.return_value = mock_cursor
    return mock_db


@pytest.fixture
def notification_repo(mock_db):
    """Create a notification repository with mock database."""
    repo = NotificationRepository()
    repo.db = mock_db
    return repo


@pytest.fixture
def notification_style():
    """Create a sample notification style."""
    return NotificationStyle(
        embed_color=0x3498db,  # Blue
        use_thumbnail=True,
        use_footer=True,
        compact_mode=False,
        show_price_history=True,
        emoji_style="default"
    )


@pytest.fixture
def delivery_status():
    """Create a sample notification delivery status."""
    return NotificationDeliveryStatus(
        notification_id="test-notification-1",
        product_id="test-product-1",
        channel_id=123456,
        delivery_attempts=1,
        last_attempt=datetime.utcnow(),
        delivered=True,
        delivered_at=datetime.utcnow(),
        error_message=None
    )


@pytest.fixture
def notification():
    """Create a sample notification."""
    return Notification(
        product_id="test-product-1",
        channel_id=123456,
        embed_data={"title": "Test Notification", "description": "Test Description"},
        role_mentions=["<@&123>"],
        timestamp=datetime.utcnow(),
        notification_id="test-notification-1",
        scheduled_time=datetime.utcnow() + timedelta(minutes=5)
    )


def test_add_notification_style(notification_repo, notification_style, mock_db):
    """Test adding a notification style."""
    result = notification_repo.add_notification_style(
        "test-style-1", "Test Style", notification_style
    )
    
    assert result is True
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


def test_update_notification_style(notification_repo, notification_style, mock_db):
    """Test updating a notification style."""
    result = notification_repo.update_notification_style(
        "test-style-1", notification_style
    )
    
    assert result is True
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


def test_get_notification_style(notification_repo, notification_style, mock_db):
    """Test getting a notification style."""
    # Setup mock row data
    mock_row = {
        'id': 'test-style-1',
        'name': 'Test Style',
        'embed_color': notification_style.embed_color,
        'use_thumbnail': notification_style.use_thumbnail,
        'use_footer': notification_style.use_footer,
        'compact_mode': notification_style.compact_mode,
        'show_price_history': notification_style.show_price_history,
        'emoji_style': notification_style.emoji_style
    }
    
    mock_cursor = mock_db.execute.return_value
    mock_cursor.fetchone.return_value = mock_row
    
    # Mock _row_to_dict to return the mock row
    notification_repo._row_to_dict = MagicMock(return_value=mock_row)
    
    result = notification_repo.get_notification_style("test-style-1")
    
    assert result is not None
    name, style = result
    assert name == "Test Style"
    assert style.embed_color == notification_style.embed_color
    assert style.use_thumbnail == notification_style.use_thumbnail
    assert style.use_footer == notification_style.use_footer
    assert style.compact_mode == notification_style.compact_mode
    assert style.show_price_history == notification_style.show_price_history
    assert style.emoji_style == notification_style.emoji_style


def test_assign_style_to_product(notification_repo, mock_db):
    """Test assigning a style to a product."""
    result = notification_repo.assign_style_to_product(
        "test-product-1", "test-style-1"
    )
    
    assert result is True
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


def test_add_delivery_status(notification_repo, delivery_status, mock_db):
    """Test adding a delivery status."""
    result = notification_repo.add_delivery_status(delivery_status)
    
    assert result is True
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


def test_update_delivery_status(notification_repo, delivery_status, mock_db):
    """Test updating a delivery status."""
    result = notification_repo.update_delivery_status(delivery_status)
    
    assert result is True
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


def test_get_delivery_status(notification_repo, delivery_status, mock_db):
    """Test getting a delivery status."""
    # Setup mock row data
    mock_row = {
        'notification_id': delivery_status.notification_id,
        'product_id': delivery_status.product_id,
        'channel_id': delivery_status.channel_id,
        'delivery_attempts': delivery_status.delivery_attempts,
        'last_attempt': delivery_status.last_attempt.isoformat(),
        'delivered': delivery_status.delivered,
        'delivered_at': delivery_status.delivered_at.isoformat(),
        'error_message': delivery_status.error_message
    }
    
    mock_cursor = mock_db.execute.return_value
    mock_cursor.fetchone.return_value = mock_row
    
    # Mock _row_to_dict to return the mock row
    notification_repo._row_to_dict = MagicMock(return_value=mock_row)
    
    result = notification_repo.get_delivery_status("test-notification-1")
    
    assert result is not None
    assert result.notification_id == delivery_status.notification_id
    assert result.product_id == delivery_status.product_id
    assert result.channel_id == delivery_status.channel_id
    assert result.delivery_attempts == delivery_status.delivery_attempts
    assert result.delivered == delivery_status.delivered


def test_create_notification_batch(notification_repo, mock_db):
    """Test creating a notification batch."""
    result = notification_repo.create_notification_batch(
        "test-batch-1", 123456, 60
    )
    
    assert result is True
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


def test_update_batch_status(notification_repo, mock_db):
    """Test updating a batch status."""
    result = notification_repo.update_batch_status(
        "test-batch-1", "processed", datetime.utcnow()
    )
    
    assert result is True
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


def test_add_scheduled_notification(notification_repo, notification, mock_db):
    """Test adding a scheduled notification."""
    result = notification_repo.add_scheduled_notification(notification)
    
    assert result is True
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


def test_mark_scheduled_notification_processed(notification_repo, mock_db):
    """Test marking a scheduled notification as processed."""
    result = notification_repo.mark_scheduled_notification_processed("test-notification-1")
    
    assert result is True
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


def test_get_pending_scheduled_notifications(notification_repo, notification, mock_db):
    """Test getting pending scheduled notifications."""
    # Setup mock row data
    mock_row = {
        'notification_id': notification.notification_id,
        'product_id': notification.product_id,
        'channel_id': notification.channel_id,
        'scheduled_time': notification.scheduled_time.isoformat(),
        'priority': notification.priority,
        'batch_id': notification.batch_id,
        'embed_data': json.dumps(notification.embed_data),
        'role_mentions': json.dumps(notification.role_mentions)
    }
    
    mock_cursor = mock_db.execute.return_value
    mock_cursor.fetchall.return_value = [mock_row]
    
    # Mock _row_to_dict to return the mock row
    notification_repo._row_to_dict = MagicMock(return_value=mock_row)
    
    result = notification_repo.get_pending_scheduled_notifications()
    
    assert len(result) == 1
    assert result[0].notification_id == notification.notification_id
    assert result[0].product_id == notification.product_id
    assert result[0].channel_id == notification.channel_id


def test_add_price_history(notification_repo, mock_db):
    """Test adding a price history entry."""
    result = notification_repo.add_price_history("test-product-1", "€59.99")
    
    assert result is True
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


def test_get_price_history(notification_repo, mock_db):
    """Test getting price history."""
    # Setup mock row data
    now = datetime.utcnow()
    mock_rows = [
        {'price': '€59.99', 'timestamp': now.isoformat()},
        {'price': '€69.99', 'timestamp': (now - timedelta(days=1)).isoformat()}
    ]
    
    mock_cursor = mock_db.execute.return_value
    mock_cursor.fetchall.return_value = mock_rows
    
    # Mock _row_to_dict to return the mock rows
    notification_repo._row_to_dict = MagicMock(side_effect=mock_rows)
    
    result = notification_repo.get_price_history("test-product-1")
    
    assert len(result) == 2
    assert result[0][0] == '€59.99'
    assert result[1][0] == '€69.99'