---
title: "Spectral Features of Internal Waves in the South China Sea"
authors: "Hui Sun, Qingxuan Yang, Jianing Li, Wei Zhao, Jiwei Tian"
journal: "Journal of Physical Oceanography"
doi: "10.1175/jpo-d-24-0098.1"
published: "2025-6"
source: "ams_pdf"
acquisition:
  provider: "ams"
  route: "browser_pdf"
  representation: "pdf"
  transport: "browser"
  fallback_used: true
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 22889
---

# Spectral Features of Internal Waves in the South China Sea

**Abstract.** The close causal link between internal waves (IWs) and IW-driven mixing highlights the importance of investigating IW spectra, especially since IW spectral features vary significantly under different dynamics. In this study, we comprehensively examine the three-dimensional structures of IW spectral levels and their associated features in the South China Sea (SCS), using conductivity–temperature–depth (CTD) and lowered acoustic Doppler current profiler (LADCP) measurements collected simultaneously. We find that the Luzon Strait has higher shear and strain spectral levels compared to the central SCS, but the opposite is true for the shear-to-strain ratio R ω . The shear spectral level shows a more significant increasing trend with depth than the strain spectral level. This results in elevated R ω values in the deep SCS, indicating a substantial presence of near-inertial IWs (NIWs) there, which are always accompanied by strain spectra featuring a pronounced high wavenumber peak and flatter displacement spectra. The analysis of a publicly available numerical simulation output further reveals two main regions of abundant deep-ocean NIWs in the SCS, namely, the region between 11° and 15°N and that around the Xisha Islands, mainly due to the parametric subharmonic instability of diurnal internal tides, wave–eddy interaction, and the breaking and dissipation of internal lee waves. Moreover, we obtain a relationship between R ω and the slope of displacement spectrum q ξ , , which offers novel insights for improving finescale parameterization based solely on strain. These results serve as an inspiration to explicitly link the IW behavior to the finescale parameterization in different regions globally. Significance Statement Internal wave spectra, which reveal how the internal wave energy is distributed across different spatial and temporal scales, play a crucial role in understanding internal wave behaviors and the resulting mixing they induce. This forms the basis for parameterizing internal wave-driven mixing, which is essential for the vertical transports and redistributions of momentum, energy, nutrients, and dissolved gases. Given that spectral features exhibit significant variations under diverse dynamics, we examine three-dimensional structures of internal wave spectra and their associated features in the South China Sea, where internal waves coexist with various multiscale processes. Our findings reveal two deep-sea regions abundant with near-inertial internal waves. We then proceed to propose a formula for deriving a parameter crucial for this parameterization to be used in mapping global ocean mixing.

717 

JUNE 2025 

S U N E T A L . 

# Spectral Features of Internal Waves in the South China Sea 

HUI SUN,<sup>a,b</sup> QINGXUAN YANG ,<sup>a,b,c</sup> JIANING LI,<sup>a,b</sup> WEI ZHAO,<sup>a,b,c</sup> AND JIWEI TIAN<sup>a,b,c</sup> 

aState Key Laboratory of Physical Oceanography, Frontier Science Center for Deep Ocean Multispheres and Earth System (FDOMES), Ocean University of China, Qingdao, China b Sanya Oceanographic Institution, Ocean University of China, Sanya, China c Laoshan Laboratory, Qingdao, China 

(Manuscript received 1 July 2024, in final form 12 February 2025, accepted 10 March 2025) 

ABSTRACT: The close causal link between internal waves (IWs) and IW-driven mixing highlights the importance of investigating IW spectra, especially since IW spectral features vary significantly under different dynamics. In this study, we comprehensively examine the three-dimensional structures of IW spectral levels and their associated features in the South China Sea (SCS), using conductivity–temperature–depth (CTD) and lowered acoustic Doppler current profiler (LADCP) measurements collected simultaneously. We find that the Luzon Strait has higher shear and strain spectral levels compared to the central SCS, but the opposite is true for the shear-to-strain ratio Rv. The shear spectral level shows a more significant increasing trend with depth than the strain spectral level. This results in elevated Rv values in the deep SCS, indicating a substantial presence of near-inertial IWs (NIWs) there, which are always accompanied by strain spectra featuring a pronounced high wavenumber peak and flatter displacement spectra. The analysis of a publicly available numerical simulation output further reveals two main regions of abundant deep-ocean NIWs in the SCS, namely, the region between 118 and 158N and that around the Xisha Islands, mainly due to the parametric subharmonic instability of diurnal internal tides, wave–eddy interaction, and the breaking and dissipation of internal lee waves. Moreover, we obtain a relationship between Rv and the slope of displacement spectrum qj, Rv 5 10<sup>0:83qj13:13</sup> , which offers novel insights for improving finescale parameterization based solely on strain. These results serve as an inspiration to explicitly link the IW behavior to the finescale parameterization in different regions globally. 

SIGNIFICANCE STATEMENT: Internal wave spectra, which reveal how the internal wave energy is distributed across different spatial and temporal scales, play a crucial role in understanding internal wave behaviors and the resulting mixing they induce. This forms the basis for parameterizing internal wave-driven mixing, which is essential for the vertical transports and redistributions of momentum, energy, nutrients, and dissolved gases. Given that spectral features exhibit significant variations under diverse dynamics, we examine three-dimensional structures of internal wave spectra and their associated features in the South China Sea, where internal waves coexist with various multiscale processes. Our findings reveal two deep-sea regions abundant with near-inertial internal waves. We then proceed to propose a formula for deriving a parameter crucial for this parameterization to be used in mapping global ocean mixing. 

KEYWORDS: Internal waves; In situ oceanic observations; Clustering 

## 1. Introduction 

Internal waves (IWs) are an essential constituent of multiscale ocean dynamics. They play a pivotal role in facilitating diapycnal mixing in the ocean, which is crucial for the vertical transports and redistributions of momentum, energy, nutrients, and dissolved gases. IW-driven mixing process can significantly influence ocean stratification and exert profound impacts on ocean circulations, marine ecosystems, and the global climate system (e.g., Munk and Wunsch 1998; Alford 2003; Wunsch 2004; Friedrich et al. 2011; Deutsch and Weber 2012; Kunze 2017a,b; Eden et al. 2019; Tuerena et al. 2019; Whalen et al. 2020; de Lavergne et al. 2022; Melet et al. 2022). In the studies of IWs, the IW spectrum is a useful tool to capture the energy distribution of the IW field across a wide range of spatial and temporal scales. It can also provide insights into spectral energy transfer (due to weakly nonlinear wave–wave interactions) among IWs with different frequencies or wavenumbers, which are closely linked to the intensity 

Corresponding author: Qingxuan Yang, yangqx@ouc.edu.cn 

of IW-driven mixing. The finescale parameterizations commonly used to estimate IW-driven mixing are originally built on this basis (e.g., Gregg 1989; Polzin et al. 1995; Gregg et al. 2003; Henyey et al. 1986). 

The parametric subharmonic instability (PSI), induced diffusion (ID), and elastic scattering (ES) are three classes of resonant triad (3 wave) interactions (McComas and Muller¨ 1981). Among these, researchers have paid the most attention to the PSI. The PSI is characterized by the decay of a lowwavenumber “parent” wave into a pair of nearly identical high-wavenumber “daughter” waves with frequencies half that of the parent wave (e.g., McComas and Muller¨ 1981; Onuki and Hibiya 2019; Olbers et al. 2020; Musgrave et al. 2022; Wu and Pan 2023). The rate at which energy is transferred through the PSI depends on the energy content of the parent wave, which is why most studies have focused on the 

Publisher's Note: This article was revised on 13 June 2025 to include improved versions of Figs. 1–11, which all had poor resolution when originally published, and to correct the appearance of the fractions in Eq. (1). 

DOI: 10.1175/JPO-D-24-0098.1 

Ó 2025 American Meteorological Society. This published article is licensed under the terms of the default AMS reuse license. For information regarding reuse of this content and general copyright information, consult the AMS Copyright Policy (www.ametsoc.org/PUBSReuseLicenses). 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

718 

VOLUME 55 

J O U R N A L O F P H Y S I C A L O C E A N O G R A P H Y 

PSI of internal tides (ITs), in particular the energetic diurnal K1 tide and semidiurnal M2 tide. Moreover, the PSI becomes particularly relevant when it transfers energy toward the local Coriolis frequency f, where the group velocity tends to approach zero and there is potential for energy buildup and breaking. Therefore, special attention is paid to the critical latitude, where the frequency of ITs is twice that of f. The following is a simple explanation of ID and ES, based on the review by Musgrave et al. (2022). The interaction of a low-frequency, low-wavenumber wave with two waves of much higher frequencies and wavenumbers, known as ID, primarily influences interactions in the highfrequency, high-wavenumber part of the spectrum. The process of ES involves two high-frequency waves, one propagating energy upward and the other downward, along with a third lowfrequency wave that has nearly twice the vertical wavenumber as the first two waves. During their interaction, energy is transferred from the more energetic of the two high-frequency waves to the less energetic one until their energy levels are equal, helping remove vertical asymmetries in the spectrum. A recent study by Dematteis et al. (2024) revealed that for ID, the energy cascade occurs directly in both wavenumber and frequency; for PSI, it is direct in wavenumber but slightly inverse in frequency; whereas for ES, it is direct in frequency but slightly inverse in wavenumber. 

The landmark Garrett–Munk (GM) spectral model (Garrett and Munk 1972, 1975; Cairns and Williams 1976; Munk 1981) is indispensable when discussing the IW spectrum. The model is based on empirical analysis of observations at site D in the western North Atlantic, which reveal that IW energy follows a power-law variation with respect to its frequency and wavenumber, specifically obeying v<sup>22</sup> and k<sup>2</sup> z<sup>2</sup> in GM76 (a commonly used version of the GM model; Cairns and Williams 1976), respectively. Here, v is the wave frequency and kz is the vertical wavenumber. From the conventional perspective, the GM-like IW spectrum is jointly sustained by wind and tides. Recently, Chen et al. (2019) revealed that sometimes M2 tidal forcing alone is sufficient to generate such a spectrum, with the key lying in near-inertial IWs (NIWs) generated by breaking ITs and nonlinear wave–wave interaction around supercritical topography. 

As early as 1975, Wunsch (1975) raised a question regarding the spatial and temporal variability of IW spectra in specific areas (e.g., source/sink region, near western boundary current, near the equator, in upper/bottom boundary layers), in different seasons, and under tidal forcing with a neap– spring cycle. Thereafter, results based on global Argo floats suggested that the slopes of IW wavenumber spectra have the highest spatial variability and deviate most strongly from the canonical GM spectral model in the North Atlantic, northwest Pacific, and Southern Ocean (Pollmann 2020). Applying these spatially variable spectral parameters to the parameterization can effectively improve estimates of turbulent kinetic energy (TKE) dissipation rate (Polzin and Lvov 2011; Pollmann 2020; Dematteis et al. 2024). Meanwhile, Le Boyer and Alford (2021) observed that the kinetic energy within the IW continuum follows a seasonal cycle in most places, indicating a wind-driven near-inertial source. They also examined variations in the slope of frequency spectra across different ocean basins and compared their probability distributions. An inference can be reached that the uncertainties in spectral parameters can impact the predictive 

capabilities of finescale parameterizations. These studies have significantly enhanced our comprehension of the spatiotemporal variability of IW spectral features. 

Despite growing attention to this issue, a gap remains in exploring the spatiotemporal variability of IW spectral features in the largest marginal sea of the western Pacific, namely, the South China Sea (SCS). The SCS is well known for the frequent occurrences of various types of IWs and for the coexistence of multiscale dynamic processes such as large-scale circulation, mesoscale eddies, submesoscale motions, IWs, and microscale mixing. The enhanced mixing in the SCS (e.g., Tian et al. 2009; Yang et al. 2016), mainly driven by IWs, plays a key role in maintaining meridional overturning circulation in the SCS and facilitating water exchange between the SCS and western Pacific Ocean (e.g., Qu et al. 2006; Zhou et al. 2014). Earlier studies indicated that the IW field exhibits significant spatial heterogeneity throughout the SCS. Notably, energetic ITs are observed primarily in the Luzon Strait and northeastern SCS, while relatively weaker ITs are present in the central and southern SCS (e.g., Xu et al. 2016). Furthermore, the interaction between active mesoscale eddies and topography surrounding the Zhongsha and Xisha Islands plays a crucial role in triggering intense NIWs in the deep layers (Yang et al. 2019; Hu et al. 2020). All these aspects result in more complex variations of the IW spectral features in the SCS. However, our prior knowledge of it is based on some “snapshots,” e.g., the spectra presented by Sun et al. (2019) using 4-day observations; thus, we still lack an understanding of its full spatial and temporal variability. 

In this paper, using several hundred conductivity–temperature– depth (CTD) and lowered acoustic Doppler current profiler (LADCP) profiles covering large areas of the SCS, we investigate the spatial structures and statistical regularities of IW spectral features (section 3), after we present the data and methodology in section 2. A discussion on strong NIWs in the deep SCS is presented in section 4, followed by a summary and discussion in section 5. We have summarized all parameters and their definitions in the appendix for the convenience of the reader. 

## 2. Data and methods 

## a. In situ observations 

The observational data used in this study are the same as in Yang et al. (2016), which were collected in the SCS between 2005 and 2012. We selected 405 profiles from 276 stations, where CTD and LADCP measurements were conducted simultaneously. The CTD instruments employed are the SBE 911plus/917plus and SBE 25, manufactured by Sea-Bird Electronics, working at frequencies of 24 and 8 Hz, respectively. Therefore, the raw CTD profiles have a resolution of approximately 1/24 m (SBE911) and 1/8 m (SBE25) when the dropping velocity is around 1 m s<sup>21</sup> . We then processed them by applying a smoothing window of 2 m and conducted subsequent segmental strain spectral analysis using the CTD profiles with a vertical interval of 2 m. The 300-kHz WorkHorse Sentinel LADCP (Teledyne RD Instruments) was used, sampling at a frequency of 1 Hz, with inconsistent vertical bin sizes (number of vertical layers), i.e., 4 m (25 layers), 8 m (15 layers), 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

