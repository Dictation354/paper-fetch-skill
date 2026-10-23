---
title: "The Pulsar Radial Acceleration Relation"
authors: "Tariq Yasin, Harry Desmond"
journal: "arXiv"
doi: "10.48550/arxiv.2605.06659v1"
published: "2026-05-07"
source: "arxiv_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 2758
---

# The Pulsar Radial Acceleration Relation

## Abstract

The radial acceleration relation (RAR) links observed and baryonic accelerations, and is best established in rotation curves of late-type galaxies. Pulsar timing, which measures line-of-sight (LOS) differential accelerations between the Sun and pulsars, provides a novel probe of this relation, including along directions outside the Galactic disc. By combining these pulsar differential accelerations with the acceleration at the Sun, we test whether current pulsar timing data carry information on a vector generalisation of the RAR, ${\mathbf{g}}_{\mathrm{obs}} = {\nu\hspace{0pt}{({|{\mathbf{g}}_{\mathrm{bar}}|})}\hspace{0pt}{\mathbf{g}}_{\mathrm{bar}}}$. Comparing the measured SPARC RAR (generalised to 3D) to 26 binary-system pulsars with literature accelerations, we find a reduced $\chi^{2}$ of 3.58, compared with 10.86 for Newtonian baryonic gravity alone. However, setting all accelerations to that of the Sun gives a reduced $\chi^{2}$ of 3.75, showing that this vector RAR test is dominated by the Solar acceleration with current data.

## I Introduction

