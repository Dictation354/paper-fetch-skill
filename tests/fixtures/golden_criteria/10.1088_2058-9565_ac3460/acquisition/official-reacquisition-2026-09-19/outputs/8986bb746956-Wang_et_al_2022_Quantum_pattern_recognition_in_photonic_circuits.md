---
title: "Quantum pattern recognition in photonic circuits"
authors: "Rui Wang, Carlos Hernani-Morales, José D Martín-Guerrero, Enrique Solano, Francisco Albarrán-Arriagada"
journal: "Quantum Science and Technology"
doi: "10.1088/2058-9565/ac3460"
published: "2022-1-1"
source: "iop_html"
acquisition:
  provider: "iop"
  route: "browser_html"
  representation: "html"
  transport: "browser"
  fallback_used: false
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 11024
---

# Quantum pattern recognition in photonic circuits

## Abstract

This paper proposes a machine learning method to characterize photonic states via a simple optical circuit and data processing of photon number distributions, such as photonic patterns. The input states consist of two coherent states used as references and a two-mode unknown state to be studied. We successfully trained supervised learning algorithms that can predict the degree of entanglement in the two-mode state as well as perform the full tomography of one photonic mode, obtaining satisfactory values in the considered regression metrics.

## 1. Introduction

Quantum information processing deals with the manipulation of quantum states in order to perform quantum informational tasks such as quantum algorithms [1], quantum error correction [2], quantum cryptography [3], or quantum teleportation [4]. It is known that quantum information has the potential to outperform classical information protocols [5–9]. However, since a quantum system is modified after measurement, extracting arbitrary information from a quantum state may require many copies. In general, quantum tomography (QT) can be employed for the full reconstruction of a quantum state or a quantum operator. In a nutshell, QT implies the measurement of the expectation values of several operators or the use of a mutually unbiased basis [10–12], which is in general a hard experimental task. In the last years, some efficient protocols have been proposed assisted by machine learning (ML) algorithms, although it may still be tricky depending on the dimension of the quantum system [13–18].

Quantum information can be encoded, decoded, and manipulated in a variety of physical systems, for example, photonic systems [19], solid state devices [20], trapped ions [21, 22], and superconducting architectures [23, 24]. Photonic platforms present several advantages for quantum information protocols, such as long coherence times and full connectivity, allowing long-distance quantum communication and quantum key distribution, among many other achievements [25–27]. Different photonic degrees of freedom, including polarization, spectral, spatial, and temporal modes can be used to encode information [19], providing a huge variety of experimental resources for many quantum information tasks.

One of the most intriguing experimental resources for photonic platform is boson sampling, which is a model of non-universal quantum computation. It consists in measuring or sampling the quantity of photons in a distribution produced by a linear interference device given an initial photonic Fock state [28]. It is a complex problem that cannot be efficiently simulated on conventional computers. However, with accessible experimental requirements, it can be simulated on linear optical quantum computers. It is attractive that the experimental setup of boson sampling only requires single-photon sources, photodetectors, and linear optical elements, i.e. beam splitters and phase shifters [29]. Such a feasibility has encouraged and inspired many research teams for lab implementations [30–34]. Particularly, recent experiments have shown the potential of photonic technologies to obtain quantum advantage for scientific relevant problems; for instance, quantum supremacy of Gaussian boson sampling with 76 photons [7], and the so-called timestamp boson sampling, that brings to light the potential of circuits to get memory effects, thus paving the way for the implementation of neuromorphic quantum computing [35, 36].

On a separate note, it is known that ML algorithms help to extract information from large and complex data sets, encompassing different techniques with sound mathematical grounds [37, 38]. The information is extracted by means of learning algorithms, that teach models which usually have no *a priori* knowledge of the problem. The increasing availability and size of data sets has spread the use of ML [39, 40], oftentimes involving reliable applications at academic and commercial levels.

The main goal of this manuscript is to show a simple and experimentally feasible photonic architecture capable to produce photonic patterns which assisted by ML algorithms could give an estimation about quantum features hard to calculate experimentally. To this end, we consider whether the full tomography of a photonic mode and two-mode entanglement can be extracted via sampling the output distribution of photons. In order to obtain a relation between the distribution probability of the output state and the information of the unknown state, we propose a particular linear optical circuit with four spatial modes, and calculate the corresponding permanent of the submatrix of the unitary matrix. We make use of a data set of probability patterns, that corresponds with the photon number distributions of output states. Then, we change the parameters of the unknown state to build a supervised learning algorithm for estimating the state of a new probability pattern, distinct from the training one.

The rest of the article is organized as follows. In section 2, we briefly review the most important aspects of boson sampling. Sections 3 and 4 introduce our four-mode optical circuit for state estimation of a photonic-mode, and entanglement estimation for a bipartite system, respectively. The results of the ML approach for state estimation and entanglement estimation are shown in section 5, ending up the paper with the conclusions of the work in section 6.

## 2. Boson-sampling model

A boson-sampling experiment consists in measuring the photon number probability produced by the interference of *N* photonic states, usually indistinguishable single-photon states, via an *M*-mode linear network. The distribution can be obtained by computing permanents of the submatrix derived from the unitary transformation matrix of the network [41]. The calculation of the permanent for an *n* × *n* complex matrix is a *#P*-hard task for classical computers and *#P*-complete for a (0, 1)-matrix [42], which means that the simulation of a boson-sampling experiment by classical devices is inefficient.

Without loss of generality, the output state of an *M*-mode optical circuit after the interference of an *N*-photon state can be calculated as follows. First, the input state is given by

**Equation 1.**

$$
\begin{equation}\vert {\psi }_{\text{in}}\rangle =\left\vert {I}_{1},{I}_{2},\dots,{I}_{M}\right\rangle =\left(\prod\limits _{k}\frac{{\hat{a}}_{k}^{{\dagger}{I}_{k}}}{\sqrt{{I}_{k}!}}\right)\left\vert 0\right\rangle,\end{equation} \tag{ 1 }
$$

where ${\hat{a}}_{k}^{{\dagger}}$ is the photon creation operator for the *k* th mode, *I*<sub>*k*</sub> is the number of photons in the *k* th mode, and ∑<sub>*k*</sub> *I*<sub>*k*</sub> = *N*. The input and output states are related by a unitary transformation,

**Equation 2.**

$$
\begin{equation}\left\vert {\psi }_{\text{out}}\right\rangle =\mathbb{U}\left\vert {\psi }_{\text{in}}\right\rangle =\mathbb{U}\left(\prod\limits _{k}\frac{{\hat{a}}_{k}^{{\dagger}{I}_{k}}}{\sqrt{{I}_{k}!}}\right){\mathbb{U}}^{{\dagger}}\mathbb{U}\left\vert 0\right\rangle,\end{equation} \tag{ 2 }
$$

where $\mathbb{U}\left\vert 0\right\rangle =\left\vert 0\right\rangle$ because a linear optical circuit preserves the photon number. Now, the operator transformation reads

**Equation 3.**

$$
\begin{equation}\mathbb{U}{\hat{a}}_{k}^{{\dagger}}{\mathbb{U}}^{{\dagger}}=\sum\limits _{j}\hspace{2pt}{u}_{k,j}\enspace {a}_{j}^{{\dagger}}.\end{equation} \tag{ 3 }
$$

Again, as a linear optical circuit preserves the number of photons, then *u*<sub>*k*, *j*</sub> defines a unitary matrix *U*, which represents a superoperator that acts over the space of the creation operators. Then, the output state reads

**Equation 4.**