719 

JUNE 2025 

S U N E T A L . 


![](10.1175_jpo-d-24-0098.1_assets/phoc-JPO-D-24-0098.1-b993d93c15.pdf-0003-03.png)


FIG. 1. Station locations in the SCS, with gray and blue contours representing 1000- and 3000-m isobaths, respectively. Red circles represent stations where both CTD and LADCP observations were conducted simultaneously. 

and 10 m (12 layers). To facilitate subsequent segmental shear spectral analysis, we uniformly interpolated the shear profiles to have a consistent vertical interval of 10 m. 

These profiles were mostly collected in the deep basins of the northern and central SCS (Fig. 1), with most of them measuring the entire water column. The observation dates of these profiles span from January to September as follows: January (1.7%), March (8.4%), April (22.7%), May (4.9%), June (3.5%), July (25.4%), August (27.7%), and September (5.7%). These guarantee a comprehensive investigation of the IW spectral features in the SCS. 

## b. Model simulation 

The hourly numerical simulation outputs from MITgcm LLC4320 (https://data.nas.nasa.gov/ecco) are used to analyze deep-ocean NIWs in the SCS. This global simulation of the ocean state, running from September 2011 to November 2012, uses a latitude–longitude polar cap (LLC) grid with a high spatial resolution of 1/488. In the vertical, it has 90 layers with a z-level coordinate. The vertical grid increases gradually from the surface to the bottom: a few meters within the surface mixed layer, expanding to 100 m at a depth of 2200 m, to 200 m at a depth of 3600 m, and to 300 m at a depth of 4800 m. The LLC4320 model is run with eight major tidal constituents, including four diurnal ones (K1, O1, P1, and Q1) and four semidiurnal ones (M2, S2, N2, and K2); thus, it resolves ITs and admits IW variability. For model configuration details, readers are referred to Rocha et al. (2016a,b). 

We focus on the region of 1108–1228E, 108–228N. The baroclinic velocity field is derived by subtracting the depth-averaged field from the total velocity field. Bandpass filtering is then applied to the baroclinic velocity field to separate NIWs, diurnal ITs, and semidiurnal ITs, using respective filtering bands of [0.95–1.15]f, [0.9–1.1]vD1, and [0.9–1.1]vD2. Here, f represents the local Coriolis frequency and vD1 and vD2 denote diurnal 

and semidiurnal frequencies, respectively. Since the frequency of ITs is equal to that of astronomical tides, the filtering band for obtaining ITs is typically chosen symmetrically around astronomical tidal frequencies, such as our choice [0.9, 1.1]. However, it is important to note that if the filtering band for diurnal ITs is too wide, there might be partial overlap with that of NIWs at the latitude of 228N, which could affect the effective separation of these two signals. For the NIWs, we use a nonsymmetric filtering band [0.95–1.15]f rather than a symmetric one centered at f. This is because the NIWs propagate equatorward on the b plane from their generation site, leading to a wave frequency slightly higher than the local Coriolis frequency. The frequency shift of the NIWs away from the local Coriolis frequency varies with latitude, initial horizontal wavenumbers, and vorticity of the background flow (Kunze 1985; Young and Jelloul 1997; Garrett 2001; Conn et al. 2025). Our band is narrower than those used in other studies, e.g., [0.8–1.25]f in Alford (2003), to better distinguish NIWs from diurnal tides. The subinertial velocities are obtained by low-pass filtering the total velocity field, with a cutoff frequency set as the minimum between 1/3 cpd and 0.5f. The former (1/3 cpd) allows to select signals with periods shorter than a few days as the subinertial flow; however, there is some overlap with the filtering band of NIWs at the latitude of 108N, so we use a smaller value between 1/3 cpd and 0.5f. 

## c. IW spectra calculation 

The temperature, salinity, and velocity profiles are divided into 320-m segments, with a 240-m overlap, to obtain a large number (more than 10 000) of segments for the subsequent cluster analysis. We chose segments starting from the maximum measuring depth, rather than from the surface, and stopping at a depth shallower than ;100 m. This cutoff depth for the upper end of the segment is comparable with that in Whalen et al. (2012, 2015). Thus, this study focuses exclusively on the water column within a depth range between at least ;100 m (at most ;170 m) and the maximum measuring depth, to exclude the contamination of IW spectrum by nonIW signals in the upper layer (e.g., surface waves, Ekman flow, and Langmuir circulation). 

These segments are used to calculate IW spectra, which are subsequently clustered through unsupervised machine learning (see section 2e). The IW shear and������������������������strain are computed for each segment using Vz 5 �(­u/­z)<sup>2</sup> 1 (­y/­z)<sup>2</sup> and jz 5 (N<sup>2</sup> 2 N 2)/N 2, respectively, where N is the buoyancy frequency and N 2 is a quadratic fit of N2. Following Kunze et al. (2006), the IW shear and strain segments are windowed at both ends with 10% sin<sup>2</sup> tapers and then used to calculate their power spectral density, namely, the shear spectrum SVz/N<sup>(k</sup> z<sup>) and</sup> strain spectrum Sjz (kz), respectively, where kz denotes the vertical wavenumber. These spectra are then corrected and integrated to obtain the buoyancy–frequency–normalized shear variance and strain variance via hVz<sup>2i/</sup> N 2 5 �kk12<sup>SV</sup> z<sup>/</sup> N<sup>S</sup> c1<sup>dk</sup> z<sup>and</sup> hj<sup>2</sup> z<sup>i 5</sup> �kk13<sup>Sj</sup> z<sup>Sc2dkz, respectively.</sup> The shear spectral correction Sc1(kz) 5 1/(TraTbinTsupTtilt) takes into account smoothing associated with range averaging Tra 5 sinc<sup>2</sup> (kzDzt/2p)sinc<sup>2</sup> (kzDzr/2p), depth binning 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

720 

VOLUME 55 

J O U R N A L O F P H Y S I C A L O C E A N O G R A P H Y 


![](10.1175_jpo-d-24-0098.1_assets/phoc-JPO-D-24-0098.1-b993d93c15.pdf-0004-03.png)


FIG. 2. (a) IW shear and strain spectra and (b) IW velocity and displacement spectra, for three segments: segment 1 (16.758N, 116.708E, 1032–1352 m), segment 2 (14.108N, 116.998E, 1033–1353 m), and segment 3 (14.108N, 116.998E, 3273–3593 m). The horizontal coordinates are the vertical wavenumber (bottom axis) and the corresponding vertical wavelength (top axis). In (a), the observed SVz/N<sup>andS</sup> jz<sup>are</sup> represented by the solid orange and sky blue curves, respectively, while the corresponding GM results are shown as dotted red and blue curves, respectively. The dashed orange curve represents 3 times the shear noise spectrum. In (b), the solid orange and skyblue curves represent the observed SV/N<sup>and Sj, respectively. The fitted Sj is shown by the dotted black curve, with the resulting low-wavenumber slope</sup> pj and high-wavenumber slope qj labeled. 

Tbin 5 sinc<sup>2</sup> (kzDzg/2p), superensemble preaveraging Tsup 5 sinc<sup>2</sup> (kzDzs/2p), and instrument tilting Ttilt 5 sinc<sup>2</sup> (kzd<sup>′</sup> /2p) (Thurnherr 2012). Here, Dzr is the vertical bin size set for LADCP deployment, Dzt is the LADCP transmit pulse length (usually Dzt 5 Dzr), Dzg is the vertical depth interval for the output shear profile, and Dzs is the superensemble preaveraging interval (often chosen to be equal to Dzg). The d<sup>′</sup> is a length scale that depends on the instrument tilt statistics. We adopt d<sup>′</sup> 5 11.8 m following Thurnherr (2012). The strain spectral correction Sc2(kz) 5 1/sinc<sup>2</sup> (kzDzstrain/2p) considers the first differencing inherent in the gradient, where Dzstrain is the vertical interval for the output strain profile. The integrated wavenumber bands are set as follows: k1 5 2p/320 rad m<sup>21</sup> , where 320 m is the segment 

length; k2 is determined as a wavenumber at which the ratio of measured shear spectrum to instrument shear noise spectrum [Snoise 5 (0:032<sup>2</sup> /120)(kz<sup>2/</sup> N 2)Sc1; Polzin et al. (2002)] is three (Naveira Garabato et al. 2004; Waterman et al. 2014; Liang et al. 2018). For the example shown in Fig. 2a, k2 stays around 0.3 rad m<sup>21</sup> . In other studies, the upper limit k2 is determined by the saturated spectrum (Kunze et al. 2006) or jointly by the noise spectrum and saturated spectrum (Takahashi and Hibiya 2019). There is no essential difference between the shear variances obtained from the two methods. The k3 is determined by �kk13<sup>Sj</sup> z<sup>dkz# 0:1toavoidcontamina-</sup> tion by instrument noise at higher wavenumbers. The shear-to-strain ratio is calculated as Rv 5 hVz<sup>2i</sup> ��N 2hj2z<sup>i</sup> �. Since Rv ffi �v<sup>2</sup> 1 f<sup>2</sup> �/ v�<sup>2</sup> − f<sup>2</sup> � under the single-wave and 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

721 

JUNE 2025 

S U N E T A L . 

hydrostatic (v ,, N) approximations, a large value of Rv always indicates dominance of NIWs. The multiwave form of Rv is obtained by averaging the single-wave form from f to N, using the normalized IW frequency spectrum as weights (Sun et al. 2024). For the GM model, Rv 5 3. However, in the real ocean, the IW frequency spectrum deviates from the GM one, resulting in different values of Rv. 

Figure 2a shows three examples of the observed and GMderived SVz/N<sup>andS</sup> jz<sup>.BothGM-derivedS</sup> Vz/N<sup>andS</sup> jz<sup>show</sup> minor variation with kz. The observed Sjz closely matches the magnitude of the GM-derived one, but there are significant differences in its shape: For segment 1, it is flat with the wavenumber; for segment 2, there is a hump in the lowwavenumber band; and for segment 3, it is lower in the lowwavenumber band and higher in the high-wavenumber band. In addition, there is a discrepancy between the observed and GMderived SVz/N<sup>;theformerconsistentlyexceedsthelatter</sup> and exhibits an increasing trend with kz. The shape of the observed SVz/N<sup>remainsrelativelyconsistentacrosssegments,</sup> except for a change in its level relative to that of GM. Consequently, it is reasonable to infer that the observed Rv value will be greater than its GM value of 3. These examples enhance our understanding of the variability in the IW spectral shape in the SCS and highlight the necessity of conducting cluster analysis on them. 

## d. Fitting of the IW spectra using the GM model 

The spectral slope is a fundamental parameter that characterizes the IW spectrum. In the classical GM spectral model, spectra of both velocity and displacement fields obey a power law of k<sup>2</sup> z<sup>2. Here, we obtained the IW velocity and displacement spec-</sup> tra according to SV/N<sup>(k</sup> z<sup>) 5 k2</sup> z<sup>2S</sup> Vz/N and Sj(kz) 5 kz<sup>22S</sup> jz<sup>,</sup> respectively. The examples shown in Fig. 2b illustrate that, limited by the vertical resolution of the LADCP data, the velocity spectrum SV/N<sup>(k</sup> z<sup>) only partially resolves the IWs</sup> within the high-wavenumber range. Therefore, only the displacement spectra Sj(kz) are fitted using 


![](10.1175_jpo-d-24-0098.1_assets/phoc-JPO-D-24-0098.1-b993d93c15.pdf-0005-07.png)


to get the IW spectral parameters, following Polzin and Lvov (2011). The undetermined IW spectral parameters in Eq. (1) include e0 (energy-related coefficient), kz∗ (vertical wavenumber scale), p (low-wavenumber slope), and q (high-wavenumber slope), where the parameter q is of the most interest. Figure 2b indicates that the displacement spectral slope varies among segments in the SCS. In several studies, researchers used a more simplified GM formula (essentially assuming p 5 q) to fit the entire vertical wavenumber spectral slope without distinguishing between high- and low-wavenumber slopes. For instance, Pollmann (2020) employed this method to analyze the global variation of the entire vertical wavenumber spectral slope. 

## e. Cluster analysis of the IW spectra 

The nonnegative matrix factorization (NMF) and Gaussian mixture model (GMM) algorithms available in Python’s 

scikit-learn library are used for cluster analysis on IW shear and strain spectra (Lele et al. 2023). The observed SVz/N<sup>and</sup> Sjz are first normalized by their respective variances and then further normalized by the GM shear and strain variances, respectively, which are obtained by integrating the GM spectra. 

The NMF algorithm is subsequently used to reduce dimensionality and extract the main features of the normalized SVz/N<sup>and</sup> Sjz . The NMF, as a matrix factorization technique, aims to decompose a nonnegative matrix A into the product of two simpler nonnegative matrices: Ansample3nfeature 5 Wnsample3ncomp 3 Hncomp3nfeature . The feature matrix W captures the main components in the data, while the coefficient matrix H reveals the contribution of these components to each data point. When A is our normalized spectra, nsample denotes the number of segments from all stations, nfeature denotes the length of a shear/strain spectrum, and ncomp denotes the desired number of main components to be extracted. Choosing an appropriate ncomp value is crucial in the NMF process. It can be determined by trying different ncomp values to train the NMF model and calculating the corresponding reconstruction error to evaluate how well the model reconstructs the training data. A small error indicates accurate reconstruction, while a large one suggests incomplete restoration of the training data. The reconstruction error is computed as the Frobenius norm of the matrix difference between the training data A and the reconstructed data W 3 H obtained from the fitted model. By examining the reconstruction errors for NMF results with ncomp ranging from 1 to 9 for strain spectra and shear spectra, we finally choose ncomp 5 2, which was also used by Lele et al. (2023). Note that this choice is not universally applicable; researchers should determine it based on the specific training data. 

The main components extracted from the output of the NMF are more suitable for cluster analysis than those from the original data. The NMF route for the normalized Sjz matrix is illustrated in Fig. 3a, where the reconstructed Sjz matrix obtained from the two main components is represented, which effectively captures both the magnitude and primary patterns exhibited by the normalized Sjz matrix. The NMF process for the normalized SVz/N<sup>matrix is similar.</sup> 

Next, we will perform a cluster analysis using the GMM on the NMF-generated feature matrix, which incorporates two main components of the normalized SVz/N<sup>andtwomain</sup> components of the normalized Sjz . The GMM is a generalized probabilistic model that assumes all data points are generated from a mixture (viz., combination) of a finite number of Gaussian distributions, each representing an independent cluster with unique parameters (including mean, variance, and mixture weight). Note that the term “mixture” here has no association with vertical diffusivity or TKE dissipation rate in oceanography. Instead, the mixture weight indicates the relative proportion and significance of each Gaussian distribution in the overall distribution. The optimal number of Gaussian distributions ncluster for the data is determined using the Bayesian information criterion (BIC) score (Fig. 3b). Typically, the model with the lowest BIC score is selected, as it provides the best tradeoff between model complexity and fit performance. Figure 3b shows that the BIC score decreases rapidly when ncluster , 7 but remains relatively stable when ncluster . 7. Hence, ncluster 5 7 is chosen in this study, 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

722 

VOLUME 55 

J O U R N A L O F P H Y S I C A L O C E A N O G R A P H Y 


![](10.1175_jpo-d-24-0098.1_assets/phoc-JPO-D-24-0098.1-b993d93c15.pdf-0006-03.png)


FIG. 3. (a) NMF process for the normalized Sjz matrix, with ncomp set to 2. (from left to right) The normalized Sjz matrix, the feature matrix W, the coefficient matrix H, and the reconstructed Sjz matrix, respectively. (b) BIC scores for GMM using different ncluster. 

which allows the GMM algorithm to divide the training data into seven clusters. 

The parameters of each Gaussian distribution are not preset; instead, they are determined through iterative training on the training data using the expectation–maximization (EM) algorithm. In the “E step,” the posterior probability for each data point belonging to each Gaussian distribution is computed; in the “M step,” the parameters of each Gaussian distribution according to the posterior probability are updated. This iterative procedure guarantees the convergence to a local optimum. Eventually, clustering is accomplished by assigning each data point to the Gaussian distribution with the highest posterior probability. Overall, the NMF 1 GMM clustering method combines the feature extraction capability of NMF with the probabilistic modeling capability of GMM to provide more effective clustering results. 

## 3. Distribution of IW spectral features 

## a. IW spectral level 

Figure 4 illustrates the three-dimensional structures of the observed shear variance hVz<sup>2i/</sup> N 2, strain variance hj2z<sup>i,and</sup> shear-to-strain ratio Rv. The magnitude of hVz<sup>2i/</sup> N 2 in the upper layer exhibits a noticeable horizontal spatial inconsistency. Specifically, the spectra in the Luzon Strait [around O(10<sup>0</sup> )] are at least one order of magnitude higher than those in the central SCS [around O(10<sup>21</sup> )] (Fig. 4a). In the vertical, there is a strong increasing trend of hVz<sup>2i/</sup> N 2 with depth at 

almost all stations, ranging from around O(10<sup>21</sup> ) (in the central SCS) or O(10<sup>0</sup> ) (in the Luzon Strait) in the upper layer to approximately O(10<sup>3</sup> ) in the deeper layer. The hj<sup>2</sup> z<sup>ivaluesin</sup> the Luzon Strait consistently exhibit an elevation [;O(10<sup>0</sup> )] throughout the entire water column, with a slight vertical variation only. In contrast, the overall hj<sup>2</sup> z<sup>ivaluesinthecentral</sup> SCS are relatively low [mostly around O(10<sup>21</sup> )], but slightly higher values (up to 1) can be seen within the column between 1500 and 3000 m compared to the layers above and below it (Fig. 4b). 

The value of Rv also demonstrates a significant increasing trend with depth, ranging from O(10<sup>0</sup> ) in the upper layer to O(10<sup>3</sup> ) in the deeper layer (Fig. 4c). This is due to the vertical increase of hVz<sup>2i/</sup> N 2 over several orders of magnitude [from O(10<sup>21</sup> ) in the upper layer to O(10<sup>3</sup> ) in the deeper layer], while there is only a slight vertical variation in hj<sup>2</sup> z<sup>i as opposed</sup> to that in hVz<sup>2i/</sup> N 2. Consequently, the vertical pattern of Rv is primarily regulated by the increasing trend of hVz<sup>2i/</sup> N 2. Additionally, lower values of Rv are found in the Luzon Strait, primarily attributed to higher values of hj<sup>2</sup> z<sup>itherecompared</sup> to those in the central SCS. The statistical analysis indicates that the majority of Rv values are concentrated within the range between 3 and 10; nevertheless, there are also a few extreme values (reaching up to 10<sup>2</sup> or even 10<sup>3</sup> ) (Fig. 4d). When combined with Fig. 4c, it becomes apparent that these extreme Rv values are predominantly distributed in the deep layer of the central SCS, where the stratification N 2 tends to be very small, approximately at a magnitude of O(10<sup>27</sup> ) s<sup>22</sup> . Our 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

723 

JUNE 2025 

S U N E T A L . 


![](10.1175_jpo-d-24-0098.1_assets/phoc-JPO-D-24-0098.1-b993d93c15.pdf-0007-03.png)


FIG. 4. Three-dimensional structures of (a) hVz<sup>2i/</sup> N 2 (shear variance), (b) hj2z<sup>i(strainvari-</sup> ance), and (c) Rv (shear-to-strain ratio). (d) Histogram of Rv. The Luzon Strait and the central SCS are marked by black and purple boxes, respectively. 

previous study indicated that Rv depends not only on N but also on f at the global scale as Rv ~ |N/f|<sup>20.7</sup> (Sun et al. 2024). The current study further emphasizes that assuming a constant Rv value for Gregg–Henyey–Polzin (GHP) finescale parameterization based solely on strain is inappropriate, not only globally but even within basin-scale regions. In addition, it is therefore reasonable to consider whether an abundance of near-inertial motions thrives in the deep SCS, which is beyond our current understanding. 

## b. IW spectral shape 

## 1) SPECTRAL SLOPE 

Let us focus on the high-wavenumber slope of the displacement spectrum qj obtained through the fitting method given in section 2d. A higher (lower) value of qj indicates a flatter 

(steeper) displacement spectrum. In GM76, qj 5 22. However, in the SCS, the actual values of qj deviate from the GM76 value and show clear spatial variability (Figs. 2b and 5). The three-dimensional structure of qj (Fig. 5a) resembles that of Rv (Fig. 4c), with qj values ranging between 23 and 22.5 in the Luzon Strait, generally lower than those in the central SCS where numerous qj values exceed 22.5 or even reach up to 21, although a few are as small as 23. Unlike Rv, there is no clear vertical trend with depth for qj; elevated values (as high as 21) are found in the bottom layer and occasionally at other depths. 

Statistical analysis reveals that the qj values in the SCS exhibit a surprising adherence to a normal distribution, ranging from 24 to 21, with a mean of 22.4 and a standard deviation of 0.5 (Fig. 5b). In contrast, the global distribution of qj (Fig. 5c; 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

724 

VOLUME 55 

J O U R N A L O F P H Y S I C A L O C E A N O G R A P H Y 


![](10.1175_jpo-d-24-0098.1_assets/phoc-JPO-D-24-0098.1-b993d93c15.pdf-0008-03.png)


FIG. 5. (a) Three-dimensional structure of qj (high-wavenumber slope of the displacement spectrum). The Luzon Strait and the central SCS are marked by black and purple boxes, respectively. (b) Histogram of qj values in the SCS (blue bars), fitted using a normal distribution (black curve), with labels for the mean value and standard deviation. (c) Histogram of qj values for the water column of 300–2000 m of the global ocean (blue bars), fitted using a t location–scale distribution (black curve), with labels for the location parameter, scale parameter, and shape parameter. The global qj dataset is from Pollmann (2020, 2022), which does not distinguish between high- and low-wavenumber slopes, essentially assuming pj 5 qj. 

Pollmann 2020, 2022) is more concentrated, primarily falling between 22.5 and 21.0. A comparison of these findings reveals significant spatial variability of the IW field in the SCS. In addition, the global distribution of qj does not follow a normal distribution. However, it can be fitted by a t location–scale distribution, with a location parameter of 21.8, a scale parameter of 0.1, and a shape parameter of 1.5. The traditional t distribution is symmetric with respect to the y axis and has one parameter}degrees of freedom}to control its shape. If it is shifted or scaled, it becomes a t location–scale distribution. In simpler terms, the relationship between the t location–scale distribution and the traditional t distribution is similar to the relationship between a normal distribution and a standard normal distribution. 

