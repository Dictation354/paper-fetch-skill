---
title: "The Kubo-Thermalization Correspondence"
authors: "Songtao Huang, Xingyu Li, Jianyi Chen, Alan Tsidilkovski, Gabriel G. T. Assumpção, Pengfei Zhang, Hui Zhai, Nir Navon"
journal: "arXiv"
doi: "10.48550/arxiv.2605.06666v1"
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
token_estimate: 8483
---

# The Kubo-Thermalization Correspondence

## Abstract

Quantum thermalization describes how interacting quantum systems relax toward thermal equilibrium [<sup>1, 2, 3</sup>], a central problem in modern physics. Yet most experimental information on many-body systems comes from short-time transition spectroscopy, typically interpreted within Kubo’s linear-response framework [<sup>4, 5</sup>]. These perspectives—long-time equilibration versus short-time response—seem fundamentally disconnected. Here we establish an exact link between them: the Kubo-Thermalization correspondence, which connects long-time thermalized magnetization under weak driving to short-time linear-response spectra for a spin coupled to a thermal bath. The correspondence holds even when the steady state differs substantially from the initial state and when each regime is individually difficult to describe theoretically [<sup>6, 7</sup>]. We experimentally confirm the correspondence using effective spin-$1/2$ impurities realized with ultracold fermions in two internal states coupled to a Fermi sea [<sup>8</sup>]. Our results provide a rare exact statement about quantum thermalization and offer a novel route to infer thermalization dynamics from equilibrium response measurements in strongly interacting quantum systems, independent of microscopic details of the system–bath coupling.

![Figure 1](2605.06666v1_assets/Fig1.png)

![Figure 1](2605.06666v1_assets/Fig1.png)

**Figure 1.** Kubo-Thermalization correspondence for a driven spin coupled to a thermal bath. (a) A spin-1/2 particle is immersed in a thermal bath at temperature $T$, and an external spin-flip term drives the quantum dynamics for a duration $t$ with a weak Rabi frequency $\Omega_{0}$. (b) (Top) Dynamical evolution of the magnetization $\mathcal{M}$ after initializing the spin in $\ket{\downarrow}$ and turning on a weak spin-flip field. (Bottom left) The short-time transition spectroscopy $R(\Delta)$, defined as the transition rate versus detuning, and $\Delta_{\text{p}}$ is its peak position. (Bottom right) The long-time steady-state magnetization $\mathcal{M}_{\infty}(\Delta)$, characterized by its zero crossing $\Delta_{0}$ (defined as $\mathcal{M}_{\infty}(\Delta_{0})=0$). Our central result, Eq. (2), is a rigorous functional relation $\Delta_{0}=\mathcal{F}[R(\Delta)]$ that connects $\Delta_{0}$ to the spectrum $R(\Delta)$.

Determining the quantum dynamics of strongly correlated many-body systems is notoriously difficult: there is no universal route from the full, exponentially large Hilbert-space description to a compact, predictive theory. When such systems are driven weakly, however, Kubo’s linear-response framework and Fermi’s Golden Rule (FGR) [<sup>4, 5</sup>] provide a powerful simplification at short times: dynamical observables reduce to correlation functions evaluated on the initial equilibrium state. This viewpoint underpins much of modern spectroscopy, including ARPES [<sup>9, 10</sup>], neutron scattering [<sup>11</sup>], and Raman spectroscopy [<sup>12</sup>].

For longer times, the situation changes dramatically: switching on even a weak drive renders the initial equilibrium reference progressively irrelevant. Indeed, a system prepared in equilibrium for the undriven Hamiltonian is evolved under the driven dynamics—an effective “drive quench” that takes it out of equilibrium with respect to the new conditions; it may then thermalize to a steady state far from the initial one despite the drive being weak. It is therefore far from obvious that short-time linear-response data around the initial equilibrium should constrain, much less encode, the ensuing long-time thermalization under sustained driving.

Here we establish a direct link between the properties of a thermalized driven state and the short-time weak-drive response of a spin coupled to a bath. Importantly, this relation formally connects macroscopic observables even though they can be very challenging to calculate independently, and is largely independent of the nature of the thermal bath. Experimentally, we leverage the controllability and isolation of an ultracold system [<sup>13, 14</sup>] to establish and explore this connection.

Our setup, shown in Fig. 1 a, is a spin-1/2 particle embedded in a thermal bath at temperature $T=1/(\beta k_{\mathrm{B}})$ [<sup>15</sup>]. In the cartoon, the spin is depicted as a blue arrow and the bath is in red; an external near-resonant oscillating field couples the two spin states (green). The full Hamiltonian is $\hat{H}=\hat{H}^{\text{s}}+\hat{H}^{\text{B}}+\hat{H}^{\text{int}}$, where the spin part reads $\hat{H}^{\text{s}}=-\frac{1}{2}\hbar\Delta\hat{\sigma}_{z}+\frac{1}{2}\hbar\Omega_{0}\hat{\sigma}_{x}$ in the rotating frame of the drive; $\Delta$ is the detuning, $\Omega_{0}$ is the Rabi frequency, and $\hat{\sigma}_{x,z}$ are the Pauli operators ($\hbar$ is the reduced Planck constant). We make no assumptions on $\hat{H}^{\mathrm{B}}$ and a minimal one for $\hat{H}^{\mathrm{int}}$: the spin-bath interaction does not induce spin flips.

The spin is initialized in state $\ket{\downarrow}$ (see Fig. 1 a) and the coupling field is switched on at $t=0$. The dynamics of the spin is monitored with the magnetization $\mathcal{M}\equiv\braket{\hat{\sigma}_{z}}$, as shown in Fig. 1 b. At long times and for sufficiently small $\Omega_{0}$, the spin will thermalize, with the asymptotic magnetization $\mathcal{M}_{\infty}\equiv\mathcal{M}(t\rightarrow\infty)$ adopting the universal form (see Methods)

