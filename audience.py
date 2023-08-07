import asyncio


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
