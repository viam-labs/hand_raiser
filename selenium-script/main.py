#!/usr/bin/env python3
import hand_raiser
import time

def run():
  test = hand_raiser.HandRaiser()

  test.setup_method()
  test.sign_in()

  # # once signed in, poll the page for hand icons
  # while True:
  #   time.sleep(1)
  #   hands = test.get_hands()
  #   print(hands)

run()
