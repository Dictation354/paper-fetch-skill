---
title: "Optimal Transition Paths for AMOC Collapse and Recovery in a Stochastic Box Model"
authors: "Jelle Soons, Tobias Grafke, Henk A. Dijkstra"
doi: "10.1175/jpo-d-23-0234.1"
source: "ams_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 22697
---

# Optimal Transition Paths for AMOC Collapse and Recovery in a Stochastic Box Model

## Abstract

There is strong evidence that the present-day Atlantic meridional overturning circulation (AMOC) is in a bistable regime, and hence, it is important to determine probabilities and pathways for noise-induced transitions between its equilibrium states. Here, using large deviation theory (LDT), the most probable transition pathways for the noise-induced collapse and recovery of the AMOC are computed in a stochastic box model of the World Ocean. This allows us to determine the physical mechanisms of noise-induced AMOC transitions. We show that the most likely path of an AMOC collapse starts paradoxically with a strengthening of the AMOC followed by an immediate drop within a couple of years due to a short but relatively strong freshwater pulse. The recovery on the other hand is a slow process, where the North Atlantic needs to be gradually salinified over the course of 20 years. The proposed method provides several benefits, including an estimate of probability ratios of collapse between various freshwater noise scenarios, showing that the AMOC is most vulnerable to freshwater forcing into the Atlantic thermocline region. Moreover, a comparison with a quasi-equilibrium approach reveals the contrasts in the behavior of a bifurcation- and noise-induced collapse of the AMOC.

## 1. Introduction

The Atlantic meridional overturning circulation (AMOC) is of paramount importance to Earth’s climate ([Srokosz et al. 2023](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib43)). It consists of a northward transport of warm upper-ocean water and a deeper southward flow of cool water. This northward heat transport is a major reason for the relatively mild climate in western Europe. An important process behind this circulation is thought to be the water mass transformation in the subpolar North Atlantic Ocean. Here, the relatively warm and salty seawater transported from low latitudes is cooled by the atmosphere and becomes the cold and salty North Atlantic Deep Water (NADW), which sinks and returns southward ([Frajka-Williams et al. 2019](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib14)).

[Stommel (1961)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib44) realized that the AMOC is affected by two competing feedback effects due to the coupling of the circulation with the density field. When the AMOC strengthens, more heat will be transported northward which will reduce deep-water formation, providing a negative feedback via this thermal circulation. On the other hand, this strengthening also increases northward salt transport which increases deep-water formation and hence is a positive feedback, the salt-advection feedback ([Marotzke 2000](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib30)). These feedbacks, and that the atmosphere damps ocean temperature anomalies much more strongly than salinity anomalies, create a multiple equilibrium regime for the AMOC. In the box model used in [Stommel (1961)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib44), two stable equilibria exist under the same buoyancy forcing conditions. Such multiple equilibrium regimes have been found in a number of other box models of the AMOC ([Rooth 1982](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib38); [Rahmstorf 1996](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib35); [Lucarini and Stone 2005](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib29); [Cimatoribus et al. 2014](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib8)) for which the steady states can be computed when parameters are changed.

In more detailed models, the common procedure to investigate a possible multiple equilibrium regime is to slowly increase the freshwater forcing in the northern Atlantic until a critical threshold is crossed: the stable AMOC state ceases to exist and the circulation collapses to the other stable state without an active AMOC in a bifurcation tipping event. Subsequently, the forcing is reduced again until the collapsed state no longer exists and the AMOC recovers. The interval in forcing conditions between collapse and recovery is the AMOC hysteresis width, and a nonzero width indicates the existence of multiple equilibria. Such AMOC hysteresis has been found in Earth system models of intermediate complexity ([Rahmstorf et al. 2005](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib36); [Lenton et al. 2007](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib27)) and global ocean models ([Hofmann and Rahmstorf 2009](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib21)). Full AMOC hysteresis simulations have also been performed with a low-resolution atmosphere–ocean coupled general circulation model (FAMOUS) ([Hawkins et al. 2011](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib19)) and in a state-of-the-art global climate model (CESM) ([van Westen and Dijkstra 2023](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib47)).

The AMOC is identified as a tipping element in the climate system ([Lenton et al. 2008](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib28)). Based on early warning signals determined from historical AMOC reconstruction data ([Caesar et al. 2018](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib5)), the AMOC is believed to be heading toward the bifurcation point ([Boers 2021](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib3)). Although estimates have recently been provided when such a bifurcation point would be reached ([Ditlevsen and Ditlevsen 2023](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib12)), many uncertainties remain, and the present-day AMOC state may be far from it. Therefore, what is more dangerous is a noise-induced transition, where the transition does not happen because a certain critical threshold was crossed, but due to the fast variability in the forcing (“noise”). Not only are there no reliable early warning signals for a noise-induced transition as opposed to a bifurcation-induced one ([Ditlevsen and Johnsen 2010](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib13)), but more so that the latter can only occur close to the bifurcation point whereas the former can take place as long as the AMOC is multistable. This is arguably the case for the present-day AMOC. Based on observations of the AMOC-induced freshwater transport at the southern boundary of the Atlantic, the present-day AMOC is thought to be in a multiple equilibrium regime ([Weijer et al. 2019](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib48)). The reliability of this transport as an indicator for multistability is, however, contentious ([Jackson and Wood 2018](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib24)). Several stochastic models of the AMOC have been developed with stochastic freshwater forcing, and the statistics of their noise-induced transitions have been analyzed ([Cessi 1994](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib7); [Timmermann and Lohmann 2000](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib46)), and recently, even a noise-induced longtime weakening of the AMOC has been found in a global model ([Romanou et al. 2023](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib37)).

However, as there is no observational evidence for an AMOC transition over the historical period, a noise-induced transition is expected to be a rare event, and simple Monte Carlo techniques are unsuitable for such low-probability events. Rare event techniques have been used to determine such transitions probabilities in box models ([Castellana et al. 2019](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib6); [Jacques-Dumas et al. 2024](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib26)). However, apart from such probabilities, information on the most likely path of such an AMOC transition is also desired. From this, likely new observable early warning signals can be determined of an AMOC collapse.

In this paper, we use a technique from large deviation theory (LDT) to directly compute the most likely transition path in the low-noise limit of a stochastic model, i.e., the instanton. This is achieved by minimizing the Freidlin–Wentzell action ([Freidlin and Wentzell 1998](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib15)), transforming a rare transition sampling problem into a deterministic one. Minimizing this action entails that we maximize the probability of the applied noise forcing under the constraints that a transition occurs. The resulting path (the instanton) allows us to analyze the mechanisms of a noise-induced transition. Note that the forcing implies the path (and vice versa), so with the most likely path comes the optimal forcing. This associated forcing is just sufficient enough to attain the rare event. In other scientific fields, instantons have already been used to analyze transitions ([Grafke et al. 2015](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib18); [Grafke and Vanden-Eijnden 2019](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib17); [Woillez and Bouchet 2020](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib49); [Schorlepp et al. 2022](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib39); [Blyuss and Kyrychko 2023](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib2)). We apply the technique here to compute the instanton for an AMOC collapse and recovery in the box model from [Wood et al. (2019)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib50), where stochastic freshwater forcing is added. We will present the paths for an AMOC collapse and recovery that have the most probable freshwater forcing needed to achieve these transitions.

