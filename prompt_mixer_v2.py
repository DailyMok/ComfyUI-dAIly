import csv
import hashlib
import json
import os
import random
import re
import threading
import time
from collections import OrderedDict

from aiohttp import web
from server import PromptServer


MAX_ATTRIBUTES = 64
ATTR_SLOTS = [f"attr_{i:03d}" for i in range(1, MAX_ATTRIBUTES + 1)]
CSV_DIR = os.path.join(os.path.dirname(__file__), "csv")

_CSV_CACHE = {}
_CSV_LOCK = threading.Lock()


def _clean_path(path):
    path = (path or "").strip().strip('"').strip("'")
    if not path:
        return ""
    if os.path.isabs(path):
        return os.path.abspath(path)

    csv_dir_path = os.path.abspath(os.path.join(CSV_DIR, path))
    if os.path.exists(csv_dir_path):
        return csv_dir_path

    return os.path.abspath(path)


def _strip_header(header):
    return (header or "").strip()


def _dedupe_header(header, used):
    base = _strip_header(header)
    if not base:
        return ""
    if base not in used:
        used.add(base)
        return base

    index = 2
    while f"{base}_{index}" in used:
        index += 1
    name = f"{base}_{index}"
    used.add(name)
    return name


def _try_read_csv(path):
    encodings_to_try = ["utf-8-sig", "utf-8", "cp1252", "iso-8859-1", "latin1"]
    last_error = None

    for encoding in encodings_to_try:
        try:
            with open(path, "r", encoding=encoding, newline="") as f:
                reader = csv.reader(f, delimiter=";")
                raw_headers = next(reader, [])
                used_headers = set()
                headers = [_dedupe_header(header, used_headers) for header in raw_headers]
                columns = OrderedDict((header, []) for header in headers if header)

                for row in reader:
                    for index, header in enumerate(headers):
                        if not header:
                            continue
                        value = row[index].strip() if index < len(row) and row[index] else ""
                        if value:
                            columns[header].append(value)

            return columns, encoding, None
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except Exception as exc:
            last_error = exc
            continue

    return None, None, last_error


def _load_csv(path, force=False):
    path = _clean_path(path)
    if not path or not os.path.exists(path):
        return None

    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None

    with _CSV_LOCK:
        cache_entry = _CSV_CACHE.get(path)
        if not force and cache_entry and cache_entry["mtime"] == mtime:
            return cache_entry["data"]

        data, encoding, error = _try_read_csv(path)
        if data is None:
            print(f"[PromptMixerV2dAIly] Could not load CSV: {error}")
            return None

        _CSV_CACHE[path] = {"mtime": mtime, "data": data, "encoding": encoding}
        if encoding != "utf-8-sig":
            print(f"[PromptMixerV2dAIly] CSV loaded with {encoding} (utf-8-sig recommended)")
        return data


def _active_columns(csv_data):
    if not csv_data:
        return []
    return [
        {"name": name, "count": len(values)}
        for name, values in csv_data.items()
        if name
    ][:MAX_ATTRIBUTES]


def _schema_from_json(schema_json, csv_data):
    names = []
    try:
        schema = json.loads(schema_json or "[]")
        if isinstance(schema, list):
            for item in schema:
                if isinstance(item, dict):
                    name = _strip_header(item.get("name", ""))
                else:
                    name = _strip_header(str(item))
                if name:
                    names.append(name)
    except Exception:
        names = []

    if not names:
        names = [column["name"] for column in _active_columns(csv_data)]

    return names[:MAX_ATTRIBUTES]


