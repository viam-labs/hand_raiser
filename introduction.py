from datetime import datetime, timedelta
import json


TIME_FORMAT = "%Y/%m/%d, %H:%M:%S"


def is_introduced(url: str) -> bool:
    try:
        with open("last_intro.json", "r") as file:
            data = json.load(file)
    except FileNotFoundError:
        return False

    if url != data.get("url"):
        return False

    last_time_str = data.get("time")
    if not last_time_str:
        return False
    last_time = datetime.strptime(last_time_str, TIME_FORMAT)
    since_last = datetime.now() - last_time
    if since_last > timedelta(minutes=60):
        return False

    return True


def save_introduction(url: str):
    data = {
        "time": datetime.now().strftime(TIME_FORMAT),
        "url": url,
    }
    with open("last_intro.json", "w") as file:
        json.dump(data, file, indent=4)


if __name__ == "__main__":
    testURL = 'test'
    print(is_introduced(testURL))
    save_introduction(testURL)
    print(is_introduced(testURL))
