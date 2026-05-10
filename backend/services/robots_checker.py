import requests

class RobotsChecker:

    def __init__(self, domain):
        self.domain = domain

    def fetch_robots(self):
        try:
            res = requests.get(self.domain + "/robots.txt")
            self.content = res.text.lower()
            return True
        except:
            return False

    def is_allowed(self):
        if "disallow: /" in self.content:
            return False
        return True