#!/usr/bin/env python3
import asyncio
from contextlib import asynccontextmanager

from viam.robot.client import RobotClient
from viam.rpc.dial import DialOptions
from viam.components.board import Board
from viam.components.servo import Servo

import secrets


class Robot:
    UPPER_POSITION = 30
    LOWER_POSITION = 0
    WIGGLE_AMOUNT = 5
    INACTIVITY_PERIOD_S = 5

    def __init__(self, client):
        """
        This class is in charge of raising and lowering the robot's hand, and
        wiggling the hand if it has been raised for too long.

        WARNING: this class is not thread safe!

        The client passed in is a RobotClient object.
        """
        self._client = client
        self._servo = Servo.from_robot(robot._client, "servo")

        # This will become an asyncio.Task when the hand is raised. It will
        # wiggle the hand when it has been raised for over INACTIVITY_PERIOD_S
        # seconds.
        self._wiggler = None

    async def start(self):
        """
        Ideally, this would happen in __init__, but it needs to be async.
        """
        await robot._servo.move(robot.LOWER_POSITION)

    async def stop(self):
        """
        Call this to ensure the hand is lowered and then close the connection
        with the hardware.
        """
        if self._wiggler is not None:
            await self.lower_hand()
        await self._client.close()

    @asynccontextmanager
    @staticmethod
    async def create(creds, address):
        """
        This should be considered a factory function: it creates a Robot
        object, and then closes the connection when the context manager exits.
        """
        opts = RobotClient.Options(
            refresh_interval=0,
            dial_options=DialOptions(credentials=creds)
        )
        client = await RobotClient.at_address(address, opts)

        robot = Robot(client)
        await robot.start()

        try:
            yield robot
        finally:
            await robot.stop()

    # TODO: remove this when we're ready
    def get_pi(self):
        return Board.from_robot(self._client, "pi")

    async def _wiggle_on_inactivity(self):
        """
        This is a background coroutine that wiggles the hand every
        INACTIVITY_PERIOD_S seconds. It is started when the hand is raised,
        and canceled when the hand is lowered.
        """
        try:
            while True:
                await asyncio.sleep(self.INACTIVITY_PERIOD_S)
                for _ in range(3):
                    await self._servo.move(self.UPPER_POSITION + self.WIGGLE_AMOUNT)
                    await asyncio.sleep(0.3)
                    await self._servo.move(self.UPPER_POSITION)
                    await asyncio.sleep(0.3)
        except asyncio.CancelledError:
            return

    async def raise_hand(self):
        """
        Call this to move the servo to the raised position and start the task
        that wiggles the hand on inactivity.
        """
        if self._wiggler is not None:
            print("LOGIC BUG: trying to raise already-raised hand")
            return
        await self._servo.move(self.UPPER_POSITION)
        self._wiggler = asyncio.create_task(self._wiggle_on_inactivity())

    async def lower_hand(self):
        """
        Call this to move the servo to the lowered position and stop the
        background task that wiggles the hand once in a while.
        """
        if self._wiggler is None:
            print("LOGIC BUG: trying to lower already-lowered hand")
            return
        self._wiggler.cancel()
        await self._wiggler
        self._wiggler = None
        await self._servo.move(self.LOWER_POSITION)


class Audience:
    def __init__(self, robot):
        """
        Audience keeps track of how many people have their hands up, and raises and lowers the
        robot's hand to match. This class is thread safe.
        """
        self._robot = robot
        self._mutex = asyncio.Lock()
        self._count = 0  # Number of people in the audience with their hand raised

    async def increment_count(self):
        """
        Call this to consider 1 extra person in the audience to have raised
        their hand. If this is the first person to do so, we'll raise our
        servo, and otherwise we take no action.
        """
        async with self._mutex:
            self._count += 1
            if self._count == 1:
                await self._robot.raise_hand()

    async def decrement_count(self):
        """
        Call this to consider 1 extra person in the audience to have lowered
        their hand. If this is the last person who had their hand raised, we'll
        lower our servo, and otherwise take no action.
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
    async with Robot.create(secrets.creds, secrets.address) as robot:
        audience = Audience(robot)
        pi = robot.get_pi()
        button = await pi.gpio_pin_by_name("18")
        led = await pi.gpio_pin_by_name("16")

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
