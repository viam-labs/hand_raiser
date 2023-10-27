from contextlib import contextmanager
import time
import urllib.parse

from selenium.common.exceptions import (ElementClickInterceptedException,
                                        NoSuchElementException)
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from viam.logging import getLogger, setLevel


@contextmanager
def monitor_zoom(url, log_level):
    zoom = ZoomMonitor(url, log_level)
    try:
        yield zoom
    finally:
        zoom.clean_up()


class ZoomMonitor():
    """
    Given a URL to a Zoom meeting, join the meeting using Selenium controlling
    a Chrome browser. We provide a way to count how many meeting participants
    currently have their hands raised.
    """
    def __init__(self, url, log_level):
        self._logger = getLogger(__name__)
        setLevel(log_level)

        chrome_options = Options()
        # Uncomment this line to keep the browser open even after this process
        # exits. It's a useful option when debugging or adding new features.
        #chrome_options.add_experimental_option("detach", True)

        self._driver = Chrome(options=chrome_options)

        raw_url = self._get_raw_url(url)
        self._logger.debug(f"parsed URL {url} to {raw_url}")
        self._driver.get(raw_url)

        self._join_meeting()

    @staticmethod
    def _get_raw_url(url):
        """
        Remove any Google redirection to the Zoom meeting, and then return a
        URL that should skip Zoom prompting you to open the link in their app
        (so you definitely join the meeting inside the browser that Selenium
        has opened).
        """
        # On certain unusual shells, when you paste a URL, it automatically
        # escapes the question mark symbol so the shell doesn't try to
        # pattern-match on files in the file system. If you put the URL in
        # quotes and still get those escapes, Zoom won't be able to find the
        # passcode in the URL. So, in here, we first must remove all
        # backslashes.
        url = url.replace("\\", "")

        # Google Calendar wraps its links in a redirect. Check for that first
        # and remove it if relevant. The "real" URL is stored in the `q`
        # parameter in the CGI arguments.
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
        Set our name and join the meeting. This function returns nothing.
        """
        self._logger.debug("logging in...")
        self._wait_for_element(By.ID, "input-for-name")
        self._driver.find_element(By.ID, "input-for-name").send_keys(
            "Hand Raiser Bot")
        self._driver.find_element(By.CSS_SELECTOR, ".zm-btn").click()
        self._logger.info("logged into Zoom successfully")

    def _acknowledge_recording(self):
        """
        If we are notified that someone is recording this meeting, click
        through so we can count hands some more. This notification will come
        either at the beginning if we joined when the recording was already
        in progress, or in the middle of the meeting if someone starts
        recording.
        """
        try:
            outer = self._driver.find_element(
                By.CLASS_NAME, "recording-disclaimer-dialog")
        except NoSuchElementException:
            return  # No one has started recording a video recently!

        # Click "Got it" to acknowledge that the meeting is being recorded.
        # This should allow us to open the participants list again.
        outer.find_element(By.CLASS_NAME, "zm-btn--primary").click()

    def _open_participants_list(self):
        """
        Wait until we can open the participants list, then open it, then wait
        until it's opened. This function returns nothing.
        """
        # First, check if it's already opened, and if so return immediately.
        try:
            self._driver.find_element(
                    By.CLASS_NAME, "participants-wrapper__inner")
            return  # Already opened!
        except NoSuchElementException:
            pass  # We need to open it.

        self._wait_for_element(By.CLASS_NAME, "SvgParticipantsDefault")
        # Right when we join Zoom, the participants button will exist but
        # won't yet be clickable. There's something else we're supposed to wait
        # for, but we can't figure out what. So, instead let's just try to
        # continue, and retry a few times if it fails.
        for attempt in range(5):
            # We want to click on an item in the class "SvgParticipantsDefault"
            # to open the participants list. However, that element is not
            # clickable, and instead throws an exception that the click would
            # be intercepted by its parent element, a div in the class
            # "footer-button-base__img-layer". So, we'd like to find that SVG
            # element and then click on its parent. But it's not obvious how to
            # do that in Selenium. So, instead let's look for all of those
            # footer divs, and then click on the one that contains the
            # participants image.
            for outer in self._driver.find_elements(
                    By.CLASS_NAME, "footer-button-base__img-layer"):
                try:
                    self._logger.debug(f"trying to find participants in {outer}")
                    # Check if this footer button contains the participants
                    outer.find_element(By.CLASS_NAME, "SvgParticipantsDefault")
                except NoSuchElementException:
                    self._logger.debug("participants not present, next...")
                    continue  # wrong footer element, try the next one

                try:
                    outer.click()
                    self._logger.debug("participants list clicked")
                except ElementClickInterceptedException:
                    self._logger.debug("DOM isn't set up; wait and try again")
                    time.sleep(1)  # The DOM isn't set up; wait a little longer
                    break  # Go to the next overall attempt

                # Now that we've clicked the participants list without raising
                # an exception, wait until it shows up.
                self._wait_for_element(
                    By.CLASS_NAME, "participants-wrapper__inner")
                self._logger.info("participants list opened")
                return  # Success!

        # If we get here, none of our attempts opened the participants list.
        raise ElementClickInterceptedException(
            f"Could not open participants list after {attempt + 1} attempts")

    def _wait_for_element(self, approach, value):  # Helper function
        """
        Wait until there is at least one element identified by the approach
        and value. If 5 seconds elapse without such an element appearing, we
        raise an exception.
        """
        WebDriverWait(self._driver, 5).until(lambda _:
            len(self._driver.find_elements(approach, value)) != 0)

    def clean_up(self):
        """
        Leave the meeting and shut down the web server.
        """
        try: # If anything goes wrong, close the browser anyway.
            # Find the "leave" button and click on it.
            # TODO: this next line raises a urllib3.exceptions.MaxRetryError if
            # called after you hit control-C to kill everything, but quits Zoom
            # correctly if this gets called without hitting control-C. See if
            # there's a way to get it to leave the Zoom room no matter what.
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
        # If someone starts recording the meeting, we'll get a pop-up modal
        # warning us about that before we can count hands again.
        self._acknowledge_recording()

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
