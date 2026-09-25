# Training

Training consumes a prepared dataset and learns a reconstruction model with
the supported dilated convolutional encoder. It runs on CUDA and never
invokes preparation.

This page currently maps the next step of the journey. Full guidance —
fixed-experiment and hyperparameter configuration, the training and explicit
resume commands, validation-selected checkpoints, one-time held-out test
reporting, and run artifacts — arrives with the reconstruction training
guide. Start from a verified processed dataset (see
[Preparation](preparation.md)) and keep its `dataset.json` identity stable:
resume and inference compare dataset identities rather than trusting paths
alone.
