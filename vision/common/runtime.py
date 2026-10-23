"""Explicit numerical policy shared by original inference and fresh replays."""
def configure_fp32():
    import torch
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.deterministic=True
    return {'dtype':'float32','cuda_matmul_tf32':False,'cudnn_tf32':False,
            'matmul_precision':'highest','cudnn_benchmark':False,'cudnn_deterministic':True}