$$ \mathcal{M}_{\infty}(\Delta)=\tanh\left(\frac{\beta\hbar(\Delta-\Delta_{0})}{2}\right), $$
(1)

which is characterized by a single parameter $\Delta_{0}$ that depends on the spin-bath interactions [<sup>8</sup>].

At short times and small $\Omega_{0}$, the dynamics is instead well captured by linear response: after a brief transient, the (normalized) transition rate from $\ket{\downarrow}$ to $\ket{\uparrow}$ approaches a constant value given by the FGR: $R_{\downarrow}=1/(\pi\Omega_{0}^{2})\mathrm{d}\mathcal{M}/\mathrm{d}t$ [<sup>16</sup>].

The quantities $\Delta_{0}$ and $R_{\downarrow}$ characterize many-body physics in seemingly disjoint regimes. The zero crossing $\Delta_{0}$ is the effective resonance frequency of the thermalized driven spin. By contrast, $R_{\downarrow}(\Delta)$ is the linear-response FGR spectrum, a near-equilibrium quantity in the absence of driving. The central discovery of this work is that they are in fact exactly related:

$$ \hbar\Delta_{0}=-\frac{1}{\beta}\ln\!\left[\int_{-\infty}^{+\infty}\!\mathrm{d}\Delta\,R_{\downarrow}(\Delta)\,e^{-\beta\hbar\Delta}\right]. $$
(2)

We call Eq. (2) the Kubo-Thermalization correspondence: it provides a bridge between short-time linear response and the long-time thermal properties (Fig. 1 b). The derivation only assumes that the system relaxes to a thermal steady state under weak drive (see Methods). Remarkably, Eq. (2) is independent of the microscopic form of the bath Hamiltonian $\hat{H}^{\mathrm{B}}$ and of the detailed $\uparrow$–bath and $\downarrow$–bath couplings, and it generalizes to an $N$-level system.

![Figure 2](2605.06666v1_assets/Fig2.png)

![Figure 2](2605.06666v1_assets/Fig2.png)

**Figure 2.** Experimental platform and the Kubo-Thermalization correspondence on the BCS side. (a) (Left) Dilute spin-1/2 particles (blue spheres) consisting of <sup>6</sup>Li atoms interact with a bath composed of atoms prepared in a third state $\ket{\text{B}}$ (red spheres). The system is confined in a cylindrical optical box trap, in the presence of both a static tunable magnetic field $B_{0}$ and a radio-frequency (rf) field. (Middle) In situ optical density image of the spin-1/2 particles. (Right) Schematic of the level structure, showing that the bath atoms are unaffected by the rf drive that connects $\ket{\downarrow}$ and $\ket{\uparrow}$. (b) Interaction strengths between two spin states and the bath atoms ($k_{\text{F}}a_{\uparrow\text{B}}$ and $k_{\text{F}}a_{\downarrow\text{B}}$) as a function of $B_{0}$. The BCS and BEC regimes correspond to $a_{\uparrow\text{B}}<0$ and $a_{\uparrow\text{B}}>0$, respectively. (c) (Top) Linear-response spectrum $R_{\downarrow}(\Delta)$ (solid blue circles) measured at $1/(k_{\mathrm{F}}a_{\uparrow\text{B}})\approx-0.5$ [indicated by the purple arrow in (b)] with $\hbar\Omega_{0}\approx 0.017E_{\mathrm{F}}$ and $t=4\,\mathrm{ms}$ ($\Omega_{0}t\approx 2.5$). (Bottom) Steady-state magnetization $\mathcal{M}_{\infty}(\Delta)$ at the same magnetic field with $\hbar\Omega_{0}\approx 0.09E_{\mathrm{F}}$; in practice, $t=20\,\mathrm{ms}$ so that $\Omega_{0}t\approx 62$. The red solid line is Eq. (1). The vertical red band and blue band mark the positions and uncertainties of $\Delta_{0}$ and $\Delta_{\text{p}}$, respectively.

![Figure 3](2605.06666v1_assets/Fig3.svg)

**Figure 3.** Testing the Kubo-Thermalization correspondence across the BCS-BEC crossover. (a) $R_{\downarrow}(\Delta)$ (blue circles, top), measured with $\hbar\Omega_{0}\approx 0.028E_{\mathrm{F}}$ and $t=4\,\mathrm{ms}$ ($\Omega_{0}t\approx 4$) and the steady-state magnetization $\mathcal{M}_{\infty}(\Delta)$ (red circles, bottom), measured with $\hbar\Omega_{0}\approx 0.27E_{\mathrm{F}}$ and $t=20\,\mathrm{ms}$ ($\Omega_{0}t\approx 195$). Both measurements are performed at $1/(k_{\mathrm{F}}a_{\uparrow\text{B}})\approx 0.5$. The vertical red and blue bands indicate the values and uncertainties of $\Delta_{0}$ and $\Delta_{\text{p}}$, respectively, and the red solid curve corresponds to Eq. (1). (b) Difference $\Delta_{\text{p}}-\Delta_{0}$ versus the full width at half maximum $\Gamma$. The black dashed line represents a power-law fit in $\log$-$\log$ scale (see text). (c) Examples of linear-response spectra $R_{\downarrow}(\Delta)$ (filled circles) and $R_{\uparrow}(\Delta)$ (open diamonds) on the BCS side ($1/(k_{\mathrm{F}}a_{\uparrow\text{B}})\approx-0.5$, in purple) and on the BEC side ($1/(k_{\mathrm{F}}a_{\uparrow\text{B}})\approx 0.5$, in blue); note that the spectra on the BEC side are multiplied by $2$ for clarity. (d) $\Delta_{0}$ versus $1/(k_{\mathrm{F}}a_{\uparrow\text{B}})$ (the binding energy $-\epsilon_{\mathrm{b}}$ is removed, see text). Red circles represent experimentally determined $\Delta_{0}$ directly from $\mathcal{M}_{\infty}$, while black squares show the predicted $\Delta_{0}$ computed from the symmetrized Kubo-Thermalization relation (see text) using the experimentally measured $R_{\uparrow}(\Delta)$ and $R_{\downarrow}(\Delta)$ as inputs.

