#!/usr/bin/env python3
"""Generate local traffic to exercise the configured usage limit and Grafana alert."""

import io
import os
import sys
import urllib.error
import urllib.request

from PIL import Image

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
MAID_ID = os.getenv("MAID_ID", "anomaly-test-user")
ROOM_ID = os.getenv("ROOM_ID", "anomaly-test-room")


def create_test_image() -> bytes:
    image = Image.effect_noise((900, 900), 100).convert("RGB")
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=0)
    return output.getvalue()


def main() -> int:
    photo = create_test_image()
    print(f"Generated valid PNG of {len(photo)} bytes.")

    for attempt in range(1, 7):
        body = (
            b"--boundary\r\n"
            b'Content-Disposition: form-data; name="room_id"\r\n\r\n'
            + ROOM_ID.encode()
            + b"\r\n--boundary\r\n"
            b'Content-Disposition: form-data; name="maid_id"\r\n\r\n'
            + MAID_ID.encode()
            + b"\r\n--boundary\r\n"
            b'Content-Disposition: form-data; name="photo"; filename="anomaly.png"\r\n'
            b"Content-Type: image/png\r\n\r\n" + photo + b"\r\n--boundary--\r\n"
        )
        request = urllib.request.Request(
            f"{API_BASE_URL}/inspection",
            data=body,
            headers={"Content-Type": "multipart/form-data; boundary=boundary"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code

        print(f"Request {attempt}/6: HTTP {status}")
        if attempt < 6 and status != 200:
            print("Expected successful request before the configured request limit.")
            return 1
        if attempt == 6 and status != 429:
            print("Expected HTTP 429 on the sixth request; check limit settings.")
            return 1
    print("Traffic sent. Allow a minute for metrics evaluation and alert delivery.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
