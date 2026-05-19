from fastapi import FastAPI, Response
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from datetime import datetime, timedelta, timezone
import pytz

app = FastAPI()

def fetch_cbar_xml():
    # Baku timezone'u
    baku_tz = pytz.timezone('Asia/Baku')
    date_obj = datetime.now(baku_tz)
    
    date_str = date_obj.strftime("%d.%m.%Y")
    url = f"https://www.cbar.az/currencies/{date_str}.xml"
    
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    
    return r.text, date_obj

def transform_to_bc_xml(cbar_xml: str, fallback_date: datetime) -> str:
    root = ET.fromstring(cbar_xml)
    cbar_date = root.attrib.get("Date", fallback_date.strftime("%d.%m.%Y"))

    try:
        iso_date = datetime.strptime(cbar_date, "%d.%m.%Y").strftime("%Y-%m-%d")
    except Exception:
        iso_date = fallback_date.strftime("%Y-%m-%d")

    out = ['<?xml version="1.0" encoding="UTF-8"?>', "<ExchangeRates>"]

    for valtype in root.findall("ValType"):
        if valtype.attrib.get("Type") != "Xarici valyutalar":
            continue

        for valute in valtype.findall("Valute"):
            code = (valute.attrib.get("Code") or "").strip()
            nominal_raw = (valute.findtext("Nominal") or "").strip()
            value_raw = (valute.findtext("Value") or "").strip()

            if not code or not value_raw:
                continue

            nominal_num = "".join(ch for ch in nominal_raw if ch.isdigit())
            if not nominal_num:
                nominal_num = "1"

            out.append("  <Rate>")
            out.append(f"    <CurrencyCode>{escape(code)}</CurrencyCode>")
            out.append(f"    <StartingDate>{iso_date}</StartingDate>")
            out.append(f"    <ExchangeRateAmount>{nominal_num}</ExchangeRateAmount>")
            out.append(f"    <RelationalExchRateAmount>{escape(value_raw)}</RelationalExchRateAmount>")
            out.append("  </Rate>")

    out.append("</ExchangeRates>")
    return "\n".join(out)


@app.get("/cbar/latest")
def cbar_latest():
    cbar_xml, used_date = fetch_cbar_xml()
    bc_xml = transform_to_bc_xml(cbar_xml, used_date)
    return Response(content=bc_xml, media_type="application/xml")


@app.get("/cbar/{date}")
def cbar_by_date(date: str):
    """
    date format: YYYY-MM-DD
    örn: /cbar/2026-05-18
    """
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return Response(content="Invalid date format. Use YYYY-MM-DD", status_code=400)

    date_str = date_obj.strftime("%d.%m.%Y")
    url = f"https://www.cbar.az/currencies/{date_str}.xml"
    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        return Response(content="CBAR data not available for given date", status_code=404)

    bc_xml = transform_to_bc_xml(r.text, date_obj)
    return Response(content=bc_xml, media_type="application/xml")