We explore the correspondence experimentally in an ultracold-atom platform: a spatially uniform gas of <sup>6</sup>Li atoms confined in an optical box trap [<sup>17, 13, 8</sup>] (Fig. 2 a). The spin is encoded in two internal states of <sup>6</sup>Li, denoted $\ket{\uparrow}$ and $\ket{\downarrow}$, while the bath consists of atoms in a third state $\ket{\mathrm{B}}$. To realize the individual-spin scenario, we prepare highly imbalanced mixtures with spin fraction $x\equiv n_{\downarrow}^{(0)}/n_{\mathrm{B}}\ll 1$, where $n_{\downarrow}^{(0)}$ and $n_{\mathrm{B}}$ are the initial densities of spins and bath atoms. In practice, $x\lesssim 0.15$, making spin–spin interactions negligible and the back-action of the spins on the bath weak. The bath Fermi energy is $E_{\mathrm{F}}\approx 2\pi\hbar\times 6\,\mathrm{kHz}$, corresponding to a Fermi time $\tau_{\mathrm{F}}\equiv\hbar/E_{\mathrm{F}}\approx 25\,\mathrm{\mu s}$; the temperature of the bath is $T=0.25(2)\,T_{\mathrm{F}}$ with $T_{\mathrm{F}}=E_{\mathrm{F}}/k_{\mathrm{B}}$, and $k_{\mathrm{B}}$ is Boltzmann’s constant (see Methods).

At $t=0$ we apply a radio-frequency (rf) field with Rabi frequency $\Omega_{0}$ and detuning $\Delta$, defined relative to the bare $\ket{\downarrow}$–$\ket{\uparrow}$ transition in the absence of the bath. Spin–bath interactions are set by the s-wave scattering lengths $a_{j\mathrm{B}}$ ($j=\downarrow,\uparrow$) and are tuned using a magnetic Feshbach resonance [<sup>18</sup>] (Fig. 2 b). We choose a range of bias fields $B_{0}$ for which the two spin states couple very differently to the bath: typically $\ket{\uparrow}$ is strongly interacting ($|k_{\mathrm{F}}a_{\uparrow\mathrm{B}}|\gtrsim 1$) while $\ket{\downarrow}$ is weakly interacting ($|k_{\mathrm{F}}a_{\downarrow\mathrm{B}}|\ll 1$), as shown in Fig. 2 b. This configuration provides a near-ideal setting to test the correspondence.

We begin in the most tractable regime, the Bardeen–Cooper–Schrieffer (BCS) side of the Feshbach resonance ($a_{\uparrow\mathrm{B}}<0$), where $\ket{\uparrow}$–$\ket{\mathrm{B}}$ interactions produce well-defined quasiparticles known as attractive Fermi polarons [<sup>19, 20</sup>]. At short times, we measure the linear-response spectrum $R_{\downarrow}(\Delta)$, normalized to the bath timescale $\tau_{\mathrm{F}}$ (top panel of Fig. 2 c). The spectrum is narrow and nearly symmetric, with a peak at $\Delta_{\mathrm{p}}$ (vertical blue band). The shift of $\Delta_{\mathrm{p}}$ from zero is a direct consequence of interactions.

At long times, we measure the steady-state magnetization spectrum $\mathcal{M}_{\infty}(\Delta)$ reached after a long (but weak) rf pulse (bottom of Fig. 2 c) [<sup>21</sup>]. We find that $\mathcal{M}_{\infty}(\Delta)$ follows Eq. (1) closely (red solid line), and that $\Delta_{0}$ (vertical red band) coincides with the spectral peak $\Delta_{\mathrm{p}}$. This agreement is the expected limit of the Kubo-Thermalization correspondence when $R_{\downarrow}(\Delta)=\delta(\Delta-\Delta_{\mathrm{p}})$, in which case Eq. (2) reduces to $\Delta_{0}=\Delta_{\mathrm{p}}$.

We next perform a more stringent test of the correspondence in a regime where $R_{\downarrow}(\Delta)$ departs markedly from a delta function. This is realized on the Bose–Einstein condensation (BEC) side of the Feshbach resonance, $a_{\uparrow\mathrm{B}}>0$, where stronger impurity–bath coupling broadens the excitation spectrum (Fig. 3 a). Although the steady-state magnetization spectrum still follows Eq. (1) (bottom panel of Fig. 3 a), the inferred $\Delta_{0}$ now clearly differs from $\Delta_{\mathrm{p}}$. To quantify this deviation, we measure $\Delta_{\mathrm{p}}-\Delta_{0}$ as a function of $a_{\uparrow\mathrm{B}}$. We find that $\Delta_{\mathrm{p}}\approx\Delta_{0}$ persists well into the BEC regime, up to $1/(k_{\mathrm{F}}a_{\uparrow\mathrm{B}})\approx 0.3$, after which the discrepancy grows monotonically (Extended Data Fig. 1 in Methods).

Equation (2) suggests a natural origin for this deviation. Indeed, for a spectrum with finite full width at half maximum $\Gamma$, Eq. (2) generally implies $\Delta_{\mathrm{p}}\neq\Delta_{0}$. We verify this by plotting the deviation $\Delta_{\text{p}}-\Delta_{0}$ versus $\Gamma$, reconstructed by varying $k_{\mathrm{F}}a_{\uparrow\text{B}}$ (see Fig. 3 b and Extended Data Fig. 1 in Methods). Interestingly, the fitted scaling $\Delta_{\text{p}}-\Delta_{0}\propto\Gamma^{2.2(2)}$ (dashed line) is close to the prediction $\Delta_{\text{p}}-\Delta_{0}\propto\Gamma^{2}$ from inserting a Gaussian ansatz $R_{\downarrow}(\Delta)=\frac{1}{\sqrt{2\pi}\gamma}\exp\left(-\frac{(\Delta-\Delta_{\text{p}})^{2}}{2\gamma^{2}}\right)$ with $\gamma=\Gamma/(2\sqrt{2\ln 2})$ into Eq. (2).

