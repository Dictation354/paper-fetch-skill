---
title: "Machine-learned atomic cluster expansion potentials for fast and quantum-accurate thermal simulations of wurtzite AlN"
authors: "Yang, Guang, Liu, Yuan-Bin, Yang, Lei, Cao, Bing-Yang"
doi: "10.1063/5.0188905"
source: "aip_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 11711
---

# Machine-learned atomic cluster expansion potentials for fast and quantum-accurate thermal simulations of wurtzite AlN

## Abstract

Thermal transport in wurtzite aluminum nitride (<em>w-</em>AlN) significantly affects the performance and reliability of corresponding electronic devices, particularly when lattice strains inevitably impact the thermal properties of *w*-AlN in practical applications. To accurately model the thermal properties of <em>w-</em>AlN with high efficiency, we develop a machine learning interatomic potential based on the atomic cluster expansion (ACE) framework. The predictive power of the ACE potential against density functional theory (DFT) is demonstrated across a broad range of properties of *w*-AlN, including ground-state lattice parameters, specific heat capacity, coefficients of thermal expansion, bulk modulus, and harmonic phonon dispersions. Validation of lattice thermal conductivity is further carried out by comparing the ACE-predicted values to the DFT calculations and experiments, exhibiting the overall capability of our ACE potential in sufficiently describing anharmonic phonon interactions. As a practical application, we perform a lattice dynamics analysis using the potential to unravel the effects of biaxial strains on thermal conductivity and phonon properties of <em>w-</em>AlN, which is identified as a significant tuning factor for near-junction thermal design of <em>w-</em>AlN-based electronics.

## I. INTRODUCTION

Wurtzite aluminum nitride (<em>w-</em>AlN) emerges as a promising semiconductor, distinguished by various exceptional characteristics. These include an ultrawide bandgap<sup>1–3</sup> (∼6.1 eV), a large critical electric field<sup>1,3</sup> (∼15 MV/cm), a high sound velocity[<sup>4</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c4) (∼11 km/s), large piezoelectric coefficients,[<sup>5</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c5) a relatively high thermal conductivity<sup>6,7</sup> (⁠ $\kappa \sim 300\hspace{0.1em}{\mathrm{W}/\mathrm{m}}\hspace{0.1em}\mathrm{K}$⁠), and a lattice similar to other semiconductors such as <em>w-</em>GaN. The large critical electric field stemming from the ultrawide bandgap results in Baliga's figure of merit (FOM) and Johnson's FOM of <em>w-</em>AlN significantly surpassing those of <em>w-</em>GaN or *β*-Ga<sub>2</sub>O<sub>3</sub>,<sup>1,3</sup> thereby establishing <em>w-</em>AlN as a remarkable candidate for novel high-power or radio frequency (RF) electronics.<sup>8,9</sup> Meanwhile, the ultrawide bandgap of <em>w-</em>AlN facilitates developments in deep-ultraviolet photonics.<sup>3,8,10,11</sup> The high sound velocity and piezoelectric performance render <em>w-</em>AlN suitable for fabricating microelectromechanical system (MEMS)-based resonators and filters, which are extensively applied in 5G communications.<sup>12–15</sup> In addition, the thermal conductivity of <em>w-</em>AlN is considered satisfactory; hence, <em>w-</em>AlN sometimes serves as high-*κ* substrates for high-power devices to improve the heat dissipation performance.<sup>9,16,17</sup> As depicted in [Fig. 1](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f1), the bandgap and thermal conductivity of <em>w-</em>AlN are compared to other representative materials,[<sup>2</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c2) further exhibiting the significant promise of <em>w-</em>AlN.

