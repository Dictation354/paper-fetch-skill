---
title: "The Pulsar Radial Acceleration Relation"
authors: "Tariq Yasin, Harry Desmond"
journal: "arXiv"
doi: "10.48550/arxiv.2605.06659v1"
published: "2026-05-07"
source: "arxiv_html"
acquisition:
  provider: "arxiv"
  route: "official_html"
  representation: "html"
  transport: "http"
  fallback_used: false
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 2217
---

# The Pulsar Radial Acceleration Relation

## Abstract

The radial acceleration relation (RAR) links observed and baryonic accelerations, and is best established in rotation curves of late-type galaxies. Pulsar timing, which measures line-of-sight (LOS) differential accelerations between the Sun and pulsars, provides a novel probe of this relation, including along directions outside the Galactic disc. By combining these pulsar differential accelerations with the acceleration at the Sun, we test whether current pulsar timing data carry information on a vector generalisation of the RAR, ${\bm{g}}_{\rm obs}=\nu(|{\bm{g}}_{\rm bar}|){\bm{g}}_{\rm bar}$. Comparing the measured SPARC RAR (generalised to 3D) to 26 binary-system pulsars with literature accelerations, we find a reduced $\chi^{2}$ of 3.58, compared with 10.86 for Newtonian baryonic gravity alone. However, setting all accelerations to that of the Sun gives a reduced $\chi^{2}$ of 3.75, showing that this vector RAR test is dominated by the Solar acceleration with current data.

## I Introduction

The radial acceleration relation (RAR) is a tight empirical correlation between the inferred centripetal acceleration $g_{\rm obs}$ and the baryonic gravitational acceleration $g_{\rm bar}$, established primarily in disc galaxies [<sup>13, 20</sup>]. Its near-zero intrinsic scatter, simple functional form, and lack of secondary correlations [<sup>5, 6, 19</sup>] have been viewed as evidence for non-Newtonian dynamics [<sup>9</sup>, e.g.] or as a consequence of coupled baryon–halo assembly in $\Lambda$ CDM [<sup>17</sup>, e.g.]; here we treat it agnostically as simply an empirical mapping. Whether the RAR phenomenology extends beyond the radial dynamics of late-type galaxies measured from rotation curves remains unsettled [<sup>12, 3, 10, 15, 11</sup>, e.g.]. Pulsar timing provides a new probe of Galactic accelerations outside the Galactic disc: binary orbital-period derivatives measure line-of-sight (LOS) accelerations through the acceleration-induced drift of the Doppler shift [<sup>18, 4, 16, 8</sup>]. In this note, we use these measurements to test a phenomenological RAR rather than infer a full Galactic acceleration field [<sup>8, 7</sup>] or test a theory-specific model. We assume a local vector relation ${\bm{g}}_{\rm obs}=\nu(|{\bm{g}}_{\rm bar}|){\bm{g}}_{\rm bar}$ which we project onto the Sun–pulsar sightline. This tests whether pulsar timing, one of very few non-rotation-curve acceleration probes, is already informative about this striking relation.

## II Data and model

We use the v3 catalogue of T. Donlon et al. [7], which has 26 independent LOS accelerations inferred from orbital-period derivatives of pulsars in binary systems after Shklovskii and relativistic corrections. The catalogue also contains a sample of spin-only millisecond-pulsar accelerations (inferred with empirical magnetic-braking corrections). However we did not find that sample informative for our test due to the larger uncertainties, and so we report results for the binary sample only.

We compute the baryonic field from an analytic approximation to the photometric Milky Way census of J. Bland-Hawthorn & O. Gerhard [2]. We represent their thin disc, thick disc, cold gas and bulge/inner-disc components by three Miyamoto–Nagai discs with $(M,a,b)=(3.5\times 10^{10},2.6,0.3)$, $(6\times 10^{9},2.0,0.9)$ and $(1.0\times 10^{10},4.5,0.08)$, denoting mass and radial/vertical scale lengths in $M_{\odot}$ and kpc, plus a Hernquist bulge with mass $1.5\times 10^{10}M_{\odot}$ and scale radius $0.6\,{\rm kpc}$. The gas disc normalisation reproduces their quoted local gas surface density, $\Sigma_{g}(R_{0})\simeq 13\,M_{\odot}{\rm pc}^{-2}$. Observed pulsar positions are transformed to Galactocentric coordinates using $R_{0}=8.20\pm 0.09\,{\rm kpc}$ [<sup>14</sup>] and $z_{\odot}=20.8\,{\rm pc}$ [<sup>1</sup>]. Distance uncertainties are propagated approximately by re-evaluating the field at $d+\sigma_{d}$ and $d-\sigma_{d}$ and taking half the difference.

Pulsar timing measures the differential LOS acceleration of the pulsar relative to the Sun,

