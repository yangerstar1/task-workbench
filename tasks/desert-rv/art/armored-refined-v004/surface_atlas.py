"""Bounded original palette treatment of the bundled CC0 Poly Haven surface.
Macro silhouette is geometry; imported rust only modulates broad paint/steel roughness.
"""
SIZE=1024
PALETTE=[(.56,.39,.20),(.30,.10,.047),(.09,.105,.10),(.16,.12,.071),(.85,.29,.027),(.50,.36,.19),(.30,.32,.28),(.025,.027,.021)]
def texel(tile,u,v,source_rgb):
    base=PALETTE[tile]; luminance=.2126*source_rgb[0]+.7152*source_rgb[1]+.0722*source_rgb[2]
    rust=max(0,min(1,(source_rgb[0]-source_rgb[2])*2.2))
    edge=min(u,1-u,v,1-v)
    # A few broad irregular wear islands plus restrained rim abrasion; no repeating stripes.
    chipped=tile in (0,1) and ((edge<.024 and luminance<.62) or (u>.83 and .24<v<.36) or (u<.13 and v>.78))
    metal=tile in (2,6) or chipped
    substrate=(.21,.235,.225) if chipped else base
    variation=(luminance-.45)*(.12 if metal else .045)
    dust=max(0,(.21-v))*.12
    rgb=tuple(max(.008,min(1,c+variation+dust*(.85,.62,.32)[i]-rust*.018)) for i,c in enumerate(substrate))
    roughness=max(.3,min(.92,(.43 if metal else .76)+rust*.12+dust))
    metallic=.78 if metal else 0
    return rgb,(1,roughness,metallic)
