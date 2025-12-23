#!/usr/bin/env python3
"""
Configuration for Agent2 NeuralCD experiments (Thermo v0).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    subject_id: str = "thermo_v0"
    seed: int = 7

    # synthetic data
    num_students: int = 200
    interactions_per_student: int = 40

    # training
    batch_size: int = 256
    lr: float = 1e-2
    epochs: int = 20
    embed_init_scale: float = 0.01  # small init around 0

