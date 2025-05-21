import logging
import pytest
from unittest.mock import patch

from ..zoom_monitor import monitor_zoom, ZoomMonitor


zoom = ZoomMonitor()
calendar_link = "https://www.google.com/url?q=https://viam.zoom.us/j/82970814958?pwd=r88bp5b88JBpLANJBUVIUpvSjPpyBJ.1&jst=2#success"
meeting_link = "https://app.zoom.us/wc/join/82970814958?pwd=r88bp5b88JBpLANJBUVIUpvSjPpyBJ.1"
log_level = logging.INFO


def test_get_raw_url():
    empty_url = zoom._get_raw_url('\\')
    assert empty_url == 'https://app.zoom.us/wc/join/'

    meeting_url = zoom._get_raw_url(calendar_link)
    assert meeting_url == meeting_link


@pytest.mark.asyncio
async def test_join_meeting():
    with patch("hand_raiser.zoom_monitor.ZoomMonitor._logger.info") as mock_log_info:
        async with monitor_zoom(meeting_link, log_level):
            pass
        mock_log_info.assert_called_with("logged into Zoom successfully")
