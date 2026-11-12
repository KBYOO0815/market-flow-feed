"""Bounded public-source transport. Access denials are never bypassed."""
import datetime as dt
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def read(request, attempts=3, opener=urllib.request.urlopen, pause=time.sleep):
    for attempt in range(attempts):
        try:
            with opener(request, timeout=10) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == attempts-1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts-1:
                raise
        pause(2 ** attempt)


def json_response(request):
    return json.loads(read(request))


class CollectionFetch:
    """At most six concurrent requests; cache belongs to one collection only."""
    def __init__(self, fetch):
        self.fetch, self.values, self.errors = fetch, {}, {}
        self.times = {}

    def prime(self, urls):
        urls = [u for u in dict.fromkeys(urls) if u not in self.values and u not in self.errors]
        def one(url):
            try:
                value = self.fetch(url)
                return url, value, None, dt.datetime.now(dt.timezone.utc)
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
                return url, None, error, dt.datetime.now(dt.timezone.utc)
        with ThreadPoolExecutor(max_workers=6) as pool:
            # Submit only six at a time: a fatal denial must not leave a large queue running.
            for start in range(0, len(urls), 6):
                for url, value, error, retrieved in pool.map(one, urls[start:start+6]):
                    self.times[url] = retrieved
                    if error is None: self.values[url] = value
                    else: self.errors[url] = error

    def __call__(self, url):
        if url in self.errors: raise self.errors[url]
        if url not in self.values: self.prime([url])
        if url in self.errors: raise self.errors[url]
        return self.values[url]
