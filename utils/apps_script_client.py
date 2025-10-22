import requests, io, pandas as pd
class AppsScriptClient:
    def __init__(self, base_url: str, secret: str):
        self.base_url = base_url.rstrip('/')
        self.secret = secret
    def fetch_latest_meta(self) -> dict:
        r = requests.get(self.base_url, params={'secret': self.secret, 'meta': '1'}, timeout=30)
        r.raise_for_status()
        return r.json()
    def fetch_latest_csv(self) -> pd.DataFrame:
        r = requests.get(self.base_url, params={'secret': self.secret}, timeout=60)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text))
