"""Bundled-runtime cache policy, separate from the unchanged numerical engine."""
import os

# Also covers the independent original 2D entry point, which does not use the bridge.
# Matplotlib's original default is relative to its engine source; that source is signed here.
os.environ.setdefault('MPLCONFIGDIR', os.path.join(os.path.expanduser('~'), 'Library', 'Caches',
                                                'ArtificialEvolution2', 'matplotlib'))