![Figure 1](https://aipp.silverchair-cdn.com/aipp/content_public/journal/jap/135/8/10.1063_5.0188905/2/m_085105_1_5.0188905.figures.online.f1.jpeg?Expires=1782155914&Signature=aOHf8P-SD50tlqITjEP1nfqgwtyOu4HSWm-dDsvK9ofPY1nMsmWECK~PmLUNlCb6c~oHvlp-vOEE-U9K98SrK10-NtVJ5fodVLHjppbttAhLS5dV0ezchNMZ10nCH~BB~g3wNOskHoDrKDdiy3p20caM-YR~lciv9jiamGDy0J1LZUJFOpJv8UA8PqPF7BdLaFqwoH-RibSzsv4eXdlMehKWC4XhCtYDSg7YtwbKtgWyhn1I4SQT1emy-vN~NnyFzOmCLW8xj6yzc8zIn9mKeCdf8RVlezlT1R6SxfZsG9BUciNp1HC~l~dkgyUadoJQxBU9aqj-16plZwbW8W4ABQ__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 1.** Room temperature thermal conductivities of different materials vs their electronic bandgaps, including amorphous materials (e.g., *a*-Si, *a*-Ga<sub>2</sub>O<sub>3</sub>), polycrystals (poly-Si), metals (Cu), and nonmetallic crystals (e.g., *w*-AlN, *w*-GaN). For the data, refer to the literature.<sup>2,3,18–21</sup> This plot reveals that *w*-AlN lies in the range of promising comprehensive performance (high thermal conductivity and ultrawide bandgap). Note that the average thermal conductivities are chosen for anisotropic materials (e.g., *β*-Ga<sub>2</sub>O<sub>3</sub>, *r*-TiO<sub>2</sub>).

Though the inherent characteristics of <em>w-</em>AlN are excellent, further studies on its properties remain necessary for developing next-generation electronics, especially in the aspects of (i) clarifying how the complex environment affects the physical properties, (ii) tuning the physical properties on demand, and (iii) analyzing the growth processes. One specific issue of interest pertains to the effects of lattice strains on the thermal properties of <em>w-</em>AlN. Since <em>w-</em>AlN is extensively used as the nucleation layer within the GaN high electron mobility transistors (HEMTs) to buffer lattice mismatch between <em>w-</em>GaN epilayers and substrates,<sup>22–25</sup> the residual stress within AlN is inevitable. However, the correlations between lattice strains with the thermal conductivity and phonon bands of <em>w-</em>AlN remain vague, which may affect the heat dissipation and reliability of corresponding devices.<sup>26,27</sup>

In addition to experimental approaches, atomistic simulations act as another avenue for gaining insights into the physical properties of novel materials,[<sup>28</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c28) which is traditionally represented by two techniques,[<sup>29</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c29) i.e., the first-principle calculations based on density functional theory (DFT) and the molecular dynamics (MD) simulations based on empirical potentials. Nevertheless, high computational cost limits the DFT methods for modeling transport properties, while the MD simulations based on simple empirical potentials are less accurate than DFT.[<sup>30</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c30) For <em>w-</em>AlN, several empirical potentials have been proposed, including the Stillinger–Weber (S–W),[<sup>31</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c31) Tersoff,[<sup>32</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c32) Vashishta,[<sup>33</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c33) and COMB3[<sup>34</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c34) models. However, each empirical potential generates divergent lattice parameters or phonon dispersions from those of DFT.<sup>33–35</sup> When predicting thermal conductivity, it is fundamental to accurately describe both harmonic and anharmonic interactions of phonons.<sup>36–38</sup> This places a heightened demand on the accuracy of interatomic potentials for <em>w-</em>AlN.

In recent years, machine learning (ML) interatomic potentials have attracted significant attention by effectively balancing computational efficiency with accuracy. A wealth of literature has shown that a well-built ML potential trained with the DFT reference data can provide an unbiased representation of potential energy surfaces and simultaneously exhibit strong transferability.<sup>36,39,40</sup> More importantly, the linear behavior in the computational cost of ML potentials enables them with much higher efficiency and scalability than DFT methods. Until now, several ML potential models have been proposed, such as the neural network potential (NNP),<sup>41,42</sup> Gaussian approximation potential (GAP),<sup>40,43,44</sup> spectral neighbor analysis potential (SNAP),<sup>45,46</sup> deep potential (DP),<sup>47,48</sup> moment tensor potential (MTP),<sup>49,50</sup> atomic cluster expansion (ACE) potential,<sup>51,52</sup> neural equivariant interatomic potential (NequIP),[<sup>53</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c53) Allegro,[<sup>54</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c54) and MACE.<sup>55,56</sup> The ACE potential is one of the most computationally efficient and quantum-accurate models available[<sup>52</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c52) and is also suitable for performing large-scale simulations on CPU platforms. Hence, ACE is chosen in this work.

Here, we introduce a machine-learned ACE potential<sup>51,52,57</sup> for <em>w-</em>AlN, aiming to facilitate the atomistic simulations of its thermal properties and gain insights into how tuning factors (such as lattice strains) influencing the phonon pictures. The remainder of this paper is organized as follows. In Sec. [II](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#88135718), we concisely introduce the ACE methodology and the construction of the training database for <em>w-</em>AlN. In Sec. [III](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#88135727), we comprehensively demonstrate the accuracy of our ACE potential in predicting various thermal and mechanical properties of <em>w-</em>AlN by comparison with either DFT calculations or experiments. Then, our ACE potential is applied to unravel the correlations between thermal conductivities and biaxial strains of <em>w-</em>AlN. Essential conclusions of this study are presented in Sec. [IV](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#88135758).

## II. METHODS

### A. Atomic cluster expansion framework

In line with other common ML potentials, the ACE model also expresses the total energy of a given system as the sum of site energies,

**Equation 1.**

$$
\begin{matrix} {E = \sum\limits_{i}\varepsilon_{i},} \end{matrix}
$$

in which each $\varepsilon_{i}$ depends on its local atomic environment within a given cutoff radius $r_{\mathrm{cut}}$⁠. Different from other many two-, three-, and many-body descriptors that are not strictly complete, the ACE framework provides an efficient representation of local atomic environments by means of a complete linear basis of body-ordered symmetric polynomials.<sup>51,52,57</sup>

Specifically, atomic energy contribution $\varepsilon_{i}$ in the ACE model is represented as

**Equation 2.**

$$
\begin{matrix} {\varepsilon_{i} = F({\varphi_{i}^{(1)},\ldots,\varphi_{i}^{(p)}}),} \end{matrix}
$$

where *F* is a generalized nonlinear function to be supplied and $\varphi_{i}^{(p)}$ is the fundamental building block of ACE, which is expanded by body-ordered functions within the set of neighbors for each atom *i*,

**Equation 3.**

$$
\begin{matrix} {\varphi_{i}^{(p)} = \sum\limits_{\boldsymbol{z}\boldsymbol{n}\boldsymbol{l}\boldsymbol{m}}{\overset{\sim }{\boldsymbol{c}}}_{z_{i}{\boldsymbol{z}\boldsymbol{n}\boldsymbol{l}\boldsymbol{m}}}^{(p)}\boldsymbol{A}_{i{\boldsymbol{z}\boldsymbol{n}\boldsymbol{l}\boldsymbol{m}}}.} \end{matrix}
$$

${\overset{\sim }{\boldsymbol{c}}}_{z_{i}{\boldsymbol{z}\boldsymbol{n}\boldsymbol{l}\boldsymbol{m}}}^{(p)}$ denotes expansion coefficients and vectors $\boldsymbol{z}$⁠, $\boldsymbol{n}$⁠, $\boldsymbol{l}$⁠, and $\boldsymbol{m}$ contain atomic species, indices for radial functions, and indices for spherical harmonics, respectively. The permutation-invariant many-body basis functions $\boldsymbol{A}_{i{\boldsymbol{z}\boldsymbol{n}\boldsymbol{l}\boldsymbol{m}}}$ are represented as

**Equation 4.**

$$
\begin{matrix} {\boldsymbol{A}_{i{\boldsymbol{z}\boldsymbol{n}\boldsymbol{l}\boldsymbol{m}}} = \prod\limits_{t = 1}^{v}A_{iz_{t}n_{t}l_{t}m_{t}},} \end{matrix}
$$

where the order of the product *v* determines the body order of a basis function. Meanwhile, the atomic base $A_{iz_{t}n_{t}l_{t}m_{t}}$ is given as

**Equation 5.**

$$
\begin{matrix} {A_{iz_{t}n_{t}l_{t}m_{t}} = \sum\limits_{j}\delta_{zz_{j}}\phi_{z_{i}z_{j}nlm}(\boldsymbol{r}_{ij}),} \end{matrix}
$$

in which $\boldsymbol{r}_{ij}$ is the relative position of neighbor atoms, and the one-particle basis $\phi_{z_{i}z_{j}nlm}$ consists of spherical harmonics functions $g_{nl}^{z_{i}z_{j}}$ and radial functions $Y_{lm}^{z_{i}z_{j}}$⁠,

**Equation 6.**

$$
\begin{matrix} {\phi_{z_{i}z_{j}nlm} = g_{nl}^{z_{i}z_{j}}Y_{lm}^{z_{i}z_{j}}.} \end{matrix}
$$

It is noteworthy that the expansion coefficients ${\overset{\sim }{\boldsymbol{c}}}_{z_{i}{\boldsymbol{z}\boldsymbol{n}\boldsymbol{l}\boldsymbol{m}}}^{(p)}$ in Eq. [(3)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#jumplink-d3) cannot be directly used for model fitting because the many-body basis functions $\boldsymbol{A}$ do not satisfy rotational symmetries. By utilizing generalized Clebsch–Gordan coefficients to couple the elements of the basis function $\boldsymbol{A}$⁠, an invariant basis function $\boldsymbol{B}$ is obtained, $\boldsymbol{B} = {\boldsymbol{C}\boldsymbol{A}}$⁠. Consequently, a linear model invariant to translation, rotation, and permutation of like atoms can be written for the site energy of ACE,

**Equation 7.**

$$
\begin{matrix} {\varphi_{i} = \boldsymbol{c}^{T}B.} \end{matrix}
$$

The coefficients $\boldsymbol{c}$ are free model parameters that can be optimized during fitting. Further information about the ACE architecture can be found in the literature.<sup>51,52,57</sup> In this work, we employ the software package Pacemaker[<sup>58</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c58) for the parametrization of the ACE potential. The final ACE model associated with the detailed hyperparameters is freely available in the [supplementary material](https://doi.org/10.60893/figshare.jap.c.7048016).

### B. Construction of the training database

Structures in the training database are obtained from MD trajectories. Here, the empirical S-W potential[<sup>31</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c31) is adopted to carry out the MD simulations. This approach allows for sampling over extended time scales (∼ns) to ensure structural diversity, while it bypasses the computationally intensive *ab initio* MD and makes the sampling more efficient. In detail, the initial structure consists of a 3 × 3 × 3 supercell containing 108 atoms. The cell is then expanded or compressed with a scaling factor ranging from 0.95 to 1.05 on each lattice constant. Next, a series of MD simulations for each cell are performed with the canonical (NVT) ensemble at temperatures of 100, 500, and 1000 K. For each temperature, a 1-ns trajectory is produced, from which structures are sampled at uncorrelated intervals of 150 ps. Finally, a total of 13 608 local atomic environments are collected from all 21 MD trajectories.

All generated structures are subsequently subjected to single-point DFT calculations to obtain well-converged reference energies and forces for training. The DFT calculations are performed with the Vienna *ab initio* simulation package (VASP).[<sup>59</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c59) Exchange and correlation are treated by using the PBEsol functional[<sup>60</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c60) with a projector-augmented wave method.[<sup>61</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c61) Moreover, we adopt Gaussian smearing of 0.05 eV width to electronic levels, a 600-eV cutoff for plane wave expansions, and a maximum spacing of 0.2 Å<sup>−1</sup> for meshing the reciprocal space. The total energy is attained with a convergence criterion of less than 10<sup>−6</sup> eV in the self-consistent electronic iterations.

## III. RESULTS AND DISCUSSION

### A. Performance of the ACE potential for wurtzite AlN

The accuracy of our ACE potential is validated through a comparison with DFT-predicted energies and forces. The training and testing datasets comprise 36 612 and 4212 atomistic force components, respectively. In [Fig. 2](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f2), we present a comparison of the total energies and atomic forces predicted by our potential with those derived from DFT. Notably, our ACE potential effectively reproduces the total energies, showcasing a remarkably low root-mean-squared error (RMSE) of 0.13 meV/atom for the testing datasets. Furthermore, the interatomic forces in the testing datasets are accurately predicted, with a relatively low RMSE of 5.01 meV/Å. The accuracy of both energy and force predictions achieved with our ACE potential is comparable to those of other reported works,<sup>40,43,52,62,63</sup> which demonstrates that our ACE potential serves as a robust representative of the DFT potential energy surface.

![Figure 2](https://aipp.silverchair-cdn.com/aipp/content_public/journal/jap/135/8/10.1063_5.0188905/2/m_085105_1_5.0188905.figures.online.f2.jpeg?Expires=1782155914&Signature=NTREgSB8FxUuQHwwxf6uMp2FZv75QO0uZgtZtkHQRw1VfdEYgO8oCMLJB4eilWVd6XLcJe4LMag~MB9oI7PVuALciyjpXQc-TnWM8Cyb3kI1P1XD05rYH6nC3GPXdaMorjJuath8Wz~Mq8a1puit2MhYV2ehUmQ9eJYZ2fk7kTcHPR9OFufsNzvhk7QZA0RpELHfTaIijy8KtY0FrqN04UkpNu2h6Wj5aKBSIeVm6Uw-Bs43m0W10augvB9Zq7pP1ot9PMFRAspX~d4BPx0lEHYuqntm9IGHFCF430sRj58e-5vsB9ChoAQ8Qh1SyJKBlMENt0UfLMPAC5gCAB5xuw__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 2.** Comparison of DFT-computed and ACE-predicted (a) total energies and (b) interatomic forces for <em>w-</em>AlN. Here, “Error” represents the absolute error.

Then, we assess the capability of our ACE potential to model the physical properties of *w*-AlN. Our evaluation begins by employing the ACE to predict lattice parameters, a fundamental property that significantly influences various intrinsic characteristics of a material. The lattice parameters produced by our ACE potential are as follows: $a = b = 3.115\hspace{0.1em}58\hspace{0.1em}\text{Å}$⁠, $c = 4.985\hspace{0.1em}13\hspace{0.1em}\text{Å}$⁠, and $\gamma = 120^{\circ}$⁠. These values are in excellent agreement with both our DFT calculations and experimental results[<sup>64</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c64) ([Table I](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#t1)). For comparison, lattice parameters are also predicted using the S-W potential[<sup>31</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c31) here as well as using the Tersoff potential elsewhere.[<sup>35</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c35) However, it is noteworthy that the relative errors in these predictions are considerably larger than those obtained with ACE.

**TABLE I.** Comparison of the lattice parameters of <em>w-</em>AlN determined by different methods.

| Method                                                                                                                                         | Lattice parameter / ${a/b}(\text{Å})$ | Lattice parameter / $c(\text{Å})$ | Lattice parameter / <strong><em>γ</em></strong> (deg) | Max relative error against Expt. (%) |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | --------------------------------- | ----------------------------------------------------- | ------------------------------------ |
| ACE potential relaxation                                                                                                                       | 3.115 58                              | 4.981 53                          | 120                                                   | 0.116                                |
| SW potential[<sup>31</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c31) relaxation | 3.080 02                              | 5.029 65                          | 120                                                   | 1.027                                |
| DFT relaxation (PBEsol)                                                                                                                        | 3.112 88                              | 4.982 47                          | 120                                                   | 0.032                                |
| Experiment[<sup>64</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c64)              | 3.111 97                              | 4.980 89                          | 120                                                   | 0                                    |

The ACE potential is subsequently employed to predict the volumetric specific heat capacity (⁠ $C_{\mathrm{V}}$⁠), coefficients of thermal expansion, and the bulk modulus of *w*-AlN. $C_{\mathrm{V}}$ is calculated using the Phonopy package<sup>65–67</sup>. [Figure 3(a)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f3) summarizes the $C_{\mathrm{V}}$ obtained from our ACE potential, the DFT calculations, and the experimental measurements.[<sup>68</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c68) Obviously, the data generated by our ACE potential exhibit strong agreement with both DFT and experiments.

![Figure 3](https://aipp.silverchair-cdn.com/aipp/content_public/journal/jap/135/8/10.1063_5.0188905/2/m_085105_1_5.0188905.figures.online.f3.jpeg?Expires=1782155914&Signature=x4Ru-Q6nMBsB~4rkT-URu5e2RwOAScZIIhgF0E6-0JRUNm1ClQDEGf70tR8n1-gT5mduQz01Y4PXSN0TRm7hy2Hm0d4baOqV7w-dhTPwRGoscxyXCche7JbZ1vNf6E7n7cP6CV5tFuw76jylp9XaCoeLjMWMEgK78S6Sgy7GXFUomB1JrwRqMMAucCvYonGpns1lce2G0HCNbsv9OWTXqg6j1rK2ZtNtAGYT6oM6FvaHTo-cm7xvPReHb75WD7iqPenp35QDMM~xfj4hTcJ-QATkLuk2RC8oE18PDXlDCo1fnC2L8N3C77savmLmXXpW3nCZL-5XucVeFRt8GTTH9w__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 3.** Temperature-dependent (a) specific heat capacity, (b) thermal expansion coefficients, and (c) bulk modulus of <em>w-</em>AlN. (d) Phonon dispersion and phonon density of states (DOS) of <em>w-</em>AlN at 0 K predicted by DFT and the ACE potential.

Thermal expansion of *w*-AlN holds significant importance in practical applications, particularly when *w*-AlN is utilized as transition layers in III-V electronics, such as GaN HEMTs.<sup>22,23,25</sup> This property determines heteroepitaxial strains arising from the thermal mismatches during growth processes.[<sup>22</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c22) The coefficient of thermal expansion (CTE, denoted by $\alpha_{\mathrm{E}}$⁠) is defined as

**Equation 8.**

$$
\begin{matrix} {\alpha_{\mathrm{E}} = {\frac{1}{V_{T}}{\frac{\mathrm{∂}V_{T}}{\mathrm{∂}T},}}} \end{matrix}
$$

where *V* denotes the volume of the AlN unit cell and *T* represents the temperature. The CTEs are calculated under the quasi-harmonic approximation[<sup>65</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c65) (QHA) implemented with Phonopy. As shown in [Fig. 3(b)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f3), the ACE potential quantitatively reproduces the thermal expansion determined by DFT calculations. Both ACE and DFT predict that the CTEs are strongly dependent on temperatures between 0 and 1000 K. It is evident that as the temperature increases, the CTEs exhibit rapid growth up to ∼300 K, after which the slopes decrease at higher temperatures.

Moreover, a mechanical property, namely, the bulk modulus (⁠ $B_{\mathrm{T}}$⁠) of <em>w-</em>AlN, is also determined by the ACE potential. As shown in [Fig. 3(c)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f3), the ACE potential quantitatively reproduces the $B_{\mathrm{T}}$ as DFT calculations. Both ACE and DFT predict a subtle decrease in the modulus as the temperature increases from 0 to 1000 K. In summary, it is obvious that our ACE potential is capable of accurately describing both thermal and mechanical properties.

The prediction of the phonon dispersions of a material is another crucial metric for the quality of a potential to describe lattice dynamics. We first calculate the second-order harmonic and third-order anharmonic interatomic force constants (IFCs) through the finite displacement method.[<sup>69</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c69) By combining the Phonopy package with the second-order IFCs calculated from our ACE and DFT, the phonon dispersions of <em>w-</em>AlN at 0 K are determined, as illustrated in [Fig. 3(d)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f3). As a characteristic of the ionic crystal, the splitting of LO–TO phonons at the Γ-point is observed, which is attributed to the long-range Coulomb interactions.[<sup>36</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c36) Since our ACE model does not encompass the Coulomb interactions, we have incorporated the non-analytical correction[<sup>26</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c26) into the dynamical matrix to resolve the splitting of LO–TO phonons at the Γ point. Our results show that the ACE model accurately predicts the phonon frequencies at almost of all high-symmetry points and accurately captures the dispersion behavior of each phonon branch. Meanwhile, the phonon density of states (DOSs) calculated by ACE is almost identical to the DFT results.

In fact, although the absence of Coulomb terms introduces some errors in force calculations, it will be shown later that the accuracy of our potential remains sufficiently high to yield thermal conductivity predictions. If the long-range Coulomb interactions become crucial for other calculations, we will properly incorporate the Coulomb interactions with fixed partial charges before fitting the ACE model. This adjustment will automatically resolve the LO–TO splitting issue and improve the accuracy of force calculations.[<sup>36</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c36) Similar treatments for GaN can be found in the literature.[<sup>43</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c43)

### B. Thermal conductivity of wurtzite AlN

Herein, we utilize the second- and third-order IFCs to predict the thermal conductivity (⁠ $\kappa$⁠) of <em>w-</em>AlN. The Wigner transport equation (WTE)<sup>70–72</sup> is solved by the direct solution in Phono3py<sup>66,73,74</sup> package, with a 25 × 25 × 25 mesh for sampling the first Brillouin zone over temperatures within 100–600 K. Due to its wurtzite lattice, it is expected that the thermal conductivities of <em>w-</em>AlN exhibit approximate isotropy along both in-plane and cross-plane directions.[<sup>27</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c27)

We also conduct ShengBTE[<sup>75</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c75) calculations including the four-phonon processes (4ph)[<sup>76</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c76) for comparison with the WTE. Since the computational cost is extremely huge with 4ph involved, we resort to the sampling-accelerated method[<sup>77</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c77) with the settings “num\_sample\_process\_4ph = 1E5” and “num\_sample\_process\_4ph\_phase\_space = 1E5.” Meanwhile, a 16 × 16 × 16 mesh of the first Brillouin zone is set, and the value of “scalebroad” is taken as 0.1. The cutoff distances of the third- and fourth-order IFCs are selected to be the seventh nearest and the second nearest atom, respectively. These mentioned parameters are large enough to make it converge to the rigorous calculations,<sup>75–78</sup> though resulting in a negligible uncertainty due to random sampling.

As illustrated in [Fig. 4(a)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f4), the ACE potential calculates the thermal conductivities of <em>w-</em>AlN along both in-plane and cross-plane directions. Though the physical pictures behind WTE and 4ph-scattering are different, their predictions are close indeed. The thermal conductivity predicted by ACE shows overall good agreements with our DFT calculations and experimental measurements (based on the three-sensor 2ω method proposed in our recent works).<sup>7,22,80</sup> Besides, the ACE-predicted values approximate the literature experiments<sup>2,79</sup> above room temperature as well, though the ACE overestimates thermal conductivities beneath 250 K owing to neglecting the phonon-defect scattering. Several theoretical and experimental studies<sup>27,79,81,82</sup> have discussed this issue, and researchers generally attribute the discrepancy between theoretical predictions and cryogenic experiments to the impacts of phonon-defect (e.g., point defects, dislocations, grain boundaries) scattering. Since the phonon-defect scattering rates are independent of temperature in principle,[<sup>27</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c27) they will dominate the phonon transport at low temperatures where the anharmonicity (normal and Umklapp processes) is weak.

![Figure 4](https://aipp.silverchair-cdn.com/aipp/content_public/journal/jap/135/8/10.1063_5.0188905/2/m_085105_1_5.0188905.figures.online.f4.jpeg?Expires=1782155914&Signature=wYkoLmSrO00AXyDeUevV1Q8fTYz8S7YvOdqBwCG4xPAFzXwxFM7G~IEITk7kLzPXJVd6bat-tLZDj4-YmSXZqb18TETFfi3B8doJz7D4WMZOupspkf1wiYwCp~B-aLjYlrmVoGGypOc-TompgbsXXVb1xh11646x0ZTayM4S5dr7QxNR5cH0PdUdEUvFrXfABjbJwWi~zN3YCEspOL1VT7OmA0eGjpZAQxpfl5gf59B0Jx4BRrSZvnroDiQdqQFj-mQBWiy8feWxKdoLFjfHETPAbrmRxLYX3OcMdGZflb2P~H~UIWhLoawEClhK2RCjsc650VRxpbQHMXv9tXxdpA__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 4.** (a) Comparison of <em>w-</em>AlN's thermal conductivities along the in-plane and cross-plane directions between the ACE model, DFT calculations, and experiments. Note that all the Phono3py calculations here have enabled the Wigner transport theory,<sup>70–72</sup> while the ShengBTE calculations have included four-phonon effects.[<sup>76</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c76) The literature experiments<sup>2,79</sup> depicted here are all based on an isotropic assumption, while experiments based on our three-sensor 2ω method[<sup>7</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c7) are capable of deriving the anisotropic thermal conductivity directly. (b) Comparison of accumulated thermal conductivity of <em>w-</em>AlN between the ACE model and DFT calculations, as a function of phonon frequency at 300 K along the in-plane and cross-plane directions, calculated by Phono3py.

The literature experiments depicted here are all based on an isotropic assumption, whereas our three-sensor 2ω method enables the direct derivation of thermal conductivities along different directions.[<sup>7</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c7) The brief introduction on the three-sensor 2ω method can be found in the [supplementary material](https://doi.org/10.60893/figshare.jap.c.7048016).

Furthermore, we conduct an equilibrium molecular dynamics (EMD) simulation based on the ACE potential to predict the <em>w-</em>AlN thermal conductivity. The large quantum effects at low temperatures significantly influence the MD-calculated thermal conductivity,<sup>28,81,83–86</sup> since the Debye temperature of <em>w-</em>AlN is quite high (⁠ $\mathrm{Θ}_{\mathrm{D}}\hspace{0.25em} \sim \hspace{0.25em}1000\hspace{0.1em}\mathrm{K}$⁠).[<sup>87</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c87) Hence, we only calculate the thermal conductivity at 1100 K, where the quantum effects could be reasonably neglected.[<sup>84</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c84) A bulk <em>w-</em>AlN system containing 4000 atoms is set as the initial configuration for EMD simulations conducted in the LAMMPS.[<sup>88</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c88) The length of each crystallographic direction reaching 10 unit cells achieves convergence for calculating the thermal conductivity of <em>w-</em>AlN.<sup>89,90</sup>

Periodic boundary conditions are applied to all three directions to mimic the infinite size of structures. A total of 4.5 ns EMD simulations based on the trained ACE potential are performed with a time step of 1 fs. After equilibrating the system in the isothermal–isobaric (NPT) ensemble for 500 ps, the system is switched to the microcanonical (NVE) ensemble for 4 ns to collect heat flux data. To mitigate the impacts of statistical uncertainties and errors, we conduct ten independent EMD simulations with different initial velocity distributions to obtain the averaged thermal conductivities at 1100 K. The thermal conductivity here is considered isotropic along the in-plane directions, so we average the thermal conductivity values along the *x*, *y* directions as the final in-plane thermal conductivity. The EMD results are $\kappa_{\mathrm{in}}^{\mathrm{MD}} = 51.0\hspace{0.1em} \pm \hspace{0.1em}5.8\hspace{0.25em}{\mathrm{W}/\mathrm{m}\hspace{0.25em}\mathrm{K}}$ and $\kappa_{\mathrm{cr}}^{\mathrm{MD}} = 48.4\hspace{0.1em} \pm \hspace{0.1em}6.3\hspace{0.25em}{\mathrm{W}/\mathrm{m}\hspace{0.25em}\mathrm{K}}$⁠, which are comparable to those of BTE calculations, as discussed in the [supplementary material](https://doi.org/10.60893/figshare.jap.c.7048016). On the AMD EPYC<sup>TM</sup> 7452 CPU platform, an average calculation efficiency of the ACE-based EMD simulations reaches 0.26 ms/MD-step/atom when calculating on a single thread (using GCC 9.1.0 compiler and LAMMPS 23-Jun-2022-Update3), which manifests the capability of the ACE potential for large-scale molecular dynamics.[<sup>52</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c52)

More detailed phonon transport characteristics of <em>w-</em>AlN are also calculated from the ACE potential by Phono3py. The accumulated thermal conductivity as a function of phonon frequency at 300 K is presented in [Fig. 4(b)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f4), which further verifies the accuracy of the ACE potential compared to the DFT results. Obviously, the thermal conductivity is primarily contributed by acoustic phonon branches with frequencies below the “phonon bandgap,” whose contributions exceed 98.5% for both in- and cross-plane values. In addition, we also calculate the accumulated thermal conductivity as a function of phonon mean free path (MFP) based on the single-mode relaxation time approximation, as detailed in the [supplementary material](https://doi.org/10.60893/figshare.jap.c.7048016). The discussions on MFP imply that the size effect of *w*-AlN film's thermal conductivity is crucial for practical applications, which limits the heat dissipation performance of the corresponding electronic devices.<sup>22,23,25,91,92</sup>

### C. Influence of biaxial strain on thermal properties of wurtzite AlN

As discussed in Sec. [I](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#88135711), there is an inevitable residual strain (stress) inside <em>w-</em>AlN in its practical applications, especially when <em>w-</em>AlN serves as the transition layer for a GaN HEMT by forming the GaN/AlN/Substrate heterojunction. Owing to the mismatches in lattice and thermal expansion between three materials, residual strain and lattice defects inside the <em>w-</em>AlN are general significant. Therefore, based on the trained ACE potential of <em>w-</em>AlN, we proceed to study the strain effects on lattice thermal conductivity of <em>w-</em>AlN.

In practical applications of transition layers, two kinds of strain exist within <em>w-</em>AlN, i.e., in-plane biaxial strain perpendicular to the polarization axis and cross-plane uniaxial strain along the polarization axis. Considering that in-plane stress is much more common than cross-plane stress in heterojunctions owing to the in-plane lattice mismatch[<sup>26</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c26) and the uniaxial strain hardly affects thermal conductivity,[<sup>93</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c93) we only investigate the biaxial strain effects in this work. Here, the strain is applied by modifying the lattice constants of the structure, and then the structure is relaxed with the in-plane lattice constant *a* (or $b$⁠) being settled. The biaxial strain is expressed by relative variation of the in-plane lattice constant,

**Equation 9.**

$$
\begin{matrix} {\sigma_{a} = {\frac{a - a_{0}}{a_{0}}.}} \end{matrix}
$$

Under in-plane biaxial strain states, the other lattice constant *c* will also vary to achieve minimal stress, and finally an optimized structure in the cross-plane direction is formed. Also, the changes of crystal symmetries are not detected under strain states in this work, i.e., AlN maintains a wurtzite structure with the space group P6<sub>3</sub>/mmc. The introduction of lattice strains and the structure optimization are performed using the atomic simulation environment (ASE)[<sup>94</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c94) package. Consequently, phonon properties as well as the thermal conductivity of <em>w-</em>AlN exhibit continuous changes under biaxial strain $\sigma_{a}$ states, ranging from −4% to 4%.

From a classical and intuitional perspective, compressive strain is expected to increase the thermal conductivity by augmenting the elasticity modulus and acoustic velocity.[<sup>26</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c26) The results, shown in [Fig. 5](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f5), reveal that both in- and cross-plane thermal conductivity of <em>w-</em>AlN decrease remarkably under the +4% biaxial strain state (tensile) at room temperature, with the average thermal conductivity decreasing by 40%. Conversely, under the −4% biaxial strain state (compressive), the average thermal conductivity increases by 30%. In the temperature range of 200–400 K, lattice thermal conductivity decreases significantly; however, the decrease/increase trend depending on biaxial strain is nearly constant at different temperatures \[[Fig. 5(b)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f5)\], implying that the influences of lattice strain and temperature on thermal conductivity should be independent. Meanwhile, the temperature dependence of thermal conductivity follows a similar trend under different biaxial strain states.

![Figure 5](https://aipp.silverchair-cdn.com/aipp/content_public/journal/jap/135/8/10.1063_5.0188905/2/m_085105_1_5.0188905.figures.online.f5.jpeg?Expires=1782155914&Signature=O7Lahg~99~Ek6h6tGXzVtCf3TQa9lePpm9j89VI0N8ytGYUfUtkO9kFuVeOe35fBxWX7Ry2LFqZNZDXdrpMMb~9qDPTtzmIdngiM01-SBchKWSEf~6Bd3ehlB~~1qLivrwDczgFlkGqqF3g6e1vquU7D~5WCFpqKL~TnHha8WBWwZ7csbCHD9LATQe7w~~EQoB~Rc8Nxz9iUuqiQXNC2MymdsNOfzcSqSDJqK~QQP1zjPB5lpDh8RX6D3EbBrILsKEnh09vqObiUG4NTYnklrMoBXEnxzbUUxsrdzolCO-lduWs-jiGWqbIcpzUVvvbI0Ook7bZSneAiM4mGIV9qkQ__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 5.** The effects of biaxial strains on thermal conductivities of <em>w-</em>AlN. (a) The dependence between thermal conductivities and the biaxial strains at 200−400 K, and (b) the variation of relative thermal conductivities at each temperature, i.e., the strained $\kappa_{strain}\hspace{0.25em}$divided by the strain-less $\kappa_{0}$ at the same temperature.

Then, we investigate the changes of phonon properties under different strain states, to elucidate the correlation with their thermal conductivity. Based on the phonon BTE, lattice thermal conductivity can be expressed as[<sup>26</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c26)

**Equation 10.**

$$
\begin{matrix} {\kappa_{\mathrm{L}}^{\alpha\beta} = \sum\limits_{\boldsymbol{q},\omega}C_{\boldsymbol{q},\omega}v_{\boldsymbol{q},\omega}^{\alpha}v_{\boldsymbol{q},\omega}^{\beta}\tau_{\boldsymbol{q},\omega},} \end{matrix}
$$

in which $\boldsymbol{q}$ and $\omega$ denote the phonon branch and the frequency of a specific phonon mode, respectively. Thus, lattice thermal conductivity primarily depends on the three variables, namely, volumetric specific heat $C_{\boldsymbol{q},\omega}$⁠, group velocity $v_{\boldsymbol{q},\omega}^{\alpha}$ (⁠ $v_{\boldsymbol{q},\omega}^{\beta}$⁠), and relaxation time $\tau_{\boldsymbol{q},\omega}$ of each phonon mode. Note that all these parameters are determined by the phonon dispersions, as illustrated in the [supplementary material](https://doi.org/10.60893/figshare.jap.c.7048016).

[Figures 6(a)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f6) and [6(b)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f6) illustrate the phonon harmonic properties under different strain states, while [Figs. 6(c)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f6) and [6(d)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f6) depict the anharmonic features. Volumetric specific heat of phonon modes reflects the energy level of a crystal system, varying with the phonon dispersions and volume of the unit cell correspondingly. As shown in [Fig. 6(a)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f6), slight decreases of mode specific heat with tensile biaxial strains occur, implying a positive correlation to the change of thermal conductivity. In [Fig. 6(b)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f6), phonon group velocity gradually increases from the tensile to compressive strain states, which is consistent with the increased thermal conductivity. [Figure 6(c)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f6) shows that phonon relaxation time decreases under the tensile strain state and increases under the compressive strain state, which is consistent with the thermal conductivity variations as well. According to the results of phonon DOSs in the [supplementary material](https://doi.org/10.60893/figshare.jap.c.7048016), the phonon bandgaps are 0.65, 1.35, and 2.40 THz under tensile, free, and compressive strains, respectively. This determines the variations of relaxation time in principle, since a smaller (larger) phonon bandgap will enable more (less) available three-phonon scattering channels, thereby enhancing (suppressing) the three-phonon anharmonic scattering processes.<sup>26,95</sup>

![Figure 6](https://aipp.silverchair-cdn.com/aipp/content_public/journal/jap/135/8/10.1063_5.0188905/2/m_085105_1_5.0188905.figures.online.f6.jpeg?Expires=1782155914&Signature=ftONJsaEO63AVQ61Gojo3nRpm2cxQFCeLWT2CEOl8oNT1-HfrM9ZRumVImjwWERj0-Jscsn5kqawoFT~KrccjT3a~KlFh4vPqc6LilG3cxiAum1JFLnxRF10IDvxDiUVfQ6e9S2iusBORdUKAURSDL883ie26yFFjx2V5p3J1hrVTliWeZdl2KrvITDX0ndEyqUpagcSoD0GcNbYOwonQx5zY32U7s7sFbyr4PEKifxXufk5FyjgJ6wtvN6HjYeHMM9qewWe7fZajJaNbAEqguCamy-gl1xGJlmRbPBujG8gaZo1tvrdjdONdZDyYd3HxKgWpye4CNdwN5dSHAe6Qg__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 6.** Phonon properties under different biaxial strain states. (a) Mode volumetric specific heat, (b) phonon group velocity, (c) phonon relaxation time, and (d) Grüneisen parameters.

The Grüneisen parameter, an indicator of lattice anharmonicity,<sup>26,27</sup> is further analyzed here to back up the influences of strains on anharmonic scattering processes \[[Fig. 6(d)](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#f6)\]. Obvious increases (decreases) in the Grüneisen parameters of acoustic phonon branches are observed under the tensile (compressive) strain state, in line with the variations of phonon bandgaps. More discussions on how and why lattice strains affect the phonon anharmonicity can be found in the [supplementary material](https://doi.org/10.60893/figshare.jap.c.7048016). Consequently, the consistent variations in mode specific heat, group velocity, relaxation time, and anharmonicity lead to significant changes in the lattice thermal conductivity[<sup>26</sup>](https://pubs.aip.org/aip/jap/article/135/8/085105/3266915/Machine-learned-atomic-cluster-expansion#c26) of *w*-AlN under different strain states.

The highlighted impacts of lattice strains on phonon properties should be favorable for tuning the heat dissipation performance of corresponding *w*-AlN-based electronic devices. By carefully engineering the residual strains within heteroepitaxial structures via annealing<sup>96,97</sup> or selecting substrates with specific lattice structures,<sup>26,98</sup> it is viable to optimize the lattice thermal properties on demand, facilitating near-junction thermal optimization of semiconductor devices.<sup>91,99</sup>

## IV. CONCLUSIONS

We have developed an ACE potential based on machine learning for atomistic simulations of monocrystalline <em>w-</em>AlN. Our ACE potential exhibits remarkable accuracy in reproducing the DFT potential energy surface of <em>w-</em>AlN, achieving an energy RMSE of ∼0.13 meV/atom and a force RMSE of ∼5.01 meV/Å for both Al and N atoms. Subsequently, the predictive power of ACE is demonstrated across a variety of properties of *w*-AlN, including ground-state lattice parameters, specific heat capacity, coefficients of thermal expansion, bulk modulus, phonon dispersions, and thermal conductivity. All these results show excellent agreement with the DFT calculations and experimental results, demonstrating that the ACE model sufficiently describes both harmonic and anharmonic phonon properties.

The lattice strain is proven as a significant tuning factor for thermal design of heteroepitaxial electronic devices. As a practical application of the ACE potential, we perform lattice dynamics simulations to unravel the effects of biaxial strains on thermal conductivity of <em>w-</em>AlN. The results indicate that a 4% biaxial tensile (compressive) strain approximately causes a 40% decrease (30% increase) in the thermal conductivity of <em>w-</em>AlN, while the influences of lattice strain and temperature on thermal conductivity appear to be independent. The investigations into phonon pictures under different strains reveal that the consistent variations in phonon mode heat capacity, group velocities, and relaxation times predominantly contribute to the variation of thermal conductivity, while all these factors stem from the variations in phonon band structures. Thus, it is feasible to facilitate near-junction thermal optimization of devices via strain engineering on phonon bands. The findings here are beneficial for the development of next-generation electronic devices.

## SUPPLEMENTARY MATERIAL

See the [supplementary material](https://doi.org/10.60893/figshare.jap.c.7048016) for brief introductions to the experiments, additional discussions on phonon properties, and the ACE potential files developed for simulations in both LAMMPS and ASE calculators.

## ACKNOWLEDGMENTS

This work was financially supported by the National Natural Science Foundation of China (NNSFC) (Grant Nos. U20A20301, 52327809, 52250273, and 51825601).

## AUTHOR DECLARATIONS

### Conflict of Interest

The authors have no conflicts to disclose.

### Author Contributions

Guang Yang and Yuan-Bin Liu contributed equally to this work.

**Guang Yang:** Conceptualization (lead); Data curation (equal); Formal analysis (equal); Investigation (lead); Methodology (equal); Software (equal); Validation (lead); Visualization (lead); Writing – original draft (lead). **Yuan-Bin Liu:** Conceptualization (supporting); Data curation (equal); Formal analysis (equal); Investigation (supporting); Methodology (equal); Resources (supporting); Software (equal); Validation (supporting); Visualization (supporting); Writing – original draft (supporting); Writing – review & editing (supporting). **Lei Yang:** Methodology (supporting); Software (supporting). **Bing-Yang Cao:** Funding acquisition (lead); Project administration (lead); Resources (lead); Supervision (lead); Writing – review & editing (lead).

## DATA AVAILABILITY

The ACE potential is attached in the [supplementary material](https://doi.org/10.60893/figshare.jap.c.7048016), which can be used with the ML-PACE package on [https://github.com/ICAMS/lammps-user-pace](https://github.com/ICAMS/lammps-user-pace). The data that support the findings of this study are available from the corresponding author upon reasonable request.

## References (99 total, showing 99)

1. W. A. Doolittle, C. M. Matthews, H. Ahmad, K. Motoki, S. Lee, A. Ghosh, E. N. Marshall, A. L. Tang, P. Manocha, and P. D. Yoder, “Prospectives for AlN electronics and optoelectronics and the important role of alternative synthesis,” Appl. Phys. Lett. 123(7), 070501 (2023). https://doi.org/10.1063/5.0156691

2. R. L. Xu, M. Muñoz Rojo, S. M. Islam, A. Sood, B. Vareskic, A. Katre, N. Mingo, K. E. Goodson, H. G. Xing, D. Jena, and E. Pop, “Thermal conductivity of crystalline AlN and the influence of atomic-scale defects,” J. Appl. Phys. 126(18), 185105 (2019). https://doi.org/10.1063/1.5097172

3. J. Yang, K. Liu, X. Chen, and D. Shen, “Recent advances in optoelectronic and microelectronic devices based on ultrawide-bandgap semiconductors,” Prog. Quant. Electron. 83, 100397 (2022). https://doi.org/10.1016/j.pquantelec.2022.100397

4. M. Bickermann, in *III-Nitride Ultraviolet Emitters Technology and Applications*, edited by M. Kneissl and J. Rass (Springer International Publishing, Cham, 2016), pp. 27–46.

5. K. Tonisch, V. Cimalla, C. Foerster, H. Romanus, O. Ambacher, and D. Dontsov, “Piezoelectric properties of polycrystalline AlN thin films for MEMS application,” Sens. Actuators Phys. 132(2), 658–663 (2006). https://doi.org/10.1016/j.sna.2006.03.001

6. R. Rounds, B. Sarkar, D. Alden, Q. Guo, A. Klump, C. Hartmann, T. Nagashima, R. Kirste, A. Franke, M. Bickermann, Y. Kumagai, Z. Sitar, and R. Collazo, “The influence of point defects on the thermal conductivity of AlN crystals,” J. Appl. Phys. 123(18), 185107 (2018). https://doi.org/10.1063/1.5028141

7. G. Yang and B.-Y. Cao, “Three-sensor 2ω method with multi-directional layout: A general methodology for measuring thermal conductivity of solid materials,” Int. J. Heat Mass Transfer 219, 124878 (2024). https://doi.org/10.1016/j.ijheatmasstransfer.2023.124878

8. R. T. Bondokov, S. G. Mueller, K. E. Morgan, G. A. Slack, S. Schujman, M. C. Wood, J. A. Smart, and L. J. Schowalter, “Large-area AlN substrates for electronic applications: An industrial perspective,” J. Cryst. Growth 310(17), 4020–4026 (2008). https://doi.org/10.1016/j.jcrysgro.2008.06.032

9. R. Yu, G. Liu, G. Wang, C. Chen, M. Xu, H. Zhou, T. Wang, J. Yu, G. Zhao, and L. Zhang, “Ultrawide-bandgap semiconductor AlN crystals: Growth and applications,” J. Mater. Chem. C 9(6), 1852–1873 (2021). https://doi.org/10.1039/D0TC04182C

10. A. Khan, K. Balakrishnan, and T. Katona, “Ultraviolet light-emitting diodes based on group three nitrides,” Nat. Photonics 2(2), 77–84 (2008). https://doi.org/10.1038/nphoton.2007.293

11. Y. Taniyasu and M. Kasu, “Aluminum nitride deep-ultraviolet light-emitting p–n junction diodes,” Diamond Relat. Mater. 17(7), 1273–1277 (2008). https://doi.org/10.1016/j.diamond.2008.02.042

12. Y. Zhu, N. Wang, C. Sun, S. Merugu, N. Singh, and Y. Gu, “A high coupling coefficient 2.3-GHz AlN resonator for high band LTE filtering application,” IEEE Electron Device Lett. 37(10), 1344–1346 (2016). https://doi.org/10.1109/LED.2016.2602852

13. U. C. Kaletta, P. V. Santos, D. Wolansky, A. Scheit, M. Fraschke, C. Wipf, P. Zaumseil, and C. Wenger, “Monolithic integrated SAW filter based on AlN for high-frequency applications,” Semicond. Sci. Technol. 28(6), 065013 (2013). https://doi.org/10.1088/0268-1242/28/6/065013

14. C. Cassella and G. Piazza, “AlN two-dimensional-mode resonators for ultra-high frequency applications,” IEEE Electron Device Lett. 36(11), 1192–1194 (2015). https://doi.org/10.1109/LED.2015.2475172

15. K. Yang, F. Lin, Z. Wu, D. Fu, L. Wu, and C. Zuo, “High electromechanical coupling SAW resonators based on a-plane AlScN-AlN-sapphire substrate,” in 2022 IEEE MTT- International Conference Microwave Acoustics and Mechanics IC-MAM (IEEE, 2022), pp. 106–109.

16. G. Wang and Y. Zhou, “Thermal management modeling for β-Ga<sub>2</sub>O<sub>3</sub>-highly thermal conductive substrates heterostructures,” IEEE Trans. Compon. Packag. Manuf. Technol. 12(4), 638–646 (2022). https://doi.org/10.1109/TCPMT.2022.3157672

17. A. Tanaka, W. Choi, R. Chen, R. Liu, W. M. Mook, K. L. Jungjohann, P. K. L. Yu, and S. A. Dayeh, “Structural and electrical characterization of thick GaN layers on Si, GaN, and engineered substrates,” J. Appl. Phys. 125(8), 082517 (2018). https://doi.org/10.1063/1.5049393

18. Y.-B. Liu, H.-L. Liang, L. Yang, G. Yang, H.-A. Yang, S. Song, Z.-X. Mei, G. Csányi, and B.-Y. Cao, “Unraveling thermal transport correlated with atomistic structures in amorphous gallium oxide via machine learning combined with experiments,” Adv. Mater. 35, 2210873 (2023). https://doi.org/10.1002/adma.202210873

19. M. H. Wong, O. Bierwagen, R. J. Kaplar, and H. Umezawa, “Ultrawide-bandgap semiconductors: An overview,” J. Mater. Res. 36(23), 4601–4615 (2021). https://doi.org/10.1557/s43578-021-00458-1

20. D.-Y. Guo, P.-G. Li, Z.-W. Chen, Z.-P. Wu, and W.-H. Tang, “Ultra-wide bandgap semiconductor of β-Ga<sub>2</sub>O<sub>3</sub> and its research progress of deep ultraviolet transparent electrode and solar-blind photodetector,” Acta Phys. Sin. 68(7), 078501–1 (2019). https://doi.org/10.7498/aps.68.20181845

21. H. Liang, Z. Han, and Z. Mei, “Recent progress of deep ultraviolet photodetectors using amorphous gallium oxide thin films,” Phys. Status Solidi A 218(1), 2000339 (2021). https://doi.org/10.1002/pssa.202000339

22. G. Yang and B.-Y. Cao, “Three-sensor 3ω-2ω method for the simultaneous measurement of thermal conductivity and thermal boundary resistance in film-on-substrate heterostructures,” J. Appl. Phys. 133(4), 045104 (2023). https://doi.org/10.1063/5.0120284

23. Z.-K. Liu, G. Yang, and B.-Y. Cao, “Pulsed thermoreflectance imaging for thermophysical properties measurement of GaN epitaxial heterostructures,” Rev. Sci. Instrum. 94(9), 094902 (2023). https://doi.org/10.1063/5.0155795

24. H.-L. Li, Y. Shen, Y.-C. Hua, S. L. Sobolev, and B.-Y. Cao, “Hybrid Monte Carlo-Diffusion studies of modeling self-heating in ballistic-diffusive regime for gallium nitride HEMTs,” J. Electron. Packag. 145, 011203 (2022). https://doi.org/10.1115/1.4054698

25. J. Cho, Y. Li, W. E. Hoke, D. H. Altman, M. Asheghi, and K. E. Goodson, “Phonon scattering in strained transition layers for GaN heteroepitaxy,” Phys. Rev. B 89(11), 115301 (2014). https://doi.org/10.1103/PhysRevB.89.115301

26. D.-S. Tang, G.-Z. Qin, M. Hu, and B.-Y. Cao, “Thermal transport properties of GaN with biaxial strain and electron-phonon coupling,” J. Appl. Phys. 127(3), 035102 (2020). https://doi.org/10.1063/1.5133105

27. D.-S. Tang, Y.-C. Hua, Y.-G. Zhou, and B.-Y. Cao, “Thermal conductivity modeling of GaN films,” Acta Phys. Sin. 70(4), 045101 (2021). https://doi.org/10.7498/aps.70.20201611

28. H. Bao, J. Chen, X.-K. Gu, and B.-Y. Cao, “A review of simulation methods in micro/nanoscale heat conduction,” ES Energy Environ. 1, 16–55 (2018). https://doi.org/10.30919/esee8c149

29. Y.-F. Luo, M.-K. Li, H.-K. Yuan, H.-J. Liu, and Y. Fang, “Predicting lattice thermal conductivity via machine learning: A mini review,” npj Comput. Mater. 9(1), 1–11 (2023). https://doi.org/10.1038/s41524-022-00962-w

30. H. Babaei, R. Guo, A. Hashemi, and S. Lee, “Machine-learning-based interatomic potential for phonon transport in perfect crystalline Si and crystalline Si with vacancies,” Phys. Rev. Mater. 3(7), 074603 (2019). https://doi.org/10.1103/PhysRevMaterials.3.074603

31. X. W. Zhou, R. E. Jones, C. J. Kimmer, J. C. Duda, and P. E. Hopkins, “Relationship of thermal boundary conductance to structure from an analytical model plus molecular dynamics simulations,” Phys. Rev. B 87(9), 094303 (2013). https://doi.org/10.1103/PhysRevB.87.094303

32. M. Tungare, Y. Shi, N. Tripathi, P. Suvarna, and F. (Shadi) Shahedipour-Sandvik, “A tersoff-based interatomic potential for wurtzite AlN,” Phys. Status Solidi A 208(7), 1569–1572 (2011). https://doi.org/10.1002/pssa.201001086

33. P. Vashishta, R. K. Kalia, A. Nakano, J. P. Rino, and Collaboratory for Advanced Computing and Simulations, “Interaction potential for aluminum nitride: A molecular dynamics study of mechanical and thermal properties of crystalline and amorphous aluminum nitride,” J. Appl. Phys. 109(3), 033514 (2011). https://doi.org/10.1063/1.3525983

34. K. Choudhary, T. Liang, K. Mathew, B. Revard, A. Chernatynskiy, S. R. Phillpot, R. G. Hennig, and S. B. Sinnott, “Dynamical properties of AlN nanostructures and heterogeneous interfaces predicted using COMB potentials,” Comput. Mater. Sci. 113, 80–87 (2016). https://doi.org/10.1016/j.commatsci.2015.11.025

35. H. Xiang, H. Li, and X. Peng, “Comparison of different interatomic potentials for MD simulations of AlN,” Comput. Mater. Sci. 140, 113–120 (2017). https://doi.org/10.1016/j.commatsci.2017.08.042

36. Y.-B. Liu, J.-Y. Yang, G.-M. Xin, L.-H. Liu, G. Csányi, and B.-Y. Cao, “Machine learning interatomic potential developed for molecular simulations on thermal properties of β-Ga<sub>2</sub>O<sub>3</sub>,” J. Chem. Phys. 153(14), 144501 (2020). https://doi.org/10.1063/5.0027643

37. G. Barbalinardo, Z. Chen, N. W. Lundgren, and D. Donadio, “Efficient anharmonic lattice dynamics calculations of thermal transport in crystalline and disordered solids,” J. Appl. Phys. 128(13), 135104 (2020). https://doi.org/10.1063/5.0020443

38. G. Barbalinardo, Z. Chen, H. Dong, Z. Fan, and D. Donadio, “Ultrahigh convergent thermal conductivity of carbon nanotubes from comprehensive atomistic modeling,” Phys. Rev. Lett. 127(2), 025902 (2021). https://doi.org/10.1103/PhysRevLett.127.025902

39. P. Gkeka, G. Stoltz, A. Barati Farimani, Z. Belkacemi, M. Ceriotti, J. D. Chodera, A. R. Dinner, A. L. Ferguson, J.-B. Maillet, H. Minoux, C. Peter, F. Pietrucci, A. Silveira, A. Tkatchenko, Z. Trstanova, R. Wiewiora, and T. Lelièvre, “Machine learning force fields and coarse-grained variables in molecular dynamics: Application to materials and biological systems,” J. Chem. Theory Comput. 16(8), 4757–4775 (2020). https://doi.org/10.1021/acs.jctc.0c00355

40. V. L. Deringer, A. P. Bartók, N. Bernstein, D. M. Wilkins, M. Ceriotti, and G. Csányi, “Gaussian process regression for materials and molecules,” Chem. Rev. 121(16), 10073–10141 (2021). https://doi.org/10.1021/acs.chemrev.1c00022

41. J. Behler and M. Parrinello, “Generalized neural-network representation of high-dimensional potential-energy surfaces,” Phys. Rev. Lett. 98(14), 146401 (2007). https://doi.org/10.1103/PhysRevLett.98.146401

42. J. Behler, “Neural network potential-energy surfaces in chemistry: A tool for large-scale simulations,” Phys. Chem. Chem. Phys. 13(40), 17930–17955 (2011). https://doi.org/10.1039/c1cp21668f

43. A. P. Bartók, M. C. Payne, R. Kondor, and G. Csányi, “Gaussian approximation potentials: The accuracy of quantum mechanics, without the electrons,” Phys. Rev. Lett. 104(13), 136403 (2010). https://doi.org/10.1103/PhysRevLett.104.136403

44. A. P. Bartók, R. Kondor, and G. Csányi, “On representing chemical environments,” Phys. Rev. B 87(18), 184115 (2013). https://doi.org/10.1103/PhysRevB.87.184115

45. A. P. Thompson, L. P. Swiler, C. R. Trott, S. M. Foiles, and G. J. Tucker, “Spectral neighbor analysis method for automated generation of quantum-accurate interatomic potentials,” J. Comput. Phys. 285, 316–330 (2015). https://doi.org/10.1016/j.jcp.2014.12.018

46. X.-G. Li, C. Hu, C. Chen, Z. Deng, J. Luo, and S. P. Ong, “Quantum-accurate spectral neighbor analysis potential models for Ni-Mo binary alloys and fcc metals,” Phys. Rev. B 98(9), 094104 (2018). https://doi.org/10.1103/PhysRevB.98.094104

47. H. Wang, L. Zhang, J. Han, and W. E, “DeePMD-kit: A deep learning package for many-body potential energy representation and molecular dynamics,” Comput. Phys. Commun. 228, 178–184 (2018). https://doi.org/10.1016/j.cpc.2018.03.016

48. J. Zeng, D. Zhang, D. Lu, P. Mo, Z. Li, Y. Chen, M. Rynik, L. Huang, Z. Li, S. Shi, Y. Wang, H. Ye, P. Tuo, J. Yang, Y. Ding, Y. Li, D. Tisi, Q. Zeng, H. Bao, Y. Xia, J. Huang, K. Muraoka, Y. Wang, J. Chang, F. Yuan, S. L. Bore, C. Cai, Y. Lin, B. Wang, J. Xu, J.-X. Zhu, C. Luo, Y. Zhang, R. E. A. Goodall, W. Liang, A. K. Singh, S. Yao, J. Zhang, R. Wentzcovitch, J. Han, J. Liu, W. Jia, D. M. York, W. E. R. Car, L. Zhang, and H. Wang, “DeePMD-kit v2: A software package for deep potential models,” J. Chem. Phys. 159(5), 054801 (2023). https://doi.org/10.1063/5.0155600

49. A. V. Shapeev, “Moment tensor potentials: A class of systematically improvable interatomic potentials,” Multiscale Model. Simul. 14(3), 1153–1173 (2016). https://doi.org/10.1137/15M1054183

50. E. V. Podryabinkin and A. V. Shapeev, “Active learning of linearly parametrized interatomic potentials,” Comput. Mater. Sci. 140, 171–180 (2017). https://doi.org/10.1016/j.commatsci.2017.08.031

51. R. Drautz, “Atomic cluster expansion for accurate and transferable interatomic potentials,” Phys. Rev. B 99(1), 014104 (2019). https://doi.org/10.1103/PhysRevB.99.014104

52. Y. Lysogorskiy, C. van der Oord, A. Bochkarev, S. Menon, M. Rinaldi, T. Hammerschmidt, M. Mrovec, A. Thompson, G. Csányi, C. Ortner, and R. Drautz, “Performant implementation of the atomic cluster expansion (PACE) and application to copper and silicon,” npj Comput. Mater. 7(1), 1–12 (2021). https://doi.org/10.1038/s41524-021-00559-9

53. S. Batzner, A. Musaelian, L. Sun, M. Geiger, J. P. Mailoa, M. Kornbluth, N. Molinari, T. E. Smidt, and B. Kozinsky, “E(3)-equivariant graph neural networks for data-efficient and accurate interatomic potentials,” Nat. Commun. 13(1), 2453 (2022). https://doi.org/10.1038/s41467-022-29939-5

54. A. Musaelian, S. Batzner, A. Johansson, L. Sun, C. J. Owen, M. Kornbluth, and B. Kozinsky, “Learning local equivariant representations for large-scale atomistic dynamics,” Nat. Commun. 14(1), 579 (2023). https://doi.org/10.1038/s41467-023-36329-y

55. I. Batatia, D. P. Kovacs, G. Simm, C. Ortner, and G. Csanyi, “MACE: Higher order equivariant message passing neural networks for fast and accurate force fields,” Adv. Neural Inf. Process. Syst. 35, 11423–11436 (2022).

56. D. P. Kovács, I. Batatia, E. S. Arany, and G. Csányi, “Evaluation of the MACE force field architecture: From medicinal chemistry to materials science,” J. Chem. Phys. 159(4), 044118 (2023). https://doi.org/10.1063/5.0155322

57. W. C. Witt, C. van der Oord, E. Gelžinytė, T. Järvinen, A. Ross, J. P. Darby, C. H. Ho, W. J. Baldwin, M. Sachs, J. Kermode, N. Bernstein, G. Csányi, and C. Ortner, “ACEpotentials.jl: A Julia implementation of the atomic cluster expansion,” J. Chem. Phys. 159(16), 164101 (2023). https://doi.org/10.1063/5.0158783

58. A. Bochkarev, Y. Lysogorskiy, S. Menon, M. Qamar, M. Mrovec, and R. Drautz, “Efficient parametrization of the atomic cluster expansion,” Phys. Rev. Mater. 6(1), 013804 (2022). https://doi.org/10.1103/PhysRevMaterials.6.013804

59. G. Kresse and J. Furthmüller, “Efficient iterative schemes for *ab initio* total-energy calculations using a plane-wave basis set,” Phys. Rev. B 54(16), 11169–11186 (1996). https://doi.org/10.1103/PhysRevB.54.11169

60. J. P. Perdew, A. Ruzsinszky, G. I. Csonka, O. A. Vydrov, G. E. Scuseria, L. A. Constantin, X. Zhou, and K. Burke, “Restoring the density-gradient expansion for exchange in solids and surfaces,” Phys. Rev. Lett. 100(13), 136406 (2008). https://doi.org/10.1103/PhysRevLett.100.136406

61. P. E. Blöchl, “Projector augmented-wave method,” Phys. Rev. B 50(24), 17953–17979 (1994). https://doi.org/10.1103/PhysRevB.50.17953

62. Y. Zuo, C. Chen, X. Li, Z. Deng, Y. Chen, J. Behler, G. Csányi, A. V. Shapeev, A. P. Thompson, M. A. Wood, and S. P. Ong, “Performance and cost assessment of machine learning interatomic potentials,” J. Phys. Chem. A 124(4), 731–745 (2020). https://doi.org/10.1021/acs.jpca.9b08723

63. G. Dusson, M. Bachmayr, G. Csányi, R. Drautz, S. Etter, C. van der Oord, and C. Ortner, “Atomic cluster expansion: Completeness, efficiency and stability,” J. Comput. Phys. 454, 110946 (2022). https://doi.org/10.1016/j.jcp.2022.110946

64. W. Paszkowicz, S. Podsiadło, and R. Minikayev, “Rietveld-refinement study of aluminium and gallium nitrides,” J. Alloys Compd. 382(1), 100–106 (2004). https://doi.org/10.1016/j.jallcom.2004.05.036

65. A. Togo, L. Chaput, I. Tanaka, and G. Hug, “First-principles phonon calculations of thermal expansion in Ti<sub>3</sub>SiC<sub>2</sub>, Ti<sub>3</sub>AlC<sub>2</sub>, and Ti<sub>3</sub>GeC<sub>2</sub>,” Phys. Rev. B 81(17), 174301 (2010). https://doi.org/10.1103/PhysRevB.81.174301

66. A. Togo, “First-principles phonon calculations with phonopy and Phono3py,” J. Phys. Soc. Jpn. 92(1), 012001 (2023). https://doi.org/10.7566/JPSJ.92.012001

67. A. Togo, L. Chaput, T. Tadano, and I. Tanaka, “Implementation strategies in phonopy and phono3py,” J. Phys.: Condens. Matter 35(35), 353001 (2023). https://doi.org/10.1088/1361-648X/acd831

68. J. C. Nipko and C.-K. Loong, “Phonon excitations and related thermal properties of aluminum nitride,” Phys. Rev. B 57(17), 10550–10554 (1998). https://doi.org/10.1103/PhysRevB.57.10550

69. A. Togo and I. Tanaka, “First principles phonon calculations in materials science,” Scr. Mater. 108, 1–5 (2015). https://doi.org/10.1016/j.scriptamat.2015.07.021

70. M. Simoncelli, N. Marzari, and F. Mauri, “Unified theory of thermal transport in crystals and glasses,” Nat. Phys. 15(8), 809–813 (2019). https://doi.org/10.1038/s41567-019-0520-x

71. M. Simoncelli, N. Marzari, and F. Mauri, “Wigner formulation of thermal transport in solids,” Phys. Rev. X 12(4), 041011 (2022). https://doi.org/10.1103/PhysRevX.12.041011

72. E. Di Lucente, M. Simoncelli, and N. Marzari, “Crossover from Boltzmann to Wigner thermal transport in thermoelectric skutterudites,” Phys. Rev. Res. 5(3), 033125 (2023). https://doi.org/10.1103/PhysRevResearch.5.033125

73. A. Togo, L. Chaput, and I. Tanaka, “Distributions of phonon lifetimes in Brillouin zones,” Phys. Rev. B 91(9), 094306 (2015). https://doi.org/10.1103/PhysRevB.91.094306

74. L. Chaput, “Direct solution to the linearized phonon Boltzmann equation,” Phys. Rev. Lett. 110(26), 265506 (2013). https://doi.org/10.1103/PhysRevLett.110.265506

75. W. Li, J. Carrete, N. A. Katcho, and N. Mingo, “ShengBTE: A solver of the Boltzmann transport equation for phonons,” Comput. Phys. Commun. 185(6), 1747–1758 (2014). https://doi.org/10.1016/j.cpc.2014.02.015

76. Z. Han, X. Yang, W. Li, T. Feng, and X. Ruan, “Fourphonon: An extension module to ShengBTE for computing four-phonon scattering rates and thermal conductivity,” Comput. Phys. Commun. 270, 108179 (2022). https://doi.org/10.1016/j.cpc.2021.108179

77. Z. Guo, Z. Han, D. Feng, G. Lin, and X. Ruan, “Sampling-accelerated first-principles prediction of phonon scattering rates for converged thermal conductivity and radiative properties,”arXiv:2311.12935 (2023).

78. A. Kundu, X. Yang, J. Ma, T. Feng, J. Carrete, X. Ruan, G. K. H. Madsen, and W. Li, “Ultrahigh thermal conductivity of θ-phase tantalum nitride,” Phys. Rev.: Lett. 126(11), 115901 (2021). https://doi.org/10.1103/PhysRevLett.126.115901

79. Z. Cheng, Y. R. Koh, A. Mamun, J. Shi, T. Bai, K. Huynh, L. Yates, Z. Liu, R. Li, E. Lee, M. E. Liao, Y. Wang, H. M. Yu, M. Kushimoto, T. Luo, M. S. Goorsky, P. E. Hopkins, H. Amano, A. Khan, and S. Graham, “Experimental observation of high intrinsic thermal conductivity of AlN,” Phys. Rev. Mater. 4(4), 044602 (2020). https://doi.org/10.1103/PhysRevMaterials.4.044602

80. Y.-C. Hua and B.-Y. Cao, “A two-sensor 3ω-2ω method for thermal boundary resistance measurement,” J. Appl. Phys. 129(12), 125107 (2021). https://doi.org/10.1063/5.0039444

81. J. E. Turney, A. J. H. McGaughey, and C. H. Amon, “Assessing the applicability of quantum corrections to classical thermal conductivity predictions,” Phys. Rev. B 79(22), 224305 (2009). https://doi.org/10.1103/PhysRevB.79.224305

82. P. Jiang, X. Qian, X. Li, and R. Yang, “Three-dimensional anisotropic thermal conductivity tensor of single crystalline β-Ga<sub>2</sub>O<sub>3</sub>,” Appl. Phys. Lett. 113(23), 232105 (2018). https://doi.org/10.1063/1.5054573

83. J. E. Turney, E. S. Landry, A. J. H. McGaughey, and C. H. Amon, “Predicting phonon properties and thermal conductivity from anharmonic lattice dynamics calculations and molecular dynamics simulations,” Phys. Rev. B 79(6), 064301 (2009). https://doi.org/10.1103/PhysRevB.79.064301

84. B.-Y. Cao, W.-J. Yao, and Z.-Q. Ye, “Networked nanoconstrictions: An effective route to tuning the thermal transport properties of graphene,” Carbon 96, 711–719 (2016). https://doi.org/10.1016/j.carbon.2015.09.097

85. X. Gu, Z. Fan, and H. Bao, “Thermal conductivity prediction by atomistic simulation methods: Recent advances and detailed comparison,” J. Appl. Phys. 130(21), 210902 (2021). https://doi.org/10.1063/5.0069175

86. Y.-X. Xu, H.-Z. Fan, and Y.-G. Zhou, “Quantifying spectral thermal transport properties in framework of molecular dynamics simulations: A comprehensive review,” Rare Met. 42(12), 3914–3944 (2023). https://doi.org/10.1007/s12598-023-02483-x

87. J. Wang, M. Zhao, S. F. Jin, D. D. Li, J. W. Yang, W. J. Hu, and W. J. Wang, “Debye temperature of wurtzite AlN determined by X-ray powder diffraction,” Powder Diffr. 29(4), 352–355 (2014). https://doi.org/10.1017/S0885715614000542

88. A. P. Thompson, H. M. Aktulga, R. Berger, D. S. Bolintineanu, W. M. Brown, P. S. Crozier, P. J. in ‘t Veld, A. Kohlmeyer, S. G. Moore, T. D. Nguyen, R. Shan, M. J. Stevens, J. Tranchida, C. Trott, and S. J. Plimpton, “LAMMPS—A flexible simulation tool for particle-based materials modeling at the atomic, meso, and continuum scales,” Comput. Phys. Commun. 271, 108171 (2022). https://doi.org/10.1016/j.cpc.2021.108171

89. Z. Huang, Q. Wang, X. Liu, and X. Liu, “First-principles based deep neural network force field for molecular dynamics simulation of N–Ga–Al semiconductors,” Phys. Chem. Chem. Phys. 25(3), 2349–2358 (2023). https://doi.org/10.1039/D2CP04697K

90. D. P. Sellan, E. S. Landry, J. E. Turney, A. J. H. McGaughey, and C. H. Amon, “Size effects in molecular dynamics thermal conductivity predictions,” Phys. Rev. B 81(21), 214305 (2010). https://doi.org/10.1103/PhysRevB.81.214305

91. D.-S. Tang and B.-Y. Cao, “Phonon thermal transport and its tunability in GaN for near-junction thermal management of electronics: A review,” Int. J. Heat Mass Transfer 200, 123497 (2023). https://doi.org/10.1016/j.ijheatmasstransfer.2022.123497

92. J. Cho, Z. Li, M. Asheghi, and K. E. Goodson, “Near-junction thermal management: Thermal conduction in gallium nitride composite substrates,” Annu. Rev. Heat Transfer 18, 7–45 (2015). https://doi.org/10.1615/AnnualRevHeatTransfer.2015011335

93. J. A. Seijas-Bellido, R. Rurali, J. Íñiguez, L. Colombo, and C. Melis, “Strain engineering of ZnO thermal conductivity,” Phys. Rev. Mater. 3(6), 065401 (2019). https://doi.org/10.1103/PhysRevMaterials.3.065401

94. A. H. Larsen, J. J. Mortensen, J. Blomqvist, I. E. Castelli, R. Christensen, M. Dułak, J. Friis, M. N. Groves, B. Hammer, C. Hargus, E. D. Hermes, P. C. Jennings, P. B. Jensen, J. Kermode, J. R. Kitchin, E. L. Kolsbjerg, J. Kubal, K. Kaasbjerg, S. Lysgaard, J. B. Maronsson, T. Maxson, T. Olsen, L. Pastewka, A. Peterson, C. Rostgaard, J. Schiøtz, O. Schütt, M. Strange, K. S. Thygesen, T. Vegge, L. Vilhelmsen, M. Walter, Z. Zeng, and K. W. Jacobsen, “The atomic simulation environment—A Python library for working with atoms,” J. Phys.: Condens. Matter 29(27), 273002 (2017). https://doi.org/10.1088/1361-648X/aa680e

95. Q. Zheng, C. Li, A. Rai, J. H. Leach, D. A. Broido, and D. G. Cahill, “Thermal conductivity of GaN, <sup>71</sup>GaN, and SiC from 150 K to 850 K,” Phys. Rev. Mater. 3(1), 014601 (2019). https://doi.org/10.1103/PhysRevMaterials.3.014601

96. F. Mu, Z. Cheng, J. Shi, S. Shin, B. Xu, J. Shiomi, S. Graham, and T. Suga, “High thermal boundary conductance across bonded heterogeneous GaN–SiC interfaces,” ACS Appl. Mater. Interfaces 11(36), 33428–33434 (2019). https://doi.org/10.1021/acsami.9b10106

97. Z. Cheng, F. Mu, T. You, W. Xu, J. Shi, M. E. Liao, Y. Wang, K. Huynh, T. Suga, M. S. Goorsky, X. Ou, and S. Graham, “Thermal transport across ion-cut monocrystalline β-Ga<sub>2</sub>O<sub>3</sub> thin films and bonded β-Ga<sub>2</sub>O<sub>3</sub>–SiC interfaces,” ACS Appl. Mater. Interfaces 12, 44943 (2020). doi:10.1021/acsami.0c11672

98. X. Li, B. Han, R. Zhu, R. Shi, M. Wu, Y. Sun, Y. Li, B. Liu, L. Wang, J. Zhang, C. Tan, P. Gao, and X. Bai, “Dislocation-tuned ferroelectricity and ferromagnetism of the BiFeO<sub>3</sub>/SrRuO<sub>3</sub> interface,” Proc. Natl. Acad. Sci. 120(13), e2213650120 (2023). https://doi.org/10.1073/pnas.2213650120

99. Y.-C. Hua, Y. Shen, Z.-L. Tang, D.-S. Tang, X. Ran, and B.-Y. Cao, “Chapter eight—Near-junction thermal managements of electronics,” Adv. Heat Transfer 56, 355–434 (2023). https://doi.org/10.1016/bs.aiht.2023.05.004