$$ a_{\rm LOS}^{\rm diff}=({\bm{g}}_{\rm psr}-{\bm{g}}_{\odot})\cdot\hat{\bm{\ell}}, $$
(1)

where ${\bm{g}}_{\rm psr}$ and ${\bm{g}}_{\odot}$ are Galactocentric accelerations and $\hat{\bm{\ell}}$ points from the Sun to the pulsar. Timing gives no information on components orthogonal to the Sun–pulsar sightline. We therefore compute $a_{\rm LOS}^{\rm obs}$, the pulsar’s Galactocentric acceleration projected onto the Sun–pulsar sightline:

$$ a_{\rm LOS}^{\rm obs}=a_{\rm LOS}^{\rm diff}+{\bm{g}}_{\odot}\cdot\hat{\bm{\ell}}={\bm{g}}_{\rm psr}\cdot\hat{\bm{\ell}}. $$
(2)

We adopt the Solar acceleration from P. J. McMillan [14] $a_{\odot,R}=-v_{0}^{2}/R_{0}=-2.15\times 10^{-10}\,{\rm m\,s}^{-2}$ (corresponding to circular velocity $v_{0}=233.1\pm 3.0\,{\rm km\,s}^{-1}$). The vertical Solar acceleration is evaluated from the baryonic model and is 1.7% of the centripetal term. As our primary output we plot $a_{\rm LOS}^{\rm obs}/({\bm{g}}_{\rm bar}\cdot\hat{\bm{\ell}})$, the ratio of the observed to baryonic Galactocentric accelerations projected along the line of sight.

The vector RAR prediction for $a_{\rm LOS}^{\rm obs}$ is

$$ a_{{\rm LOS},i}^{\rm pred}=\nu(|{\bm{g}}_{{\rm bar},i}|)({\bm{g}}_{{\rm bar},i}\cdot\hat{\bm{\ell}}_{i}), $$
(3)

with $\nu=1$ for Newtonian baryon-only gravity. We adopt the Simple interpolating function as constrained by galaxy dynamics in H. Desmond [6],

$$ \nu(x)=\frac{1}{2}+\sqrt{\frac{1}{4}+\frac{a_{0}}{x}},\quad a_{0}=1.19\times 10^{-10}\,{\rm m\,s}^{-2}. $$
(4)

We compare observed and predicted accelerations with $\chi^{2}_{\rm LOS}=\sum\limits_{i}(a_{{\rm LOS},i}^{\rm obs}-a_{{\rm LOS},i}^{\rm pred})^{2}/\sigma_{i}^{2}$, where $\sigma_{i}$ includes timing, Solar-correction, and distance-propagated baryonic-field uncertainties.

Converting the pulsar differential timing acceleration to a Galactocentric acceleration requires combining it with the empirical Solar centripetal acceleration. With the present sample, the median Solar acceleration fraction, $f_{\odot}\equiv|a_{\odot,\rm LOS}|/(|a_{\rm LOS}^{\rm diff}|+|a_{\odot,\rm LOS}|)$, is 0.73 for the binary sample. We therefore additionally conduct a Solar-acceleration-only test ($a_{\rm LOS}^{\rm diff}=0$) to isolate the effect of the pulsar-specific accelerations.

## III Results and discussion

![Figure 1](2605.06659v1_assets/fig_combined_binary.svg)

**Figure 1.** (a) Galactocentric positions of the binary pulsar sample (circles). (b) Boost ratio $a_{\rm LOS}^{\rm obs}/({\bm{g}}_{\rm bar}\cdot\hat{\bm{\ell}})$ versus $|{\bm{g}}_{\rm bar}|$. The red curve is the Simple RAR fit to galaxy rotation curves of H. Desmond [5] and the grey line is Newtonian. Points are coloured by the fraction of acceleration magnitude that is from the Solar acceleration. The cyan error bars show inverse-variance-weighted means in equally spaced bins in $\log_{10}g_{\rm bar}$ (only bins with two or more pulsars are shown). The black crosses show the Solar-only bin means (i.e. setting the measured differential acceleration to zero), offset horizontally for visual clarity. Triangles mark points clipped beyond the plotting range.

For the binary sample, the projected RAR gives $\chi^{2}_{\rm LOS}/N=3.58$ (for $N=26$ binaries), compared with 10.86 for Newtonian baryonic gravity. Neither value gives a satisfactory absolute goodness of fit, but the projected RAR is substantially closer to the data. The plot in fig. 1 shows this in ratio form, but the scatter is large and the sampled range in $|{\bm{g}}_{\rm bar}|$ is only about 0.8 dex around $a_{0}$. These data therefore cannot distinguish non-radial RAR extensions or theory-specific Galactic acceleration fields. The Solar-only null (setting $a_{\rm LOS}^{\rm diff}=0$ while retaining each sightline’s Solar projection) gives $\chi^{2}_{\rm LOS}/N=3.75$, close to the real binary value. This shows that the result is determined in large part by the Solar acceleration rather than by the pulsar-specific differential accelerations. Using the Milky Way baryonic potential of P. J. McMillan [14] instead gives $\chi^{2}/N=3.94$ for the projected RAR, 10.74 for Newtonian baryons, and 4.16 for the Solar-only comparison, demonstrating qualitative insensitivity to this systematic.