A full test of the Kubo-Thermalization correspondence requires determining both sides of Eq. (2). In practice, directly evaluating Eq. (2) is challenging because the $\Delta<0$ tail of $R_{\downarrow}(\Delta)$ is exponentially amplified, demanding prohibitively high signal-to-noise. We circumvent this by deriving a symmetrized form of the correspondence $\mathcal{F}_{\downarrow}(\Delta_{0})=\mathcal{F}_{\uparrow}(-\Delta_{0})$, where $\mathcal{F}_{j}(z)\equiv\int_{z}^{\infty}\mathrm{d}\Delta~R_{j}(\pm\Delta)\Big(e^{-\beta\hbar(\Delta-z)}-1\Big)$, $R_{\uparrow}(\Delta)$ is the spectrum measured when the spin is initialized in $\ket{\uparrow}$, and the plus (resp. minus) sign applies to $j=\downarrow$ (resp. $\uparrow$); see Methods for the derivation. This symmetrized expression avoids exponential amplification of the tails in both $R_{\downarrow}$ and $R_{\uparrow}$.

In Fig. 3 c, we show representative spectra $R_{\downarrow}$ (filled circles) and $R_{\uparrow}$ (open diamonds) for two values of $k_{\mathrm{F}}a_{\uparrow\mathrm{B}}$. As shown in Fig. 3 d, $\Delta_{0}$ extracted from $\mathcal{M}_{\infty}(\Delta)$ (red circles) agrees closely with $\Delta_{0}$ obtained from the symmetrized correspondence (black squares) across the BCS-BEC crossover; to make the comparison more demanding, we removed the binding energy $-\epsilon_{\mathrm{b}}\equiv-\hbar^{2}/(ma_{\uparrow\text{B}}^{2})$ on the BEC side. The agreement is particularly striking because, in this strongly correlated regime, calculating $\Delta_{0}$ and $R_{\downarrow,\uparrow}$ poses serious theoretical challenges [<sup>8, 6, 7</sup>], so that no reliable predictions exist for the data in Fig. 3 d. As an independent consistency check of thermalization, we measure the susceptibility $\chi\equiv(\partial\mathcal{M}_{\infty}/\partial(\hbar\Delta))|_{\Delta=\Delta_{0}}$ and find that it is constant across interactions and equal to $\beta/2$, with $\beta$ independently obtained from time-of-flight thermometry of the bath (Extended Data Fig. 2 in Methods). This verifies that the driven spin equilibrates to the bath temperature. Together, Fig. 3 d and Extended Data Fig. 2 provide a complete experimental confirmation of the Kubo-Thermalization correspondence.

![Figure 4](2605.06666v1_assets/Fig4.png)

![Figure 4](2605.06666v1_assets/Fig4.png)

**Figure 4.** The Kubo-Thermalization correspondence for the metastable (repulsive) branch. (a) Intensity map of $R_{\downarrow}(\Delta)$ across different interaction strengths $1/(k_{\mathrm{F}}a_{\uparrow\text{B}})$. (b) Top panel: Linear-response spectrum $R_{\downarrow}(\Delta)$ (blue circles), measured with $\hbar\Omega_{0}\approx 0.003E_{\text{F}}$ and $t=12\,\mathrm{ms}$ ($\Omega_{0}t\approx 1.4$). Lower panel: steady-state magnetization $\mathcal{M}_{\infty}(\Delta)$ (red circles) measured with $\hbar\Omega_{0}\approx 0.27E_{\mathrm{F}}$ and $t=200\,\mathrm{ms}$ ($\Omega_{0}t\approx 1950$). Both measurements are performed at $1/(k_{\mathrm{F}}a_{\uparrow\text{B}})\approx 4.2$, shown for detunings near the repulsive polaron energy. Vertical red and blue bands mark the values and uncertainties of $\Delta_{0}$ and $\Delta_{\text{p}}$, respectively. (c) Deviation $\Delta_{\text{p}}-\Delta_{0}$ for the repulsive branch in the regime $1/(k_{\text{F}}a_{\uparrow\text{B}})\gg 1$. The gray horizontal line indicates $0$. Inset: Lifetime $\tau$ of the repulsive branch.

Finally, we show that the Kubo-Thermalization correspondence remains valid on a metastable branch. To this end, we focus on the regime $1/(k_{\mathrm{F}}a_{\uparrow\mathrm{B}})\gg 1$, where a weakly repulsive Fermi polaron can be long-lived despite lying above the Feshbach-molecule ground state [<sup>22, 23</sup>]. In this limit the spectrum exhibits two branches (Fig. 4 a): a metastable repulsive-polaron feature at $\Delta>0$ (highlighted by the rectangle) and an attractive molecular feature at $\Delta<0$. In the regime explored here, $R_{\downarrow}$ is sharply peaked at the repulsive-polaron energy so that we expect $\Delta_{0}\approx\Delta_{\text{p}}$. In Fig. 4 b, we compare $R_{\downarrow}(\Delta)$ (blue circles) and $\mathcal{M}_{\infty}(\Delta)$ (red circles) near the repulsive-polaron energy for $1/(k_{\mathrm{F}}a_{\uparrow\mathrm{B}})\approx 4.2$. The extracted $\Delta_{0}$ coincides with $\Delta_{\mathrm{p}}$, consistent with the correspondence.

