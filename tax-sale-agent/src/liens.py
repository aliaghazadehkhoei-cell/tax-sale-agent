from __future__ import annotations
import re, json, logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
import pandas as pd
from .utils import parse_money

LOGGER = logging.getLogger(__name__)

SURVIVES = {
    "municipal": True,
    "state_ch61": True,
    "irs": "conditional",
    "tax_loan": True,
    "doj": True,
    "hoa": False,
    "mechanics": False,
    "judgment": False,
    "state_other": False
}

DEFAULT_CONFIG = {
    "score": {
        "target_margin_pct": 0.35,
        "max_score": 100,
        "weights": {"equity": 0.65, "risk": 0.35},
        "risk_penalties": {
            "irs_present": 18,
            "state_ch61": 20,
            "municipal": 12,
            "tax_loan": 15,
            "doj": 25,
            "hoa": 6,
            "mechanics": 8,
            "judgment": 5
        }
    }
}

def classify_row(row: Dict[str, Any]) -> str:
    txt = " ".join(str(row.get(k,"")).lower() for k in ["DocType","Grantor","Grantee","Notes","Legal","LienType"])
    if "internal revenue service" in txt or "irs" in txt: return "irs"
    if "department of justice" in txt: return "doj"
    if "state tax lien" in txt or "texas comptroller" in txt or "workforce commission" in txt:
        if "chapter 61" in txt or "ch. 61" in txt or "§61" in txt: return "state_ch61"
        return "state_other"
    if "transfer tax lien" in txt or "32.06" in txt or "property tax loan" in txt or "tax payment transfer" in txt: return "tax_loan"
    if "hoa" in txt or "homeowner association" in txt or "property owners association" in txt or "poa" in txt: return "hoa"
    if "mechanic" in txt or "materialman" in txt or "contractor lien" in txt: return "mechanics"
    if "city of" in txt or "weed" in txt or "mow" in txt or "abatement" in txt or "board-up" in txt or "demolition" in txt or "municipal" in txt: return "municipal"
    if "abstract of judgment" in txt or "judgment" in txt: return "judgment"
    return "unknown"

def summarize_liens(df: Optional[pd.DataFrame]) -> Tuple[List[Dict[str,Any]], float, List[str]]:
    if df is None or df.empty: return ([], 0.0, [])
    items: List[Dict[str,Any]] = []
    total = 0.0
    flags: List[str] = []
    for _, row in df.iterrows():
        ltype = classify_row(row.to_dict())
        survives = SURVIVES.get(ltype, False)
        amt = parse_money(row.get("Amount"))
        if survives is True:
            items.append({"type": ltype, "amount": amt, "desc": row.get("DocType") or row.get("LienType")})
            if amt: total += amt
            if ltype not in flags: flags.append(ltype)
        elif survives == "conditional":
            if "irs_present" not in flags: flags.append("irs_present")
    return (items, round(total,2), flags)

def deal_score(est_value: Optional[float], min_bid: Optional[float], survive_total: float, flags: List[str], cfg=DEFAULT_CONFIG) -> float:
    if not est_value or not min_bid: return 0.0
    net_equity = max(0.0, est_value - (min_bid + survive_total))
    equity_pct = net_equity / est_value if est_value else 0.0
    equity_score = max(0.0, min(1.0, equity_pct / cfg["score"]["target_margin_pct"]))
    penalty_points = sum(cfg["score"]["risk_penalties"].get(f,0) for f in flags)
    risk_score = 1.0 - min(1.0, penalty_points/100.0)
    combined = cfg["score"]["weights"]["equity"]*equity_score + cfg["score"]["weights"]["risk"]*risk_score
    return round(combined * cfg["score"]["max_score"], 2)
