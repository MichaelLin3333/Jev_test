import json
from urllib.parse import urlencode
from urllib.request import urlopen

parameters = {
    "query": "(NVIDIA OR NVDA) sourcelang:english",
    "mode": "artlist",
    "format": "json",
    "timespan": "24h",
    "maxrecords": 5,
    "sort": "datedesc",
}

url = (
    "https://api.gdeltproject.org/api/v2/doc/doc?"
    + urlencode(parameters)
)

with urlopen(url, timeout=30) as response:
    data = json.load(response)

print(json.dumps(data, indent=2, ensure_ascii=False))