This measurement is delicate because it must satisfy competing constraints: interactions must be strong enough to enable thermalization under driving, yet weak enough to suppress coupling between the repulsive and attractive branches. Consistent with this picture, Fig. 4 c shows that the correspondence holds only within an intermediate interaction window. For smaller $k_{\mathrm{F}}a_{\uparrow\mathrm{B}}$, thermalization becomes too slow and is ultimately limited by experimental timescales (e.g. the vacuum-limited lifetime). For larger $k_{\mathrm{F}}a_{\uparrow\mathrm{B}}$, the repulsive branch rapidly decays into the lower branch (which is related to losses in the three-component mixture [<sup>24</sup>]). We confirm this interpretation by measuring the impurity lifetime $\tau$ versus $1/(k_{\mathrm{F}}a_{\uparrow\mathrm{B}})$ (inset of Fig. 4 c): the agreement $\Delta_{0}\approx\Delta_{\mathrm{p}}$ is obtained when thermalization occurs faster than $\tau$. These results show that the Kubo-Thermalization correspondence can apply even when equilibration is restricted to a sector of the Hilbert space on relevant timescales.

In summary, this work has uncovered a fundamental and rigorous correspondence between short- and long-time many-body quantum dynamics. We established this result experimentally using tunable ultracold fermions over a wide range of interactions. Because this correspondence is general, it could find applications in other systems such as NMR [<sup>25</sup>], trapped ions [<sup>26</sup>], and Rydberg atom arrays [<sup>27</sup>], where similar quantum spin dynamics take place, thereby opening a new pathway to understanding quantum thermalization and its universal signatures in non-equilibrium dynamics.

Acknowledgment. We thank Franklin Vivanco for contributions in the early stages of this project. We thank Xiaoling Cui, Qi Gu, and Tiangang Zhou for helpful discussions, and Nathan Apfel for comments on the manuscript. N.N. acknowledges support from the ARO (Grant No. W911NF-25-1-0285), the AFOSR (Grant No. FA9550-23-1-0605), the David and Lucile Packard Foundation, and the Alfred P. Sloan Foundation. H.Z. acknowledges support from the National Key Research and Development Program of China (Grant No. 2023YFA1406702), and the National Natural Science Foundation of China (Grant Nos. 12488301 and U23A6004). P.Z. acknowledges support from the National Natural Science Foundation of China (Grant Nos. 12374477), and the Shanghai Rising-Star Program (Grant No. 24QA2700300).

## I Methods

### I.1 Preparation of highly imbalanced uniform Fermi gases

We prepare an incoherent mixture of the first and third lowest Zeeman sublevels of <sup>6</sup>Li, denoted $\ket{\uparrow}$ and $\ket{\text{B}}$, in a red-detuned optical dipole trap. The impurity spin-$1/2$ states are encoded in the internal states $\ket{\uparrow}\equiv\ket{F=1/2,m_{F}=+1/2}$ and $\ket{\downarrow}\equiv\ket{F=1/2,m_{F}=-1/2}$, while the bath atoms occupy the state $\ket{\text{B}}\equiv\ket{F=3/2,m_{F}=-3/2}$ (the labels $\ket{F,m_{F}}$ refer to the corresponding states in the low-field basis). Following procedures similar to Ref. [<sup>8</sup>], we prepare a highly imbalanced mixture in a cylindrical optical box trap, with initial impurity fraction $x=n_{\downarrow}^{(0)}/n_{\text{B}}\lesssim 0.15$, at a magnetic field of $B\approx 700\,\mathrm{G}$. At this field, the impurity–bath interaction is weak for $\ket{\downarrow}$, with $k_{\mathrm{F}}a_{\downarrow\text{B}}\approx 0.2$. The gas is held for 400 ms to equilibrate, after which the magnetic field is ramped to its final value $B_{0}$ and the system is allowed to equilibrate for an additional 1 s before applying the rf drive. To initialize impurities in the $\ket{\uparrow}$ state, we apply a resonant 12 $\mu$ s rf $\pi$ pulse at 700 G (where $1/(k_{\mathrm{F}}a_{\uparrow\text{B}})\approx-0.5$) to transfer all impurities from $\ket{\downarrow}$ to $\ket{\uparrow}$, and then repeat the same sequence.

### I.2 Measurement of $\Delta_{\text{p}}-\Delta_{0}$ versus interaction strength

In Extended Data Fig. 1, we show $\Delta_{\text{p}}-\Delta_{0}$ as a function of $1/(k_{\mathrm{F}}a_{\uparrow\text{B}})$. We also show the spectral width $\Gamma$ (inset) extracted by fitting a Lorentzian function to $R_{\downarrow}(\Delta)$; Gaussian fits give consistent results within error bars.

![Figure 1](2605.06666v1_assets/EFig1.svg)

Extended Data Fig. 1: Difference $\Delta_{\text{p}}-\Delta_{0}$ as a function of $1/(k_{\mathrm{F}}a_{\uparrow\text{B}})$. Inset: $\hbar\Gamma/E_{\text{F}}$ extracted from a Lorentzian fit to $R_{\downarrow}(\Delta)$ versus $1/(k_{\text{F}}a_{\uparrow\text{B}})$.

### I.3 Measurement of $\chi$

In Extended Data Fig. 2, we show the slope $\chi\equiv(\partial\mathcal{M}_{\infty}/\partial(\hbar\Delta))|_{\Delta=\Delta_{0}}$ as a function of $1/(k_{\mathrm{F}}a_{\uparrow\text{B}})$. The bath temperature $T=0.25(2)T_{\mathrm{F}}$ (gray band) is extracted by time-of-flight measurement of the bath atoms.

![Figure 2](2605.06666v1_assets/EFig2.svg)

Extended Data Fig. 2: Verification of thermalization. Susceptibility $\chi\equiv(\partial\mathcal{M}_{\infty}/\partial(\hbar\Delta))|_{\Delta=\Delta_{0}}$ as a function of $1/(k_{\text{F}}a_{\uparrow\text{B}})$. The gray band is determined from the bath temperature $T/T_{\mathrm{F}}=0.25(2)$ (which is measured by time of flight of the bath component).

### I.4 Derivation of the Kubo-Thermalization correspondence

