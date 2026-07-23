from __future__ import annotations

import csv
import json
import math
import os
import statistics
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://spdf.gsfc.nasa.gov/pub/data/omni/high_res_omni/monthly_1min"
OUT = Path(os.environ.get("EAGC_OUT", "artifacts/eagc012"))
OUT.mkdir(parents=True, exist_ok=True)

EVENTS = [
    ("E2001-0331", "200103", "2001-03-29T00:00:00Z", "2001-04-01T23:59:00Z"),
    ("E2004-1108", "200411", "2004-11-06T00:00:00Z", "2004-11-10T23:59:00Z"),
    ("E2005-0515", "200505", "2005-05-13T00:00:00Z", "2005-05-16T23:59:00Z"),
    ("E2015-0622", "201506", "2015-06-20T00:00:00Z", "2015-06-24T23:59:00Z"),
]

# Official HRO 1-minute columns, zero-based after whitespace splitting.
IDX = {
    "year": 0, "doy": 1, "hour": 2, "minute": 3,
    "bmag": 13, "bz": 18, "speed": 21, "density": 25,
    "pressure": 27, "ae": 37, "al": 38, "symh": 41,
}
FILLS = {"bmag": 999.99, "bz": 999.99, "speed": 99999.9, "density": 999.99,
         "pressure": 99.99, "ae": 99999.0, "al": 99999.0, "symh": 99999.0}

@dataclass
class Row:
    t: datetime
    bmag: float | None
    bz: float | None
    speed: float | None
    density: float | None
    pressure: float | None
    ae: float | None
    al: float | None
    symh: float | None


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def clean(name: str, value: str) -> float | None:
    try:
        x = float(value)
    except ValueError:
        return None
    fill = FILLS[name]
    if abs(x - fill) < 1e-6 or abs(x) >= fill:
        return None
    return x


def download(month: str) -> Path:
    dest = OUT / f"omni_min{month}.asc"
    if not dest.exists():
        url = f"{BASE}/omni_min{month}.asc"
        urllib.request.urlretrieve(url, dest)
    return dest


def parse(path: Path, start: datetime, end: datetime) -> list[Row]:
    rows: list[Row] = []
    with path.open("r", encoding="ascii", errors="ignore") as f:
        for line in f:
            p = line.split()
            if len(p) < 46:
                continue
            try:
                t = datetime.strptime(f"{p[0]} {p[1]} {p[2]} {p[3]}", "%Y %j %H %M").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if start <= t <= end:
                rows.append(Row(t, clean("bmag", p[IDX["bmag"]]), clean("bz", p[IDX["bz"]]),
                    clean("speed", p[IDX["speed"]]), clean("density", p[IDX["density"]]),
                    clean("pressure", p[IDX["pressure"]]), clean("ae", p[IDX["ae"]]),
                    clean("al", p[IDX["al"]]), clean("symh", p[IDX["symh"]])))
    return rows


def coverage(rows: list[Row], key: str) -> float:
    return sum(getattr(r, key) is not None for r in rows) / max(1, len(rows))


def max_gap(rows: list[Row], key: str) -> int:
    run = best = 0
    for r in rows:
        if getattr(r, key) is None:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def q(x: float, lo: float, hi: float) -> float:
    return max(0.0, min(1.0, (x-lo)/(hi-lo)))


def features(rows: list[Row]) -> dict[str, float | int | str | None]:
    valid = [r for r in rows if r.bz is not None and r.speed is not None and r.pressure is not None]
    if not valid:
        return {"status": "HOLD-DATA"}
    south = [r for r in valid if r.bz < -5]
    iq = sum(max(0.0, -r.bz) * r.speed * math.sqrt(max(r.pressure, 0.0)) for r in valid) / len(valid)
    vb = sum(max(0.0, -r.bz) * r.speed for r in valid) / len(valid)
    # Front candidates: joint 30-minute changes in V, Pdyn and |B|, clustered within 3h.
    cand: list[int] = []
    for i in range(30, len(rows)):
        a, b = rows[i-30], rows[i]
        if None in (a.speed, b.speed, a.pressure, b.pressure, a.bmag, b.bmag):
            continue
        dv = b.speed - a.speed
        rp = b.pressure / max(a.pressure, 0.1)
        rb = b.bmag / max(a.bmag, 0.1)
        if dv >= 70 and rp >= 1.8 and rb >= 1.4:
            cand.append(i)
    clusters: list[int] = []
    for i in cand:
        if not clusters or i - clusters[-1] > 180:
            clusters.append(i)
    nfront = len(clusters)
    if nfront > 1:
        gaps = [(clusters[i]-clusters[i-1])/60 for i in range(1, nfront)]
        compact = math.exp(-statistics.median(gaps)/18)
    else:
        compact = 0.15
    south_hours = len(south)/60
    persistence = 1-math.exp(-south_hours/5)
    compression = q(max((r.pressure or 0) for r in rows), 2, 25)
    stages = min(1.0, nfront/3)
    lambda_arrival = 0.5*(max(1e-9, stages*compact*compression*persistence))**0.25 + 0.5*math.sqrt(max(0, compact*persistence))
    # Receiver state from first 12h only; this avoids main-phase target leakage.
    pre = rows[:min(len(rows), 720)]
    sym = [r.symh for r in pre if r.symh is not None]
    ae = [r.ae for r in pre if r.ae is not None]
    al = [r.al for r in pre if r.al is not None]
    den = [r.density for r in pre if r.density is not None]
    bz = [r.bz for r in pre if r.bz is not None]
    quiet = (sum(abs(x)<20 for x in sym)/len(sym)) if sym else 0.0
    plasma = q(statistics.median(den), 2, 15) if den else 0.0
    memory = q(-statistics.median(sym), 0, 80) if sym else 0.0
    conduct = q(statistics.quantiles(ae, n=4)[2] if len(ae)>=4 else (max(ae) if ae else 0), 100, 1200)
    tail = 0.5*q(sum(max(0,-x) for x in bz)/60, 0, 120) + 0.5*q(abs(statistics.quantiles(al,n=4)[0]) if len(al)>=4 else 0, 100, 1200)
    pi_e = 1-(1-0.25*math.sqrt(quiet*plasma))*(1-0.35*math.sqrt(memory*conduct))*(1-0.60*tail)
    target = min((r.symh for r in rows if r.symh is not None), default=None)
    return {"status":"SCORABLE", "rows":len(rows), "fronts":nfront, "south_hours":round(south_hours,3),
            "I_Q":iq, "V_Bs":vb, "Lambda":lambda_arrival, "Pi":pi_e,
            "EAGC":iq*(0.5+lambda_arrival)*(0.5+pi_e), "SYM_H_min":target}


