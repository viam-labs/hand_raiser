#!/usr/bin/env python3
import asyncio

from audience import Audience
from robot import create_robot
import secrets


async def main():
    async with create_robot(secrets.creds, secrets.address) as (robot, board):
        audience = Audience(robot)
        button = await board.gpio_pin_by_name("18")
        led = await board.gpio_pin_by_name("16")

        should_raise = False
        old_state = False
        while True:
            button_state = await button.get()
            if button_state != old_state:
                print("button state has changed to {}!".format(button_state))
                if button_state:
                    should_raise = not should_raise
                    if should_raise:
                        await audience.increment_count()
                    else:
                        await audience.decrement_count()
            old_state = button_state
            await led.set(button_state)


if __name__ == "__main__":
    asyncio.run(main())
