#!/usr/bin/env python3
import hand_raiser
import time


def run():
    test = hand_raiser.SeleniumBrowser(
        "https://viam.zoom.us/j/85967895337?pwd=SkQ5dFRGOVlTbnRQNVhIdkJzdmFIUT09")

    try:
        while True:
            time.sleep(1)
            hands = test.get_hands()
            print(hands)
    finally:
        test.teardown_method()


if __name__ == "__main__":
    run()
