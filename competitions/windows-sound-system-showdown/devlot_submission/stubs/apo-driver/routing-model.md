# Stereo to 7.2 Routing Model

Channel order used by this submission:

1. FL
2. FR
3. FC
4. BL
5. BR
6. SL
7. SR
8. LFE1
9. LFE2

Routing coefficients:

- FC = 0.75 * (L + R) / 2
- BL = 0.55 * L
- BR = 0.55 * R
- SL = 0.40 * L
- SR = 0.40 * R
- LFE1 = 0.30 * (L + R) / 2
- LFE2 = 0.18 * (L + R) / 2

For devices with lower channel counts, this model folds down to endpoint mix format in user-mode.
