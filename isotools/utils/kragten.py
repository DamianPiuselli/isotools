"""
Numerical uncertainty propagation using the Kragten method.
"""
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np


def propagate_kragten(
    model_func: Callable[[List[float]], float],
    params: List[float],
    uncertainties: List[float],
) -> Tuple[float, float]:
    """
    Performs uncertainty propagation using the Kragten numerical differentiation method.

    Args:
        model_func: A function that accepts a list of float arguments and returns a float.
                    f([x1, x2, ...]) -> y
        params: List of nominal values [x1, x2, ...]
        uncertainties: List of standard uncertainties (1 sigma) [u1, u2, ...] for each param.

    Returns:
        (nominal_y, combined_uncertainty)
    """
    y0, u_combined, _ = propagate_kragten_budget(model_func, params, uncertainties)
    return y0, u_combined


def propagate_kragten_budget(
    model_func: Callable[[List[float]], float],
    params: List[float],
    uncertainties: List[float],
    param_names: Optional[List[str]] = None,
) -> Tuple[float, float, Dict[str, float]]:
    """
    Performs Kragten numerical differentiation and returns the individual variance
    contributions (dy_i^2) for each parameter or named category.

    Args:
        model_func: Function f([x1, x2, ...]) -> y
        params: List of nominal values [x1, x2, ...]
        uncertainties: List of 1-sigma standard uncertainties [u1, u2, ...]
        param_names: Optional list of names/categories for each parameter.
                     If multiple parameters share a category name, their squared
                     contributions are summed into that category.

    Returns:
        (nominal_y, combined_uncertainty, variance_contributions_dict)
    """
    y0 = float(model_func(params))
    sum_squares = 0.0
    contributions: Dict[str, float] = {}

    if param_names is None:
        param_names = [f"param_{i}" for i in range(len(params))]

    for name in param_names:
        contributions.setdefault(name, 0.0)

    for i, u_i in enumerate(uncertainties):
        if u_i == 0 or np.isnan(u_i):
            continue

        p_perturbed = list(params)
        p_perturbed[i] += u_i

        y_p = float(model_func(p_perturbed))
        dy_sq = (y_p - y0) ** 2
        sum_squares += dy_sq

        cat_name = param_names[i] if i < len(param_names) else f"param_{i}"
        contributions[cat_name] = contributions.get(cat_name, 0.0) + dy_sq

    u_combined = float(np.sqrt(sum_squares))
    return y0, u_combined, contributions