The radial acceleration relation (RAR) is a tight empirical correlation between the inferred centripetal acceleration $g_{\rm obs}$ and the baryonic gravitational acceleration $g_{\rm bar}$, established primarily in disc galaxies (S. S. McGaugh et al., [2016](https://arxiv.org/html/2605.06659v1#bib.bib13); A. A. Vărăşteanu et al., [2025](https://arxiv.org/html/2605.06659v1#bib.bib20)). Its near-zero intrinsic scatter, simple functional form, and lack of secondary correlations (H. Desmond, [2023a](https://arxiv.org/html/2605.06659v1#bib.bib5), [b](https://arxiv.org/html/2605.06659v1#bib.bib6); R. Stiskalek & H. Desmond, [2023](https://arxiv.org/html/2605.06659v1#bib.bib19)) have been viewed as evidence for non-Newtonian dynamics (e.g. B. Famaey & S. S. McGaugh, [2012](https://arxiv.org/html/2605.06659v1#bib.bib9)) or as a consequence of coupled baryon–halo assembly in $\Lambda$CDM (e.g. A. Paranjape & R. K. Sheth, [2021](https://arxiv.org/html/2605.06659v1#bib.bib17)); here we treat it agnostically as simply an empirical mapping. Whether the RAR phenomenology extends beyond the radial dynamics of late-type galaxies measured from rotation curves remains unsettled (e.g. F. Lelli et al., [2017](https://arxiv.org/html/2605.06659v1#bib.bib12); M. M. Brouwer et al., [2021](https://arxiv.org/html/2605.06659v1#bib.bib3); J. Freundlich et al., [2022](https://arxiv.org/html/2605.06659v1#bib.bib10); T. Mistele et al., [2024](https://arxiv.org/html/2605.06659v1#bib.bib15); M. P. Júlio et al., [2025](https://arxiv.org/html/2605.06659v1#bib.bib11)). Pulsar timing provides a new probe of Galactic accelerations outside the Galactic disc: binary orbital-period derivatives measure line-of-sight (LOS) accelerations through the acceleration-induced drift of the Doppler shift (D. F. Phillips et al., [2021](https://arxiv.org/html/2605.06659v1#bib.bib18); S. Chakrabarti et al., [2021](https://arxiv.org/html/2605.06659v1#bib.bib4); A. Moran et al., [2024](https://arxiv.org/html/2605.06659v1#bib.bib16); T. I. Donlon et al., [2024](https://arxiv.org/html/2605.06659v1#bib.bib8)). In this note, we use these measurements to test a phenomenological RAR rather than infer a full Galactic acceleration field (T. I. Donlon et al., [2024](https://arxiv.org/html/2605.06659v1#bib.bib8); T. Donlon et al., [2025](https://arxiv.org/html/2605.06659v1#bib.bib7)) or test a theory-specific model. We assume a local vector relation ${\mathbf{g}}_{\mathrm{obs}} = {\nu\hspace{0pt}{({|{\mathbf{g}}_{\mathrm{bar}}|})}\hspace{0pt}{\mathbf{g}}_{\mathrm{bar}}}$ which we project onto the Sun–pulsar sightline. This tests whether pulsar timing, one of very few non-rotation-curve acceleration probes, is already informative about this striking relation.

## II Data and model

We use the v3 catalogue of T. Donlon et al. ([2025](https://arxiv.org/html/2605.06659v1#bib.bib7)), which has 26 independent LOS accelerations inferred from orbital-period derivatives of pulsars in binary systems after Shklovskii and relativistic corrections. The catalogue also contains a sample of spin-only millisecond-pulsar accelerations (inferred with empirical magnetic-braking corrections). However we did not find that sample informative for our test due to the larger uncertainties, and so we report results for the binary sample only.

We compute the baryonic field from an analytic approximation to the photometric Milky Way census of J. Bland-Hawthorn & O. Gerhard ([2016](https://arxiv.org/html/2605.06659v1#bib.bib2)). We represent their thin disc, thick disc, cold gas and bulge/inner-disc components by three Miyamoto–Nagai discs with $(M,a,b)=(3.5\times 10^{10},2.6,0.3)$, $(6\times 10^{9},2.0,0.9)$ and $(1.0\times 10^{10},4.5,0.08)$, denoting mass and radial/vertical scale lengths in $M_{\odot}$ and kpc, plus a Hernquist bulge with mass $1.5\times 10^{10}M_{\odot}$ and scale radius $0.6\,{\rm kpc}$. The gas disc normalisation reproduces their quoted local gas surface density, $\Sigma_{g}(R_{0})\simeq 13\,M_{\odot}{\rm pc}^{-2}$. Observed pulsar positions are transformed to Galactocentric coordinates using $R_{0}=8.20\pm 0.09\,{\rm kpc}$ (P. J. McMillan, [2017](https://arxiv.org/html/2605.06659v1#bib.bib14)) and $z_{\odot}=20.8\,{\rm pc}$ (M. Bennett & J. Bovy, [2019](https://arxiv.org/html/2605.06659v1#bib.bib1)). Distance uncertainties are propagated approximately by re-evaluating the field at $d+\sigma_{d}$ and $d-\sigma_{d}$ and taking half the difference.

Pulsar timing measures the differential LOS acceleration of the pulsar relative to the Sun,

$$
\begin{aligned}
{a_{\mathrm{LOS}}^{\mathrm{diff}} = {{({{\mathbf{g}}_{\mathrm{psr}} - {\mathbf{g}}_{\odot}})} \cdot \hat{\mathbf{ℓ}}}},
\end{aligned}\tag{1}
$$

where ${\mathbf{g}}_{\mathrm{psr}}$ and ${\mathbf{g}}_{\odot}$ are Galactocentric accelerations and $\hat{\mathbf{ℓ}}$ points from the Sun to the pulsar. Timing gives no information on components orthogonal to the Sun–pulsar sightline. We therefore compute $a_{\rm LOS}^{\rm obs}$, the pulsar’s Galactocentric acceleration projected onto the Sun–pulsar sightline:

$$
\begin{aligned}
{a_{\mathrm{LOS}}^{\mathrm{obs}} = {a_{\mathrm{LOS}}^{\mathrm{diff}} + {{\mathbf{g}}_{\odot} \cdot \hat{\mathbf{ℓ}}}} = {{\mathbf{g}}_{\mathrm{psr}} \cdot \hat{\mathbf{ℓ}}}}.
\end{aligned}\tag{2}
$$

We adopt the Solar acceleration from P. J. McMillan ([2017](https://arxiv.org/html/2605.06659v1#bib.bib14)) $a_{\odot,R}=-v_{0}^{2}/R_{0}=-2.15\times 10^{-10}\,{\rm m\,s}^{-2}$ (corresponding to circular velocity $v_{0}=233.1\pm 3.0\,{\rm km\,s}^{-1}$). The vertical Solar acceleration is evaluated from the baryonic model and is 1.7% of the centripetal term. As our primary output we plot $a_{\mathrm{LOS}}^{\mathrm{obs}}/{({{\mathbf{g}}_{\mathrm{bar}} \cdot \hat{\mathbf{ℓ}}})}$, the ratio of the observed to baryonic Galactocentric accelerations projected along the line of sight.

The vector RAR prediction for $a_{\rm LOS}^{\rm obs}$ is

$$
\begin{aligned}
{a_{\mathrm{LOS},i}^{\mathrm{pred}} = {\nu\hspace{0pt}{({|{\mathbf{g}}_{\mathrm{bar},i}|})}\hspace{0pt}{({{\mathbf{g}}_{\mathrm{bar},i} \cdot {\hat{\mathbf{ℓ}}}_{i}})}}},
\end{aligned}\tag{3}
$$

with $\nu=1$ for Newtonian baryon-only gravity. We adopt the Simple interpolating function as constrained by galaxy dynamics in H. Desmond ([2023b](https://arxiv.org/html/2605.06659v1#bib.bib6)),

$$
\begin{aligned}
\nu(x)=\frac{1}{2}+\sqrt{\frac{1}{4}+\frac{a_{0}}{x}},\quad a_{0}=1.19\times 10^{-10}\,{\rm m\,s}^{-2}.
\end{aligned}\tag{4}
$$

We compare observed and predicted accelerations with $\chi^{2}_{\rm LOS}=\sum_{i}(a_{{\rm LOS},i}^{\rm obs}-a_{{\rm LOS},i}^{\rm pred})^{2}/\sigma_{i}^{2}$, where $\sigma_{i}$ includes timing, Solar-correction, and distance-propagated baryonic-field uncertainties.

Converting the pulsar differential timing acceleration to a Galactocentric acceleration requires combining it with the empirical Solar centripetal acceleration. With the present sample, the median Solar acceleration fraction, $f_{\odot}\equiv|a_{\odot,\rm LOS}|/(|a_{\rm LOS}^{\rm diff}|+|a_{\odot,\rm LOS}|)$, is 0.73 for the binary sample. We therefore additionally conduct a Solar-acceleration-only test ($a_{\rm LOS}^{\rm diff}=0$) to isolate the effect of the pulsar-specific accelerations.

## III Results and discussion

![Figure 1](https://arxiv.org/html/2605.06659v1/x1.png)

**Figure 1.** (a) Galactocentric positions of the binary pulsar sample (circles). (b) Boost ratio $a_{\mathrm{LOS}}^{\mathrm{obs}}/{({{\mathbf{g}}_{\mathrm{bar}} \cdot \hat{\mathbf{ℓ}}})}$ versus $|{\mathbf{g}}_{\mathrm{bar}}|$. The red curve is the Simple RAR fit to galaxy rotation curves of H. Desmond ([2023a](https://arxiv.org/html/2605.06659v1#bib.bib5)) and the grey line is Newtonian. Points are coloured by the fraction of acceleration magnitude that is from the Solar acceleration. The cyan error bars show inverse-variance-weighted means in equally spaced bins in $\log_{10}g_{\rm bar}$ (only bins with two or more pulsars are shown). The black crosses show the Solar-only bin means (i.e. setting the measured differential acceleration to zero), offset horizontally for visual clarity. Triangles mark points clipped beyond the plotting range.

For the binary sample, the projected RAR gives $\chi^{2}_{\rm LOS}/N=3.58$ (for $N=26$ binaries), compared with 10.86 for Newtonian baryonic gravity. Neither value gives a satisfactory absolute goodness of fit, but the projected RAR is substantially closer to the data. The plot in [fig. 1](https://arxiv.org/html/2605.06659v1#S3.F1) shows this in ratio form, but the scatter is large and the sampled range in $|{\mathbf{g}}_{\mathrm{bar}}|$ is only about 0.8 dex around $a_{0}$. These data therefore cannot distinguish non-radial RAR extensions or theory-specific Galactic acceleration fields. The Solar-only null (setting $a_{\rm LOS}^{\rm diff}=0$ while retaining each sightline’s Solar projection) gives $\chi^{2}_{\rm LOS}/N=3.75$, close to the real binary value. This shows that the result is determined in large part by the Solar acceleration rather than by the pulsar-specific differential accelerations. Using the Milky Way baryonic potential of P. J. McMillan ([2017](https://arxiv.org/html/2605.06659v1#bib.bib14)) instead gives $\chi^{2}/N=3.94$ for the projected RAR, 10.74 for Newtonian baryons, and 4.16 for the Solar-only comparison, demonstrating qualitative insensitivity to this systematic.

In conclusion, pulsar timing offers a direct probe of acceleration-based scaling relations, but the current binary sample is not yet significantly more informative than the Solar acceleration contribution alone. More precise binary acceleration measurements, larger samples, improved distances, and sightlines for which the Solar acceleration is a smaller fraction of the Galactocentric acceleration are required for more informative tests. The most useful future objects will be binary pulsars at lower $|{\mathbf{g}}_{\mathrm{bar}}|$, larger $|z|$, or Galactic longitudes for which the Solar centripetal acceleration projects weakly onto the Sun–pulsar sightline.

## References (20 total, showing 20)

- M. Bennett & J. Bovy (2019) Bennett, M., & Bovy, J. 2019,, MNRAS, 482, 1417, doi: [10.1093/mnras/sty2813](http://doi.org/10.1093/mnras/sty2813)

- J. Bland-Hawthorn & O. Gerhard (2016) Bland-Hawthorn, J., & Gerhard, O. 2016, The Galaxy in Context: Structural, Kinematic, and Integrated Properties, ARA&A, 54, 529, doi: [10.1146/annurev-astro-081915-023441](http://doi.org/10.1146/annurev-astro-081915-023441)

- M. M. Brouwer et al. (2021) Brouwer, M. M., Oman, K. A., Valentijn, E. A., et al. 2021,, A&A, 650, A113, doi: [10.1051/0004-6361/202040108](http://doi.org/10.1051/0004-6361/202040108)

- S. Chakrabarti et al. (2021) Chakrabarti, S., Chang, P., Lam, M. T., Vigeland, S. J., & Quillen, A. C. 2021, A Measurement of the Galactic Plane Mass Density from Binary Pulsar Accelerations, ApJ, 907, L26, doi: [10.3847/2041-8213/abd635](http://doi.org/10.3847/2041-8213/abd635)

- H. Desmond (2023a) Desmond, H. 2023a,, MNRAS, 526, 3342, doi: [10.1093/mnras/stad2762](http://doi.org/10.1093/mnras/stad2762)

- H. Desmond (2023b) Desmond, H. 2023b,, MNRAS, 521, 1817, doi: [10.1093/mnras/stad597](http://doi.org/10.1093/mnras/stad597)

- T. Donlon et al. (2025) Donlon, T., Chakrabarti, S., Vanderwaal, S., et al. 2025,, Phys. Rev. D, 111, 103036, doi: [10.1103/PhysRevD.111.103036](http://doi.org/10.1103/PhysRevD.111.103036)

- T. I. Donlon et al. (2024) Donlon, T. I., Chakrabarti, S., Widrow, L. M., et al. 2024, Galactic structure from binary pulsar accelerations: Beyond smooth models, Phys. Rev. D, 110, 023026, doi: [10.1103/PhysRevD.110.023026](http://doi.org/10.1103/PhysRevD.110.023026)

- B. Famaey & S. S. McGaugh (2012) Famaey, B., & McGaugh, S. S. 2012,, Living Reviews in Relativity, 15, 10, doi: [10.12942/lrr-2012-10](http://doi.org/10.12942/lrr-2012-10)

- J. Freundlich et al. (2022) Freundlich, J., Famaey, B., Oria, P.-A., et al. 2022,, A&A, 658, A26, doi: [10.1051/0004-6361/202142060](http://doi.org/10.1051/0004-6361/202142060)

- M. P. Júlio et al. (2025) Júlio, M. P., Read, J. I., Pawlowski, M. S., et al. 2025,, A&A, 704, A330, doi: [10.1051/0004-6361/202557106](http://doi.org/10.1051/0004-6361/202557106)

- F. Lelli et al. (2017) Lelli, F., McGaugh, S. S., Schombert, J. M., & Pawlowski, M. S. 2017, One Law to Rule Them All: The Radial Acceleration Relation of Galaxies, ApJ, 836, 152, doi: [10.3847/1538-4357/836/2/152](http://doi.org/10.3847/1538-4357/836/2/152)

- S. S. McGaugh et al. (2016) McGaugh, S. S., Lelli, F., & Schombert, J. M. 2016,, Physical Review Letters, 117, 201101, doi: [10.1103/PhysRevLett.117.201101](http://doi.org/10.1103/PhysRevLett.117.201101)

- P. J. McMillan (2017) McMillan, P. J. 2017,, MNRAS, 465, 76, doi: [10.1093/mnras/stw2759](http://doi.org/10.1093/mnras/stw2759)

- T. Mistele et al. (2024) Mistele, T., McGaugh, S., Lelli, F., Schombert, J., & Li, P. 2024,, Journal of Cosmology and Astroparticle Physics, 2024, 020, doi: [10.1088/1475-7516/2024/04/020](http://doi.org/10.1088/1475-7516/2024/04/020)

- A. Moran et al. (2024) Moran, A., Mingarelli, C. M. F., Van Tilburg, K., & Good, D. 2024, Pulsar-based map of galactic acceleration, Phys. Rev. D, 109, 123015, doi: [10.1103/PhysRevD.109.123015](http://doi.org/10.1103/PhysRevD.109.123015)

- A. Paranjape & R. K. Sheth (2021) Paranjape, A., & Sheth, R. K. 2021,, MNRAS, 507, 632, doi: [10.1093/mnras/stab2141](http://doi.org/10.1093/mnras/stab2141)

- D. F. Phillips et al. (2021) Phillips, D. F., Ravi, A., Ebadi, R., & Walsworth, R. L. 2021, Milky Way Accelerometry via Millisecond Pulsar Timing, Phys. Rev. Lett., 126, 141103, doi: [10.1103/PhysRevLett.126.141103](http://doi.org/10.1103/PhysRevLett.126.141103)

- R. Stiskalek & H. Desmond (2023) Stiskalek, R., & Desmond, H. 2023,, MNRAS, 525, 6130, doi: [10.1093/mnras/stad2675](http://doi.org/10.1093/mnras/stad2675)

- A. A. Vărăşteanu et al. (2025) Vărăşteanu, A. A., Jarvis, M. J., Ponomareva, A. A., et al. 2025, MIGHTEE-HI: the radial acceleration relation with resolved stellar mass measurements, MNRAS, 541, 2366, doi: [10.1093/mnras/staf1079](http://doi.org/10.1093/mnras/staf1079)
