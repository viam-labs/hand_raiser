import functools
import os
import socket
import subprocess
import sys

from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options


def spawn_driver():
    """
    Normally, if you hit control-C, Selenium shuts down the web browser
    immediately, but we want to leave the meeting before disconnecting.
    Put the subprocess running the web browser in a separate process group
    from ourselves, so it doesn't receive the SIGINT from the control-C.
    Solution inspired by https://stackoverflow.com/a/62430234

    Return the created driver.
    """
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
    driver = Chrome(options=get_chrome_options())
    subprocess.Popen = subprocess_Popen  # Undo the monkey patch
    return driver

def get_chrome_options():
    chrome_options = Options()
    #chrome_options.add_argument("--headless=new")

    # Chromium can hang if something else is using its default remote
    # debugging port (e.g., if you've got another Chromium window open at
    # the same time. So, we give our Chromium window a brand new, ephemeral
    # port. This solution was taken from Jingyu Lei's comment on
    # https://stackoverflow.com/q/60151593
    sock=socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    chrome_options.add_argument(f"--remote-debugging-port={port}")

    # Uncomment this next line to keep the browser open even after this
    # process exits. It's a useful option when debugging or adding new
    # features, though it's most useful when you comment out the previous
    # line so the browser is headful.
    #chrome_options.add_experimental_option("detach", True)

    return chrome_options
