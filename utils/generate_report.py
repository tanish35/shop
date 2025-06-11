# from ast import List
import csv
from datetime import datetime, time, timedelta
from typing import Any, Dict, List

import pytz

from engine import db

REPORTS: Dict[str, Dict[str, Any]] = {}
HARDCODED_MAX_TS = datetime(2024, 10, 14, 23, 59, 59, tzinfo=pytz.UTC)


async def get_business_hours(store_id: str, date: datetime):
    weekday = date.weekday()
    return await db.store_hours.find_first(where={"store_id": store_id, "dayOfWeek": weekday})


def interpolate_status(timeline: List[Dict[str, Any]], bh_start, bh_end):
    filled_timeline = [{"ts": bh_start, "status": None}] + timeline + [{"ts": bh_end, "status": None}]
    intervals = []
    for i in range(1, len(filled_timeline)):
        prev = filled_timeline[i - 1]
        curr = filled_timeline[i]
        status = prev["status"] or curr["status"] or "inactive"
        start_ts = max(prev["ts"], bh_start)
        end_ts = min(curr["ts"], bh_end)
        if start_ts < end_ts:
            intervals.append({"start": start_ts, "end": end_ts, "status": status})
    return intervals


async def generate_report(report_id: str):
    print(f"[REPORT] Starting report generation for report_id={report_id}")
    max_ts = HARDCODED_MAX_TS
    print(f"[REPORT] Using HARDCODED_MAX_TS: {max_ts}")

    status_map = {"active": "uptime", "inactive": "downtime"}

    intervals = {
        "last_hour": max_ts - timedelta(hours=1),
        "last_day": max_ts - timedelta(days=1),
        "last_week": max_ts - timedelta(days=7),
    }
    print(f"[REPORT] Defined intervals: {intervals}")

    stores = await db.store_timezones.find_many()
    print(f"[REPORT] Found {len(stores)} stores to process")

    output_rows = []

    for idx, store in enumerate(stores, 1):
        timezone = pytz.timezone(store.timezone_str or "UTC")
        store_id = store.store_id
        metrics = {f"{t}_{k}": 0.0 for t in ["uptime", "downtime"] for k in intervals}
        print(f"\n[STORE {idx}/{len(stores)}] Processing store_id={store_id} in timezone={timezone}")

        for day_offset in range(7):
            day = max_ts - timedelta(days=day_offset)
            bh = await get_business_hours(store_id, day)
            if not bh or not bh.start_time_local or not bh.end_time_local:
                print(f"  [DAY {day_offset}] Missing business hours, assuming 24-hour open.")
                start_local = time(0, 0, 0)
                end_local = time(23, 59, 59)
            else:
                try:
                    start_local = datetime.strptime(bh.start_time_local, "%H:%M:%S").time()
                    end_local = datetime.strptime(bh.end_time_local, "%H:%M:%S").time()
                except Exception as e:
                    print(f"  [DAY {day_offset}] Error parsing business hours: {e}, assuming 24-hour open.")
                    start_local = time(0, 0, 0)
                    end_local = time(23, 59, 59)
            start_dt = timezone.localize(datetime.combine(day.date(), start_local)).astimezone(pytz.UTC)
            end_dt = timezone.localize(datetime.combine(day.date(), end_local)).astimezone(pytz.UTC)
            if start_dt >= end_dt:
                print(f"  [DAY {day_offset}] Invalid business hours (start >= end), skipping.")
                continue
            print(f"  [DAY {day_offset}] Business hours: {start_dt} to {end_dt} (UTC)")

            statuses = await db.storestatus.find_many(
                where={
                    "store_id": store_id,
                    "timestamp": {"gte": start_dt, "lte": end_dt},
                },
                order={"timestamp": "asc"},
            )
            print(f"    [STATUS] Found {len(statuses)} status records in business hours.")

            timeline = [{"ts": s.timestamp, "status": s.status} for s in statuses]
            intervals_filled = interpolate_status(timeline, start_dt, end_dt)
            print(f"    [INTERPOLATE] Interpolated {len(intervals_filled)} intervals for business hours.")

            for interval in intervals_filled:
                dur_min = (interval["end"] - interval["start"]).total_seconds() / 60
                for name, iv_start in intervals.items():
                    if interval["end"] <= iv_start or interval["start"] >= max_ts:
                        continue
                    overlap_start = max(interval["start"], iv_start)
                    overlap_end = min(interval["end"], max_ts)
                    overlap_min = (overlap_end - overlap_start).total_seconds() / 60
                    if overlap_min > 0:
                        status_type = status_map.get(interval["status"])
                        if not status_type:
                            continue
                        key = f"{status_type}_{name}"
                        if "day" in name or "week" in name:
                            metrics[key] += overlap_min / 60
                        else:
                            metrics[key] += overlap_min

        print(f"[STORE {idx}] Metrics: {metrics}")
        output_rows.append({"store_id": store_id, **{k: round(v, 2) for k, v in metrics.items()}})

    path = f"/tmp/report_{report_id}.csv"
    print(f"[REPORT] Writing report to {path}")
    with open(path, mode="w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "store_id",
                "uptime_last_hour",
                "uptime_last_day",
                "uptime_last_week",
                "downtime_last_hour",
                "downtime_last_day",
                "downtime_last_week",
            ],
        )
        writer.writeheader()
        for row in output_rows:
            writer.writerow(row)

    REPORTS[report_id]["status"] = "Complete"
    REPORTS[report_id]["path"] = path
    print(f"[REPORT] Report generation complete. Status updated for report_id={report_id}")
