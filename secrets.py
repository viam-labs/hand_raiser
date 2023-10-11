# Secret credentials for the robot. Ask us on Slack if you want a copy!
# If your repo is dirty after updating this file, run:
#     git update-index --skip-worktree secrets.py

from viam.rpc.dial import Credentials

creds = Credentials(
    type="robot-location-secret",
    payload="its-a-fake-secret")

address = "not-the-real-one.viam.cloud"