We consider a spin-1/2 impurity that is driven near resonance by an external field, and coupled to a large unspecified thermal bath with temperature $T=1/\beta$ (we take $\hbar=k_{\mathrm{B}}=1$ in this section). The total Hilbert space is $\mathcal{H}^{\text{tot}}=\mathcal{H}^{\text{s}}\otimes\mathcal{H}^{\text{res}}$, where $\mathcal{H}^{\text{s}}$ is the two-dimensional Hilbert space of a single spin $1/2$, and $\mathcal{H}^{\text{res}}$ is the Hilbert space of all other degrees of freedom in the problem. The total Hamiltonian is

$$ \hat{H}=\hat{H}^{\text{s}}+\hat{H}^{\text{B}}+\hat{H}^{\text{int}}, $$
(S1)

where the spin part (acting on $\mathcal{H}^{\text{s}}$) in the rotating frame of the drive is

$$ \hat{H}^{\text{s}}=-\frac{1}{2}\Delta\hat{\sigma}_{z}+\frac{1}{2}\Omega_{0}\hat{\sigma}_{x}, $$
(S2)

where $\Delta$ and $\Omega_{0}$ are the detuning and Rabi frequency of the drive. Here, $\hat{\sigma}_{x,z}$ denote the Pauli operators. The bath Hamiltonian $\hat{H}^{\text{B}}$ acts on (a subset of) $\cal H^{\text{res}}$ and is assumed to be time independent but otherwise unspecified. The spin-bath interaction acts on $\cal H^{\text{tot}}$ and is assumed to take the form

$$ \hat{H}^{\text{int}}=\hat{n}_{\uparrow}\hat{O}_{\uparrow}+\hat{n}_{\downarrow}\hat{O}_{\downarrow}. $$
(S3)

The operators $\hat{O}_{\uparrow,\downarrow}$ act on $\mathcal{H}^{\text{res}}$, and $\hat{n}_{\uparrow,\downarrow}=(1\pm\hat{\sigma}_{z})/2$ are the spin projection operators for the impurity acting on $\mathcal{H}^{\text{s}}$. This form for $\hat{H}^{\text{int}}$ covers both cases of immobile and mobile impurities. Indeed, for an immobile impurity $\mathcal{H}^{\text{res}}$ coincides with $\mathcal{H}^{\text{B}}$ [<sup>28</sup>], the Hilbert space of the bath. For a mobile impurity, $\mathcal{H}^{\text{res}}=\mathcal{H}^{\text{B}}\otimes\mathcal{H}^{\text{sp}}$ also includes the spatial degrees of freedom of the impurity. In that case, the energy associated with these other degrees of freedom (e.g. the kinetic energy) can be absorbed in the definition of $\hat{O}_{\uparrow,\downarrow}$ so that the form of Eq. (S1) still works. We only require that the impurity-bath interactions do not flip the spin of the impurity.

We initialize the spin in either $\ket{\uparrow}$ or $\ket{\downarrow}$ and turn on the external drive at $t=0$. Our primary observable here is the magnetization $\mathcal{M}\equiv\braket{\hat{\sigma}_{z}}$. The key assumption of the following derivation is that the weakly driven spin thermalizes in the long-time limit with the bath, at temperature $T$. For sufficiently small $\Omega_{0}$, the asymptotic magnetization $\mathcal{M}_{\infty}\equiv\mathcal{M}(t\rightarrow\infty)$ takes the form:

$\displaystyle\mathcal{M}_{\infty}=\frac{\text{tr}(e^{-\beta\hat{H}}\hat{\sigma}_{z})}{\text{tr}(e^{-\beta\hat{H}})}$
$\displaystyle=\frac{e^{\beta\frac{\Delta}{2}}\,\text{tr}_{\text{res}}(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{\uparrow})})-e^{-\beta\frac{\Delta}{2}}\,\text{tr}_{\text{res}}(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{\downarrow})})}{e^{\beta\frac{\Delta}{2}}\,\text{tr}_{\text{res}}(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{\uparrow})})+e^{-\beta\frac{\Delta}{2}}\,\text{tr}_{\text{res}}(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{\downarrow})})},$
(S4)

where tr and $\text{tr}_{\text{res}}$ respectively denote the traces over $\mathcal{H}^{\text{tot}}$ and $\mathcal{H}^{\text{res}}$.

Defining the zero crossing $\Delta_{0}$ as

$$ \Delta_{0}\equiv\frac{1}{\beta}\ln\frac{\text{tr}_{\text{res}}(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{\downarrow})})}{\text{tr}_{\text{res}}(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{\uparrow})})}, $$
(S5)

Eq. (S4) simplifies to the universal form Eq. (1):

$$ \mathcal{M}_{\infty}(\Delta)=\tanh\left(\frac{\beta(\Delta-\Delta_{0})}{2}\right). $$
(S6)

Next, we calculate the linear-response spectrum $R_{\downarrow}(\Delta)$ for a spin initialized in $\ket{\downarrow}$ and coupled to $\ket{\uparrow}$ using Fermi’s Golden Rule:

$\displaystyle R_{\downarrow}(\Delta)=\sum\limits_{\nu,\mu}p_{\nu}\left|\bra{\uparrow;\mu}\hat{\sigma}_{x}\ket{\downarrow;\nu}\right|^{2}\delta(E_{\downarrow,\nu}-E_{\uparrow,\mu})$
$\displaystyle=\frac{1}{2\pi}\int_{-\infty}^{\infty}\mathrm{d}t\,e^{it\Delta}\frac{\text{tr}_{\text{res}}\left(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{\downarrow})}e^{it(\hat{H}^{\text{B}}+\hat{O}_{\downarrow})}e^{-it(\hat{H}^{\text{B}}+\hat{O}_{\uparrow})}\right)}{\text{tr}_{\text{res}}\left(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{\downarrow})}\right)}$
$\displaystyle=\frac{1}{2\pi}\int_{-\infty}^{\infty}\mathrm{d}t\,e^{it\Delta}\mathcal{R}_{\downarrow}(t),$
(S7)

