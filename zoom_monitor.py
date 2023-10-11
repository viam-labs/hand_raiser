from contextlib import contextmanager
import time
import urllib.parse

from selenium.common.exceptions import (ElementClickInterceptedException,
                                        NoSuchElementException)
from selenium.webdriver import Chrome
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

        self._driver = Chrome()

        raw_url = self._get_raw_url(url)
        self._logger.debug(f"updated URL {url} to {raw_url}")
        self._driver.get(raw_url)

        self._join_meeting()
        self._open_participants_list()

    @staticmethod
    def _get_raw_url(url):
        """
        Remove any Google redirection to the Zoom meeting, and then return a
        URL that should skip Zoom prompting you to open the link in their app
        (so you definitely join the meeting inside the browser that Selenium
        has opened).
        """
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
<<<<<<< HEAD
        self._logger.debug("logging in...")
        # Set our name and join the meeting
=======
        """
        Set our name and join the meeting. This function returns nothing.
        """
>>>>>>> 7efac01 (add docstrings to the ZoomMonitor class)
        self._wait_for_element(By.ID, "input-for-name")
        self._driver.find_element(By.ID, "input-for-name").send_keys(
            "Hand Raiser Bot")
        self._driver.find_element(By.CSS_SELECTOR, ".zm-btn").click()
        self._logger.info("logged into Zoom successfully")

    def _open_participants_list(self):
        """
        Wait until we can open the participants list, then open it, then wait
        until it's opened. This function returns nothing.
        """
        self._wait_for_element(By.CLASS_NAME, "SvgParticipantsDefault")
        # There's something else we're supposed to wait for, but we can't
        # figure out what. So, instead let's just try to continue, and retry a
        # few times if it fails.
        for attempt in range(5):
            # We want to click on an item in the class "SvgParticipantsDefault"
            # to open the participants list. However, that element is not
            # clickable, and instead throws an exception that the click would
            # be intercepted by its parent element, a div in the class
            # "footer-button-base__img-layer". So, we'd like to find that SVG
            # element and then click on its parent. but it's not obvious how to
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
                    self._logger.debug("participants list found")
                    # Now that we've clicked the participants list without
                    # raising an exception, wait until it shows up.
                    self._wait_for_element(
                        By.CLASS_NAME, "participants-wrapper__inner")
                    self._logger.info("participants list clicked!")
                    return  # Success!
                except ElementClickInterceptedException:
                    self._logger.debug("DOM isn't set up; wait and try again")
                    time.sleep(1)  # The DOM isn't set up; wait a little longer
                    break  # Go to the next overall attempt
        # If we get here, none of our attempts opened the participants list.
        raise ElementClickInterceptedException(
            f"Could not open participants list after {attempt + 1} attempts")

    def _wait_for_element(self, approach, value):  # Helper function
        """
        Wait until there is at least one element identified by the value within
        the approach. If 5 seconds elapse without such an element appearing,
        we raise an exception.
        """
        WebDriverWait(self._driver, 5).until(lambda _:
            len(self._driver.find_elements(approach, value)) != 0)

    def clean_up(self):
        """
        Shut down the web server.
        """
        # TODO: Might be polite to leave the Zoom meeting first.
        self._driver.quit()

    def count_hands(self):
        """
        Return the number of people in the participants list with raised hands
        """
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
