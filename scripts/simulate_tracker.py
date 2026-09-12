import argparse
import json
import random
import time
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description="Simulate an elephant GPS collar")
parser.add_argument("--url", default="http://127.0.0.1:8000/api/v1/telemetry")
parser.add_argument("--device-id", default="ELE-001")
parser.add_argument("--device-key", default="demo-device-key")
parser.add_argument("--interval", type=float, default=5)
args = parser.parse_args()
lat, lon, battery = 12.905, 74.845, 100.0
while True:
    lat += random.uniform(-0.001, 0.0015); lon += random.uniform(-0.001, 0.0015); battery=max(0,battery-0.1)
    payload={"device_id":args.device_id,"latitude":lat,"longitude":lon,"battery_percent":battery,
             "speed_kmh":random.uniform(1,7),"temperature_c":random.uniform(26,34),"signal_strength":random.uniform(45,95)}
    request=Request(args.url,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json","X-Device-Key":args.device_key},method="POST")
    try:
        with urlopen(request,timeout=10) as response: print(response.read().decode())
    except Exception as exc: print(f"Send failed: {exc}")
    time.sleep(args.interval)

