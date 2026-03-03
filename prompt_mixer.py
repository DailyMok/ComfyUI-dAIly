import csv
import json
import os
import random
import threading
import time
import hashlib

# --- Cache CSV thread-safe ---
_CSV_CACHE = {}
_CSV_LOCK = threading.Lock()

# Tous les champs peuvent maintenant venir du CSV
FIELDS = [
    "Skin", "Bodytype", "Hairstyle", "Haircolor", "Eyes", "Clothes",
    "Expression", "Pose", "Locate",
    "LightSource", "LightingType", "ShotSize", "Composition",
    "FocalLength", "CameraAngle", "LensType", "Color",
    "Effect",
    "Extra1", "Extra2", "Extra3",
    "Accessories"
]

def _norm(s: str) -> str:
    return (s or "").strip().lower().replace("_", " ").replace("-", " ")

def _strip_header(h: str) -> str:
    return (h or "").strip()

CSV_COLUMN_ALIASES = {
    "skin": ["skin"],
    "bodytype": ["bodytype", "body type", "body"],
    "hairstyle": ["hairstyle", "hair style", "haircut"],
    "haircolor": ["haircolor", "hair color", "hair colour"],
    "eyes": ["eyes", "eye", "eyes color", "eye color"],
    "clothes": ["clothes", "outfit", "clothing"],
    "expression": ["expression", "facial expression", "mood"],
    "pose": ["pose", "poses", "posture", "stance"],
    "locate": ["locate", "location", "place", "background", "scene", "setting"],
    "lightsource": ["light source", "lighting source", "main light", "key light", "light"],
    "lightingtype": ["lighting type", "light type", "illumination type"],
    "shotsize": ["shot size", "shot", "frame size"],
    "composition": ["composition", "framing", "frame composition", "rule of thirds", "balance"],
    "focallength": ["focal length", "focal", "lens length", "mm"],
    "cameraangle": ["camera angle", "angle", "view angle"],
    "lenstype": ["lens type", "lens", "prime", "zoom"],
    "color": ["color", "colortone", "colour tone", "color grading", "tone", "grading"],
    "effect": ["effect", "effects", "fx", "vfx"],
    "extra1": ["extra1", "extra 1", "bonus1"],
    "extra2": ["extra2", "extra 2", "bonus2"],
    "extra3": ["extra3", "extra 3", "bonus3"],
    "accessories": ["accessories", "accessory", "props", "items"],
}

def _match_column(header_names, wanted_key):
    wanted = _norm(wanted_key)
    aliases = CSV_COLUMN_ALIASES.get(wanted, [wanted])
    normalized_headers = {h: _norm(h) for h in header_names}

    alias_norm = {_norm(a) for a in aliases}
    for h, hn in normalized_headers.items():
        if hn in alias_norm:
            return h

    head = wanted.split()[0] if wanted else ""
    for h, hn in normalized_headers.items():
        if head and hn.startswith(head):
            return h

    for h, hn in normalized_headers.items():
        if any(tok and tok in hn for tok in alias_norm):
            return h

    return None


def _load_csv(path):
    """
    Tente de charger le CSV avec plusieurs encodages courants dans l'ordre le plus probable.
    Retourne None si aucun encodage ne fonctionne.
    """
    path = (path or "").strip().strip('"').strip("'")
    if not path or not os.path.exists(path):
        return None

    try:
        mtime = os.path.getmtime(path)
    except:
        return None

    with _CSV_LOCK:
        cache_entry = _CSV_CACHE.get(path)
        if cache_entry and cache_entry["mtime"] == mtime:
            return cache_entry["data"]

        # Ordre des encodages : le plus courant → le moins courant
        encodings_to_try = [
            "utf-8-sig",      # Excel "CSV UTF-8" + Notepad++ UTF-8 BOM
            "utf-8",          # Standard Linux/Mac, éditeurs modernes
            "cp1252",         # Windows ANSI Europe de l'Ouest (Excel classique FR)
            "iso-8859-1",     # Latin-1 (très proche de cp1252)
            "latin1"          # Dernier recours (ne plante jamais, mais peut donner des caractères bizarres)
        ]

        data_by_col = None
        used_encoding = None

        for encoding in encodings_to_try:
            try:
                data_by_col = {}
                with open(path, "r", encoding=encoding, newline="") as f:
                    reader = csv.DictReader(f, delimiter=";")
                    headers = [_strip_header(h) for h in (reader.fieldnames or [])]
                    
                    for h in headers:
                        data_by_col[h] = []
                    
                    for row in reader:
                        for h in headers:
                            val = (row.get(h) or "").strip()
                            if val:
                                data_by_col[h].append(val)

                used_encoding = encoding
                break  # Succès → on arrête ici

            except UnicodeDecodeError:
                continue  # Cet encodage ne convient pas → on passe au suivant
            except Exception as e:
                print(f"[PromptMixerdAIly] Erreur CSV avec {encoding}: {e}")
                continue

        if data_by_col is not None:
            _CSV_CACHE[path] = {"mtime": mtime, "data": data_by_col}
            if used_encoding != "utf-8-sig":  # On prévient gentiment si ce n'est pas l'idéal
                print(f"[PromptMixerdAIly] CSV chargé avec {used_encoding} (utf-8-sig recommandé pour compatibilité max)")
            return data_by_col
        
        print("[PromptMixerdAIly] Impossible de charger le CSV - aucun encodage compatible trouvé")
        return None


