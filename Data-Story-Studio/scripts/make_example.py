"""Generate the built-in guided example: Brightleaf Coffee Co. (fictional).

Four related files that exercise every part of the tool:
  orders.csv      ~20K orders, hourly timestamps (fact table; includes a few exact duplicates)
  products.csv    lookup -> orders.product_id
  stores.xlsx     lookup -> orders.store_id (Excel, to show Excel support; has each store's state for the map)
  feedback.csv    survey answers for ~30% of orders -> orders.order_id (partial match)

Stories planted for the analysis to find:
  - Delivery grows from ~8% to ~28% of orders
  - Harbour Quay opens in March 2025 and ramps up
  - Riverside closes for renovation for three weeks in August 2025
  - Hot drink prices rise 8% in January 2026 (revenue up, volume flat)
  - Cold drinks peak in summer months
  - Weekday 7-9am rush; longer waits at peak and on delivery drive lower ratings
  - Stores sit in six Australian states, so revenue by state is drawn as a map

Usage: python scripts/make_example.py   (writes to data/Example/)
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data" / "Example"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(2024)

START, END = pd.Timestamp("2024-07-01"), pd.Timestamp("2026-06-30 23:59")

products = pd.DataFrame([
    ("P01", "Flat white", "Hot coffee", 5.20), ("P02", "Latte", "Hot coffee", 5.40),
    ("P03", "Cappuccino", "Hot coffee", 5.20), ("P04", "Long black", "Hot coffee", 4.60),
    ("P05", "Mocha", "Hot coffee", 5.90), ("P06", "Iced latte", "Cold drinks", 6.20),
    ("P07", "Cold brew", "Cold drinks", 6.00), ("P08", "Iced chocolate", "Cold drinks", 6.50),
    ("P09", "Chai latte", "Tea", 5.30), ("P10", "English breakfast", "Tea", 4.20),
    ("P11", "Almond croissant", "Food", 6.80), ("P12", "Banana bread", "Food", 5.50),
    ("P13", "Breakfast roll", "Food", 9.90), ("P14", "Avocado toast", "Food", 14.50),
], columns=["product_id", "product_name", "category", "unit_price"])

# the chain spans six Australian states, so the dashboard can draw a map of where revenue comes from
stores = pd.DataFrame([
    ("S1", "Central Station", "New South Wales", "Metro", "Café"),
    ("S2", "Riverside", "Victoria", "Metro", "Café"),
    ("S3", "Northgate Mall", "Queensland", "Suburban", "Kiosk"),
    ("S4", "Westfield Drive", "Western Australia", "Suburban", "Drive-thru"),
    ("S5", "Uni Quarter", "South Australia", "Metro", "Kiosk"),
    ("S6", "Harbour Quay", "Tasmania", "Metro", "Café"),
], columns=["store_id", "store_name", "state", "area", "format"])
store_weight = {"S1": 1.5, "S2": 1.2, "S3": 0.9, "S4": 1.0, "S5": 0.8, "S6": 1.1}

# ---- order timestamps: daily volume x hourly profile
days = pd.date_range(START, END.normalize(), freq="D")
weekday_hours = np.array([0, 0, 0, 0, 0, 0, 3, 10, 12, 7, 5, 5, 6, 5, 4, 4, 3, 2, 1, 0, 0, 0, 0, 0], float)
weekend_hours = np.array([0, 0, 0, 0, 0, 0, 1, 3, 6, 9, 10, 8, 7, 5, 4, 3, 2, 1, 1, 0, 0, 0, 0, 0], float)
rows = []
for d in days:
    t = (d - START).days / len(days)
    for s, w in store_weight.items():
        if s == "S6" and d < pd.Timestamp("2025-03-01"):
            continue
        if s == "S2" and pd.Timestamp("2025-08-04") <= d < pd.Timestamp("2025-08-25"):
            continue  # Riverside renovation
        ramp = min(1.0, (d - pd.Timestamp("2025-03-01")).days / 120) if s == "S6" else 1.0
        weekend = d.dayofweek >= 5
        base = 4.2 * w * ramp * (0.75 if weekend and s in ("S1", "S5") else 1.0) * (1 + 0.12 * t)
        if s == "S5" and d.month in (12, 1):
            base *= 0.55  # university holidays
        n = rng.poisson(base)
        prof = weekend_hours if weekend else weekday_hours
        hours = rng.choice(24, n, p=prof / prof.sum())
        for h in hours:
            rows.append((d + pd.Timedelta(hours=int(h), minutes=int(rng.integers(0, 60))), s, t, weekend, h))
orders = pd.DataFrame(rows, columns=["ts", "store_id", "t", "weekend", "hour"])
n = len(orders)

# channel: delivery share grows over time; drive-thru has no delivery
p_delivery = 0.08 + 0.20 * orders["t"].to_numpy()
p_app = np.full(n, 0.22)
r = rng.random(n)
channel = np.where(r < p_delivery, "Delivery", np.where(r < p_delivery + p_app, "App", "In-store"))
channel = np.where((orders["store_id"] == "S4") & (channel == "Delivery"), "In-store", channel)

# product: cold drinks more likely in summer (Dec-Feb, southern hemisphere), food at breakfast
month = orders["ts"].dt.month.to_numpy()
summer = np.isin(month, [12, 1, 2])
pid = []
base_p = np.array([14, 14, 10, 8, 5, 5, 4, 3, 6, 4, 7, 6, 8, 6], float)
for i in range(n):
    p = base_p.copy()
    if summer[i]:
        p[5:8] *= 3.0
    elif month[i] in (6, 7, 8):
        p[5:8] *= 0.4
    if 7 <= orders["hour"].iat[i] <= 9:
        p[12] *= 2.0
    pid.append(products["product_id"].iat[rng.choice(14, p=p / p.sum())])
orders["product_id"] = pid
price = products.set_index("product_id").loc[orders["product_id"], "unit_price"].to_numpy()
cat = products.set_index("product_id").loc[orders["product_id"], "category"].to_numpy()
price = np.where((orders["ts"] >= "2026-01-01").to_numpy() & (cat == "Hot coffee"), np.round(price * 1.08, 2), price)
qty = rng.choice([1, 1, 1, 1, 2, 2, 3], n)
qty = np.where(channel == "Delivery", np.maximum(qty, rng.choice([1, 2, 2, 3], n)), qty)
discount = np.where(channel == "App", np.where(rng.random(n) < 0.5, 0.10, 0.0), 0.0)
orders["channel"] = channel
orders["quantity"] = qty
orders["discount"] = discount
orders["revenue"] = np.round(qty * price * (1 - discount) + np.where(channel == "Delivery", 3.50, 0), 2)
orders = orders.sort_values("ts").reset_index(drop=True)
orders.insert(0, "order_id", np.arange(100001, 100001 + len(orders)))

# ---- feedback for ~30% of orders: waits drive ratings
fb = orders.sample(frac=0.3, random_state=7).sort_values("order_id")
peak = fb["hour"].between(7, 9) & ~fb["weekend"]
wait = rng.gamma(2.2, 2.0, len(fb)) + np.where(peak, 4, 0) + np.where(fb["channel"] == "Delivery", 14, 0)
wait += np.where(fb["store_id"] == "S3", 3, 0)
wait = np.round(wait, 1)
rating = np.clip(np.round(5.3 - wait / 9 + rng.normal(0, 0.7, len(fb))), 1, 5).astype(int)
recommend = np.where(rating >= 4, "Yes", np.where(rating <= 2, "No", np.where(rng.random(len(fb)) < 0.5, "Yes", "No")))
feedback = pd.DataFrame({"order_id": fb["order_id"].to_numpy(), "rating": rating, "wait_minutes": wait, "would_recommend": recommend})

# ---- write; orders gets a few exact duplicate rows (a POS export glitch) for the dedupe fix
out = orders[["order_id", "ts", "store_id", "product_id", "channel", "quantity", "discount", "revenue"]].rename(columns={"ts": "order_date"})
out["order_date"] = out["order_date"].dt.strftime("%Y-%m-%d %H:%M")
dupes = out.sample(36, random_state=3)
out = pd.concat([out, dupes]).sort_values(["order_date", "order_id"]).reset_index(drop=True)
out.to_csv(OUT / "orders.csv", index=False)
products.to_csv(OUT / "products.csv", index=False)
feedback.to_csv(OUT / "feedback.csv", index=False)
with pd.ExcelWriter(OUT / "stores.xlsx") as xw:
    stores.to_excel(xw, sheet_name="Stores", index=False)
print(f"orders {len(out)}  feedback {len(feedback)}  -> {OUT}")
