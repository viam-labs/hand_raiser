import logging
import pytest
import time
from unittest.mock import patch

from ..zoom_monitor import monitor_zoom, ZoomMonitor
from .. import secrets

zoom = ZoomMonitor()
log_level = logging.INFO
# This is a real meeting link so the test can only be run with a valid
# internet connection.
meeting_link = secrets.test_meeting_link


def test_get_raw_url():
    empty_url = zoom._get_raw_url('\\')
    assert empty_url == 'https://app.zoom.us/wc/join/'

    meeting_url = zoom._get_raw_url("https://www.hello.itsme.com/woo")
    assert meeting_url == "https://app.zoom.us/wc/join/woo"


@pytest.mark.asyncio
async def test_join_meeting():
    with patch("hand_raiser.zoom_monitor.ZoomMonitor._logger.info") as mock_log_info:
        async with monitor_zoom(meeting_link, log_level):
            pass
        mock_log_info.assert_called_with("logged into Zoom successfully")


@pytest.mark.asyncio
async def test_count_hands():
    with patch("hand_raiser.zoom_monitor.ZoomMonitor._logger.info") as mock_log_info:
        async with monitor_zoom(meeting_link, log_level) as zoom:
            count = await zoom.count_hands()
            assert count == 0

            await zoom._click_child_button("Reactions", "Raise Hand")

            time.sleep(1)
            count = await zoom.count_hands()
            assert count == 1
    mock_log_info.assert_called_with("participants list opened")
