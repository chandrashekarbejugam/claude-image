import base64, json, os, sys, time, urllib.request, urllib.error

ACCOUNT = os.environ["CF_ACCOUNT_ID"]
TOKEN = os.environ["CF_API_TOKEN"]
MODEL = "@cf/black-forest-labs/flux-1-schnell"
URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run/{MODEL}"
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "100"))  # protects the free daily quota
OUT = "images"


def generate(prompt, steps):
    body = json.dumps({"prompt": prompt[:2000], "steps": steps}).encode()
    req = urllib.request.Request(
        URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            if not data.get("success"):
                raise RuntimeError(str(data.get("errors")))
            return base64.b64decode(data["result"]["image"])
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError):
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def main(path):
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    os.makedirs(OUT, exist_ok=True)
    made, failed = 0, []
    for item in items:
        name = str(item["id"])
        dest = os.path.join(OUT, f"{name}.jpg")
        if os.path.exists(dest):
            print(f"skip {name} (exists)")
            continue
        if made >= MAX_PER_RUN:
            print(f"stopped at MAX_PER_RUN={MAX_PER_RUN}")
            break
        try:
            img = generate(item["prompt"], int(item.get("steps", 4)))
            with open(dest, "wb") as f:
                f.write(img)
            made += 1
            print(f"ok   {name} ({len(img)//1024} KB)")
        except Exception as e:
            print(f"FAIL {name}: {e}")
            failed.append(name)
    print(f"done: {made} generated, {len(failed)} failed")
    if failed:
        with open(os.path.join(OUT, "_failed.txt"), "w") as f:
            f.write("\n".join(failed))


if __name__ == "__main__":
    main(sys.argv[1])
