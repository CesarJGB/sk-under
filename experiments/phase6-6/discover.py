#!/usr/bin/env python3
"""Read-only discovery of public authorization metadata; never accepts secrets."""
import json
import sys
import urllib.error
import urllib.request

HOSTS = ("https://accounts.chillyroom.com", "https://api-gateway.soulknight.chillyroom.com")
PATHS = ("/.well-known/openid-configuration", "/.well-known/oauth-authorization-server")

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def probe(opener, url):
    try:
        with opener.open(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=10) as response:
            content_type = response.headers.get_content_type()
            data = response.read(65537)
            if len(data) > 65536:
                return {"url": url, "status": response.status, "result": "response_too_large"}
            try:
                document = json.loads(data) if content_type == "application/json" else None
            except (ValueError, UnicodeDecodeError):
                document = None
            required = ("issuer", "authorization_endpoint", "token_endpoint")
            valid = isinstance(document, dict) and all(isinstance(document.get(k), str) and document[k].startswith("https://") for k in required)
            return {"url": url, "status": response.status, "content_type": content_type,
                    "result": "candidate_metadata_requires_manual_validation" if valid else "not_authorization_metadata"}
    except urllib.error.HTTPError as exc:
        return {"url": url, "status": exc.code, "result": "http_error"}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"url": url, "result": "network_error"}

def main():
    if len(sys.argv) != 1:
        print("Usage: python3 discover.py (no credentials or arguments)", file=sys.stderr)
        return 2
    opener = urllib.request.build_opener(NoRedirect())
    for host in HOSTS:
        for path in PATHS:
            print(json.dumps(probe(opener, host + path)))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