where $\ket{\downarrow;\nu}$ and $\ket{\uparrow;\mu}$ denote the eigenstates of $\hat{H}$ at $\Omega_{0}=0$, where the spin is respectively in state $\ket{\downarrow}$ and $\ket{\uparrow}$ (the indices $\nu$ and $\mu$ span the Hilbert space $\mathcal{H}^{\text{res}}$). The energy of those states are $E_{\downarrow,\nu}$ and $E_{\uparrow,\mu}$ and $p_{\nu}=e^{-\beta E_{\downarrow,\nu}}/\sum\limits_{\nu^{\prime}}e^{-\beta E_{\downarrow,\nu^{\prime}}}$ is a Boltzmann weight. $\mathcal{R}_{\downarrow}(t)$ is the Fourier transform of $R_{\downarrow}(\Delta)$. Note that $R_{\downarrow}$ obeys the spectral sum rule

$$ \int_{-\infty}^{\infty}\mathrm{d}\Delta~R_{\downarrow}(\Delta)=1. $$
(S8)

It is important to note that $\mathcal{R}_{\downarrow}(t)$ is analytic on the strip $-\beta<\text{Im}\,t<0$ and continuous on its boundaries $\text{Im}\,t=0$ and $-\beta$, provided that the spectrum of $\hat{H}$ is bounded from below. This allows the following analytic continuation:

$$ \mathcal{R}_{\downarrow}(-i\beta)=\frac{\text{tr}_{\text{res}}\left(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{\uparrow})}\right)}{\text{tr}_{\text{res}}\left(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{\downarrow})}\right)}=e^{-\beta\Delta_{0}}. $$
(S9)

We can then reverse the Fourier transform in Eq. (S7) and perform the analytic continuation to obtain

$$ \mathcal{R}_{\downarrow}(-i\beta)=\int_{-\infty}^{\infty}\mathrm{d}\Delta~R_{\downarrow}(\Delta)e^{-\beta\Delta}=e^{-\beta\Delta_{0}}. $$
(S10)

Along with Eqs. (S5)-(S6), this yields the main result, Eq. (2).

To derive the symmetrized form of Eq. (2), we calculate $R_{\uparrow}(\Delta)$ for a spin initialized in $\ket{\uparrow}$ along the lines of Eq. (S7). This allows us to derive an important relation connecting $R_{\uparrow}(\Delta)$ and $R_{\downarrow}(\Delta)$:

$\displaystyle R_{\uparrow}(\Delta)$
$\displaystyle=\frac{1}{2\pi}\int_{-\infty}^{\infty}\mathrm{d}t\,e^{-it\Delta}e^{\beta\Delta_{0}}$
(S11)
$\displaystyle\times\frac{\text{tr}_{\text{res}}\left(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{\uparrow})}e^{it(\hat{H}^{\text{B}}+\hat{O}_{\uparrow})}e^{-it(\hat{H}^{\text{B}}+\hat{O}_{\downarrow})}\right)}{\text{tr}_{\text{res}}\left(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{\downarrow})}\right)}$
$\displaystyle=\frac{1}{2\pi}e^{\beta\Delta_{0}}\int_{-\infty}^{\infty}\mathrm{d}t^{\prime}\,e^{(it^{\prime}-\beta)\Delta}\mathcal{R}_{\downarrow}(t^{\prime})$
$\displaystyle=e^{-\beta(\Delta-\Delta_{0})}R_{\downarrow}(\Delta).$

The first equality utilizes the analyticity of $\mathcal{R}_{\downarrow}$ to shift the integration contour by $-i\beta$ and a change of variable $t^{\prime}=-t-i\beta$. This result, as a manifestation of detailed balance, connects the forward and reverse transition rates of a single spin in thermal equilibrium with a bath [<sup>29</sup>]. Finally, we find the symmetrized version of the correspondence, $\mathcal{F}_{\downarrow}(\Delta_{0})=\mathcal{F}_{\uparrow}(-\Delta_{0})$, by plugging both Eq. (S11) and Eq. (S8) into Eq. (2).

### I.5 Generalization of the Kubo-Thermalization correspondence to an $N$-level system

Consider the following Hamiltonian:

$$ \hat{H}^{\text{s}}=\sum\limits_{i}^{N}E_{i}\ket{i}\bra{i}+\frac{1}{2}\sum\limits_{i\neq j}\Omega_{ij}\ket{i}\bra{j}, $$
(S12)

where $\ket{i}$ is the eigenstate of the system with energy $E_{i}$. The system-bath interaction takes the form of $\hat{H}^{\text{int}}=\sum\limits_{i}^{N}\hat{n}_{i}\hat{O}_{i}$ with $\hat{n}_{i}\equiv\ket{i}\bra{i}$.

Initializing the system in one of these eigenstates $\ket{k}$, we define the magnetization to be $\mathcal{M}^{k}\equiv\braket{\sum\limits_{i\neq k}\hat{n}_{i}-\hat{n}_{k}}$. At long time and sufficiently small $\Omega_{ij}$, we assume that the system will thermalize with the bath and thus the magnetization will take the form

$$ \mathcal{M}_{\infty}^{k}(E_{k})=\tanh\left(\frac{\beta(E_{k}-\mathcal{E}_{0}^{k})}{2}\right), $$
(S13)

where the generalized zero crossing $\mathcal{E}_{0}^{k}$ is defined as

$$ \mathcal{E}_{0}^{k}\equiv\frac{1}{\beta}\ln\frac{\text{tr}_{\text{res}}(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{k})})}{\sum\limits_{i\neq k}\text{tr}_{\text{res}}(e^{-\beta(\hat{H}^{\text{B}}+\hat{O}_{i}+E_{i})})}. $$
(S14)

