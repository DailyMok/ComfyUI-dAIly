# __init__.py

from .token_counter import SimpleTokenDisplay
from .prompt_mixer import PromptMixerdAIly

NODE_CLASS_MAPPINGS = {
    "SimpleTokenDisplay": SimpleTokenDisplay,
    "PromptMixerdAIly": PromptMixerdAIly
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SimpleTokenDisplay": "Token Info Display (CLIP / T5 / Qwen)",
    "PromptMixerdAIly":   "Prompt Mixer dAIly (CSV Wildcards)"
}