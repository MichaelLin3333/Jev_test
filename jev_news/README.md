# News and API utilities

Supporting code for [jev_model_eval](../jev_model_eval/README.md).

| Module | Role |
| --- | --- |
| `jev_client.py` | Shared Jev HTTP transport and response validation |
| `collect.py`, `http.py` | GDELT news discovery and SEC filing metadata retrieval |
| `model.py`, `store.py` | Normalize records and keep a replayable SQLite archive |
| `jev_analysis.py`, `jev_report.py` | Earlier staged-analysis and report helpers |

## Collection tools

`config.example.json` supplies example queries and companies. Inspect the utility commands with:

```sh
python -B -m jev_news --help
```

The collector supports `collect`, `status`, and `export`. SEC retrieval needs `SEC_USER_AGENT` with contact information. GDELT discovery supplies article metadata, not full article text.

Legacy `demo`, `jev-demo`, and `historical_pilot` entry points require retired fixtures that are no longer distributed. Use [JEV_DEMO.md](../JEV_DEMO.md) for the current evaluation walkthrough.
