import torch
from torch import Tensor

from utils.pytorch_utils import masked_mean_std


def _mask_either_nan(x: Tensor, y: Tensor, fill_with: float = torch.nan):
    x = x.clone()
    y = y.clone()
    nan_mask = x.isnan() | y.isnan()
    x[nan_mask] = fill_with
    y[nan_mask] = fill_with
    n = (~nan_mask).sum(dim=1)
    return x, y, n, nan_mask


def _rank_data_1d(x: Tensor) -> Tensor:
    _, inv, counts = x.unique(return_inverse=True, return_counts=True)
    cs = counts.cumsum(dim=0)
    cs = torch.cat((torch.zeros(1, dtype=x.dtype, device=x.device), cs))
    rmin = cs[:-1]
    rmax = cs[1:] - 1
    ranks = (rmin + rmax) / 2
    return ranks[inv]


def _rank_data(x: Tensor, nan_mask: Tensor) -> Tensor:
    rank = torch.stack([_rank_data_1d(row) for row in x])
    rank[nan_mask] = 0
    return rank  # [d, s]


def _batch_pearsonr_given_mask(x: Tensor, y: Tensor, n: Tensor, mask: Tensor) -> Tensor:
    x_mean, x_std = masked_mean_std(x, n, mask)
    y_mean, y_std = masked_mean_std(y, n, mask)
    cov = (x * y).sum(dim=1) / n - x_mean * y_mean
    stdmul = x_std * y_std
    stdmul[(x_std < 1e-3) | (y_std < 1e-3)] = 1
    corrs = cov / stdmul
    return corrs


def batch_spearmanr(x: Tensor, y: Tensor) -> Tensor:
    x, y, n, nan_mask = _mask_either_nan(x, y)
    rx = _rank_data(x, nan_mask)
    ry = _rank_data(y, nan_mask)
    return _batch_pearsonr_given_mask(rx, ry, n, nan_mask)


def batch_pearsonr(x: Tensor, y: Tensor) -> Tensor:

    return _batch_pearsonr_given_mask(*_mask_either_nan(x, y, fill_with=0.0))
