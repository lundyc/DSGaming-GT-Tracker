from PIL import Image, ImageOps
import easyocr
import base64, requests, os, re, warnings, csv, json
from urllib.parse import quote_plus
from datetime import datetime, timezone

# ---- quiet Torch + EasyOCR noise ----
warnings.filterwarnings("ignore", message=".*pin_memory.*")
os.environ["KMP_WARNINGS"] = "0"

try:
    import torch
    GPU_AVAILABLE = bool(getattr(torch, "cuda", None) and torch.cuda.is_available()) \
                    or bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
except Exception:
    GPU_AVAILABLE = False

# ---- config ----
HOST = "149.202.87.35:27015"
START = "-1w"
OUT_DIR = "images"
DATA_DIR = "docs/data"
CROP_BOX = (39, 0, 260, 152)
SCALE_FACTOR = 2

def b64_name(name: str) -> str:
    return quote_plus(base64.b64encode(name.encode("utf-8")).decode("ascii"))

def build_url(name: str) -> str:
    return ("https://cache.gametracker.com/images/graphs/player_time.php"
            f"?nameb64={b64_name(name)}&host={HOST}&start={START}")

def download_image(url: str, out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    r = requests.get(url, timeout=20, headers={"User-Agent": "GTStatsBot/1.0"})
    r.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(r.content)
    return out_path

def ocr_total_minutes(reader, image_path: str) -> int:
    gray = ImageOps.grayscale(Image.open(image_path)).crop(CROP_BOX)
    resized = gray.resize(
        (gray.width * SCALE_FACTOR, gray.height * SCALE_FACTOR),
        resample=Image.Resampling.LANCZOS
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp_path = os.path.join(OUT_DIR, "inprogress.png")
    resized.save(tmp_path)
    tokens = reader.readtext(tmp_path, detail=0)

    nums = []
    for t in tokens:
        for x in re.findall(r"\d+", str(t)):
            try:
                nums.append(int(x))
            except ValueError:
                pass
    return sum(nums) if nums else 0

def load_admins(path="admins.txt"):
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]

def write_outputs(results, week_label="last-7d"):
    """Write TXT, CSV, JSON and append to historical CSV."""
    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_date = run_at[:10]  # YYYY-MM-DD
    rows = [{"run_at_utc": run_at, "week_label": week_label, "admin_name": n, "minutes": t}
            for n, t in results]

    # TXT
    with open("weekly_results.txt", "w", encoding="utf-8") as f:
        f.write("GT FOR PUBLIC\n")
        for r in rows:
            f.write(f"{r['admin_name']} = {r['minutes']}\n")

    # Per-run CSV
    os.makedirs(DATA_DIR, exist_ok=True)
    per_run_csv = os.path.join(DATA_DIR, f"{run_date}_weekly_results.csv")
    with open(per_run_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["run_at_utc","week_label","admin_name","minutes"])
        w.writeheader()
        w.writerows(rows)

    # JSON (optional, handy)
    with open("weekly_results.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    # Append to history CSV
    history_csv = os.path.join(DATA_DIR, "leaderboard_history.csv")
    file_exists = os.path.exists(history_csv)
    with open(history_csv, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["run_at_utc","week_label","admin_name","minutes"])
        if not file_exists:
            w.writeheader()
        w.writerows(rows)

    print(f"Saved results to weekly_results.txt and {per_run_csv}")
    return per_run_csv, history_csv

def main():
    admins = load_admins()
    if not admins:
        print("GT FOR PUBLIC")
        return

    reader = easyocr.Reader(['en'], gpu=GPU_AVAILABLE, verbose=False)

    results = []
    for name in admins:
        try:
            local_path = os.path.join(OUT_DIR, f"{name.replace('/', '_')}.png")
            download_image(build_url(name), local_path)
            total = ocr_total_minutes(reader, local_path)
        except Exception:
            total = 0
        results.append((name, total))

    # sort by total minutes desc, then by name
    results.sort(key=lambda x: (-x[1], x[0].lower()))

    # ---- print to console ----
    print("GT FOR PUBLIC")
    for name, total in results:
        print(f"{name} = {total}")

    # ---- write files (TXT/CSV/JSON + append to history) ----
    write_outputs(results, week_label="last-7d")

if __name__ == "__main__":
    main()