## 2) SPECTRAL CLUSTER 

The fitted spectral slope, while capturing the power-law relationship between IW spectral energy and vertical wavenumber, may not fully provide the multiple spectral peaks at various vertical wavenumbers, potentially losing some crucial spectral information (Fig. 2b). Therefore, in addition to examining the spectral slope, we also employ a machine learning approach (section 2e) to examine the categorization and distribution of spectral appearances in the SCS in this paper. 

Figure 6a reveals the percentage of each cluster, and Figs. 6b and 6c show the cluster-averaged results for normalized and unnormalized shear and strain spectra, respectively. Clusters 1–5 collectively account for more than 90% of the total, with individual contributions of 27.7%, 17.2%, 23.9%, 5.6%, and 17.9%, respectively. On the other hand, clusters 6–7 only contribute to less than 10% of the total (Fig. 6a). The clustering of the normalized shear spectra (dashed curves in Fig. 6b) reveals a consistent increasing trend with kz for all but cluster 2; however, the increasing extent varies from cluster to cluster. Regarding the unnormalized shear spectra (dashed curves in Fig. 6c), although the overall spectral shape remains similar (increasing with kz), there are obvious differences across clusters in both the spectral level and increasing extent. The clustering of the normalized strain spectra (solid curves in Fig. 6b) indicates that clusters 1–5 share similar shapes, with a peak around kz 5 1 3 10<sup>21</sup> rad m<sup>21</sup> . The spectral level increases with kz when kz , 1 3 10<sup>21</sup> rad m<sup>21</sup> and decreases with kz when kz . 1 3 10<sup>21</sup> rad m<sup>21</sup> . In contrast, clusters 6–7 exhibit a more pronounced peak at higher wavenumbers (around 5–10 3 10<sup>21</sup> rad m<sup>21</sup> ). In the case of unnormalized strain spectra (solid curves in Fig. 6c), clusters 1–5 maintain consistent shapes with a peak at low wavenumbers (around 1 3 10<sup>21</sup> rad m<sup>21</sup> ), albeit with a slight decrease in spectral level from cluster 1 to cluster 5; however, there are marked 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

725 

JUNE 2025 

S U N E T A L . 


![](10.1175_jpo-d-24-0098.1_assets/phoc-JPO-D-24-0098.1-b993d93c15.pdf-0009-03.png)


FIG. 6. Results of the cluster analysis. (a) Pie chart showing the percentage of each cluster. (b) Cluster-averaged results for normalized shear spectra (dashed curves) and strain spectra (solid curves). (c) As in (b), but for unnormalized spectra. (d) Three-dimensional structure of cluster number. The Luzon Strait and the central SCS are marked by black and purple boxes, respectively. (e)–(g) Ridgeline plots of the longitude, latitude, and located depth for the segments of each cluster, respectively. A ridgeline plot, also known as a joyplot, displays a sequence of probability density distributions of multiple variables in a compact and informative way. These distributions are aligned on their x axis and offset vertically for easy comparison. 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

726 

VOLUME 55 

J O U R N A L O F P H Y S I C A L O C E A N O G R A P H Y 


![](10.1175_jpo-d-24-0098.1_assets/phoc-JPO-D-24-0098.1-b993d93c15.pdf-0010-03.png)


FIG. 7. Relationship between Rv and qj. (a),(b) Ridgeline plots of Rv and qj for different clusters, respectively. (c) Scatterplot of Rv against qj (color dots), with black squares representing bin-averaged results and a black line representing the fitted result. 

differences in clusters 6–7: the spectral level at low wavenumber sharply decreases, while the spectral peak notably shifts toward higher wavenumbers (around 5–10 3 10<sup>21</sup> rad m<sup>21</sup> ). Note that the high-wavenumber peak around 5–10 3 10<sup>21</sup> rad m<sup>21</sup> would not be identified without a high enough CTD resolution. 

The spatial distribution of each cluster is shown in detail in Figs. 6d–g. Horizontally, clusters 1–4 occur predominantly near the Luzon Strait (1208–1228E, 188–228N); in contrast, clusters 5–7, especially cluster 7, are mostly found in the central SCS (Figs. 6d–f). Furthermore, there is a notable disparity in the probability density distribution of these clusters in terms of depth. Clusters 1–4 all exhibit a “unimodal” feature, yet each cluster shows a distinct distribution pattern (Fig. 6g). Cluster 1 is primarily distributed above 3000 m, with the highest probability occurring at 1000 m; cluster 2 exists mainly at depths shallower than 1500 m, with the highest probability occurring at 500 m; and clusters 3 and 4 are predominantly distributed above 4000 m, with their respective highest probabilities at 2000 and 2500 m. Clusters 5–6, on the other hand, exhibit a “bimodal” feature, with probability density peaking at 500 m and then again at 2500 m (cluster 5) or 3500 m (cluster 6). The difference lies in that the first peak of cluster 5 