def _seed_to_int(seed, salt=""):
    digest = hashlib.sha256(f"{int(seed)}::{salt}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _pick_seeded(seed, name, values):
    if not values:
        return ""
    rng = random.Random(_seed_to_int(seed, name))
    return values[rng.randrange(len(values))]


def _format_prompt(prompt, flat_mode):
    if flat_mode:
        return " ".join(prompt.split())
    return "\n".join(line.rstrip() for line in prompt.splitlines()).strip()


def _safe_upload_name(filename):
    name = os.path.basename(filename or "prompt-data.csv")
    stem, ext = os.path.splitext(name)
    if ext.lower() != ".csv":
        ext = ".csv"
    stem = re.sub(r"[^A-Za-z0-9_. -]+", "_", stem).strip(" .") or "prompt-data"
    return f"{stem}{ext}"


def _schema_response(path, force=False):
    cleaned_path = _clean_path(path)
    csv_data = _load_csv(cleaned_path, force=force)
    if csv_data is None:
        return {
            "ok": False,
            "path": cleaned_path,
            "columns": [],
            "error": "CSV not found or unreadable",
        }

    return {
        "ok": True,
        "path": cleaned_path,
        "columns": _active_columns(csv_data),
        "maxAttributes": MAX_ATTRIBUTES,
    }


@PromptServer.instance.routes.get("/daily/prompt-mixer-v2/schema")
async def daily_prompt_mixer_v2_schema(request):
    path = request.query.get("path", "")
    return web.json_response(_schema_response(path, force=True))


@PromptServer.instance.routes.post("/daily/prompt-mixer-v2/upload-csv")
async def daily_prompt_mixer_v2_upload_csv(request):
    os.makedirs(CSV_DIR, exist_ok=True)
    post = await request.post()
    upload = post.get("csv")
    if not upload or not getattr(upload, "file", None):
        return web.json_response({"ok": False, "error": "No CSV received"}, status=400)

    filename = _safe_upload_name(getattr(upload, "filename", "prompt-data.csv"))
    destination = os.path.abspath(os.path.join(CSV_DIR, filename))

    with open(destination, "wb") as f:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    return web.json_response(_schema_response(destination, force=True))


class PromptMixerV2dAIly:
    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "csv_path": ("STRING", {"default": "", "multiline": False, "defaultInput": True}),
            "template": (
                "STRING",
                {
                    "default": (
                        "A portrait with {Skin}, {Haircolor} hair, and {Eyes} eyes.\n"
                        "Scene: {Locate}.\n"
                        "Tip: click Refresh CSV after changing headers."
                    ),
                    "multiline": True,
                },
            ),
            "flat_mode": (
                "BOOLEAN",
                {
                    "default": True,
                    "label_on": "Flat (single line)",
                    "label_off": "Keep formatting (¶)",
                },
            ),
            "show_attribute_outputs": (
                "BOOLEAN",
                {
                    "default": True,
                    "label_on": "Show attribute outputs",
                    "label_off": "PROMPT only",
                },
            ),
            "seed": (
                "INT",
                {
                    "default": 0,
                    "min": 0,
                    "max": 0xFFFFFFFFFFFFFFFF,
                    "control_after_generate": True,
                },
            ),
            "schema_json": ("STRING", {"default": "[]", "multiline": False}),
        }

        optional = {
            slot: ("STRING", {"default": "", "multiline": False})
            for slot in ATTR_SLOTS
        }

        return {"required": required, "optional": optional}

    RETURN_TYPES = ("STRING", "STRING", *("STRING" for _ in ATTR_SLOTS))
    RETURN_NAMES = ("PROMPT", "USED_JSON", *(slot.upper() for slot in ATTR_SLOTS))
    FUNCTION = "make_prompt"
    CATEGORY = "Prompt/Utility"

    def make_prompt(
        self,
        csv_path,
        template,
        flat_mode=True,
        show_attribute_outputs=True,
        seed=0,
        schema_json="[]",
        **kwargs,
    ):
        if seed == 0:
            seed = int(time.time_ns() & 0x7FFFFFFF)

        csv_data = _load_csv(csv_path) or OrderedDict()
        schema_names = _schema_from_json(schema_json, csv_data)

        used = OrderedDict()
        attr_values = []
        for index, name in enumerate(schema_names):
            slot = ATTR_SLOTS[index]
            override = (kwargs.get(slot, "") or "").strip()
            if override:
                value = override
            else:
                value = _pick_seeded(seed, name, csv_data.get(name, []))
            used[name] = value
            attr_values.append(value)

        prompt = template or ""
        for name, value in used.items():
            prompt = prompt.replace("{" + name + "}", value)
        prompt = _format_prompt(prompt, flat_mode)

        used_json = json.dumps(
            {
                "seed": seed,
                "csv_path": _clean_path(csv_path),
                "attributes": used,
            },
            ensure_ascii=False,
        )

        attr_values.extend([""] * (MAX_ATTRIBUTES - len(attr_values)))
        return (prompt, used_json, *attr_values)