$$
\begin{equation}\left\vert {\psi }_{\text{out}}\right\rangle =\left[\prod\limits _{k}\frac{{(U{\hat{a}}_{k}^{{\dagger}})}^{{I}_{k}}}{\sqrt{{I}_{k}!}}\right]\left\vert 0\right\rangle =\sum\limits _{O}\hspace{2pt}{\gamma }_{O}\underset{k}{\bigotimes}\left\vert {O}_{k}\right\rangle =\sum\limits _{O}\hspace{2pt}{\gamma }_{O}\left\vert {\psi }_{\text{O}}\right\rangle,\end{equation} \tag{ 4 }
$$

where *O* is a photon-mode configuration containing *N* photons, *γ*<sub>*O*</sub> is the superposition factor of the configuration *O*, and $\left\vert {O}_{k}\right\rangle$ is the photon number state for the *k* th-output mode in the *O* th configuration. The probability of measuring configuration *O* is given by *P*<sub>*O*</sub> = | *γ*<sub>*O*</sub> |<sup>2</sup>. The probability *P*<sub>*O*</sub> is given by

**Equation 5.**

$$
\begin{equation}{P}_{O}=\frac{{\left\vert \text{Per}[{{\Lambda}}_{\vert {\psi }_{\text{I}}\rangle,\vert {\psi }_{\text{O}}\rangle }]\right\vert }^{2}}{{I}_{1}!\dots {I}_{M}!{O}_{1}!\dots {O}_{M}!},\end{equation} \tag{ 5 }
$$

where Per[⋅] is the permanent and ${{\Lambda}}_{\vert {\psi }_{\text{I}}\rangle,\vert {\psi }_{\text{O}}\rangle }$ is an *N* × *N* matrix, which can be obtained from the elements *u*<sub>*jk*</sub> of that defines *U* [29]. The matrix ${{\Lambda}}_{\vert {\psi }_{\text{I}}\rangle,\vert {\psi }_{\text{O}}\rangle }$ reads

**Equation 6.**

$$
\begin{align}{({{\Lambda}}_{\vert {\psi }_{\text{I}}\rangle,\vert {\psi }_{\text{O}}\rangle })}_{j,k}={U}_{p,q}={u}_{p,q}& \enspace \Longleftrightarrow\enspace {S}_{p-1}^{\text{O}}+1\leqslant j\leqslant {S}_{p}^{\text{O}},\\ & {S}_{q-1}^{\text{I}}+1\leqslant k\leqslant {S}_{q}^{\text{I}},\end{align} \tag{ 6 }
$$

where

**Equation 7.**

$$
\begin{equation}{S}_{\ell }^{\text{O}}=\sum\limits _{i=1}^{\ell }{O}_{i}\quad \wedge \quad {S}_{\ell }^{\text{I}}=\sum\limits _{i=1}^{\ell }{I}_{i}\end{equation} \tag{ 7 }
$$

are the number of output and input photons until mode *ℓ*, respectively, being ${S}_{0}^{\text{I}(\text{O})}=0$. It should be borne in mind that, for any linear network with *M* modes, we have that ${S}_{M}^{\text{I}}={S}_{M}^{\text{O}}=N$. For example, if $\left\vert {\psi }_{\text{I}}\right\rangle =\left\vert {0}_{1}{1}_{2}{0}_{3}{2}_{4}\right\rangle$ and $\left\vert {\psi }_{\text{O}}\right\rangle =\left\vert {1}_{1}{0}_{2}{1}_{3}{1}_{4}\right\rangle$, then ${S}_{1}^{\text{I}}=0$, ${S}_{2}^{\text{I}}=1$, ${S}_{3}^{\text{I}}=1$, and ${S}_{4}^{\text{I}}=3$, while ${S}_{1}^{\text{O}}=1$, ${S}_{2}^{\text{O}}=1$, ${S}_{3}^{\text{O}}=2$, and ${S}_{4}^{\text{O}}=3$. Then, the matrix ${{\Lambda}}_{\vert {\psi }_{\text{I}}\rangle,\vert {\psi }_{\text{O}}\rangle }$ reads

**Equation 8.**

$$
\begin{equation}{{\Lambda}}_{\vert {\psi }_{\text{I}}\rangle,\vert {\psi }_{\text{O}}\rangle }=\left(\begin{matrix}\hfill {U}_{1,2}\hfill & \hfill {U}_{3,2}\hfill & \hfill {U}_{4,2}\hfill \\ \hfill {U}_{1,4}\hfill & \hfill {U}_{3,4}\hfill & \hfill {U}_{4,4}\hfill \\ \hfill {U}_{1,4}\hfill & \hfill {U}_{3,4}\hfill & \hfill {U}_{4,4}\hfill \end{matrix}\right).\end{equation} \tag{ 8 }
$$

## 3. Optical circuit for state tomography

We used a boson-sampling circuit to achieve the full QT of an unknown superposition state in the Fock basis. For obtaining more information of the unknown state, we proposed a simple optical circuit formed by three 50%–50% beam splitters, as shown in figure 1. The unitary matrix *U* for this circuit is given by

**Equation 9.**

$$
\begin{equation}\hat{U}=\left(\begin{matrix}\hfill a\hfill & \hfill -{a}^{2}\hfill & \hfill {a}^{2}\hfill & \hfill 0\hfill \\ \hfill a\hfill & \hfill {a}^{2}\hfill & \hfill -{a}^{2}\hfill & \hfill 0\hfill \\ \hfill 0\hfill & \hfill {a}^{2}\hfill & \hfill {a}^{2}\hfill & \hfill -a\hfill \\ \hfill 0\hfill & \hfill {a}^{2}\hfill & \hfill {a}^{2}\hfill & \hfill a\hfill \end{matrix}\right)\end{equation} \tag{ 9 }
$$

where $a=1/\sqrt{2}$. The input states for the first and the last mode are coherent states given by

**Equation 10.**

$$
\begin{equation}\vert {\alpha }_{j}^{(\theta)}\rangle =\sum\limits _{n}^{\infty }\frac{{\text{e}}^{-\frac{1}{2}\vert \alpha {\vert }^{2}}\enspace {\text{e}}^{\text{i}n\theta }\vert \alpha {\vert }^{n}}{\sqrt{n!}}\vert {n}_{j}\rangle,\end{equation} \tag{ 10 }
$$

with *θ* = 0 for the mode 1 and *θ* = *π*/2 for the mode 4. The initial state for mode 2 is the vacuum state $\left\vert {0}_{2}\right\rangle$, and for the mode 3 it is an arbitrary unknown state $\vert {\eta }_{3}\rangle ={\sum }_{\ell =0}^{N}\hspace{2pt}{r}_{\ell }\enspace {\text{e}}^{\text{i}{\phi }_{\ell }}\vert {n}_{3}\rangle$.

![Figure 1](10.1088_2058-9565_ac3460_assets/qstac3460f1_hr.jpg)

**Figure 1.** Core optical circuit for QT made up of three beam splitters and the initial state $\vert {\psi }_{\text{I}}\rangle =\vert {\psi }_{1}^{(0)}\rangle \vert {0}_{2}\rangle \vert {\eta }_{3}\rangle \vert {\psi }_{4}^{(\pi /2)}\rangle$.

The considered initial state of our optical circuit is given by

**Equation 11.**

