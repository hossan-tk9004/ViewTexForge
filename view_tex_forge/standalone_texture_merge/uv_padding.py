import numpy as np


def pad(rgb, direct, occupied, islands, radius):
    """Exterior-only four-neighbor dilation; never fill unobserved UV interior.

    Shortest grid distance wins, then lowest island ID, then lowest source
    row-major pixel index. Never average competing islands or wrap borders.
    """
    height, width = direct.shape
    sentinel = np.iinfo(np.int64).max
    source = np.where(direct, np.arange(height*width).reshape(height, width), sentinel)
    island = np.where(direct, np.asarray(islands, np.int64), sentinel)
    valid = direct.copy()
    for _ in range(radius):
        candidate_source, candidate_island = source.copy(), island.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            s = np.roll(source, (dy, dx), (0, 1))
            i = np.roll(island, (dy, dx), (0, 1))
            if dy == 1: s[0], i[0] = sentinel, sentinel
            if dy == -1: s[-1], i[-1] = sentinel, sentinel
            if dx == 1: s[:, 0], i[:, 0] = sentinel, sentinel
            if dx == -1: s[:, -1], i[:, -1] = sentinel, sentinel
            better = (~occupied & ~valid & ((i < candidate_island) | ((i == candidate_island) & (s < candidate_source))))
            candidate_source[better], candidate_island[better] = s[better], i[better]
        added = ~valid & (candidate_source != sentinel)
        if not added.any():
            break
        source, island = candidate_source, candidate_island
        rgb[added] = rgb.reshape(-1, 3)[source[added]]
        valid |= added
    return rgb, valid & ~direct