In conclusion, pulsar timing offers a direct probe of acceleration-based scaling relations, but the current binary sample is not yet significantly more informative than the Solar acceleration contribution alone. More precise binary acceleration measurements, larger samples, improved distances, and sightlines for which the Solar acceleration is a smaller fraction of the Galactocentric acceleration are required for more informative tests. The most useful future objects will be binary pulsars at lower $|{\bm{g}}_{\rm bar}|$, larger $|z|$, or Galactic longitudes for which the Solar centripetal acceleration projects weakly onto the Sun–pulsar sightline.

## References (20 total, showing 20)

[1] Bennett, M., & Bovy, J. 2019,, MNRAS, 482, 1417, doi: 10.1093/mnras/sty2813
[2] Bland-Hawthorn, J., & Gerhard, O. 2016, The Galaxy in Context: Structural, Kinematic, and Integrated Properties, ARA&A, 54, 529, doi: 10.1146/annurev-astro-081915-023441
[3] Brouwer, M. M., Oman, K. A., Valentijn, E. A., et al. 2021,, A&A, 650, A113, doi: 10.1051/0004-6361/202040108
[4] Chakrabarti, S., Chang, P., Lam, M. T., Vigeland, S. J., & Quillen, A. C. 2021, A Measurement of the Galactic Plane Mass Density from Binary Pulsar Accelerations, ApJ, 907, L26, doi: 10.3847/2041-8213/abd635
[5] Desmond, H. 2023a,, MNRAS, 526, 3342, doi: 10.1093/mnras/stad2762
[6] Desmond, H. 2023b,, MNRAS, 521, 1817, doi: 10.1093/mnras/stad597
[7] Donlon, T., Chakrabarti, S., Vanderwaal, S., et al. 2025,, Phys. Rev. D, 111, 103036, doi: 10.1103/PhysRevD.111.103036
[8] Donlon, T. I., Chakrabarti, S., Widrow, L. M., et al. 2024, Galactic structure from binary pulsar accelerations: Beyond smooth models, Phys. Rev. D, 110, 023026, doi: 10.1103/PhysRevD.110.023026
[9] Famaey, B., & McGaugh, S. S. 2012,, Living Reviews in Relativity, 15, 10, doi: 10.12942/lrr-2012-10
[10] Freundlich, J., Famaey, B., Oria, P.-A., et al. 2022,, A&A, 658, A26, doi: 10.1051/0004-6361/202142060
[11] Júlio, M. P., Read, J. I., Pawlowski, M. S., et al. 2025,, A&A, 704, A330, doi: 10.1051/0004-6361/202557106
[12] Lelli, F., McGaugh, S. S., Schombert, J. M., & Pawlowski, M. S. 2017, One Law to Rule Them All: The Radial Acceleration Relation of Galaxies, ApJ, 836, 152, doi: 10.3847/1538-4357/836/2/152
[13] McGaugh, S. S., Lelli, F., & Schombert, J. M. 2016,, Physical Review Letters, 117, 201101, doi: 10.1103/PhysRevLett.117.201101
[14] McMillan, P. J. 2017,, MNRAS, 465, 76, doi: 10.1093/mnras/stw2759
[15] Mistele, T., McGaugh, S., Lelli, F., Schombert, J., & Li, P. 2024,, Journal of Cosmology and Astroparticle Physics, 2024, 020, doi: 10.1088/1475-7516/2024/04/020
[16] Moran, A., Mingarelli, C. M. F., Van Tilburg, K., & Good, D. 2024, Pulsar-based map of galactic acceleration, Phys. Rev. D, 109, 123015, doi: 10.1103/PhysRevD.109.123015
[17] Paranjape, A., & Sheth, R. K. 2021,, MNRAS, 507, 632, doi: 10.1093/mnras/stab2141
[18] Phillips, D. F., Ravi, A., Ebadi, R., & Walsworth, R. L. 2021, Milky Way Accelerometry via Millisecond Pulsar Timing, Phys. Rev. Lett., 126, 141103, doi: 10.1103/PhysRevLett.126.141103
[19] Stiskalek, R., & Desmond, H. 2023,, MNRAS, 525, 6130, doi: 10.1093/mnras/stad2675
[20] Vărăşteanu, A. A., Jarvis, M. J., Ponomareva, A. A., et al. 2025, MIGHTEE-HI: the radial acceleration relation with resolved stellar mass measurements, MNRAS, 541, 2366, doi: 10.1093/mnras/staf1079
