"""Verified captured satellite pages explicitly linked by the main article."""

import hashlib
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def captured_table_pages(fixture):
    if fixture.provider != "springer":
        return {}
    from tests.golden_criteria import golden_criteria_dir_for_doi

    fixture_dir = golden_criteria_dir_for_doi(fixture.doi)
    provenance = fixture_dir / "acquisition/provenance.json"
    if not provenance.is_file():
        return {}
    main = BeautifulSoup(fixture.raw_path.read_bytes(), "lxml")
    links = {
        urljoin(fixture.source_url, a["href"])
        for a in main.select("a[href]")
        if re.search(r"/tables/\d+(?:$|[?#])", a["href"])
    }
    responses = {}
    for record in json.loads(provenance.read_text()).get("records", []):
        requested = record.get("requested_url")
        headers = record.get("response_headers") or {}
        if (
            requested not in links
            or record.get("status_code") != 200
            or not headers.get("content-type", "").startswith("text/html")
        ):
            continue
        path = fixture_dir / record["body_file"]
        body = path.read_bytes()
        assert len(body) == record["size"]
        assert hashlib.sha256(body).hexdigest() == record["sha256"]
        responses[requested] = {
            "body": body,
            "headers": headers,
            "status_code": 200,
            "url": record["final_url"],
        }
    return responses
