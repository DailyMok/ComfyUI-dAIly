import torch
from transformers import CLIPTokenizerFast, T5TokenizerFast, AutoTokenizer
import comfy.sd
import folder_paths
import os

class TokenCounterdAIly:
    """
    Compte les tokens CLIP-L / T5 / Qwen et affiche uniquement une STRING formatée
    + met à jour le titre du node
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "clip": ("CLIP", ),       # optionnel → pour précision CLIP-L
                "t5_clip": ("CLIP", ),    # optionnel → pour précision T5 Flux
            }
        }

    RETURN_TYPES = ("STRING", )
    RETURN_NAMES = ("token_info", )
    FUNCTION = "count_and_format"
    CATEGORY = "utils/text"
    OUTPUT_NODE = True

    # Cache tokenizers
    clip_tokenizer = None
    t5_tokenizer = None
    qwen_tokenizer = None

    @classmethod
    def try_load_tokenizers(cls):
        if cls.clip_tokenizer is None:
            try:
                clip_path = folder_paths.get_full_path("clip", "clip_l.safetensors") or \
                            folder_paths.get_full_path("clip", "clip_g.safetensors")
                if clip_path and os.path.exists(clip_path):
                    cls.clip_tokenizer = comfy.sd.load_clip_tokenizer(clip_path)
                else:
                    cls.clip_tokenizer = CLIPTokenizerFast.from_pretrained("openai/clip-vit-large-patch14")
            except Exception as e:
                print(f"[TokenDisplay] CLIP load failed: {e}")
                cls.clip_tokenizer = CLIPTokenizerFast.from_pretrained("openai/clip-vit-large-patch14")

        if cls.t5_tokenizer is None:
            try:
                t5_path = folder_paths.get_full_path("clip", "t5xxl_fp16.safetensors") or \
                          folder_paths.get_full_path("clip", "t5xxl_fp8_e4m3fn.safetensors")
                if t5_path and os.path.exists(t5_path):
                    cls.t5_tokenizer = comfy.sd.load_t5_tokenizer(t5_path)
                else:
                    cls.t5_tokenizer = T5TokenizerFast.from_pretrained("google/flan-t5-xxl")
            except Exception as e:
                print(f"[TokenDisplay] T5 load failed: {e}")
                cls.t5_tokenizer = T5TokenizerFast.from_pretrained("google/flan-t5-xxl")

        if cls.qwen_tokenizer is None:
            try:
                qwen_path = folder_paths.get_full_path("LLM", "Qwen2.5-3B-Instruct") or \
                            folder_paths.get_full_path("LLM", "Qwen2.5-7B-Instruct")
                if qwen_path and os.path.exists(qwen_path):
                    cls.qwen_tokenizer = AutoTokenizer.from_pretrained(qwen_path)
                else:
                    cls.qwen_tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct")
            except Exception as e:
                print(f"[TokenDisplay] Qwen load failed: {e}")
                cls.qwen_tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct")

    def count_and_format(self, text, clip=None, t5_clip=None):
        self.try_load_tokenizers()

        clip_count = 0
        t5_count = 0
        qwen_count = 0

        if text.strip():
            # CLIP-L
            if self.clip_tokenizer:
                try:
                    tokens = self.clip_tokenizer(text, truncation=False)["input_ids"]
                    clip_count = len(tokens)
                except:
                    clip_count = len(self.clip_tokenizer.encode(text))

            # T5
            if self.t5_tokenizer:
                try:
                    tokens = self.t5_tokenizer(text, truncation=False)["input_ids"]
                    t5_count = len(tokens)
                except:
                    t5_count = len(self.t5_tokenizer.encode(text))

            # Qwen
            if self.qwen_tokenizer:
                try:
                    tokens = self.qwen_tokenizer(text, add_special_tokens=True)["input_ids"]
                    qwen_count = len(tokens)
                except:
                    qwen_count = len(self.qwen_tokenizer.encode(text))

        chars = len(text)

        # Format exact demandé
        info = (
            f"Clip L token : {clip_count}\n"
            f"T5 Token : {t5_count}\n"
            f"Qwen 3_4 b Token : {qwen_count}\n"
            f"Character : {chars}"
        )

        # Mise à jour titre node (visible même sans preview)
        self.display_name = f"Tokens | C{clip_count} T{t5_count} Q{qwen_count} | {chars}ch"

        return (info, )


# Pas de NODE_CLASS_MAPPINGS ici → c'est géré dans __init__.py