exceeds its second one, whereas the opposite is true in cluster 6. Cluster 7 reaches its maximum value of probability density only around 4000 m, and we relate this to the much smaller amount of data available for this cluster compared to the others. 

By combining Figs. 4–6, it becomes evident that the strain spectrum with a dominant high-wavenumber peak (clusters 6–7) tends to appear in deeper ocean areas, which also coincides with the location of elevated values of Rv and qj. This implies that the importance of clusters 6–7 should not be underestimated despite only accounting for less than 10% of the total samples (Fig. 6a), and this also prompts us to further explore the intrinsic connection among these variables (Fig. 7). 

The ridgeline plot of Rv (Fig. 7a) closely resembles that of the primary existing depth of each cluster (Fig. 6g), showing a gradual increase in Rv across clusters, from O(10<sup>0</sup> )–O(10<sup>1</sup> ) for cluster 1 to O(10<sup>3</sup> )–O(10<sup>4</sup> ) for cluster 7. This resemblance can be easily comprehended as Fig. 4c, which visually illustrates a robust positive correlation between Rv and depth. Similarly, the ridgeline plot of qj (Fig. 7b) reveals an analogous trend, with qj steadily increasing from cluster 1 (between 24 and 22) to cluster 7 (larger than 21). The reason for this 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

727 

JUNE 2025 

S U N E T A L . 

tendency is that Sj inevitably becomes flatter (i.e., qj increases), while the low-wavenumber peak diminishes and the high-wavenumber peak becomes more apparent from cluster 1 to cluster 7 (Fig. 6c). The magnitude of Rv is directly related to the relative strengths of the NIWs’ peak and the internal tidal peak in the IW frequency spectrum, rather than being linked through the IW wavenumber spectrum. However, the IW frequency spectrum and wavenumber spectrum represent two different domains of the same IW field, which are inherently connected through the IW dispersion relation. Therefore, it can be inferred that Rv must also be correlated with the shape of the IW wavenumber spectrum, a point overlooked by existing studies (e.g., Sheen et al. 2013; Ijichi and Hibiya 2015; Howatt et al. 2021; Ferris et al. 2022). The scatterplot shown in Fig. 7c demonstrates a remarkable positive correlation (correlation coefficient 5 0.5) between Rv and qj. By fitting the data, a quantitative relationship is derived as follows: Rv 5 10<sup>0:83qj13:13</sup> . More discussion about this formula is provided in section 5. 

The above clustering results focus solely on the shape features of the IW spectra. However, extra variables such as vertical diffusivity or TKE dissipation rate are not involved. As for the potential impact of including Rv in the training data on the conclusions, we are confident that this will not cause essential changes. As illustrated in Fig. 7a, there is a gradual increase in Rv from cluster 1 to cluster 7, indicating an intrinsic link between Rv with the variables already incorporated in the training data. 

## 4. Discussion on strong NIWs in the deep SCS 

Section 4 further validates the conclusion highlighted in section 3, which implies the presence of significant NIWs in the deep layer of the SCS. The difference is that in section 3, we discuss the NIWs based on IW wavenumber spectra and Rv. In contrast, when it comes to the high-resolution LLC4320 output used in section 4, its spatial resolution is insufficient to resolve the finescale IW field (thus making variables such as Rv, qj, etc., uncomputable), but its temporal resolution can resolve the NIWs and ITs. Consequently, we compared the relative strengths of NIW energy and internal tidal energy to qualitatively assess whether strong NIWs and large Rv may potentially exist. The signals of the NIWs, diurnal, and semidiurnal ITs are extracted from the LLC4320 output (section 2b). Then, the ratio between the kinetic energy of NIWs and that of diurnal and semidiurnal ITs is defined as rE 5 hENIWi/ h� ED1i 1 hED2i�, with h?i representing daily averaged results. A higher value of rE suggests an elevated Rv value. 

All analyses in section 4 focus on the near-bottom layer (at a height of approximately 500 m above the ocean bottom). Given that the LLC4320 output has 90 nonuniform vertical layers, we use the available data closest to 500 m above the ocean bottom in each grid cell. Statistically, the resulting bias for depth selection is less than 50 m for areas shallower than 3000 m and no more than 150 m in deeper water. Based on a full-depth analysis conducted at two representative locations, this bias does not significantly affect our subsequent conclusions (see the discussion at the end of section 4). 

a. Spatial and temporal properties 

The snapshots of rE at different dates show significant variations in both space and time, ranging widely from O(10<sup>22</sup> ) to O(10<sup>1</sup> ) (Figs. 8a–f). On 14 September 2011, small patches of rE ; O(10<sup>0</sup> ) appeared sporadically. On 9 October 2011, there was a substantial area near the Xisha Islands where rE reached as high as O(10<sup>1</sup> ); however, it faded by 24 November 2011. Furthermore, the latitudinal band between 118 and 158N always exhibited enhanced rE values, particularly in its eastern and western parts. Moreover, within this latitudinal band, the values of rE changed significantly with time. For instance, on 12 March 2012, a dominant area extending from 1178 to 1208E showed rE values reaching up to O(10<sup>1</sup> ). Moreover, there was no extensive region with elevated rE values west of the Luzon Strait; only a few fragments can be found. 

Statistical analysis is conducted on the time series of rE at each grid, including the median and maximum values, and the occurrence frequency for rE . 0.5. Their distribution maps (Figs. 8g–i) suggest that the regions with high rE medians and maxima are in the eastern and western parts of the latitudinal band between 118 and 158N, the Xisha Islands, and west of the Luzon Strait, which are consistent with the above snapshot results. For convenience, these regions are denoted as regions A–D (see Fig. 8g). The map of median values of rE (Fig. 8g) shows that regions A and B are the strongest, followed by region C, while region D is the weakest. Remarkably, within region A, most locations have median values exceeding 1, indicating the predominance of stronger NIWs over ITs for more than half of the analyzed period. In contrast, in regions C and D, the median values are only around 0.1, signifying the consistent dominance of ITs over NIWs in these two areas. The same conclusion can also be drawn from the map of the occurrence frequency for rE . 0.5 (Fig. 8i). The occurrence frequency exceeds 70% in regions A and B, reaches 30% in region C, but decreases to only about 10% in region D. The map of the maximum values of rE (Fig. 8h), however, shows slightly different rankings among these four regions, with region C emerging as the most dominant, followed by regions A and B, while region D is the weakest. This implies the rE enhancement events in region C [reaching O(10<sup>2</sup> )] are significantly more extreme than those in regions A and B, although less frequent. Sometimes, at certain locations within region C, the NIWs can outperform ITs by up to two orders of magnitude. 

The temporal evolutions of daily and region-averaged hED2i, hED1i, hENIWi, and rE are examined in the four regions (Fig. 9). In regions A–C, diurnal ITs dominate over semidiurnal ITs, whereas in region D, they are comparable. The semidiurnal ITs in all four regions do not exhibit distinct seasonal variation (Fig. 9a), although showing a significantly high level in region D (west of the Luzon Strait). In contrast, the diurnal ITs display a semiannual cycle in all four regions: strong in winter and summer but weak in spring and autumn (Fig. 9b). Previous studies (e.g., Shang et al. 2015) showed that the ITs in the southern SCS mainly consist of mode-1 diurnal ITs, including O1, P1, and K1 components. In addition to the apparent 14-day neap–spring cycle, these diurnal ITs also have 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

728 

VOLUME 55 

J O U R N A L O F P H Y S I C A L O C E A N O G R A P H Y 


![](10.1175_jpo-d-24-0098.1_assets/phoc-JPO-D-24-0098.1-b993d93c15.pdf-0012-03.png)


FIG. 8. Maps of rE on different dates and their statistical results. (a)–(f) Snapshots of rE taken on various dates, including 14 Sep, 9 Oct, 24 Nov, and 28 Dec in 2011, and 12 Mar and 20 Sep in 2012. (g) Map of the median values of rE derived from the time series data at each grid. (h),(i) As in (g), but for the maximum values of rE and the occurrence frequency for rE . 0.5, respectively. The areas marked by the four black boxes are region A (1168–1208E, 118–158N), region B (1108–1148E, 118–158N), region C (1118–1178E, 168–198N), and region D (1188–1218E, 198–228N). All results are obtained at a height of approximately 500 m above the ocean bottom. Points A0 and C0 (blue pentagon) are used for a full-depth analysis. 

significant seasonal variation, with approximately 60% higher energy observed during summer and winter compared to that in spring and autumn. This seasonality arises primarily from the semiannual periodicity of the barotropic forcing induced by the modulations of P1 and K1 components, since there is no significant seasonal variation in the stratification in the southern SCS. 

Mooring observations revealed that the diurnal ITs in the Luzon Strait and northern SCS also show seasonal variation, with stronger amplitudes during winter and summer and weaker ones during spring and autumn; in contrast, there is no noticeable seasonal variation in the semidiurnal ITs (Huang et al. 2018; Zhao et al. 2019). Our results are consistent with these studies. 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

729 

JUNE 2025 

S U N E T A L . 


![](10.1175_jpo-d-24-0098.1_assets/phoc-JPO-D-24-0098.1-b993d93c15.pdf-0013-03.png)


FIG. 9. Temporal variations of daily and domain-averaged (a) hED2i, (b) hED1i, (c) hENIWi, and (d) rE for regions A–D. All results are obtained at a height of approximately 500 m above the ocean bottom. 

The behaviors of the NIWs differ among the four regions (Fig. 9c). Although the magnitude of hENIWi in region D [about O(10<sup>24</sup> )] is wholly larger than that in the other three regions [most of the time O(10<sup>25</sup> )], it is overshadowed by the dominant ITs there [both hED2i and hED1i are O(10<sup>23</sup> )], consequently resulting in a relatively small value of rE in this region (Fig. 9d). Furthermore, neither hENIWi nor rE shows any obvious seasonal variation in region D. In region C (near the Xisha Islands), there is a prominent peak in both hENIWi [approximately O(10<sup>24</sup> )] and rE (exceeding 2.5) during October– November 2011; during the other periods, hENIWi is comparatively weaker, and rE values are smaller and comparable to those in region D, without distinct seasonal patterns. In regions A and B, hENIWi exhibits a similar semiannual pattern to that of hED1i, albeit with a slight phase shift. Moreover, rE also exhibits a less pronounced semiannual cycle. Notably, rE reaches its peak during two periods of low values of hED1i (February–April 2012 and August–September 2012), with peaks being significantly larger during the former than in the latter. 

## b. Potential mechanism 

To explore the potential mechanisms of enhanced deepocean NIWs and elevated rE values, we calculate the correlation coefficients of rE with hEsubi, hED1i, and hED2i (Figs. 10a–c). We also obtain the correlation coefficients of hENIWi with hEsubi, hED1i, and hED2i (Figs. 10d–f). Herein, hEsubi denotes the kinetic energy of subinertial flow. 

In region C, hENIWi shows a significant positive correlation with hEsubi, while displaying minimal correlations with hED1i and hED2i (Figs. 10d–f). Similar results are obtained for rE (Figs. 10a–c). This suggests the enhanced deep-ocean NIWs in this region are closely associated with subinertial flow (i.e., mesoscale eddies). Considering earlier studies (e.g., Yang et al. 2019), we suspect that when westward-propagating mesoscale eddies in the northern SCS encounter the small-scale topography surrounding the Xisha Islands, they interact with the topography and generate internal lee waves. The subsequent breaking and dissipation of these lee waves give rise to wave stress (like wind stress acting on the sea surface), which can trigger active NIWs. 

This process can be qualitatively assessed via internal leewave energy flux: 


![](10.1175_jpo-d-24-0098.1_assets/phoc-JPO-D-24-0098.1-b993d93c15.pdf-0013-10.png)


where the steepness (or inverse Froude number), FrL 5 Nboth0/|Usub|, measures the nonlinearity of internal lee waves. Here, r0 is a reference density, kh 5 (kx, ky) is the horizontal 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

730 

VOLUME 55 

J O U R N A L O F P H Y S I C A L O C E A N O G R A P H Y 


![](10.1175_jpo-d-24-0098.1_assets/phoc-JPO-D-24-0098.1-b993d93c15.pdf-0014-03.png)


FIG. 10. Spatial distribution maps of correlation coefficients. (a)–(c) Correlation coefficients of rE with hEsubi, hED1i, and hED2i, respectively. (d)–(f) Correlation coefficients of hENIWi with hEsubi, hED1i, and hED2i, respectively. The hEsubi is the kinetic energy of subinertial flow. The gray contour represents the 1000-m isobath. The purple box in (d) represents the area analyzed for Fig. 11. 

wavenumber, P(kx, ky) is the two-dimensional topographic spectrum, Nbot is the near-bottom buoyancy frequency, h0 is the root-mean-square topographic height for small-scale topography (horizontal scale less than 10 km), and Usub is the near-bottom subinertial velocity. According to Nikurashin and Ferrari (2010a,b), when the steepness is below its critical value (FrL)c (;0.4 suggested by Nikurashin et al. 2014), the internal lee waves behave linearly with slight dissipation, resulting in weak NIWs. However, when this parameter exceeds its critical value, the nonlinearity of internal lee waves intensifies rapidly, leading to intense wave breaking and dissipation over the topography, thus exciting vigorous NIWs. 

Taking the region where hENIWi and hEsubi exhibit a significant positive correlation (highlighted by the purple box in Fig. 10d) as an example, Fig. 11 shows the temporal variation of domain-averaged internal lee-wave energy flux and steepness. The purple box is representative to a certain extent for the whole region C, since both the daily averaged NIW energy in region C and within the purple box exhibit similar temporal 

