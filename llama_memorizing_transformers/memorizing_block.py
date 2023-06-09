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
    def __init__(self,
                 module: LlamaDecoderLayer,
                 context_choice: BaseContextChoice,
                 memory: BaseMemoryCollection,
                 device: torch.device) -> None:
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

    def _extract_from_memory(self, hidden_states: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            batch_size, seq_length, embeddings_dim = hidden_states.shape
            hidden_states_memory = []
            for i in range(batch_size):
                hidden_states_memory.append(
                    self.memory.get(hidden_states[i]).view((1, seq_length, embeddings_dim))
                )
            hidden_states_memory = torch.cat(hidden_states_memory)
        return hidden_states_memory
    
    def _add_to_memory(self, hidden_states: torch.Tensor, position_ids: torch.LongTensor) -> None:
        with torch.no_grad():
            batch_size, _, _ = hidden_states.shape
            for i in range(batch_size):
                sample_hidden_states = hidden_states[i]
                sample_memory_position_ids = position_ids[i]
                self.memory.add(sample_hidden_states, sample_memory_position_ids)

    def _normed(self, hidden_states: torch.Tensor) -> torch.Tensor:
        norm = torch.sqrt((hidden_states ** 2).sum(dim=-1, keepdim=True)) + 1e-4
        return hidden_states / norm, norm

    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        position_ids: Optional[torch.LongTensor] = None,
        past_key_value: Optional[Tuple[torch.Tensor]] = None,
        output_attentions: Optional[bool] = False,
        use_cache: Optional[bool] = False,
    ) -> Tuple[torch.FloatTensor, Optional[Tuple[torch.FloatTensor, torch.FloatTensor]]]:
        hidden_states_memory = self._extract_from_memory(hidden_states)
        hidden_states_normed, hidden_states_norm = self._normed(hidden_states)
        hidden_states_memory_normed, _ = self._normed(hidden_states_memory)
        hidden_states_merged = self.context_choice(hidden_states_normed, hidden_states_memory_normed)
        
        hidden_states_merged_rescaled = hidden_states_merged * hidden_states_norm

        self._add_to_memory(hidden_states, position_ids)
        return self.module(hidden_states_merged_rescaled,
                           attention_mask,
                           position_ids,
                           past_key_value,
                           output_attentions,
                           use_cache)
