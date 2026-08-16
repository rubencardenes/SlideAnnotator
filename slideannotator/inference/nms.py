from time import time

import numpy as np


class NMSExtensionUnavailable(RuntimeError):
    """The compiled StarDist NMS extension is missing for this platform."""


def _nms_ext(module_name):
    """Import a compiled NMS extension, or explain why it is unavailable.

    ``lib/stardist2d`` is a prebuilt macOS/arm64 CPython 3.12 binary, so on
    other platforms StarDist inference has to degrade with a clear message
    instead of an opaque ImportError from deep inside the call stack.
    """
    from importlib import import_module

    try:
        return import_module(f".lib.{module_name}", __package__)
    except ImportError as e:
        raise NMSExtensionUnavailable(
            f"StarDist non-maximum suppression is unavailable on this platform: "
            f"the compiled '{module_name}' extension is not bundled ({e})."
        ) from e


def _raise(e):
    if isinstance(e, BaseException):
        raise e
    else:
        raise ValueError(e)


def _is_power_of_2(i):
    assert i > 0
    e = np.log2(i)
    return e == int(e)


def _normalize_grid(grid, n):
    try:
        grid = tuple(grid)
        (
            len(grid) == n and all(map(np.isscalar, grid)) and all(map(_is_power_of_2, grid))
        ) or _raise(TypeError())
        return tuple(int(g) for g in grid)
    except (TypeError, AssertionError):
        raise ValueError(
            f"grid = {grid} must be a list/tuple of length {n} with values that are power of 2"
        )


def _ind_prob_thresh(prob, prob_thresh, b=2):
    if b is not None and np.isscalar(b):
        b = ((b, b),) * prob.ndim

    ind_thresh = prob > prob_thresh
    if b is not None:
        _ind_thresh = np.zeros_like(ind_thresh)
        ss = tuple(
            slice(_bs[0] if _bs[0] > 0 else None, -_bs[1] if _bs[1] > 0 else None) for _bs in b
        )
        _ind_thresh[ss] = True
        ind_thresh &= _ind_thresh
    return ind_thresh


def non_maximum_suppression(
    dist,
    prob,
    grid=(1, 1),
    b=2,
    nms_thresh=0.5,
    prob_thresh=0.5,
    use_bbox=True,
    use_kdtree=True,
    verbose=False,
):
    """Non-Maximum-Supression of 2D polygons

    Retains only polygons whose overlap is smaller than nms_thresh

    dist.shape = (Ny,Nx, n_rays)
    prob.shape = (Ny,Nx)

    returns the retained points, probabilities, and distances:

    points, prob, dist = non_maximum_suppression(dist, prob, ....

    """

    # TODO: using b>0 with grid>1 can suppress small/cropped objects at the image boundary

    assert prob.ndim == 2 and dist.ndim == 3 and prob.shape == dist.shape[:2]
    dist = np.asarray(dist)
    prob = np.asarray(prob)
    # n_rays = dist.shape[-1]

    grid = _normalize_grid(grid, 2)

    # mask = prob > prob_thresh
    # if b is not None and b > 0:
    #     _mask = np.zeros_like(mask)
    #     _mask[b:-b,b:-b] = True
    #     mask &= _mask

    mask = _ind_prob_thresh(prob, prob_thresh, b)
    points = np.stack(np.where(mask), axis=1)

    dist = dist[mask]
    scores = prob[mask]

    # sort scores descendingly
    ind = np.argsort(scores)[::-1]
    dist = dist[ind]
    scores = scores[ind]
    points = points[ind]

    points = points * np.array(grid).reshape((1, 2))

    if verbose:
        t = time()

    inds = non_maximum_suppression_inds(
        dist,
        points.astype(np.int32, copy=False),
        scores=scores,
        use_bbox=use_bbox,
        use_kdtree=use_kdtree,
        thresh=nms_thresh,
        verbose=verbose,
    )

    if verbose:
        print(f"keeping {np.count_nonzero(inds)}/{len(inds)} polygons")
        print(f"NMS took {time() - t:.4f} s")

    return points[inds], scores[inds], dist[inds]


