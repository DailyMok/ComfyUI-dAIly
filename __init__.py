# __init__.py

from .token_counter import TokenCounterdAIly
from .prompt_mixer import PromptMixerdAIly
from .prompt_mixer_v2 import PromptMixerV2dAIly

NODE_CLASS_MAPPINGS = {
    "TokenCounterdAIly": TokenCounterdAIly,
    "PromptMixerdAIly": PromptMixerdAIly,
    "PromptMixerV2dAIly": PromptMixerV2dAIly
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TokenCounterdAIly": "Token Count",
    "PromptMixerdAIly":   "Prompt Mixer dAIly (CSV Wildcards)",
    "PromptMixerV2dAIly": "Prompt Mixer dAIly v2 (Dynamic CSV)"
}

WEB_DIRECTORY = "./js"
