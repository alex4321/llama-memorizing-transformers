# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_memory_collection.ipynb.

# %% ../nbs/01_memory_collection.ipynb 4
from __future__ import annotations
import os
from typing import Union, List
import pickle
import numpy as np
import pandas as pd
import torch
from sklearn.neighbors import NearestNeighbors

# %% auto 0
__all__ = ['BaseMemoryCollection', 'CosineKnnMemoryCollection']

# %% ../nbs/01_memory_collection.ipynb 5
class BaseMemoryCollection:
    def reset(self) -> None:
        """
        Reset memory
        """
        raise NotImplementedError()
    
    def get(self, inputs: torch.FloatTensor) -> torch.FloatTensor:
        """
        Get relevant "memories".
        """
        raise NotImplementedError()
    
    def add(self, inputs: torch.FloatTensor) -> torch.FloatTensor:
        """
        Remember stuff
        """
        raise NotImplementedError()
    
    def save(self, directory: str) -> None:
        """
        Save memory state
        """
        raise NotImplementedError()
    
    @staticmethod
    def load(directory: str) -> BaseMemoryCollection:
        """
        Load memory state
        """
        raise NotImplementedError()

# %% ../nbs/01_memory_collection.ipynb 6
class CosineKnnMemoryCollection(BaseMemoryCollection):
    def __init__(self, max_temporary_buffer_size: int) -> None:
        super().__init__()
        self.max_temporary_buffer_size = max_temporary_buffer_size
        self.knns = []
        self.temporary_buffer = []
        self.vectors = []

    def _embeddings_numpy(self, embeddings: Union[np.ndarray, List[np.ndarray]]) -> np.ndarray:
        if isinstance(embeddings, list):
            return np.array(embeddings)
        return embeddings
    
    def _norm(self, inputs: np.ndarray) -> np.ndarray:
        embedding_dim = inputs.shape[-1]
        
        # sqrt(embedding_dim * (x^2)) = 1.0, x>0
        # embedding_dim * x^2 = 1.0, x>0
        # x^2 = 1/embedding_dim, x>0
        # x = 1/sqrt(embedding_dim)
        filler_dim_value = 1 / np.sqrt(embedding_dim)

        norm = np.sqrt((inputs ** 2).sum(axis=-1, keepdims=True))
        
        inputs_normed = inputs / norm
        inputs_normed[norm[:, 0] == 0] = filler_dim_value
        
        return inputs_normed

    def _bruteforce_knn(self, embeddings) -> NearestNeighbors:
        # Cosine similarity and L2 distance on normed vectors have 1.0 corellation
        # Minkowski metric with p=2 is same as L2
        nn = NearestNeighbors(n_neighbors=1, algorithm="brute", metric="minkowski", p=2, n_jobs=-1)
        nn.fit(self._norm(self._embeddings_numpy(embeddings)))
        return nn
    
    def _knn(self, embeddings) -> NearestNeighbors:
        # Cosine similarity and L2 distance on normed vectors have 1.0 corellation
        # Minkowski metric with p=2 is same as L2
        nn = NearestNeighbors(n_neighbors=1, algorithm="auto", metric="minkowski", p=2, n_jobs=-1)
        nn.fit(self._norm(self._embeddings_numpy(embeddings)))
        return nn
    
    def get(self, inputs: torch.FloatTensor) -> torch.FloatTensor:
        vectors = inputs.detach().cpu().float().numpy()
        vectors_normed = self._norm(vectors)
        nn: NearestNeighbors
        knns = self.knns
        if self.temporary_buffer:
            knns = knns + [self._bruteforce_knn(self.temporary_buffer)]
        if len(knns) == 0:
            return inputs
        vectors_found = np.zeros(
            (inputs.shape[0], len(knns), inputs.shape[1]),
            dtype=np.float32
        )
        for i, nn in enumerate(knns):
            indices_local = nn.kneighbors(vectors_normed, return_distance=False)
            indices = indices_local + i * self.max_temporary_buffer_size
            indices = indices.ravel()
            nn_vectors = [self.vectors[i] for i in indices]
            vectors_found[:, i, :] = nn_vectors
        vectors_chosen = np.zeros((inputs.shape[0], inputs.shape[1]))
        for i in range(inputs.shape[0]):
            nn: NearestNeighbors = self._bruteforce_knn(vectors_found[i])
            index = nn.kneighbors(vectors_normed[[i]], return_distance=False)
            index = index.ravel()[0]
            vectors_chosen[i, :] = vectors_found[i, index, :]
        vectors_chosen_torch = torch.tensor(vectors_chosen, dtype=inputs.dtype, device=inputs.device)
        return vectors_chosen_torch
    
    def add(self, inputs: torch.FloatTensor) -> torch.FloatTensor:
        vectors = inputs.detach().cpu().float().numpy()
        vectors_list = list(vectors)
        self.temporary_buffer += vectors_list
        self.vectors += vectors_list
        if len(self.temporary_buffer) >= self.max_temporary_buffer_size:
            knn_count = len(self.temporary_buffer) // self.max_temporary_buffer_size
            rest_buffer_length = len(self.temporary_buffer) % self.max_temporary_buffer_size
            for i in range(knn_count):
                embeddings = self.temporary_buffer[i * self.max_temporary_buffer_size : (i + 1) * self.max_temporary_buffer_size]
                self.knns.append(self._knn(embeddings))
            if rest_buffer_length == 0:
                self.temporary_buffer = []
            else:
                self.temporary_buffer = self.temporary_buffer[-rest_buffer_length:]

    def save(self, directory: str) -> None:
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, "cosine-knn-memory.pkl"), "wb") as dst:
            pickle.dump(self, dst)
    
    @staticmethod
    def load(directory: str) -> BaseMemoryCollection:
        with open(os.path.join(directory, "cosine-knn-memory.pkl"), "rb") as src:
            memory = pickle.load(src)
            assert isinstance(memory, CosineKnnMemoryCollection)
            return memory
