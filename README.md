# Hand Raiser robot for Zoom meetings

When we have large meetings, sometimes the remote employees are unable to participate in the Q&A section at the end, even though they're able to view the main meeting over Zoom. This repo provides a way for a robot to join the Zoom meeting and raise a physical hand in the (meatspace) meeting room when someone on Zoom has a question.

## Installation

1. Clone this repo locally.
2. Run `pip install -r requirements.txt` to install the dependencies.
3. Edit `secrets.py` so it contains the robot's secret and URL. You can get these from anyone who worked on this project.
4. Step 3 probably made the repo dirty. Run `git update-index --skip-worktree secrets.py` to make the repo clean again.

## Running
1. When you want Hand Raiser Bot to join a meeting, run `./main.py '<url-of-zoom-meeting>'` to start it. The URL likely contains a question mark, so we recommend enclosing the entire URL in single quotes so your terminal doesn't try pattern-matching on it.
2. This will open a Chrome window and join the Zoom meeting as the user "Hand Raiser Bot".
3. Whenever someone in the Zoom meeting selects the "Raise Hand" reaction, we'll move the servo on the robot. It will be raised whenever _at least 1_ person in the Zoom meeting has their hand raised, and lowered again when no one has their hand raised.
4. If Hand Raiser Bot's servo has been raised for at least 30 seconds, we will wiggle it side to side, to try to call attention to ourselves.
5. When the meeting is over (or when you want Hand Raiser Bot to leave), hit control-C in the terminal to shut everything down. This will also lower the servo even if someone in the Zoom meeting still has their hand raised.

## Code Layout
- `robot.py` is how to talk to Viam to move the hardware itself. This can raise and lower the servo, and wiggle it if it has been raised for long enough.
- `audience.py` is how to keep track of how many hands are raised. This will tell the robot when it's time to raise and lower the hand.
- `zoom_monitor.py` is how to use Selenium to open a web browser and join the Zoom meeting. It lets you count how many participants in the meeting have their hands raised.
  - As of summer 2023, Zoom did not have an official API for participart reactions like whether someone has raised their hand. Consequently, we're getting this data by webscraping with Selenium.
- `secrets.py` contains the way to connect to the robot itself. This repo does not contain production data: this file must be edited before things will work.
- `main.py` ties everything together: it sets up a ZoomMonitor, connects to a robot, wraps the robot in an Audience object, and then sets the hand count in the Audience based on what is reported from the ZoomMonitor.