def non_maximum_suppression_sparse(
    dist,
    prob,
    points,
    b=2,
    nms_thresh=0.5,
    use_bbox=True,
    use_kdtree=True,
    verbose=False,
):
    """Non-Maximum-Supression of 2D polygons from a list of dists, probs (scores), and points

    Retains only polyhedra whose overlap is smaller than nms_thresh

    dist.shape = (n_polys, n_rays)
    prob.shape = (n_polys,)
    points.shape = (n_polys,2)

    returns the retained instances

    (pointsi, probi, disti, indsi)

    with
    pointsi = points[indsi] ...

    """

    # TODO: using b>0 with grid>1 can suppress small/cropped objects at the image boundary

    dist = np.asarray(dist)
    prob = np.asarray(prob)
    points = np.asarray(points)
    # n_rays = dist.shape[-1]

    assert (
        dist.ndim == 2
        and prob.ndim == 1
        and points.ndim == 2
        and points.shape[-1] == 2
        and len(prob) == len(dist) == len(points)
    )

    verbose and print(
        f"predicting instances with nms_thresh = {nms_thresh}",
        flush=True,
    )

    inds_original = np.arange(len(prob))
    _sorted = np.argsort(prob)[::-1]
    probi = prob[_sorted]
    disti = dist[_sorted]
    pointsi = points[_sorted]
    inds_original = inds_original[_sorted]

    if verbose:
        print("non-maximum suppression...")
        t = time()

    inds = non_maximum_suppression_inds(
        disti,
        pointsi,
        scores=probi,
        thresh=nms_thresh,
        use_kdtree=use_kdtree,
        verbose=verbose,
    )

    if verbose:
        print(f"keeping {np.count_nonzero(inds)}/{len(inds)} polyhedra")
        print(f"NMS took {time() - t:.4f} s")

    return pointsi[inds], probi[inds], disti[inds], inds_original[inds]


def non_maximum_suppression_inds(
    dist, points, scores, thresh=0.5, use_bbox=True, use_kdtree=True, verbose=1
):
    """
    Applies non maximum supression to ray-convex polygons given by dists and points
    sorted by scores and IoU threshold

    P1 will suppress P2, if IoU(P1,P2) > thresh

    with IoU(P1,P2) = Ainter(P1,P2) / min(A(P1),A(P2))

    i.e. the smaller thresh, the more polygons will be supressed

    dist.shape = (n_poly, n_rays)
    point.shape = (n_poly, 2)
    score.shape = (n_poly,)

    returns indices of selected polygons
    """
    c_non_max_suppression_inds = _nms_ext("stardist2d").c_non_max_suppression_inds

    assert dist.ndim == 2
    assert points.ndim == 2

    n_poly = dist.shape[0]

    if scores is None:
        scores = np.ones(n_poly)

    assert len(scores) == n_poly
    assert points.shape[0] == n_poly

    def _prep(x, dtype):
        return np.ascontiguousarray(x.astype(dtype, copy=False))

    inds = c_non_max_suppression_inds(
        _prep(dist, np.float32),
        _prep(points, np.float32),
        np.int_(use_kdtree),
        np.int_(use_bbox),
        np.int_(verbose),
        np.float32(thresh),
    )

    return inds


#########


def non_maximum_suppression_3d(
    dist,
    prob,
    rays,
    grid=(1, 1, 1),
    b=2,
    nms_thresh=0.5,
    prob_thresh=0.5,
    use_bbox=True,
    use_kdtree=True,
    verbose=False,
):
    """Non-Maximum-Supression of 3D polyhedra

    Retains only polyhedra whose overlap is smaller than nms_thresh

    dist.shape = (Nz,Ny,Nx, n_rays)
    prob.shape = (Nz,Ny,Nx)

    returns the retained points, probabilities, and distances:

    points, prob, dist = non_maximum_suppression_3d(dist, prob, ....
    """

    # TODO: using b>0 with grid>1 can suppress small/cropped objects at the image boundary

    dist = np.asarray(dist)
    prob = np.asarray(prob)

    assert (
        prob.ndim == 3
        and dist.ndim == 4
        and dist.shape[-1] == len(rays)
        and prob.shape == dist.shape[:3]
    )

    grid = _normalize_grid(grid, 3)

    verbose and print(
        f"predicting instances with prob_thresh = {prob_thresh} and nms_thresh = {nms_thresh}",
        flush=True,
    )

    # ind_thresh = prob > prob_thresh
    # if b is not None and b > 0:
    #     _ind_thresh = np.zeros_like(ind_thresh)
    #     _ind_thresh[b:-b,b:-b,b:-b] = True
    #     ind_thresh &= _ind_thresh

    ind_thresh = _ind_prob_thresh(prob, prob_thresh, b)
    points = np.stack(np.where(ind_thresh), axis=1)
    verbose and print(f"found {len(points)} candidates")
    probi = prob[ind_thresh]
    disti = dist[ind_thresh]

    _sorted = np.argsort(probi)[::-1]
    probi = probi[_sorted]
    disti = disti[_sorted]
    points = points[_sorted]

    verbose and print("non-maximum suppression...")
    points = points * np.array(grid).reshape((1, 3))

    inds = non_maximum_suppression_3d_inds(
        disti,
        points,
        rays=rays,
        scores=probi,
        thresh=nms_thresh,
        use_bbox=use_bbox,
        use_kdtree=use_kdtree,
        verbose=verbose,
    )

    verbose and print(f"keeping {np.count_nonzero(inds)}/{len(inds)} polyhedra")
    return points[inds], probi[inds], disti[inds]


