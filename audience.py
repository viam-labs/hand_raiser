import asyncio
from viam.logging import getLogger, setLevel


class Audience:
    def __init__(self, robot, log_level):
        """
        Audience keeps track of how many people have their hands up, and raises
        and lowers the robot's hand to match. This class is thread safe.
        """
        self._logger = getLogger(__name__)
        setLevel(log_level)

        self._robot = robot
        self._mutex = asyncio.Lock()
        self._count = 0  # Number of people in the audience raising their hands

    async def set_count(self, new_value):
        """
        Call this to set the number of hands raised in the audience to a certain
        value.
        """
        async with self._mutex:
            self._logger.debug(f"set hand count {self._count} to {new_value}")
            if self._count == 0 and new_value > 0:
                await self._robot.raise_hand()
            if self._count > 0 and new_value == 0:
                await self._robot.lower_hand()

            self._count = new_value
