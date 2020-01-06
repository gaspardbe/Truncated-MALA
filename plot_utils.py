from typing import Callable, Dict, Union

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse
from scipy.stats import chi2

from hasting_metropolis import HastingMetropolis, MALA


def grid_evaluation(function: Callable[[np.ndarray], float], n_samples: int, x_range: tuple, y_range: tuple):
    """
    Evaluate a function of 2 variables on a grid.

    Parameters
    ----------
    function
        Function to evaluate; should take as input an array of dim. 2.
    n_samples: int
        # of samples on both dimensions.
    x_range: tuple
        Range for first variable.
    y_range: tuple
        Range for second variable.

    Returns
    -------
    Array of shape (n_samples, n_samples).
    """
    tx, ty = np.linspace(x_range[0], x_range[1], n_samples), np.linspace(y_range[0], y_range[1], n_samples)
    xx, yy = np.meshgrid(tx, ty)
    xy = np.stack([xx, yy], axis=-1).reshape(n_samples ** 2, 2)
    result = np.zeros(n_samples ** 2)
    # Should be broadcasted...
    for i in range(n_samples ** 2):
        result[i] = function(xy[i])
    return result.reshape((n_samples, n_samples))


def _check_models_dims(models: Dict[str, HastingMetropolis], dims, n_start, n_end, colors,
                       function_coords) -> Dict[str, HastingMetropolis]:
    if type(models) is HastingMetropolis:
        models = {'HM': models}
    for k in models:
        model = models[k]
        assert model.dims == dims, f"All model should have dimension {dims}"
        try:
            model.history['state'][n_start:n_end]
        except Exception as e:
            raise ValueError(f"Could not access indices {n_start} to {n_end} in model {k}. Got exception: {e}.")
    if len(colors) < len(models):
        raise ValueError(f"Provide more color for the legend ({len(colors)} < {len(models)})")
    if len(function_coords) != 4:
        raise ValueError(f"You need to provide an interval of size 4: (x_start, x_end, y_start, y_end). "
                         f"Got len: {len(function_coords)}.")
    return models


def _plot_ellipse_covariance(mean, cov, ax: plt.Axes, confidence=.9, facecolor='none', edgecolor="k",
                            linestyle='--', **kwargs):
    if type(confidence) is not list:
        confidence = [confidence]
    eigvals, eigvecs = np.linalg.eigh(cov)
    if np.min(eigvals) < 0:
        print(f"Found a negative eigenvalue. Aborting. ({eigvals})")
        return
    eigvals = np.sqrt(eigvals)
    if eigvecs[1, 0] == 0:
        angle = np.sign(eigvecs[1, 1]) * 90
    else:
        angle = np.arctan(eigvecs[1, 1]/eigvecs[1, 0]) * 360 / (2 * np.pi)

    patches = []
    for conf in confidence:
        s = np.sqrt(chi2.ppf(conf, df=2))
        ellipse = Ellipse(mean, width=2*eigvals[1] * s, height=2 * eigvals[0] * s, angle=angle,
                          facecolor=facecolor, alpha=.3,
                          edgecolor=edgecolor, linestyle=linestyle)
        patches.append(ax.add_patch(ellipse))
    return patches


def animation_model_states(models: Union[Dict[str, HastingMetropolis], HastingMetropolis],
                           function_array: np.ndarray, function_coords: tuple,
                           n_start: int = 0,
                           n_end: int = 100,
                           fig: plt.Figure = None,
                           ax: plt.Axes = None,
                           interval: float = 200,
                           colors=('g', 'b', 'k', 'c', 'r'),
                           plot_covariance=True,
                           **kwargs):
    """
    Make an animation, displaying one after the other the states of a model.

    Parameters
    ----------
    models: Union[Dict[str, HastingMetropolis], HastingMetropolis]
        The dictionary of models or a single model.
    function_array
        The array displayed in background. Should represent the target pdf we're trying to sample from.
    function_coords
        This array displayed in background is defined on a grid, function_coords: (x_start, x_end, y_start, y_end).
    n_start
        When to start displaying the steps
    n_end
        When to stop displaying the steps
    fig
        Matplotlib Figure or None.
    ax
        Matplotlib Axes or None.
    interval
        The interval between each image, in milliseconds.
    colors
        The colors of each models.
    plot_covariance
        Whether to plot the covariance matrices, for models with drifts.
    kwargs
        Other kwargs passed to Animation.

    Returns
    -------
    A Animation object.
    """
    models = _check_models_dims(models, dims=2, n_start=n_start, n_end=n_end, colors=colors,
                                function_coords=function_coords)
    if fig is None:
        fig = plt.gcf()
    if ax is None:
        ax = plt.gca()

    ax.imshow(function_array, extent=function_coords, cmap='coolwarm')

    # Just turning the history of each state in an array
    models_states = {k: np.array(models[k].history['state']) for k in models}
    lines = {}
    for i, k in enumerate(models):
        lines[k], = ax.plot([], [], "*%s" % colors[i])

    legend_elements = [Line2D([0], [0], lw=0, markerfacecolor=c, marker='*', label=k)
                       for c, k in zip(colors, models)]
    ax.legend(handles=legend_elements)

    def update_frame(iteration):
        covariance_patches = []
        for i, k in enumerate(models):
            model = models[k]
            model_state = models_states[k]
            x_data, y_data = model_state[:iteration, 0], model_state[:iteration, 1]
            lines[k].set_data(x_data, y_data)

            if plot_covariance and hasattr(model, 'gamma'):
                # Annoying little case for samplers which do not update the gamma param
                len_gamma = len(model.params_history['gamma'])
                if len_gamma-1 < iteration:
                    cov = model.params_history['gamma'][-1]
                else:
                    cov = model.params_history['gamma'][iteration]
                new_patch = _plot_ellipse_covariance(model_state[iteration],
                                                     cov=cov,
                                                     ax=ax,
                                                     edgecolor=colors[i])
                covariance_patches += new_patch
        return list(lines.values()) + covariance_patches

    animation = FuncAnimation(fig, update_frame, frames=np.arange(1, n_end-n_start), blit=True, interval=interval,
                              **kwargs)

    return animation