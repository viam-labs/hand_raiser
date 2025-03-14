import asyncio
from contextlib import asynccontextmanager
import time
import urllib.parse

from playwright.async_api import async_playwright, TimeoutError
from viam.logging import getLogger, setLevel

import browser


# XPath path expression to find participants button node
PARTICIPANTS_BTN = "//*[contains(@class, 'SvgParticipants')]"


@asynccontextmanager
async def monitor_zoom(url, log_level):
    async with async_playwright() as p:
        # __init__ doesn't support async stuff, so do everything in our own
        # async _init function.
        zoom = ZoomMonitor()
        await zoom._init(p, url, log_level)
        try:
            yield zoom
        finally:
            await zoom.clean_up()


class MeetingEndedException(Exception):
    """
    We'll raise this if we detect that the meeting has been ended by the host.
    """
    pass


class ZoomMonitor():
    """
    Given a URL to a Zoom meeting, join the meeting using Playwright controlling
    a Chrome browser. We provide a way to count how many meeting participants
    currently have their hands raised.
    """
    async def _init(self, p, url, log_level):
        self._logger = getLogger(__name__)
        self._meeting_ended = False
        setLevel(log_level)

        # TODO: move this into browser.py
        self._browser = await browser.spawn_driver(p)
        self._driver = await self._browser.new_page()

        raw_url = self._get_raw_url(url)
        self._logger.debug(f"parsed URL {url} to {raw_url}")
        await self._driver.goto(raw_url)

        await self._join_meeting()

    @staticmethod
    def _get_raw_url(url):
        """
        Remove any Google redirection or Zoom prompts to the Zoom meeting.
        Returns the URL needed to connect inside the Playwright browser.
        """
        # Remove all blackslashes since shells may automatically add them.
        url = url.replace("\\", "")

        # Google Calendar wraps its links in a redirect. In these links, the
        # "real" URL is stored in the `q` parameter in the CGI arguments.
        parsed_url = urllib.parse.urlparse(url)
        if "google.com" in parsed_url.netloc:
            cgi_params = urllib.parse.parse_qs(parsed_url.query)
            url = cgi_params["q"][0]

        # Many links that we receive from Zoom will prompt you to open the
        # Zoom app if it's available. Replace the domain name and first couple
        # directories in the path to skip that.
        return f"https://app.zoom.us/wc/join/{url.split('/')[-1]}"

    async def _join_meeting(self):
        """
        Set our name and join the meeting.
        """
        self._logger.debug("logging in...")
        await self._driver.fill("#input-for-name", "Hand Raiser Bot")
        button = await self._driver.query_selector(".zm-btn")
        await button.click()
        await self._driver.wait_for_selector(PARTICIPANTS_BTN, state="attached")
        self._logger.info("logged into Zoom successfully")

    async def _wait_for_element(self, value, *, timeout_s=5):
        """
        Wait until there is at least one element identified by the approach
        and value. If `timeout_s` seconds elapse without such an element
        appearing, we raise a TimeoutError.
        """
        # Playwright's timeouts are all in milliseconds
        await self._driver.wait_for_selector(
            value, state="attached", timeout=timeout_s * 1000)

    async def _check_if_meeting_ended(self):
        """
        Throw a MeetingEndedException if the meeting has been ended by the
        host, and otherwise do nothing.
        """
        modal_title = await self._driver.query_selector(".zm-modal-body-title")
        if not modal_title:
            return

        if modal_title.text_content() == "This meeting has been ended by host":
            self._meeting_ended = True  # Don't try logging out later
            raise MeetingEndedException()

    async def _ignore_recording(self):
        """
        If we are notified that someone is recording this meeting, click past
        so we can count hands some more. This notification can come either at
        the beginning if we joined when the recording was already in progress,
        or in the middle of the meeting if someone starts recording.
        """
        outer = await self._driver.query_selector(
                ".recording-disclaimer-dialog")
        if not outer:
            return  # No one has started recording a video recently!

        # Click "Got it" to acknowledge that the meeting is being recorded.
        got_it_button = await outer.query_selector(".zm-btn--primary")
        await got_it_button.click()

    async def _open_participants_list(self):
        """
        Wait until we can open the participants list, then open it, then wait
        until it's opened.
        """
        # First, check if it's already opened, and if so return immediately.
        if await self._driver.query_selector(".participants-wrapper__inner"):
            return  # Already opened!

        # Right when we join Zoom, the participants button is not clickable so
        # we have to wait. Attempt to click the button a few times.
        for attempt in range(5):
            button = self._driver.get_by_role("button", name="open the participants list")
            if not button:
                self._logger.info("Could not find participants button.")
                await asyncio.sleep(1)
                continue  # Go to the next attempt

            await button.click()
            self._logger.debug("participants list clicked")

            try:
                # Now that we've clicked the participants list without raising
                # an exception, wait until it shows up. If it doesn't show up
                # yet, it might be that we've highlighted the button but
                # haven't properly clicked it, and the next iteration's attempt
                # will succeed.
                await self._wait_for_element(
                    ".participants-wrapper__inner", timeout_s=1)
            except TimeoutError:
                self._logger.info("timed out waiting for participants list,"
                                  "will try clicking again soon.")
                continue  # Go to the next attempt
            self._logger.info("participants list opened")
            return  # Success!

        # If we get here, none of our attempts opened the participants list.
        raise ValueError(
            f"Could not open participants list after {attempt + 1} attempts")

    async def clean_up(self):
        """
        Leave the meeting and shut down the web server.
        """
        try:  # If anything goes wrong, close the browser anyway.
            if self._meeting_ended:
                return  # Just abandon the meeting without trying to leave it.

            # Find the "leave" button and click on it.
            leave_button = self._driver.get_by_role("button", name="Leave")
            # Double-clicking here is super weird, but single-clicking doesn't seem to work!?
            await leave_button.dblclick()
            await self._driver.get_by_role("menuitem", name="Leave Meeting").click()
        except Exception as e:
            print(f"encountered exception: {type(e)} {e}")
            raise
        finally:
            await self._browser.close()

    async def count_hands(self):
        """
        Return the number of people in the participants list with raised hands
        """
        await self._check_if_meeting_ended()
        await self._ignore_recording()

        # WARNING: there's a race condition right here. If someone starts
        # recording the meeting here, after _ignore_recording returns and
        # before _open_participants_list runs, we will time out opening the
        # list and crash. It's such an unlikely event that we haven't bothered
        # fixing it yet.

        # If someone else shares their screen, it closes the participants list.
        # So, try reopening it every time we want to count hands.
        await self._open_participants_list()

        # We want to find an SVG element whose class is
        # "lazy-svg-icon__icon lazy-icon-nvf/270b". However,
        # `find_elements(By.CLASS_NAME, ...)` has problems when the class name
        # contains a slash. So, instead we use xpath to find class names that
        # contain "270b" (the hex value of the Unicode code point for the "hand
        # raised" emoji). Elements whose class contains "270b" show up in
        # several places, however, so we restrict it to only the ones that are
        # within the participants list.
        hands = await self._driver.query_selector_all(
            "//*[@class='participants-wrapper__inner']"
            "//*[contains(@class, '270b')]")
        return len(hands)
