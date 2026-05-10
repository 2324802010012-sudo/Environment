from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests


class RobotsChecker:
    def __init__(self, domain, user_agent="*"):
        self.domain = domain.rstrip("/")
        self.user_agent = user_agent
        self.content = ""
        self.parser = RobotFileParser()

    def fetch_robots(self):
        try:
            url = urljoin(self.domain + "/", "robots.txt")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            self.content = response.text
            self.parser.parse(response.text.splitlines())
            return True
        except Exception:
            return False

    def is_allowed(self, path="/"):
        if not self.content:
            return False
        url = urljoin(self.domain + "/", path.lstrip("/"))
        return self.parser.can_fetch(self.user_agent, url)