The generalization of the correspondence involves the individual linear-response spectra from state $\ket{k}$ to state $\ket{i\neq k}$: $R_{ki}(E_{k})=1/(\pi\Omega_{ki}^{2})\mathrm{d}\mathcal{M}/\mathrm{d}t$, where all $\Omega_{kj}=0$ except for $j=i$. The generalized correspondence is

$$ \mathcal{E}_{0}^{k}=-\frac{1}{\beta}\ln\left[\sum\limits_{i\neq k}\int_{-\infty}^{\infty}\mathrm{d}\mathcal{E}~R_{ki}(\mathcal{E})e^{-\beta\mathcal{E}}\right]. $$
(S15)

Given its general nature, it is likely that the Kubo-Thermalization correspondence could be further generalized to various other types of observables and spin-bath interactions.

## References (29 total, showing 29)

[1] Linden, N., Popescu, S., Short, A. J., Winter, A., Quantum mechanical evolution towards thermal equilibrium, Phys. Rev. E 79, 061103 (2009).
[2] Nandkishore, R., Huse, D. A., Many-body localization and thermalization in quantum statistical mechanics, Annu. Rev. Condens. Matter Phys. 6, 15–38 (2015).
[3] Eisert, J., Friesdorf, M., Gogolin, C., Quantum many-body systems out of equilibrium, Nature Phys. 11, 124–130 (2015).
[4] Fermi, E., Nuclear physics: a course given by Enrico Fermi at the University of Chicago (University of Chicago Press, 1950).
[5] Kubo, R., Statistical-mechanical theory of irreversible processes. I. General theory and simple applications to magnetic and conduction problems, J. Phys. Soc. Jpn. 12, 570–586 (1957).
[6] Hu, H., Wang, J., Liu, X.-J., Theory of the Spectral Function of Fermi Polarons at Finite Temperature, Phys. Rev. Lett. 133, 083403 (2024).
[7] Mulkerin, B. C., Levinsen, J., Parish, M. M., Rabi oscillations and magnetization of a mobile spin-1/2 impurity in a Fermi sea, Phys. Rev. A 109, 023302 (2024).
[8] Vivanco, F. J., et al., The strongly driven Fermi polaron, Nature Phys. 21, 564–569 (2025).
[9] Damascelli, A., Hussain, Z., Shen, Z.-X., Angle-resolved photoemission studies of the cuprate superconductors, Rev. Mod. Phys. 75, 473–541 (2003).
[10] Boschini, F., Zonno, M., Damascelli, A., Time-resolved ARPES studies of quantum materials, Rev. Mod. Phys. 96, 015003 (2024).
[11] Furrer, A., Mesot, J. F., Strässle, T., Neutron scattering in condensed matter physics, vol. 4 (World Scientific Publishing Company, 2009).
[12] Devereaux, T. P., Hackl, R., Inelastic light scattering from correlated electrons, Rev. Mod. Phys. 79, 175–233 (2007).
[13] Navon, N., Smith, R. P., Hadzibabic, Z., Quantum gases in optical boxes, Nature Phys. 17, 1334–1341 (2021).
[14] Vale, C. J., Zwierlein, M., Spectroscopic probes of quantum gases, Nature Phys. 17, 1305–1315 (2021).
[15] Leggett, A. J., et al., Dynamics of the dissipative two-state system, Rev. Mod. Phys. 59, 1 (1987).
[16] Chen, J., et al., Emergence of Fermi’s Golden Rule in the Probing of a Quantum Many-Body System, arXiv:2502.14867 (2025).
[17] Mukherjee, B., et al., Homogeneous atomic Fermi gases, Phys. Rev. Lett. 118, 123401 (2017).
[18] Chin, C., Grimm, R., Julienne, P., Tiesinga, E., Feshbach resonances in ultracold gases, Rev. Mod. Phys. 82, 1225–1286 (2010).
[19] Chevy, F., Mora, C., Ultra-cold polarized Fermi gases, Rep. Prog. Phys. 73, 112401 (2010).
[20] Massignan, P., Zaccanti, M., Bruun, G. M., Polarons, dressed molecules and itinerant ferromagnetism in ultracold Fermi gases, Rep. Prog. Phys. 77, 034401 (2014).
[21] We use a stronger drive to reach the steady state more rapidly (while still satisfying $\hbar\Omega_{0}\ll E_{\mathrm{F}}$) in order to minimize atom loss in the three-component mixture [ 24 ]. For all the data shown, the total impurity loss remains below $10\%$. We further verify that the extracted $\Delta_{0}$ is independent of the drive strength $\Omega_{0}$ over the explored parameter range.
[22] Cui, X., Zhai, H., Stability of a fully magnetized ferromagnetic state in repulsively interacting ultracold Fermi gases, Phys. Rev. A 81, 041602 (2010).
[23] Scazza, F., Zaccanti, M., Massignan, P., Parish, M. M., Levinsen, J., Repulsive Fermi and Bose polarons in quantum gases, Atoms 10, 55 (2022).
[24] Schumacher, G. L., et al., Observation of anomalous decay of a polarized three-component Fermi gas, Nature Comm. 17, 174 (2026).
[25] Du, J., Shi, F., Kong, X., Jelezko, F., Wrachtrup, J., Single-molecule scale magnetic resonance spectroscopy using quantum diamond sensors, Rev. Mod. Phys. 96, 025001 (2024).
[26] Monroe, C., et al., Programmable quantum simulations of spin systems with trapped ions, Rev. Mod. Phys. 93, 025001 (2021).
[27] Browaeys, A., Lahaye, T., Many-body physics with individually controlled Rydberg atoms, Nature Phys. 16, 132–142 (2020).
[28] Knap, M., Abanin, D. A., Demler, E., Dissipative Dynamics of a Driven Quantum Spin Coupled to a Bath of Ultracold Fermions, Phys. Rev. Lett. 111, 265302 (2013).
[29] Liu, W. E., Shi, Z.-Y., Levinsen, J., Parish, M. M., Radio-frequency response and contact of impurities in a quantum gas, Phys. Rev. Lett. 125, 065301 (2020).