variation (subplot of Fig. 11). The internal lee-wave energy flux shows three peaks during October–November 2011, February–March 2012, and June–July 2012, respectively. The first peaks (also the most prominent one) of NIW energy, internal lee-wave energy flux, and FrL almost coincided, occurring during October–November 2011. It lasted for more than a month and was accompanied by a steepness exceeding 0.4. The third peak of NIW energy (June–September 2012) aligned with the third period of high FrL (June–September 2012), encompassing the third peak of internal lee-wave energy flux (June–July 2012) but exhibiting a longer duration. Nonetheless, it can be considered that the third peaks of all three variables also coincided. However, the second peak of NIW energy (March–April 2012) was noticeably weaker in terms of both intensity and duration. Moreover, it did not temporally align well with the second peaks (February–March 2012) of internal lee-wave energy flux and FrL. In conclusion, the breaking of the nonlinear internal lee waves played a significant role in generating deep-ocean NIWs near the Xisha 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

731 

JUNE 2025 

S U N E T A L . 


![](10.1175_jpo-d-24-0098.1_assets/phoc-JPO-D-24-0098.1-b993d93c15.pdf-0015-03.png)


FIG. 11. Domain-averaged results of internal lee-wave energy flux (skyblue curve) and steepness FrL (orange curve) for the region shown by the purple box in Fig. 10d. The inset displays the daily averaged hENIWi calculated both in the whole region C (blue-green curve) and in the purple box in region C (purple curve). 

Islands. However, we cannot disregard the possibility of other contributing mechanisms. 

In regions A and B, a strong positive correlation exists between hENIWi and hED1i, while a weak one exists between hENIWi and hED2i (Figs. 10e,f). This implies that the intensified deep-ocean NIWs in these regions are closely linked to diurnal ITs, possibly through the PSI mechanism, considering their proximity to the critical latitude of diurnal tides (;148N). Alford (2008) reported shipboard observations confirming the occurrence of PSI for diurnal K1 and O1 ITs at critical latitudes of 14.528 and 13.448N, respectively, analogous to those observed at the critical latitude of M2 (28.88N) (MacKinnon et al. 2013a,b). Moored ADCP data in the upper ocean also revealed significant peaks appearing at subharmonic frequencies of diurnal ITs (0.5 K1–f) around this critical latitude (Xie et al. 2009). Recently, Hu et al. (2023) employed long-term moorings to investigate the latitude variation of NIWs in the deep SCS; their findings indicate a dominance at approximately 148N where these abyssal NIWs are phase coupled with diurnal ITs, displaying common seasonal variation that is more pronounced during winter and summer, in line with our results. These studies provided evidence supporting diurnal PSI near its critical latitudes being responsible for elevated values of both hENIWi and rE in regions A and B. For the other two classes of resonant triad interactions, both ID and ES exhibit a direct energy cascade in frequency, whereas only the PSI exhibits a slightly inverse energy cascade in frequency (Wu and Pan 2023; Dematteis et al. 2024). Therefore, we believe that ID and ES may be less effective in enhancing NIWs compared to the PSI. 

We also find an association between hENIWi and hEsubi in regions A and B (Fig. 10d), which is reasonable since the relative vorticity of mesoscale eddies can significantly modify the critical latitude of PSI by changing the local effective Coriolis frequency (e.g., Yang et al. 2018). Besides, mesoscale eddies 

can directly provide energy to NIWs through wave–eddy interactions (e.g., Polzin 2010), and thus, the wave–eddy interaction mechanism is also a possible explanation for the enhancement of NIWs. In region A, both positive and negative correlations are present in comparable proportions. In region B, the prevalence of negative correlations significantly exceeds that of positive correlations. The dissimilarity between regions A and B may be attributed to the distinct features of the mesoscale eddies in these two regions. For example, statistical analysis conducted by Chen et al. (2011) revealed that eddy probability in region B (east of Vietnam) is higher (reaching 70%) than that in region A (;30%); in region B, anticyclonic eddies and cyclonic eddies have comparable probabilities, while in region A, anticyclonic eddies have twice the probability of cyclonic eddies. 

In region D (west of the Luzon Strait), hENIWi and hED1i have a strong positive correlation, while hENIWi shows no correlations with hED2i and hEsubi (Figs. 10d–f). Currently, we cannot provide a definite explanation for this yet, as existing studies have seldom associated the enhanced NIWs in this region with diurnal ITs; instead, researchers attributed it to the potential contribution of the PSI triad involving D2, f, and D2–f (e.g., Xie et al. 2011). Since the focus of this study here is to highlight the prevalence of significant NIWs in the deep SCS, these specific generation mechanisms require exploration and clarification in the future. 

To address any concerns that analyzing different depth levels might yield varying results and conclusions, a full-depth analysis of rE at two representative locations (point A0 in region A and point C0 in region C as shown in Fig. 8h) was conducted, because reanalyzing all depths of the entire SCS is beyond our reach due to the large volume of the LLC4320 output. The results indicated that at point A0, rE typically 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

732 

VOLUME 55 

J O U R N A L O F P H Y S I C A L O C E A N O G R A P H Y 

reaches O(10<sup>1</sup> ) on most dates. Furthermore, rE remains vertically consistent within the height range of 300–1200 m above the ocean bottom on a particular day. At point C0, the values of rE increased to O(10<sup>1</sup> ) or as larger as O(10<sup>2</sup> ) only during the period from October to November 2011 and were extremely weak in the other periods. Regardless of whether it is during the strong or weak period of rE, the values of rE show a high vertical consistency from the seabed to 1200 m above the ocean bottom. These two examples suggest that even if we choose other depth levels for analysis, the results may have small quantitative changes, but the qualitative conclusions would remain the same. 

## 5. Summary and discussion 

In this study, we use in situ data from simultaneously deployed CTD and LADCP to examine the three-dimensional structures of IW shear and strain spectra in the SCS. We focus on various associated spectral features, including spectra level, spectral slope, spectra clustering, and the shear-tostrain ratio Rv. We also develop a formula to estimate Rv based on qj (the high-wavenumber slope of the displacement spectrum) and explore the potential mechanisms responsible for the prevalence of NIWs in some regions of the deep SCS. 

The spectral levels of both shear and strain are more prominent in the Luzon Strait compared to those in the central SCS. With increasing depth, the shear spectral level experiences a significant increase spanning three orders of magnitude, while the strain spectral level exhibits only slight variation (within one order of magnitude). The qj ranges from 24 to 21 and follows a normal distribution, deviating from the GM value of 22. The statistical result of qj in the SCS is less concentrated than that in the global result (Pollmann 2020). Clustering analysis reveals that the strain spectra in the upper layer have a less pronounced low-wavenumber peak, whereas the deeper layers exhibit a more pronounced highwavenumber peak. 

The Rv gradually intensifies with depth and is generally weaker in the Luzon Strait compared to the central SCS. Moreover, there is a strong positive correlation between Rv and qj, with a fitted formula of Rv 5 10<sup>0:83qj13:13</sup> . While most Rv values fall within the range of 3–10, there exist some extreme values reaching up to 10<sup>2</sup> or even 10<sup>3</sup> , primarily in the deep SCS. These extreme values are accompanied by strain spectra those feature a pronounced high-wavenumber peak, indicating the significant presence of NIWs there. 

The analysis of a high-resolution numerical simulation confirms the presence of abundant deep-ocean NIWs in two main regions: the region between 118 and 158N and that around the Xisha Islands. In the former region, NIW formation is mainly attributed to the PSI mechanism of diurnal ITs as well as the wave–eddy interaction. In the latter, it results from the breaking and dissipation of internal lee waves generated by the interaction between mesoscale eddies and small-scale topography. Strong vertical shear within these NIWs indicates enhanced deep-ocean mixing in these areas. 

Some tests and discussions on the potential applicability of the newly derived formal relationship between Rv and qj are involved here. We focused on the regional fitted results for the Luzon Strait and central SCS, as these two regions show significant dynamic differences in both shear variance and strain variance (Fig. 4). The fitted results are Rv 5 10<sup>0:66qj12:54</sup> in the Luzon Strait, Rv 5 10<sup>0:75qj13:14</sup> in the central SCS, and Rv 5 10<sup>0:83qj13:13</sup> for the whole SCS. The above results imply a strong positive correlation between Rv and qj, which can be fitted using a specific formula. However, the fitted coefficients vary from region to region. At present, we cannot provide a definite conclusion on how specific environmental variables (such as topographic roughness, wind forcing, and presence of eddies or tides) affect the fitted coefficients, due to insufficient information (e.g., lack of data on wind speed and eddy velocity during the observation). More in-depth analysis is indeed required. Therefore, the formal relationship derived in this study still has a long way to go before it can be directly applied to improve the GHP based solely on strain. If we aim to completely shift the expression of the GHP from being based on Rv to being based on qj, we need to delve into the theoretical foundations and further explore the analytical expressions between these two variables. At least, this study provides an inspiration for selecting an optimal Rv value for the GHP based solely on strain, thereby offering an important insight to improve this parameterization. 

The ongoing study of IW spectra is not limited to the study of their spatiotemporal variability and discrepancy with the GM model. The comprehension of the underlying mechanisms driving the IW spectral energy transfer is constantly growing too. In addition to nonlocal interactions among separated scales (such as PSI, ID, and ES; McComas and Bretherton 1977; McComas and Muller¨ 1981), there also exist spectrally local interactions between adjacent scales (e.g., Wu and Pan 2023; Dematteis et al. 2024). Furthermore, it has been found that the direction of spectral energy transfer due to these interaction mechanisms is not always downscale. Wu and Pan (2023) indicated that downscale energy transfer is supplied by PSI and local interactions, while ID can cause cascades in both downscale and upscale directions depending on spectral slopes. Additionally, in the vertically symmetric IW field, ES promotes a forward frequency cascade but without any cascade in the wavenumber domain. Dematteis et al. (2024) revealed that for ID, the energy cascade occurs directly in both wavenumber and frequency; for PSI, it is direct in wavenumber but slightly inverse in frequency, whereas for ES, it is direct in frequency but slightly inverse in wavenumber. Obviously, some conclusions have not yet been unified. These analyses all begin with the GM model; however, real ocean observations sometimes deviate significantly from the GM model results. For example, Eden et al. (2019) found a dependence of IW energy dissipation on vertical wavenumber spectral slope, suggesting that using a fixed value for the slope yields a corresponding error (a factor of 4–5) in existing finescale parameterization estimates of the dissipation rate. In such cases, there may be variations in the mechanism, direction, and rate of spectral energy transfer, potentially posing challenges for the use of the current finescale 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

733 

JUNE 2025 

S U N E T A L . 

parameterization and for the interpretation of the resulting mixing maps in both local and global senses. 

Acknowledgments. This work is jointly supported by the National Natural Science Foundation of China (Grants 92258301, 42376012, 42006012, and 42076012). 

Data availability statement. The LLC4320 simulation output is available at https://data.nas.nasa.gov/ecco/eccodata/llc_ 4320/regions/SouthChinaSea3/. The bathymetric data are from 

GEBCO Gridded Bathymetry Data (https://www.gebco.net/ data_and_products/gridded_bathymetry_data/). Anyone who wants to get access to the in situ data can contact the corresponding author. 

## APPENDIX 

## All the Parameters and Their Definitions 

Table A1 shows all the parameters and their definitions we used in this paper. 

TABLE A1. The parameters summary table. 

|Symbol|Description|
|---|---|
|v, N, and f|Wave frequency, buoyancy frequency, and local Coriolis frequency|
|vD1 and vD2|Diurnal frequency (including the tidal constituents of K1, O1, P1, and Q1) and semidiurnal<br>frequency (including the tidal constituents of M2, S2, N2, and K2)<br>i|
|kz and lz|Vertical wavenumber and vertical wavelength of IW field|
|Vz and jz<br><br>2|IW shear and IW strain|
|hV<sup>2</sup><br>z<sup>i/</sup><br>N<br> and hj2<br>z<sup>i</sup>|IW shear variance (normalized by buoyancy frequency) and IW strain variance<br>|
|Rv|Shear-to-strain ratio<br>ii|
|SV/<br>N <sup>(k</sup>z<sup>) and Sj(kz)</sup>|Vertical wavenumber spectrum of IW velocity field and IW displacement field|
|SV/<br>N <sup>(k</sup>z<sup>) and S</sup>j<sup>(k</sup>z<sup>)</sup>|Vertical wavenumber spectrum of IW shear field and IW strain field|
|z<br>z<br>Sc1(kz) and Sc2(kz)|Shear spectral correction and strain spectral correction|
|Snoise|Instrument shear noise spectrum|
|Tra, Tbin, Tsup, and Ttilt|Transfer function for correcting shear spectra with the effect of range averaging, depth<br>binning, superensemble preaveraging, and instrument tilting|
|Dzr and Dzt|LADCP vertical bin size and LADCP transmit pulse length (usually Dzt 5 Dzr)|
|Dzg and Dzs|Vertical depth interval for the output shear profile and superensemble preaveraging interval<br>(often chosen to be Dzs 5 Dzg)|
|d<sup>′</sup>|A length scale that depends on the instrument tilt statistics|
|Dzstrain|Vertical depth interval for the output strain profile|
|k1|Lower limit of the integral wave band for obtaining shear and strain variances|
|k2 and k3|Upper limits of the integral wave band for obtaining shear variance and strain variance<br>i|
|F(kz)|Nonlinear fitting formula for SV/<br>N <sup>(k</sup>z<sup>) and Sj(kz)</sup>|
|G|Gamma function<br>i|
|e0|Energy-related coefficient in F(kz)<br>|
|kz∗|Vertical wavenumber scale in F(kz)|
|p and pj|Low-wavenumber slope in F(kz) and its fitted result for Sj(kz)|
|q and qj|High-wavenumber slope in F(kz) and its fitted result for Sj(kz)|
|An3n|Nonnegative data matrix for input in NMF|
|samplefeature<br>Wnl3n|Feature matrix derived from the output of NMF|
|sampecomp<br>Hn3n|Coefficient matrix derived from the output of NMF|
|compfeature<br>nsample|Number of the samples, e.g., the number of IW spectral segments from all stations<br>|
|nfeature|Length of each sample, e.g., the length of a shear/strain spectrum|
|ncomp|The desired number of main features to be extracted from matrix A by NMF|
|ncluster|The desired number of Gaussian components to be contained in the GMM, namely, the<br>number of clusters for the cluster analysis|
|hEsubi, hENIWi, hED1i, and hED2i|Daily averaged kinetic energy of subinertial flow, NIWs, diurnal, and semidiurnal ITs (at a<br>height of approximately 500 m above the ocean bottom)|
|rE|Ratio between the kinetic energy of NIWs and that of diurnal and semidiurnal ITs (at a<br>height of approximately 500 m above the ocean bottom)|
|Fluxlee|Vertical energy flux of internal lee waves|
|r0|Reference seawater density|
|Nbot and Usub|Near-bottom buoyancy frequency and near-bottom subinertial velocity|
|P(kx, ky) and kh 5 (kx, ky)|Topographic spectrum and horizontal wavenumber vector|
|h0|Root-mean-square topographic height for small-scale topography (horizontal scale less than 10 km)|
|FrL and (FrL)c|Steepness (measuring the nonlinearity of internal lee waves) and its critical value|



Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

734 

VOLUME 55 

J O U R N A L O F P H Y S I C A L O C E A N O G R A P H Y 

### REFERENCES 

- Alford, M. H., 2003: Redistribution of energy available for ocean mixing by long-range propagation of internal waves. Nature, 423, 159–162, https://doi.org/10.1038/nature01628. 

- }}, 2008: Observations of parametric subharmonic instability of the diurnal internal tide in the South China Sea. Geophys. Res. Lett., 35, L15602, https://doi.org/10.1029/2008GL034720. 

