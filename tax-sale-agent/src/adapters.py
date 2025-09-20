from __future__ import annotations
import os, re, json, logging
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from .utils import parse_money, split_city_state_zip, normalize_zip

load_dotenv()
LOGGER = logging.getLogger(__name__)

@dataclass
class PropertyRecord:
    county: str
    case_no: Optional[str]
    cause_no: Optional[str]
    account_no: Optional[str]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip: Optional[str]
    legal_description: Optional[str]
    sale_date: Optional[str]
    min_bid: Optional[float]
    adjudged_value: Optional[float]
    source_name: str
    source_url: Optional[str]
    est_value: Optional[float] = None
    est_value_source: Optional[str] = None

    def to_row(self) -> Dict[str, Any]:
        d = asdict(self)
        for k in ("min_bid", "adjudged_value", "est_value"):
            if d.get(k) is not None:
                try:
                    d[k] = round(float(d[k]), 2)
                except Exception:
                    pass
        return d

class HCTaxNetAdapter:
    BASE_URL = "https://www.hctax.net"
    PATH = "/Property/listings/taxsalelisting"
    name = "hctax.net"

    def fetch(self) -> List[PropertyRecord]:
        url = urljoin(self.BASE_URL, self.PATH)
        sess = requests.Session()
        sess.headers.update({"User-Agent": "Mozilla/5.0"})
        r = sess.get(url, timeout=40)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        table = soup.find("table")
        records: List[PropertyRecord] = []
        if table:
            rows = table.find_all("tr")
            headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th","td"])]
            for tr in rows[1:]:
                cols = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                if not cols:
                    continue
                def get(colname: str) -> Optional[str]:
                    for i, h in enumerate(headers):
                        if colname in h and i < len(cols):
                            return cols[i]
                    return None
                addr = get("address") or get("situs") or get("property")
                citysz = get("city") or ""
                city, state, zc = split_city_state_zip(citysz)
                case = get("cause") or get("case") or get("cause no")
                acct = get("account") or get("acct")
                legal = get("legal")
                sale_date = get("sale") or get("date")
                min_bid = parse_money(get("min") or get("minimum"))
                adjudged = parse_money(get("adjudged") or get("value"))
                records.append(PropertyRecord(
                    county="Harris",
                    case_no=case, cause_no=case, account_no=acct,
                    address=addr, city=city, state=state or "TX", zip=zc,
                    legal_description=legal, sale_date=sale_date,
                    min_bid=min_bid, adjudged_value=adjudged,
                    source_name=self.name, source_url=r.url
                ))
        else:
            LOGGER.warning("No table found on %s", url)
        return records

class ZillowEstimatorRapidAPI:
    API_HOST = os.getenv("ZILLOW_RAPIDAPI_HOST","zillow-com1.p.rapidapi.com")
    API_KEY = os.getenv("ZILLOW_RAPIDAPI_KEY")

    def __init__(self):
        self.sess = requests.Session()
        if self.API_KEY:
            self.sess.headers.update({
                "X-RapidAPI-Key": self.API_KEY,
                "X-RapidAPI-Host": self.API_HOST,
                "User-Agent": "Mozilla/5.0"
            })

    def estimate(self, rec: PropertyRecord) -> Tuple[Optional[float], Optional[str]]:
        if not self.API_KEY or not rec.address or not (rec.city or rec.zip):
            return (None, None)
        try:
            params = {"address": rec.address, "citystatezip": f"{rec.city or ''} {rec.state or 'TX'} {rec.zip or ''}"}
            r = self.sess.get(f"https://{self.API_HOST}/propertyExtendedSearch", params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            zpid = None
            if isinstance(data, dict):
                for item in data.get("props", []):
                    if item.get("zpid"):
                        zpid = item["zpid"]; break
            if not zpid:
                return (None, None)
            r2 = self.sess.get(f"https://{self.API_HOST}/property", params={"zpid": zpid}, timeout=30)
            r2.raise_for_status()
            d2 = r2.json()
            val = d2.get("zestimate") or d2.get("price")
            try:
                return (float(val), "zillow_rapidapi") if val is not None else (None, None)
            except Exception:
                return (None, None)
        except Exception:
            return (None, None)

class CADFallbackEstimator:
    def estimate(self, rec: PropertyRecord) -> Tuple[Optional[float], Optional[str]]:
        if rec.adjudged_value:
            return (rec.adjudged_value, "adjudged_value")
        return (None, None)

def estimate_values(records: List[PropertyRecord]) -> List[PropertyRecord]:
    chain = [ZillowEstimatorRapidAPI(), CADFallbackEstimator()]
    for r in records:
        for est in chain:
            val, src = est.estimate(r)
            if val is not None:
                r.est_value, r.est_value_source = val, src
                break
    return records
