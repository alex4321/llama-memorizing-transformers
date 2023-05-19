# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_memorizing_block.ipynb.

# %% auto 0
__all__ = ['MemorizingLlamaDecoderLayer']

# %% ../nbs/02_memorizing_block.ipynb 1
from typing import Optional, Tuple
import torch
import torch.nn as nn
from transformers.models.llama.modeling_llama import LlamaDecoderLayer
from .context_choice import BaseContextChoice
from .memory_collection import BaseMemoryCollection

# %% ../nbs/02_memorizing_block.ipynb 2
class MemorizingLlamaDecoderLayer(nn.Module):
    def __init__(self, module: LlamaDecoderLayer, context_choice: BaseContextChoice, memory: BaseMemoryCollection) -> None:
        """
        Module wraps original LlamaDecoderLayer to add memorizing stuff
        :param module: original decoder layer
        :param context_choice: local vs memory context mixer
        :param memory: memory implementation itself
        """
        super(MemorizingLlamaDecoderLayer, self).__init__()
        self.module = module
        self.context_choice = context_choice
        self.memory = memory

    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        position_ids: Optional[torch.LongTensor] = None,
        past_key_value: Optional[Tuple[torch.Tensor]] = None,
        output_attentions: Optional[bool] = False,
        use_cache: Optional[bool] = False,
    ) -> Tuple[torch.FloatTensor, Optional[Tuple[torch.FloatTensor, torch.FloatTensor]]]:
        hidden_states_memory = self.memory.get(hidden_states)
        hidden_states_merged = self.context_choice(hidden_states, hidden_states_memory)
        self.memory.add(hidden_states)

        return self.module(hidden_states_merged, attention_mask, position_ids, past_key_value, output_attentions, use_cache)
