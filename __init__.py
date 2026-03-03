# __init__.py

from .token_counter import TokenCounterdAIly
from .prompt_mixer import PromptMixerdAIly

NODE_CLASS_MAPPINGS = {
    "TokenCounterdAIly": TokenCounterdAIly,
    "PromptMixerdAIly": PromptMixerdAIly
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TokenCounterdAIly": "Token Count",
    "PromptMixerdAIly":   "Prompt Mixer dAIly (CSV Wildcards)"
}