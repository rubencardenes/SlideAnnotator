import numpy as np

from .nms import (
    _raise,
    non_maximum_suppression,
    non_maximum_suppression_sparse,
)


def ray_angles(n_rays=32):
    return np.linspace(0, 2 * np.pi, n_rays, endpoint=False)


def dist_to_coord(dist, points):
    """convert from polar to cartesian coordinates for a list of distances and center points
    dist.shape   = (n_polys, n_rays)
    points.shape = (n_polys, 2)
    return coord.shape = (n_polys,2,n_rays)
    """
    dist = np.asarray(dist)
    points = np.asarray(points)
    assert (
        dist.ndim == 2
        and points.ndim == 2
        and len(dist) == len(points)
        and points.shape[1] == 2
    )
    n_rays = dist.shape[1]
    phis = ray_angles(n_rays)
    coord = points[..., np.newaxis] + (
        dist[:, np.newaxis] * np.array([np.sin(phis), np.cos(phis)])
    )
    return coord


def label_are_sequential(y):
    """returns true if y has only sequential labels from 1..."""
    labels = np.unique(y)
    return (set(labels) - {0}) == set(range(1, 1 + labels.max()))


def is_array_of_integers(y):
    return isinstance(y, np.ndarray) and np.issubdtype(y.dtype, np.integer)


def _check_label_array(y, name=None, check_sequential=False):
    err = ValueError(
        "{label} must be an array of {integers}.".format(
            label="labels" if name is None else name,
            integers=("sequential " if check_sequential else "")
            + "non-negative integers",
        )
    )
    is_array_of_integers(y) or _raise(err)
    if len(y) == 0:
        return True
    if check_sequential:
        label_are_sequential(y) or _raise(err)
    else:
        y.min() >= 0 or _raise(err)
    return True


def polygons_to_label_coord(coord, shape, labels=None):
    """renders polygons to image of given shape

    coord.shape   = (n_polys, n_rays)
    """
    from skimage.draw import polygon

    coord = np.asarray(coord)
    if labels is None:
        labels = np.arange(len(coord))

    _check_label_array(labels, "labels")
    assert (
        coord.ndim == 3 and coord.shape[1] == 2 and len(coord) == len(labels)
    )

    lbl = np.zeros(shape, np.int32)

    for i, c in zip(labels, coord):
        rr, cc = polygon(*c, shape)
        lbl[rr, cc] = i + 1

    return lbl


def polygons_to_label(dist, points, shape, prob=None, thr=-np.inf):
    """converts distances and center points to label image

    dist.shape   = (n_polys, n_rays)
    points.shape = (n_polys, 2)

    label ids will be consecutive and adhere to the order given
    """
    dist = np.asarray(dist)
    points = np.asarray(points)
    prob = np.inf * np.ones(len(points)) if prob is None else np.asarray(prob)

    assert dist.ndim == 2 and points.ndim == 2 and len(dist) == len(points)
    assert len(points) == len(prob) and points.shape[1] == 2 and prob.ndim == 1

    # n_rays = dist.shape[1]

    ind = prob > thr
    points = points[ind]
    dist = dist[ind]
    prob = prob[ind]

    ind = np.argsort(prob, kind="stable")
    points = points[ind]
    dist = dist[ind]

    coord = dist_to_coord(dist, points)

    return polygons_to_label_coord(coord, shape=shape, labels=ind)


def instances_from_prediction(
    img_shape,
    prob,
    dist,
    grid,
    points=None,
    prob_class=None,
    prob_thresh=None,
    nms_thresh=None,
    overlap_label=None,
    return_labels=True,
    **nms_kwargs,
):
    """
    if points is None     -> dense prediction
    if points is not None -> sparse prediction

    if prob_class is None     -> single class prediction
    if prob_class is not None -> multi  class prediction
    """
    if overlap_label is not None:
        raise NotImplementedError("overlap_label not supported for 2D yet!")

    # sparse prediction
    if points is not None:
        points, probi, disti, indsi = non_maximum_suppression_sparse(
            dist, prob, points, nms_thresh=nms_thresh, **nms_kwargs
        )
        if prob_class is not None:
            prob_class = prob_class[indsi]

    # dense prediction
    else:
        points, probi, disti = non_maximum_suppression(
            dist,
            prob,
            grid=grid,
            prob_thresh=prob_thresh,
            nms_thresh=nms_thresh,
            **nms_kwargs,
        )
        if prob_class is not None:
            inds = tuple(p // g for p, g in zip(points.T, grid))
            prob_class = prob_class[inds]

    if return_labels:
        labels = polygons_to_label(disti, points, prob=probi, shape=img_shape)
    else:
        labels = None

    coord = dist_to_coord(disti, points)
    res_dict = dict(coord=coord, points=points, prob=probi)

    # multi class prediction
    if prob_class is not None:
        prob_class = np.asarray(prob_class)
        class_id = np.argmax(prob_class, axis=-1)
        res_dict.update(dict(class_prob=prob_class, class_id=class_id))

    return labels, res_dict
