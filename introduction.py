from datetime import datetime
import json


TIME_FORMAT = "%Y/%m/%d, %H:%M:%S"


def save_introduction(url: str):
    data = {
        "time": datetime.now().strftime(TIME_FORMAT),
        "url": url,
    }
    with open("introductions.json", "w") as file:
        json.dump(data, file, indent=4)


if __name__ == "__main__":
    save_introduction('test')
