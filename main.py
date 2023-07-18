#!/usr/bin/env python3
import asyncio

from robot import create_robot
import secrets


class Audience:
    def __init__(self, robot):
        """
        Audience keeps track of how many people have their hands up, and raises
        and lowers the robot's hand to match. This class is thread safe.
        """
        self._robot = robot
        self._mutex = asyncio.Lock()
        self._count = 0  # Number of people in the audience raising their hands

    async def increment_count(self):
        """
        Call this to consider 1 extra person in the audience to have raised
        their hand. If this is the first person to do so, we'll raise the
        robot's hand, and otherwise we take no action.
        """
        async with self._mutex:
            self._count += 1
            if self._count == 1:
                await self._robot.raise_hand()

    async def decrement_count(self):
        """
        Call this to consider 1 extra person in the audience to have lowered
        their hand. If this is the last person who had their hand raised, we'll
        lower the robot's hand, and otherwise take no action.
        """
        async with self._mutex:
            self._count -= 1
            if self._count == 0:
                await self._robot.lower_hand()

    # TODO: either test this thoroughly or remove it. It's currently unused.
    async def set_count(self, new_value):
        """
        Call this to set the number of hands raised in the audience to a certain
        value. This is mainly used to reset the count of raised hands if someone
        forgets to lower their hand.
        """
        async with self._mutex:
            if self._count == 0 and new_value > 0:
                await self._robot.raise_hand()
            if self._count > 0 and new_value == 0:
                await self._robot.lower_hand()

            self._count = new_value


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