- Cairns, J. L., and G. O. Williams, 1976: Internal wave observations from a midwater float, 2. J. Geophys. Res., 81, 1943– 1950, https://doi.org/10.1029/JC081i012p01943. 

- Chen, G., Y. Hou, and X. Chu, 2011: Mesoscale eddies in the South China Sea: Mean properties, spatiotemporal variability, and impact on thermohaline structure. J. Geophys. Res., 116, C06018, https://doi.org/10.1029/2010JC006716. 

- Chen, Z., S. Chen, Z. Liu, J. Xu, J. Xie, Y. He, and S. Cai, 2019: Can tidal forcing alone generate a GM-like internal wave spectrum? Geophys. Res. Lett., 46, 14 644–14 652, https://doi. org/10.1029/2019GL086338. 

- Conn, S., J. Callies, and A. Lawrence, 2025: Regimes of nearinertial wave dynamics. J. Fluid Mech., 1002, A22, https://doi. org/10.1017/jfm.2024.1175. 

- de Lavergne, C., S. Groeskamp, J. Zika, and H. L. Johnson, 2022: The role of mixing in the large-scale ocean circulation. Ocean Mixing, M. Meredith and A. Naveira Garabato, Eds., Elsevier, 35–63. 

- Dematteis, G., A. Le Boyer, F. Pollmann, K. L. Polzin, M. H. Alford, C. B. Whalen, and Y. V. Lvov, 2024: Interacting internal waves explain global patterns of interior ocean mixing. Nat. Commun., 15, 7468, https://doi.org/10.1038/s41467-02451503-6. 

- Deutsch, C., and T. Weber, 2012: Nutrient ratios as a tracer and driver of ocean biogeochemistry. Ann. Rev. Mar. Sci., 4, 113– 141, https://doi.org/10.1146/annurev-marine-120709-142821. 

- Eden, C., F. Pollmann, and D. Olbers, 2019: Numerical evaluation of energy transfers in internal gravity wave spectra of the ocean. J. Phys. Oceanogr., 49, 737–749, https://doi.org/10. 1175/JPO-D-18-0075.1. 

- Ferris, L., D. Gong, S. Merrifield, and L. S. Laurent, 2022: Contamination of finescale strain estimates of turbulent kinetic energy dissipation by frontal physics. J. Atmos. Oceanic Technol., 39, 619–640, https://doi.org/10.1175/JTECH-D-21-0088.1. 

- Friedrich, T., A. Timmermann, T. Decloedt, D. S. Luther, and A. Mouchet, 2011: The effect of topography-enhanced diapycnal mixing on ocean and atmospheric circulation and marine biogeochemistry. Ocean Modell., 39, 262–274, https://doi.org/10.1016/j.ocemod.2011.04.012. 

- Garrett, C., 2001: What is the “near-inertial” band and why is it different from the rest of the internal wave spectrum? J. Phys. Oceanogr., 31, 962–971, https://doi.org/10.1175/15200485(2001)031,0962:WITNIB.2.0.CO;2. 

- }}, and W. Munk, 1972: Space-time scales of internal waves. Geophys. Fluid Dyn., 3, 225–264, https://doi.org/10.1080/ 03091927208236082. 

- }}, and }}, 1975: Space-time scales of internal waves: A progress report. J. Geophys. Res., 80, 291–297, https://doi.org/10. 1029/JC080i003p00291. 

- Gregg, M. C., 1989: Scaling turbulent dissipation in the thermocline. J. Geophys. Res., 94, 9686–9698, https://doi.org/10.1029/ JC094iC07p09686. 

- }}, T. B. Sanford, and D. P. Winkel, 2003: Reduced mixing from the breaking of internal waves in equatorial waters. Nature, 422, 513–515, https://doi.org/10.1038/nature01507. 

- Henyey, F. S., J. Wright, and S. M. Flatté, 1986: Energy and action flow through the internal wave field: An eikonal approach. J. Geophys. Res., 91, 8487–8495, https://doi.org/10. 1029/JC091iC07p08487. 

- Howatt, T., S. Waterman, and T. Ross, 2021: On using the finescale parameterization and Thorpe scales to estimate turbulence from glider data. J. Atmos. Oceanic Technol., 38, 1187– 1204, https://doi.org/10.1175/JTECH-D-20-0144.1. 

- Hu, Q., and Coauthors, 2020: Cascade of internal wave energy catalyzed by eddy-topography interactions in the deep South China Sea. Geophys. Res. Lett., 47, e2019GL086510, https:// doi.org/10.1029/2019GL086510. 

- }}, and Coauthors, 2023: Parametric subharmonic instability of diurnal internal tides in the abyssal South China Sea. J. Phys. Oceanogr., 53, 195–213, https://doi.org/10.1175/JPO-D22-0020.1. 

- Huang, X. D., Z. Y. Wang, Z. W. Zhang, Y. C. Yang, C. Zhou, Q. X. Yang, W. Zhao, and J. W. Tian, 2018: Role of mesoscale eddies in modulating the semidiurnal internal tide: Observation results in the northern South China Sea. J. Phys. Oceanogr., 48, 1749–1770, https://doi.org/10.1175/JPO-D-17-0209.1. 

- Ijichi, T., and T. Hibiya, 2015: Frequency-based correction of finescale parameterization of turbulent dissipation in the deep ocean. J. Atmos. Oceanic Technol., 32, 1526–1535, https://doi. org/10.1175/JTECH-D-15-0031.1. 

- Kunze, E., 1985: Near-inertial wave propagation in geostrophic shear. J. Phys. Oceanogr., 15, 544–565, https://doi.org/10.1175/ 1520-0485(1985)015,0544:NIWPIG.2.0.CO;2. 

- }}, 2017a: The internal-wave-driven meridional overturning circulation. J. Phys. Oceanogr., 47, 2673–2689, https://doi.org/10. 1175/JPO-D-16-0142.1. 

- }}, 2017b: Internal-wave-driven mixing: Global geography and budgets. J. Phys. Oceanogr., 47, 1325–1345, https://doi.org/10. 1175/JPO-D-16-0141.1. 

- }}, E. Firing, J. M. Hummon, T. K. Chereskin, and A. M. Thurnherr, 2006: Global abyssal mixing inferred from lowered ADCP shear and CTD strain profiles. J. Phys. Oceanogr., 36, 1553–1576, https://doi.org/10.1175/JPO2926.1. 

- Le Boyer, A., and M. H. Alford, 2021: Variability and sources of the internal wave continuum examined from global moored velocity records. J. Phys. Oceanogr., 51, 2807–2823, https:// doi.org/10.1175/JPO-D-20-0155.1. 

- Lele, R., S. G. Purkey, J. A. MacKinnon, and J. D. Nash, 2023: Global patterns of bias in ocean mixing parameterization identified through unsupervised machine learning. ESS Open Archive, https://doi.org/10.22541/essoar.168055231.12155392/ v1. 

- Liang, C.-R., X.-D. Shang, Y.-F. Qi, G.-Y. Chen, and L.-H. Yu, 2018: Assessment of fine-scale parameterizations at low latitudes of the North Pacific. Sci. Rep., 8, 10281, https://doi.org/ 10.1038/s41598-018-28554-z. 

- MacKinnon, J. A., M. H. Alford, R. Pinkel, J. Klymak, and Z. K. Zhao, 2013a: The latitudinal dependence of shear and mixing in the Pacific transiting the critical latitude for PSI. J. Phys. Oceanogr., 43, 3–16, https://doi.org/10.1175/JPO-D-11-0107.1. 

- }}, }}, O. Sun, R. Pinkel, Z. Zhao, and J. Klymak, 2013b: Parametric subharmonic instability of the internal tide at 298N. J. Phys. Oceanogr., 43, 17–28, https://doi.org/10.1175/ JPO-D-11-0108.1. 

- McComas, C. H., and F. P. Bretherton, 1977: Resonant interaction of oceanic internal waves. J. Geophys. Res., 82, 1397–1412, https://doi.org/10.1029/JC082i009p01397. 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

735 

JUNE 2025 

S U N E T A L . 

- }}, and P. Muller, 1981: The dynamic balance of internal waves.¨ J. Phys. Oceanogr., 11, 970–986, https://doi.org/10.1175/15200485(1981)011,0970:TDBOIW.2.0.CO;2. 

- Melet, A. V., R. Hallberg, and D. P. Marshall, 2022: The role of ocean mixing in the climate system. Ocean Mixing, M. Meredith and A. Naveira Garabato, Eds., Elsevier, 5–34. 

- Munk, W., 1981: Internal waves and small-scale processes. Evolution of Physical Oceanography, B. Warren and C. Wunch, Eds., The MIT Press, 264–291. 

- }}, and C. Wunsch, 1998: Abyssal recipes II: Energetics of tidal and wind mixing. Deep-Sea Res. I, 45, 1977–2010, https://doi. org/10.1016/S0967-0637(98)00070-3. 

- Musgrave, R., F. Pollmann, S. Kelly, and M. Nikurashin, 2022: The lifecycle of topographically-generated internal waves. Ocean Mixing, M. Meredith and A. Naveira Garabato, Eds., Elsevier, 117–144. 

- Naveira Garabato, A. C., K. L. Polzin, B. A. King, K. J. Heywood, and M. Visbeck, 2004: Widespread intense turbulent mixing in the Southern Ocean. Science, 303, 210–213, https://doi.org/ 10.1126/science.1090929. 

- Nikurashin, M., and R. Ferrari, 2010a: Radiation and dissipation of internal waves generated by geostrophic motions impinging on small-scale topography: Theory. J. Phys. Oceanogr., 40, 1055–1074, https://doi.org/10.1175/2009JPO4199.1. 

- }}, and }}, 2010b: Radiation and dissipation of internal waves generated by geostrophic motions impinging on small-scale topography: Application to the Southern Ocean. J. Phys. Oceanogr., 40, 2025–2042, https://doi.org/10.1175/2010JPO4315.1. 

- }}, }}, N. Grisouard, and K. Polzin, 2014: The impact of finite-amplitude bottom topography on internal wave generation in the Southern Ocean. J. Phys. Oceanogr., 44, 2938– 2950, https://doi.org/10.1175/JPO-D-13-0201.1. 

- Olbers, D., F. Pollmann, and C. Eden, 2020: On PSI interactions in internal gravity wave fields and the decay of baroclinic tides. J. Phys. Oceanogr., 50, 751–771, https://doi.org/10.1175/ JPO-D-19-0224.1. 

- Onuki, Y., and T. Hibiya, 2019: Parametric subharmonic instability in a narrow-band wave spectrum. J. Fluid Mech., 865, 247–280, https://doi.org/10.1017/jfm.2019.44. 

- Pollmann, F., 2020: Global characterization of the ocean’s internal wave spectrum. J. Phys. Oceanogr., 50, 1871–1891, https://doi. org/10.1175/JPO-D-19-0185.1. 

- }}, 2022: Global characterization of the ocean’s internal gravity wave vertical wavenumber spectrum from Argo float profiles. Zenodo, accessed 29 September 2024, https://doi.org/10.5281/ zenodo.6966416. 

- Polzin, K., E. Kunze, J. Hummon, and E. Firing, 2002: The finescale response of lowered ADCP velocity profiles. J. Atmos. Oceanic Technol., 19, 205–224, https://doi.org/10.1175/15200426(2002)019,0205:TFROLA.2.0.CO;2. 

- Polzin, K. L., 2010: Mesoscale eddy–internal wave coupling. Part II: Energetics and results from PolyMode. J. Phys. Oceanogr., 40, 789–801, https://doi.org/10.1175/2009JPO4039.1. 

- }}, and Y. V. Lvov, 2011: Toward regional characterizations of the oceanic internal wavefield. Rev. Geophys., 49, RG4003, https://doi.org/10.1029/2010RG000329. 