def non_maximum_suppression_3d_sparse(
    dist,
    prob,
    points,
    rays,
    b=2,
    nms_thresh=0.5,
    use_kdtree=True,
    verbose=False,
):
    """Non-Maximum-Supression of 3D polyhedra from a list of dists, probs and points

    Retains only polyhedra whose overlap is smaller than nms_thresh
    dist.shape = (n_polys, n_rays)
    prob.shape = (n_polys,)
    points.shape = (n_polys,3)

    returns the retained instances

    (pointsi, probi, disti, indsi)

    with
    pointsi = points[indsi] ...
    """

    # TODO: using b>0 with grid>1 can suppress small/cropped objects at the image boundary

    dist = np.asarray(dist)
    prob = np.asarray(prob)
    points = np.asarray(points)

    assert (
        dist.ndim == 2
        and prob.ndim == 1
        and points.ndim == 2
        and dist.shape[-1] == len(rays)
        and points.shape[-1] == 3
        and len(prob) == len(dist) == len(points)
    )

    verbose and print(
        f"predicting instances with nms_thresh = {nms_thresh}",
        flush=True,
    )

    inds_original = np.arange(len(prob))
    _sorted = np.argsort(prob)[::-1]
    probi = prob[_sorted]
    disti = dist[_sorted]
    pointsi = points[_sorted]
    inds_original = inds_original[_sorted]

    verbose and print("non-maximum suppression...")

    inds = non_maximum_suppression_3d_inds(
        disti,
        pointsi,
        rays=rays,
        scores=probi,
        thresh=nms_thresh,
        use_kdtree=use_kdtree,
        verbose=verbose,
    )

    verbose and print(f"keeping {np.count_nonzero(inds)}/{len(inds)} polyhedra")
    return pointsi[inds], probi[inds], disti[inds], inds_original[inds]


def non_maximum_suppression_3d_inds(
    dist,
    points,
    rays,
    scores,
    thresh=0.5,
    use_bbox=True,
    use_kdtree=True,
    verbose=1,
):
    """
    Applies non maximum supression to ray-convex polyhedra given by dists and rays
    sorted by scores and IoU threshold

    P1 will suppress P2, if IoU(P1,P2) > thresh

    with IoU(P1,P2) = Ainter(P1,P2) / min(A(P1),A(P2))

    i.e. the smaller thresh, the more polygons will be supressed

    dist.shape = (n_poly, n_rays)
    point.shape = (n_poly, 3)
    score.shape = (n_poly,)

    returns indices of selected polygons
    """
    c_non_max_suppression_inds = _nms_ext("stardist3d").c_non_max_suppression_inds

    assert dist.ndim == 2
    assert points.ndim == 2
    assert dist.shape[1] == len(rays)

    n_poly = dist.shape[0]

    if scores is None:
        scores = np.ones(n_poly)

    assert len(scores) == n_poly
    assert points.shape[0] == n_poly

    # sort scores descendingly
    ind = np.argsort(scores)[::-1]
    survivors = np.ones(n_poly, np.bool)
    dist = dist[ind]
    points = points[ind]
    scores = scores[ind]

    def _prep(x, dtype):
        return np.ascontiguousarray(x.astype(dtype, copy=False))

    if verbose:
        t = time()

    survivors[ind] = c_non_max_suppression_inds(
        _prep(dist, np.float32),
        _prep(points, np.float32),
        _prep(rays.vertices, np.float32),
        _prep(rays.faces, np.int32),
        _prep(scores, np.float32),
        np.int(use_bbox),
        np.int(use_kdtree),
        np.int(verbose),
        np.float32(thresh),
    )

    if verbose:
        print("NMS took %.4f s" % (time() - t))

    return survivors