def _seed_to_int(seed, salt=""):
    h = hashlib.sha256(f"{int(seed)}::{salt}".encode()).hexdigest()
    return int(h[:16], 16)


class _SeededRNG:
    def __init__(self, seed, salt=""):
        self._rng = random.Random(_seed_to_int(seed, salt))
    
    def choice(self, seq):
        return seq[self._rng.randrange(len(seq))] if seq else ""


class PromptMixerdAIly:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "csv_path": ("STRING", {"default": "", "multiline": False}),
                "template": ("STRING", {
                    "default": (
                        "A stunning graphic anime illustration image with one stunning young woman,\n"
                        "with a beautiful anatomy in her 20s.\n\n"
                        "About the woman : she is a {ShotSize} woman, named Amanda : she have {Skin} with a {Bodytype}.\n"
                        "She have beautiful {Haircolor} hair styled in a {Hairstyle} and stunning {Eyes} eyes.\n"
                        "She is wearing {Clothes}.\n"
                        "Alone, She {Pose} .\n\n"
                        "About the locate : a unique mix between {Locate} and {FocalLength}.\n\n"
                        "Tip: turn flat_mode OFF to preserve paragraphs and line breaks."
                    ),
                    "multiline": True
                }),
                "flat_mode": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Flat (single line)",
                    "label_off": "Keep formatting (¶)",
                    "tooltip": "ON = aplatit tout en une ligne (comme avant)\nOFF = conserve les sauts de ligne et la mise en forme"
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff,
                    "control_after_generate": True,  # active fixed / randomize / increment / decrement
                }),
            },
            "optional": {
                field: ("STRING", {"default": "", "multiline": False})
                for field in FIELDS
            }
        }

    RETURN_TYPES = (
        "STRING", "STRING",
        "STRING", "STRING", "STRING", "STRING", "STRING", "STRING",
        "STRING", "STRING", "STRING", "STRING", "STRING", "STRING",
        "STRING", "STRING", "STRING", "STRING", "STRING", "STRING",
        "STRING", "STRING", "STRING", "STRING"
    )
    
    RETURN_NAMES = (
        "PROMPT", "USED_JSON",
        "Skin", "Bodytype", "Hairstyle", "Haircolor", "Eyes", "Clothes",
        "Expression", "Pose", "Locate",
        "LightSource", "LightingType", "ShotSize", "Composition",
        "FocalLength", "CameraAngle", "LensType", "Color",
        "Effect",
        "Extra1", "Extra2", "Extra3",
        "Accessories"
    )
    
    FUNCTION = "make_prompt"
    CATEGORY = "Prompt/Utility"

    def make_prompt(self, csv_path, template, flat_mode=True, seed=0, **kwargs):
        
        # Si seed == 0 et qu'on n'est pas en mode "fixed" forcé par connexion,
        # ComfyUI gère déjà randomize/increment → on peut laisser tel quel
        # Mais pour cohérence on garde la logique "0 = random frais"
        if seed == 0:
            seed = int(time.time_ns() & 0x7FFFFFFF)

        csv_data = _load_csv(csv_path)
        headers = list(csv_data.keys()) if csv_data else []

        used = {}
        for field in FIELDS:
            user_val = kwargs.get(field, "").strip()
            if user_val:
                used[field] = user_val
                continue

            picked = ""
            if csv_data:
                col = _match_column(headers, field)
                if col:
                    seq = csv_data[col]
                    picked = _SeededRNG(seed, f"{field}::{col}").choice(seq)
            used[field] = picked or ""

        prompt = template
        for k, v in used.items():
            prompt = prompt.replace("{" + k + "}", v)

        # ────────────────────────────────────────────────
        #  GESTION DU FLATTENING
        # ────────────────────────────────────────────────
        if flat_mode:
            # Mode original : tout sur une seule ligne
            prompt = " ".join(prompt.split())
        else:
            # Mode paragraphes : on conserve la structure
            lines = []
            for line in prompt.splitlines():
                lines.append(line.rstrip())  # enlève espaces de fin seulement

            prompt = "\n".join(lines).strip()

        used_json = json.dumps({"seed": seed, **used}, ensure_ascii=False)

        return (
            prompt,
            used_json,
            used.get("Skin", ""),
            used.get("Bodytype", ""),
            used.get("Hairstyle", ""),
            used.get("Haircolor", ""),
            used.get("Eyes", ""),
            used.get("Clothes", ""),
            used.get("Expression", ""),
            used.get("Pose", ""),
            used.get("Locate", ""),
            used.get("LightSource", ""),
            used.get("LightingType", ""),
            used.get("ShotSize", ""),
            used.get("Composition", ""),
            used.get("FocalLength", ""),
            used.get("CameraAngle", ""),
            used.get("LensType", ""),
            used.get("Color", ""),
            used.get("Effect", ""),
            used.get("Extra1", ""),
            used.get("Extra2", ""),
            used.get("Extra3", ""),
            used.get("Accessories", "")
        )