def fit_loocv(items: list[dict], key: str) -> list[float]:
    pred=[]
    for i, item in enumerate(items):
        train=[x for j,x in enumerate(items) if j!=i and x.get(key) is not None and x.get("SYM_H_min") is not None]
        xs=[math.log1p(float(x[key])) for x in train]
        ys=[-float(x["SYM_H_min"]) for x in train]
        if len(xs)<2 or statistics.pvariance(xs)==0:
            p=statistics.mean(ys) if ys else 0
        else:
            b=sum((x-statistics.mean(xs))*(y-statistics.mean(ys)) for x,y in zip(xs,ys))/sum((x-statistics.mean(xs))**2 for x in xs)
            a=statistics.mean(ys)-b*statistics.mean(xs)
            p=a+b*math.log1p(float(item[key]))
        pred.append(-max(0,p))
    return pred


def rmse(y, p):
    return math.sqrt(sum((a-b)**2 for a,b in zip(y,p))/len(y))


def main():
    summaries=[]
    for eid, month, s, e in EVENTS:
        rows=parse(download(month), dt(s), dt(e))
        csv_path=OUT/f"{eid}.csv"
        with csv_path.open("w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(["Time_UTC","Bmag_nT","BZ_GSM_nT","flow_speed_km_s","proton_density_cm3","Pressure_nPa","AE_INDEX_nT","AL_INDEX_nT","SYM_H_nT"])
            for r in rows: w.writerow([r.t.isoformat(),r.bmag,r.bz,r.speed,r.density,r.pressure,r.ae,r.al,r.symh])
        cov={k:coverage(rows,k) for k in ("bz","speed","density","pressure","ae","al","symh")}
        gaps={k:max_gap(rows,k) for k in ("bz","speed","pressure")}
        feat=features(rows)
        status="SCORABLE" if min(cov["bz"],cov["speed"],cov["pressure"])>=0.90 and max(gaps.values())<=15 else "HOLD-DATA"
        feat.update({"event_id":eid,"month":month,"coverage":cov,"max_gap_min":gaps,"quality_status":status})
        summaries.append(feat)
    sc=[x for x in summaries if x.get("quality_status")=="SCORABLE" and x.get("SYM_H_min") is not None]
    metrics={"n_registered":len(EVENTS),"n_scorable":len(sc),"minimum_required":20,"decision":"HOLD-SAMPLE"}
    if len(sc)>=4:
        y=[x["SYM_H_min"] for x in sc]
        for key in ("I_Q","V_Bs","EAGC"):
            p=fit_loocv(sc,key); metrics[f"rmse_{key}"]=rmse(y,p)
        if len(sc)>=20:
            imp=(metrics["rmse_I_Q"]-metrics["rmse_EAGC"])/metrics["rmse_I_Q"]
            metrics["improvement_vs_IQ"]=imp
            metrics["decision"]="PASS" if imp>=0.05 else "REJECT"
    (OUT/"event_summary.json").write_text(json.dumps(summaries,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"gate_metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    with (OUT/"event_summary.csv").open("w",newline="",encoding="utf-8") as f:
        fields=["event_id","quality_status","rows","fronts","south_hours","I_Q","V_Bs","Lambda","Pi","EAGC","SYM_H_min"]
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for x in summaries: w.writerow({k:x.get(k) for k in fields})
    print(json.dumps(metrics,ensure_ascii=False))

if __name__ == "__main__":
    main()
