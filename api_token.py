import os

def token():
    return os.getenv("SLACK_API_TOKEN")