- }}, J. M. Toole, and R. W. Schmitt, 1995: Finescale parameterizations of turbulent dissipation. J. Phys. Oceanogr., 25, 306–328, https://doi.org/10.1175/1520-0485(1995)025,0306:FPOTD.2. 0.CO;2. 

- Qu, T., J. B. Girton, and J. A. Whitehead, 2006: Deepwater overflow through Luzon Strait. J. Geophys. Res., 111, C01002, https://doi.org/10.1029/2005JC003139. 

- Rocha, C. B., S. T. Gille, T. K. Chereskin, and D. Menemenlis, 2016a: Seasonality of submesoscale dynamics in the Kuroshio Extension. Geophys. Res. Lett., 43, 11304–11 311, https://doi. org/10.1002/2016GL071349. 

- }}, T. K. Chereskin, S. T. Gille, and D. Menemenlis, 2016b: Mesoscale to submesoscale wavenumber spectra in Drake Passage. J. Phys. Oceanogr., 46, 601–620, https://doi.org/10. 1175/JPO-D-15-0087.1. 

- Shang, X., Q. Liu, X. Xie, G. Chen, and R. Chen, 2015: Characteristics and seasonal variability of internal tides in the southern South China Sea. Deep-Sea Res. I, 98, 43–52, https://doi. org/10.1016/j.dsr.2014.12.005. 

- Sheen, K. L., and Coauthors, 2013: Rates and mechanisms of turbulent dissipation and mixing in the Southern Ocean: Results from the Diapycnal and Isopycnal Mixing Experiment in the Southern Ocean (DIMES). J. Geophys. Res. Oceans, 118, 2774–2792, https://doi.org/10.1002/jgrc.20217. 

- Sun, H., W. Zhao, Q. Yang, S. Cai, X. Liang, and J. Tian, 2019: Estimating four-dimensional internal wave spectrum in the northern South China Sea. J. Atmos. Oceanic Technol., 36, 1199–1216, https://doi.org/10.1175/JTECH-D-18-0046.1. 

- }}, Q. Yang, J. Li, W. Zhao, and J. Tian, 2024: Parameterization of shear-to-strain ratio used in finescale parameterization. J. Geophys. Res. Oceans, 129, e2023JC020393, https:// doi.org/10.1029/2023JC020393. 

- Takahashi, A., and T. Hibiya, 2019: Assessment of finescale parameterizations of deep ocean mixing in the presence of geostrophic current shear: Results of microstructure measurements in the Antarctic Circumpolar Current Region. J. Geophys. Res. Oceans, 124, 135–153, https://doi.org/10.1029/2018JC014030. 

- Thurnherr, A. M., 2012: The finescale response of lowered ADCP velocity measurements processed with different methods. J. Atmos. Oceanic Technol., 29, 597–600, https://doi.org/10.1175/ JTECH-D-11-00158.1. 

- Tian, J., Q. Yang, and W. Zhao, 2009: Enhanced diapycnal mixing in the South China Sea. J. Phys. Oceanogr., 39, 3191–3203, https://doi.org/10.1175/2009JPO3899.1. 

- Tuerena, R. E., R. G. Williams, C. Mahaffey, C. Vic, J. A. M. Green, A. Naveira-Garabato, A. Forryan, and J. Sharples, 2019: Internal tides drive nutrient fluxes into the deep chlorophyll maximum over mid-ocean ridges. Global Biogeochem. Cycles, 33, 995–1009, https://doi.org/10.1029/2019GB006214. 

- Waterman, S., K. L. Polzin, A. C. Naveira Garabato, K. L. Sheen, and A. Forryan, 2014: Suppression of internal wave breaking in the Antarctic Circumpolar Current near topography. J. Phys. Oceanogr., 44, 1466–1492, https://doi.org/10.1175/JPOD-12-0154.1. 

- Whalen, C. B., L. D. Talley, and J. A. MacKinnon, 2012: Spatial and temporal variability of global ocean mixing inferred from Argo profiles. Geophys. Res. Lett., 39, L18612, https://doi.org/ 10.1029/2012GL053196. 

- }}, J. A. MacKinnon, L. D. Talley, and A. F. Waterhouse, 2015: Estimating the mean diapycnal mixing using a finescale strain parameterization. J. Phys. Oceanogr., 45, 1174–1188, https://doi.org/10.1175/JPO-D-14-0167.1. 

- }}, C. de Lavergne, A. C. Naveira Garabato, J. M. Klymak, J. A. MacKinnon, and K. L. Sheen, 2020: Internal wavedriven mixing: Governing processes and consequences for climate. Nat. Rev. Earth Environ., 1, 606–621, https://doi.org/10. 1038/s43017-020-0097-z. 

- Wu, Y., and Y. Pan, 2023: Energy cascade in the Garrett–Munk spectrum of internal gravity waves. J. Fluid Mech., 975, A11, https://doi.org/10.1017/jfm.2023.862. 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 

736 

VOLUME 55 

J O U R N A L O F P H Y S I C A L O C E A N O G R A P H Y 

- Wunsch, C., 1975: Deep ocean internal waves: What do we really know? J. Geophys. Res., 80, 339–343, https://doi.org/10.1029/ JC080i003p00339. 

- }}, 2004: Vertical mixing, energy, and the general circulation of the oceans. Annu. Rev. Fluid Mech., 36, 281–314, https://doi. org/10.1146/annurev.fluid.36.050802.122121. 

- Xie, X.-H., X.-D. Shang, G.-Y. Chen, and L. Sun, 2009: Variations of diurnal and inertial spectral peaks near the bi-diurnal critical latitude. Geophys. Res. Lett., 36, L02606, https://doi.org/ 10.1029/2008GL036383. 

- }}, }}, H. van Haren, G.-Y. Chen, and Y.-Z. Zhang, 2011: Observations of parametric subharmonic instability-induced near-inertial waves equatorward of the critical diurnal latitude. Geophys. Res. Lett., 38, L05603, https://doi.org/10.1029/ 2010GL046521. 

- Xu, Z., K. Liu, B. Yin, Z. Zhao, Y. Wang, and Q. Li, 2016: Longrange propagation and associated variability of internal tides in the South China Sea. J. Geophys. Res. Oceans, 121, 8268– 8286, https://doi.org/10.1002/2016JC012105. 

- Yang, Q., W. Zhao, X. Liang, and J. Tian, 2016: Three-dimensional distribution of turbulent mixing in the South China Sea. J. 

   - Phys. Oceanogr., 46, 769–788, https://doi.org/10.1175/JPO-D14-0220.1. 

- }}, M. Nikurashin, H. Sasaki, H. Sun, and J. Tian, 2019: Dissipation of mesoscale eddies and its contribution to mixing in the northern South China Sea. Sci. Rep., 9, 556, https://doi. org/10.1038/s41598-018-36610-x. 

- Yang, W., T. Hibiya, Y. Tanaka, L. Zhao, and H. Wei, 2018: Modification of parametric subharmonic instability in the presence of background geostrophic currents. Geophys. Res. Lett., 45, 12 957–12962, https://doi.org/10.1029/2018GL080183. 

- Young, W., and M. B. Jelloul, 1997: Propagation of near-inertial oscillations through a geostrophic flow. J. Mar. Res., 55, 735– 766, https://doi.org/10.1357/0022240973224283. 

- Zhao, J., Y. Zhang, Z. Liu, Y. Zhao, and M. Wang, 2019: Seasonal variability of tides in the deep northern South China Sea. Sci. China Earth Sci., 62, 671–683, https://doi.org/10.1007/ s11430-017-9315-7. 

- Zhou, C., W. Zhao, J. Tian, Q. Yang, and T. Qu, 2014: Variability of the deep-water overflow in the Luzon Strait. J. Phys. Oceanogr., 44, 2972–2986, https://doi.org/10.1175/JPO-D-14-0113.1. 

Brought to you by Peking University | Unauthenticated | Downloaded 09/19/26 02:16 AM UTC 



## References (77 total, showing 77)

