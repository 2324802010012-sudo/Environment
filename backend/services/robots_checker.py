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


def check_openmeteo_compliance(user_agent="*"):
    """Return a compact compliance report for the main data source."""
    checker = RobotsChecker("https://open-meteo.com", user_agent=user_agent)
    robots_available = checker.fetch_robots()

    return {
        "source": "Open-Meteo Air Quality API",
        "api_url": "https://air-quality-api.open-meteo.com/v1/air-quality",
        "docs_url": "https://open-meteo.com/en/docs/air-quality-api",
        "collection_method": "API",
        "uses_prebuilt_dataset": False,
        "requires_api_key": False,
        "robots_txt_checked": robots_available,
        "docs_path_allowed": checker.is_allowed("/en/docs/air-quality-api") if robots_available else None,
        "note": "Open-Meteo is consumed through its public API, not by scraping HTML pages.",
    }
