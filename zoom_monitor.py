from contextlib import contextmanager
import time
import urllib.parse

from selenium.common.exceptions import (ElementClickInterceptedException,
                                        NoSuchElementException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from viam.logging import getLogger, setLevel

import browser

# XPath path expression to find participants button node
PARTICIPANTS_BTN = ".//*[contains(@class, 'SvgParticipants')]"


@contextmanager
def monitor_zoom(url, log_level):
    zoom = ZoomMonitor(url, log_level)
    try:
        yield zoom
    finally:
        zoom.clean_up()


class MeetingEndedException(Exception):
    """
    We'll raise this if we detect that the meeting has been ended by the host.
    """
    pass


class ZoomMonitor():
    """
    Given a URL to a Zoom meeting, join the meeting using Selenium controlling
    a Chrome browser. We provide a way to count how many meeting participants
    currently have their hands raised.
    """
    def __init__(self, url, log_level):
        self._logger = getLogger(__name__)
        self._meeting_ended = False
        setLevel(log_level)

        self._driver = browser.spawn_driver()

        raw_url = self._get_raw_url(url)
        self._logger.debug(f"parsed URL {url} to {raw_url}")
        self._driver.get(raw_url)

        self._join_meeting()

    @staticmethod
    def _get_raw_url(url):
        """
        Remove any Google redirection or Zoom prompts to the Zoom meeting.
        Returns the URL needed to connect inside the Selenium browser.
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

    def _join_meeting(self):
        """
        Set our name and join the meeting.
        """
        self._logger.debug("logging in...")
        self._wait_for_element(By.ID, "input-for-name")
        self._driver.find_element(By.ID, "input-for-name").send_keys(
            "Hand Raiser Bot")
        self._driver.find_element(By.CSS_SELECTOR, ".zm-btn").click()
        self._wait_for_element(By.XPATH, PARTICIPANTS_BTN, timeout_s=30)
        self._logger.info("logged into Zoom successfully")

    def _wait_for_element(self, approach, value, timeout_s=5):  # Helper function
        """
        Wait until there is at least one element identified by the approach
        and value. If `timeout_s` seconds elapse without such an element
        appearing, we raise an exception.

        Return the first element that is found.
        """
        WebDriverWait(self._driver, timeout_s).until(lambda _:
            len(self._driver.find_elements(approach, value)) != 0)
        return self._driver.find_elements(approach, value)[0]

    def _checkIfMeetingEnded(self):
        """
        Throw a MeetingEndedException if the meeting has been ended by the
        host, and otherwise do nothing.
        """
        try:
            modal_title = self._driver.find_element(
                By.CLASS_NAME, "zm-modal-body-title")
        except NoSuchElementException:
            return

        if modal_title.text == "This meeting has been ended by host":
            self._meeting_ended = True  # Don't try logging out later
            raise MeetingEndedException()

    def _ignore_recording(self):
        """
        If we are notified that someone is recording this meeting, click past
        so we can count hands some more. This notification can come either at
        the beginning if we joined when the recording was already in progress,
        or in the middle of the meeting if someone starts recording.
        """
        try:
            outer = self._driver.find_element(
                By.CLASS_NAME, "recording-disclaimer-dialog")
        except NoSuchElementException:
            return  # No one has started recording a video recently!

        # Click "Got it" to acknowledge that the meeting is being recorded.
        outer.find_element(By.CLASS_NAME, "zm-btn--primary").click()

    def _open_participants_list(self):
        """
        Wait until we can open the participants list, then open it, then wait
        until it's opened.
        """
        # First, check if it's already opened, and if so return immediately.
        try:
            self._driver.find_element(
                By.CLASS_NAME, "participants-wrapper__inner")
            return  # Already opened!
        except NoSuchElementException:
            pass  # We need to open it.

        # Right when we join Zoom, the participants button is not clickable so
        # we have to wait. Attempt to click the button a few times.
        for attempt in range(5):
            try:
                button = self._find_participants_button()
            except NoSuchElementException:
                self._logger.debug("Could not find participants button.")
                time.sleep(1)
                continue  # Go to the next attempt

            selected = self._is_participants_button_selected()
            try:
                # Clicking on the participants list only selects the button.
                # As a small clue: if a human clicks on it, the mouse-down
                # selects the button while the mouse-up opens the participants
                # list. Double-clicking on it seems to work okay (maybe the
                # second click implicitly creates a mouse-up on the first one).
                # If the button is already selected, only one click is needed.
                button.click()
                if not selected:
                    button.click()  # Channeling our inner grandma
            except ElementClickInterceptedException:
                self._logger.debug("DOM isn't set up; wait and try again")
                time.sleep(1)
                continue  # Go to the next attempt

            self._logger.debug("participants list clicked")
            # Now that we've clicked the participants list without raising
            # an exception, wait until it shows up.
            self._wait_for_element(
                By.CLASS_NAME, "participants-wrapper__inner")
            self._logger.info("participants list opened")
            return  # Success!

        # If we get here, none of our attempts opened the participants list.
        raise ElementClickInterceptedException(
            f"Could not open participants list after {attempt + 1} attempts")

    def _is_participants_button_selected(self):
        """
        Find the participants icon using the class name.

        The two classes the participant icon can have are:
        "SvgParticipantsDefault" - the default button class.
        "SvgParticipantsHovered" - the button is already selected.

        Return whether the participants button is selected or not.
        """

        element = self._wait_for_element(By.XPATH, PARTICIPANTS_BTN)
        return element.get_attribute("class") == "SvgParticipantsHovered"

    def _find_participants_button(self):
        """
        We want to click on an item with the participants icon. However, the
        icon itself is not clickable. A click would be intercepted by its
        grandparent element, a button with the class
        "footer-button-base__button". Since it's not obvious how to click an
        SVG element's grandparent, look through all footer buttons.

        Return the button that contains the participants icon.
        """
        for outer in self._driver.find_elements(
            By.CLASS_NAME, "footer-button-base__button"):

            try:
                self._logger.debug(
                    f"trying to find participants default in {outer}")
                # Check if this footer button contains the participants
                outer.find_element(By.XPATH, PARTICIPANTS_BTN)
                return outer
            except NoSuchElementException:
                self._logger.debug("participants not present, next...")
                continue  # wrong footer element, try the next one
        raise NoSuchElementException("could not find participants button")

    def clean_up(self):
        """
        Leave the meeting and shut down the web server.
        """
        try:  # If anything goes wrong, close the browser anyway.
            if self._meeting_ended:
                return  # Just abandon the meeting without trying to leave it.

            # Find the "leave" button and click on it.
            self._driver.find_element(
                By.CLASS_NAME, "footer__leave-btn").click()
            self._driver.find_element(
                By.CLASS_NAME, "leave-meeting-options__btn").click()
        finally:
            self._driver.quit()

    def count_hands(self):
        """
        Return the number of people in the participants list with raised hands
        """
        self._checkIfMeetingEnded()
        self._ignore_recording()

        # WARNING: there's a race condition right here. If someone starts
        # recording the meeting here, after _ignore_recording returns and
        # before _open_participants_list runs, we will time out opening the
        # list and crash. It's such an unlikely event that we haven't bothered
        # fixing it yet.

        # If someone else shares their screen, it closes the participants list.
        # So, try reopening it every time we want to count hands.
        self._open_participants_list()

        # We want to find an SVG element whose class is
        # "lazy-svg-icon__icon lazy-icon-nvf/270b". However,
        # `find_elements(By.CLASS_NAME, ...)` has problems when the class name
        # contains a slash. So, instead we use xpath to find class names that
        # contain "270b" (the hex value of the Unicode code point for the "hand
        # raised" emoji). Elements whose class contains "270b" show up in
        # several places, however, so we restrict it to only the ones that are
        # within the participants list.
        return len(self._driver.find_elements(
            By.XPATH, "//*[@class='participants-wrapper__inner']"
                      "//*[contains(@class, '270b')]"))
