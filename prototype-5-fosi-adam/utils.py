import torch
import torch_xla    # This is the PyTorch-XLA package that works onluy in the server not need to install in the local machine
import torch_xla.core.xla_model as xm # This is the PyTorch-XLA package that works onluy in the server not need to install in the local machine
import random
import numpy as np
from icecream import ic

def set_seed(seed: int):
    """
    Set random seed for reproducibility across multiple libraries.

    Args:
        seed (int): The seed value to set.
    """
    # Set seed for random and numpy
    random.seed(seed)
    np.random.seed(seed)

    # Set seed for torch
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    # Set seed for tensorflow (if available)
    if torch.cuda.is_available():
        try:
            import tensorflow as tf
            tf.random.set_seed(seed)
        except ImportError:
            pass  # TensorFlow is not available


def select_device():
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif xm.xla_device():
        device = torch.device("xla")
    else:
        device = torch.device("cpu")
    ic(device)
    return device