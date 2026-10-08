"""Pure alpha-footprint validation; no Blender or image-editing dependencies."""
def alpha_bounds(pixels, width, height, channels=4, threshold=.05):
    if width <= 0 or height <= 0 or channels != 4:
        raise ValueError(f'Expected nonempty RGBA image, got {width}x{height} channels={channels}')
    expected = width * height * channels
    if len(pixels) != expected:
        raise ValueError(f'Incomplete image pixel buffer: expected {expected}, got {len(pixels)}')
    xmin, ymin, xmax, ymax = width, height, -1, -1
    for index in range(width * height):
        if pixels[index * channels + 3] > threshold:
            y, x = divmod(index, width)
            xmin, ymin = min(xmin, x), min(ymin, y)
            xmax, ymax = max(xmax, x), max(ymax, y)
    if xmax < 0:
        raise ValueError('Rendered image contains no visible asset pixels')
    return [xmin / width, ymin / height, (xmax + 1) / width, (ymax + 1) / height]

def is_core_asset(name):
    # Only the two long sleeves may leave frame, never gloves/cuffs/grip markers.
    return name not in {'Forearm_L', 'Forearm_R'}

def core_fully_visible(bounds, margin=.025):
    x0, y0, x1, y1 = bounds
    return margin <= x0 < x1 <= 1-margin and margin <= y0 < y1 <= 1-margin

def core_fit_score(bounds):
    if not core_fully_visible(bounds):
        return float('inf')
    x0, y0, x1, y1 = bounds
    return abs(x1-x0-.285)+abs(y1-y0-.27)+10*(max(0,.62-x0)+max(0,x1-.975)+max(0,.045-y0)+max(0,y1-.345))
