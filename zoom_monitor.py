from contextlib import contextmanager
import time
import urllib.parse

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait


@contextmanager
def monitor_zoom(url):
    zoom = ZoomMonitor(url)
    try:
        yield zoom
    finally:
        zoom.clean_up()


class ZoomMonitor():
    def __init__(self, url):
        self.driver = Chrome()

        # Google Calendar wraps its links in a redirect. Check for that first
        # and remove it if relevant. The "real" URL is stored in the `q`
        # parameter in the CGI arguments.
        parsed_url = urllib.parse.urlparse(url)
        if "google.com" in parsed_url.netloc:
            cgi_params = urllib.parse.parse_qs(parsed_url.query)
            url = cgi_params["q"][0]

        # The links that we receive from Zoom prompt you to open the Zoom app
        # if it's available. Replace the domain name and first couple
        # directories in the path to skip that.
        updated_url = f"https://app.zoom.us/wc/join/{url.split('/')[-1]}"
        self.driver.get(updated_url)

        # Set our name and join the meeting
        self.wait_for_element(By.ID, "input-for-name")
        name_field = self.driver.find_element(By.ID, "input-for-name")
        name_field.send_keys("Hand Raiser Bot")
        self.driver.find_element(By.CSS_SELECTOR, ".zm-btn").click()

        self.wait_for_element(By.CLASS_NAME, "SvgParticipantsDefault")
        time.sleep(1) # The DOM isn't all set up yet; wait a little longer

        # We want to click on an item in the class "SvgParticipantsDefault" to
        # open the participants list. However, that element is not clickable,
        # and instead throws an exception that the click would be intercepted
        # by its parent element, a div in the class
        # "footer-button-base__img-layer". So, instead let's look for all of
        # those divs, and then find the one that contains the participants
        # image.
        for outer in self.driver.find_elements(
                By.CLASS_NAME, "footer-button-base__img-layer"):
            try:
                outer.find_element(By.CLASS_NAME, "SvgParticipantsDefault")
            except NoSuchElementException:
                continue # wrong footer element, try the next one
            outer.click()
            break # We found it! Skip the rest of the footer buttons.

        # Now that we've clicked the participants list, wait until it shows up.
        self.wait_for_element(By.CLASS_NAME, "participants-wrapper__inner")

    def clean_up(self):
        self.driver.quit()

    def wait_for_element(self, approach, value):  # Helper function
        WebDriverWait(self.driver, 5).until(lambda _:
            len(self.driver.find_elements(approach, value)) != 0)

    def count_hands(self):
        # We want to find an SVG element whose class is
        # "lazy-svg-icon__icon lazy-icon-nvf/270b". However,
        # `find_elements(By.CLASS_NAME, ...)` has problems when the class name
        # contains a slash. So, instead we use xpath to find class names that
        # contain "270b" (the hex value of the Unicode code point for the "hand
        # raised" emoji). Elements whose class contains "270b" show up in
        # several places, however, so we restrict it to only the ones that are
        # within the participants list.
        return len(self.driver.find_elements(
            By.XPATH, "//*[@class='participants-wrapper__inner']"
                      "//*[contains(@class, '270b')]"))
