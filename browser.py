import asyncio
import functools
import os
import socket
import subprocess
import sys


async def spawn_driver(playwright):
    """
    Normally, if you hit control-C, Playwright shuts down the web browser
    immediately, but we want to leave the meeting before disconnecting.
    Put the subprocess running the web browser in a separate process group
    from ourselves, so it doesn't receive the SIGINT from the control-C.
    Solution inspired by https://stackoverflow.com/a/62430234

    Return the created driver.
    """
    print("monkey patching...")
    asyncio_create_subprocess_exec = asyncio.create_subprocess_exec
    asyncio_create_subprocess_shell = asyncio.create_subprocess_shell
    if sys.version_info.major == 3 and sys.version_info.minor >= 11:
        # In recent versions of Python, Popen has a process_group argument
        # to put the new process in its own group.
        asyncio.create_subprocess_exec = functools.partial(
            asyncio_create_subprocess_exec, process_group=0)
        asyncio.create_subprocess_shell = functools.partial(
            asyncio_create_subprocess_shell, process_group=0)
    else:
        # In older versions, set a pre-execution function to create its own
        # process group instead.
        asyncio.create_subprocess_exec = functools.partial(
            asyncio_create_subprocess_exec, preexec_fn=lambda: os.setpgid(0, 0))
        asyncio.create_subprocess_shell = functools.partial(
            asyncio_create_subprocess_shell, preexec_fn=lambda: os.setpgid(0, 0))
    driver = await playwright.webkit.launch(headless=False)
    # Undo the monkey patch
    asyncio.create_subprocess_exec = asyncio_create_subprocess_exec
    asyncio.create_subprocess_shell = asyncio_create_subprocess_shell
    print("done monkey patching!")
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
