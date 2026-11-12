"""Append run-specific evidence without changing editorial research or public feeds."""
import json
import os
import re
import urllib.error
from publish_feed import api


def save(path, value):
    if not re.fullmatch(r'operations/(source-checks|publications)/[A-Za-z0-9/_-]+\.json', path):
        raise ValueError('operation path outside allowed namespaces')
    content = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    # Always leave a runner artifact, including when the GitHub write fails.
    os.makedirs('operation-artifacts', exist_ok=True)
    with open('operation-artifacts/' + path.replace('/', '_'), 'w') as stream:
        stream.write(content)
    for attempt in range(3):
        head = api('GET', 'git/ref/heads/main')['object']['sha']
        commit = api('GET', 'git/commits/' + head)
        tree = api('POST', 'git/trees', {'base_tree': commit['tree']['sha'], 'tree': [
            {'path': path, 'mode': '100644', 'type': 'blob', 'content': content}]})
        new = api('POST', 'git/commits', {'message': 'Record briefing operation evidence',
            'tree': tree['sha'], 'parents': [head]})
        try:
            api('PATCH', 'git/refs/heads/main', {'sha': new['sha'], 'force': False})
            return
        except urllib.error.HTTPError as error:
            if error.code not in (409, 422) or attempt == 2:
                raise