In [section 2](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#s2), a brief introduction to the Freidlin–Wentzell theory of large deviations is provided, and the algorithm used to compute the instanton is presented. Then, [section 3](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#s3) discusses the stochastic version of the box model from [Wood et al. (2019)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib50) together with the assumptions on the applied freshwater noise. [Section 4](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#s4) presents results on the instantons and the accompanying optimal forcing found for an AMOC collapse and recovery for the stochastic box model. In [section 5](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#s5), the distribution of this stochastic freshwater forcing over the boxes in the model is altered to study the effects of different freshwater forcing on the most likely AMOC collapse and recovery. Furthermore, the instanton trajectories are compared to the trajectories resulting from a standard deterministic hosing experiment. Finally, in [section 6](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#s6), a summary and discussion of the results follow.

## 2. Theory

### a. Freidlin–Wentzell theory of large deviations

Consider a dynamical system with state vector <strong>X</strong><em><sub>t</sub></em> in $\mathbb{R}^{d}$, forced by small random perturbations which are white in time and additive Gaussian. The noise amplitude scales with smallness parameter ϵ. The system can then be described by the stochastic differential equation (SDE):

**Equation 1.**

$$
d\mathbf{X}_{t} = \mathbf{f}{(\mathbf{X}_{t})}dt + \sqrt{\epsilon}\boldsymbol{σ}\hspace{0.25em}d\mathbf{W}_{t},\hspace{1em}t \geq 0,
$$

where $\left. \mathbf{f}:\mathbb{R}^{d}\rightarrow\mathbb{R}^{d} \right.$ is the deterministic drift, $\mathbf{a}$ = <strong><em>σσ</em></strong><sup>T</sup> is the noise covariance with $\boldsymbol{σ} \in \mathbb{R}^{d \times k}$, and <strong>W</strong><em><sub>t</sub></em> is a *k*-dimensional Wiener process. For simplicity, we take $\mathbf{a}$ to be independent of the system’s state (although this theory can be generalized to include multiplicative noise), but it is not assumed that $\mathbf{a}$ is invertible, i.e., the noise can be degenerate. Of interest are situations where the stochastic process [(1)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E1) realizes a certain event, say a transition within time *T* starting at **X**<sub>0</sub> = **x** and ending at **X**<sub><em>T</em></sub> = **y** for certain points in phase space $\mathbf{x},\mathbf{y} \in \mathbb{R}^{d}$ and time *T*. These events might be impossible in the deterministic setting (ϵ = 0) but can occur in the presence of noise (ϵ &gt; 0) although they become increasingly rare in the low-noise limit (ϵ → 0).

LDT provides the rate at which this probability decays to zero with *ϵ*. The probability of observing a sample path close to a function $\left. \boldsymbol{ϕ}:{\lbrack{0,T}\rbrack}\rightarrow\mathbb{R}^{d}\left. t\mapsto\boldsymbol{ϕ}{(t)} \right. \right.$ behaves as

**Equation 2.**

$$
\mathbb{P}\left\lbrack {\underset{t \in {\lbrack{0,T}\rbrack}}{\sup }\left\| {\mathbf{X}_{t} - \boldsymbol{ϕ}{(t)}} \right\| < \delta} \right\rbrack \asymp \exp {({{- S_{T}{\lbrack\boldsymbol{ϕ}\rbrack}}/\epsilon})},
$$

for sufficiently small *δ* &gt; 0, and where $\asymp$ denotes the log-asymptotic equivalence. The functional *S<sub>T</sub>*\[<strong><em>ϕ</em></strong>\] is the Freidlin–Wentzell action and is defined as

**Equation 3.**

$$
S_{T}{\lbrack\boldsymbol{ϕ}\rbrack} = \frac{1}{2}{\int_{0}^{T}\left\langle {\overset{˙}{\boldsymbol{ϕ}}{(t)} - \mathbf{f}{\lbrack{\boldsymbol{ϕ}{(t)}}\rbrack},\mathbf{a}^{- 1}{({\overset{˙}{\boldsymbol{ϕ}}{(t)} - \mathbf{f}{\lbrack{\boldsymbol{ϕ}{(t)}}\rbrack}})}} \right\rangle}dt,
$$

if the integral converges; otherwise, *S<sub>T</sub>*\[<strong><em>ϕ</em></strong>\] = ∞. Here, 〈⋅,⋅〉 is the standard Euclidean inner product which induces the norm ‖⋅‖ and $\mathbf{a}$<sup>−1</sup> is the inverse of the covariance matrix ([Freidlin and Wentzell 1998](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib15)). More technical constraints are that **f**(<strong><em>ϕ</em></strong>) needs to be Lipschitz continuous in <strong><em>ϕ</em></strong> and the path <strong><em>ϕ</em></strong>(*t*) needs to be absolutely continuous in time *t*. Moreover, if $\mathbf{a}$ is singular, then $\mathbf{a}$<sup>−1</sup> can be replaced by the Moore–Penrose inverse provided a positive-definite $\mathbf{a}$<sup>1/2</sup> exists and provided $\overset{˙}{\boldsymbol{ϕ}} - \mathbf{f}{(\boldsymbol{ϕ})}$ is in the image of $\mathbf{a}$ ([Puhalskii 2004](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib34)).

The important consequence of [(2)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E2) is that in the limit of ϵ → 0, the trajectory $\boldsymbol{ϕ}^{*}{(t)}$ with the smallest action becomes the least unlikely trajectory to realize the rare event, and all sample paths conditioned on the rare event ($\boldsymbol{ϕ}{(0)} = \mathbf{x},\boldsymbol{ϕ}{(T)} = \mathbf{y}$) will concentrate around $\boldsymbol{ϕ}^{*}$. More precisely,

**Equation 4.**

$$
\boldsymbol{ϕ}^{*}{(t)} = \underset{\{{\boldsymbol{ϕ}{(0)} = \mathbf{x},\boldsymbol{ϕ}{(T)} = \mathbf{y}}\}}{\text{arg min}}S_{T}{\lbrack\boldsymbol{ϕ}\rbrack}
$$

is the instanton (or maximum likelihood pathway), and for *δ* &gt; 0, sufficiently small

$$
\underset{\epsilon\rightarrow 0}{\lim }\mathbb{P}\left\lbrack {\underset{t \in {\lbrack{0,T}\rbrack}}{\sup }\left\| {\mathbf{X}_{t} - \boldsymbol{ϕ}^{*}{(t)}} \right\| < \left. \delta \right|\mathbf{X}_{0} = \mathbf{x},\mathbf{X}_{T} = \mathbf{y}} \right\rbrack = 1.
$$

So the objective here is to compute the instanton $\boldsymbol{ϕ}^{*}$, i.e. the minimizing path of the Freidlin–Wentzell action functional under the constraints that this is a transition path. Simply speaking, it is the path whose associated forcing is the most likely to occur of all possible forcings that cause a transition in a time *T*.

### b. Hamiltonian principle

The minimization problem [(4)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E4) is a common problem within classical mechanics ([Taylor 2005](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib45)), and so similar methods can be applied. The Lagrangian of [(4)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E4) is

$$
\mathcal{ℓ}{({\boldsymbol{ϕ},\overset{˙}{\boldsymbol{ϕ}}})} = \frac{1}{2}\left\langle {\overset{˙}{\boldsymbol{ϕ}}{(t)} - \mathbf{f}{\lbrack{\boldsymbol{ϕ}{(t)}}\rbrack},\mathbf{a}^{- 1}{({\overset{˙}{\boldsymbol{ϕ}}{(t)} - \mathbf{f}{\lbrack{\boldsymbol{ϕ}{(t)}}\rbrack}})}} \right\rangle,
$$

and assuming convexity of $\mathcal{L}{({\boldsymbol{ϕ},\overset{˙}{\boldsymbol{ϕ}}})}$ in $\overset{˙}{\boldsymbol{ϕ}}$, a Hamiltonian can be formulated by taking its Fenchel–Legendre transform ([Grafke and Vanden-Eijnden 2019](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib17)):

$$
\mathcal{H}{({\boldsymbol{ϕ},\boldsymbol{θ}})} = \underset{\mathbf{y}}{\sup }{\lbrack{\left\langle {\boldsymbol{θ},\mathbf{y}} \right\rangle - \mathcal{ℓ}{({\boldsymbol{ϕ},\mathbf{y}})}}\rbrack},
$$

where *θ* is the conjugate momentum defined as

$$
\boldsymbol{θ} = \frac{\partial\mathcal{ℓ}{({\boldsymbol{ϕ},\overset{˙}{\boldsymbol{ϕ}}})}}{\partial\overset{˙}{\boldsymbol{ϕ}}}.
$$

Hence, the Hamiltonian is

**Equation 5.**

$$
\mathcal{H}{({\boldsymbol{ϕ},\boldsymbol{θ}})} = \left\langle {\mathbf{f}{(\boldsymbol{ϕ})},\boldsymbol{θ}} \right\rangle + \frac{1}{2}\left\langle {\boldsymbol{θ},\mathbf{a}\boldsymbol{θ}} \right\rangle,
$$

and so the Hamiltonian equations of motion, i.e., the instanton equations, are as follows:

**Equation 6.**

$$
{\{\begin{array}{l} {\overset{˙}{\boldsymbol{ϕ}} = \nabla_{\boldsymbol{θ}}\mathcal{H}{({\boldsymbol{ϕ},\boldsymbol{θ}})} = \mathbf{f}{(\boldsymbol{ϕ})} + \mathbf{a}\boldsymbol{θ}} \\ {\overset{˙}{\boldsymbol{θ}} = - \nabla_{\boldsymbol{ϕ}}\mathcal{H}{({\boldsymbol{ϕ},\boldsymbol{θ}})} = - {({\nabla\mathbf{f}{(\boldsymbol{ϕ})}})}^{\text{T}}\boldsymbol{θ}} \end{array}},
$$

with boundary conditions <strong><em>ϕ</em></strong>(0) = **x** and <strong><em>ϕ</em></strong>(*T*) = **y**. Solving these equations yields the instanton $\boldsymbol{ϕ}^{*}{(t)}$. Note that for this path, the Hamiltonian is conserved. An advantage of this approach is that the covariance matrix $\mathbf{a}$ does not need to be inverted. A disadvantage is that for one first-order equation, two boundary conditions are known, while for the conjugated equation, there are none. A naive solution would be to guess *θ*(0) such that <strong><em>ϕ</em></strong>(*T*) is close to **y**, i.e., a shooting method, which is unpractical in higher dimensions. So to solve [(6)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E6), we use the augmented Lagrangian method ([Hestenes 1969](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib20); [Schorlepp et al. 2022](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib39)); see [appendix A](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#app1) for details.

## 3. Model

The ocean model used was originally introduced by [Wood et al. (2019)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib50) and is chosen since it is calibrated to the FAMOUS model ([Smith et al. 2008](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib42); [Smith 2012](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib40)). They show that this simple box model encapsulates the physics of the more complicated AOGCM. It represents the World Ocean in five boxes, see [Fig. 1](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig1). Each box represents large contiguous regions of the global ocean, corresponding to large-scale water mass structures. The *T* box represents the Atlantic thermocline; the *N* box is the NADW formation region and Artic region; the *B* box is the southward-propagating NADW and its upwelling in the Southern Ocean as Circumpolar Deep Water; the *S* box is the fresh Southern Ocean near-surface waters and their return into the Atlantic as Antarctic Intermediate Water; and last, the IP box represents the Indo-Pacific thermocline. The calibration entails that the box model reproduces the decadal means of salinities, temperatures, volumes, and transports of these mean water masses observed in the stable preindustrial climate state of the AOGCM. The boxes have salinities denoted by *S<sub>N</sub>*, *S<sub>T</sub>*, *S<sub>S</sub>*, *S<sub>B</sub>*, and *S*<sub>IP</sub>, respectively, along with fixed volumes *V<sub>N</sub>*, *V<sub>T</sub>*, *V<sub>S</sub>*, *V<sub>B</sub>*, and *V*<sub>IP</sub>.

![Figure 1](https://journals.ametsoc.org/view/journals/phoc/54/12/full-JPO-D-23-0234.1-f1.jpg)

**Figure 1.** Sketch of the box model, from [Wood et al. (2019)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib50).

### a. Formulation

It is assumed that density variations in the boxes are solely due to changes in the boxes’ salinity and in the temperature of the northern box. The other boxes’ temperatures are taken to be constant. The following volume fluxes occur between the boxes: downwelling in the North Atlantic (and hence AMOC strength) *q* that transports salt between the *T*, *N*, and *B* boxes; a cold water path (CWP) that returns a fraction *γ* of the AMOC from the *B* box via the *S* box to the *T* box, representing the return flow via the Drake Passage; and a warm water path (WWP) that returns the AMOC’s remaining fraction 1 − *γ* from the *B* box via the IP box to the *T* box, representing the return flow via the Agulhas leakage. It is assumed that the overturning circulation is linearly dependent on the density difference of the *N* and *S* boxes:

$$
q = \lambda{({\alpha{({T_{S} - T_{N}})} + \beta{({S_{N} - S_{S}})}})},
$$

where *α* and *β* are the thermal and haline compressibility, respectively; *λ* is a hydraulic coefficient; and *T<sub>S</sub>* is the fixed mean temperature of the *S* box. Additionally, *T<sub>N</sub>* is the mean temperature of the northern box obeying

$$
T_{N} = \mu q + T_{0},
$$

where *T*<sub>0</sub> is a fixed baseline temperature and *μ* &gt; 0 is the fixed heat transport coefficient. This represents the northward transport of heat by the overturning circulation. Combining the latter two equations yields

$$
\begin{array}{l} {q = \kappa{({\alpha{({T_{S} - T_{0}})} + \beta{({S_{N} - S_{S}})}})},} \\ {\hspace{1em}\text{where}\hspace{0.33em}\kappa = \frac{\lambda}{1 + \alpha\lambda\mu},} \end{array}
$$

eliminating *T<sub>N</sub>* from the equations, and hence, the state of the dynamical model is completely characterized by the boxes’ five salinities.

The other salinity transports are due to the wind-driven subtropical gyres, captured by the coefficients *K<sub>N</sub>*, *K<sub>S</sub>*, and *K*<sub>IP</sub> for the exchange between *T* and *N*, *T* and *S*, and IP and *S*, respectively. Furthermore, the coefficient *η* captures the mixing between *B* and *S*. The atmospheric fluxes are denoted by *F<sub>i</sub>* for the flux into box *i*.

The stochastic extension of the [Wood et al. (2019)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib50) model is given by the following equations:

**Equation 7a.**

$$
V_{N}\frac{dS_{N}}{dt} = q{({\theta{(q)}{({S_{T} - S_{N}})} - \theta{({- q})}{({S_{B} - S_{N}})}})} + K_{N}{({S_{T} - S_{N}})} - F_{N}S_{0} + A_{N}S_{0}\tilde{\eta},
$$

**Equation 7b.**

$$
V_{T}\frac{dS_{T}}{dt} = q{({\theta{(q)}{({\gamma S_{S} + {({1 - \gamma})}S_{\text{IP}} - S_{T}})} - \theta{({- q})}{({S_{N} - S_{T}})}})} + K_{S}{({S_{S} - S_{T}})} - F_{T}S_{0} + A_{T}S_{0}\tilde{\eta},
$$

**Equation 7c.**

$$
V_{S}\frac{dS_{S}}{dt} = \gamma q{({\theta{(q)}{({S_{B} - S_{S}})} - \theta{({- q})}{({S_{T} - S_{S}})}})} + K_{{}_{\text{IP}}}{({S_{\text{IP}} - S_{S}})} + K_{S}{({S_{T} - S_{S}})} + \eta{({S_{B} - S_{S}})} - F_{S}S_{0} + A_{S}S_{0}\tilde{\eta},
$$

**Equation 7d.**

$$
V_{\text{IP}}\frac{dS_{\text{IP}}}{dt} = {({1 - \gamma})}q{({\theta{(q)}{({S_{B} - S_{\text{IP}}})} - \theta{({- q})}{({S_{T} - S_{\text{IP}}})}})} + K_{\text{IP}}{({S_{S} - S_{\text{IP}}})} - F_{\text{IP}}S_{0} + A_{\text{IP}}S_{0}\tilde{\eta},
$$

**Equation 7e.**

$$
V_{B}\frac{dS_{B}}{dt} = q{({\theta{(q)}{({S_{N} - S_{B}})} - \theta{({- q})}{({\gamma S_{S} + {({1 - \gamma})}S_{\text{IP}} - S_{B}})}})} + \eta{({S_{S} - S_{B}})},
$$

where *S*<sub>0</sub> is a baseline salinity value and *θ*(*x*) is the Heaviside function. The stochastic freshwater flux $\tilde{\eta}{(t)}$ is modeled as a zero-mean Gaussian white noise process with correlation function $\mathbb{E}{\lbrack{\tilde{\eta}{(t)}\tilde{\eta}{(t')}}\rbrack} = \nu\delta{({t - t'})}$. The parameters *A<sub>i</sub>* indicate what fraction of $\tilde{\eta}$ enters or exits box *i*.

The total salinity *C* is

**Equation 8.**

$$
C = V_{N}S_{N} + V_{T}S_{T} + V_{S}S_{S} + V_{\text{IP}}S_{\text{IP}} + V_{B}S_{B},
$$

and using [(7)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E7a), it follows that

$$
\frac{dC}{dt} = - {({F_{N} + F_{T} + F_{S} + F_{\text{IP}}})}S_{0}, + {({A_{N} + A_{T} + A_{S} + A_{\text{IP}}})}S_{0}\tilde{\eta}.
$$

The total salinity is conserved, so it is demanded that

$$
\begin{array}{l} {F_{N} + F_{T} + F_{S} + F_{\text{IP}} = 0,} \\ {A_{N} + A_{T} + A_{S} + A_{\text{IP}} = 0.} \end{array}
$$

Using [(8)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E8), the differential [(7e)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E7e) is replaced by

$$
S_{B} = \frac{1}{V_{B}}{({C - V_{N}S_{N} - V_{T}S_{T} - V_{S}S_{S} - V_{\text{IP}}S_{\text{IP}}})},
$$

where *C* is the basin’s total (fixed) salinity.

### b. Nondimensional equations

The nondimensional salinities *ϕ<sub>i</sub>* of the boxes are introduced, together with nondimensionalized volumes *V<sub>i</sub>*:

$$
\begin{array}{l} {S_{N} = S_{0}\phi_{1}\hspace{1em}V_{N} = V_{0}V_{1}} \\ {S_{T} = S_{0}\phi_{2}\hspace{1em}V_{T} = V_{0}V_{2}} \\ {S_{S} = S_{0}\phi_{3}\hspace{1em}V_{S} = V_{0}V_{3}} \\ {S_{\text{IP}} = S_{0}\phi_{4}\hspace{1em}V_{\text{IP}} = V_{0}V_{4}} \\ {S_{B} = S_{0}\phi_{5}\hspace{1em}V_{B} = V_{0}V_{5}} \end{array},
$$

and furthermore, time *t* is nondimensionalized as *t* = *t<sub>d</sub>τ*, with notation ${\overset{˙}{\phi}}_{i} = {{d\phi_{i}}/{d\tau}}$. The nondimensional model equations then become

**Equation 9a.**

$$
{\overset{˙}{\phi}}_{1} = \frac{t_{d}}{V_{0}}\frac{1}{V_{1}}{({q{({\theta{(q)}{({\phi_{2} - \phi_{1}})} - \theta{({- q})}{({\phi_{5} - \phi_{1}})}})} + K_{N}{({\phi_{2} - \phi_{1}})} - F_{N}})} + \frac{t_{d}}{V_{0}}\frac{A_{N}}{V_{1}}\sqrt{\nu}\zeta,
$$

**Equation 9b.**

$$
{\overset{˙}{\phi}}_{2} = \frac{t_{d}}{V_{0}}\frac{1}{V_{2}}\left({q{({\theta{(q)}{({\gamma\phi_{3} + {({1 - \gamma})}\phi_{4} - \phi_{2}})} - \theta{({- q})}{({\phi_{1} - \phi_{2}})}})} + K_{S}{({\phi_{3} - \phi_{2}})} + K_{N}{({\phi_{1} - \phi_{2}})} - F_{T}} \right) + \frac{t_{d}}{V_{0}}\frac{A_{T}}{V_{2}}\sqrt{\nu}\zeta,
$$

**Equation 9c.**

$$
{\overset{˙}{\phi}}_{3} = \frac{t_{d}}{V_{0}}\frac{1}{V_{3}}{({\gamma q{({\theta{(q)}{({\phi_{5} - \phi_{3}})} - \theta{({- q})}{({\phi_{2} - \phi_{3}})}})} + K_{\text{IP}}{({\phi_{4} - \phi_{3}})} + K_{S}{({\phi_{2} - \phi_{3}})} + \eta{({\phi_{5} - \phi_{3}})} - F_{S}})} + \frac{t_{d}}{V_{0}}\frac{A_{S}}{V_{3}}\sqrt{\nu}\zeta,
$$

**Equation 9d.**

$$
{\overset{˙}{\phi}}_{4} = \frac{t_{d}}{V_{0}}\frac{1}{V_{4}}{({{({1 - \gamma})}q{({\theta{(q)}{({\phi_{5} - \phi_{4}})} - \theta{({- q})}{({\phi_{2} - \phi_{4}})}})} + K_{\text{IP}}{({\phi_{3} - \phi_{4}})} - F_{\text{IP}}})} + \frac{t_{d}}{V_{0}}\frac{A_{\text{IP}}}{V_{4}}\sqrt{\nu}\zeta,
$$

where *ζ*(*t*) is a unit-variance white noise process and the (dimensional) AMOC strength is written as

**Equation 10.**

$$
q = \kappa{({\alpha{({T_{S} - T_{0}})} + \beta S_{0}{({\phi_{1} - \phi_{3}})}})},
$$

and nondimensionalized *S<sub>B</sub>* follows from salinity conservation:

$$
\phi_{5} = {\left({\frac{C}{V_{0}S_{0}} - V_{1}\phi_{1} - V_{2}\phi_{2} - V_{3}\phi_{3} - V_{4}\phi_{4}} \right)/V_{5}}.
$$

From now on, *t* is again used, but now to denote the nondimensional time.

The system of nondimensionalized equations is rewritten as an Itô stochastic differential equation ([Mikosch 1998](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib32)):

**Equation 11.**

$$
d\boldsymbol{ϕ}_{t} = \mathbf{f}{(\boldsymbol{ϕ}_{t})}dt + \sqrt{\epsilon}\boldsymbol{σ}\hspace{0.25em}d\mathbf{W}_{t},
$$

where <strong><em>ϕ</em></strong><em><sub>t</sub></em> = (*ϕ*<sub>1</sub>(*t*), *ϕ*<sub>2</sub>(*t*), *ϕ*<sub>3</sub>(*t*), *ϕ*<sub>4</sub>(*t*))<sup>T</sup> is the state vector, and the deterministic parts of the evolution equations are **f**(<strong><em>ϕ</em></strong>) = (*f*<sub>1</sub> (<strong><em>ϕ</em></strong>), *f*<sub>2</sub> (<strong><em>ϕ</em></strong>), *f*<sub>3</sub> (<strong><em>ϕ</em></strong>), *f*<sub>4</sub> (<strong><em>ϕ</em></strong>))<sup>T</sup>. Furthermore, the noise amplitude is given by $\sqrt{\epsilon} = {({t_{d}/V_{0}})}\sqrt{\nu}$, and

$$
\boldsymbol{σ} = {({{A_{N}/V_{1}},{A_{T}/V_{2}},{A_{S}/V_{3}},{A_{\text{IP}}/V_{4}}})}^{\text{T}}
$$

acts on the one-dimensional Wiener process. The system has degenerate noise: one degree of stochastic freedom is acting on the process $\boldsymbol{ϕ}_{t} \in \mathbb{R}^{4}$.

The parameter values (*V<sub>i</sub>*, *F<sub>i</sub>*, *K<sub>i</sub>*, *T<sub>S</sub>*, *T*<sub>0</sub>, *μ*, *λ*, *η*, and *γ*) are taken from the calibration to the FAMOUS\_B model ([Wood et al. 2019](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib50)), see [Table B1](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#tblB1) in [appendix B](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#app2). The total salinity *C* is found using the salinity values from [Alkhayuon et al. (2019)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib1). For these values, the deterministic model has two stationary stable points, an ON and OFF state of the AMOC ($q \lessgtr 0$), and an unstable saddle state ([Alkhayuon et al. 2019](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib1)). In the ON state (*q* &gt; 0), downwelling occurs in the north, and the resulting flow flows southward along the bottom before it returns to the Atlantic thermocline via either the Southern Ocean or the Indo-Pacific thermocline. In the OFF state, these flows are reversed, and upwelling occurs in the northern Atlantic (*q* < 0). So states <strong><em>ϕ</em></strong><sub>ON</sub> and <strong><em>ϕ</em></strong><sub>OFF</sub> represent an active and collapsed AMOC, respectively. They are found numerically using a root finding function, the dogleg method ([Nocedal and Wright 1999](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib33)), to $\left. \mathbf{f}:\mathbb{R}^{4}\rightarrow\mathbb{R}^{4} \right.$.

### c. Instanton equations

Recall that we want to compute the instantons for an AMOC collapse (<strong><em>ϕ</em></strong><sub>ON</sub> → <strong><em>ϕ</em></strong><sub>OFF</sub>) and recovery (<strong><em>ϕ</em></strong><sub>OFF</sub> → <strong><em>ϕ</em></strong><sub>ON</sub>) in the model [(11)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E11). So, we need **f**(<strong><em>ϕ</em></strong>) to be Lipschitz continuous in <strong><em>ϕ</em></strong>. We did this by approximating the Heaviside function by *θ*(*x*) ≈ \[erf(*x*/*ϵ*<sub><em>θ</em></sub>) + 1\]/2, where erf is the error function, for small *ϵ*<sub><em>θ</em></sub> = 10<sup>−10</sup>. The error caused by this approximation is assumed to be negligible.

Two assumptions were made of the freshwater noise: (i) the noise is white in time and (ii) this noise is small. To justify (ii), estimating the noise amplitude can be done in a similar way as [Castellana et al. (2019)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib6). The parameter *ϵ* is estimated by using the annual *P* − *E* (precipitation minus evaporation) time series in the Atlantic Ocean, assuming that this represents the interannual variability of freshwater perturbations relevant to the AMOC strength. Using the same time series, the ERA-Interim archive at ECMWF ([Dee et al. 2011](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib9)), it is found for its variance that $\sqrt{\nu} \sim 0.0175 \pm 0.0025\hspace{0.33em}\text{Sv}$ (1 Sv ≡ 10<sup>6</sup> m<sup>3</sup> s<sup>−1</sup>). Hence, *ϵ* ∼ 0.0055 ± 0.0008. This is in the regime of small noise, as for $\sqrt{\nu} \sim 0.07\hspace{0.33em}\text{Sv}$, typically no transition occurs even after 10<sup>6</sup> years, while a transition usually does not take longer than 35 years. Assumption (i) is harder to justify as the annual freshwater perturbation series might be autocorrelated, especially under climate change. However, the white noise assumption is still made to keep the model analysis relatively simple.

Applying the equations from [section 2](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#s2) to the stochastic box model yields the Lagrangian

$$
\mathcal{ℓ}{({\boldsymbol{ϕ},\overset{˙}{\boldsymbol{ϕ}}})} = \frac{1}{2\left\| \boldsymbol{σ} \right\|^{4}}{\sum\limits_{i,j = 1}^{4}{\sigma_{i}\sigma_{j}{\lbrack{{\overset{˙}{\phi}}_{i} - f_{i}{(\boldsymbol{ϕ})}}\rbrack}{\lbrack{{\overset{˙}{\phi}}_{j} - f_{j}{(\boldsymbol{ϕ})}}\rbrack}}},
$$

with conjugate momentum $\left. \boldsymbol{θ}:{\lbrack{0,T}\rbrack}\rightarrow\mathbb{R}^{4} \right.$:

$$
\theta_{i}{(t)} = \frac{\mathit{σ}_{i}}{\left\| \boldsymbol{σ} \right\|^{4}}{\sum\limits_{j = 1}^{4}{\sigma_{j}{({{\overset{˙}{\phi}}_{j}{(t)} - f_{j}{\lbrack{\boldsymbol{ϕ}{(t)}}\rbrack}})}}}\hspace{1em}\text{for}\hspace{0.33em}1 \leq i \leq 4,
$$

and hence, the Hamiltonian for this minimization problem is

$$
\mathcal{H}{({\boldsymbol{ϕ},\boldsymbol{θ}})} = \left\langle {\mathbf{f}{(\boldsymbol{ϕ})},\boldsymbol{θ}} \right\rangle + \frac{1}{2}{\boldsymbol{σ},\boldsymbol{θ}^{2}}.
$$

Therefore, the equations for the instanton from <strong><em>ϕ</em></strong><sub>start</sub> to <strong><em>ϕ</em></strong><sub>end</sub> within a time interval \[0, *T*\] are

**Equation 12.**

$$
\{\begin{array}{l} {\overset{˙}{\boldsymbol{ϕ}}{(t)} = \mathbf{f}{\lbrack{\boldsymbol{ϕ}{(t)}}\rbrack} + \boldsymbol{σ}\left\langle {\boldsymbol{σ},\boldsymbol{θ}{(t)}} \right\rangle} \\ {\overset{˙}{\boldsymbol{θ}}{(t)} = - {({\nabla\mathbf{f}{\lbrack{\boldsymbol{ϕ}{(t)}}\rbrack}})}^{\text{T}}\boldsymbol{θ}{(t)}} \\ {\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\text{with}\hspace{0.33em}\boldsymbol{ϕ}{(0)} = \boldsymbol{ϕ}_{\text{start}}\hspace{0.33em}\text{and}\hspace{0.33em}\boldsymbol{ϕ}{(T)} = \boldsymbol{ϕ}_{\text{end}}.} \end{array}
$$

As the stochastic forcing is just a one-dimensional Wiener process, all deviations from the deterministic system are the same in every direction up to a scaling factor $\sigma_{i}^{- 1}$, and one can define

$$
\begin{array}{l} {\xi{(t)} = {{({{\overset{˙}{\phi}}_{i}{(t)} - f_{i}{\lbrack{\boldsymbol{ϕ}{(t)}}\rbrack}})}/\sigma_{i}}\hspace{1em}\text{for}\hspace{0.33em}1 \leq i \leq 4} \\ {\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em} = {\left\langle {\boldsymbol{σ},\boldsymbol{θ}{(t)}} \right\rangle,}} \end{array}
$$

which reduces the previously mentioned relationships to

**Equation 13a.**

$$
\mathcal{ℓ}{(\xi)} = \frac{1}{2}\xi^{2},
$$

**Equation 13b.**

$$
\mathcal{H}{({\boldsymbol{ϕ},\xi})} = \frac{\left\langle {\mathbf{f}{(\boldsymbol{ϕ})},\boldsymbol{σ}} \right\rangle}{\left\| \boldsymbol{σ} \right\|^{2}}\xi + \frac{1}{2}\xi^{2}.
$$

The Lagrangian shows trivially that the most likely path is the one that minimizes the absolute total applied freshwater noise, while the Hamiltonian implies that to any freshwater perturbation, the system <strong><em>ϕ</em></strong> responds with salinity changes in all boxes with proportionality factors *σ<sub>i</sub>*/‖<strong><em>σ</em></strong>‖<sup>2</sup>. We will obtain the path <strong><em>ϕ</em></strong> and accompanying forcing *ξ* that minimize this Lagrangian and do not vary the Hamiltonian—provided that this path is a transition.

## 4. Results: AMOC transitions

### a. Instantons

The instanton for an AMOC collapse from <strong><em>ϕ</em></strong><sub>ON</sub> to <strong><em>ϕ</em></strong><sub>OFF</sub> and its reverse (the “anti-instanton”) are computed for the noise parameters (*A<sub>N</sub>*, *A<sub>T</sub>*, *A<sub>S</sub>*, *A*<sub>IP</sub>)<sup>T</sup> = (0.070, 0.752, −0.257, −0.565) which follow from the same calibration to the FAMOUS\_B model ([Wood et al. 2019](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib50)). So, freshwater goes into boxes *N* and *T*, and as compensation, freshwater is extracted from boxes *S* and IP. This conserves the total salinity, and <strong><em>ϕ</em></strong><sub>ON</sub> and <strong><em>ϕ</em></strong><sub>OFF</sub> do not change during the hosing process. Equation [(12)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#UE17) is solved using the discussed augmented Lagrangian method, where explicit Euler is used for time integration with time step Δ<em>t</em> = 0.05. The instantons <strong><em>ϕ</em></strong>(*t*) are terminated once ‖<strong><em>ϕ</em></strong>(*T*) − <strong><em>ϕ</em></strong><sub>end</sub>‖ < 10<sup>−5</sup>. For different values of 30 < *T* < 100, the trajectory of the instanton is just translated in time without any significant change in behavior. Moreover, the average times of a realization to transit from the ON basin (defined by *q* &gt; 14 Sv) to the OFF basin (defined by *q* < −4.5 Sv) and vice versa level off for smaller noise levels (tested down to *ϵ* ∼ 0.035) at *T* = 17 and *T* = 32 for the collapse and recovery, respectively. Hence, *T* = 32 is sufficient to capture the relevant instanton behavior for both transition directions.

In the limit of large *T*, the instantons are expected to cross from one basin to the other via the saddle present in the model. We do not consider these instantons to be representable of a typical transition since the realizations here tend to avoid the saddle, which is an issue discussed in [Börner et al. (2023)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib4).

In addition to the instanton trajectory <strong><em>ϕ</em></strong>(*t*), the associated optimal freshwater noise forcing *ξ*(*t*) also follows from the optimization procedure [(12)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#UE17) and is analyzed below. In [Fig. 2](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig2), the resulting instantons are shown in several projected phase spaces (*ϕ<sub>i</sub>* and *ϕ<sub>j</sub>*) together with multiple realized transitions of the model. It shows that the instantons lie at the center of these transitions, as they should be according to theory, and this serves as their verification. We will analyze the mechanisms underlying the behavior of these instantons in the following subsections.

![Figure 2](https://journals.ametsoc.org/view/journals/phoc/54/12/full-JPO-D-23-0234.1-f2.jpg)

**Figure 2.** Instantons from <strong><em>ϕ</em></strong><sub>ON</sub> to <strong><em>ϕ</em></strong><sub>OFF</sub> (blue) and vice versa (anti-instantons; green) in several salinity spaces (*ϕ<sub>i</sub>* and *ϕ<sub>j</sub>*), together with a histogram of multiple realizations of the model for noise level ϵ ∼ 0.035 ($\sqrt{\nu} \sim 0.11\hspace{0.33em}\text{Sv}$) (red), using a logarithmic scale.

### b. Dynamics of collapse and recovery

In [Fig. 3](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig3), the dimensional instantons of the collapse and recovery are shown together with their AMOC strength *q* for a time frame *t* ∈ \[0, 32\] years. The insets show the accompanying dimensional stochastic freshwater forcing into boxes *N* and *T*, which are computed as $- {({V_{0}/t_{d}})}{({V_{1}\sigma_{1} + V_{2}\sigma_{2}})}\xi{(t)}$. A positive sign indicates net freshwater going into these boxes. Mainly the salinities in the *N* and *T* boxes change, while those in the other boxes only vary marginally. [Wood et al. (2019)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib50) observed this already and suggested a possible reduction of the model without *S* and IP. In those boxes, advection by the density-induced flow plays a lesser role, and their salinities are mainly controlled by the atmospheric fluxes and the Indo-Pacific gyre transport. Hence, the tipping of the AMOC affects these boxes to a lesser extent than the *N* and *T* boxes.

![Figure 3](https://journals.ametsoc.org/view/journals/phoc/54/12/full-JPO-D-23-0234.1-f3.jpg)

**Figure 3.** Instantons (left) from the ON state to the OFF state and (right) reverse shown as the (top) five salinities and (bottom) AMOC strength, with the optimal freshwater forcing as insets. The salinities *S<sub>N</sub>*, *S<sub>T</sub>*, *S<sub>S</sub>*, *S*<sub>IP</sub>, and *S<sub>B</sub>* are indicated by blue, yellow, green, red, and purple, respectively.

The dynamics of the AMOC collapse and recovery can be captured by a reduced model. We assume *ϕ*<sub>3</sub> (i.e., *S<sub>S</sub>*) is constant and that *A<sub>N</sub>* is negligible. The former assumption is justified as it can be deduced from [Fig. 3](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig3), while the latter is justified since the hosing transport into box *N* is several orders of magnitude smaller than the other transports. Now, for *q* &gt; 0, it holds that

$$
\begin{array}{l} {\overset{˙}{q} = \kappa\beta S_{0}{\overset{˙}{\phi}}_{1}} \\ {\ {}\ {} = \kappa\beta S_{0}\frac{t_{d}}{V_{0}V_{1}}{({{({K_{N} + q})}{({\phi_{2} - \phi_{1}})} - F_{N}})}} \end{array},
$$

and then, substituting the relation *ϕ*<sub>1</sub>(*q*) derived directly from [(10)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E10) yields

**Equation 14.**

$$
\begin{array}{l} {{\overset{˙}{q}}_{\text{ON}}{({q,\phi_{2}})} = A_{\text{ON}}q^{2} + B_{\text{ON}}q + C_{\text{ON}}} \\ \text{with} \\ {A_{\text{ON}} = - \frac{t_{d}}{V_{0}V_{1}},} \\ {B_{\text{ON}} = \frac{t_{d}}{V_{0}V_{1}}{({\kappa\beta S_{0}{({\phi_{2} - \phi_{3}})} - K_{N} + \kappa\alpha{({T_{S} - T_{0}})}})},} \\ {C_{\text{ON}} = \frac{t_{d}}{V_{0}V_{1}}\kappa\beta S_{0}\left({K_{N}\left({\phi_{2} + \frac{\alpha{({T_{S} - T_{0}})}}{\beta S_{0}} - \phi_{3}} \right) - F_{N}} \right) \cdot} \end{array}
$$

A similar derivation can be done for the AMOC dynamics as *q* < 0 which leads to

**Equation 15.**

$$
\begin{array}{l} {{\overset{˙}{q}}_{\text{OFF}}{({q,\phi_{2}})} = A_{\text{OFF}}q^{2} + B_{\text{OFF}}q + C_{\text{OFF}}} \\ \text{with} \\ {A_{\text{OFF}} = \frac{t_{d}}{V_{0}V_{1}}} \\ {B_{\text{OFF}} = \frac{t_{d}}{V_{0}V_{1}}{({\kappa\beta S_{0}{({\phi_{3} - \phi_{5}})} - K_{N} - \kappa\alpha{({T_{S} - T_{0}})}})}} \\ {C_{\text{OFF}} = \frac{t_{d}}{V_{0}V_{1}}\kappa\beta S_{0}\left({K_{N}\left({\phi_{2} + \frac{\alpha{({T_{S} - T_{0}})}}{\beta S_{0}} - \phi_{3}} \right) - F_{N}} \right) \cdot} \end{array}
$$

The evolution of $\overset{˙}{q}{({q,\phi_{2}})}$ along the instantons is depicted in [Fig. 4](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4).

![Figure 4](https://journals.ametsoc.org/view/journals/phoc/54/12/full-JPO-D-23-0234.1-f4.jpg)

**Figure 4.** Dynamics of the (a)–(d) AMOC collapse (e)–(h) AMOC recovery: $\overset{˙}{q}{({q,\phi_{2}})}$ (blue) in the $({\overset{˙}{q},q})$ plane with time *t* and salinity *ϕ*<sub>2</sub> values along each instanton added and current AMOC strength *q* indicated by the red dot. The arrows on the *q* axis indicate the sign of $\overset{˙}{q}$. (i) Complete $\overset{˙}{q}{({q,\phi_{2}})}$ curves for several *ϕ*<sub>2</sub> ∈ (1.01, 1.05).

#### 1) Collapse

Initially, the system is in equilibrium <strong><em>ϕ</em></strong><sub>ON</sub>, which is a stable root of ${\overset{˙}{q}}_{\text{ON}}{({q,\boldsymbol{ϕ}_{2}})} = 0$ ([Fig. 4a](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4)). This right root is stable since a small increase (decrease) in *q* would cause the *N* box to become saltier (fresher), which is mitigated by a decrease (an increase) in northern gyre transport that in turn freshens (salinifies) the northern box, which finally weakens (strengthens) the AMOC. This stable root will continue to exist as long as the discriminant of ${\overset{˙}{q}}_{\text{ON}}{({q,\phi_{2}})}$ stays positive, i.e., $D_{\text{ON}} = B_{\text{ON}}^{2} - 4A_{\text{ON}}C_{\text{ON}} > 0$. It can be derived that this condition is equivalent to

**Equation 16.**

$$
\begin{array}{l} {\phi_{2} - \phi_{3} > r{({T_{S} - T_{0}})} - k_{N} + 2\sqrt{f_{N}} \approx 0.0494} \\ {\text{or}\hspace{0.33em}\phi_{2} - \phi_{3} < r{({T_{S} - T_{0}})} - k_{N} - 2\sqrt{f_{N}} \approx - 0.0477} \\ {\text{where}\hspace{0.33em}k_{N} = \frac{K_{N}}{\kappa\beta S_{0}},\hspace{1em}r = \frac{\alpha}{\beta S_{0}},\hspace{1em}\text{and}\hspace{1em}f_{N} = \frac{F_{N}}{\kappa\beta S_{0}}} \end{array},
$$

where only the first inequality is considered as *ϕ*<sub>2</sub> − *ϕ*<sub>3</sub> < 0 does not happen. Looking at this inequality, it follows that a larger northern gyre strength, a warmer southern box, or a smaller atmospheric flux into box *N* would all enlarge this range for *ϕ*<sub>2</sub> − *ϕ*<sub>3</sub>. This follows directly from the facts that the northern gyre serves as a stabilizing mechanism (as just described), whereas a warmer south would decrease the density of the *S* box (so increasing *q*) and *F<sub>N</sub>* is a destabilizing freshening into box *N*. The role of *κ* is ambiguous, as a stronger feedback mechanism would stabilize the AMOC via the thermal circulation and destabilize it via the haline circulation (the salt-advection feedback).

The AMOC collapse paradoxically starts off with an increase in its strength. Initially, the optimal hosing scheme salinifies the northern *N* and the thermocline *T* boxes, while the other salinities change marginally as their volumes are larger. The increase in *S<sub>N</sub>* causes an increase in *q*, peaking at roughly *t* ≈ 10.8 years with *q* ≈ 16.3 Sv. This short salinification pulse ends already at *t* ≈ 12 years, and *q* is back at its original level. However, the current state is a transient state (i.e., nonequilibrium), with box *T* slightly fresher ($\mathcal{O}{(10^{- 3})}$), while the others are marginally saltier ($\mathcal{O}{(10^{- 4})}$) compared to the equilibrium ON state. So, the salt is redistributed. The salinity difference *S<sub>N</sub>* − *S<sub>S</sub>*, which determines the AMOC strength, is still the same, while *S<sub>T</sub>* − *S<sub>N</sub>* has decreased. When applying freshwater to the northern boxes, the salinity difference *S<sub>N</sub>* − *S<sub>S</sub>* drops, and *S<sub>N</sub>* cannot as easily be restored via the gyre since *S<sub>T</sub>* − *S<sub>N</sub>* is lower. This also follows from [(16)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E16): as *ϕ*<sub>2</sub> − *ϕ*<sub>3</sub> decreases, the discriminant *D*<sub>ON</sub> will decrease; thus, the distance between the two roots in [Fig. 4a](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4) diminishes and the stability region for an ON state narrows. This destabilizing effect of the initial AMOC strengthening is quantified by computing the probabilities of a collapse within 100 years for trajectories starting in the standard ON state and in this destabilized state. These probabilities are estimated using Monte Carlo simulations for various (unrealistically high) noise levels $\sqrt{\nu} \in {\{{0.11,\hspace{0.33em}0.10,\hspace{0.33em}0.09,\hspace{0.33em}0.08}\}}\hspace{0.33em}\text{Sv}$. They are \{\{6.4 × 10<sup>−3</sup>, 6.5 × 10<sup>−3</sup>\}, \{1.9 × 10<sup>−3</sup>, 2.1 × 10<sup>−3</sup>\}, \{3 × 10<sup>−4</sup>, 4 × 10<sup>−4</sup>\}, \{2 × 10<sup>−5</sup>, 4 × 10<sup>−5</sup>\}\} for trajectories starting in the ON state and in the destabilized state, respectively. Hence, this probability is only slightly larger in the destabilized state than in the ON state for the various noise levels. However, the ratio of the respective probabilities increases for smaller noise, and hence, especially in the low-noise regime, this initial strengthening of the AMOC increases the collapse probability significantly.

After this initial strengthening, a relatively large freshwater pulse is added to *T* during *t* ∈ (11, 15) years causing its salinity to drop. Now, fresher water is transported northward by the AMOC, and so, *S<sub>N</sub>* drops too. This in turn causes the AMOC strength to decrease, so less saline water is transported northward by it, which decreases *S<sub>N</sub>* even further: the salt-advection feedback. This freshening of *N* is partly offset by salt transport by the northern gyre. Note that this also follows from [(14)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E14): for increased *ϕ*<sub>2</sub>, the stable root disappears and ${\overset{˙}{q}}_{\text{ON}} < 0$ for all *q* &gt; 0 ([Fig. 4b](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4)). Using [(16)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E16) and taking *ϕ*<sub>3</sub> ≈ *ϕ*<sub>ON,3</sub>, then no roots exist for *ϕ*<sub>2</sub> < 1.0146 (*S<sub>T</sub>* < 35.5). During this time, the salinities of *S* and IP increase due to the pulse of salinity and remain at this level with an increased Indo-Pacific gyre transport.

The freshwater pulse peaks at *t* = 12 years and then decreases. The *T* box is not freshened anymore, and its salinity increases again due to the reduced advection of saline water to the north and of fresher water from the *S* and IP boxes. Apparently, a fresher Atlantic thermocline is no longer needed to destabilize the AMOC. Its salinity even overshoots before it converges to its new stable *ϕ*<sub>OFF,2</sub> state. As can be seen from [Fig. 4c](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4), a stable ON state exists again, but the current state of the AMOC is to the left of the unstable root and hence in an unstable regime. The AMOC is now too weak to sustain itself as it cannot transport enough salt northward and even a saltier thermocline cannot save it. At the maximum value of *ϕ*<sub>2</sub> < 1.025 (*S<sub>T</sub>* ≈ 35.9), the AMOC is still unstable ($\overset{˙}{q} < 0$) for *q* < 2.9 Sv.

In [Fig. 4d](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4), the final phase of the collapse is depicted: a sharp freshwater pulse has put the AMOC into the unstable regime. It will continue to the OFF regime (*q* < 0) and eventually collapse to the stable OFF equilibrium at *q* = −6 Sv. Apparently, it is more efficient to put the AMOC in this regime via a salinification and a subsequent freshwater pulse than via just one big freshwater pulse. Note that in this new regime (*q* < 0), there is only one stable root ([Fig. 4e](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4)), so from now on, it converges deterministically to this stable OFF state, and the freshwater forcing is no longer needed.

#### 2) Recovery

As seen in [Fig. 4e](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4), in the OFF regime (*q* < 0), there is only one root (equilibrium), which is stable. The physical intuition here is that for a lower (higher) AMOC, more (less) salinity is transported from *B* to *N*, which salinifies (freshens) *N* and hence increases (decreases) the AMOC.

To restart the AMOC, the *N* box needs to be more saline, which can only be achieved via northern gyre transport from *T* and its increased salinity *S<sub>T</sub>*. That is why *ϕ*<sub>2</sub> only occurs multiplied by the gyre coefficient *K<sub>N</sub>* in [(15)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E15). From this equation, it can also be derived that there will always be a stable attracting root in the range *q* < 0 unless

**Equation 17.**

$$
\phi_{2} \geq \phi_{3} + \frac{f_{N}}{k_{N}} - r{({T_{S} - T_{0}})} \approx 1.045.
$$

For any higher *S<sub>T</sub>* values, the gyre transport can salinify the *N* box enough for the AMOC to restart. From [(17)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E17), it also follows that an increased gyre coefficient *K<sub>N</sub>* or temperature difference would aid this recovery, whereas increasing *S<sub>S</sub>* or the freshwater flux *F<sub>N</sub>* would inhibit it.

So, the salinities *S<sub>T</sub>* and *S<sub>N</sub>* (via the gyre transport) slowly increase until *S<sub>T</sub>* ≈ 36.58 (*ϕ*<sub>2</sub> ≈ 1.045). Meanwhile, in the other boxes, the salinity remains largely unchanged. As *S<sub>N</sub>* − *S<sub>S</sub>* slowly increases, so does the AMOC strength, see [Figs. 4f](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4) and [4g](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4). Note that the AMOC remains close to the shifting stable root (the equilibrium).

The moment that the AMOC reverses, indeed at *S<sub>T</sub>* ≈ 36.58, there is no longer a attracting stable OFF state. Suddenly, a large salinity transport occurs from the *T* box to the *N* box. Hence, the salinity in the *T* box rapidly drops, while the opposite takes place in the northern box. With this strong increase in *S<sub>N</sub>*, the AMOC strength also rises fast and even overshoots above the level of the stable root ${\overset{˙}{q}}_{\text{ON}}{({q,\phi_{2}})} = 0$ ([Fig. 4h](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4)). During the increase of the AMOC, the salinities in IP and *S* adjust with a decreased Indo-Pacific gyre transport.

From thereon, the AMOC converges to the stable ON state: the *N* box freshens and the *T* box salinifies via a reduced northern gyre transport; with that, the AMOC strength decreases to the stable ON equilibrium at *q* = 15 Sv ([Fig. 3d](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig3)). Note that due to high salinity *S<sub>T</sub>*, just after *q* &gt; 0 is attained, the basin of attraction of the stable root is huge, and so, the system can reach this equilibrium without any additional forcing ([Fig. 4i](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4)).

### c. Sharp versus sustained forcing

There is a stark asymmetry between the collapse and the recovery of the AMOC. For the collapse, a sharp pulse of freshwater is sufficient to get the system into the unstable regime from where it collapses due to its own dynamics. So, the pulse already decreases before the actual collapse at *q* = 0. In the OFF region, there is no unstable regime, and the stable root has to be shifted with a sustained pulse of salinity until it is close to the AMOC restart at *q* = 0.

The differences between [(14)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E14) and [(15)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E15) are between the coefficients *B*<sub>ON</sub> and *B*<sub>OFF</sub>, and that *A*<sub>ON</sub> = −*A*<sub>OFF</sub>. The latter equation follows from the fact that for a too large AMOC (|*q*| → ∞), it transports a lot of salinity out off *N* box to either *B* or *T*, and so, *S<sub>N</sub>* decreases again (note that ${\overset{˙}{\phi}}_{1} \sim - |q|\phi_{1}$). Hence, $\left| \overset{˙}{q} \middle| \sim - |q|^{2} \right.$ prevents |*q*| from exploding. The difference between the coefficients *B*<sub>ON</sub> and *B*<sub>OFF</sub> is more interesting as the thermocline’s salinity appears in *B*<sub>ON</sub> but not in *B*<sub>OFF</sub>. This is because, in the ON regime, the salinity *S<sub>N</sub>* (and so the AMOC strength) is also determined by the advective salinity transport from the thermocline (i.e., *qϕ*<sub>2</sub>). In the OFF regime, only the gyre transport (*K<sub>N</sub>ϕ*<sub>2</sub>) is present. Hence, in the ON regime, it is possible to use *ϕ*<sub>2</sub> to manipulate the AMOC to enlarge the unstable regime, whereas for the OFF regime, the *B*<sub>OFF</sub> term cannot be altered.

Last, we consider the shape of the optimal forcing associated with the most likely transition paths. A sharp pulse is optimal to collapse the AMOC, and to recover, a gradual (almost linear) increase in forcing has the highest probability. In both cases, a certain salinity value *S<sub>T</sub>* needs to be attained: for the collapse, *T* needs to be fresh enough such that ${\overset{˙}{q}}_{\text{ON}}$ has no roots, while for the recovery, it needs to be saline enough to move the stable root to *q* = 0. Also, for both cases, there is a time penalty: the longer it takes to get to this *S<sub>T</sub>* value, the more of the input leaks away to other boxes. On the other hand, it should not be done too fast because this requires high freshwater input values, which are unlikely. The additional leakages that occur when changing *ϕ*<sub>2</sub> are

$$
V_{2}\frac{V_{0}}{t_{d}}\frac{\partial{\overset{˙}{\phi}}_{2}}{\partial\phi_{2}} = - {({K_{N} + K_{S}})} - |q|,
$$

which are additional outpour via gyres and varying outpour via advection. Now, *K<sub>N</sub>* + *K<sub>S</sub>* ≈ 10.9 Sv, and |*q*| ≈ 15.5 Sv and |*q*| ≈ 6.3 Sv in the stable ON and OFF state, respectively. So in the recovery, the additional outpour from the thermocline box is mainly via the gyres, especially as |*q*| → 0. Therefore, the additional salinity input during the recovery ideally grows linearly since the leakage also grows linearly. However, for the collapse, the decreased salinity transport out of the thermocline is dominated by the AMOC advection. As it diminishes, less salinity is transported out of the Atlantic thermocline, and it becomes more saline, i.e., as |*q*| → 0, the salinification rate ${\overset{˙}{\phi}}_{2}$ slows down with the freshening of box *T*. The evolution of the AMOC is nonlinear due to salt-advection feedback, and it can be heuristically concluded (as the shape of the optimal freshwater forcing cannot be analytically determined) that the loss of advective salinity transport is compensated by the surface freshwater input, and hence, the initial shape of the optimal freshwater pulse is determined by the decrease of the AMOC.

## 5. Response to surface freshwater forcing

### a. Effect of freshwater forcing locations

Following the large deviation principle (LDP), the leading order term of the ratios of probabilities in the limit of small noise can be determined. Suppose one has paths <strong><em>ϕ</em></strong><em><sub>A</sub></em>(*t*) and <strong><em>ϕ</em></strong><em><sub>B</sub></em>(*t*) with Freidlin–Wentzell actions *S<sub>A</sub>* and *S<sub>B</sub>*, respectively, then their relative likelihood is

$$
\frac{\mathbb{P}{\lbrack\boldsymbol{ϕ}_{B}\rbrack}}{\mathbb{P}{\lbrack\boldsymbol{ϕ}_{A}\rbrack}} \asymp \exp {({{({S_{A} - S_{B}})}/\epsilon})},
$$

as long as <strong><em>ϕ</em></strong><em><sub>A</sub></em> and <strong><em>ϕ</em></strong><em><sub>B</sub></em> occur in systems like [(1)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E1) with the same dimensions *d* and *k* and the same smallness parameter *ϵ*; see the derivation in [appendix C](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#app3). Now, the relative likelihood for the collapse and recovery of the AMOC can be determined: $S{\lbrack\boldsymbol{ϕ}_{\text{ON}\rightarrow\text{OFF}}\rbrack} = {({1/2})}{\sum_{t}\xi_{\text{ON}\rightarrow\text{OFF}}^{2}}\mathrm{Δ}t = 0.008\hspace{0.25em}65$ and *S*\[<strong><em>ϕ</em></strong><sub>OFF→ON</sub>\] = 0.011 31 for the standard case of FAMOUS\_B calibrated parameters. Therefore, the collapse is exp\[0.002 66/ϵ\] times more likely than its recovery, which is a factor 1.645 ± 0.115 for our value of ϵ = 0.0055 ± 0.0008.

A similar analysis can be done for the AMOC collapse under various freshwater flux parameters as a way to quantify the effect of different forcing strategies. In [Smith and Gregory (2009)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib41), it is shown that the AMOC response is sensitive to the choice of hosing regions. By varying the fraction of freshwater forcing in different surface boxes, we can express this sensitivity in terms of relative likelihoods. Previously, we used the noise parameters from the FAMOUS\_B calibration, but now, we vary these and compute for each different set of (*A<sub>N</sub>*, *A<sub>T</sub>*, *A<sub>s</sub>*, *A*<sub>IP</sub>) the most likely noise-induced collapse and associated noise. These parameters are changed using

$$
{({A_{N},A_{T},A_{S},A_{\text{IP}}})} = {({\gamma_{1},1 - \gamma_{1}, - \gamma_{2},\gamma_{2} - 1})},
$$

with varying 0 ≤ *γ*<sub>1</sub>, *γ*<sub>2</sub> ≤ 1. Next, the noise vector <strong><em>σ</em></strong> is computed as

$$
\sigma_{i} = f_{\text{norm}}\frac{A_{i}}{V_{i}},
$$

with normalization factor

$$
f_{\text{norm}} = \left. {0.106\hspace{0.25em}318\hspace{0.25em}1}/\sqrt{{\sum\limits_{i}\left(\frac{A_{i}}{V_{i}} \right)}^{2}} \right.,
$$

such that the norm ‖<strong><em>σ</em></strong>‖ is 0.106 318 1 as is the case for the original parameters, and a fair comparison can be made. Following these computations, the earlier used (*A<sub>N</sub>*, *A<sub>T</sub>*, *A<sub>s</sub>*, *A*<sub>IP</sub>) = (0.070, 0.752, −0.257, −0.565) is achieved using (*γ*<sub>1</sub>, *γ*<sub>2</sub>) = (0.09, 0.31). The results are in [Table 1](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#tbl1), where the ratios of the probability of an AMOC collapse for various (*γ*<sub>1</sub>, *γ*<sub>2</sub>) values compared to the probability of an AMOC collapse under the standard parameters are listed.

**Table 1.** The ratio of probabilities of an AMOC collapse under various hosing parameters (*γ*<sub>1</sub> and *γ*<sub>2</sub>) compared to the collapse under standard FAMOUS\_B calibrated hosing parameters for ϵ = 0.0055 ± 0.0008. The fractions of the hosing are (*A<sub>N</sub>*, *A<sub>T</sub>*, *A<sub>S</sub>*, *A*<sub>IP</sub>) = (*γ*<sub>1</sub>, 1 − *γ*<sub>1</sub>, −*γ*<sub>2</sub>, *γ*<sub>2</sub> − 1), so increasing *γ*<sub>1</sub> results in more freshwater hosing in the *N* box and less in the *T* box and increasing *γ*<sub>2</sub> results in more salinity compensation in the *S* box and less in the IP box. The bold values indicate an increased likelihood of an AMOC collapse.

![Table 1](https://journals.ametsoc.org/view/journals/phoc/54/12/full-JPO-D-23-0234.1-t1.jpg)

From [Table 1](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#tbl1), it follows that to increase the likelihood of an AMOC collapse, the freshwater forcing needs to be redistributed with a higher fraction of freshwater into the northern box (increased *γ*<sub>1</sub>) and a lower fraction of compensation into the southern box (decreased *γ*<sub>2</sub>). However, these changes should not be overdone, as dumping all freshwater into the northern box or compensating for it fully from the southern box would actually reduce the likelihood.

To examine the physical reasons behind the changes in likelihood, the scenario with the highest likelihood of collapse ((*γ*<sub>1</sub>, *γ*<sub>2</sub>) = (0.25, 0.25)) and scenarios with either one of the parameters changed are analyzed. Their instantons are shown in [Fig. 5](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig5). Varying *γ*<sub>1</sub> yields the instantons in the left panels of [Fig. 5](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig5). The differences in the salinities *S<sub>S</sub>* and *S*<sub>IP</sub> between scenarios are marginal ($\mathcal{O}{(10^{- 2})}$). As *γ*<sub>1</sub> increases, a higher fraction of the freshwater is dumped into box *N*, and so, the AMOC *q* shuts down more rapidly. The surplus salinity left behind in *T* cannot leave via box *N* and is then redistributed via gyres to *S* and IP, and so, the salinities here are slightly higher during the collapse. Moreover, for lower *γ*<sub>1</sub>, the *T* box is fresher since, with higher *A<sub>T</sub>*, more freshwater is simply deposited here. Similarly, as *γ*<sub>1</sub> increases, the salinity *S<sub>N</sub>* drops more rapidly as a greater amount of freshwater is put here.

![Figure 5](https://journals.ametsoc.org/view/journals/phoc/54/12/full-JPO-D-23-0234.1-f5.jpg)

**Figure 5.** The instantons for (left) varying *γ*<sub>1</sub> and (right) varying *γ*<sub>2</sub> with dimensional salinities: (a),(f) *S<sub>N</sub>*; (b),(g) *S<sub>T</sub>*; (c),(h) *S<sub>S</sub>*; and (d),(i) *S*<sub>IP</sub> and (e),(j) the associated optimal freshwater forcings.

As *γ*<sub>1</sub> is higher than the optimal value *γ*<sub>1</sub> = 0.25, the initial salinification becomes larger, while the subsequent freshwater pulse is sharper and higher. As discussed before, the initial salinification puts the system into a transient state with a fresher *T* box, which destabilizes the AMOC; see also derivation [(14)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E14). As *γ*<sub>1</sub> increases, it becomes harder to directly freshen *T*, and so, the higher initial salinification with a temporary stronger AMOC is required. However, *S<sub>T</sub>* is still higher than usual, so the upcoming freshwater pulse also needs to be stronger. On the other hand, if *γ*<sub>1</sub> decreases from the optimal value, the only way to get the necessary freshwater into box *N* is via advection and gyre transport, which is ineffective as the freshwater input into *T* also leaks to the *S* and IP boxes. So, some freshwater input directly into *N* helps, especially since *V<sub>N</sub>* is relatively small, so its salinity is more easily changed. In conclusion, for *γ*<sub>1</sub>, there is an optimal compromise: *γ*<sub>1</sub> needs to be low enough to directly freshen the stabilizing saline thermocline yet high enough to add freshwater to the relatively small *N* box.

In the right panels of [Fig. 5](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig5), again the optimal hosing scenario is taken, but now, *γ*<sub>2</sub> is varied. Compared to varying *γ*<sub>1</sub>, the salinity and likelihood changes across hosing scenarios are quite small. The salinity changes in the directly affected boxes *S* and IP are only of order $\mathcal{O}{(10^{- 2})}$. The effects are straightforward: an increased *γ*<sub>2</sub> implies a higher fraction of salinification into box IP and so *S*<sub>IP</sub> rises while *S<sub>S</sub>* drops. For the boxes *N* and *T*, there are hardly any differences. Also, the optimal freshwater perturbations change only marginally.

The changes in likelihood can be derived from the graphs in [Fig. 5](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig5). As *γ*<sub>2</sub> is put to zero (*A<sub>S</sub>* = 0), there is no way to directly control *S<sub>S</sub>*, and so, any required marginal changes are done via ineffective gyre and AMOC transport. So, the likelihood slightly decreases. On the other hand, decreasing *A*<sub>IP</sub> has a significant negative effect on the likelihood of collapse. This can be understood with the zoomed inset in the *S<sub>T</sub>* graph ([Fig. 5g](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig5)). As *A*<sub>IP</sub> decreases, the southern box becomes more saline, while the Indo-Pacific freshens. The transport from *S* to *T* is larger than the one from IP to *T* since *K<sub>N</sub>* + *γq* ≈ 11 Sv, while (1 − *γ*)*q* ≈ 9 Sv (taking *q* ≈ 15 Sv). So a saltier Southern Ocean means a saltier Atlantic thermocline which stabilizes the AMOC \[see [(14)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E14)\] and hence decreases the likelihood of collapse.

### b. Linear deterministic versus optimal stochastic forcing

In this section, the behavior of the AMOC in the noise-induced transition following the instanton is compared to its deterministic behavior in a bifurcation-induced tipping. For the latter, we force the AMOC with a prescribed freshwater flux which is piecewise linear time dependent similar to the method of [Wood et al. (2019)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib50). The goal there was to force the AMOC to stay close to equilibrium, and hence, the bifurcation tipping was produced. In [Fig. 6b](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig6), the graph from [Wood et al. (2019)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib50) is qualitatively reproduced with the following deterministic hosing procedure:

$$
\overset{˙}{\boldsymbol{ϕ}}{(t)} = \mathbf{f}{\lbrack{\boldsymbol{ϕ}{(t)}}\rbrack} + \boldsymbol{σ}h{(t)},
$$

where

**Equation 18.**

$$
h{(t)} = {\{\begin{array}{ll} {- 0.012t} & {\text{for}\hspace{0.33em}t < 25} \\ {- 0.3 + 0.012{({t - 25})}} & {\text{for}\hspace{0.33em}t > 25,} \end{array}}
$$

where <strong><em>σ</em></strong> follows from the original hosing parameters from the FAMOUS\_B calibration. Note that with this simple hosing procedure, the amount of hosing sufficient for a transition is not minimized nor the stable OFF state was reached. Moreover, the graph in the original paper was produced with the FAMOUS\_A hosing parameters. In [Fig. 6a](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig6), the instanton is shown, directly followed by the “anti”-instanton, so it is the most likely transition path from ON to OFF and back. Both are computed for the original hosing fractions and are already discussed in [section 4](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#s4). The comparison of the two graphs in [Fig. 6](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig6) illuminates the different behaviors of noise-induced and bifurcation-induced tipping.

![Figure 6](https://journals.ametsoc.org/view/journals/phoc/54/12/full-JPO-D-23-0234.1-f6.jpg)

**Figure 6.** (a) The instanton directly followed by the anti-instanton and (b) the deterministic model behavior under the prescribed freshwater forcing [(18)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E18) for dimensional salinities: *S<sub>N</sub>* (red), *S<sub>T</sub>* (blue), *S<sub>S</sub>* (cyan), *S*<sub>IP</sub> (brown), and *S<sub>B</sub>* (black).

First, the salinity *S<sub>T</sub>* is in the deterministic hosing simulation much lower than for the instanton trajectory. In the former, freshwater is continuously put into the thermocline box causing its salinity to stay low. But along the instanton, one sees *S<sub>T</sub>* bouncing back since an AMOC collapse means that salt is no longer transported northward out of the thermocline. Second, the salinity *S<sub>N</sub>* drops less rapidly than in the instanton’s case. The main reason is that in the latter case, a sharp freshwater pulse is introduced to the *T* box, which rapidly freshens the northern box via the AMOC before it collapses, whereas in the former case, the freshwater is introduced gradually, so *S<sub>N</sub>* drops less rapidly. Third, smaller features are seen in the trajectories of *S*<sub>IP</sub> and *S<sub>S</sub>*. For these boxes, the salinities grow more slowly since freshwater is extracted more gently. It seems that due to the excess freshwater extraction in the hosing, the salinities of these two boxes and of the *B* box are artificially higher. Last, the recovery of the AMOC shows the same overshooting for both freshwater forcing strategies: in both cases, we need *S<sub>T</sub>* ≈ 36.58 since this is just salty enough to reactivate the AMOC. After this, all the salt is suddenly transported northward, causing a huge rise and drop in *S<sub>N</sub>* and *S<sub>T</sub>*, respectively. Small salinity differences after the recovery between the hosing strategies are because in the linear hosing case, freshwater is still being extracted from *T*, and so additional salt is transported northward causing a higher *S<sub>N</sub>*. That the bifurcation- and noise-induced tipping do not differ that much when the AMOC recovers could also be concluded from [Figs. 4e–g](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4), as the system stays close to the shifting stable root.

Comparing the bifurcation points of the system with the computed optimal forcing also indicates the similarity between the most likely noise-induced and bifurcation-induced recovery. The AMOC has two stable states for *h* ∈ (−0.069, 0.025), i.e., (−0.066, 0.180) Sv of freshwater input into *N* and *T*. So, in the quasi-equilibrium approach done in [Fig. 6b](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig6), the AMOC is in a monostable OFF and ON regimes for *t* ∈ (6, 44) years and *t* &gt; 52 years, respectively. The optimal forcing for the noise-induced AMOC collapse only crosses the bifurcation point briefly for 1.7 years \[*t* ∈ (12, 13.7) years, see [Fig. 2c](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig2)\], and this ends already 1.3 years before reaching the separatrix. A brief time interval where no stable ON state exists (see [Fig. 4b](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4)) is enough to put the AMOC in an unstable regime from where it collapses even though a stable ON state exists again (see [Fig. 4c](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4)). Contrarily, the optimal forcing for the recovery crosses the bifurcation threshold for *t* ∈ (15.9, 25) years continuing till the separatrix, see [Fig. 2d](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig2). So here, the separatrix is crossed when no stable OFF state exists, similar to a bifurcation-induced tipping. This can also be deduced from [Figs. 4e–g](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#fig4): the crossing happens when eventually there is no stable root for *q* < 0, i.e., the OFF regime no longer sees any state with a decreasing *q* for the given salinity *ϕ*<sub>2</sub>. Hence, the most likely noise-induced collapse only crosses the bifurcation briefly and before reaching the separatrix, while the noise-induced collapse has a sustained forcing that crosses this bifurcation threshold through to the separatrix and behaves like a bifurcation-induced tipping.

## 6. Summary and discussion

In this work, we computed the most likely paths of an AMOC collapse and recovery in a stochastic version of the [Wood et al. (2019)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib50) model. This is a conceptual box model representation of the World Ocean which is calibrated to the AOGCM FAMOUS. We added the stochasticity to allow for noise-induced tipping of the AMOC, which was justified as a representation of the *P* − *E* annual variation in the North Atlantic. Thanks to the model’s simplicity, the instantons can be readily computed. Using this method, we made a thorough analysis of noise-induced transitions of the AMOC. The most likely collapse of the AMOC will be preempted by an initial strengthening of the AMOC, which puts it into a less stable transient state. This is followed by a sharp freshwater pulse into the Atlantic thermocline such that the AMOC ends up in an unstable regime from where it collapses due to its own deterministic dynamics. Contrarily, the noise-induced recovery is quite close to the shifting equilibrium and is comparable to a bifurcation tipping.

By comparing the actions of the instantons, the ratios of their probabilities in the low-noise limit were computed. Any biases toward an ON or OFF state due to the hosing method are now eliminated, accommodating a quantitative analysis of various hosing methods. This is a strength of the method since probabilities are determined and not merely mechanisms or theoretical possibilities of the hosing methods. This showed that to maximize the probability of an AMOC collapse, most of the freshwater forcing needs to be added to the Atlantic thermocline such that it cannot salinify the northern Atlantic, while only a small fraction of the compensation needs to be in the Southern Ocean since from here the Atlantic thermocline can most easily be salinified.

The limitations of our approach are first the assumptions on the freshwater noise. Adding a white noise process for freshwater forcing to the model has been done many times ([Cessi 1994](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib7); [Timmermann and Lohmann 2000](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib46); [Castellana et al. 2019](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib6)) and simplifies many computations, but under climate change, this noise can be colored and state-dependent. Furthermore, the system needs to be in the limit of low noise. This is the case for the model used here and arguably holds for other AMOC models, as the noise compared to the AMOC strength should not depend too much on the model choice. The computation itself of the instanton can be tedious for more detailed ocean models and was here limited to low-dimensional continuous models. However, formally, the Freidlin–Wentzell action holds for infinite dimensional stochastic PDEs (SPDEs) and can be extended to multiplicative and even non-Gaussian noise ([Grafke and Vanden-Eijnden 2019](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib17)).

Last, this study’s relevance relies on the present-day AMOC being in a multistable regime in order for noise-induced transitions to be possible. As mentioned, it is debatable whether the observed negative AMOC-induced freshwater transport at the southern boundary of the Atlantic basin is an indicator of this multistability. We think that the evidence in favor of this claim is strong enough that the possibility of multistability should not be ignored. A range of studies have shown this indicator to be reliable in a hierarchy of ocean models ([de Vries and Weber 2005](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib10); [Dijkstra 2007](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib11); [Huisman et al. 2010](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib22)) and even in a state-of-the-art global climate model ([van Westen and Dijkstra 2023](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib47)). However, there are also numerous studies arguing the present-day AMOC to be monostable ([Jackson 2013](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib23); [Jackson et al. 2023](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib25)). That said, we should consider that this indicator in these models is sensitive to model biases ([Mecking et al. 2017](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib31)). This debate is far from settled and outside the study’s scope.

It will obviously be a challenge to compute instantons in spatially extended models of the AMOC that are governed by SPDEs, which would provide the identification of the most vulnerable freshwater forcing regions to tip the AMOC. From this, likely ensemble simulations can be designed to optimize the probability of a noise-induced AMOC transition, which can possibly be used in global climate models. Also—given a computed probability of an AMOC collapse ([Castellana et al. 2019](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib6))—the probabilities for other forcing scenarios in the low-noise limit can be computed. Last, as instantons have been used as precursors for noise-induced tipping in more simplified models ([Giorgini et al. 2020](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#bib16)), it is worth exploring whether they can be used to identify early warning signals of an approaching AMOC collapse.

## Acknowledgments

We thank Reyk Börner, Raphael Römer, Jason Frank, and the two anonymous reviewers for their insightful suggestions. J.S. and H.A.D. are funded by the European Research Council through ERC-AdG project TAOC (Project 101055096). T.G. acknowledges support from EPSRC projects EP/T011866/1 and EP/V013319/1. For the purpose of open access, the authors have applied a Creative Commons Attribution (CC BY) licence to any author accepted manuscript version arising from this submission.

## Data availability statement

The results can be readily reproduced using the described method and the stated parameter values.

## APPENDIX A

### Numerical Solution of the Instanton Equations

We want to solve the Hamiltonian [(6)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E6) with boundary conditions <strong><em>ϕ</em></strong>(0) = **x** and <strong><em>ϕ</em></strong>(*T*) = **y**. Reformulating it as a minimization problem of the cost function yields

$$
\begin{array}{l} {J{\lbrack{\boldsymbol{ϕ}{(t)},\boldsymbol{θ}{(t)},\boldsymbol{μ}{(t)}}\rbrack} = \frac{1}{2}{\int_{0}^{T}{\left\langle {\boldsymbol{θ}{(t)},\mathbf{a}\boldsymbol{θ}{(t)}} \right\rangle dt}}} \\ {+ {\int_{0}^{T}{\left\langle {\boldsymbol{μ}{(t)},\overset{˙}{\boldsymbol{ϕ}}{(t)} - \mathbf{f}{\lbrack{\boldsymbol{ϕ}{(t)}}\rbrack} - \mathbf{a}\boldsymbol{θ}{(t)}} \right\rangle dt}}} \\ {\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em}\hspace{0.25em} + \left\langle {\beta,\boldsymbol{ϕ}{(T)} - \mathbf{y}} \right\rangle + \lambda\left\| {\boldsymbol{ϕ}{(T)} - \mathbf{y}} \right\|^{2},} \end{array}
$$

where $\left. \boldsymbol{μ}:{\lbrack{0,T}\rbrack}\rightarrow\mathbb{R}^{d} \right.$ and $\boldsymbol{β} \in \mathbb{R}^{d}$ are the Lagrange multipliers to fulfill the constraints and *λ* is an additional penalty term. Equalizing the variational derivatives to zero,

$$
\begin{array}{l} \left. \frac{\delta J}{\delta\boldsymbol{θ}} = 0\Leftrightarrow\mathbf{a}{({\boldsymbol{θ}{(t)} - \boldsymbol{μ}{(t)}})} = 0 \right. \\ \left. \frac{\delta J}{\delta\boldsymbol{ϕ}} = 0\Leftrightarrow - \overset{˙}{\boldsymbol{μ}}{(t)} - {({\nabla\mathbf{f}{\lbrack{\boldsymbol{ϕ}{(t)}}\rbrack}})}^{\text{T}}\boldsymbol{μ}{(t)} = 0 \right. \\ \left. \frac{\delta J}{\delta\boldsymbol{μ}} = 0\Leftrightarrow\overset{˙}{\boldsymbol{ϕ}}{(t)} - \mathbf{f}{\lbrack{\boldsymbol{ϕ}{(t)}}\rbrack} - \mathbf{a}\boldsymbol{θ}{(t)} = 0, \right. \end{array}
$$

and for the constraints,

$$
\begin{array}{l} {\frac{\partial J}{\partial\lambda} = \left\| {\boldsymbol{ϕ}{(T)} - \mathbf{y}} \right\|^{2} = 0} \\ {\nabla_{\boldsymbol{β}}J = \boldsymbol{ϕ}{(T)} - \mathbf{y} = 0.} \end{array}
$$

Minimizing this cost function together with initial condition <strong><em>ϕ</em></strong>(0) = **x** solves the instanton equations. This pseudocode is used to find the minimum:

**Given initials** <strong><em>ϕ</em></strong><sup>0</sup>(*t*), <strong><em>θ</em></strong><sup>0</sup>(*t*), <strong><em>μ</em></strong><sup>0</sup>(*t*)

**Repeat:**

&emsp;&emsp;**Repeat until** ǁ<strong><em>θ</em></strong><em><sup>k</sup></em>(*t*) − <strong><em>μ</em></strong><em><sup>k</sup></em><sup>+1</sup>(*t*)ǁ<**tol:**

&emsp;&emsp;&emsp;&emsp;**Integrate forward**

&emsp;&emsp;&emsp;&emsp;&emsp;&emsp; ${\overset{˙}{\boldsymbol{ϕ}}}^{k + 1}{(t)} = \mathbf{f}{\lbrack{\boldsymbol{ϕ}^{k}{(t)}}\rbrack} + \mathbf{a}\boldsymbol{θ}^{k}{(t)}$

&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;**with** <strong><em>ϕ</em></strong><em><sup>k</sup></em><sup>+1</sup>(0) = **x**

&emsp;&emsp;&emsp;&emsp;**Integrate backward**

&emsp;&emsp;&emsp;&emsp;&emsp; ${\overset{˙}{\boldsymbol{μ}}}^{k + 1}{(t)} = - \nabla\mathbf{f}{\lbrack{\boldsymbol{ϕ}^{k + 1}{(t)}}\rbrack}^{\text{T}}\boldsymbol{μ}^{k}{(t)}$

&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;**with** <strong><em>μ</em></strong><em><sup>k</sup></em><sup>+1</sup>(*T*) = −(2<em>λ</em>(<strong><em>ϕ</em></strong><em><sup>k</sup></em><sup>+1</sup>(*T*) − **y**) + <strong><em>β</em></strong>),

&emsp;&emsp;&emsp;&emsp;<strong><em>θ</em></strong><em><sup>k</sup></em><sup>+1</sup>(*t*) = <strong><em>θ</em></strong><em><sup>k</sup></em> − *α*(<strong><em>θ</em></strong><em><sup>k</sup></em>(*t*) − <strong><em>μ</em></strong><em><sup>k</sup></em><sup>+1</sup>(*t*))

&emsp;&emsp;&emsp;&emsp;&emsp;**with** *α* = max\{*α|J*\[<strong><em>ϕ</em></strong><em><sup>k</sup></em><sup>+1</sup>, <strong><em>θ</em></strong><em><sup>k</sup></em><sup>+1</sup>, <strong><em>μ</em></strong><em><sup>k</sup></em><sup>+1</sup>\]

&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;<*J*\[<strong><em>ϕ</em></strong><em><sup>k</sup></em><sup>+1</sup>, <strong><em>θ</em></strong><em><sup>k</sup></em>, <strong><em>μ</em></strong><em><sup>k</sup></em><sup>+1</sup>\]\}

&emsp;&emsp;<strong><em>β</em></strong> → <strong><em>β</em></strong> + *λ*(<strong><em>ϕ</em></strong><em><sup>k</sup></em><sup>+1</sup>(*T*) − **y**)

&emsp;&emsp;*λ* → *f<sub>λ</sub>λ*

where *f<sub>λ</sub>* &gt; 1 is a factor to update *λ*. The algorithm searches for the end condition <strong><em>θ</em></strong>(*T*) = −*β* such that <strong><em>ϕ</em></strong>(*T*) = **y**. The equation for the path <strong><em>ϕ</em></strong>(*t*) is integrated forward in time, while that for the conjugate momentum is integrated backward in time to ensure numerical stability. To speed up convergence, we added <strong><em>θ</em></strong> = 0 after *q* switches sign. This is justified as the model converges deterministically to the new stationary point after this switch following the analysis done in [section 4b](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#s4b).

## APPENDIX B

### Used Parameter Values

In [Table B1](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#tblB1), the parameter values of the nondimensional model are provided. The volumes and transports are written in units 10<sup>6</sup> m<sup>3</sup> and Sverdrups, respectively, such that most parameters have an order of magnitude $\mathcal{O}{(10^{- 2})}–\mathcal{O}{(10^{2})}$. The parameters that do not fullfill this always occur in reasonable ratios: *t<sub>d</sub>*/*V*<sub>0</sub> ∼ 0.315 36 × 10<sup>−6</sup> m<sup>−3</sup> s and *C*/(*S*<sub>0</sub>*V*<sub>0</sub>) ∼ 127.

**Table B1.** Used parameter values.

![Table B1](https://journals.ametsoc.org/view/journals/phoc/54/12/full-JPO-D-23-0234.1-tB1.jpg)

## APPENDIX C

### Relative Likelihood in Low-Noise Limit

Consider two stochastic systems as in [(1)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E1) with the same smallness parameter *ϵ* indicating the noise amplitude:

$$
\begin{array}{l} {d\mathbf{X}_{t}^{1} = \mathbf{f}_{1}{(\mathbf{X}_{t}^{1})}dt + \boldsymbol{σ}_{1}\sqrt{\epsilon}\hspace{0.25em}d\mathbf{W}_{t}^{1}} \\ {d\mathbf{X}_{t}^{2} = \mathbf{f}_{2}{(\mathbf{X}_{t}^{2})}dt + \boldsymbol{σ}_{2}\sqrt{\epsilon}\hspace{0.25em}d\mathbf{W}_{t}^{2}} \end{array},
$$

where $\mathbf{X}_{t}^{i} \in \mathbb{R}^{d}$ is the state vector, $\left. \mathbf{f}_{i}:\mathbb{R}^{d}\rightarrow\mathbb{R}^{d} \right.$ is the deterministic drift, $\mathbf{W}_{t}^{i}$ is a *k*-dimensional Wiener process, and $\boldsymbol{σ}_{i} \in \mathbb{R}^{d \times k}$ distributes the noise for *i* ∈ \{1, 2\}. We need ‖<strong><em>σ</em></strong><sub>1</sub>‖ = ‖<strong><em>σ</em></strong><sub>2</sub>‖ in order for the noise amplitudes to be the same in both systems. Again, we state [(2)](https://journals.ametsoc.org/view/journals/phoc/54/12/JPO-D-23-0234.1.xml#E2) for both systems:

$$
\epsilon\hspace{0.25em}\log \left({\mathbb{P}\left\lbrack {\underset{t \in {\lbrack{0,T}\rbrack}}{\sup }\left\| {\mathbf{X}_{t}^{i} - \boldsymbol{ϕ}^{i}{(t)}} \right\| < \delta} \right\rbrack} \right) = - S_{T}^{i}{\lbrack\boldsymbol{ϕ}^{i}\rbrack} + \mathcal{ℴ}{(\epsilon)},
$$

where $S_{T}^{i}$ is the Freidlin–Wentzell action for system *i* and $\left. \boldsymbol{ϕ}^{i}{(t)}:{\lbrack{0,T}\rbrack}\rightarrow\mathbb{R}^{d} \right.$ is a path in that system. The relative likelihood in the low-noise limit between path <strong><em>ϕ</em></strong><sup>1</sup>(*t*) in the first and <strong><em>ϕ</em></strong><sup>2</sup>(*t*) in the second system is now computed as

$$
\begin{array}{l} {\epsilon\hspace{0.25em}\log \left(\frac{\mathbb{P}\left\lbrack {{\sup }_{t \in {\lbrack{0,T}\rbrack}}\left\| {\mathbf{X}_{t}^{1} - \boldsymbol{ϕ}^{1}{(t)}} \right\| < \delta} \right\rbrack}{\mathbb{P}\left\lbrack {{\sup }_{t \in {\lbrack{0,T}\rbrack}}\left\| {\mathbf{X}_{t}^{2} - \boldsymbol{ϕ}^{2}{(t)}} \right\| < \delta} \right\rbrack} \right)} \\ {\hspace{1em} = S_{T}^{2}{\lbrack\boldsymbol{ϕ}^{2}\rbrack} - S_{T}^{1}{\lbrack\boldsymbol{ϕ}^{1}\rbrack} + \mathcal{ℴ}{(\epsilon)},} \end{array}
$$

and hence,

$$
\begin{array}{l} \frac{\mathbb{P}\left({{\sup }_{t \in {\lbrack{0,T}\rbrack}}\left\| {\mathbf{X}_{t}^{1} - \boldsymbol{ϕ}^{1}{(t)}} \right\| < \delta} \right)}{\mathbb{P}\left({{\sup }_{t \in {\lbrack{0,T}\rbrack}}\left\| {\mathbf{X}_{t}^{2} - \boldsymbol{ϕ}^{2}{(t)}} \right\| < \delta} \right)} \\ {\hspace{1em} \asymp \exp {({{({S_{T}^{2}{(\boldsymbol{ϕ}^{2})} - S_{T}^{1}{(\boldsymbol{ϕ}^{1})}})}/\epsilon})} \cdot} \end{array}
$$

## References (50 total, showing 50)

- Alkhayuon, H., P. Ashwin, L. C. Jackson, C. Quinn, and R. A. Wood, 2019: Basin bifurcations, oscillatory instability and rate-induced thresholds for Atlantic meridional overturning circulation in a global oceanic box model. <em>Proc. Roy. Soc.</em>, **475A**, 20190051, https://doi.org/10.1098/rspa.2019.0051.

- Blyuss, K. B., and Y. N. Kyrychko, 2023: Sex, ducks, and rock “n” roll: Mathematical model of sexual response. <em>Chaos</em>, **33**, 043106, https://doi.org/10.1063/5.0143190.

- Boers, N., 2021: Observation-based early-warning signals for a collapse of the Atlantic Meridional Overturning Circulation. <em>Nat. Climate Change</em>, **11**, 680–688, https://doi.org/10.1038/s41558-021-01097-4.

- Börner, R., R. Deeley, R. Römer, T. Grafke, V. Lucarini, and U. Feudel, 2023: Saddle avoidance of noise-induced transitions in multiscale systems. arXiv, 2311.10231v4, https://doi.org/10.48550/arXiv.2311.10231.

- Caesar, L., S. Rahmstorf, A. Robinson, G. Feulner, and V. Saba, 2018: Observed fingerprint of a weakening Atlantic Ocean overturning circulation. <em>Nature</em>, **556**, 191–196, https://doi.org/10.1038/s41586-018-0006-5.

- Castellana, D., S. Baars, F. W. Wubs, and H. A. Dijkstra, 2019: Transition probabilities of noise-induced transitions of the Atlantic Ocean circulation. <em>Sci. Rep.</em>, **9**, 20284, https://doi.org/10.1038/s41598-019-56435-6.

- Cessi, P., 1994: A simple box model of stochastically forced thermohaline flow. <em>J. Phys. Oceanogr.</em>, **24**, 1911–1920, https://doi.org/10.1175/1520-0485(1994)024<1911:ASBMOS&gt;2.0.CO;2.

- Cimatoribus, A. A., S. S. Drijfhout, and H. A. Dijkstra, 2014: Meridional overturning circulation: Stability and ocean feedbacks in a box model. <em>Climate Dyn.</em>, **42**, 311–328, https://doi.org/10.1007/s00382-012-1576-9.

- Dee, D. P., and Coauthors, 2011: The era-interim reanalysis: Configuration and performance of the data assimilation system. <em>Quart. J. Roy. Meteor. Soc.</em>, **137**, 553–597, https://doi.org/10.1002/qj.828.

- de Vries, P., and S. L. Weber, 2005: The Atlantic freshwater budget as a diagnostic for the existence of a stable shut down of the meridional overturning circulation. <em>Geophys. Res. Lett.</em>, **32**, L09606, https://doi.org/10.1029/2004GL021450.

- Dijkstra, H. A., 2007: Characterization of the multiple equilibria regime in a global ocean model. <em>Tellus</em>, **59A**, 695–705, https://doi.org/10.1111/j.1600-0870.2007.00267.x.

- Ditlevsen, P. D., and S. J. Johnsen, 2010: Tipping points: Early warning and wishful thinking. <em>Geophys. Res. Lett.</em>, **37**, L19703, https://doi.org/10.1029/2010GL044486.

- Ditlevsen, P. D., and S. Ditlevsen, 2023: Warning of a forthcoming collapse of the Atlantic meridional overturning circulation. <em>Nat. Commun.</em>, **14**, 4254, https://doi.org/10.1038/s41467-023-39810-w.

- Frajka-Williams, E., and Coauthors, 2019: Atlantic meridional overturning circulation: Observed transport and variability. <em>Front. Mar. Sci.</em>, **6**, 260, https://doi.org/10.3389/fmars.2019.00260.

- Freidlin, M. I., and A. D. Wentzell, 1998: *Random Perturbations*. Springer, 430 pp.

- Giorgini, L. T., S. H. Lim, W. Moon, and J. S. Wettlaufer, 2020: Precursors to rare events in stochastic resonance. <em>Europhys. Lett.</em>, **129**, 40003, https://doi.org/10.1209/0295-5075/129/40003.

- Grafke, T., and E. Vanden-Eijnden, 2019: Numerical computation of rare events via large deviation theory. <em>Chaos</em>, **29**, 063118, https://doi.org/10.1063/1.5084025.

- Grafke, T., R. Grauer, and T. Schäfer, 2015: The instanton method and its numerical implementation in fluid mechanics. <em>J. Phys. A: Math. Theor.</em>, **48**, 333001, https://doi.org/10.1088/1751-8113/48/33/333001.

- Hawkins, E., R. S. Smith, L. C. Allison, J. M. Gregory, T. J. Woollings, H. Pohlmann, and B. De Cuevas, 2011: Bistability of the Atlantic overturning circulation in a global climate model and links to ocean freshwater transport. <em>Geophys. Res. Lett.</em>, **38**, L10605, https://doi.org/10.1029/2011GL047208.

- Hestenes, M. R., 1969: Multiplier and gradient methods. <em>J. Optim. Theory Appl.</em>, **4**, 303–320, https://doi.org/10.1007/BF00927673.

- Hofmann, M., and S. Rahmstorf, 2009: On the stability of the Atlantic meridional overturning circulation. <em>Proc. Natl. Acad. Sci. USA</em>, **106**, 20 584–20 589, https://doi.org/10.1073/pnas.0909146106.

- Huisman, S. E., M. Den Toom, H. A. Dijkstra, and S. Drijfhout, 2010: An indicator of the multiple equilibria regime of the Atlantic meridional overturning circulation. <em>J. Phys. Oceanogr.</em>, **40**, 551–567, https://doi.org/10.1175/2009JPO4215.1.

- Jackson, L. C., 2013: Shutdown and recovery of the AMOC in a coupled global climate model: The role of the advective feedback. <em>Geophys. Res. Lett.</em>, **40**, 1182–1188, https://doi.org/10.1002/grl.50289.

- Jackson, L. C., and R. A. Wood, 2018: Hysteresis and resilience of the AMOC in an eddy-permitting GCM. <em>Geophys. Res. Lett.</em>, **45**, 8547–8556, https://doi.org/10.1029/2018GL078104.

- Jackson, L. C., and Coauthors, 2023: Understanding AMOC stability: The North Atlantic Hosing Model Intercomparison Project. <em>Geosci. Model Dev.</em>, **16**, 1975–1995, https://doi.org/10.5194/gmd-16-1975-2023.

- Jacques-Dumas, V., R. M. van Westen, and H. A. Dijkstra, 2024: Estimation of AMOC transition probabilities using a machine learning based rare-event algorithm. arXiv, 2401.10800v3, https://doi.org/10.48550/arXiv.2401.10800.

- Lenton, T. M., and Coauthors, 2007: Effects of atmospheric dynamics and ocean resolution on bi-stability of the thermohaline circulation examined using the Grid Enabled Integrated Earth system modelling (GENIE) framework. <em>Climate Dyn.</em>, **29**, 591–613, https://doi.org/10.1007/s00382-007-0254-9.

- Lenton, T. M., H. Held, E. Kriegler, J. W. Hall, W. Lucht, S. Rahmstorf, and H. J. Schellnhuber, 2008: Tipping elements in the Earth’s climate system. <em>Proc. Natl. Acad. Sci. USA</em>, **105**, 1786–1793, https://doi.org/10.1073/pnas.0705414105.

- Lucarini, V., and P. H. Stone, 2005: Thermohaline circulation stability: A box model study. Part I: Uncoupled model. <em>J. Climate</em>, **18**, 501–513, https://doi.org/10.1175/JCLI-3278.1.

- Marotzke, J., 2000: Abrupt climate change and thermohaline circulation: Mechanisms and predictability. <em>Proc. Natl. Acad. Sci. USA</em>, **97**, 1347–1350, https://doi.org/10.1073/pnas.97.4.1347.

- Mecking, J. V., S. S. Drijfhout, L. C. Jackson, and M. B. Andrews, 2017: The effect of model bias on Atlantic freshwater transport and implications for AMOC bi-stability. <em>Tellus</em>, **69A**, 1299910, https://doi.org/10.1080/16000870.2017.1299910.

- Mikosch, T., 1998: *Elementary Stochastic Calculus with Finance in View*. World Scientific, 212 pp.

- Nocedal, J., and S. J. Wright, 1999: *Numerical Optimization*. Springer, 636 pp.

- Puhalskii, A., 2004: On some degenerate large deviation problems. <em>Electron. J. Probab.</em>, **9**, 862–886, https://doi.org/10.1214/EJP.v9-232.

- Rahmstorf, S., 1996: On the freshwater forcing and transport of the Atlantic thermohaline circulation. <em>Climate Dyn.</em>, **12**, 799–811, https://doi.org/10.1007/s003820050144.

- Rahmstorf, S., and Coauthors, 2005: Thermohaline circulation hysteresis: A model intercomparison. <em>Geophys. Res. Lett.</em>, **32**, L23605, https://doi.org/10.1029/2005GL023655.

- Romanou, A., and Coauthors, 2023: Stochastic bifurcation of the North Atlantic circulation under a midrange future climate scenario with the NASA-GISS modelE. <em>J. Climate</em>, **36**, 6141–6161, https://doi.org/10.1175/JCLI-D-22-0536.1.

- Rooth, C., 1982: Hydrology and ocean circulation. <em>Prog. Oceanogr.</em>, **11**, 131–149, https://doi.org/10.1016/0079-6611(82)90006-4.

- Schorlepp, T., T. Grafke, S. May, and R. Grauer, 2022: Spontaneous symmetry breaking for extreme vorticity and strain in the three-dimensional Navier–Stokes equations. <em>Philos. Trans. Roy. Soc.</em>, **A380**, 20210051, https://doi.org/10.1098/rsta.2021.0051.

- Smith, R. S., 2012: The FAMOUS climate model (versions XFXWB and XFHCC): Description update to version XDBUA. <em>Geosci. Model Dev.</em>, **5**, 269–276, https://doi.org/10.5194/gmd-5-269-2012.

- Smith, R. S., and J. M. Gregory, 2009: A study of the sensitivity of ocean overturning circulation and climate to freshwater input in different regions of the North Atlantic. <em>Geophys. Res. Lett.</em>, **36**, L15701, https://doi.org/10.1029/2009GL038607.

- Smith, R. S., J. M. Gregory, and A. Osprey, 2008: A description of the FAMOUS (version XDBUA) climate model and control run. <em>Geosci. Model Dev.</em>, **1**, 53–68, https://doi.org/10.5194/gmd-1-53-2008.

- Srokosz, M. A., N. P. Holliday, and H. L. Bryden, 2023: Atlantic overturning: New observations and challenges. <em>Philos. Trans. Roy. Soc.</em>, **A381**, 20220196, https://doi.org/10.1098/rsta.2022.0196.

- Stommel, H., 1961: Thermohaline convection with two stable regimes of flow. <em>Tellus</em>, **13A**, 224–230, https://doi.org/10.3402/tellusa.v13i2.9491.

- Taylor, J. R., 2005: *Classical Mechanics*. Vol. 1. Springer, 808 pp.

- Timmermann, A., and G. Lohmann, 2000: Noise-induced transitions in a simplified model of the thermohaline circulation. <em>J. Phys. Oceanogr.</em>, **30**, 1891–1900, https://doi.org/10.1175/1520-0485(2000)030<1891:NITIAS&gt;2.0.CO;2.

- van Westen, R. M., and H. A. Dijkstra, 2023: Asymmetry of AMOC hysteresis in a state-of-the-art global climate model. <em>Geophys. Res. Lett.</em>, **50**, e2023GL106088, https://doi.org/10.1029/2023GL106088.

- Weijer, W., and Coauthors, 2019: Stability of the Atlantic Meridional Overturning Circulation: A review and synthesis. <em>J. Geophys. Res. Oceans</em>, **124**, 5336–5375, https://doi.org/10.1029/2019JC015083.

- Woillez, E., and F. Bouchet, 2020: Instantons for the destabilization of the inner solar system. <em>Phys. Rev. Lett.</em>, **125**, 021101, https://doi.org/10.1103/PhysRevLett.125.021101.

- Wood, R. A., J. M. Rodríguez, R. S. Smith, L. C. Jackson, and E. Hawkins, 2019: Observable, low-order dynamical controls on thresholds of the Atlantic meridional overturning circulation. <em>Climate Dyn.</em>, **53**, 6815–6834, https://doi.org/10.1007/s00382-019-04956-1.
