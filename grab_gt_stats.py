from PIL import Image, ImageOps
import easyocr
import base64, requests, os, re, warnings
from urllib.parse import quote_plus

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
CROP_BOX = (39, 0, 260, 152)
SCALE_FACTOR = 2

def b64_name(name: str) -> str:
    return quote_plus(base64.b64encode(name.encode("utf-8")).decode("ascii"))

def build_url(name: str) -> str:
    return ("https://cache.gametracker.com/images/graphs/player_time.php"
            f"?nameb64={b64_name(name)}&host={HOST}&start={START}")

def download_image(url: str, out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    r = requests.get(url, timeout=20)
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

    print("GT FOR PUBLIC")
    for name, total in results:
        print(f"{name} = {total}")

if __name__ == "__main__":
    main()