- Alford, M. H., 2003: Redistribution of energy available for ocean mixing by long-range propagation of internal waves. Nature, 423, 159–162, https://doi.org/10.1038/nature01628.
- Alford, M. H., 2008: Observations of parametric subharmonic instability of the diurnal internal tide in the South China Sea. Geophys. Res. Lett., 35, L15602, https://doi.org/10.1029/2008GL034720.
- Cairns, J. L., and G. O. Williams, 1976: Internal wave observations from a midwater float, 2. J. Geophys. Res., 81, 1943–1950, https://doi.org/10.1029/JC081i012p01943.
- Chen, G., Y. Hou, and X. Chu, 2011: Mesoscale eddies in the South China Sea: Mean properties, spatiotemporal variability, and impact on thermohaline structure. J. Geophys. Res., 116, C06018, https://doi.org/10.1029/2010JC006716.
- Chen, Z., S. Chen, Z. Liu, J. Xu, J. Xie, Y. He, and S. Cai, 2019: Can tidal forcing alone generate a GM-like internal wave spectrum? Geophys. Res. Lett., 46, 14 644–14 652, https://doi.org/10.1029/2019GL086338.
- Conn, S., J. Callies, and A. Lawrence, 2025: Regimes of near-inertial wave dynamics. J. Fluid Mech., 1002, A22, https://doi.org/10.1017/jfm.2024.1175.
- de Lavergne, C., S. Groeskamp, J. Zika, and H. L. Johnson, 2022: The role of mixing in the large-scale ocean circulation. Ocean Mixing, M. Meredith and A. Naveira Garabato, Eds., Elsevier, 35–63.
- Dematteis, G., A. Le Boyer, F. Pollmann, K. L. Polzin, M. H. Alford, C. B. Whalen, and Y. V. Lvov, 2024: Interacting internal waves explain global patterns of interior ocean mixing. Nat. Commun., 15, 7468, https://doi.org/10.1038/s41467-024-51503-6.
- Deutsch, C., and T. Weber, 2012: Nutrient ratios as a tracer and driver of ocean biogeochemistry. Ann. Rev. Mar. Sci., 4, 113–141, https://doi.org/10.1146/annurev-marine-120709-142821.
- Eden, C., F. Pollmann, and D. Olbers, 2019: Numerical evaluation of energy transfers in internal gravity wave spectra of the ocean. J. Phys. Oceanogr., 49, 737–749, https://doi.org/10.1175/JPO-D-18-0075.1.
- Ferris, L., D. Gong, S. Merrifield, and L. S. Laurent, 2022: Contamination of finescale strain estimates of turbulent kinetic energy dissipation by frontal physics. J. Atmos. Oceanic Technol., 39, 619–640, https://doi.org/10.1175/JTECH-D-21-0088.1.
- Friedrich, T., A. Timmermann, T. Decloedt, D. S. Luther, and A. Mouchet, 2011: The effect of topography-enhanced diapycnal mixing on ocean and atmospheric circulation and marine biogeochemistry. Ocean Modell., 39, 262–274, https://doi.org/10.1016/j.ocemod.2011.04.012.
- Garrett, C., 2001: What is the “near-inertial” band and why is it different from the rest of the internal wave spectrum? J. Phys. Oceanogr., 31, 962–971, https://doi.org/10.1175/1520-0485(2001)031 2.0.CO;2.
- Garrett, C., and W. Munk, 1972: Space-time scales of internal waves. Geophys. Fluid Dyn., 3, 225–264, https://doi.org/10.1080/03091927208236082.
- Garrett, C., and W. Munk, 1975: Space-time scales of internal waves: A progress report. J. Geophys. Res., 80, 291–297, https://doi.org/10.1029/JC080i003p00291.
- Gregg, M. C., 1989: Scaling turbulent dissipation in the thermocline. J. Geophys. Res., 94, 9686–9698, https://doi.org/10.1029/JC094iC07p09686.
- Gregg, M. C., T. B. Sanford, and D. P. Winkel, 2003: Reduced mixing from the breaking of internal waves in equatorial waters. Nature, 422, 513–515, https://doi.org/10.1038/nature01507.
- Henyey, F. S., J. Wright, and S. M. Flatté, 1986: Energy and action flow through the internal wave field: An eikonal approach. J. Geophys. Res., 91, 8487–8495, https://doi.org/10.1029/JC091iC07p08487.
- Howatt, T., S. Waterman, and T. Ross, 2021: On using the finescale parameterization and Thorpe scales to estimate turbulence from glider data. J. Atmos. Oceanic Technol., 38, 1187–1204, https://doi.org/10.1175/JTECH-D-20-0144.1.
- Hu, Q., and Coauthors, 2020: Cascade of internal wave energy catalyzed by eddy-topography interactions in the deep South China Sea. Geophys. Res. Lett., 47, e2019GL086510, https://doi.org/10.1029/2019GL086510.
- Hu, Q., and Coauthors, 2023: Parametric subharmonic instability of diurnal internal tides in the abyssal South China Sea. J. Phys. Oceanogr., 53, 195–213, https://doi.org/10.1175/JPO-D-22-0020.1.
- Huang, X. D., Z. Y. Wang, Z. W. Zhang, Y. C. Yang, C. Zhou, Q. X. Yang, W. Zhao, and J. W. Tian, 2018: Role of mesoscale eddies in modulating the semidiurnal internal tide: Observation results in the northern South China Sea. J. Phys. Oceanogr., 48, 1749–1770, https://doi.org/10.1175/JPO-D-17-0209.1.
- Ijichi, T., and T. Hibiya, 2015: Frequency-based correction of finescale parameterization of turbulent dissipation in the deep ocean. J. Atmos. Oceanic Technol., 32, 1526–1535, https://doi.org/10.1175/JTECH-D-15-0031.1.
- Kunze, E., 1985: Near-inertial wave propagation in geostrophic shear. J. Phys. Oceanogr., 15, 544–565, https://doi.org/10.1175/1520-0485(1985)015 2.0.CO;2.
- Kunze, E., 2017a: The internal-wave-driven meridional overturning circulation. J. Phys. Oceanogr., 47, 2673–2689, https://doi.org/10.1175/JPO-D-16-0142.1.
- Kunze, E., 2017b: Internal-wave-driven mixing: Global geography and budgets. J. Phys. Oceanogr., 47, 1325–1345, https://doi.org/10.1175/JPO-D-16-0141.1.
- Kunze, E., E. Firing, J. M. Hummon, T. K. Chereskin, and A. M. Thurnherr, 2006: Global abyssal mixing inferred from lowered ADCP shear and CTD strain profiles. J. Phys. Oceanogr., 36, 1553–1576, https://doi.org/10.1175/JPO2926.1.
- Le Boyer, A., and M. H. Alford, 2021: Variability and sources of the internal wave continuum examined from global moored velocity records. J. Phys. Oceanogr., 51, 2807–2823, https://doi.org/10.1175/JPO-D-20-0155.1.
- Lele, R., S. G. Purkey, J. A. MacKinnon, and J. D. Nash, 2023: Global patterns of bias in ocean mixing parameterization identified through unsupervised machine learning. ESS Open Archive, https://doi.org/10.22541/essoar.168055231.12155392/v1.
- Liang, C.-R., X.-D. Shang, Y.-F. Qi, G.-Y. Chen, and L.-H. Yu, 2018: Assessment of fine-scale parameterizations at low latitudes of the North Pacific. Sci. Rep., 8, 10281, https://doi.org/10.1038/s41598-018-28554-z.
- MacKinnon, J. A., M. H. Alford, R. Pinkel, J. Klymak, and Z. K. Zhao, 2013a: The latitudinal dependence of shear and mixing in the Pacific transiting the critical latitude for PSI. J. Phys. Oceanogr., 43, 3–16, https://doi.org/10.1175/JPO-D-11-0107.1.
- MacKinnon, J. A., M. H. Alford, O. Sun, R. Pinkel, Z. Zhao, and J. Klymak, 2013b: Parametric subharmonic instability of the internal tide at 29°N. J. Phys. Oceanogr., 43, 17–28, https://doi.org/10.1175/JPO-D-11-0108.1.
- McComas, C. H., and F. P. Bretherton, 1977: Resonant interaction of oceanic internal waves. J. Geophys. Res., 82, 1397–1412, https://doi.org/10.1029/JC082i009p01397.
- McComas, C. H., and P. Müller, 1981: The dynamic balance of internal waves. J. Phys. Oceanogr., 11, 970–986, https://doi.org/10.1175/1520-0485(1981)011 2.0.CO;2.
- Melet, A. V., R. Hallberg, and D. P. Marshall, 2022: The role of ocean mixing in the climate system. Ocean Mixing, M. Meredith and A. Naveira Garabato, Eds., Elsevier, 5–34.
- Munk, W., 1981: Internal waves and small-scale processes. Evolution of Physical Oceanography, B. Warren and C. Wunch, Eds., The MIT Press, 264–291.
- Munk, W., and C. Wunsch, 1998: Abyssal recipes II: Energetics of tidal and wind mixing. Deep-Sea Res. I, 45, 1977–2010, https://doi.org/10.1016/S0967-0637(98)00070-3.
- Musgrave, R., F. Pollmann, S. Kelly, and M. Nikurashin, 2022: The lifecycle of topographically-generated internal waves. Ocean Mixing, M. Meredith and A. Naveira Garabato, Eds., Elsevier, 117–144.
- Naveira Garabato, A. C., K. L. Polzin, B. A. King, K. J. Heywood, and M. Visbeck, 2004: Widespread intense turbulent mixing in the Southern Ocean. Science, 303, 210–213, https://doi.org/10.1126/science.1090929.
- Nikurashin, M., and R. Ferrari, 2010a: Radiation and dissipation of internal waves generated by geostrophic motions impinging on small-scale topography: Theory. J. Phys. Oceanogr., 40, 1055–1074, https://doi.org/10.1175/2009JPO4199.1.
- Nikurashin, M., and R. Ferrari, 2010b: Radiation and dissipation of internal waves generated by geostrophic motions impinging on small-scale topography: Application to the Southern Ocean. J. Phys. Oceanogr., 40, 2025–2042, https://doi.org/10.1175/2010JPO4315.1.
- Nikurashin, M., R. Ferrari, N. Grisouard, and K. Polzin, 2014: The impact of finite-amplitude bottom topography on internal wave generation in the Southern Ocean. J. Phys. Oceanogr., 44, 2938–2950, https://doi.org/10.1175/JPO-D-13-0201.1.
- Olbers, D., F. Pollmann, and C. Eden, 2020: On PSI interactions in internal gravity wave fields and the decay of baroclinic tides. J. Phys. Oceanogr., 50, 751–771, https://doi.org/10.1175/JPO-D-19-0224.1.
- Onuki, Y., and T. Hibiya, 2019: Parametric subharmonic instability in a narrow-band wave spectrum. J. Fluid Mech., 865, 247–280, https://doi.org/10.1017/jfm.2019.44.
- Pollmann, F., 2020: Global characterization of the ocean’s internal wave spectrum. J. Phys. Oceanogr., 50, 1871–1891, https://doi.org/10.1175/JPO-D-19-0185.1.
- Pollmann, F., 2022: Global characterization of the ocean’s internal gravity wave vertical wavenumber spectrum from Argo float profiles. Zenodo, accessed 29 September 2024, https://doi.org/10.5281/zenodo.6966416.
- Polzin, K., E. Kunze, J. Hummon, and E. Firing, 2002: The finescale response of lowered ADCP velocity profiles. J. Atmos. Oceanic Technol., 19, 205–224, https://doi.org/10.1175/1520-0426(2002)019 2.0.CO;2.
- Polzin, K. L., 2010: Mesoscale eddy–internal wave coupling. Part II: Energetics and results from PolyMode. J. Phys. Oceanogr., 40, 789–801, https://doi.org/10.1175/2009JPO4039.1.
- Polzin, K. L., and Y. V. Lvov, 2011: Toward regional characterizations of the oceanic internal wavefield. Rev. Geophys., 49, RG4003, https://doi.org/10.1029/2010RG000329.
- Polzin, K. L., J. M. Toole, and R. W. Schmitt, 1995: Finescale parameterizations of turbulent dissipation. J. Phys. Oceanogr., 25, 306–328, https://doi.org/10.1175/1520-0485(1995)025 2.0.CO;2.
- Qu, T., J. B. Girton, and J. A. Whitehead, 2006: Deepwater overflow through Luzon Strait. J. Geophys. Res., 111, C01002, https://doi.org/10.1029/2005JC003139.
- Rocha, C. B., S. T. Gille, T. K. Chereskin, and D. Menemenlis, 2016a: Seasonality of submesoscale dynamics in the Kuroshio Extension. Geophys. Res. Lett., 43, 11 304–11 311, https://doi.org/10.1002/2016GL071349.
- Rocha, C. B., T. K. Chereskin, S. T. Gille, and D. Menemenlis, 2016b: Mesoscale to submesoscale wavenumber spectra in Drake Passage. J. Phys. Oceanogr., 46, 601–620, https://doi.org/10.1175/JPO-D-15-0087.1.
- Shang, X., Q. Liu, X. Xie, G. Chen, and R. Chen, 2015: Characteristics and seasonal variability of internal tides in the southern South China Sea. Deep-Sea Res. I, 98, 43–52, https://doi.org/10.1016/j.dsr.2014.12.005.
- Sheen, K. L., and Coauthors, 2013: Rates and mechanisms of turbulent dissipation and mixing in the Southern Ocean: Results from the Diapycnal and Isopycnal Mixing Experiment in the Southern Ocean (DIMES). J. Geophys. Res. Oceans, 118, 2774–2792, https://doi.org/10.1002/jgrc.20217.
- Sun, H., W. Zhao, Q. Yang, S. Cai, X. Liang, and J. Tian, 2019: Estimating four-dimensional internal wave spectrum in the northern South China Sea. J. Atmos. Oceanic Technol., 36, 1199–1216, https://doi.org/10.1175/JTECH-D-18-0046.1.
- Sun, H., Q. Yang, J. Li, W. Zhao, and J. Tian, 2024: Parameterization of shear-to-strain ratio used in finescale parameterization. J. Geophys. Res. Oceans, 129, e2023JC020393, https://doi.org/10.1029/2023JC020393.
- Takahashi, A., and T. Hibiya, 2019: Assessment of finescale parameterizations of deep ocean mixing in the presence of geostrophic current shear: Results of microstructure measurements in the Antarctic Circumpolar Current Region. J. Geophys. Res. Oceans, 124, 135–153, https://doi.org/10.1029/2018JC014030.
- Thurnherr, A. M., 2012: The finescale response of lowered ADCP velocity measurements processed with different methods. J. Atmos. Oceanic Technol., 29, 597–600, https://doi.org/10.1175/JTECH-D-11-00158.1.
- Tian, J., Q. Yang, and W. Zhao, 2009: Enhanced diapycnal mixing in the South China Sea. J. Phys. Oceanogr., 39, 3191–3203, https://doi.org/10.1175/2009JPO3899.1.
- Tuerena, R. E., R. G. Williams, C. Mahaffey, C. Vic, J. A. M. Green, A. Naveira-Garabato, A. Forryan, and J. Sharples, 2019: Internal tides drive nutrient fluxes into the deep chlorophyll maximum over mid-ocean ridges. Global Biogeochem. Cycles, 33, 995–1009, https://doi.org/10.1029/2019GB006214.
- Waterman, S., K. L. Polzin, A. C. Naveira Garabato, K. L. Sheen, and A. Forryan, 2014: Suppression of internal wave breaking in the Antarctic Circumpolar Current near topography. J. Phys. Oceanogr., 44, 1466–1492, https://doi.org/10.1175/JPO-D-12-0154.1.
- Whalen, C. B., L. D. Talley, and J. A. MacKinnon, 2012: Spatial and temporal variability of global ocean mixing inferred from Argo profiles. Geophys. Res. Lett., 39, L18612, https://doi.org/10.1029/2012GL053196.
- Whalen, C. B., J. A. MacKinnon, L. D. Talley, and A. F. Waterhouse, 2015: Estimating the mean diapycnal mixing using a finescale strain parameterization. J. Phys. Oceanogr., 45, 1174–1188, https://doi.org/10.1175/JPO-D-14-0167.1.
- Whalen, C. B., C. de Lavergne, A. C. Naveira Garabato, J. M. Klymak, J. A. MacKinnon, and K. L. Sheen, 2020: Internal wave-driven mixing: Governing processes and consequences for climate. Nat. Rev. Earth Environ., 1, 606–621, https://doi.org/10.1038/s43017-020-0097-z.
- Wu, Y., and Y. Pan, 2023: Energy cascade in the Garrett–Munk spectrum of internal gravity waves. J. Fluid Mech., 975, A11, https://doi.org/10.1017/jfm.2023.862.
- Wunsch, C., 1975: Deep ocean internal waves: What do we really know? J. Geophys. Res., 80, 339–343, https://doi.org/10.1029/JC080i003p00339.
- Wunsch, C., 2004: Vertical mixing, energy, and the general circulation of the oceans. Annu. Rev. Fluid Mech., 36, 281–314, https://doi.org/10.1146/annurev.fluid.36.050802.122121.
- Xie, X.-H., X.-D. Shang, G.-Y. Chen, and L. Sun, 2009: Variations of diurnal and inertial spectral peaks near the bi-diurnal critical latitude. Geophys. Res. Lett., 36, L02606, https://doi.org/10.1029/2008GL036383.
- Xie, X.-H., X.-D. Shang, H. van Haren, G.-Y. Chen, and Y.-Z. Zhang, 2011: Observations of parametric subharmonic instability-induced near-inertial waves equatorward of the critical diurnal latitude. Geophys. Res. Lett., 38, L05603, https://doi.org/10.1029/2010GL046521.
- Xu, Z., K. Liu, B. Yin, Z. Zhao, Y. Wang, and Q. Li, 2016: Long-range propagation and associated variability of internal tides in the South China Sea. J. Geophys. Res. Oceans, 121, 8268–8286, https://doi.org/10.1002/2016JC012105.
- Yang, Q., W. Zhao, X. Liang, and J. Tian, 2016: Three-dimensional distribution of turbulent mixing in the South China Sea. J. Phys. Oceanogr., 46, 769–788, https://doi.org/10.1175/JPO-D-14-0220.1.
- Yang, Q., M. Nikurashin, H. Sasaki, H. Sun, and J. Tian, 2019: Dissipation of mesoscale eddies and its contribution to mixing in the northern South China Sea. Sci. Rep., 9, 556, https://doi.org/10.1038/s41598-018-36610-x.
- Yang, W., T. Hibiya, Y. Tanaka, L. Zhao, and H. Wei, 2018: Modification of parametric subharmonic instability in the presence of background geostrophic currents. Geophys. Res. Lett., 45, 12 957–12 962, https://doi.org/10.1029/2018GL080183.
- Young, W., and M. B. Jelloul, 1997: Propagation of near-inertial oscillations through a geostrophic flow. J. Mar. Res., 55, 735–766, https://doi.org/10.1357/0022240973224283.
- Zhao, J., Y. Zhang, Z. Liu, Y. Zhao, and M. Wang, 2019: Seasonal variability of tides in the deep northern South China Sea. Sci. China Earth Sci., 62, 671–683, https://doi.org/10.1007/s11430-017-9315-7.
- Zhou, C., W. Zhao, J. Tian, Q. Yang, and T. Qu, 2014: Variability of the deep-water overflow in the Luzon Strait. J. Phys. Oceanogr., 44, 2972–2986, https://doi.org/10.1175/JPO-D-14-0113.1.