$$
\begin{equation}\left\vert {\Psi}\right\rangle =\sum\limits _{m,n=0}^{\infty }\sum\limits _{\ell =0}^{N}{\text{i}}^{n}\frac{{\text{e}}^{-\vert \alpha {\vert }^{2}}\vert \alpha {\vert }^{m+n}}{\sqrt{m!n!}}{r}_{\ell }\enspace {\text{e}}^{\text{i}{\phi }_{\ell }}\left\vert {m}_{1}\right\rangle \left\vert {0}_{2}\right\rangle \left\vert {\ell }_{3}\right\rangle \left\vert {n}_{4}\right\rangle.\end{equation} \tag{ 11 }
$$

This state is a superposition of different four-mode states with different number of photons. For the sake of clarity and simplicity, we rewrite the initial state as

**Equation 12.**

$$
\begin{equation}\left\vert {\Psi}\right\rangle =\sum\limits _{s=0}^{\infty }\vert {\psi }_{s}^{\text{I}}\rangle,\end{equation} \tag{ 12 }
$$

where $\vert {\psi }_{s}^{\text{I}}\rangle$ is a non-normalized state with the superposition of all the four-mode states with *s* photons, which reads

**Equation 13.**

$$
\begin{equation}\vert {\psi }_{s}^{\text{I}}\rangle =\sum\limits _{\ell =0}^{N}\sum\limits _{n=0}^{s-\ell }{\text{i}}^{n}\frac{{\text{e}}^{-\vert \alpha {\vert }^{2}}\vert \alpha {\vert }^{s-\ell }}{\sqrt{(s-\ell -n)!n!}}{r}_{\ell }\enspace {\text{e}}^{\text{i}{\phi }_{\ell }}\times \left\vert {(s-\ell -n)}_{1}\right\rangle \left\vert {0}_{2}\right\rangle \left\vert {\ell }_{3}\right\rangle \left\vert {n}_{4}\right\rangle.\end{equation} \tag{ 13 }
$$

Then, the output state is a superposition of different configurations of how the photons may have arrived to their modes,

**Equation 14.**

$$
\begin{equation}\vert {\psi }_{s}^{\text{O}}\rangle =\sum\limits _{{C}_{s}}\hspace{2pt}{\gamma }_{{C}_{s}}\vert ghk{f\rangle }_{{C}_{s}},\end{equation} \tag{ 14 }
$$

where *C*<sub>*s*</sub> denotes a particular configuration with *s* photons. The probability of measuring a configuration *C*<sub>*s*</sub> is given by

**Equation 15.**

$$
\begin{equation}{P}_{{C}_{s}}={\text{e}}^{-2\vert \alpha {\vert }^{2}}{\left\vert \sum\limits _{\ell =0}^{{N}_{\mathrm{min}}}\sum\limits _{n=0}^{s-\ell }{\text{i}}^{n}\frac{{r}_{\ell }\enspace {\text{e}}^{\text{i}{\phi }_{\ell }}\vert \alpha {\vert }^{s-\ell }\enspace \text{Per}[{{\Lambda}}_{\vert {\psi }_{\text{I}}\rangle,\vert {\psi }_{\text{O}}\rangle }]}{(s-\ell -n)!n!\sqrt{\ell!g!h!k!f!}}\right\vert }^{2},\end{equation} \tag{ 15 }
$$

where *N*<sub>min</sub> = min (*s*, *N*). Next, we will consider particular cases of the maximum number of photons of the state $\left\vert {\eta }_{3}\right\rangle$ (*N* = 1 and *N* = 2), and then we will extend them to an arbitrary superposition of Fock states.

### 3.1. The case N = 1

The unknown state is $\vert {\eta }_{3}\rangle ={r}_{0}\vert 0\rangle +{r}_{1}\enspace {\text{e}}^{\text{i}{\phi }_{1}}\vert 1\rangle$ when *N* = 1. Firstly, for *s* = 0 we have only one possible output ${C}_{0}=\left\vert 0000\right\rangle$ with probability given by equation (15),

**Equation 16.**

$$
\begin{equation}{P}_{{C}_{0}}={\text{e}}^{-2\vert \alpha {\vert }^{2}}{r}_{0}^{2}\end{equation} \tag{ 16 }
$$

where we consider *ϕ*<sub>0</sub> = 0. For *s* = 1 we have four different outputs, ${C}_{1}\in \left\{\left\vert 1000\right\rangle,\left\vert 0100\right\rangle,\left\vert 0010\right\rangle,\left\vert 0001\right\rangle \right\}$, with the general formula to get the probability given by

**Equation 17.**

