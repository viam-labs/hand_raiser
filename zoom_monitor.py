from contextlib import contextmanager
import functools
import os
import subprocess
import sys
import time
import urllib.parse

from selenium.common.exceptions import (ElementClickInterceptedException,
                                        NoSuchElementException)
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from viam.logging import getLogger, setLevel


PARTICIPANTS_BTN = "//*[contains(@class, 'SvgParticipants')]"


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

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        # Uncomment this next line to keep the browser open even after this
        # process exits. It's a useful option when debugging or adding new
        # features, though it's most useful when you comment out the previous
        # line so the browser is headful.
        #chrome_options.add_experimental_option("detach", True)

        # Normally, if you hit control-C, Selenium shuts down the web browser
        # immediately. However, we want to leave the meeting before
        # disconnecting. So, we need to make the subprocess running the web
        # browser be in a separate process group from ourselves, so it doesn't
        # receive the SIGINT from the control-C.
        # Solution inspired by https://stackoverflow.com/a/62430234
        subprocess_Popen = subprocess.Popen
        if sys.version_info.major == 3 and sys.version_info.minor >= 11:
            # In recent versions of Python, Popen has a process_group argument
            # to put the new process in its own group.
            subprocess.Popen = functools.partial(
                subprocess_Popen, process_group=0)
        else:
            # In older versions, set a pre-execution function to create its own
            # process group instead.
            subprocess.Popen = functools.partial(
                subprocess_Popen, preexec_fn=lambda: os.setpgid(0, 0))
        self._driver = Chrome(options=chrome_options)
        subprocess.Popen = subprocess_Popen  # Undo the monkey patch

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

        element = self._wait_for_element(By.XPATH, PARTICIPANTS_BTN)
        hovering = element.get_attribute("class") == "SvgParticipantsHovered"
            
        # Right when we join Zoom, the participants button will exist but
        # won't yet be clickable. There's something else we're supposed to wait
        # for, but we can't figure out what. So, instead let's just try to
        # continue, and retry a few times if it fails.
        for attempt in range(5):
            # We want to click on an item in the class "SvgParticipantsDefault"
            # to open the participants list. However, that element is not
            # clickable, and instead throws an exception that the click would
            # be intercepted by its grandparent element, a button in the class
            # "footer-button-base__button". So, we'd like to find that SVG
            # element and then click on its grandparent. But it's not obvious
            # how to do that in Selenium. So, instead let's look for all of
            # those footer buttons, and then click on the one that contains the
            # participants image.
            for outer in self._driver.find_elements(
                    By.CLASS_NAME, "footer-button-base__button"):
                try:
                    self._logger.debug(
                        f"trying to find participants default in {outer}")
                    # Check if this footer button contains the participants
                    outer.find_element(By.XPATH, PARTICIPANTS_BTN)
                except NoSuchElementException:
                    self._logger.debug("participants not present, next...")
                    continue  # wrong footer element, try the next one

                try:
                    # For reasons we haven't figured out yet, something
                    # changed in late 2023 so that clicking on the participants
                    # list merely causes the button to be selected, not fully
                    # clicked. As a small clue: if a human clicks on it, the
                    # mouse-down makes the button selected, and the mouse-up
                    # actually opens the participants list. We haven't tracked
                    # down exactly what's going wrong, but double-clicking on
                    # it seems to work okay (and Alan suspects that the second
                    # click implicitly creates a mouse-up on the first one,
                    # and that's the important part).
                    # If the button is already selected, only one click is
                    # needed.
                    outer.click()
                    if not hovering:
                        outer.click()  # Channeling our inner grandma
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
        Return the element the first element that is found.
        """
        WebDriverWait(self._driver, 5).until(lambda _:
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
        # If the meeting has ended, we can't count the hands any more, so raise
        # a MeetingEndedException.
        self._checkIfMeetingEnded()

        # If someone starts recording the meeting, we'll get a pop-up modal
        # warning us about that before we can count hands again.
        self._acknowledge_recording()

        # WARNING: there's a race condition right here. If someone starts
        # recording the meeting here, after _acknowledge_recording returns and
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
