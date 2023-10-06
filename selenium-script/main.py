#!/usr/bin/env python3
import hand_raiser
import time

def run():
  print("starting run...")
  test = hand_raiser.HandRaiser()
  print("created object")

  test.setup_method()
  print("setup finished")
  test.sign_in()
  print("signin finished")

  # once signed in, poll the page for hand icons
  # while True:
  #   time.sleep(2)
  #   hands = test.get_hands()
  #   print(hands)

run()
