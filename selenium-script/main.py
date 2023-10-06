#!/usr/bin/env python3
import hand_raiser
import time


def run():
    test = hand_raiser.SeleniumBrowser()

    test.setup_method()
    test.sign_in()

    # once signed in, poll the page for hand icons
    try:
        while True:
            time.sleep(1)
            hands = test.get_hands()
            print(hands)
    finally:
        test.teardown_method()


if __name__ == "__main__":
    run()