$$
\begin{equation}{P}_{{C}_{1}}={\text{e}}^{-2\vert \alpha {\vert }^{2}}{\left\vert \vert \alpha \vert {r}_{0}(\text{Per}[{{\Lambda}}_{(\left\vert 1000\right\rangle,\left\vert {C}_{1}\right\rangle)}]+\text{i}\enspace \text{Per}[{\Lambda}[(\left\vert 0001\right\rangle \left\vert {C}_{1}\right\rangle,]))+{r}_{1}\enspace {\text{e}}^{\text{i}{\phi }_{1}}\enspace \text{Per}[{\Lambda}[(\left\vert 0010\right\rangle,\left\vert {C}_{1}\right\rangle)]\right\vert }^{2}.\end{equation} \tag{ 17 }
$$

The probabilities are

**Equation 18.**

$$
\begin{equation}{P}_{\left\vert 1000\right\rangle }=\frac{1}{2}\enspace {\text{e}}^{-2\vert \alpha {\vert }^{2}}\left(\vert \alpha {\vert }^{2}{r}_{0}^{2}+\frac{1}{2}{r}_{1}^{2}+\sqrt{2}\vert \alpha \vert {r}_{0}{r}_{1}\enspace \mathrm{cos}\enspace {\phi }_{1}\right),\end{equation} \tag{ 18 }
$$

**Equation 19.**

$$
\begin{equation}{P}_{\left\vert 0100\right\rangle }=\frac{1}{2}\enspace {\text{e}}^{-2\vert \alpha {\vert }^{2}}\left(\vert \alpha {\vert }^{2}{r}_{0}^{2}+\frac{1}{2}{r}_{1}^{2}-\sqrt{2}\vert \alpha \vert {r}_{0}{r}_{1}\enspace \mathrm{cos}\enspace {\phi }_{1}\right),\end{equation} \tag{ 19 }
$$

**Equation 20.**

$$
\begin{equation}{P}_{\left\vert 0010\right\rangle }=\frac{1}{2}\enspace {\text{e}}^{-2\vert \alpha {\vert }^{2}}\left(\vert \alpha {\vert }^{2}{r}_{0}^{2}+\frac{1}{2}{r}_{1}^{2}-\sqrt{2}\vert \alpha \vert {r}_{0}{r}_{1}\enspace \mathrm{sin}\enspace {\phi }_{1}\right),\end{equation} \tag{ 20 }
$$

**Equation 21.**

$$
\begin{equation}{P}_{\left\vert 0001\right\rangle }=\frac{1}{2}\enspace {\text{e}}^{-2\vert \alpha {\vert }^{2}}\left(\vert \alpha {\vert }^{2}{r}_{0}^{2}+\frac{1}{2}{r}_{1}^{2}+\sqrt{2}\vert \alpha \vert {r}_{0}{r}_{1}\enspace \mathrm{sin}\enspace {\phi }_{1}\right).\end{equation} \tag{ 21 }
$$

Note that the parameters *r*<sub>0</sub>, *r*<sub>1</sub>, and *ϕ*<sub>1</sub> are encoded in the probabilities. Therefore, these parameters can be obtained by calculating the sum or difference of the probability distributions.

### 3.2. The case N = 2

In this case, we consider $\vert {\eta }_{3}\rangle ={r}_{0}\vert 0\rangle +{r}_{1}\enspace {\text{e}}^{\text{i}{\phi }_{1}}\vert 1\rangle +{r}_{2}\enspace {\text{e}}^{\text{i}{\phi }_{2}}\vert 2\rangle$; the probabilities for *s* < 2 are the same as in the previous case. For *s* = 2, we have

**Equation 22.**

$$
\begin{align}{P}_{{C}_{2}}& =\frac{{\text{e}}^{-2\vert \alpha {\vert }^{2}}}{g!h!k!f!}\left[\frac{\vert \alpha {\vert }^{2}{r}_{0}}{2}\left(\text{Per}[{{\Lambda}}_{(\left\vert 2000\right\rangle,\left\vert {C}_{2}\right\rangle)}]-\text{Per}[{{\Lambda}}_{(\left\vert 0002\right\rangle,\left\vert {C}_{2}\right\rangle)}]+2\text{i}\enspace \text{Per}[{{\Lambda}}_{(\left\vert 1001\right\rangle,\left\vert {C}_{2}\right\rangle)}]\right)\right.\\ & \quad {\left.+\vert \alpha \vert {r}_{1}\enspace {\text{e}}^{{\imath}{\phi }_{1}}\left(\text{Per}[{{\Lambda}}_{(\left\vert 1010\right\rangle,\left\vert {C}_{2}\right\rangle)}]+\text{i}\enspace \text{Per}[{{\Lambda}}_{(\left\vert 0011\right\rangle,\left\vert {C}_{2}\right\rangle)}]+\frac{{r}_{2}\enspace {\text{e}}^{{\phi }_{2}}}{\sqrt{2}}\enspace \text{Per}[{{\Lambda}}_{(\left\vert 0020\right\rangle,\left\vert {C}_{2}\right\rangle)}]\right)\right]}^{2}.\end{align} \tag{ 22 }
$$

For *ℓ* = 0 and *g* + *h* = 2 − *n*, the permanent is given by

**Equation 23.**

$$
\begin{equation}\text{Per}[{{\Lambda}}_{\left\vert {(2-n)}_{1}\right\rangle \left\vert {0}_{2}\right\rangle \left\vert {0}_{3}\right\rangle \left\vert {n}_{4}\right\rangle,\vert {C}_{2}\rangle]}={(-1)}^{k}{a}^{2}(2-n)!n!\end{equation} \tag{ 23 }
$$

For *ℓ* ≠ 0, we have the case *g* + *h* − *d* = 2 − *ℓ* − *n* and *k* + *f* − *q* = *n*, where *d* + *q* = *ℓ*. Here, the corresponding permanent reads

**Equation 24.**

$$
\begin{align}\text{Per}[{{\Lambda}}_{\left\vert {(2-\ell -n)}_{1}\right\rangle \left\vert {0}_{2}\right\rangle \left\vert {\ell }_{3}\right\rangle \left\vert {n}_{4}\right\rangle,\vert {C}_{2}\rangle }]& ={B}_{\ell }^{d}\cdot {a}^{2+\ell }\cdot \left[\sum\limits _{x=0}^{d}{B}_{d}^{x}{(-1)}^{x}(2-\ell -n)!\frac{g!}{[g-(d-x)]!}\frac{h!}{(h-x)!}\right]\cdot \\ & \quad \times \left[\sum\limits _{y=0}^{q}{B}_{q}^{y}{(-1)}^{y}n!\frac{f!}{[f-(q-y)]!}\frac{k!}{(k-y)!}\right],\end{align} \tag{ 24 }
$$

where ${B}_{j}^{k}=\frac{j!}{k!(j-k)!}$ is the binomial coefficient. For example, for *ℓ* = 1, $\text{Per}[{{\Lambda}}_{\left\vert 1010\right\rangle,\left\vert 2000\right\rangle }]$ is given by

**Equation 25.**

$$
\begin{equation}\text{Per}[{{\Lambda}}_{\left\vert 1010\right\rangle,\left\vert 2000\right\rangle }]={(-1)}^{k}{a}^{3}(g-h).\end{equation} \tag{ 25 }
$$

When *ℓ* = 2, ${\text{Per}}_{{{\Lambda}}_{\left\vert 0020\right\rangle,\left\vert 1001\right\rangle }}$ can be written as

**Equation 26.**

$$
\begin{equation}\text{Per}[{{\Lambda}}_{\left\vert 0020\right\rangle,\left\vert 1001\right\rangle }]=2\cdot {(-1)}^{k}{a}^{4}\left[(f-k)(g-h)\right].\end{equation} \tag{ 26 }
$$

Then, the probabilities for the configurations $\left\vert 2000\right\rangle$ and $\left\vert 0020\right\rangle$ are given by

**Equation 27.**

$$
\begin{align}{P}_{\left\vert 2000\right\rangle }& =\frac{1}{4}\enspace {\text{e}}^{-2\vert \alpha {\vert }^{2}}\left(\frac{\vert \alpha {\vert }^{4}{r}_{0}^{2}}{2}+\vert \alpha {\vert }^{2}{r}_{1}^{2}+\frac{{r}_{2}^{2}}{4}+\sqrt{2}\vert \alpha {\vert }^{3}{r}_{0}{r}_{1}\enspace \mathrm{cos}({\phi }_{1})\right.\\ & \quad \left.+\frac{\sqrt{2}\vert \alpha {\vert }^{2}{r}_{0}{r}_{2}\enspace \mathrm{cos}({\phi }_{2})}{2}+\vert \alpha \vert {r}_{1}{r}_{2}\enspace \mathrm{cos}({\phi }_{1}-{\phi }_{2})\right),\end{align} \tag{ 27 }
$$

**Equation 28.**

$$
\begin{align}{P}_{\left\vert 0020\right\rangle }& =\frac{1}{4}\enspace {\text{e}}^{-2\vert \alpha {\vert }^{2}}\left(\frac{\vert \alpha {\vert }^{4}{r}_{0}^{2}}{2}+\vert \alpha {\vert }^{2}{r}_{1}^{2}+\frac{{r}_{2}^{2}}{4}+\sqrt{2}\vert \alpha {\vert }^{3}{r}_{0}{r}_{1}\enspace \mathrm{sin}({\phi }_{1})\right.\\ & \quad \left.-\frac{\sqrt{2}\vert \alpha {\vert }^{2}{r}_{0}{r}_{2}\enspace \mathrm{cos}({\phi }_{2})}{2}-\vert \alpha \vert {r}_{1}{r}_{2}\enspace \mathrm{sin}({\phi }_{1}-{\phi }_{2})\right).\end{align} \tag{ 28 }
$$

For the two-photon configuration (*s* = 2), we can code the different phase differences *ϕ*<sub>*j*</sub> − *ϕ*<sub>*k*</sub> and probabilities amplitudes *r*<sub>*j*</sub> for *j*, *k* ∈ {0, 1, 2}.

The same process can be considered for each configuration with a fix number of photons *s*, and we can find that the unknown phases and amplitudes will be encoded in the different probabilities. This will produce more complex mathematical expressions, thus being hard to calculate the analytical expression to recover some information from the unknown state $\left\vert {\eta }_{3}\right\rangle$. Nevertheless, it looks a suitable problem for ML methods, which can learn and recognize patterns from data. It is important to mention that when the reference states are quantum superpositions $(\left\vert 0\right\rangle +{\text{e}}^{\text{i}\theta }\left\vert 1\right\rangle)/\sqrt{2}$ for *θ* = 0 and *θ* = *π*/2, the mathematical form of the output probabilities are simple. In this case, analytical expressions for all the amplitudes and phases may be found in a straightforward manner, reaching full tomography with 100% accuracy.

## 4. Entanglement estimation

Entanglement is one of the most important resources for quantum information. It describes nonlocal correlations between quantum states, and it has become an important tool for understanding the states of many-body systems. For bipartite systems, the entanglement entropy has become a theoretical measure for categorizing such states. For the entanglement coding, we used the optical circuit shown in figure 2, where there is an unknown two-mode input state. We will make use of the von Neumann entropy of a state, which is defined as

**Equation 29.**

$$
\begin{equation}S(\rho)=-\mathrm{Tr}(\rho \enspace \mathrm{ln}\enspace \rho),\end{equation} \tag{ 29 }
$$

where *ρ* is the density operator of the composite system, while Tr(⋅) denotes the trace.

![Figure 2](10.1088_2058-9565_ac3460_assets/qstac3460f2_hr.jpg)

**Figure 2.** Core optical circuit for QT made up of three beam splitters and the initial input state.

For the calculation of the initial state, we suppose that the first and last modes are coherent states given by

**Equation 30.**

$$
\begin{equation}\vert {\alpha }_{j}^{(\theta)}\rangle =\sum\limits _{n=0}^{\infty }\enspace \frac{{\text{e}}^{-\frac{1}{2}\vert \alpha {\vert }^{2}}{\text{e}}^{\text{i}n\theta }\vert \alpha {\vert }^{n}}{\sqrt{n!}}\vert {n}_{j}\rangle,\end{equation} \tag{ 30 }
$$

with *θ* = 0 for the mode 1, *θ* = *π*/2 for the mode 4 as in the previous case, and a bipartite system for the second and third mode, it means a wave function of the following form

**Equation 31.**

$$
\begin{equation}\vert \psi \rangle =\sum\limits _{j,v=0}^{N}{r}_{jv}\enspace {\text{e}}^{\text{i}{\phi }_{jv}}\vert {j}_{2}\rangle \vert {v}_{3}\rangle,\end{equation} \tag{ 31 }
$$

where the parameters *r*<sub>*jv*</sub> and *ϕ*<sub>*jv*</sub> satisfy ${\sum }_{j,v=0}^{N}\hspace{2pt}{r}_{jv}^{2}=1$ and *ϕ*<sub>*jv*</sub> ∈ [0, 2 *π*]. Then, the initial state of our optical circuit is

**Equation 32.**

$$
\begin{equation}\left\vert {\Psi}\right\rangle =\sum\limits _{m,n=0}^{\infty }\sum\limits _{j,v=0}^{N}{\text{i}}^{n}\frac{{\text{e}}^{-\vert \alpha {\vert }^{2}}\vert \alpha {\vert }^{m+n}}{\sqrt{m!n!}}{r}_{jv}\enspace {\text{e}}^{\text{i}{\phi }_{jv}}\left\vert {m}_{1}\right\rangle \left\vert {j}_{2}\right\rangle \left\vert {v}_{3}\right\rangle \left\vert {n}_{4}\right\rangle.\end{equation} \tag{ 32 }
$$

We describe the bipartite system in modes 3 and 4 by the density operator *ρ*<sub>*AB*</sub> = | *ψ*⟩⟨ *ψ*|, and the reduced density matrix of the subsystem *A*(*B*) as *ρ*<sub>*A*</sub> = Tr<sub>*B*</sub>(*ρ*<sub>*AB*</sub>) (*ρ*<sub>*B*</sub> = Tr<sub>*A*</sub>(*ρ*<sub>*AB*</sub>)). ${\mathrm{Tr}}_{\mathcal{S}}$ means tracing over subsystem $\mathcal{S}$. The entanglement *E*(*ρ*<sub>*AB*</sub>) of a bipartite system *ρ*<sub>*AB*</sub> may be defined as the von Neumann entropy of the reduced density matrix of a subsystem,

**Equation 33.**

$$
\begin{equation}E({\rho }_{AB})=S({\rho }_{A})=S({\rho }_{B}).\end{equation} \tag{ 33 }
$$

For simplicity, we rewrite the state given by equation (32) as

**Equation 34.**

$$
\begin{equation}\left\vert {\Psi}\right\rangle =\sum\limits _{s=0}^{\infty }\vert {\psi }_{s}^{\text{I}}\rangle,\end{equation} \tag{ 34 }
$$

where $\vert {\psi }_{s}^{\text{I}}\rangle$ is a non-normalized state of the superposition of all the four-mode states with *s* photons, which reads

**Equation 35.**

$$
\begin{equation}\vert {\psi }_{s}^{\text{I}}\rangle =\sum\limits _{j,v=0}^{N}\sum\limits _{n=0}^{s-j-v}{\text{i}}^{n}\frac{{e}^{-\vert \alpha {\vert }^{2}}\vert \alpha {\vert }^{s-j-v}}{\sqrt{(s-j-v-n)!n!}}{r}_{jv}\enspace {\text{e}}^{\text{i}{\phi }_{jv}}\left\vert {(s-j-v-n)}_{1}\right\rangle \left\vert {j}_{2}\right\rangle \left\vert {v}_{3}\right\rangle \left\vert {n}_{4}\right\rangle.\end{equation} \tag{ 35 }
$$

Then, the output state is a superposition of the different configurations of how photons may have arrived to output modes,

**Equation 36.**

$$
\begin{equation}\vert {\psi }_{s}^{\text{O}}\rangle =\sum\limits _{{C}_{s}}\hspace{2pt}{\gamma }_{{C}_{s}}\vert ghk{f\rangle }_{{C}_{s}},\end{equation} \tag{ 36 }
$$

where *C*<sub>*s*</sub> denotes a particular configuration with *s* photons. The probability of measuring a specific configuration *C*<sub>*s*</sub> reads

**Equation 37.**

$$
\begin{equation}{P}_{{C}_{s}}={\text{e}}^{2\vert \alpha {\vert }^{2}}{\left\vert \sum\limits _{j,v=0}^{N}\sum\limits _{n=0}^{s-j-v}\frac{{i}^{n}\vert \alpha {\vert }^{s-j-v}\enspace {\text{e}}^{\text{i}{\phi }_{jv}}{r}_{jv}\enspace \text{Per}[{{\Lambda}}_{\left\vert {s}^{\ast }jvn\right\rangle,\left\vert ghkf\right\rangle }]}{(s-j-v-n)!n!\sqrt{g!h!k!f!j!v!}}\right\vert }^{2},\end{equation} \tag{ 37 }
$$

where *s** = *s* − *j* − *v* − *n*. Now, each set of probabilities is related to a given degree of entanglement. Then, again via the use of an ML protocol based on training a pattern recognition algorithm, we can estimate this essential feature.

## 5. Machine learning for state characterization

ML was used to find the relation between the patterns and the initial arbitrary state so that the model, once trained, could infer the state of a new pattern not belonging to the training set. In particular, we developed regression models for the values of amplitude and phase, calculating the associated fidelity as figure-of-merit. Due to the sparsity of the data set, support vector regressors (SVRs) were chosen to carry out the regression of amplitudes and phases as our first approach [43, 44]. SVRs are a generalization of support vector machines, which try to solve classification problems by formulating them as convex optimization problems. In this manner, one has to find the suitable hyperplanes that classify correctly as many training samples as possible. In particular, SVRs work by creating a transformed data space in which the problem is more easily solvable and, ideally the problem is transformed into a linear one. That transformation between spaces is carried out by the so-called kernels. Gaussian, linear, and polynomial kernels have been used in this experimentation. An SVR introduces a region in the hyperspace of the problem called -tube, within which, all predictions are considered as correct.

The first three tables show the results of the predictions made by the ML models, evaluating those predictions by means of the fidelity as figure-of-merit. For each data instance, there is a corresponding fidelity value; the tables show the mean value of the fidelities as well as its standard deviation and the quartiles as measures of dispersal. A percentile X% means that in X% of our data samples, fidelities are below the percentile X% value. For example, in table 1, for the Radial basis function (RBF) (Gaussian SVR), 25% of the samples give fidelities below 0.6397; this of course means that 75% of the results give fidelity values above 0.6397. Tables 4 and 5 report the entanglement estimation. The entropy mean value is given for reference purposes to compare its magnitude and its mean absolute error (MAE). We also give the standard deviation of the absolute errors as well as their quartiles and the coefficient of determination (*R*<sup>2</sup>-score) for the models. The coefficient of determination evaluates the quality of the regression, being 1 its best possible value; a constant model that gives the same output value disregarding the input features would have a score of 0.

**Table 1.** Fidelities achieved by SVRs in the *N* = 3 case with three different kernels: RBF (Gaussian), linear, and polynomial. The first column specifies the metrics used to assess the fidelities, namely, the mean value alongside the corresponding standard deviation as dispersal measure, as well as the minimum, maximum and quartile values to give information about the distribution of fidelity measures.

**Table**

|                    | RBF       | Linear    | Polynomial |
| ------------------ | --------- | --------- | ---------- |
| Mean               | 0.742 530 | 0.655 262 | 0.735 201  |
| Standard deviation | 0.215 096 | 0.237 184 | 0.221 150  |
| Minimum            | 0.072 721 | 0.006 989 | 0.063 000  |
| 25%                | 0.639 721 | 0.486 128 | 0.620 836  |
| 50%                | 0.807 703 | 0.699 080 | 0.802 010  |
| 75%                | 0.914 678 | 0.844 586 | 0.926 584  |
| Maximum            | 0.992 325 | 0.983 482 | 0.991 405  |

Starting with the specific results of each experiment, table 1 shows the values of fidelity obtained by SVRs implemented with Gaussian (RBF), linear, and polynomial kernels for the case of *N* = 3. The maximum fidelities are achieved by the Gaussian kernel, that will be hence selected for ulterior analyses. The polynomial kernel obtains slightly lower fidelities than the Gaussian one, whereas the linear kernel shows the poorest modeling capability among the three.

For the sake of comparison with SVRs, we considered a state-of-the-art method, such as extremely randomized trees (ERTs) [45], which build multiple regression trees. Each tree takes a random subset of the input features, while nodes are randomly split for the whole data set (in contrast with the well-known random forest, there is no bootstrap). To reduce the problem dimensionality, we made use of a principal component analysis (PCA) [37]. We set the explained variance ratio at 0.999, so that we could get a good-enough representation of our data that allows for a reliable fidelity modeling while considerably reducing the computational time.

Table 2 shows the fidelity values obtained by SVRs with a Gaussian kernel, for non-PCA and PCA versions of the data sets. The use of PCA seems to have no visible effects on the fidelity performance. In fact, fidelities tend to be slightly higher when using PCA, thus suggesting its suitability for dimensionality reduction. Table 2 also shows that the most reliable fidelities are achieved for *N* = 2, slightly lower values are obtained for *N* = 1, and even lower for *N* = 3.

**Table 2.** Fidelities achieved by SVRs with a Gaussian kernel for the three different data sets: *N* = 1, *N* = 2 and *N* = 3. Results using a preprocessing based on a PCA and not using PCA are compared. The first column specifies the metrics used to assess the fidelities, namely, the mean value alongside the corresponding standard deviation as dispersal measure, as well as minimum, maximum and quartile values to give information about the distribution of fidelity measures.

**Table**

| Without PCA        | *N* = 1  | *N* = 2  | *N* = 3  |
| ------------------ | -------- | -------- | -------- |
| Mean               | 0.823151 | 0.850400 | 0.742530 |
| Standard deviation | 0.190404 | 0.204878 | 0.215096 |
| Minimum            | 0.054745 | 0.105860 | 0.072721 |
| 25%                | 0.740702 | 0.787348 | 0.639721 |
| 50%                | 0.881910 | 0.950054 | 0.807703 |
| 75%                | 0.970362 | 0.983219 | 0.914678 |
| Maximum            | 0.999827 | 0.998861 | 0.992325 |

**Table**

| With PCA           | *N* = 1   | *N* = 2   | *N* = 3   |
| ------------------ | --------- | --------- | --------- |
| Mean               | 0.816 223 | 0.867 969 | 0.743 020 |
| Standard deviation | 0.221 873 | 0.200 754 | 0.212 160 |
| Minimum            | 0.058 625 | 0.127 300 | 0.135 495 |
| 25%                | 0.734 036 | 0.811 426 | 0.636 835 |
| 50%                | 0.908 766 | 0.963 327 | 0.783 768 |
| 75%                | 0.986 301 | 0.991 305 | 0.912 941 |
| Maximum            | 0.999 982 | 0.998 994 | 0.998 755 |

Table 3 includes the values of fidelity obtained by ERTs for both non-PCA and PCA versions of the data sets. As in the case of SVRs, the use of PCA does not affect the performances in a great extent. In particular, the use of PCA provides slightly better results for *N* = 2 and *N* = 3, while for *N* = 1 the use of the original data without PCA yields higher values of fidelity. The comparison of tables 2 and 3 show that the ERTs carry out a better regression than SVRs for *N* = 2 and *N* = 3, being an SVR approach better for *N* = 1. This might likely be due to the fact that *N* = 1 corresponds to a more sparse data set, where the SVR is a more adequate and natural solution. Furthermore, that data set may not contain enough variability to exploit ERT capabilities. In summary, the use of SVRs is suggested for *N* = 1 and ERTs for any *N* > 1. Furthermore, as PCA does not have a relevant impact on performance, tends to lead to higher fidelities, and allows a reduction of the computational times, its use to reduce the dimensionality of the data sets is encouraged.

**Table 3.** Fidelities achieved by ERTs for the three different data sets: *N* = 1, *N* = 2 and *N* = 3. Results using a preprocessing based on a PCA and not using PCA are compared. The first column specifies the metrics used to assess the fidelities, namely, the mean value alongside the corresponding standard deviation as dispersal measure, as well as minimum, maximum and quartile values to give information about the distribution of fidelity measures.

**Table**

| Without PCA        | *N* = 1  | *N* = 2  | *N* = 3  |
| ------------------ | -------- | -------- | -------- |
| Mean               | 0.719850 | 0.900017 | 0.761558 |
| Standard deviation | 0.227072 | 0.191405 | 0.206226 |
| Minimum            | 0.069204 | 0.138863 | 0.090518 |
| 25%                | 0.557748 | 0.934672 | 0.671530 |
| 50%                | 0.751323 | 0.987036 | 0.813736 |
| 75%                | 0.916520 | 0.994959 | 0.928541 |
| Maximum            | 0.999996 | 0.999894 | 0.988078 |

**Table**

| With PCA           | *N* = 1   | *N* = 2   | *N* = 3   |
| ------------------ | --------- | --------- | --------- |
| Mean               | 0.664 226 | 0.922 877 | 0.787 241 |
| Standard deviation | 0.250 087 | 0.157 877 | 0.189 888 |
| Minimum            | 0.066 888 | 0.050 081 | 0.116 078 |
| 25%                | 0.467 351 | 0.947 035 | 0.702 872 |
| 50%                | 0.703 973 | 0.981 661 | 0.852 074 |
| 75%                | 0.892 137 | 0.992 386 | 0.936 313 |
| Maximum            | 0.999 233 | 0.999 749 | 0.994 355 |

Results about entanglement estimation via the corresponding entropy are shown in tables 4 and 5. The performance of SVRs and ERTs are compared via the MAE and *R*<sup>2</sup> scores for different data sets. ERTs outperform SVRs in all cases except for *N* = 1, when there is no PCA preprocessing again very likely due to sparsity. This conjecture is reinforced by the fact that after using PCA, hence reducing sparsity, SVRs are not better regressors than ERTs, even for *N* = 1. As in the estimation of fidelities, PCA does not have a relevant impact on performance. In fact, its use tends to lead to slightly better performances (higher *R*<sup>2</sup>-scores and lower MAEs) whilst allowing a reduction of the computational times. Therefore, its use to reduce the dimensionality of the data sets is encouraged. We may infer that, for entanglement estimation, ERTs represent a more adequate choice than SVRs.

**Table 4.** SVRs with Gaussian kernel: entanglement estimation (by entropy) performance for 200 test samples and the three different data sets: *N* = 1, *N* = 2 and *N* = 3. Results using a preprocessing based on a PCA and not using PCA are compared. The first column specifies the mean values of entropy (as a reference for the committed errors) and the metrics used to evaluate the performance. Namely, MAE with its corresponding standard deviation, as well as the minimum, quartile and maximum values, and also *R*<sup>2</sup>-scores.

**Table**

| Without PCA           | *N* = 1   | *N* = 2   | *N* = 3   |
| --------------------- | --------- | --------- | --------- |
| Entropy mean value    | 0.297 344 | 0.297 822 | 0.159 738 |
| MAE                   | 0.082 243 | 0.142 873 | 0.118 600 |
| Standard deviation    | 0.067 844 | 0.147 551 | 0.121 629 |
| Minimum               | 0.000 213 | 0.000 861 | 0.000 331 |
| 25%                   | 0.034 487 | 0.065 343 | 0.074 025 |
| 50%                   | 0.072 087 | 0.093 323 | 0.096 292 |
| 75%                   | 0.104 777 | 0.161 541 | 0.115 779 |
| Maximum               | 0.436 492 | 0.934 630 | 1.082 693 |
| *R*<sup>2</sup>-score | 0.818 407 | 0.600 526 | 0.507 575 |

**Table**

| With PCA              | *N* = 1   | *N* = 2   | *N* = 3   |
| --------------------- | --------- | --------- | --------- |
| Entropy mean value    | 0.297 344 | 0.297 822 | 0.159 738 |
| MAE                   | 0.085 969 | 0.132 719 | 0.113 547 |
| Standard deviation    | 0.071 639 | 0.123 191 | 0.122 406 |
| Minimum               | 0.000 968 | 0.003 429 | 0.002 213 |
| 25%                   | 0.038 139 | 0.063 135 | 0.060 838 |
| 50%                   | 0.070 745 | 0.095 576 | 0.093 087 |
| 75%                   | 0.112 728 | 0.147 261 | 0.113 246 |
| Maximum               | 0.518 710 | 0.654 891 | 1.169 980 |
| *R*<sup>2</sup>-score | 0.800 968 | 0.689 208 | 0.522 331 |

**Table 5.** ERTs: entanglement estimation (by entropy) performance for 200 test samples and the three different data sets: *N* = 1, *N* = 2 and *N* = 3. Results using a preprocessing based on a PCA and not using PCA are compared. The first column specifies the mean values of entropy (as a reference for the committed errors) and the metrics used to evaluate the performance. Namely, MAE with its corresponding standard deviation, as well as the minimum, quartile and maximum values, and also *R*<sup>2</sup>-scores.

**Table**

| Without PCA           | *N* = 1   | *N* = 2   | *N* = 3   |
| --------------------- | --------- | --------- | --------- |
| Real mean             | 0.297 344 | 0.297 822 | 0.159 738 |
| MAE                   | 0.081 303 | 0.131 039 | 0.084 841 |
| Standard deviation    | 0.078 961 | 0.143 680 | 0.108 290 |
| Minimum               | 0.000 018 | 0.000 094 | 0.000 005 |
| 25%                   | 0.018 078 | 0.019 206 | 0.012 170 |
| 50%                   | 0.054 899 | 0.082 159 | 0.042 033 |
| 75%                   | 0.130 161 | 0.191 042 | 0.117 126 |
| Maximum               | 0.408 034 | 0.704 982 | 0.573 232 |
| *R*<sup>2</sup>-score | 0.766 088 | 0.627 655 | 0.664 271 |

**Table**

| With PCA              | *N* = 1   | *N* = 2   | *N* = 3   |
| --------------------- | --------- | --------- | --------- |
| Real mean             | 0.297 344 | 0.297 822 | 0.159 738 |
| MAE                   | 0.073 482 | 0.094 449 | 0.060 760 |
| Standard deviation    | 0.073 704 | 0.110 135 | 0.103 725 |
| Minimum               | 0.000 082 | 0.000 058 | 0.000 004 |
| 25%                   | 0.018 621 | 0.010 909 | 0.007 419 |
| 50%                   | 0.047 475 | 0.050 592 | 0.026 540 |
| 75%                   | 0.100 847 | 0.138 207 | 0.075 164 |
| Maximum               | 0.386 189 | 0.484 120 | 0.971 228 |
| *R*<sup>2</sup>-score | 0.822 516 | 0.770 742 | 0.752 039 |

## 6. Conclusion

We have proposed a state characterization via a pattern recognition algorithm in ML for photonics. It is based on the estimation of quantum features by using the output photon number distribution in a photonic circuit, similar to boson-sampling protocols for continuous variables. We have focused on the estimation of single-mode phases and amplitudes and, also, on the two-mode entanglement estimation.

SVRs and ERTs have been used to extrapolate the estimation for states not present in the training set, i.e. new probability patterns. The obtained fidelities hint that ML estimations are reliable and can be used to boost the proposed QT protocol. In particular, the use of ERTs with previous PCA preprocessing seems to be a suitable approach for setups with *N* > 1.

The same two ML approaches were employed for entanglement estimation through modeling the von Neumann entropy, yielding *R*<sup>2</sup> scores higher than 0.75, thus suggesting the appropriateness of ML for this relevant task. In this case, the use of ERTs with a previous PCA preprocessing turns out to be the most adequate choice for all cases.

The proposed photonic circuit with four modes and three beam splitters is experimentally accessible. It means that by using a bigger circuit, with more output probabilities for the number of photons, ML algorithms will likely increase its performance, since the patterns will be more complex and will encode more information. Nevertheless, the numerical generation of the data will be a hard task due to the complexity of the problem. Also, the generation of experimental data for the training set is a demanding task due to the difficulties to characterize a quantum state. In any case, it is a useful technique even if we use simple photonic circuits or historical data produced by current photonic experiments for more complex setups. Finally, this work shows that ML techniques can be suitably used for state characterization without the burden of full tomography, paving the way for more sophisticated tools that may help for fast estimation of quantum features.

## Data availability statement

The data that support the findings of this study are available upon reasonable request from the authors.

## References (44 total, showing 44)

1. Montanaro A 2016 Quantum algorithms: an overview npj Quantum Inf. 2 15023 doi:10.1038/npjqi.2015.23
2. Roffe J 2019 Quantum error correction: an introductory guide Contemp. Phys. 60 226 doi:10.1080/00107514.2019.1667078
3. Scarani V, Bechmann-Pasquinucci H, Cerf N J, Dušek M, Lütkenhaus N, Peev M 2009 The security of practical quantum key distribution Rev. Mod. Phys. 81 1301 doi:10.1103/revmodphys.81.1301
4. Pirandola S, Eisert J, Weedbrook C, Furusawa A, Braunstein S L 2015 Advances in quantum teleportation Nat. Photon. 9 641 doi:10.1038/nphoton.2015.154
5. Bravyi S, Gosset D, König R, Tomamichel M 2020 Quantum advantage with noisy shallow circuits Nat. Phys. 16 1040 doi:10.1038/s41567-020-0948-z
6. Arute F, others 2019 Quantum supremacy using a programmable superconducting processor Nature 574 505 doi:10.1038/s41586-019-1666-5
7. Zhong H-S, others 2020 Quantum computational advantage using photons Science 370 1460 doi:10.1126/science.abe8770
8. Yin J, others 2020 Entanglement-based secure quantum cryptography over 1120 kilometres Nature 582 501 doi:10.1038/s41586-020-2401-y
9. Wu Y, others 2021 Strong quantum computational advantage using a superconducting quantum processor
10. Hradil Z 1997 Quantum-state estimation Phys. Rev. A 55 R1561(R) doi:10.1103/physreva.55.r1561
11. D’Ariano G M, Lo Presti P 2001 Quantum tomography for measuring experimentally the matrix elements of an arbitrary quantum operation Phys. Rev. Lett. 86 4195 doi:10.1103/PhysRevLett.86.4195
12. Adamson R B A, Steinberg A M 2010 Improving quantum state estimation with mutually unbiased Phys. Rev. Lett. 105 030406 doi:10.1103/physrevlett.105.030406
13. Tiunov E S, Tiunova V V, Ulanov A E, Lvovsky A I, Fedorov A K 2020 Experimental quantum homodyne tomography via machine learning Optica 7 448 doi:10.1364/optica.389482
14. Palmieri A M, Kovlakov E, Bianchi F, Yudin D, Straupe S, Biamonte J D, Kulik S 2020 Experimental neural network enhanced quantum tomography npj Quantum Inf. 6 20 doi:10.1038/s41534-020-0248-6
15. Torlai G, Mazzola G, Carrasquilla J, Troyer M, Melko R, Carleo G 2018 Neural-network quantum state tomography Nat. Phys. 14 447 doi:10.1038/s41567-018-0048-5
16. Lohani S, Kirby B T, Brodsky M, Danaci O, Glasser R T 2020 Machine learning assisted quantum state estimation Mach. Learn.: Sci. Technol. 1 035007 doi:10.1088/2632-2153/ab9a21
17. Albarrán-Arriagada F, Retamal J C, Solano E, Lamata L 2018 Measurement-based adaptation protocol with quantum reinforcement learning Phys. Rev. A 98 042315 doi:10.1103/physreva.98.042315
18. Yu S, others 2019 Reconstruction of a photonic qubit state with reinforcement learning Adv. Quantum Technol. 2 1800074 doi:10.1002/qute.201800074
19. Flamini F, Spagnolo N, Sciarrino F 2018 Photonic quantum information processing: a review Rep. Prog. Phys. 82 016001 doi:10.1088/1361-6633/aad5b2
20. Yao N Y, Jiang L, Gorshkov A V, Maurer P C, Giedke G, Cirac J I, Lukin M D 2012 Scalable architecture for a room temperature solid-state quantum information processor Nat. Commun. 3 800 doi:10.1038/ncomms1788
21. Bruzewicz C D, Chiaverini J, McConnell R, Sage J M 2019 Trapped-ion quantum computing: progress and challenges Appl. Phys. Rev. 6 021314 doi:10.1063/1.5088164
22. Eltony A M, Gangloff D, Shi M, Bylinskii A, Vuletić V, Chuang I L 2016 Technologies for trapped-ion quantum information systems Quantum Inf. Process. 15 5351 doi:10.1007/s11128-016-1298-8
23. Devoret M H, Schoelkopf R J 2013 Superconducting circuits for quantum information: an outlook Science 339 1169 doi:10.1126/science.1231930
24. Wendin G 2017 Quantum information processing with superconducting circuits: a review Rep. Prog. Phys. 80 106001 doi:10.1088/1361-6633/aa7e1a
25. Liao S-K, others 2017 Satellite-to-ground quantum key distribution Nature 549 43 doi:10.1038/nature23655
26. Ren J-G, others 2017 Ground-to-satellite quantum teleportation Nature 549 70 doi:10.1038/nature23675
27. Chen Y-A, others 2021 An integrated space-to-ground quantum communication network over 4600 kilometres Nature 589 214 doi:10.1038/s41586-020-03093-8
28. Aaronson Scott, Arkhipov A 2011 The computational complexity of linear optics Proceedings of the forty-third annual ACM symposium on Theory of computing 333-342 doi:10.1145/1993636.1993682
29. Gard B T, Motes K R, Olson J P, Rohde P P, Dowling J P 2015 An introduction to boson-sampling
30. Broome M A, Fedrizzi A, Rahimi-Keshari S, Dove J, Aaronson S, Ralph T C, White A G 2013 Photonic boson sampling in a tunable circuit Science 339 794 doi:10.1126/science.1231440
32. Bentivegna M, others 2015 Experimental scattershot boson sampling Sci. Adv. 1 e1400255 doi:10.1126/sciadv.1400255
33. Spagnolo N, others 2014 Experimental validation of photonic boson sampling Nat. Photon. 8 615 doi:10.1038/nphoton.2014.135
34. Wang H, others 2019 Boson sampling with 20 input photons and a 60-mode interferometer in a 1014-dimensional Hilbert space Phys. Rev. Lett. 123 250503 doi:10.1103/physrevlett.123.250503
35. Zhou W-H, others 2020 Timestamp boson sampling
36. Gao J, others 2020 Quantum advantage with timestamp membosonsampling
37. Alpaydin E 2010 Introduction to Machine Learning MIT Press
38. Shalev-Shwartz S, Ben-David S 2014 Understanding Machine Learning: From Theory to Algorithms Cambridge University Press
39. Mathur P 2019 Machine Learning Applications Using Python: Cases Studies from Healthcare, Retail and Finance Apress
40. Olivas-Soria E, Martín-Guerrero J D, Marcelino M S 2009 Handbook of Research on Machine Learning Applications and Trends: Algorithms, Methods, and Techniques IGI Global
41. Scheel S 2004 Permanents in linear optical networks
42. Valiant L G 1979 The complexity of computing the permanent Theor. Comput. Sci. 8 189 doi:10.1016/0304-3975(79)90044-6
43. Schölkopf B, Smola A J 2018 Learning with Kernels: Support Vector Machines, Regularization, Optimization, and Beyond MIT Press
44. Alvarez-Rodriguez U, Lamata L, Escandell-Montero P, Martín-Guerrero J D, Solano E 2017 Supervised quantum learning without measurements Sci. Rep. 7 13645 doi:10.1038/s41598-017-13378-0
45. Geurts P, Ernst D, Wehenkel L 2006 Extremely randomized trees Mach. Learn. 63 3-42 doi:10.1007/s10994-006-6226-1
