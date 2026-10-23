---
title: "From Baby Universes to Narain Moduli: Topological Boundary Averaging in SymTFTs"
authors: "Xingyang Yu"
journal: "arXiv"
doi: "10.48550/arxiv.2605.06653v1"
published: "2026-05-07"
source: "arxiv_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 35555
---

# From Baby Universes to Narain Moduli: Topological Boundary Averaging in SymTFTs

## Abstract

We propose a SymTFT interpretation of ensemble averaging in low-dimensional holography. The central operation is to keep fixed both the SymTFT and the physical boundary condition, while averaging over topological boundary conditions at the other end of the SymTFT slab. Each such boundary condition gives an absolute completion of the same relative theory, so the ensemble is interpreted as an average over topological completions rather than over arbitrary local dynamics. We formulate this construction in terms of cap functionals and their natural groupoid or Haar-type measures, and illustrate it in two examples. In the closed-string sector of the Marolf–Maxfield model, topological boundary conditions are labelled by finite sets, and the groupoid sum reproduces the Poisson/Bell-polynomial moments. In the Narain case, compact topological boundary conditions of an $\mathbb{R}$-valued BF SymTFT are identified with maximal isotropic subgroups, so that topological-boundary averaging becomes the usual Narain moduli average with Zamolodchikov measure. We also discuss possible extensions to JT gravity, random matrix theory, Virasoro T(Q)FT, and 3D gravity.

## 1 Introduction

A striking lesson from recent developments in low-dimensional holography is that a gravitational path integral need not compute the partition function of a single boundary theory. When the bulk sum includes Euclidean wormholes connecting several asymptotic boundaries, the result generally fails to factorize:

$$
\begin{aligned}
\big\langle Z[J_{1}]Z[J_{2}]\big\rangle\neq\big\langle Z[J_{1}]\big\rangle\big\langle Z[J_{2}]\big\rangle.
\end{aligned}\tag{1.1}
$$

A natural interpretation is that the gravitational path integral computes moments in an ensemble averaged boundary theories. This idea appears concretely in JT gravity and its relation to double-scaled random matrix theory, in baby-universe models of spacetime wormholes, and in 3D examples where sums over bulk topologies reproduce averages over families of 2D CFTs \[1903.11115, 1907.03363, 2002.08950, 2006.04855, 2006.04839, 2405.20366\]. These examples suggest that ensemble averaging is not merely a technical device, but may be an intrinsic feature of certain gravitational path integrals<sup>1</sup>.

A second, largely independent, development is the modern understanding of generalized global symmetries \[1412.5148\]. A D-dimensional QFT with generalized symmetry can often be viewed as a boundary condition for a (D+1)-dimensional topological theory, the Symmetry TFT or SymTFT \[1212.1692, 2212.00195\]<sup>2</sup>. In this formulation the boundary QFT is a relative theory \[1212.1692\]: its partition function is not a number, but a vector in the Hilbert space of the SymTFT. To obtain an ordinary absolute QFT, one must choose a topological boundary condition at the other end of the SymTFT slab. Different topological boundary conditions correspond to different global forms, gaugings, or more generally different topological completions of the same relative theory.

The purpose of this paper is to connect these two ideas. We propose that, in a class of low-dimensional ensemble holography examples, the ensemble average can be understood as an average over topological boundary conditions of a fixed SymTFT. The basic setup is as follows. We fix a SymTFT $\mathfrak{T}_{\mathrm{sym}}$ and a physical boundary condition $B_{\mathrm{phys}}(J)$, depending on metric and source data $J$. This physical boundary prepares a state

$$
\begin{aligned}
\big|\Psi_{\mathrm{phys}}(M;J)\big\rangle\in\mathcal{H}_{\mathrm{sym}}(M)
\end{aligned}\tag{1.2}
$$

on a closed $d$-manifold $M$. A topological boundary condition $L$ at the other end of the slab defines a cap functional

$$
\begin{aligned}
\big\langle L;M\big|\in\mathcal{H}_{\mathrm{sym}}(M)^{*}.
\end{aligned}\tag{1.3}
$$

The absolute partition function obtained by choosing the cap $L$ is then

$$
\begin{aligned}
Z_{L}(M;J)=\big\langle L;M\,\big|\,\Psi_{\mathrm{phys}}(M;J)\big\rangle.
\end{aligned}\tag{1.4}
$$

The ensemble average considered in this paper is obtained by varying $L$, while keeping both the SymTFT and the physical boundary fixed:

$$
\begin{aligned}
\big\langle Z(M;J)\big\rangle_{\mathrm{top}}=\int_{\mathcal{L}_{\mathrm{top}}}d\mu(L)\,\big\langle L;M\,\big|\,\Psi_{\mathrm{phys}}(M;J)\big\rangle.
\end{aligned}\tag{1.5}
$$

For a finite family of topological boundaries, the integral is replaced by a groupoid sum, with the usual factor $1/|\operatorname{Aut}(L)|$. For a continuous family, the measure is a Haar-type measure on the corresponding space of Lagrangian boundary data.

This construction should be distinguished from averaging over arbitrary boundary conditions. A general boundary condition at the second end of the slab would usually carry its own local degrees of freedom, its own dependence on metric or coupling data, and its own Hamiltonian. Such an average would be an average over local dynamics. By contrast, the topological boundary conditions considered here carry zero Hamiltonian. They do not change the physical time evolution supplied by $B_{\mathrm{phys}}(J)$. Instead, they specify the Hilbert space, charge lattice, global form, or other topological completion on which the fixed physical Hamiltonian acts. This is the sense in which our ensemble average is an average over topological completions of a fixed relative theory.

This viewpoint also gives a clean relation to summing over topologies. In a functorial TFT, a bordism $Y:M\to\emptyset$ defines a linear functional on $\mathcal{H}_{\mathrm{sym}}(M)$. Thus a sum over fillings of $M$ becomes, after applying the TFT functor, a sum over cap functionals. A topological boundary condition also defines such a cap. Therefore, whenever the topology sum is only sensitive to the induced topological cap data, it can be reorganized as a sum over topological boundary conditions. This is the mechanism we isolate and study in this paper.

There are several operations in the literature that are all called ensemble averaging. One may average over a moduli space of absolute theories, as in Narain averaging \[2006.04855, 2006.04839\]; one may sum over modular images of a seed boundary partition function, as in Poincaré-series constructions of 3D gravity \[0712.0155, 1407.6008\]; or one may average over topological boundary conditions, maximal gaugings, or Lagrangian algebras of a fixed TFT \[2201.00903, 2310.13044, 2405.20366, 2511.04311\]. These operations are not identical in general. One of the main points of this paper is that, in the examples studied below, the SymTFT formulation identifies the relevant averaging variable with topological boundary data. The moduli being averaged over are reinterpreted as topological completions, and the canonical measure on moduli space is reproduced as the natural groupoid or Haar measure on the space of caps.

Our first example is the closed-string sector of the Marolf–Maxfield topological model \[2002.08950, 2201.00903\]. The baby-universe analysis of this model gives moments of a Poisson random variable. We reproduce these moments from a fixed discrete SymTFT-like parent object $\mathfrak{S}_{\mathrm{Fin}}$, whose simple topological boundary conditions are labelled by finite sets. After choosing a finite set $S$, the corresponding absolute closed 2D TFT has Frobenius algebra

$$
\begin{aligned}
A_{S}=\operatorname{Fun}(S,\mathbb{C}).
\end{aligned}\tag{1.6}
$$

The physical boundary is represented by the unit $1_{S}$, while the topological cap is represented by the Frobenius counit. Their pairing gives

$$
\begin{aligned}
Z_{S}(S^{1})=|S|.
\end{aligned}\tag{1.7}
$$

Averaging over finite sets up to bijection, with groupoid weight $1/|\operatorname{Aut}(S)|$ and fugacity $\lambda^{|S|}$, gives

$$
\begin{aligned}
\big\langle Z^{n}\big\rangle_{\mathrm{top}}=e^{-\lambda}\sum_{d=0}^{\infty}\frac{\lambda^{d}}{d!}\,d^{n}=B_{n}(\lambda),
\end{aligned}\tag{1.8}
$$

the Bell-polynomial moments of the Marolf–Maxfield ensemble. At fixed $S$ the theory factorizes, while the non-factorization is produced entirely by the average over finite-set topological caps.

Our second example is the Narain ensemble \[2006.04855, 2006.04839\]. We describe the $c$-dimensional (target space dimension) compact boson using a 3D $\mathbb{R}$-valued BF SymTFT. The physical boundary condition supplies the left- and right-moving current algebra, the oscillator descendants, and the conformal Hamiltonian. The compact topological boundary condition supplies the even self-dual charge lattice, and hence the current-algebra primary spectrum. For $c>1$, the compact component of the space of topological boundary conditions is

$$
\begin{aligned}
\mathcal{L}_{\mathrm{Narain}}^{(c)}=O(c,c;\mathbb{Z})\backslash O(c,c;\mathbb{R})/\bigl(O(c)\times O(c)\bigr),
\end{aligned}\tag{1.9}
$$

which is precisely the Narain moduli space. The Haar-induced measure on this space is the usual Narain, or Zamolodchikov \[Zamolodchikov:1986gt\], measure. For $c>2$, the Siegel–Weil formula then gives

$$
\begin{aligned}
\big\langle Z(\tau)\big\rangle_{\mathrm{top}}^{(c)}=\frac{E_{c/2}(\tau)}{\tau_{2}^{c/2}|\eta(\tau)|^{2c}},
\end{aligned}\tag{1.10}
$$

reproducing the standard genus-one Narain average. The $c=1$ compact boson is useful as a warm-up example: it makes the radius dictionary transparent and also illustrates the infinite-volume subtlety of rank-one Narain averaging.

The conceptual lesson of these examples is simple. In the Marolf–Maxfield model, the topological completion is a finite set. In the Narain ensemble, it is an maximal isotropic subgroup of the defect group. In both cases, the local physical boundary dynamics is held fixed, while the topological boundary condition specifies the absolute theory. The ensemble average is therefore not an average over arbitrary dynamics, but an average over admissible topological completions.

We also discuss two speculative directions.. JT gravity admits a BF-theory formulation \[1812.00918, 1905.02726\], and its relation to random matrix theory suggests that the random matrix ensemble may be understood as an average over topological completions of a fixed relative one-dimensional quantum mechanics. Similarly, recent work on Virasoro TQFT \[2304.13650, 2401.13900\] suggests a possible SymTFT framework for pure $\mathrm{AdS}_{3}$ gravity, in which a doubled Virasoro TQFT would play the role of the parent topological theory and the ensemble of 2D CFT data would arise from averaging over suitable Virasoro topological boundary conditions. These directions are not developed into complete constructions here, but they suggest that topological-boundary averaging may provide a useful organizing principle for ensemble holography beyond the two examples explicitly analyzed in this paper.

Before presenting the organization of the paper, let us briefly mention some closely related literature. SymTFTs and topological holography have already appeared in discussions of gravitational path integrals. In the Liouville/Virasoro direction, higher-dimensional topological data and Virasoro T(Q)FT have been used to reconstruct CFT path integrals and to formulate aspects of non-perturbative $\mathrm{AdS}_{3}/\mathrm{CFT}_{2}$ gravity \[2210.12127, 2311.18005, 2403.03179, 2412.12045, 2504.21660\]. In particular, recent work relates fixed-topology $\mathrm{AdS}_{3}$ gravity amplitudes to Virasoro T(Q)FT amplitude-squared and to Conformal Turaev–Viro theory \[2507.12696\]. In a complementary TQFT-gravity direction, ensembles of boundary CFTs have been related to sums over maximal gaugings, or equivalently to sums over topological boundary conditions described by Lagrangian algebras \[2310.13044, 2405.20366, 2511.04311\]. Our work is closer in spirit to this second perspective, but provides a general prescription from a more TFT perspective which works nicely beyond finite RCFT cases. This distinction is transparent from examples we considered: the Marolf–Maxfield model involves a countably *infinite* groupoid of finite-set caps, and the Narain example is governed by an $\mathbb{R}$-valued BF SymTFT whose compact topological boundaries sweep out the full Narain moduli space, including generic *irrational* points.

The paper is organized as follows. In Section [2](https://arxiv.org/html/2605.06653v1#S2) we formulate the general construction of averaging over topological boundary conditions, including the finite groupoid measure and its continuous Haar-measure analogue. In Section [3](https://arxiv.org/html/2605.06653v1#S3) we apply this framework to the closed-string sector of the Marolf–Maxfield model and reproduce the Poisson/Bell-polynomial moments. In Section [4](https://arxiv.org/html/2605.06653v1#S4) we study the compact boson and higher-rank Narain theories using $\mathbb{R}$-valued BF SymTFTs, and show that Narain moduli averaging is topological-boundary averaging. Section [5](https://arxiv.org/html/2605.06653v1#S5) discusses possible extensions to JT gravity, random matrix theory, Virasoro TQFT, and 3D gravity.

## 2 Averaging over Topological Boundary Conditions as Summing over Topologies

In this section we formulate the basic operation that will be used throughout the paper. The point is simple. In a functorial topological field theory, a bordism from a manifold $M$ to the empty set defines a linear functional on the Hilbert space assigned to $M$. Thus, after applying the TFT functor, a sum over fillings of $M$ becomes a sum over cap functionals. In a SymTFT, there is a distinguished class of such caps: those produced by topological boundary conditions. We will use this observation to define a SymTFT-controlled version of ensemble averaging.

The discussion in this section is not meant to define the most general holographic ensemble. Instead, we are just isolating a more restrictive construction. We keep fixed a relative theory, namely a fixed SymTFT together with a fixed physical boundary condition, and we vary only the topological boundary condition used to cap the SymTFT slab. The resulting average is an average over topological completions of a fixed relative theory.

### 2.1 Caps and topological boundary conditions

We start with a simple observation. In a $(d+1)$-dimensional topological field theory, a filling of a $d$-manifold $M$ is not merely seen as a geometry by itself, but as a linear functional on the state space associated to $M$ \[Atiyah:1989vu\]. Let $\mathfrak{T}$ be a $(d+1)$-dimensional TFT. It assigns to a closed $d$-manifold $M$ a vector space

$$
\begin{aligned}
\mathcal{H}_{\mathfrak{T}}(M).
\end{aligned}\tag{2.1}
$$

A bordism

$$
\begin{aligned}
Y:M\longrightarrow\emptyset
\end{aligned}\tag{2.2}
$$

defines a map

$$
\begin{aligned}
Z_{\mathfrak{T}}(Y):\mathcal{H}_{\mathfrak{T}}(M)\longrightarrow\mathcal{H}_{\mathfrak{T}}(\emptyset)\cong\mathbb{C}.
\end{aligned}\tag{2.3}
$$

Thus $Y$ defines an element of the dual space,

$$
\begin{aligned}
Z_{\mathfrak{T}}(Y)\in\mathcal{H}_{\mathfrak{T}}(M)^{*}.
\end{aligned}\tag{2.4}
$$

In this sense, a bordism from $M$ to the empty set is a cap.

A sum over bordisms with fixed boundary $M$ therefore gives a distinguished element of $\mathcal{H}_{\mathfrak{T}}(M)^{*}$:

$$
\begin{aligned}
\mathcal{C}_{\mathrm{bord}}(M)=\sum_{[Y:M\to\emptyset]}w(Y)\,Z_{\mathfrak{T}}(Y)\in\mathcal{H}_{\mathfrak{T}}(M)^{*}.
\end{aligned}\tag{2.5}
$$

The coefficient $w(Y)$ denotes whatever weight the theory assigns to the bordism $Y$. At this stage we will not specify it. In an ordinary gravitational path integral it would come from the action and the path-integral measure. In a purely topological or finite groupoid version it includes the usual symmetry factors. The point of [(2.5)](https://arxiv.org/html/2605.06653v1#S2.E5) is not the precise choice of weight, but the fact that the topology sum has become a sum of cap functionals.

This is a useful way to state the problem because a topological boundary condition also naturally defines a cap. If $L$ is a topological boundary condition of $\mathfrak{T}$, then putting $\mathfrak{T}$ on a collar ending on $L$ gives, for each $M$, a linear functional

$$
\begin{aligned}
\langle L;M|\in\mathcal{H}_{\mathfrak{T}}(M)^{*}.
\end{aligned}\tag{2.6}
$$

This functional is not an arbitrary element of the dual vector space. It is one that can be realized by a boundary condition of the same topological theory.

The construction that we will use is that, in some cases, the bordism sum [(2.5)](https://arxiv.org/html/2605.06653v1#S2.E5) can be reorganized in terms of these topological caps:

$$
\begin{aligned}
\mathcal{C}_{\mathrm{bord}}(M)=\sum_{[L]}W_{M}(L)\,\langle L;M|.
\end{aligned}\tag{2.7}
$$

Here $W_{M}(L)$ is the total weight of all bordisms that give the same cap, or more generally the same cap data, in the TFT. Equivalently, the statement is that the image of the bordism sum in $\mathcal{H}_{\mathfrak{T}}(M)^{*}$ factors through the set of topological boundary conditions.

This should not be interpreted as saying that a geometric filling $Y$ is literally the same thing as a topological boundary condition $L$. The statement is weaker, and more natural from the TFT point of view. After applying the functor $Z_{\mathfrak{T}}$, the filling $Y$ is remembered only through the functional, or physically speaking the “wave function” $Z_{\mathfrak{T}}(Y)$. Distinct fillings may therefore define the same cap. If the caps that occur in the sum are naturally labelled by topological boundary conditions, then the topology sum descends to a sum over such boundary conditions.

This is the sense in which we will relate topology sums to boundary condition averaging. The geometric objects may be handlebodies or more exotic fillings. The TFT sees only the corresponding elements of the dual Hilbert space. In favorable examples, these elements are classified by Lagrangian data. This is what happens in the Narain example \[2006.04855\]: for connected $\Sigma$, a handlebody determines a Lagrangian sublattice of $H_{1}(\Sigma,\mathbb{Z})$; after rewriting the formula in these terms, the same expression continues to make sense also when $\Sigma$ is disconnected, even though there is no longer a preferred ordinary handlebody associated to each Lagrangian sublattice. This suggests that the more intrinsic object is the Lagrangian cap data, not the ordinary smooth manifold itself.

We now specialize this observation to SymTFTs. Let $\mathfrak{T}_{\mathrm{sym}}$ be the $(d+1)$-dimensional SymTFT associated with a $d$-dimensional QFT. The SymTFT is placed on a slab

$$
\begin{aligned}
M\times[0,1].
\end{aligned}\tag{2.8}
$$

One end of the slab is coupled to the physical $d$-dimensional relative theory \[1212.1692, 2212.00195\]. This boundary in general is not topological. It depends on the metric and possible source data on $M$, which we denote collectively by $J$. We then write the physical boundary condition as

$$
\begin{aligned}
B_{\mathrm{phys}}(J).
\end{aligned}\tag{2.9}
$$

This physical boundary provides a state in the Hilbert space on $M$:

$$
\begin{aligned}
|\Psi_{\mathrm{phys}}(M;J)\rangle\in\mathcal{H}_{\mathrm{sym}}(M),
\end{aligned}\tag{2.10}
$$

which is the partition vector, instead of a number, of the relative physical boundary theory.

To obtain an absolute theory, one chooses a topological boundary condition $L$ at the other end of the slab. $L$ specifies which bulk topological operators can end on the topological boundary. The remaining bulk operators, modulo those trivialized by $L$, become the symmetry operators of the absolute theory. In finite semisimple SymTFTs, $L$ is often described as a Lagrangian algebra of the category of bulk topological operators \[hep-th/0204148, 1008.0654, 1012.0911\]. In the continuous abelian examples considered in the following sections, the analogous object will be a maximal isotropic subset in the continuous family of topological operators in the SymTFT \[hep-th/9812012, 2010.15890, 2203.09537, 2306.11783\].

For each $M$, $L$ defines a cap functional

$$
\begin{aligned}
\langle L;M|\in\mathcal{H}_{\mathrm{sym}}(M)^{*}.
\end{aligned}\tag{2.11}
$$

The partition function of the absolute theory specified by $L$ is

$$
\begin{aligned}
Z_{L}(M;J)=\langle L;M|\Psi_{\mathrm{phys}}(M;J)\rangle.
\end{aligned}\tag{2.12}
$$

We here emphasize an important restriction in this construction. We do not average over arbitrary boundary conditions at the second end of the slab. A general boundary condition $B$ would also define a linear functional

$$
\begin{aligned}
\langle B;M,J_{B}|:\mathcal{H}_{\mathrm{sym}}(M)\longrightarrow\mathbb{C},
\end{aligned}\tag{2.13}
$$

which can be regarded as another physical boundary with reversed orientation of $M$. However, such a boundary condition would usually carry its own local degrees of freedom and its own dependence on metric and coupling data. In Hamiltonian language, such a boundary would come with its own nontrivial boundary Hamiltonian. Summing over general boundary conditions would therefore be a sum over local dynamics. This is too large an operation for our purposes. In the ensemble examples we have in mind, the average is over a specified family of theories, such as a fixed theory with random couplings drawn from a prescribed ensemble with measure. An arbitrary sum over boundary conditions would not single out such an ensemble, and would not be determined by the SymTFT alone.

The SymTFT construction uses a smaller class of caps. The boundary $L$ is topological: it carries zero Hamiltonian at the end of the slab. In this sense, the Hamiltonian of the boundary absolute QFTs solely come from $B_{\mathrm{phys}}(J)$, while $L$ supplies which Hilbert space the Hamiltonian acting upon.

We may now construct the object whose measure will be discussed in the next subsection. Let $\mathcal{L}_{\mathrm{top}}$ denote the collection of admissible topological boundary conditions<sup>3</sup> of the SymTFT. Before specifying a measure, the possible averaged cap functionals lie in the span

$$
\begin{aligned}
\operatorname{Span}\left\{\langle L;M|:L\in\mathcal{L}_{\mathrm{top}}\right\}\subset\mathcal{H}_{\mathrm{sym}}(M)^{*}.
\end{aligned}\tag{2.14}
$$

An averaged partition function will be obtained by choosing a linear combination, or in continuous examples an integral, of these cap functionals and applying it to $|\Psi_{\mathrm{phys}}(M;J)\rangle$.

The analogy with summing over topologies is now direct. A bordism $Y:M\to\emptyset$ defines a cap in $\mathcal{H}_{\mathrm{sym}}(M)^{*}$. A topological boundary condition $L$ also defines a cap in $\mathcal{H}_{\mathrm{sym}}(M)^{*}$. If, after applying the SymTFT functor, the bordism sum only depends on the filling through its induced topological cap, then the sum over topologies can be reorganized as a sum over topological boundary conditions. Schematically,

$$
\begin{aligned}
\text{bordisms }Y:M\to\emptyset\xrightarrow{\;Z_{\mathrm{sym}}\;}\text{cap functionals in }\mathcal{H}_{\mathrm{sym}}(M)^{*}\leadsto\text{topological boundary conditions }L.
\end{aligned}\tag{2.15}
$$

Note that we by no means claim that every ensemble in holography arises this way. We also do not claim that every geometric filling is literally a topological boundary condition. The claim is that, for a fixed SymTFT, the natural topological caps are supplied by its topological boundary conditions, and in examples where the bulk topology sum is only sensitive to this cap data, the topology sum can be rewritten as an average over such boundary conditions.

It remains to specify how the different caps should be weighted. For a finite SymTFT, the natural object is not a set but a groupoid: topological boundary conditions can have automorphisms, and equivalent boundary conditions should not be counted independently. The corresponding average is therefore a groupoid sum over isomorphism classes of topological boundary conditions, in the same spirit as the groupoid-cardinality factors that appear in sums over fields or bordisms. The same principle applies to discrete, possibly infinite, families whenever the sum is well-defined. For a continuous SymTFT, this counting problem is replaced by a measure problem. The space of Lagrangian boundary data should be equipped with a measure invariant under the natural duality action of the SymTFT. We now turn to this question.

### 2.2 Weights and measures on the space of topological boundary conditions

Let us specify weights in the sum over topological caps. If the weights depended on the spacetime $M$, or on the sources $J$, then the resulting object would not be an ensemble average in the usual sense. It would instead be a separate prescription for each observable. An ensemble measure should be chosen once and for all on the space of caps, and the same measure should then be used for all boundary manifolds and all insertions.

Let

$$
\begin{aligned}
F_{M,J}(L)=Z_{L}(M;J)=\langle L;M|\Psi_{\mathrm{phys}}(M;J)\rangle
\end{aligned}\tag{2.16}
$$

be the function on the space of topological boundary conditions obtained by evaluating the physical boundary state against the cap, i.e. topological boundary $L$. The problem is to define an integral of this function over the allowed topological boundary conditions.

We first consider the case where the collection of topological boundary conditions is finite. The correct notion is generally not a merely set but a groupoid<sup>4</sup>. The associated physical facts include that two topological boundary conditions may be equivalent, and/or a given topological boundary condition may have automorphisms. Therefore one should not simply sum over all topological boundaries with the same weight. For a finite groupoid $\mathcal{G}$, the natural integral of a function $F$ on its objects is the groupoid cardinality integral

$$
\begin{aligned}
\int_{\mathcal{G}}F:=\sum_{[x]\in\pi_{0}(\mathcal{G})}\frac{1}{|\operatorname{Aut}_{\mathcal{G}}(x)|}\,F(x).
\end{aligned}\tag{2.17}
$$

Here the sum is over isomorphism classes of objects, and $\operatorname{Aut}_{\mathcal{G}}(x)$ is the automorphism group of the object $x$. This is the same counting rule that appears in finite group gauge theory (see, e.g., \[1511.00295\]) and in summed-bordism constructions (see, e.g., \[2201.00903\]): configurations with nontrivial automorphisms are weighted by the inverse order of their automorphism group.

Applying this rule to the groupoid $\mathcal{L}_{\mathrm{top}}$ of topological boundary conditions gives

$$
\begin{aligned}
\boxed{\left\langle Z(M;J)\right\rangle_{\mathrm{top}}=\sum_{[L]}\frac{1}{|\operatorname{Aut}(L)|}\,\langle L;M|\Psi_{\mathrm{phys}}(M;J)\rangle.}
\end{aligned}\tag{2.18}
$$

This formula is the finite version of the topological-boundary ensemble. The automorphism group in [(2.18)](https://arxiv.org/html/2605.06653v1#S2.E18) is the automorphism group of the cap as an object of the groupoid of topological boundary conditions. It is not an automorphism group of the spacetime $M$. The spacetime data have already entered through the function $F_{M,J}(L)=\langle L;M|\Psi_{\mathrm{phys}}(M;J)\rangle$.

The same principle applies to discrete but possibly infinite families of caps. If the set of isomorphism classes is countable and the automorphism groups are finite, the ensemble averaging is again [(2.18)](https://arxiv.org/html/2605.06653v1#S2.E18). Now, however, convergence is part of the problem. The counting prescription tells us how each cap should be weighted, but it does not by itself guarantee that the total sum defines a finite partition function.

For continuous SymTFTs, the groupoid sum is replaced by the integral with a measure. The space of topological boundary conditions can have continuous components, and the sum over $[L]$ is promoted to an integral

$$
\begin{aligned}
\boxed{\left\langle Z(M;J)\right\rangle_{\mathrm{top}}=\int_{\mathcal{L}_{\mathrm{top}}}d\mu(L)\,\langle L;M|\Psi_{\mathrm{phys}}(M;J)\rangle.}
\end{aligned}\tag{2.19}
$$

The measure $d\mu(L)$ should be intrinsic to the SymTFT. In the examples of interest, there is a natural duality group acting on the space of topological boundary, and the measure is fixed by invariance under this action.

More explicitly, suppose that a generic component of the space of topological boundary conditions reads

$$
\begin{aligned}
\mathcal{L}_{\mathrm{gen}}\simeq\Gamma\backslash G/H.
\end{aligned}\tag{2.20}
$$

Here $G$ is the continuous group of automorphisms of the topological defect data preserving the bulk TFT structure, e.g., braiding or quadratic form, $H$ is the stabilizer of a reference topological boundary condition, and $\Gamma$ is the discrete duality group by which physically equivalent data are identified. The measure on $G/H$ is induced from Haar measure \[9006cc9e-2dcc-3fd8-aada-e4af19b6e225\] on $G$, and it descends to a measure on $\Gamma\backslash G/H$. Equivalently, it is characterized by

$$
\begin{aligned}
d\mu(gL)=d\mu(L),\qquad g\in G,
\end{aligned}\tag{2.21}
$$

together with the quotient by $\Gamma$.

If the quotient has finite volume, one can either use the unnormalized measure or normalize it to unit total volume. Thus one may define

$$
\begin{aligned}
\left\langle Z(M;J)\right\rangle_{\mathrm{top}}^{\mathrm{norm}}=\frac{1}{\operatorname{Vol}_{\mu}(\mathcal{L}_{\mathrm{top}})}\int_{\mathcal{L}_{\mathrm{top}}}d\mu(L)\,Z_{L}(M;J),
\end{aligned}\tag{2.22}
$$

provided

$$
\begin{aligned}
\operatorname{Vol}_{\mu}(\mathcal{L}_{\mathrm{top}})=\int_{\mathcal{L}_{\mathrm{top}}}d\mu(L)<\infty.
\end{aligned}\tag{2.23}
$$

In many cases of interest, the overall normalization is conventional, so we will not specify it.

The finite and continuous prescriptions are compatible. If the quotient $\Gamma\backslash G/H$ has orbifold points, then the invariant measure should be understood as an orbifold measure. Locally, if a point has a finite stabilizer group $G_{L}$, integration over a small neighborhood $U/G_{L}$ is defined by

$$
\begin{aligned}
\int_{U/G_{L}}f=\frac{1}{|G_{L}|}\int_{U}f.
\end{aligned}\tag{2.24}
$$

Thus the familiar factor $1/|\operatorname{Aut}(L)|$ is the discrete version of the same principle.

## 3 A SymTFT Realization of the Marolf–Maxfield Topological Ensemble

In this section we explain, in a deliberately minimal setting, how the closed-string sector ensemble of Marolf–Maxfield \[2002.08950\] can be reproduced as a sum over topological boundary conditions of a fixed SymTFT. By the closed-string sector we mean the part of the model without end-of-the-world branes. We use the corresponding topological-boundary-condition formalism and show that the sum over topological boundary conditions reproduces the normalized Bell-polynomial moments of the Marolf–Maxfield model. We leave the open-string sector, including end-of-the-world branes, for future work.

### 3.1 The closed-string sector of Marolf–Maxfield

We begin by recalling the general baby-universe interpretation of ensemble averaging, and then specialize it to the closed-string sector of the Marolf–Maxfield topological model \[2002.08950\]. This review is slightly longer than what is strictly needed for the computation, but it will be useful for explaining what the SymTFT construction in the next subsection is supposed to reproduce.

Consider a gravitational path integral with asymptotic boundary conditions $J_{i}$ imposed on $n$ disconnected boundary components. Schematically one writes

$$
\begin{aligned}
\big\langle Z[J_{1}]\cdots Z[J_{n}]\big\rangle_{\mathrm{grav}}=\int_{\Phi\sim\{J_{i}\}}\mathcal{D}\Phi\,e^{-S[\Phi]}.
\end{aligned}\tag{3.1}
$$

If the bulk path integral includes connected geometries whose conformal boundary has several connected components, then the answer need not factorize. For example,

$$
\begin{aligned}
\big\langle Z[J_{1}]Z[J_{2}]\big\rangle_{\mathrm{grav}}\neq\big\langle Z[J_{1}]\big\rangle_{\mathrm{grav}}\big\langle Z[J_{2}]\big\rangle_{\mathrm{grav}}.
\end{aligned}\tag{3.2}
$$

The connected contribution is interpreted as a spacetime wormhole between the two asymptotic boundaries. This is the basic origin of the ensemble interpretation.

A convenient way to organize this non-factorization is to cut open the gravitational path integral along an intermediate slice. The slice may contain components that do not reach any asymptotic boundary. These closed spatial components are called baby universes. The states obtained in this way span the baby-universe Hilbert space \[Coleman:1988cy, Giddings:1988cx, Giddings:1988wv\], denoted $\mathcal{H}_{\mathrm{BU}}$. Given $n$ boundary insertions, there is a corresponding state

$$
\begin{aligned}
\big|Z[J_{1}]\cdots Z[J_{n}]\big\rangle\in\mathcal{H}_{\mathrm{BU}}.
\end{aligned}\tag{3.3}
$$

The state with no asymptotic boundary is the Hartle–Hawking state,

$$
\begin{aligned}
|\mathrm{HH}\rangle\in\mathcal{H}_{\mathrm{BU}},\qquad\mathcal{N}:=\langle\mathrm{HH}|\mathrm{HH}\rangle=\langle 1\rangle_{\mathrm{grav}}.
\end{aligned}\tag{3.4}
$$

Here $\mathcal{N}$ is the no-boundary amplitude, or cosmological partition function. In a completely precise construction one should also quotient by null states in the inner product defined by the gravitational path integral. We will not need this refinement explicitly in the closed-string sector example below.

For each asymptotic boundary condition $J$, one defines an operator $\widehat{Z}[J]$ on $\mathcal{H}_{\mathrm{BU}}$ by adding one more boundary component:

$$
\begin{aligned}
\widehat{Z}[J]\,\big|Z[J_{1}]\cdots Z[J_{n}]\big\rangle=\big|Z[J]Z[J_{1}]\cdots Z[J_{n}]\big\rangle.
\end{aligned}\tag{3.5}
$$

Since the order of the boundary components in the gravitational path integral is irrelevant, these operators commute:

$$
\begin{aligned}
[\widehat{Z}[J_{1}],\widehat{Z}[J_{2}]]=0.
\end{aligned}\tag{3.6}
$$

Thus they can be diagonalized simultaneously. We denote their common eigenstates by $\alpha$:

$$
\begin{aligned}
\widehat{Z}[J]|\alpha\rangle=Z_{\alpha}[J]\,|\alpha\rangle,\qquad\forall\,J.
\end{aligned}\tag{3.7}
$$

Inserting a resolution of the identity in the $\alpha$-basis gives

$$
\begin{aligned}
\frac{\big\langle Z[J_{1}]\cdots Z[J_{n}]\big\rangle_{\mathrm{grav}}}{\langle 1\rangle_{\mathrm{grav}}}=\sum_{\alpha}p_{\alpha}\,Z_{\alpha}[J_{1}]\cdots Z_{\alpha}[J_{n}],\qquad p_{\alpha}=\frac{|\langle\mathrm{HH}|\alpha\rangle|^{2}}{\langle\mathrm{HH}|\mathrm{HH}\rangle}.
\end{aligned}\tag{3.8}
$$

This is the ensemble interpretation. A fixed $\alpha$-sector is a factorizing theory, while the Hartle–Hawking state prepares a probability distribution over such sectors. If the $\alpha$-spectrum is continuous, the sum in [(3.8)](https://arxiv.org/html/2605.06653v1#S3.E8) is replaced by an integral with the corresponding probability measure.

We now specialize this discussion to the closed-string sector of the Marolf–Maxfield topological model. By “closed-string sector” we mean the sector with closed circular asymptotic boundaries and no end-of-the-world branes. There is only one type of closed asymptotic boundary $S^{1}$, so there is a single boundary observable, which we denote by $Z$. Equivalently, the general operator $\widehat{Z}[J]$ above reduces to one baby-universe operator, which we denote by a reduced symbol $\widehat{Z}$. The gravitational path integral with $n$ labelled circular boundaries computes the moment $\big\langle Z^{n}\big\rangle_{\mathrm{MM}}$. The boundaries are held fixed and labelled. Thus automorphisms of a bulk surface are required to act trivially on the boundary components.

The combinatorics of the closed sector is simple. A connected component of the bulk can end on any nonempty subset of the $n$ boundary circles. After summing over the genus of that connected component, and after absorbing the boundary weight into the normalization of $Z$, every connected component with at least one boundary contributes the same effective factor. We denote this factor by $\lambda$. Equivalently, this is to say that all connected closed-boundary amplitudes are normalized to the same $\lambda$:

$$
\begin{aligned}
\frac{\big\langle Z^{m}\big\rangle_{\mathrm{conn}}}{\langle 1\rangle_{\mathrm{MM}}}=\lambda,\qquad m\geq 1.
\end{aligned}\tag{3.9}
$$

The detailed dependence of $\lambda$ on the topological action is not important for us. It can be regarded as the effective fugacity for one connected bulk component that touches the asymptotic boundary.

For $n$ labelled boundaries, a bulk configuration is therefore specified by a partition $\pi$ of the set $[n]=\{1,\ldots,n\}$. Each block of $\pi$ records the set of boundary circles that lie on one connected component of the bulk. Since each block contributes a factor $\lambda$, we obtain

$$
\begin{aligned}
\frac{\big\langle Z^{n}\big\rangle_{\mathrm{MM}}}{\langle 1\rangle_{\mathrm{MM}}}=\sum_{\pi\in\operatorname{Part}([n])}\lambda^{|\pi|}=B_{n}(\lambda)\equiv e^{-\lambda}\sum_{d=0}^{\infty}\frac{\lambda^{d}}{d!}\,d^{n}.
\end{aligned}\tag{3.10}
$$

where $B_{n}(\lambda)$ is the Bell (or Touchard) polynomial. The normalized generating function thus is

$$
\begin{aligned}
\frac{\big\langle e^{uZ}\big\rangle_{\mathrm{MM}}}{\langle 1\rangle_{\mathrm{MM}}}=\exp\!\left[\lambda(e^{u}-1)\right].
\end{aligned}\tag{3.11}
$$

Equations [(3.11)](https://arxiv.org/html/2605.06653v1#S3.E11) show that the closed-string sector Marolf–Maxfield moments are precisely the moments of a Poisson random variable of mean $\lambda$. Thus the $\alpha$-sectors can be labelled by a non-negative integer $d$, and the baby-universe operator has spectrum

$$
\begin{aligned}
\widehat{Z}|d\rangle=d\,|d\rangle,\qquad d\in\mathbb{Z}_{\geq 0}.
\end{aligned}\tag{3.12}
$$

The Hartle–Hawking state prepares the probability distribution

$$
\begin{aligned}
p_{d}=\frac{|\langle\mathrm{HH}|d\rangle|^{2}}{\langle\mathrm{HH}|\mathrm{HH}\rangle}=e^{-\lambda}\frac{\lambda^{d}}{d!}.
\end{aligned}\tag{3.13}
$$

In a fixed $d$-sector the theory factorizes:

$$
\begin{aligned}
\big\langle Z^{n}\big\rangle_{d}=d^{n}.
\end{aligned}\tag{3.14}
$$

The non-factorizing Marolf–Maxfield answer [(3.10)](https://arxiv.org/html/2605.06653v1#S3.E10) is obtained only after averaging over the $d$-sectors with the Poisson weights [(3.13)](https://arxiv.org/html/2605.06653v1#S3.E13).

### 3.2 SymTFT approach to Marolf–Maxfield ensemble

We now give a SymTFT realization of the closed-string sector ensemble averaging problem reviewed above. The model does not enjoy a nice Lagrangian description such as BF or Chern–Simons theory. The fixed parent object we use is instead a discrete, stacky, groupoid-completed 2D SymTFT analogue, which we denote by $\mathfrak{S}_{\mathrm{Fin}}$. It is not the ordinary TFT associated with one chosen finite set. Rather, it is a single parent object whose admissible topological boundary conditions, to be summed over below, are labelled by finite sets. Since the closed-string sector of Marolf–Maxfield has only one asymptotic boundary observable $Z$, the topological data needed to reproduce their result is very small and explicit.

A mathematical fact we will use is that oriented 2D TFTs can be constructed via Frobenius algebras \[Abrams:1996ty, Kock\_2003, 2206.12448\]<sup>5</sup>. We will use this fact only after a topological cap has been chosen. Let $S$ be a finite set. The cap labelled by $S$ produces an ordinary absolute closed 2D TFT whose Frobenius algebra is

$$
\begin{aligned}
\mathcal{A}_{S}=\operatorname{Fun}(S,\mathbb{C})=\bigoplus_{s\in S}\mathbb{C}e_{s},
\end{aligned}\tag{3.15}
$$

where $e_{s}$ is the delta-function supported at $s$. The categorical data of this algebra is labeled by the Frobenius object $(\mathcal{A}_{S},\mu,\eta,\delta,\varepsilon)$:

$$
\begin{aligned}
\begin{split}\text{multiplication }\mu&:\mathcal{A}_{S}\otimes\mathcal{A}_{S}\rightarrow\mathcal{A}_{S},\\
\text{unit }\eta&:I\rightarrow\mathcal{A}_{S},\\
\text{comultiplication }\delta&:\mathcal{A}_{S}\rightarrow\mathcal{A}_{S}\otimes\mathcal{A}_{S},\\
\text{counit }\varepsilon&:\mathcal{A}_{S}\rightarrow I.\end{split}
\end{aligned}\tag{3.16}
$$

which respectively read

$$
\begin{aligned}
e_{s}e_{s^{\prime}}=\delta_{s,s^{\prime}}e_{s},\qquad 1_{S}=\sum_{s\in S}e_{s},\qquad\Delta_{S}(e_{s})=e_{s}\otimes e_{s},\qquad\varepsilon_{S}(e_{s})=1.
\end{aligned}\tag{3.17}
$$

The Frobenius pairing is

$$
\begin{aligned}
\langle e_{s},e_{s^{\prime}}\rangle_{S}=\varepsilon_{S}(e_{s}e_{s^{\prime}})=\delta_{s,s^{\prime}}.
\end{aligned}\tag{3.18}
$$

By the mathematical construction of oriented 2D TFTs via Frobenius algebras, our algebra $\mathcal{A}_{S}$ defines an oriented closed worldsheet TFT, which we denote by $\mathcal{T}_{S}$. Its state space on a circle is

$$
\begin{aligned}
\mathcal{H}_{\mathcal{T}_{S}}(S^{1})=\mathcal{A}_{S}.
\end{aligned}\tag{3.19}
$$

The case $S=\varnothing$ will also be included. We regard it as the formal zero-dimensional sector

$$
\begin{aligned}
\mathcal{A}_{\varnothing}=0.
\end{aligned}\tag{3.20}
$$

For $d>0$, we choose the representative

$$
\begin{aligned}
[d]=\{1,\ldots,d\},\qquad\mathcal{A}_{[d]}\cong\mathbb{C}^{d}.
\end{aligned}\tag{3.21}
$$

We should not regard the theories $\mathcal{T}_{S}$ as different parent SymTFTs that are subsequently summed over. Rather, the fixed parent object is a discrete analogue

$$
\begin{aligned}
\mathfrak{S}_{\mathrm{Fin}},
\end{aligned}\tag{3.22}
$$

whose simple topological boundary conditions form the groupoid

$$
\begin{aligned}
\operatorname{TopBdy}(\mathfrak{S}_{\mathrm{Fin}})\simeq\mathsf{FinSet}^{\simeq}.
\end{aligned}\tag{3.23}
$$

Since finite sets can have arbitrary cardinality, $\mathfrak{S}_{\mathrm{Fin}}$ is not a finite SymTFT in the usual finite-semisimple sense; it is a countably semisimple, discrete non-compact SymTFT. A choice of topological boundary condition $\mathsf{B}_{S}$ labelled by a finite set $S$ produces the absolute closed TFT $\mathcal{T}_{S}$ described above. Thus

$$
\begin{aligned}
\mathcal{T}_{S}(S^{1})=\mathcal{A}_{S}=\operatorname{Fun}(S,\mathbb{C})
\end{aligned}\tag{3.24}
$$

is the closed algebra of the fixed-cap absolute theory, not the parent SymTFT itself.

This is analogous to a finite discrete gauge-theory SymTFT. For example, in 2D $\mathbb{Z}_{N}$ BF theory, with schematic action

$$
\begin{aligned}
\frac{iN}{2\pi}\int a_{0}\,db_{1},
\end{aligned}\tag{3.25}
$$

one fixed SymTFT controls a family of absolute theories labelled by a discrete parameter in $\mathbb{Z}_{N}$. A topological boundary condition selects one member of that family. In the present finite-set model, the discrete label $r\in\mathbb{Z}_{N}$ is replaced by a finite set $S$, and the selected absolute theory is $\mathcal{T}_{S}$.

#### The physical boundary and the topological boundary conditions.

We next specify the physical boundary condition. In the closed-string sector of the Marolf–Maxfield model there is a single asymptotic boundary condition, corresponding to one circular boundary and one observable $Z$. The physical boundary should not be understood as a boundary condition of one already chosen absolute TFT $\mathcal{T}_{S}$. It is instead a universal identity section over the groupoid of topological caps. After the topological cap $\mathsf{B}_{S}$ is chosen, this same physical boundary is represented in the fixed-cap theory $\mathcal{T}_{S}$ by the unit state:

$$
\begin{aligned}
B_{\mathrm{phys}}(S^{1}):\qquad S\longmapsto|\Psi_{\mathrm{phys}}(S^{1})\rangle_{S}=1_{S}\in\mathcal{A}_{S}.
\end{aligned}\tag{3.26}
$$

Here the subscript $S$ on the state is only a reminder that this is the representation of the same physical boundary after the topological cap $\mathsf{B}_{S}$ has been chosen. Thus $B_{\mathrm{phys}}$ itself is not $S$-dependent; only its fixed-cap description is.

The topological boundary condition determined by the finite set $S$, which we denote by $\mathsf{B}_{S}$, is the cap of the parent theory $\mathfrak{S}_{\mathrm{Fin}}$. In the fixed-cap absolute description, this cap is represented by the Frobenius counit $\varepsilon_{S}:\mathcal{A}_{S}\longrightarrow\mathbb{C}$ in [(3.17)](https://arxiv.org/html/2605.06653v1#S3.E17):

$$
\begin{aligned}
B_{\mathrm{top}}(S^{1}):\langle\mathsf{B}_{S};S^{1}|=\varepsilon_{S}.
\end{aligned}\tag{3.27}
$$

The resulting partition function by pairing the physical boundary [(3.26)](https://arxiv.org/html/2605.06653v1#S3.E26) and topological boundary [(3.27)](https://arxiv.org/html/2605.06653v1#S3.E27) is

$$
\begin{aligned}
Z_{S}(S^{1})=\langle\mathsf{B}_{S};S^{1}|\Psi_{\mathrm{phys}}(S^{1})\rangle_{S}=\varepsilon_{S}(1_{S})=\sum_{s\in S}\varepsilon_{S}(e_{s})=|S|.
\end{aligned}\tag{3.28}
$$

For $S=\varnothing$, this formula gives $Z_{\varnothing}(S^{1})=0$, which aligns with our convention that $\mathcal{A}_{\varnothing}=0$ is the formal zero-dimensional sector.

It is now straightforward to see that a fixed topological boundary condition $\mathsf{B}_{S}$, labelled by the finite set $S$, realizes an $\alpha$-sector in which the closed-boundary baby-universe operator has eigenvalue

$$
\begin{aligned}
\widehat{Z}(S^{1})\,|S\rangle=Z_{S}(S^{1})\,|S\rangle=|S|\,|S\rangle.
\end{aligned}\tag{3.29}
$$

For the representative $[d]=\{1,\ldots,d\},d\geq 0$, we write $|d\rangle:=|[d]\rangle$, which allows us to reproduce [(3.12)](https://arxiv.org/html/2605.06653v1#S3.E12)

$$
\begin{aligned}
\widehat{Z}(S^{1})\,|d\rangle=d\,|d\rangle.
\end{aligned}\tag{3.30}
$$

#### The groupoid of topological boundary conditions.

By definition of the parent finite-set SymTFT analogue $\mathfrak{S}_{\mathrm{Fin}}$, a simple topological boundary condition is labelled by a finite set $S$. We now discuss how to sum over all such topological boundary conditions to obtain an ensemble average. As discussed in general strategy in Section [2.2](https://arxiv.org/html/2605.06653v1#S2.SS2), we must specify what it means to sum over such topological boundary conditions, which amounts to determine the weight/measure structure over the space of topological boundary conditions.

The point is that the elements of $S$ do not enjoy a specific way of labeling. Relabelling the points of $S$ gives an isomorphic Frobenius algebra and hence the same topological boundary condition. Therefore the space of topological boundary conditions is not merely a set, but a groupoid, whose objects and morphisms are

$$
\begin{aligned}
\begin{split}\text{objects (0-morphisms):}&\qquad\text{finite sets}\\
\text{1-morphisms:}&\qquad\text{bijections between sets}\end{split}
\end{aligned}\tag{3.31}
$$

In the Frobenius-algebra language, a bijection $f:S\to S^{\prime}$ induces an isomorphism

$$
\begin{aligned}
f^{*}:\mathcal{A}_{S^{\prime}}\longrightarrow\mathcal{A}_{S},\qquad e_{s^{\prime}}\longmapsto e_{f^{-1}(s^{\prime})}.
\end{aligned}\tag{3.32}
$$

Conversely, every algebra automorphism of $\mathcal{A}_{S}=\operatorname{Fun}(S,\mathbb{C})$ permutes the primitive idempotents $e_{s}$.<sup>6</sup> Since all primitive idempotents have the same Frobenius trace,

$$
\begin{aligned}
\varepsilon_{S}(e_{s})=1,
\end{aligned}\tag{3.33}
$$

every permutation preserves the Frobenius counit, and it also preserves the comultiplication $\Delta_{S}(e_{s})=e_{s}\otimes e_{s}$. Hence

$$
\begin{aligned}
\operatorname{Aut}_{\mathrm{Frob}}(\mathcal{A}_{S})\cong\operatorname{Aut}(S)\cong\mathfrak{S}_{|S|}.
\end{aligned}\tag{3.34}
$$

Thus the groupoid of topological boundary conditions of $\mathfrak{S}_{\mathrm{Fin}}$ is the groupoid of finite sets,

$$
\begin{aligned}
\mathfrak{B}_{\mathrm{top}}\simeq\mathsf{FinSet}^{\simeq}.
\end{aligned}\tag{3.35}
$$

After choosing the representative $[d]=\{1,\ldots,d\}$ in each isomorphism class, this groupoid decomposes as

$$
\begin{aligned}
\mathfrak{B}_{\mathrm{top}}\simeq\mathsf{FinSet}^{\simeq}\simeq\coprod_{d\geq 0}B\mathfrak{S}_{d}.
\end{aligned}\tag{3.36}
$$

Here $B\mathfrak{S}_{d}$ denotes the one-object groupoid whose automorphism group is $\mathfrak{S}_{d}=\mathfrak{S}_{|S|}\cong\operatorname{Aut}(S)$. In other words, there is one finite-set topological boundary condition of each cardinality $d$, but the topological boundary condition with $d$ points has an automorphism group $\mathfrak{S}_{d}$ coming from relabellings of the points. The Frobenius algebras $\mathcal{A}_{S}$ are the absolute closed TFTs obtained after choosing these caps.

This is the origin of the weighted factor in the topological-boundary sum. For any function $F$ of the topological-boundary-condition data, the groupoid-counting prescription gives

$$
\begin{aligned}
\int_{\mathfrak{B}_{\mathrm{top}}}F:=\sum_{[S]\in\pi_{0}(\mathfrak{B}_{\mathrm{top}})}\frac{1}{|\operatorname{Aut}(S)|}\,F(S)=\sum_{d=0}^{\infty}\frac{1}{|\mathfrak{S}_{d}|}\,F([d])=\sum_{d=0}^{\infty}\frac{1}{d!}\,F([d]).
\end{aligned}\tag{3.37}
$$

#### The groupoid average and (non-)factorization.

We are now ready to reproduce the Marolf–Maxfield closed-string sector ensemble. In addition to the groupoid-counting factor, we assign a fugacity $\lambda$ to each point of the finite set $S$, or equivalently to each primitive idempotent of the fixed-cap algebra $\mathcal{A}_{S}$. The factor $1/|\operatorname{Aut}(S)|$ is the intrinsic groupoid-counting factor, while $\lambda^{|S|}$ is the fugacity, equivalently the choice of Hartle–Hawking/ensemble state in this discrete model. Thus the unnormalized boundary-condition measure is

$$
\begin{aligned}
d\mu_{\lambda}(S)=\frac{\lambda^{|S|}}{|\operatorname{Aut}(S)|}.
\end{aligned}\tag{3.38}
$$

Here $\operatorname{Aut}(S)$ is the group of bijections from $S$ to itself. The normalization is the weighted groupoid cardinality

$$
\begin{aligned}
\mathcal{N}_{\lambda}=\sum_{[S]\in\pi_{0}(\mathfrak{B}_{\mathrm{top}})}\frac{\lambda^{|S|}}{|\operatorname{Aut}(S)|}=\sum_{d=0}^{\infty}\frac{\lambda^{d}}{|\mathfrak{S}_{d}|}=\sum_{d=0}^{\infty}\frac{\lambda^{d}}{d!}=e^{\lambda}.
\end{aligned}\tag{3.39}
$$

The normalized one-boundary average is then

$$
\begin{aligned}
\bigl\langle Z\bigr\rangle_{\mathrm{top}}=\frac{1}{\mathcal{N}_{\lambda}}\sum_{[S]\in\pi_{0}(\mathfrak{B}_{\mathrm{top}})}\frac{\lambda^{|S|}}{|\operatorname{Aut}(S)|}Z_{S}(S^{1}).
\end{aligned}\tag{3.40}
$$

Using $Z_{S}(S^{1})=\langle\mathsf{B}_{S};S^{1}|\Psi_{\mathrm{phys}}(S^{1})\rangle_{S}=|S|$, this becomes

$$
\begin{aligned}
\bigl\langle Z\bigr\rangle_{\mathrm{top}}=e^{-\lambda}\sum_{d=0}^{\infty}\frac{\lambda^{d}}{d!}\,d=\lambda.
\end{aligned}\tag{3.41}
$$

This agrees with the Marolf–Maxfield closed-string sector result

$$
\begin{aligned}
\frac{\left\langle Z\right\rangle_{\mathrm{MM}}}{\left\langle 1\right\rangle_{\mathrm{MM}}}=\lambda.
\end{aligned}\tag{3.42}
$$

The integer $d$ in the Marolf–Maxfield $\alpha$-sector is thus interpreted as the cardinality of the finite-set topological boundary condition, i.e., $d=|S|$, while the Poisson probability is the normalized groupoid measure on finite-set topological boundary conditions with fugacity $\lambda$:

$$
\begin{aligned}
p_{d}=\frac{1}{\mathcal{N}_{\lambda}}\frac{\lambda^{d}}{|\operatorname{Aut}([d])|}=\frac{1}{\mathcal{N}_{\lambda}}\frac{\lambda^{d}}{|\mathfrak{S}_{d}|}=e^{-\lambda}\frac{\lambda^{d}}{d!}.
\end{aligned}\tag{3.43}
$$

It is also straightforward to generalize to the case with multiple boundary components. Concretely, we consider $n$ labelled closed boundaries as

$$
\begin{aligned}
M_{n}=\bigsqcup_{i=1}^{n}S^{1}_{i},
\end{aligned}\tag{3.44}
$$

where $S_{i}^{1}$ labels the $i$-th $S^{1}$ component of the boundary manifold $M_{n}$. After capping by $\mathsf{B}_{S}$, the state space on this boundary manifold is a tensor product Hilbert space

$$
\begin{aligned}
\mathcal{H}_{\mathcal{T}_{S}}(M_{n})=\mathcal{A}_{S}^{\otimes n}
\end{aligned}\tag{3.45}
$$

The same universal physical boundary and the topological cap are then represented, in the fixed-cap theory, by

$$
\begin{aligned}
|\Psi_{\mathrm{phys}}(M_{n})\rangle_{S}=1_{S}^{\otimes n}\in\mathcal{A}_{S}^{\otimes n},\qquad\langle\mathsf{B}_{S};M_{n}|=\varepsilon_{S}^{\otimes n}.
\end{aligned}\tag{3.46}
$$

Therefore, the partition function for a given topological boundary condition $\langle\mathsf{B}_{S};M_{n}|$ reads

$$
\begin{aligned}
Z_{S}(M_{n})=\langle\mathsf{B}_{S};M_{n}|\Psi_{\mathrm{phys}}(M_{n})\rangle_{S}=\prod_{i=1}^{n}Z_{S}(S^{1}_{i})=|S|^{n}.
\end{aligned}\tag{3.47}
$$

This corresponds to the $\alpha$-sector represented by $[d]$ with $d=|S|$,

$$
\begin{aligned}
\langle d|\widehat{Z}(S^{1})^{n}|d\rangle=d^{n}.
\end{aligned}\tag{3.48}
$$

The normalized average over the space of topological boundary conditions is thus

$$
\begin{aligned}
\bigl\langle Z^{n}\bigr\rangle_{\mathrm{top}}=\frac{1}{\mathcal{N}_{\lambda}}\sum_{[S]\in\pi_{0}(\mathfrak{B}_{\mathrm{top}})}\frac{\lambda^{|S|}}{|\operatorname{Aut}(S)|}|S|^{n}.
\end{aligned}\tag{3.49}
$$

Under the representatives $[d]$, this becomes

$$
\begin{aligned}
\bigl\langle Z^{n}\bigr\rangle_{\mathrm{top}}=e^{-\lambda}\sum_{d=0}^{\infty}\frac{\lambda^{d}}{d!}\,d^{n},
\end{aligned}\tag{3.50}
$$

which is exactly the $n$-th moment of a Poisson random variable of mean $\lambda$. Hence, we obtain

$$
\begin{aligned}
\bigl\langle Z^{n}\bigr\rangle_{\mathrm{top}}=B_{n}(\lambda)=\frac{\left\langle Z^{n}\right\rangle_{\mathrm{MM}}}{\left\langle 1\right\rangle_{\mathrm{MM}}},
\end{aligned}\tag{3.51}
$$

reproducing the Marolf–Maxfield moment formula as the Bell polynomial. The generating function is likewise

$$
\begin{aligned}
\bigl\langle e^{uZ}\bigr\rangle_{\mathrm{top}}=e^{-\lambda}\sum_{d=0}^{\infty}\frac{\lambda^{d}}{d!}\,e^{ud}=\exp\!\left[\lambda(e^{u}-1)\right],
\end{aligned}\tag{3.52}
$$

again matching the normalized Marolf–Maxfield result.

This also provides a SymTFT perspective for the (non-)factorization. Without loss of generality, consider two $S^{1}$ components for the boundary. At a fixed topological boundary condition $\mathsf{B}_{S}$ labelled by $S$, or equivalently in the fixed-cap absolute theory with algebra $\mathcal{A}_{S}$, we have

$$
\begin{aligned}
Z_{S}(S^{1}\sqcup S^{1})=Z_{S}(S^{1})^{2}=|S|^{2}.
\end{aligned}\tag{3.53}
$$

But after averaging over topological boundary conditions, i.e. over the caps $\mathsf{B}_{S}$ or equivalently over finite sets $S$ up to bijection, we have

$$
\begin{aligned}
\bigl\langle Z^{2}\bigr\rangle_{\mathrm{top}}=e^{-\lambda}\sum_{d=0}^{\infty}\frac{\lambda^{d}}{d!}\,d^{2}=\lambda^{2}+\lambda,
\end{aligned}\tag{3.54}
$$

whereas, [(3.41)](https://arxiv.org/html/2605.06653v1#S3.E41) gives rise to

$$
\begin{aligned}
\bigl\langle Z\bigr\rangle_{\mathrm{top}}^{2}=\lambda^{2}.
\end{aligned}\tag{3.55}
$$

Therefore, the connected two-boundary correlator is

$$
\begin{aligned}
\bigl\langle Z^{2}\bigr\rangle_{\mathrm{top}}-\bigl\langle Z\bigr\rangle_{\mathrm{top}}^{2}=\lambda\neq 0.
\end{aligned}\tag{3.56}
$$

This is the wormhole contribution in the Marolf–Maxfield model, reproduced in the SymTFT language as the variance of the finite-set cardinality $|S|$ over the space of topological boundary conditions<sup>7</sup>.

We close this section by pointing out that a careful treatment of Marolf–Maxfield model via summing over TFT bordisms is discussed in \[2201.00903\]. It would be interesting to build an explicit correspondence between that treatment with the SymTFT perspective in this section, which we leave it as a future work.

## 4 A SymTFT Realization of Averaging over Narain Moduli

We now turn from the discrete example of the previous section to a genuinely continuous example. The guiding principle is the same as before. We keep fixed a relative theory, or equivalently a fixed SymTFT together with a fixed physical boundary condition, and we vary the topological boundary condition used to cap the SymTFT slab. The difference is that the relevant topological boundary conditions now form a continuous space rather than a finite groupoid. Thus the groupoid sum of Section [3](https://arxiv.org/html/2605.06653v1#S3) is replaced by an integral over a space of topological boundary conditions

In this section we use the central charge $c=c_{L}=c_{R}$ to denote the rank of the Narain lattice, or equivalently the dimension of the target space torus $T^{c}$ in the boundary 2D compact bosons. The SymTFT we use is the 3D abelian BF theory with $\mathbb{R}$-valued gauge fields \[2401.10165, 2401.06128\]

$$
\begin{aligned}
S_{\mathrm{BF}}={1\over 2\pi}\int_{X_{3}}\sum_{i=1}^{c}a_{i}\wedge db_{i},\qquad a_{i},b_{i}\in\Omega^{1}(X_{3};\mathbb{R}).
\end{aligned}\tag{4.1}
$$

For $c=1$ this is the $\mathbb{R}$-valued SymTFT of the compact boson. For general $c$, it is the natural continuous analogue of the finite abelian SymTFTs discussed in the Chern–Simons/code-CFT literature.

The theory has topological line operators

$$
\begin{aligned}
U_{\vec{\alpha}}[\gamma]=\exp\left(i\alpha_{i}\oint_{\gamma}a_{i}\right),\qquad V_{\vec{\beta}}[\gamma]=\exp\left(i\beta_{i}\oint_{\gamma}b_{i}\right),\qquad\vec{\alpha},\vec{\beta}\in\mathbb{R}^{c}.
\end{aligned}\tag{4.2}
$$

Since the gauge group is $\mathbb{R}$, there are no large gauge transformations, and $\alpha,\beta$ are real rather than integral labels. The braiding of two such lines is given by

$$
\begin{aligned}
\left\langle U_{\alpha}[\gamma_{1}]V_{\beta}[\gamma_{2}]\right\rangle=\exp\left(2\pi i\,\vec{\alpha}\cdot\vec{\beta}\,\mathrm{Link}(\gamma_{1},\gamma_{2})\right).
\end{aligned}\tag{4.3}
$$

The defect group is

$$
\begin{aligned}
\mathbb{D}_{c}=\mathbb{R}^{c}\oplus\mathbb{R}^{c}
\end{aligned}\tag{4.4}
$$

equipped with the Dirac pairing

$$
\begin{aligned}
\big\langle(\alpha,\beta),(\alpha^{\prime},\beta^{\prime})\big\rangle=\alpha\cdot\beta^{\prime}+\alpha^{\prime}\cdot\beta\quad\mathrm{mod}\ \mathbb{Z}.
\end{aligned}\tag{4.5}
$$

The topological boundary conditions, in this continuous setting, correspond to maximal isotropic subgroups (or Lagrangian subgroups, analogue of Lagrangian algebras for finite semisimple TFTs) \[hep-th/9812012, 2010.15890, 2203.09537, 2306.11783\]

$$
\begin{aligned}
L\subset\mathbb{D}_{c}
\end{aligned}\tag{4.6}
$$

with respect to [(4.5)](https://arxiv.org/html/2605.06653v1#S4.E5). Physically, a topological boundary condition is a Dirichlet boundary condition trivializing a maximal subset of lines operators $U_{\vec{\alpha}}V_{\vec{\beta}}$ with trivial braiding. We will continue to occasionally call such an object a Lagrangian boundary condition, although one should keep in mind that this is a continuous, non-finite version of the usual finite semisimple terminology.

Let $\Sigma$ be the physical 2D boundary, equipped with the moduli data (e.g., $\tau$ for a $T^{2}$) collectively denoted by $\Omega$. It gives rise to a conformal boundary condition for the 3D BF theory, equipped with local Hamiltonian of $c$ compact bosons as well as their conformal blocks. From the BF theory quantization perspective, the physical boundary condition prepares a state in the state space on $\Sigma$

$$
\begin{aligned}
\left|\Psi_{\mathrm{phys}}(\Sigma;\Omega)\right\rangle\in\mathcal{H}_{\mathrm{BF}}(\Sigma),
\end{aligned}\tag{4.7}
$$

and a topological boundary condition $L$ defines a cap functional

$$
\begin{aligned}
\langle L;\Sigma|\in\mathcal{H}_{\mathrm{BF}}(\Sigma)^{*}.
\end{aligned}\tag{4.8}
$$

The absolute theory obtained by capping the slab with $L$ has partition function

$$
\begin{aligned}
Z_{L}(\Sigma;\Omega)=\langle L;\Sigma|\Psi_{\mathrm{phys}}(\Sigma;\Omega)\rangle,
\end{aligned}\tag{4.9}
$$

which is the partition function of the Narain CFT on 2-manifold $\Sigma$ with modulus parameter $\Omega$.

In this section, we will show from the compact Narain perspective, the possible $L$’s are precisely the data that determine points on the moduli space of Narain compactification. More precisely, naive space of topological boundary conditions will be covering space for the moduli space, up to certain limit points. After taking into account the symmetry/reparameterization of the SymTFT, the genuine space of topological boundary conditions to be averaged over is

$$
\begin{aligned}
\mathcal{L}_{\mathrm{Narain}}^{(c)}\simeq O(c,c;\mathbb{Z})\backslash O(c,c;\mathbb{R})/\bigl(O(c)\times O(c)\bigr).
\end{aligned}\tag{4.10}
$$

This is exactly the usual Narain moduli space \[Narain:1985jj, Narain:1986am\]. The continuous integral measure for ensemble averaging discussed in Section [2.2](https://arxiv.org/html/2605.06653v1#S2.SS2) is the invariant *Haar measure* \[9006cc9e-2dcc-3fd8-aada-e4af19b6e225\] on this quotient, which is the same measure that obtained from the Zamolodchikov metric in \[2006.04855\].

The resulting topological-boundary average takes the form

$$
\begin{aligned}
\begin{split}\big\langle Z_{\Sigma}(\Omega)\big\rangle_{\mathrm{top}}&={1\over\mathrm{Vol}(\mathcal{L}_{\mathrm{Narain}}^{(d)})}\int_{\mathcal{L}_{\mathrm{Narain}}^{(d)}}d\mu(L)\,Z_{L}(\Sigma;\Omega),\\
&={1\over\mathrm{Vol}(\mathcal{L}_{\mathrm{Narain}}^{(d)})}\int_{\mathcal{L}_{\mathrm{Narain}}^{(d)}}d\mu(L)\,\langle L;\Sigma|\Psi_{\mathrm{phys}}(\Sigma;\Omega)\rangle.\end{split}
\end{aligned}\tag{4.11}
$$

This is the continuous SymTFT analogue of the discrete SymTFT average in Section [3](https://arxiv.org/html/2605.06653v1#S3). The ensemble is not an average over arbitrary states in $\mathcal{H}_{\mathrm{BF}}(\Sigma)$, nor over arbitrary boundary dynamics. It is an average over topological completions of one fixed relative theory.

There are also boundary/infinity points of the space of Lagrangian subgroups. Physically these correspond to partial decompactification limits, i.e., noncompact bosons and their noncompact winding-mode duals. The compact Narain average is obtained by integrating over the compact Narain space of Lagrangian boundaries [(4.10)](https://arxiv.org/html/2605.06653v1#S4.E10). The role of the noncompact point is particularly visible for $c=1$, where the formal average diverges. We now discuss this rank-one case in detail.

### 4.1 $c=1$

For $c=1$, the SymTFT action [(4.1)](https://arxiv.org/html/2605.06653v1#S4.E1) reduces to the $\mathbb{R}$-valued BF theory \[2401.10165\]

$$
\begin{aligned}
S_{\mathrm{BF}}={1\over 2\pi}\int_{X_{3}}a\wedge db,\qquad a,b\in\Omega^{1}(X_{3};\mathbb{R}).
\end{aligned}\tag{4.12}
$$

The topological line operators are

$$
\begin{aligned}
U_{\alpha}[\gamma]=\exp\left(i\alpha\oint_{\gamma}a\right),\qquad V_{\beta}[\gamma]=\exp\left(i\beta\oint_{\gamma}b\right),\qquad\alpha,\beta\in\mathbb{R}.
\end{aligned}\tag{4.13}
$$

Their braiding is

$$
\begin{aligned}
\left\langle U_{\alpha}[\gamma_{1}]V_{\beta}[\gamma_{2}]\right\rangle=\exp\left(2\pi i\,\alpha\beta\,\mathrm{Link}(\gamma_{1},\gamma_{2})\right).
\end{aligned}\tag{4.14}
$$

Equivalently, the defect group is

$$
\begin{aligned}
\mathbb{D}_{1}=\mathbb{R}\oplus\mathbb{R}
\end{aligned}\tag{4.15}
$$

with Dirac pairing

$$
\begin{aligned}
\big\langle(\alpha,\beta),(\alpha^{\prime},\beta^{\prime})\big\rangle=\alpha\beta^{\prime}+\alpha^{\prime}\beta\quad\mathrm{mod}\ \mathbb{Z}.
\end{aligned}\tag{4.16}
$$

#### Conformal boundary condition as the physical boundary.

Let us first specify the physical boundary condition that prepares the state

$$
\begin{aligned}
|\Psi_{\mathrm{phys}}(\Sigma;\Omega)\rangle\in\mathcal{H}_{\mathrm{BF}}(\Sigma).
\end{aligned}\tag{4.17}
$$

This is the fixed conformal boundary condition at the physical end of the SymTFT slab. Introduce the linear combinations

$$
\begin{aligned}
A_{\mathrm{L}}=a+b,\qquad A_{\mathrm{R}}=a-b.
\end{aligned}\tag{4.18}
$$

On the physical boundary $\Sigma$, with local complex coordinates $z,\bar{z}$, the conformal boundary condition is

$$
\begin{aligned}
(A_{\mathrm{L}})_{\bar{z}}\big|_{\Sigma}=0,\qquad(A_{\mathrm{R}})_{z}\big|_{\Sigma}=0.
\end{aligned}\tag{4.19}
$$

Equivalently,

$$
\begin{aligned}
(a+b)_{\bar{z}}\big|_{\Sigma}=0,\qquad(a-b)_{z}\big|_{\Sigma}=0.
\end{aligned}\tag{4.20}
$$

Thus $A_{\mathrm{L}}$ supplies the left-moving current algebra, while $A_{\mathrm{R}}$ supplies the right-moving current algebra. If one works on the Lorentzian boundary cylinder $\Sigma=S^{1}_{\varphi}\times\mathbb{R}_{t}$, this same condition becomes

$$
\begin{aligned}
(a_{t}+b_{t})\big|_{\Sigma}=(a_{\varphi}+b_{\varphi})\big|_{\Sigma},\qquad(a_{t}-b_{t})\big|_{\Sigma}=-(a_{\varphi}-b_{\varphi})\big|_{\Sigma},
\end{aligned}\tag{4.21}
$$

or, equivalently,

$$
\begin{aligned}
a_{t}\big|_{\Sigma}=b_{\varphi}\big|_{\Sigma},\qquad b_{t}\big|_{\Sigma}=a_{\varphi}\big|_{\Sigma}.
\end{aligned}\tag{4.22}
$$

The corresponding physical boundary Hamiltonian is fixed once and for all by this conformal boundary condition. In the normalization of [(4.12)](https://arxiv.org/html/2605.06653v1#S4.E12), it is

$$
\begin{aligned}
H_{\mathrm{phys}}={1\over 4\pi}\int_{S^{1}}d\varphi\,:\!\left(a_{\varphi}^{2}+b_{\varphi}^{2}\right)\!:,
\end{aligned}\tag{4.23}
$$

whose corresponding spatial momentum reads

$$
\begin{aligned}
P_{\mathrm{phys}}={1\over 2\pi}\int_{S^{1}}d\varphi\,:\!a_{\varphi}b_{\varphi}\!:.
\end{aligned}\tag{4.24}
$$

Let $\mathsf{P}_{\mathrm{L}}$ and $\mathsf{P}_{\mathrm{R}}$ denote the zero-mode charge operators of the left- and right-moving current algebras supplied by $A_{\mathrm{L}}$ and $A_{\mathrm{R}}$. A bulk line labelled by $(\alpha,\beta)\in\mathbb{D}_{1}$ specifies a charge sector of the physical boundary theory. Here $\alpha$ and $\beta$ are real charge labels, not dynamical fields. In the charge sector labelled by $(\alpha,\beta)$, the zero-mode operators $\mathsf{P}_{\mathrm{L}}$ and $\mathsf{P}_{\mathrm{R}}$ have eigenvalues

$$
\begin{aligned}
p_{\mathrm{L}}(\alpha,\beta)=\alpha+\beta,\qquad p_{\mathrm{R}}(\alpha,\beta)=\alpha-\beta.
\end{aligned}\tag{4.25}
$$

Equivalently, the Virasoro zero-mode operators are

$$
\begin{aligned}
L_{0}={1\over 4}\mathsf{P}_{\mathrm{L}}^{2}+N_{\mathrm{L}},\qquad\bar{L}_{0}={1\over 4}\mathsf{P}_{\mathrm{R}}^{2}+N_{\mathrm{R}}.
\end{aligned}\tag{4.26}
$$

Therefore, in the charge sector $(\alpha,\beta)$, their eigenvalues are

$$
\begin{aligned}
h_{\alpha,\beta;N_{\mathrm{L}}}={1\over 4}\bigl(\alpha+\beta\bigr)^{2}+N_{\mathrm{L}},\qquad\bar{h}_{\alpha,\beta;N_{\mathrm{R}}}={1\over 4}\bigl(\alpha-\beta\bigr)^{2}+N_{\mathrm{R}}.
\end{aligned}\tag{4.27}
$$

We then have the familiar relation

$$
\begin{aligned}
H_{\mathrm{phys}}=L_{0}+\bar{L}_{0}-{1\over 12},\qquad P_{\mathrm{phys}}=L_{0}-\bar{L}_{0}.
\end{aligned}\tag{4.28}
$$

The radius $R$ has not appeared in the local physical boundary dynamics. It will enter only through the topological boundary condition, which selects the allowed charge sectors.

#### Continuous compact topological boundary conditions.

We now turn to the topological boundary conditions. As discussed in \[2401.10165\], there are boundary conditions realizing $U(1)\times U(1)$ symmetry in 2D QFTs, as well as two boundary conditions realizing $\mathbb{R}$ symmetries. In the former case, the topological boundary conditions are associated to the maximal isotropic subgroups of the defect group $\mathbb{D}_{1}$:

$$
\begin{aligned}
L_{R}=\left\{\left({n\over R},wR\right)\;:\;n,w\in\mathbb{Z}\right\},\qquad R\in\mathbb{R}_{>0}.
\end{aligned}\tag{4.29}
$$

Here $R$ will play the role as the compactification radius of the target $S^{1}$, in the convention where the self-dual radius is $R=1$.

Let us check that $L_{R}$ is Lagrangian. For two elements of $L_{R}$,

$$
\begin{aligned}
x_{1}=\left({n_{1}\over R},w_{1}R\right),\qquad x_{2}=\left({n_{2}\over R},w_{2}R\right),
\end{aligned}\tag{4.30}
$$

the pairing is

$$
\begin{aligned}
\langle x_{1},x_{2}\rangle=n_{1}w_{2}+n_{2}w_{1}\in\mathbb{Z},
\end{aligned}\tag{4.31}
$$

so $L_{R}$ is isotropic. Conversely, suppose that $(\alpha,\beta)\in\mathbb{R}^{2}$ pairs trivially with every element of $L_{R}$, i.e.,

$$
\begin{aligned}
\alpha\,wR+{n\over R}\,\beta\in\mathbb{Z}\qquad\forall\,n,w\in\mathbb{Z}.
\end{aligned}\tag{4.32}
$$

Setting $n=0$ gives $\alpha R\in\mathbb{Z}$, and setting $w=0$ gives $\beta/R\in\mathbb{Z}$. Therefore

$$
\begin{aligned}
\alpha\in R^{-1}\mathbb{Z},\qquad\beta\in R\mathbb{Z},
\end{aligned}\tag{4.33}
$$

which exactly means $(\alpha,\beta)\in L_{R}$. Hence $L_{R}$ is also maximal.

The boundary condition $L_{R}$ trivializes the lines

$$
\begin{aligned}
U_{n/R},\qquad V_{wR},\qquad n,w\in\mathbb{Z}.
\end{aligned}\tag{4.34}
$$

More precisely, for each element

$$
\begin{aligned}
\left({n\over R},wR\right)\in L_{R},
\end{aligned}\tag{4.35}
$$

the composite bulk line

$$
\begin{aligned}
\mathcal{U}_{n,w}:=U_{n/R}V_{wR}
\end{aligned}\tag{4.36}
$$

can end on the topological boundary. Take into account also the other endpoint on the physical boundary, it creates a local operator $\mathcal{O}_{n,w}$ of the absolute 2D compact boson CFT. These are precisely the primary fields of the compact boson at radius $R$. In the convention used above, their left- and right-moving zero-mode eigenvalues are

$$
\begin{aligned}
p_{\mathrm{L}}={n\over R}+wR,\qquad p_{\mathrm{R}}={n\over R}-wR,
\end{aligned}\tag{4.37}
$$

and hence

$$
\begin{aligned}
h_{n,w}={1\over 4}\left({n\over R}+wR\right)^{2},\qquad\bar{h}_{n,w}={1\over 4}\left({n\over R}-wR\right)^{2},
\end{aligned}\tag{4.38}
$$

before adding oscillator excitations.

The surviving topological line operators on the boundary are therefore labelled by

$$
\begin{aligned}
\alpha\in\mathbb{R}/R^{-1}\mathbb{Z}\cong U(1),\qquad\beta\in\mathbb{R}/R\mathbb{Z}\cong U(1).
\end{aligned}\tag{4.39}
$$

These two $U(1)$’s are the momentum and winding symmetries of the compact boson. Their action on the local primary $\mathcal{O}_{n,w}$ is determined by the braiding in the $\mathbb{R}$-valued BF theory. A surviving line $U_{\alpha}$ linked with the endpoint of $\mathcal{U}_{n,w}$ gives

$$
\begin{aligned}
U_{\alpha}:\quad\mathcal{O}_{n,w}\longmapsto\exp\!\left(2\pi i\,\alpha\,wR\right)\mathcal{O}_{n,w},
\end{aligned}\tag{4.40}
$$

while a surviving line $V_{\beta}$ gives

$$
\begin{aligned}
V_{\beta}:\quad\mathcal{O}_{n,w}\longmapsto\exp\!\left(2\pi i\,{\beta n\over R}\right)\mathcal{O}_{n,w}.
\end{aligned}\tag{4.41}
$$

Equivalently, writing

$$
\begin{aligned}
\alpha={\vartheta_{\mathrm{w}}\over R},\qquad\beta=\vartheta_{\mathrm{m}}R,\qquad\vartheta_{\mathrm{w}},\vartheta_{\mathrm{m}}\in\mathbb{R}/\mathbb{Z},
\end{aligned}\tag{4.42}
$$

the two symmetry actions become

$$
\begin{aligned}
U_{\vartheta_{\mathrm{w}}/R}:\quad\mathcal{O}_{n,w}\longmapsto e^{2\pi i\,\vartheta_{\mathrm{w}}w}\mathcal{O}_{n,w},\qquad V_{\vartheta_{\mathrm{m}}R}:\quad\mathcal{O}_{n,w}\longmapsto e^{2\pi i\,\vartheta_{\mathrm{m}}n}\mathcal{O}_{n,w}.
\end{aligned}\tag{4.43}
$$

Thus $\mathcal{O}_{n,w}$ carries

$$
\begin{aligned}
(Q_{\mathrm{m}},Q_{\mathrm{w}})=(n,w)
\end{aligned}\tag{4.44}
$$

under $U(1)_{\mathrm{m}}\times U(1)_{\mathrm{w}}$, where $U(1)_{\mathrm{m}}$ is generated by the $V$-type surviving lines and $U(1)_{\mathrm{w}}$ is generated by the $U$-type surviving lines.

#### The two noncompact topological boundary conditions.

The above compact boundary conditions $L_{R}$ have two degenerate limits \[2401.10165\],

$$
\begin{aligned}
L_{\infty}=\mathbb{R}\oplus 0,\qquad L_{0}=0\oplus\mathbb{R}.
\end{aligned}\tag{4.45}
$$

They are again maximal isotropic subgroups of $\mathbb{D}_{1}=\mathbb{R}\oplus\mathbb{R}$. Indeed, $L_{\infty}$ has trivial self-pairing, and an element $(\alpha,\beta)\in\mathbb{D}_{1}$ pairs trivially with every $(x,0)\in L_{\infty}$ only if

$$
\begin{aligned}
x\beta\in\mathbb{Z}\qquad\forall\,x\in\mathbb{R},
\end{aligned}\tag{4.46}
$$

which implies $\beta=0$.

Let us first consider $L_{\infty}$. Since $L_{\infty}$ contains all $U_{\alpha}$ lines, they can end on the topological boundary. This leads to 2D local operators $\mathcal{O}^{(\infty)}_{\alpha},\alpha\in\mathbb{R}$. They lie in the charge sector

$$
\begin{aligned}
(\alpha,\beta)=(\alpha,0),
\end{aligned}\tag{4.47}
$$

and therefore have left- and right-moving zero-mode eigenvalues

$$
\begin{aligned}
p_{\mathrm{L}}=\alpha,\qquad p_{\mathrm{R}}=\alpha.
\end{aligned}\tag{4.48}
$$

Before adding oscillator descendants, their conformal weights are

$$
\begin{aligned}
h_{\alpha}^{(\infty)}={1\over 4}\alpha^{2},\qquad\bar{h}_{\alpha}^{(\infty)}={1\over 4}\alpha^{2},
\end{aligned}\tag{4.49}
$$

which precisely match the primaries of the noncompact boson. Equivalently, one may think of them as the $R\to\infty$ limit of the compact-boson primaries with $w=0$, where $n/R$ becomes a continuous momentum.

The topological lines that survive on the $L_{\infty}$ boundary are the quotient

$$
\begin{aligned}
\mathbb{D}_{1}/L_{\infty}\simeq 0\oplus\mathbb{R},
\end{aligned}\tag{4.50}
$$

represented by the $V_{\beta}$ lines. Thus the noncompact boson has an $\mathbb{R}$-valued topological symmetry generated by

$$
\begin{aligned}
V_{\beta},\qquad\beta\in\mathbb{R}.
\end{aligned}\tag{4.51}
$$

Its action on the local primary $\mathcal{O}^{(\infty)}_{\alpha}$ is determined by the BF braiding:

$$
\begin{aligned}
V_{\beta}:\quad\mathcal{O}^{(\infty)}_{\alpha}\longmapsto\exp\!\left(2\pi i\,\beta\alpha\right)\mathcal{O}^{(\infty)}_{\alpha}.
\end{aligned}\tag{4.52}
$$

Thus $\mathcal{O}^{(\infty)}_{\alpha}$ carries continuous $\mathbb{R}$-charge $\alpha$. This is the $\mathbb{R}$ symmetry of the noncompact boson.

The other degenerate boundary condition is $L_{0}=0\oplus\mathbb{R}$. Now all $V_{\beta}$ lines can end, and they give rise to local operators $\widetilde{\mathcal{O}}^{(0)}_{\beta},\beta\in\mathbb{R}$. They lie in the charge sector $(\alpha,\beta)=(0,\beta)$ with conformal weights are

$$
\begin{aligned}
h_{\beta}^{(0)}={1\over 4}\beta^{2},\qquad\bar{h}_{\beta}^{(0)}={1\over 4}\beta^{2}.
\end{aligned}\tag{4.53}
$$

These are the primaries of the noncompact dual boson, or equivalently the $R\to 0$ limit of the compact boson. The surviving topological lines on the $L_{0}$ boundary are

$$
\begin{aligned}
\mathbb{D}_{1}/L_{0}\simeq\mathbb{R}\oplus 0,
\end{aligned}\tag{4.54}
$$

represented by $U_{\alpha}$, $\alpha\in\mathbb{R}$. Their action on the local primary $\widetilde{\mathcal{O}}^{(0)}_{\beta}$ is

$$
\begin{aligned}
U_{\alpha}:\quad\widetilde{\mathcal{O}}^{(0)}_{\beta}\longmapsto\exp\!\left(2\pi i\,\alpha\beta\right)\widetilde{\mathcal{O}}^{(0)}_{\beta}.
\end{aligned}\tag{4.55}
$$

Thus $\widetilde{\mathcal{O}}^{(0)}_{\beta}$ carries continuous $\mathbb{R}$-charge $\beta$ under the dual $\mathbb{R}$ symmetry.

Alternatively, these two degenerate boundary conditions also have a simple interpretation as topological gaugings of the compact-boson symmetries. Flat gauging a finite subgroup of, e.g., $\mathbb{Z}_{N}\subset U(1)_{w}$ sends

$$
\begin{aligned}
L_{R}\longmapsto L_{NR}=\left\{\left({n\over NR},wNR\right):n,w\in\mathbb{Z}\right\}.
\end{aligned}\tag{4.56}
$$

Taking $N\to\infty$, this sequence approaches

$$
\begin{aligned}
L_{NR}\longrightarrow L_{\infty}=\mathbb{R}\oplus 0.
\end{aligned}\tag{4.57}
$$

This aligns with the fact that flat gauging the full winding symmetry $U(1)_{w}$ produces the noncompact boson. Similarly, flat gauging a finite subgroup $\mathbb{Z}_{N}\subset U(1)_{m}$ sends

$$
\begin{aligned}
L_{R}\longmapsto L_{R/N}=\left\{\left({Nn\over R},{wR\over N}\right):n,w\in\mathbb{Z}\right\}.
\end{aligned}\tag{4.58}
$$

Taking $N\to\infty$, this approaches

$$
\begin{aligned}
L_{R/N}\longrightarrow L_{0}=0\oplus\mathbb{R},
\end{aligned}\tag{4.59}
$$

producing the noncompact dual boson by flat gauging the full $U(1)_{m}$ symmetry. In this sense the two boundary conditions $L_{\infty}$ and $L_{0}$ are precisely the SymTFT realizations of the $R=\infty$ and $R=0$ endpoints of the compact-boson radius line.

#### Duality and integral measure.

The compact locus of topological boundary conditions contains a discrete redundancy coming from an automorphism of the $\mathbb{R}$-valued BF SymTFT. Namely, the bulk topological theory has an electric-magnetic duality as an invertible automorphism

$$
\begin{aligned}
\mathsf{T}:\qquad a\longleftrightarrow b,
\end{aligned}\tag{4.60}
$$

which exchanges the two factors of the defect group $\mathbb{D}_{1}=\mathbb{R}\oplus\mathbb{R}$. On line labels this acts as

$$
\begin{aligned}
\mathsf{T}:\qquad(\alpha,\beta)\longmapsto(\beta,\alpha),\qquad U_{\alpha}\longleftrightarrow V_{\alpha}.
\end{aligned}\tag{4.61}
$$

This should be regarded as a duality automorphism of the SymTFT, or equivalently as an invertible 2D topological interface.

The reason it becomes the usual $T$-duality of the absolute 2D theory is that it acts compatibly with the fixed physical boundary condition. Indeed, using

$$
\begin{aligned}
A_{\mathrm{L}}=a+b,\qquad A_{\mathrm{R}}=a-b,
\end{aligned}\tag{4.62}
$$

the automorphism $\mathsf{T}$ sends

$$
\begin{aligned}
A_{\mathrm{L}}\longmapsto A_{\mathrm{L}},\qquad A_{\mathrm{R}}\longmapsto-A_{\mathrm{R}}.
\end{aligned}\tag{4.63}
$$

The second transformation is just charge conjugation of the right-moving current algebra. Thus, with our fixed physical boundary condition, $\mathsf{T}$ maps the absolute theory obtained from one topological cap to an isomorphic absolute theory obtained from the transformed cap.

On the compact-boson Lagrangian boundary condition,

$$
\begin{aligned}
L_{R}=\left\{\left({n\over R},wR\right):n,w\in\mathbb{Z}\right\},
\end{aligned}\tag{4.64}
$$

this gives

$$
\begin{aligned}
\mathsf{T}(L_{R})=L_{1/R}.
\end{aligned}\tag{4.65}
$$

Therefore $R$ and $1/R$ label the same absolute compact-boson CFT. In the language of the space of topological boundary conditions, the $\mathbb{Z}_{2}$ generated by $\mathsf{T}$ is a gauge redundancy of the moduli problem, and we should quotient by it:

$$
\begin{aligned}
\mathcal{L}_{\mathrm{comp}}^{(1)}=\mathbb{R}_{>0}/(R\sim R^{-1})\simeq[1,\infty).
\end{aligned}\tag{4.66}
$$

At the self-dual point $R=1$, the $\mathbb{Z}_{2}$ automorphism has a fixed point. Thus the quotient should be understood as an orbifold<sup>8</sup>, although this fixed point has measure zero in the continuous integral below.

The two degenerate maximal isotropic subgroups, $L_{\infty}$ and $L_{0}$ are exchanged by $\mathsf{T}$, aligning with the fact that they correspond to the two endpoints of the radius line. In what follows we first integrate over the compact locus [(4.66)](https://arxiv.org/html/2605.06653v1#S4.E66); the role of the degenerate loci will be visible as a divergence at the end of the integral.

In addition to this discrete duality, the SymTFT also has a continuous automorphism, which is a reparameterization

$$
\begin{aligned}
a\longmapsto\lambda^{-1}a,\qquad b\longmapsto\lambda b,\qquad\lambda\in\mathbb{R}_{>0}.
\end{aligned}\tag{4.67}
$$

At the level of labels for topological line operators, this acts as

$$
\begin{aligned}
(\alpha,\beta)\longmapsto(\lambda^{-1}\alpha,\lambda\beta),
\end{aligned}\tag{4.68}
$$

and therefore scaling the $R$ for topological boundary conditions:

$$
\begin{aligned}
L_{R}\longmapsto L_{\lambda R}.
\end{aligned}\tag{4.69}
$$

Unlike the discrete $T$-duality above, this continuous automorphism is not quotienting out the radius modulus of the absolute compact-boson CFT. With the fixed physical boundary condition, it moves us along the family of topological caps and hence along the compact-boson radius line. Its role is instead to determine the invariant measure on this continuous family of topological boundary conditions.

Before imposing the $T$-duality quotient, the generic compact locus is a free and transitive $\mathbb{R}_{>0}$-orbit. Therefore, the most natural measure, which is invariant under the continuous automorphism [(4.67)](https://arxiv.org/html/2605.06653v1#S4.E67) is the Haar measure on $\mathbb{R}_{>0}$,

$$
\begin{aligned}
d\mu_{C}(R)=C\,{dR\over R},\qquad C>0.
\end{aligned}\tag{4.70}
$$

The constant $C$ is not fixed by this automorphism. In fact, Haar measure is unique only up to an overall multiplicative constant.<sup>9</sup> After quotienting by $R\sim 1/R$, the same measure can be written on the fundamental domain as

$$
\begin{aligned}
d\mu_{C}(R)=C\,{dR\over R},\qquad R\in[1,\infty).
\end{aligned}\tag{4.71}
$$

For a $T$-duality-invariant integrand this is equivalently obtained from $\frac{1}{2}\int_{0}^{\infty}C\,dR/R$, with the factor of $\frac{1}{2}$ implementing the $\mathbb{Z}_{2}$ quotient. The self-dual fixed point should be treated with the usual orbifold stabilizer factor, but it does not affect the continuous integral.

#### Averaging over topological boundary conditions.

Pairing the physical boundary state with $L_{R}$ gives the usual compact-boson partition function

$$
\begin{aligned}
\begin{split}Z_{R}(\tau)=Z_{L_{R}}(T^{2};\tau)&=\langle L_{R};T^{2}|\Psi_{\mathrm{phys}}(T^{2};\tau)\rangle\\
&={1\over|\eta(\tau)|^{2}}\sum_{n,w\in\mathbb{Z}}q^{{1\over 4}(n/R+wR)^{2}}\bar{q}^{{1\over 4}(n/R-wR)^{2}},~~q=e^{2\pi i\tau}.\end{split}
\end{aligned}\tag{4.72}
$$

The factor $1/|\eta(\tau)|^{2}$ comes from the oscillator part of the fixed physical boundary Hamiltonian [(4.23)](https://arxiv.org/html/2605.06653v1#S4.E23). The discrete sum is supplied by the topological boundary condition $L_{R}$, which restricts the allowed charge sectors to

$$
\begin{aligned}
(\alpha,\beta)=\left({n\over R},wR\right),\qquad n,w\in\mathbb{Z}.
\end{aligned}\tag{4.73}
$$

Substituting these charge labels into the zero-mode eigenvalue formula [(4.25)](https://arxiv.org/html/2605.06653v1#S4.E25) gives

$$
\begin{aligned}
p_{\mathrm{L}}={n\over R}+wR,\qquad p_{\mathrm{R}}={n\over R}-wR.
\end{aligned}\tag{4.74}
$$

This matches with the fact that the exponents in [(4.72)](https://arxiv.org/html/2605.06653v1#S4.E72) are precisely the eigenvalues of the current-algebra zero-mode contribution to $L_{0}$ and $\bar{L}_{0}$. Equivalently, the lattice sum in [(4.72)](https://arxiv.org/html/2605.06653v1#S4.E72) is the sum over the local primaries $\mathcal{O}_{n,w}$ selected by the topological boundary condition $L_{R}$.

Combining the previous discussion of duality quotient and the integral measure, the topological-boundary average over the compact-boson locus is thus

$$
\begin{aligned}
\big\langle Z(\tau)\big\rangle_{\mathrm{top},C}^{(c=1)}=\int_{\mathcal{L}_{\mathrm{comp}}^{(1)}}d\mu_{C}(L)\,Z_{L}(T^{2};\tau)=C\int_{1}^{\infty}{dR\over R}\,Z_{R}(\tau).
\end{aligned}\tag{4.75}
$$

In the rest of this subsection we set $C=1$ unless otherwise stated. The integral in [(4.75)](https://arxiv.org/html/2605.06653v1#S4.E75) is over the compact-boson locus only. The degenerate topological boundary conditions $L_{\infty}$ and $L_{0}$ are not integrated over as ordinary points of this Haar orbit; rather, they appear as endpoints in a partial compactification of the radius line.

The expression [(4.75)](https://arxiv.org/html/2605.06653v1#S4.E75) is the rank-one analogue of the Narain average in \[2006.04855\]. Note that it is not a finitely normalized average. Indeed, for $R\to\infty$, the winding sectors with $w\neq 0$ are exponentially suppressed, and the $w=0$ sector gives

$$
\begin{aligned}
Z_{R}(\tau)\sim{1\over|\eta(\tau)|^{2}}\sum_{n\in\mathbb{Z}}\exp\left(-{\pi\tau_{2}n^{2}\over R^{2}}\right).
\end{aligned}\tag{4.76}
$$

By Poisson resummation,

$$
\begin{aligned}
\sum_{n\in\mathbb{Z}}\exp\left(-{\pi\tau_{2}n^{2}\over R^{2}}\right)\sim{R\over\sqrt{\tau_{2}}},\qquad R\to\infty.
\end{aligned}\tag{4.77}
$$

Thus

$$
\begin{aligned}
Z_{R}(\tau)\sim{R\over\sqrt{\tau_{2}}\,|\eta(\tau)|^{2}},\qquad R\to\infty,
\end{aligned}\tag{4.78}
$$

and hence

$$
\begin{aligned}
\int^{\infty}{dR\over R}\,Z_{R}(\tau)\sim{1\over\sqrt{\tau_{2}}\,|\eta(\tau)|^{2}}\int^{\infty}dR=\infty.
\end{aligned}\tag{4.79}
$$

The rank-one average therefore has no normalized probabilistic interpretation. From the present SymTFT viewpoint, this divergence has a simple structural origin: the space of topological boundary conditions as the radius line is noncompact, and its large-radius end approaches the degenerate topological boundary condition $L_{\infty}=\mathbb{R}\oplus 0$, which describes the noncompact boson. The dual endpoint $L_{0}=0\oplus\mathbb{R}$ is obtained by applying $T$-duality. This reintreprets the $c=1$ pathology of Narain averaging as an endpoint effect in the space of topological boundary conditions.

This example is nevertheless useful because it makes the general mechanism explicit. The compact-boson radius is not inserted as a coupling in the local physical boundary condition, nor in the boundary Hamiltonian [(4.23)](https://arxiv.org/html/2605.06653v1#S4.E23). It is supplied by the choice of a topological boundary condition $L_{R}$ of the fixed $\mathbb{R}$-valued BF SymTFT. Averaging over radii is therefore identified with integrating over topological boundary conditions of the SymTFT, where the duality quotient and the integral measure both enjoy a SymTFT interpretation. For higher Narain rank, the same construction leads to the Narain moduli space reproduced by the space topological boundary conditions, and the invariant integral measure becomes the Haar-induced measure on the Narain quotient by dualities.

### 4.2 $c>1$

We now pass from the rank-one compact boson to higher-rank Narain theories \[2006.04855, 2006.04839\]. Throughout this subsection, $c$ denotes the rank of the Narain lattice, equivalently the dimension of the target torus $T^{c}$, i.e., $c_{\mathrm{L}}=c_{\mathrm{R}}=c$. We use the $\mathbb{R}$-valued BF SymTFT introduced at the beginning of this section, with action

$$
\begin{aligned}
S_{\mathrm{BF}}={1\over 2\pi}\int_{X_{3}}\sum_{i=1}^{c}a_{i}\wedge db_{i},\qquad a_{i},b_{i}\in\Omega^{1}(X_{3};\mathbb{R}),
\end{aligned}\tag{4.80}
$$

and line operators

$$
\begin{aligned}
U_{\vec{\alpha}}[\gamma]=\exp\left(i\alpha_{i}\oint_{\gamma}a_{i}\right),\qquad V_{\vec{\beta}}[\gamma]=\exp\left(i\beta_{i}\oint_{\gamma}b_{i}\right),\qquad\vec{\alpha},\vec{\beta}\in\mathbb{R}^{c}.
\end{aligned}\tag{4.81}
$$

The defect group reads

$$
\begin{aligned}
\mathbb{D}_{c}=\mathbb{R}^{c}\oplus\mathbb{R}^{c},
\end{aligned}
$$

with the Dirac pairing

$$
\begin{aligned}
\big\langle(\vec{\alpha},\vec{\beta}),(\vec{\alpha}^{\prime},\vec{\beta}^{\prime})\big\rangle=\vec{\alpha}\cdot\vec{\beta}^{\prime}+\vec{\alpha}^{\prime}\cdot\vec{\beta}\quad\mathrm{mod}\ \mathbb{Z}.
\end{aligned}\tag{4.82}
$$

We also use the quadratic refinement

$$
\begin{aligned}
q(\vec{\alpha},\vec{\beta})=\vec{\alpha}\cdot\vec{\beta}\quad\mathrm{mod}\ \mathbb{Z},
\end{aligned}\tag{4.83}
$$

which controls the spin of the corresponding line.

#### Physical boundary.

The physical boundary condition is the fixed conformal boundary condition at the physical end of the BF slab. It prepares the state

$$
\begin{aligned}
|\Psi_{\mathrm{phys}}(\Sigma;\Omega)\rangle\in\mathcal{H}_{\mathrm{BF}}(\Sigma).
\end{aligned}\tag{4.84}
$$

Introduce the left- and right-moving combinations

$$
\begin{aligned}
A_{\mathrm{L},i}=a_{i}+b_{i},\qquad A_{\mathrm{R},i}=a_{i}-b_{i},\qquad i=1,\ldots,c.
\end{aligned}\tag{4.85}
$$

On the physical boundary $\Sigma$, with local complex coordinates $z,\bar{z}$, the conformal boundary condition is

$$
\begin{aligned}
(A_{\mathrm{L},i})_{\bar{z}}\big|_{\Sigma}=0,\qquad(A_{\mathrm{R},i})_{z}\big|_{\Sigma}=0,\qquad i=1,\ldots,c.
\end{aligned}\tag{4.86}
$$

Equivalently,

$$
\begin{aligned}
(a_{i}+b_{i})_{\bar{z}}\big|_{\Sigma}=0,\qquad(a_{i}-b_{i})_{z}\big|_{\Sigma}=0.
\end{aligned}\tag{4.87}
$$

Thus the physical boundary supplies $c$ left-moving and $c$ right-moving abelian current algebras.

On the Lorentzian boundary cylinder $\Sigma=S^{1}_{\varphi}\times\mathbb{R}_{t}$, the same boundary condition can be written as

$$
\begin{aligned}
(a_{i})_{t}\big|_{\Sigma}=(b_{i})_{\varphi}\big|_{\Sigma},\qquad(b_{i})_{t}\big|_{\Sigma}=(a_{i})_{\varphi}\big|_{\Sigma}.
\end{aligned}\tag{4.88}
$$

The corresponding physical boundary Hamiltonian is fixed once and for all by this conformal boundary condition:

$$
\begin{aligned}
H_{\mathrm{phys}}={1\over 4\pi}\int_{S^{1}}d\varphi\,:\!\sum_{i=1}^{c}\left((a_{i})_{\varphi}^{2}+(b_{i})_{\varphi}^{2}\right)\!:,
\end{aligned}\tag{4.89}
$$

and the spatial momentum is

$$
\begin{aligned}
P_{\mathrm{phys}}={1\over 2\pi}\int_{S^{1}}d\varphi\,:\!\sum_{i=1}^{c}(a_{i})_{\varphi}(b_{i})_{\varphi}\!:.
\end{aligned}\tag{4.90}
$$

Let $\mathsf{P}_{\mathrm{L},i}$ and $\mathsf{P}_{\mathrm{R},i}$ denote the zero-mode charge operators of the left- and right-moving current algebras. A bulk line labelled by $(\vec{\alpha},\vec{\beta})\in\mathbb{D}_{c}$ specifies a charge sector of the physical boundary theory. Here $\vec{\alpha}$ and $\vec{\beta}$ are real charge labels, not dynamical fields. In the charge sector labelled by $(\vec{\alpha},\vec{\beta})$, the zero-mode operators have eigenvalues

$$
\begin{aligned}
\vec{p}_{\mathrm{L}}(\vec{\alpha},\vec{\beta})=\vec{\alpha}+\vec{\beta},\qquad\vec{p}_{\mathrm{R}}(\vec{\alpha},\vec{\beta})=\vec{\alpha}-\vec{\beta}.
\end{aligned}\tag{4.91}
$$

The Virasoro zero-mode operators are

$$
\begin{aligned}
L_{0}={1\over 4}\left|\mathsf{P}_{\mathrm{L}}\right|^{2}+N_{\mathrm{L}},\qquad\bar{L}_{0}={1\over 4}\left|\mathsf{P}_{\mathrm{R}}\right|^{2}+N_{\mathrm{R}}.
\end{aligned}\tag{4.92}
$$

Therefore, in the charge sector $(\vec{\alpha},\vec{\beta})$, their eigenvalues are

$$
\begin{aligned}
h_{\vec{\alpha},\vec{\beta};N_{\mathrm{L}}}={1\over 4}\left|\vec{\alpha}+\vec{\beta}\right|^{2}+N_{\mathrm{L}},\qquad\bar{h}_{\vec{\alpha},\vec{\beta};N_{\mathrm{R}}}={1\over 4}\left|\vec{\alpha}-\vec{\beta}\right|^{2}+N_{\mathrm{R}}.
\end{aligned}\tag{4.93}
$$

Thus

$$
\begin{aligned}
H_{\mathrm{phys}}=L_{0}+\bar{L}_{0}-{c\over 12},\qquad P_{\mathrm{phys}}=L_{0}-\bar{L}_{0}.
\end{aligned}\tag{4.94}
$$

The Narain moduli do not appear in this local physical boundary Hamiltonian. They enter only through the choice of topological cap.

#### Continuous compact topological boundary conditions.

A compact topological boundary condition is a discrete Lagrangian subgroup

$$
\begin{aligned}
L\subset\mathbb{D}_{c}.
\end{aligned}\tag{4.95}
$$

More explicitly, $L$ is associated with a rank-$2c$ lattice satisfying

$$
\begin{aligned}
q(\ell)\in\mathbb{Z},\qquad\big\langle\ell,\ell^{\prime}\big\rangle\in\mathbb{Z},\qquad\ell,\ell^{\prime}\in L,
\end{aligned}\tag{4.96}
$$

together with the maximality condition

$$
\begin{aligned}
L\cong L^{\perp},\qquad L^{\perp}:=\left\{x\in\mathbb{D}_{c}:\big\langle x,\ell\big\rangle\in\mathbb{Z}\ \mathrm{for\ all}\ \ell\in L\right\}.
\end{aligned}\tag{4.97}
$$

The condition $q(\ell)\in\mathbb{Z}$ says that the lines ending on the topological boundary are bosonic<sup>10</sup>. The condition $\langle\ell,\ell^{\prime}\rangle\in\mathbb{Z}$ says that all lines within $L$ have mutually trivial braiding. The maximality condition says that every line trivially-braiding with those in $L$ is already in $L$. In other words, this maximal isotropic condition tells us the lattice associated to $L$ is even self-dual in $\mathbb{R}^{c,c}$, but in the SymTFT language written in the $(\vec{\alpha},\vec{\beta})$ polarization determined by the BF line operators.

We now parameterize these compact topological boundary conditions explicitly from the SymTFT. Start from a compact boundary as the reference boundary condition

$$
\begin{aligned}
L_{\circ}=\left\{(\vec{n},\vec{w}):\vec{n},\vec{w}\in\mathbb{Z}^{c}\right\}\subset\mathbb{D}_{c}=\mathbb{R}^{c}\oplus\mathbb{R}^{c}.
\end{aligned}\tag{4.98}
$$

The pairing on $L_{\circ}$ is

$$
\begin{aligned}
\big\langle(\vec{n},\vec{w}),(\vec{n}^{\prime},\vec{w}^{\prime})\big\rangle=\vec{n}\cdot\vec{w}^{\prime}+\vec{n}^{\prime}\cdot\vec{w}\in\mathbb{Z},
\end{aligned}\tag{4.99}
$$

and the quadratic refinement is

$$
\begin{aligned}
q(\vec{n},\vec{w})=\vec{n}\cdot\vec{w}\in\mathbb{Z}.
\end{aligned}\tag{4.100}
$$

Conversely, if $x=(\vec{\alpha},\vec{\beta})\in\mathbb{D}_{c}$ pairs integrally with every $(\vec{n},\vec{w})\in L_{\circ}$, then

$$
\begin{aligned}
\vec{\alpha}\cdot\vec{w}+\vec{\beta}\cdot\vec{n}\in\mathbb{Z}\qquad\forall\,\vec{n},\vec{w}\in\mathbb{Z}^{c}.
\end{aligned}\tag{4.101}
$$

Taking $\vec{w}=0$ implies $\vec{\beta}\in\mathbb{Z}^{c}$, and taking $\vec{n}=0$ implies $\vec{\alpha}\in\mathbb{Z}^{c}$. Hence $x\in L_{\circ}$, so

$$
\begin{aligned}
L_{\circ}=L_{\circ}^{\perp}.
\end{aligned}\tag{4.102}
$$

Therefore, $L_{\circ}$ is a compact Lagrangian boundary condition of the BF SymTFT. In fact, it is the higher-rank analogue of the self-dual-radius boundary at $R=1$ in the $c=1$ example.

In order to find other topological boundary conditions from this reference one, we determine the relevant automorphism group of the BF theory. Introduce the $2c$-component vector of gauge fields

$$
\begin{aligned}
\mathcal{A}=\begin{pmatrix}a_{1}\\
\vdots\\
a_{c}\\
b_{1}\\
\vdots\\
b_{c}\end{pmatrix},\qquad\eta=\begin{pmatrix}0&\mathbf{1}_{c}\\
\mathbf{1}_{c}&0\end{pmatrix}.
\end{aligned}\tag{4.103}
$$

Up to a total derivative, the BF action can be written in the following symmetric form

$$
\begin{aligned}
S_{\mathrm{BF}}={1\over 4\pi}\int_{X_{3}}\mathcal{A}^{T}\eta\,d\mathcal{A}.
\end{aligned}\tag{4.104}
$$

Indeed,

$$
\begin{aligned}
{1\over 4\pi}\int\mathcal{A}^{T}\eta\,d\mathcal{A}={1\over 4\pi}\int\sum_{i=1}^{c}\left(a_{i}\wedge db_{i}+b_{i}\wedge da_{i}\right)={1\over 2\pi}\int\sum_{i=1}^{c}a_{i}\wedge db_{i}
\end{aligned}\tag{4.105}
$$

on a closed three-manifold, or modulo the boundary polarization on a slab.

Now consider a constant linear transformation of variables

$$
\begin{aligned}
\mathcal{A}\longmapsto N\mathcal{A},\qquad N\in GL(2c,\mathbb{R}).
\end{aligned}\tag{4.106}
$$

The action becomes

$$
\begin{aligned}
S_{\mathrm{BF}}\longmapsto{1\over 4\pi}\int\mathcal{A}^{T}N^{T}\eta N\,d\mathcal{A}.
\end{aligned}\tag{4.107}
$$

This field redefinition is an automorphism of the BF SymTFT precisely when

$$
\begin{aligned}
N^{T}\eta N=\eta.
\end{aligned}\tag{4.108}
$$

Therefore, the bulk SymTFT heory has a continuous group of linear automorphisms

$$
\begin{aligned}
O(c,c;\mathbb{R})=\left\{N\in GL(2c,\mathbb{R}):N^{T}\eta N=\eta\right\}.
\end{aligned}\tag{4.109}
$$

This is a statement about the automorphisms of the $\mathbb{R}$-valued BF theory, or equivalently about invertible topological interfaces (i.e. 0-form symmetry operators) of the SymTFT. It is not yet a quotient by physical equivalences of the absolute boundary CFT.

Let us now see the same group directly from the line operators. For a line labelled by

$$
\begin{aligned}
x=(\vec{\alpha},\vec{\beta})\in\mathbb{D}_{c}=\mathbb{R}^{c}\oplus\mathbb{R}^{c},
\end{aligned}\tag{4.110}
$$

write

$$
\begin{aligned}
\mathcal{W}_{x}[\gamma]:=U_{\vec{\alpha}}[\gamma]V_{\vec{\beta}}[\gamma]=\exp\left(i\oint_{\gamma}x^{T}\mathcal{A}\right).
\end{aligned}\tag{4.111}
$$

The Dirac pairing can be written as

$$
\begin{aligned}
\langle x,y\rangle=x^{T}\eta y\quad\mathrm{mod}\ \mathbb{Z}.
\end{aligned}\tag{4.112}
$$

Equivalently, the braiding phase is

$$
\begin{aligned}
\mathcal{W}_{x}[\gamma_{1}]\mathcal{W}_{y}[\gamma_{2}]=\exp\left(2\pi i\,x^{T}\eta y\,\mathrm{Link}(\gamma_{1},\gamma_{2})\right)\mathcal{W}_{y}[\gamma_{2}]\mathcal{W}_{x}[\gamma_{1}].
\end{aligned}\tag{4.113}
$$

A general field transformation $\mathcal{A}\mapsto N\mathcal{A}$ sends the line label to

$$
\begin{aligned}
x\longmapsto N^{T}x.
\end{aligned}\tag{4.114}
$$

Given $N\in O(c,c;\mathbb{R})$, this preserves the Dirac pairing / line braiding:

$$
\begin{aligned}
\langle N^{T}x,N^{T}y\rangle=x^{T}N\eta N^{T}y=x^{T}\eta y=\langle x,y\rangle.
\end{aligned}\tag{4.115}
$$

Equivalently, we may describe the induced automorphism directly on the defect group by

$$
\begin{aligned}
x\longmapsto gx,\qquad g\in O(c,c;\mathbb{R}),\qquad g^{T}\eta g=\eta.
\end{aligned}\tag{4.116}
$$

Note that we haven not used the Narain CFT as an input to obtain this $O(c,c;\mathbb{R})$; it is the group of linear automorphisms of the SymTFT defect data preserving the braiding.

Now choose the reference compact topological boundary condition

$$
\begin{aligned}
L_{\circ}=\left\{(\vec{n},\vec{w}):\vec{n},\vec{w}\in\mathbb{Z}^{c}\right\}\subset\mathbb{D}_{c}.
\end{aligned}\tag{4.117}
$$

For any $g\in O(c,c;\mathbb{R})$ we can define

$$
\begin{aligned}
L_{g}=gL_{\circ}.
\end{aligned}\tag{4.118}
$$

This is again a compact Lagrangian topological boundary condition. To see this, let $\ell_{1},\ell_{2}\in L_{\circ}$, then the braiding-preserving tells us

$$
\begin{aligned}
\langle g\ell_{1},g\ell_{2}\rangle=\langle\ell_{1},\ell_{2}\rangle\in\mathbb{Z},
\end{aligned}\tag{4.119}
$$

and similarly

$$
\begin{aligned}
q(g\ell)=q(\ell)\in\mathbb{Z}.
\end{aligned}\tag{4.120}
$$

Moreover,

$$
\begin{aligned}
(gL_{\circ})^{\perp}=g(L_{\circ}^{\perp})=gL_{\circ}.
\end{aligned}\tag{4.121}
$$

Thus acting with the SymTFT automorphism group on the reference Lagrangian boundary produces another allowed topological cap. From a defect perspective, this amounts to pushing invertible topological surfaces labeled by $O(c,c;\mathbb{R})$ elements onto the reference topological boundary $L_{\circ}$ and transform it to $gL_{\circ}$. This is the intrinsic SymTFT origin of the continuous family of compact topological boundary conditions, which correspond to Narain moduli before the quotient.

As in $c=1$, where the modulus $R$ labeling different CFTs can enter the parameterization of topological boundary conditions explicitly, we now present how the usual torus sigma-model moduli, metric and $B$-field, can enter the space of topological boundary conditions. Without any input from Narain CFTs, we set

$$
\begin{aligned}
G=G^{T}>0,\qquad B^{T}=-B,
\end{aligned}\tag{4.122}
$$

where $G$ is a positive definite symmetric matrix and $B$ is an antisymmetric matrix. We choose the positive square root of $G$,

$$
\begin{aligned}
e=G^{1/2},\qquad e^{T}=e,\qquad e^{2}=G,
\end{aligned}\tag{4.123}
$$

and then define a linear map on the defect group $\mathbb{D}_{c}=\mathbb{R}^{c}\oplus\mathbb{R}^{c}$ by

$$
\begin{aligned}
g_{G,B}=\begin{pmatrix}e^{-T}&e^{-T}B\\
0&e\end{pmatrix}.
\end{aligned}\tag{4.124}
$$

More explicitly, on a line defect labeled by $x=(\vec{\alpha},\vec{\beta})$, $g_{G,B}$ acts as

$$
\begin{aligned}
g_{G,B}:\begin{pmatrix}\vec{\alpha}\\
\vec{\beta}\end{pmatrix}\longmapsto\begin{pmatrix}e^{-T}(\vec{\alpha}+B\vec{\beta})\\
e\vec{\beta}\end{pmatrix}.
\end{aligned}\tag{4.125}
$$

It is easy to check $g_{G,B}$ satisfies

$$
\begin{aligned}
\begin{split}g_{G,B}^{T}\eta g_{G,B}&=\begin{pmatrix}e^{-1}&0\\
B^{T}e^{-1}&e^{T}\end{pmatrix}\begin{pmatrix}0&e\\
e^{-T}&e^{-T}B\end{pmatrix}\\
&=\begin{pmatrix}0&\mathbf{1}_{c}\\
\mathbf{1}_{c}&B^{T}+B\end{pmatrix}=\begin{pmatrix}0&\mathbf{1}_{c}\\
\mathbf{1}_{c}&0\end{pmatrix}=\eta,\end{split}
\end{aligned}\tag{4.126}
$$

where we used $B^{T}=-B$. Therefore $g_{G,B}$ parametrizes the $O(c,c;\mathbb{R})$ automorphism of the SymTFT defect data.

Applying this defect automorphism to the reference boundary $L_{\circ}$ gives an explicit expression of the topological boundary condition

$$
\begin{aligned}
L_{G,B}=\left\{\left(e^{-T}(\vec{n}+B\vec{w}),e\vec{w}\right):\vec{n},\vec{w}\in\mathbb{Z}^{c}\right\}\subset\mathbb{D}_{c}.
\end{aligned}\tag{4.127}
$$

That is to say, $G$ and $B$ appear as coordinates on the SymTFT family of compact topological boundary conditions. Note that the above derivation requires no input from the physical boundary Hamiltonian. Rather, we are just characterizing which SymTFT line defects $(\vec{\alpha},\vec{\beta})$ are allowed to end on the topological boundary, and the characterization happens to match the Narain moduli $G$ and $B$.

Although the above discussion is sufficient to see $L_{G,B}$ generated by $g_{G,B}$ is topological boundary condition, let us still check the Lagrangian condition explicitly. Write an element in the defect group as

$$
\begin{aligned}
\ell_{G,B}(\vec{n},\vec{w})=\left(\vec{\alpha}_{G,B}(\vec{n},\vec{w}),\vec{\beta}_{G,B}(\vec{n},\vec{w})\right)=\left(e^{-T}(\vec{n}+B\vec{w}),e\vec{w}\right).
\end{aligned}\tag{4.128}
$$

For two such elements,

$$
\begin{aligned}
\ell=\ell_{G,B}(\vec{n},\vec{w}),\qquad\ell^{\prime}=\ell_{G,B}(\vec{n}^{\prime},\vec{w}^{\prime}),
\end{aligned}
$$

the Dirac pairing is

$$
\begin{aligned}
\begin{split}\langle\ell,\ell^{\prime}\rangle&=\vec{\alpha}_{G,B}(\vec{n},\vec{w})\cdot\vec{\beta}_{G,B}(\vec{n}^{\prime},\vec{w}^{\prime})+\vec{\alpha}_{G,B}(\vec{n}^{\prime},\vec{w}^{\prime})\cdot\vec{\beta}_{G,B}(\vec{n},\vec{w})\\
&=(\vec{n}+B\vec{w})\cdot\vec{w}^{\prime}+(\vec{n}^{\prime}+B\vec{w}^{\prime})\cdot\vec{w}\\
&=\vec{n}\cdot\vec{w}^{\prime}+\vec{n}^{\prime}\cdot\vec{w}\in\mathbb{Z}.\end{split}
\end{aligned}\tag{4.129}
$$

The $B$-dependent terms cancel because $B$ is antisymmetric:

$$
\begin{aligned}
(B\vec{w})\cdot\vec{w}^{\prime}+(B\vec{w}^{\prime})\cdot\vec{w}=\vec{w}^{T}B^{T}\vec{w}^{\prime}+\vec{w}^{\prime T}B^{T}\vec{w}=-\vec{w}^{T}B\vec{w}^{\prime}-\vec{w}^{\prime T}B\vec{w}=0.
\end{aligned}
$$

Similarly,

$$
\begin{aligned}
q(\ell)=\vec{\alpha}_{G,B}(\vec{n},\vec{w})\cdot\vec{\beta}_{G,B}(\vec{n},\vec{w})=(\vec{n}+B\vec{w})\cdot\vec{w}=\vec{n}\cdot\vec{w}\in\mathbb{Z},
\end{aligned}\tag{4.130}
$$

because $\vec{w}^{T}B\vec{w}=0$. Thus the lines in $L_{G,B}$ are bosonic and have mutually trivial braiding. Finally, since $g_{G,B}$ preserves the pairing,

$$
\begin{aligned}
L_{G,B}^{\perp}=(g_{G,B}L_{\circ})^{\perp}=g_{G,B}(L_{\circ}^{\perp})=g_{G,B}L_{\circ}=L_{G,B}.
\end{aligned}\tag{4.131}
$$

Therefore $L_{G,B}$ is a compact Lagrangian topological boundary condition.

Another quick consistency check is to consider $c=1$, where we have

$$
\begin{aligned}
G=R^{2},\qquad B=0,\qquad e=R,
\end{aligned}\tag{4.132}
$$

and thus

$$
\begin{aligned}
L_{G,B}=\left\{\left({n\over R},wR\right):n,w\in\mathbb{Z}\right\}=L_{R},
\end{aligned}\tag{4.133}
$$

which exactly reduces to the $R$-labeled topological boundary conditions.

#### Local primaries and surviving symmetry lines.

We now explain the operator content of the absolute 2D theory obtained via a topological boundary condition $L$. The elements of $L$ are precisely the bulk line labels that become trivial on the topological boundary. Thus, for each $\ell=(\vec{\alpha},\vec{\beta})\in L$, the composite bulk line

$$
\begin{aligned}
\mathcal{W}_{\ell}[\gamma]:=U_{\vec{\alpha}}[\gamma]V_{\vec{\beta}}[\gamma]
\end{aligned}\tag{4.134}
$$

can end on the topological boundary. If we bring the other endpoint of this line to the physical boundary, it creates a local operator of the absolute 2D theory. We denote this local operator by $\mathcal{O}_{\ell}$. In this sense, the Lagrangian subgroup $L$ gives the current-algebra primary spectrum of the absolute CFT.

The conformal weights of $\mathcal{O}_{\ell}$ are read using the fixed physical boundary condition. Namely, the zero-mode eigenvalues in the charge sector $\ell=(\vec{\alpha},\vec{\beta})$ are

$$
\begin{aligned}
\vec{p}_{\mathrm{L}}(\ell)=\vec{\alpha}+\vec{\beta},\qquad\vec{p}_{\mathrm{R}}(\ell)=\vec{\alpha}-\vec{\beta}.
\end{aligned}\tag{4.135}
$$

Therefore, before adding oscillator descendants,

$$
\begin{aligned}
h_{\ell}={1\over 4}\left|\vec{p}_{\mathrm{L}}(\ell)\right|^{2},\qquad\bar{h}_{\ell}={1\over 4}\left|\vec{p}_{\mathrm{R}}(\ell)\right|^{2}.
\end{aligned}\tag{4.136}
$$

Moreover,

$$
\begin{aligned}
h_{\ell}-\bar{h}_{\ell}=\vec{\alpha}\cdot\vec{\beta}=q(\ell)\in\mathbb{Z},
\end{aligned}\tag{4.137}
$$

so the endpoint operator has integer spin in the bosonic 2D theory. This is the operator-theoretic meaning of the condition $q(\ell)\in\mathbb{Z}$.

For the boundary condition $L_{G,B}$, parameterized by $G$ and $B$, the condensed lines are labelled by $\vec{n},\vec{w}\in\mathbb{Z}^{c}$ through

$$
\begin{aligned}
\ell_{G,B}(\vec{n},\vec{w})=\left(e^{-T}(\vec{n}+B\vec{w}),e\vec{w}\right)\in L_{G,B}.
\end{aligned}\tag{4.138}
$$

The corresponding local primary is denoted by $\mathcal{O}_{\vec{n},\vec{w}}^{G,B}$. Its left- and right-moving momenta are

$$
\begin{aligned}
\vec{p}_{\mathrm{L}}(\vec{n},\vec{w};G,B)=e^{-T}\bigl(\vec{n}+(B+G)\vec{w}\bigr),\qquad\vec{p}_{\mathrm{R}}(\vec{n},\vec{w};G,B)=e^{-T}\bigl(\vec{n}+(B-G)\vec{w}\bigr).
\end{aligned}\tag{4.139}
$$

and the corresponding conformal weights are

$$
\begin{aligned}
h_{\vec{n},\vec{w}}^{G,B}={1\over 4}\left|e^{-T}\bigl(\vec{n}+(B+G)\vec{w}\bigr)\right|^{2},\qquad\bar{h}_{\vec{n},\vec{w}}^{G,B}={1\over 4}\left|e^{-T}\bigl(\vec{n}+(B-G)\vec{w}\bigr)\right|^{2},
\end{aligned}\tag{4.140}
$$

That is to say, the familiar Narain primary labeled by momentum and winding quantum numbers $(\vec{n},\vec{w})$ is now realized from the SymTFT line $\mathcal{W}_{\ell_{G,B}(\vec{n},\vec{w})}$.

We now discuss the topological symmetry lines of the absolute theory. A general bulk line labelled by

$$
\begin{aligned}
\gamma=(\vec{\rho},\vec{\sigma})\in\mathbb{D}_{c}
\end{aligned}\tag{4.141}
$$

can be laid on the topological boundary. However, two such lines define the same boundary topological defect if they differ by a line that is trivialized by the boundary condition $L$. Therefore the surviving topological line operators are labelled by $\mathbb{D}_{c}/L$ \[2401.10165\]. Their action on the local primaries is determined by the braiding of bulk lines. Namely,

$$
\begin{aligned}
\gamma:\quad\mathcal{O}_{\ell}\longmapsto\exp\!\left(2\pi i\,\big\langle\gamma,\ell\big\rangle\right)\mathcal{O}_{\ell}.
\end{aligned}\tag{4.142}
$$

This action is well-defined on the quotient $\mathbb{D}_{c}/L$, because shifting $\gamma$ by an element of $L$ changes the phase by an integer multiple of $2\pi i$.

For $L=L_{G,B}$, the quotient $\mathbb{D}_{c}/L_{G,B}$ is a $2c$-torus. A convenient representative of its elements is

$$
\begin{aligned}
\gamma_{\vec{\vartheta}_{\mathrm{m}},\vec{\vartheta}_{\mathrm{w}}}=\left(e^{-T}\bigl(\vec{\vartheta}_{\mathrm{w}}+B\vec{\vartheta}_{\mathrm{m}}\bigr),e\vec{\vartheta}_{\mathrm{m}}\right),\qquad\vec{\vartheta}_{\mathrm{m}},\vec{\vartheta}_{\mathrm{w}}\in\mathbb{R}^{c}/\mathbb{Z}^{c}.
\end{aligned}\tag{4.143}
$$

The periodicity follows because shifting

$$
\begin{aligned}
\vec{\vartheta}_{\mathrm{m}}\mapsto\vec{\vartheta}_{\mathrm{m}}+\vec{r},\qquad\vec{\vartheta}_{\mathrm{w}}\mapsto\vec{\vartheta}_{\mathrm{w}}+\vec{s},\qquad\vec{r},\vec{s}\in\mathbb{Z}^{c},
\end{aligned}
$$

changes $\gamma_{\vec{\vartheta}_{\mathrm{m}},\vec{\vartheta}_{\mathrm{w}}}$ by

$$
\begin{aligned}
\left(e^{-T}(\vec{s}+B\vec{r}),e\vec{r}\right)=\ell_{G,B}(\vec{s},\vec{r})\in L_{G,B}.
\end{aligned}
$$

Therefore $\vec{\vartheta}_{\mathrm{m}}$ and $\vec{\vartheta}_{\mathrm{w}}$ indeed parametrize two $c$-dimensional compact symmetry groups.

The action of this surviving line on the primary $\mathcal{O}_{\vec{n},\vec{w}}^{G,B}$ is

$$
\begin{aligned}
\begin{split}\big\langle\gamma_{\vec{\vartheta}_{\mathrm{m}},\vec{\vartheta}_{\mathrm{w}}},\ell_{G,B}(\vec{n},\vec{w})\big\rangle&=\bigl(\vec{\vartheta}_{\mathrm{w}}+B\vec{\vartheta}_{\mathrm{m}}\bigr)\cdot\vec{w}+\bigl(\vec{n}+B\vec{w}\bigr)\cdot\vec{\vartheta}_{\mathrm{m}}\\
&=\vec{\vartheta}_{\mathrm{w}}\cdot\vec{w}+\vec{\vartheta}_{\mathrm{m}}\cdot\vec{n}\quad\mathrm{mod}\ \mathbb{Z},\end{split}
\end{aligned}\tag{4.144}
$$

where the $B$-dependent terms cancel because $B^{T}=-B$. Hence

$$
\begin{aligned}
\gamma_{\vec{\vartheta}_{\mathrm{m}},\vec{\vartheta}_{\mathrm{w}}}:\quad\mathcal{O}_{\vec{n},\vec{w}}^{G,B}\longmapsto\exp\!\left[2\pi i\left(\vec{\vartheta}_{\mathrm{m}}\cdot\vec{n}+\vec{\vartheta}_{\mathrm{w}}\cdot\vec{w}\right)\right]\mathcal{O}_{\vec{n},\vec{w}}^{G,B}.
\end{aligned}\tag{4.145}
$$

Thus $\mathcal{O}_{\vec{n},\vec{w}}^{G,B}$ carries charges

$$
\begin{aligned}
(Q_{\mathrm{m}},Q_{\mathrm{w}})=(\vec{n},\vec{w})
\end{aligned}\tag{4.146}
$$

under

$$
\begin{aligned}
U(1)_{\mathrm{m}}^{\,c}\times U(1)_{\mathrm{w}}^{\,c}.
\end{aligned}\tag{4.147}
$$

Here $U(1)_{\mathrm{m}}^{\,c}$ is generated by the parameter $\vec{\vartheta}_{\mathrm{m}}$, and measures momentum charge $\vec{n}$, while $U(1)_{\mathrm{w}}^{\,c}$ is generated by $\vec{\vartheta}_{\mathrm{w}}$, and measures winding charge $\vec{w}$.

#### Noncompact topological boundary conditions.

The compact Narain boundary conditions $L_{G,B}$ are not the only maximal isotropic subgroups of $\mathbb{D}_{c}$. They are the ones relevant for compact torus CFTs, since they associate with discrete rank-$2c$ lattices. The enlarged space of topological boundary conditions also contains degenerate maximal isotropic subgroups which are continuous. The simplest examples are

$$
\begin{aligned}
L_{\infty}^{(c)}=\mathbb{R}^{c}\oplus 0,\qquad L_{0}^{(c)}=0\oplus\mathbb{R}^{c}.
\end{aligned}\tag{4.148}
$$

Similarly to $c=1$ case, it is straightforward to check they are Lagrangian. Physically, $L_{\infty}^{(c)}$ describes $c$ noncompact bosons, while $L_{0}^{(c)}$ describes their dual noncompact bosons. They are the higher-rank analogues of the $R=\infty$ and $R=0$ endpoints in the $c=1$ discussion.

More generally, one may decompactify only part of the compact Lagrangian boundary condition. After choosing a splitting

$$
\begin{aligned}
\mathbb{D}_{c}=\mathbb{D}_{r}\oplus\mathbb{D}_{c-r},\qquad\mathbb{D}_{r}=\mathbb{R}^{r}\oplus\mathbb{R}^{r},
\end{aligned}\tag{4.149}
$$

one can consider boundary conditions of the form

$$
\begin{aligned}
L_{\infty,r;G_{\perp},B_{\perp}}=\bigl(\mathbb{R}^{r}\oplus 0\bigr)\oplus L_{G_{\perp},B_{\perp}},
\end{aligned}\tag{4.150}
$$

or

$$
\begin{aligned}
L_{0,r;G_{\perp},B_{\perp}}=\bigl(0\oplus\mathbb{R}^{r}\bigr)\oplus L_{G_{\perp},B_{\perp}}.
\end{aligned}\tag{4.151}
$$

Here $L_{G_{\perp},B_{\perp}}\subset\mathbb{D}_{c-r}$ is an ordinary compact Narain boundary condition for the remaining $c-r$ compact directions. Thus $L_{\infty,r;G_{\perp},B_{\perp}}$ describes $r$ noncompact bosons together with a compact Narain theory of rank $c-r$, while $L_{0,r;G_{\perp},B_{\perp}}$ describes the corresponding dual noncompact directions.

These noncompact boundary conditions arise as degeneration of compact Narain topological boundaries. For example, take $B=0$ and

$$
\begin{aligned}
G=\mathrm{diag}\bigl(R_{1}^{2},\ldots,R_{r}^{2},G_{\perp}\bigr).
\end{aligned}\tag{4.152}
$$

Then the compact boundary condition contains charge labels

$$
\begin{aligned}
\left({n_{1}\over R_{1}},\ldots,{n_{r}\over R_{r}};w_{1}R_{1},\ldots,w_{r}R_{r}\right)
\end{aligned}\tag{4.153}
$$

in the first $r$ directions. Sending $R_{1},\ldots,R_{r}\to\infty$, the momentum labels $n_{i}/R_{i}$ become continuous while the winding sectors with $w_{i}\neq 0$ are pushed to infinite energy in the physical boundary Hamiltonian. The limiting topological boundary condition is thus of the form [(4.150)](https://arxiv.org/html/2605.06653v1#S4.E150). Sending $R_{i}\to 0$ instead gives the dual boundary condition [(4.151)](https://arxiv.org/html/2605.06653v1#S4.E151).

The compact Narain average considered below integrates only over the compact Narain locus of discrete lattices $L_{G,B}$. The degenerate boundary conditions [(4.148)](https://arxiv.org/html/2605.06653v1#S4.E148)–[(4.151)](https://arxiv.org/html/2605.06653v1#S4.E151) are not ordinary points of the space of Lagrangian boundaries whose integral measure for averaging will be shown to be Haar measure as in $c=1$ case. Rather, they should be regarded as boundary or cusp loci in a partial compactification of the topological-boundary space. Their role is nevertheless important for understanding convergence: divergences of Narain averages arise precisely from regions of the compact Narain locus that approach such noncompact limits.

#### Dualities and integral measure.

Having determined the parametrization of the (compact) topological boundary conditions is given by $O(c,c;\mathbb{R})$, the next natural question to ask is what is the genuine space we want to average over, and whether that matches the Narain moduli space. This requires us to identify redundancies in this parametrization. First, the reference Lagrangian lattice $L_{\circ}\simeq\mathbb{Z}^{c}\oplus\mathbb{Z}^{c}$ has an automorphism group,

$$
\begin{aligned}
O(c,c;\mathbb{Z})=\mathrm{Aut}(L_{\circ},\langle\,,\,\rangle,q).
\end{aligned}\tag{4.154}
$$

Acting on the integer labels $(\vec{n},\vec{w})$, this group preserves the integral Dirac pairing and the quadratic refinement associated to spins. We thus have

$$
\begin{aligned}
g\gamma L_{\circ}=gL_{\circ},\qquad\gamma\in O(c,c;\mathbb{Z}),
\end{aligned}\tag{4.155}
$$

which means $O(c,c;\mathbb{Z})$ is a redundancy in the parametrization of the same compact topological boundary condition. In the absolute 2D CFT, this is the familiar integral T-duality group. It includes changes of integral torus basis, integral $B$-field shifts, and factorized dualities.

There is also a continuous frame redundancy associated with the fixed physical boundary condition<sup>11</sup>. Recall that the Hamiltonian supported on the physical boundary only depends on the Euclidean norms

$$
\begin{aligned}
|\vec{p}_{\mathrm{L}}|^{2},\qquad|\vec{p}_{\mathrm{R}}|^{2}.
\end{aligned}\tag{4.156}
$$

Therefore independent orthogonal rotations

$$
\begin{aligned}
\vec{p}_{\mathrm{L}}\longmapsto O_{\mathrm{L}}\vec{p}_{\mathrm{L}},\qquad\vec{p}_{\mathrm{R}}\longmapsto O_{\mathrm{R}}\vec{p}_{\mathrm{R}},\qquad O_{\mathrm{L}},O_{\mathrm{R}}\in O(c),
\end{aligned}\tag{4.157}
$$

only change the orthonormal frame of the left- and right-moving current algebras. They do not change the absolute CFT. Thus, after fixing the physical boundary condition, the compact component of the space of topological boundary conditions is

$$
\begin{aligned}
\mathcal{L}_{\mathrm{Narain}}^{(c)}=O(c,c;\mathbb{Z})\backslash O(c,c;\mathbb{R})/\bigl(O(c)\times O(c)\bigr).
\end{aligned}\tag{4.158}
$$

Equivalently, with the convention $L_{g}=gL_{\circ}$, one may first quotient on the right by the automorphisms of $L_{\circ}$ and then quotient by the left/right frame rotations; the two descriptions are related by $g\mapsto g^{-1}$. This is exactly the usual Narain moduli space, now obtained as the space of compact topological boundary conditions of the fixed $\mathbb{R}$-valued BF SymTFT.

Before performing the averaging, let us decide the measure from the same SymTFT automorphism principle. Since $O(c,c;\mathbb{R})$ is the continuous automorphism group preserving the BF braiding data, the natural measure on the orbit of compact Lagrangian boundaries is the measure induced from Haar measure on $O(c,c;\mathbb{R})$. Descending this measure through the discrete quotient by $O(c,c;\mathbb{Z})$ and the frame quotient by $O(c)\times O(c)$ gives an invariant measure on $\mathcal{L}_{\mathrm{Narain}}^{(c)}$. We denote it by

$$
\begin{aligned}
d\mu(L).
\end{aligned}\tag{4.159}
$$

This is the continuous version of the groupoid measure discussed in Section [2.2](https://arxiv.org/html/2605.06653v1#S2.SS2): the finite groupoid factor $1/|\mathrm{Aut}(L)|$ is replaced by the Haar measure on the quotient of the continuous automorphism orbit.

The overall normalization of $d\mu(L)$ is conventional. In a $G,B$ coordinate patch, the Haar-induced measure can be written, up to an overall constant, as

$$
\begin{aligned}
d\mu(G,B)=C_{\mathrm{Nar}}\,{\displaystyle\prod_{1\leq i\leq j\leq c}dG_{ij}\prod_{1\leq i<j\leq c}dB_{ij}\over(\det G)^{c}}.
\end{aligned}\tag{4.160}
$$

For $c=1$, this reduces to $dG/G=2\,dR/R$, which agrees with the radius Haar measure of the previous subsection up to the expected overall normalization.

This Haar-induced measure is the same measure that appears in the standard Narain average. From the 2D CFT point of view, the Narain moduli space carries the Zamolodchikov metric, and its associated volume form agrees with the locally homogeneous measure on

$$
\begin{aligned}
O(c,c;\mathbb{Z})\backslash O(c,c;\mathbb{R})/(O(c)\times O(c)).
\end{aligned}
$$

From the SymTFT viewpoint, the same measure is obtained because the space of compact topological caps is an $O(c,c;\mathbb{R})$-orbit and the averaging measure must be invariant under this defect-data automorphism group. Thus the SymTFT construction reproduces both the Narain moduli space \[Narain:1985jj, Narain:1986am\] and the natural Narain averaging measure \[2006.04839, 2006.04855\].

For $c>1$, the Haar volume of the compact Narain quotient is finite. Hence one may use the normalized measure

$$
\begin{aligned}
d\widehat{\mu}(L)={d\mu(L)\over\mathrm{Vol}\!\left(\mathcal{L}_{\mathrm{Narain}}^{(c)}\right)}.
\end{aligned}\tag{4.161}
$$

The compact Narain average below is taken with respect to this measure, whenever the observable being averaged is integrable.

#### Averaging over topological-boundary conditions.

Pairing the fixed physical boundary state with a compact topological boundary condition $L$ gives the Narain partition function

$$
\begin{aligned}
Z_{L}(T^{2};\tau)=\langle L;T^{2}|\Psi_{\mathrm{phys}}(T^{2};\tau)\rangle.
\end{aligned}\tag{4.162}
$$

Using the Lagrangian lattice $L\subset\mathbb{D}_{c}$, this is

$$
\begin{aligned}
Z_{L}(\tau)={1\over|\eta(\tau)|^{2c}}\Theta_{L}(\tau),
\end{aligned}\tag{4.163}
$$

where

$$
\begin{aligned}
\Theta_{L}(\tau)=\sum_{\ell=(\vec{\alpha},\vec{\beta})\in L}q^{{1\over 4}\left|\vec{\alpha}+\vec{\beta}\right|^{2}}\bar{q}^{{1\over 4}\left|\vec{\alpha}-\vec{\beta}\right|^{2}},\qquad q=e^{2\pi i\tau}.
\end{aligned}\tag{4.164}
$$

The factor $1/|\eta(\tau)|^{2c}$ comes from the oscillator part of the fixed physical boundary Hamiltonian [(4.89)](https://arxiv.org/html/2605.06653v1#S4.E89). The theta function $\Theta_{L}(\tau)$ is supplied entirely by the topological boundary condition $L$. This aligns with our previous discussion that changing $L$ changes the allowed current-algebra primary sectors, while the local physical boundary dynamics is held fixed.

For the explicit compact topological boundary condition $L_{G,B}$, this becomes

$$
\begin{aligned}
Z_{G,B}(\tau)={1\over|\eta(\tau)|^{2c}}\sum_{\vec{n},\vec{w}\in\mathbb{Z}^{c}}q^{{1\over 4}\left|e^{-T}\bigl(\vec{n}+(B+G)\vec{w}\bigr)\right|^{2}}\bar{q}^{{1\over 4}\left|e^{-T}\bigl(\vec{n}+(B-G)\vec{w}\bigr)\right|^{2}}.
\end{aligned}\tag{4.165}
$$

This is the standard genus-one partition function of the toroidal Narain compactification with metric $G$ and $B$-field $B$ \[2006.04855\]. In the present SymTFT interpretation, however, $(G,B)$ are not couplings in the physical boundary Hamiltonian. They are coordinates on the space of topological boundaries $L_{G,B}$, specifying which bulk line-defect labels are allowed to end on the topological boundary.

The topological-boundary average over compact Narain caps is therefore

$$
\begin{aligned}
\big\langle Z(\tau)\big\rangle_{\mathrm{top}}^{(c)}=\int_{\mathcal{L}_{\mathrm{Narain}}^{(c)}}d\widehat{\mu}(L)\,Z_{L}(T^{2};\tau),
\end{aligned}\tag{4.166}
$$

whenever the integral converges as an ordinary integral. Equivalently, using the pairing notation of [(4.162)](https://arxiv.org/html/2605.06653v1#S4.E162),

$$
\begin{aligned}
\big\langle Z(\tau)\big\rangle_{\mathrm{top}}^{(c)}=\int_{\mathcal{L}_{\mathrm{Narain}}^{(c)}}d\widehat{\mu}(L)\,\langle L;T^{2}|\Psi_{\mathrm{phys}}(T^{2};\tau)\rangle.
\end{aligned}\tag{4.167}
$$

Here $d\widehat{\mu}(L)$ is the normalized Haar-induced measure introduced in [(4.161)](https://arxiv.org/html/2605.06653v1#S4.E161). If one instead works with the unnormalized Haar measure $d\mu(L)$, then [(4.166)](https://arxiv.org/html/2605.06653v1#S4.E166) should be replaced by

$$
\begin{aligned}
{1\over\mathrm{Vol}\!\left(\mathcal{L}_{\mathrm{Narain}}^{(c)}\right)}\int_{\mathcal{L}_{\mathrm{Narain}}^{(c)}}d\mu(L)\,Z_{L}(T^{2};\tau).
\end{aligned}
$$

The compact Narain average integrates only over the compact locus of discrete rank-$2c$ lattices $L$. The degenerate noncompact endpoints discussed above are not included as ordinary points of the Haar integral; they appear as cusp or boundary loci approached by sequences of compact caps.

Since the oscillator factor is independent of $L$, the average reduces to the Haar average of the Siegel–Narain theta function:

$$
\begin{aligned}
\big\langle Z(\tau)\big\rangle_{\mathrm{top}}^{(c)}={1\over|\eta(\tau)|^{2c}}\int_{\mathcal{L}_{\mathrm{Narain}}^{(c)}}d\widehat{\mu}(L)\,\Theta_{L}(\tau).
\end{aligned}\tag{4.168}
$$

This is the higher-rank version of the $c=1$ radius average.

There is an important distinction between the finite volume of the compact Narain quotient and the convergence of the partition-function integral. For $c>1$, the Haar volume of $\mathcal{L}_{\mathrm{Narain}}^{(c)}$ is finite, so the normalized measure $d\widehat{\mu}(L)$ exists. However, the genus-one theta integral

$$
\begin{aligned}
\int_{\mathcal{L}_{\mathrm{Narain}}^{(c)}}d\widehat{\mu}(L)\,\Theta_{L}(\tau)
\end{aligned}
$$

is finite only for $c>2$ \[2006.04855\]. At $c=2$, the moduli-space volume is finite, but the theta integral still diverges at the cusps, for example in large-volume and large-complex-structure limits. Thus $c=2$ is closer to the $c=1$ example from the viewpoint of the unregularized genus-one partition-function average, even though the quotient itself has finite Haar volume.

For $c>2$, the normalized genus-one average is finite. In the convention where $d\widehat{\mu}(L)$ has unit total volume, the Siegel–Weil formula gives \[2006.04855\]

$$
\begin{aligned}
\int_{\mathcal{L}_{\mathrm{Narain}}^{(c)}}d\widehat{\mu}(L)\,\Theta_{L}(\tau)={E_{c/2}(\tau)\over\tau_{2}^{c/2}},\qquad c>2,
\end{aligned}\tag{4.169}
$$

up to the convention used for the normalization of the real-analytic Eisenstein series $E_{c/2}(\tau)$. Therefore

$$
\begin{aligned}
\big\langle Z(\tau)\big\rangle_{\mathrm{top}}^{(c)}={E_{c/2}(\tau)\over\tau_{2}^{c/2}|\eta(\tau)|^{2c}},\qquad c>2.
\end{aligned}\tag{4.170}
$$

The measure in this statement is the Haar-induced measure on the Narain quotient, or equivalently the measure obtained from the Zamolodchikov metric on the Narain moduli space. The Siegel–Weil formula is the identity that evaluates the corresponding Haar average of the Siegel–Narain theta function; it is not a separate choice of measure.

This completes the higher-rank version of the $c=1$ dictionary. The fixed physical boundary condition supplies the current algebra, oscillator descendants, and Hamiltonian. The compact topological boundary condition $L$ supplies the even self-dual charge lattice, hence the current-algebra primary spectrum. Averaging over Narain CFTs is therefore realized as averaging over compact topological boundary conditions of a fixed $\mathbb{R}$-valued BF SymTFT.

## 5 Toward JT Gravity and 3D Gravity

In this paper we have studied low-dimensional ensemble averaging holography from the perspective of SymTFTs. The central idea is that the physical boundary condition is held fixed, while the topological boundary condition is varied. In the closed Marolf–Maxfield model this becomes a groupoid sum over finite-set caps, whereas in the Narain example it becomes an integral over (compact) topological boundary conditions of an $\mathbb{R}$-valued BF SymTFT. These two examples suggest that some familiar holographic ensemble averages can be reinterpreted as averages over topological completions of a fixed relative theory. It would be interesting to understand how far this interpretation extends beyond the topological and abelian examples discussed above.

### 5.1 Toward JT Gravity and Random Matrix Theory

A natural next example is JT gravity and its relation to random matrix theory \[1903.11115, 1907.03363\]. Although JT gravity is usually presented as a metric-dilaton theory, it also has a first-order BF-theory formulation \[1812.00918, 1905.02726\]. In its simplest bosonic form, one may write schematically<sup>12</sup>

$$
\begin{aligned}
S_{\mathrm{BF}}=i\int_{Y}{\mathrm{Tr}}\,\Phi F_{A}
\end{aligned}\tag{5.1}
$$

together with the Euler-characteristic term $S_{0}\chi(Y)$ and the appropriate asymptotic boundary term. Here $A$ is an $SL(2,\mathbb{R})$ connection, and $\Phi$ is an adjoint-valued scalar field whose components include the JT dilaton. Integrating over $\Phi$ imposes the flatness of $A$, so the bulk path integral reduces, up to the boundary degrees of freedom, to an integral over a moduli space of flat $SL(2,\mathbb{R})$ connections. The asymptotic $AdS_{2}$ boundary condition is not topological; it gives the Schwarzian boundary mode and hence the usual one-dimensional quantum-mechanical observable $\mathrm{Tr}\,e^{-\beta H}$.

From the BF-theory point of view, the scalar field $\Phi$ is a local zero-form field in the 2D topological theory. Therefore given gauge-invariant functions of $\Phi$, for example

$$
\begin{aligned}
{\cal O}_{f}(x)=f\!\left(C(x)\right),\qquad C(x)=\frac{1}{2}{\mathrm{Tr}}\,\Phi(x)^{2},
\end{aligned}\tag{5.2}
$$

one defines local operators of the underlying 2D TFT. In the JT boundary problem, the quadratic Casimir $C$ is naturally related, up to normalization conventions, to the Hamiltonian of the Schwarzian quantum mechanics. Thus insertions of functions of the BF scalar should be viewed as topological representatives of spectral observables of the boundary quantum mechanics.

This makes JT gravity structurally close to the Marolf–Maxfield example discussed in Section [3](https://arxiv.org/html/2605.06653v1#S3). In that example, a fixed topological parent SymTFT was capped by a topological boundary condition labelled by a finite set $S$, and the resulting absolute theory had

$$
\begin{aligned}
Z_{S}(S^{1})=|S|.
\end{aligned}\tag{5.3}
$$

Averaging over the finite-set caps then produced the Marolf–Maxfield moments. For JT gravity, the analogous SymTFT would be the $SL(2,\mathbb{R})$ BF theory, refined by the local algebra generated by the dilaton/BF scalar and by the non-topological asymptotic JT boundary condition. Given there are nontrivial local operators in the 2D bulk, the physical boundary should prepare a class of relative one-dimensional quantum mechanics \[2411.14997\] rather than a single quantum mechanics or number. A topological boundary condition $L$ would then specify an absolute completion of this relative boundary theory, namely a Hilbert space and a Hamiltonian on which the Schwarzian/spectral observables act.

In this language, one expects a fixed topological boundary condition $L$ to produce a factorizing one-dimensional quantum mechanics,

$$
\begin{aligned}
Z_{L}(\beta)=\big\langle L;S^{1}\,\big|\,\Psi_{\mathrm{phys}}(\beta)\big\rangle={\mathrm{Tr}}_{\mathcal{H}_{L}}e^{-\beta H_{L}}.
\end{aligned}\tag{5.4}
$$

For several asymptotic boundaries, the same topological cap should give the corresponding product of traces in the fixed absolute theory. Averaging over topological boundary conditions would therefore take the schematic form

$$
\begin{aligned}
\left\langle\prod_{i=1}^{n}Z(\beta_{i})\right\rangle_{\mathrm{top}}=\int_{\mathcal{L}_{\mathrm{JT}}}d\mu(L)\,\big\langle L;\bigsqcup_{i=1}^{n}S^{1}_{i}\,\big|\,\Psi_{\mathrm{phys}}(\beta_{1},\ldots,\beta_{n})\big\rangle.
\end{aligned}\tag{5.5}
$$

The desired statement is that, for an appropriate space $\mathcal{L}_{\mathrm{JT}}$ of admissible topological boundary conditions and an appropriate measure $d\mu(L)$, this average reproduces the double-scaled random matrix ensemble average

$$
\begin{aligned}
\left\langle\prod_{i=1}^{n}{\mathrm{Tr}}\,e^{-\beta_{i}H}\right\rangle_{\mathrm{RMT}}.
\end{aligned}\tag{5.6}
$$

Different choices of additional topological data, such as orientation reversal, spin or pin structures, and supersymmetry, should then correspond to different random matrix universality classes \[1907.03363\].

We emphasize that the above perspective should be regarded as a very sloppy proposal. The main missing ingredients are a precise classification of topological boundary conditions for the noncompact $SL(2,\mathbb{R})$ BF theory relevant to JT gravity, and a derivation of the measure on this space that reproduces the matrix-model eigenvalue measure and spectral curve. Nevertheless, the analogy with Section [3](https://arxiv.org/html/2605.06653v1#S3) suggests a useful organizing principle.

### 5.2 Toward Virasoro TFT and 3D Gravity

Another natural direction is pure 3D gravity with negative cosmological constant. Recent work suggests that the fixed-topology path integral of pure $\mathrm{AdS}_{3}$ gravity can be reformulated in terms of a topological theory built from the quantization of Teichmüller space, usually called Virasoro T(Q)FT \[2304.13650, 2401.13900\]. In particular, for suitable quasi-local boundary conditions, fixed-length amplitudes can be written as Virasoro T(Q)FT amplitude-squared, while fixed-angle amplitudes are naturally related to Conformal Turaev–Viro theory \[2507.12696\]. More precisely, Virasoro T(Q)FT should be regarded as a chiral building block. The gravitational answer is obtained by combining a left-moving and a right-moving copy, schematically

$$
\begin{aligned}
\mathcal{T}_{\mathrm{grav}}\sim\mathcal{T}_{\mathrm{Vir}}\boxtimes\overline{\mathcal{T}}_{\mathrm{Vir}},
\end{aligned}\tag{5.7}
$$

or, at the level of fixed-topology amplitudes, by an absolute-square type pairing of Virasoro-T(Q)FT wavefunctions. This is the non-abelian analogue of the abelian Chern–Simons/BF structures discussed in Section [4](https://arxiv.org/html/2605.06653v1#S4).

It is useful to phrase this point in the language of SymTFT. An ordinary rational-CFT SymTFT based on a modular tensor category (MTC) usually starts from a chosen extended chiral algebra $\mathcal{A}$. The corresponding MTC captures topological defect lines that commute with, or preserve, this full chiral algebra. By contrast, Virasoro T(Q)FT should be thought of as the universal version in which only the Virasoro symmetry is fixed. Its topological line operators are expected to encode defects that commute with the left and right Virasoro algebras, without requiring preservation of any further extended chiral algebra. This is why it is the natural candidate SymTFT for an ensemble in which the central charge and Virasoro kinematics are fixed, while the extra chiral algebra, the spectrum of Virasoro primaries, and the OPE data are supplied by the topological boundary.

Let $\Sigma$ be the conformal boundary. The Virasoro T(Q)FT assigns to $\Sigma$ a Hilbert space of Virasoro conformal blocks, which we denote schematically by

$$
\begin{aligned}
\mathcal{H}_{\mathrm{Vir}}(\Sigma).
\end{aligned}\tag{5.8}
$$

For gravity one should use the left-right doubled space

$$
\begin{aligned}
\mathcal{H}_{\mathrm{grav}}(\Sigma)=\mathcal{H}_{\mathrm{Vir}}(\Sigma)\otimes\overline{\mathcal{H}}_{\mathrm{Vir}}(\Sigma).
\end{aligned}\tag{5.9}
$$

This is the direct analogue of the Hilbert space of the $\mathbb{R}$-valued BF SymTFT in the Narain example. A physical conformal boundary condition, with complex structure, operator insertions, and possible moduli collectively denoted by $\Omega$, should prepare a relative state

$$
\begin{aligned}
\big|\Psi_{\mathrm{phys}}(\Sigma;\Omega)\big\rangle\in\mathcal{H}_{\mathrm{grav}}(\Sigma).
\end{aligned}\tag{5.10}
$$

This boundary is not topological. It contains the Virasoro Hamiltonian. For example, on the torus one expects the physical boundary to carry

$$
\begin{aligned}
H_{\mathrm{phys}}=L_{0}+\overline{L}_{0}-\frac{c}{12},
\end{aligned}\tag{5.11}
$$

so that, after choosing an absolute completion via a topological boundary, the torus observable has the usual form

$$
\begin{aligned}
Z_{L}(\tau,\overline{\tau})=\mathrm{Tr}_{\mathcal{H}_{L}}\left(q^{L_{0}-c/24}\,\overline{q}^{\,\overline{L}_{0}-c/24}\right).
\end{aligned}\tag{5.12}
$$

Here $L$ denotes a topological boundary condition of the doubled Virasoro T(Q)FT. As in the previous examples, the topological boundary is required to carry zero Hamiltonian. It does not change the local Virasoro time evolution; rather, it specifies the absolute Hilbert space $\mathcal{H}_{L}$ on which this Hamiltonian acts.

This is very close in spirit to the Narain construction. In Section [4](https://arxiv.org/html/2605.06653v1#S4), the physical boundary supplied the oscillator sector, the current algebra descendants, and the Hamiltonian, while the (compact) topological boundary condition supplied the even self-dual charge lattice and hence the current-algebra primary spectrum. In the Virasoro case, the physical boundary should supply the universal Virasoro kinematics: the conformal blocks, the descendant contributions, and the conformal Hamiltonian. The topological boundary condition should supply the dynamical CFT data: the spectrum of Virasoro primaries, their multiplicities, and the OPE coefficients obeying crossing and modular invariance.

For example, on a torus one may write schematically

$$
\begin{aligned}
Z_{L}(\tau,\overline{\tau})=\sum_{(h,\overline{h})\in\mathcal{S}_{L}}N_{L}(h,\overline{h})\,\chi_{h}(\tau)\,\overline{\chi}_{\overline{h}}(\overline{\tau}),
\end{aligned}\tag{5.13}
$$

where the characters are universal Virasoro objects, while the spectrum $\mathcal{S}_{L}$ and multiplicities $N_{L}(h,\overline{h})$ are supplied by the Lagrangian boundary $L$. Similarly, for a four-point function on the sphere, one expects an expansion of the schematic form

$$
\begin{aligned}
\big\langle\mathcal{O}_{1}\mathcal{O}_{2}\mathcal{O}_{3}\mathcal{O}_{4}\big\rangle_{L}=\sum_{p,\overline{p}}C^{(L)}_{12p}\,C^{(L)}_{34p}\,\mathcal{F}_{p}\left[\begin{matrix}h_{1}&h_{2}\\
h_{3}&h_{4}\end{matrix}\right](z)\,\overline{\mathcal{F}}_{\overline{p}}\left[\begin{matrix}\overline{h}_{1}&\overline{h}_{2}\\
\overline{h}_{3}&\overline{h}_{4}\end{matrix}\right](\overline{z}).
\end{aligned}\tag{5.14}
$$

Again, the conformal blocks are universal and belong to the physical boundary data, while the coefficients $C^{(L)}_{ijk}$ and the spectrum of exchanged primaries are part of the topological completion.

Thus a possible SymTFT interpretation of the ensemble dual to pure $\mathrm{AdS}_{3}$ gravity is the following. We conjecture that there should exist a space

$$
\begin{aligned}
\mathcal{L}_{\mathrm{Vir}}
\end{aligned}\tag{5.15}
$$

of admissible topological boundary conditions of the doubled Virasoro T(Q)FT. For each $L\in\mathcal{L}_{\mathrm{Vir}}$, the pairing

$$
\begin{aligned}
Z_{L}(\Sigma;m)=\big\langle L;\Sigma\,\big|\,\Psi_{\mathrm{phys}}(\Sigma;m)\big\rangle
\end{aligned}\tag{5.16}
$$

defines an absolute 2D CFT-like object with fixed central charge and fixed Virasoro symmetry. The proposed ensemble average is then

$$
\begin{aligned}
\big\langle Z(\Sigma;m)\big\rangle_{\mathrm{top}}=\int_{\mathcal{L}_{\mathrm{Vir}}}d\mu(L)\,\big\langle L;\Sigma\,\big|\,\Psi_{\mathrm{phys}}(\Sigma;m)\big\rangle.
\end{aligned}\tag{5.17}
$$

For several disconnected conformal boundaries, the same topological boundary condition should be used on all components:

$$
\begin{aligned}
\left\langle\prod_{a=1}^{n}Z(\Sigma_{a};m_{a})\right\rangle_{\mathrm{top}}=\int_{\mathcal{L}_{\mathrm{Vir}}}d\mu(L)\,\prod_{a=1}^{n}\big\langle L;\Sigma_{a}\,\big|\,\Psi_{\mathrm{phys}}(\Sigma_{a};m_{a})\big\rangle.
\end{aligned}\tag{5.18}
$$

At fixed $L$, the answer factorizes, as it should for a single absolute CFT. The non-factorization of the gravitational answer is then produced by the integral over topological caps.

This perspective also gives a natural way to interpret the wormhole computations in Virasoro T(Q)FT. A multi-boundary Euclidean wormhole computes a moment of CFT data in the putative ensemble. In the present language, this moment should arise because the same topological boundary condition $L$ is used to cap all physical boundaries before being averaged over. Thus the Virasoro-T(Q)FT wormhole is not changing the local boundary Hamiltonian; it is correlating the absolute completion data, namely the spectrum and OPE coefficients, across different copies of the physical boundary.

Here the main missing ingredient, which is also the most nontrivial step, is the correct definition of $\mathcal{L}_{\mathrm{Vir}}$ and of the measure $d\mu(L)$. For finite rational T(Q)FTs, topological boundary conditions are described by Lagrangian algebras in a modular tensor category. For the $R$-valued BF theories used in the Narain example, this becomes a continuous space of Lagrangian subgroups equipped with a Haar-type measure. The Virasoro case should be simultaneously non-rational and non-compact analogue of these two situations. A topological boundary condition should be an object that pairs left and right Virasoro conformal blocks into a single-valued, crossing-symmetric, modular invariant full CFT. In categorical language, it should be a kind of Lagrangian algebra or full-center object in the non-rational braided category of Virasoro representations, but this statement requires functional-analytic input beyond the finite semisimple framework.

The relation to quantum groups may be useful precisely here. Quantum Teichmüller theory is closely related to the modular double of $U_{q}(\mathfrak{sl}(2,\mathbb{R}))$ \[1109.6295, 1302.3454\], with

$$
\begin{aligned}
q=e^{i\pi b^{2}},\qquad\widetilde{q}=e^{i\pi b^{-2}},\qquad c=1+6(b+b^{-1})^{2}.
\end{aligned}\tag{5.19}
$$

The fusion and braiding kernels of Virasoro conformal blocks can be interpreted in terms of Clebsch–Gordan coefficients and $6j$-symbols of this modular-double quantum group \[math/0007097, 1202.4698, 2309.11540\]. Therefore the algebra of topological line operators and the Moore–Seiberg moves of Virasoro T(Q)FT should admit a quantum-group description. From this point of view, the desired topological boundary conditions may be formulated as suitable module categories, or commutative algebra objects, for the representation category of the modular double. The measure $d\mu(L)$ should then be related to the Plancherel measure \[math/0007097, 1202.4698\] or Haar-type measure naturally associated with this non-compact quantum group.

Again, we emphasize that this should be taken only as a very sloppy proposal, not as a promising construction. At generic $q$, the relevant representation theory is continuous and non-compact, so one should not expect a finite groupoid sum over Lagrangian algebras. At special rational or root-of-unity points, finite quantum-group categories may give controlled toy models, closer to ordinary Reshetikhin–Turaev \[Reshetikhin:1991tc\] or Turaev–Viro theory \[Turaev:1992hq\]. The generic Virasoro case, however, should involve a genuinely continuous topological-boundary average, more like the Narain integral than like the finite Marolf–Maxfield groupoid sum.

The conceptual payoff would be significant. Pure $\mathrm{AdS}_{3}$ gravity would then fit the same pattern as the examples studied in this paper: For Narain theories, the topological boundary condition is equivalent to a charge lattice. For the Marolf–Maxfield model, it is a finite set. For pure 3D gravity, it should be the full Virasoro CFT data selected by a topological boundary condition of the doubled Virasoro T(Q)FT. Making this statement precise would require a classification of admissible Virasoro topological boundaries, a derivation of the corresponding measure, and a proof that this topological-boundary average reproduces the known Virasoro-T(Q)FT gravity amplitudes. These are open problems, but the analogy suggests a concrete route for organizing them.

Acknowledgement The author thanks Scott Collier, Max Hübner, Patrick Jefferson, Ho Tat Lam, Alex Maloney, and Ling-Yan Hung for valuable discussions, with special thanks to Yikun Jiang for insightful discussions and encouragement at various stages of this project. The authors thanks Jonathan Heckman, Ethan Torres, and Andrew Turner for collaboration on related projects. This work is partially supported by the NSF grant PHY-2310588.

## Notes

<sup>1</sup> See, e.g., \[2006.11317, 2006.13414, 2006.13971, 2006.16289, 2103.16754, 2104.01184, 2105.02142, 2105.08207, 2106.09048, 2107.02178, 2107.13130, Heckman:2021vzx, 2111.07863, 2111.14856, 2201.00903, 2203.09537, 2209.02131, 2404.10035, 2006.05499, 2006.08648, 2007.15653, 2012.15830, 2102.03136, 2102.12509, 2103.15826, 2104.10178, 2104.14710, 2106.12760, 2110.14649, 2112.09143, 2203.06511, 2208.14457, 2304.13650, 2306.07321, 2307.03707, 2308.01787, 2308.03829, 2309.10846, 2310.06012, 2310.13044, 2311.00699, 2311.08132, 2312.02276, 2401.13900, 2403.02976, 2405.13111, 2407.02649, 2503.00101, 2504.08724, 2506.19817, 2511.04311\] and references therein for a partial list of references to recent literature on ensemble holography.

<sup>2</sup> See, e.g., \[Reshetikhin:1991tc, Turaev:1992hq, Barrett:1993ab, hep-th/9812012, hep-th/0204148, Kirillov2010TuraevViroIA, 1012.0911, Kitaev:2011dxc, Fuchs:2012dt, 1212.1692, Kong:2014qka, Kong:2017hcw, Heckman:2017uxe, Freed:2018cec, Gaiotto:2020iye, Kong:2020cie, Apruzzi:2021nmk, Freed:2022qnc, Kaidi:2022cpf, Antinucci:2022vyk, 2306.11783, Baume:2023kkf, Yu:2023nyn, 2401.06128, 2401.10165, DelZotto:2024tae, Argurio:2024oym, Franco:2024mxa, Heckman:2024zdo, Gagliano:2024off, Cordova:2024iti, Cvetic:2024dzu, Bhardwaj:2024igy, Bonetti:2024cjk, Apruzzi:2024htg, 2411.14997, Jia:2025jmn, Apruzzi:2025mdl, Heckman:2025lmw, Pace:2025hpb, Luo:2025phx, Apruzzi:2025hvs, 2510.06319, 2603.12323\] and references therein for a partial list of references to foundational early work, as well as more recent generalizations.

<sup>3</sup> More precisely, simple topological boundary conditions are those cannot be reduced to simpler topological boundaries. Since here we are only interested in semisimple TFTs, simple topological boundaries are equivalently those which are indecomposible into sums of other topological boundaries.

<sup>4</sup> For the physics reader comfortable with categories, a groupoid can be regarded as a special category with all objects and morphisms invertible.

<sup>5</sup> We refer the reader to \[2311.16230\] for a physics friendly introduction to Frobenius algebra.

<sup>6</sup> An idempotent is an element $p$ satisfying $p^{2}=p$. It is called primitive if it is nonzero and cannot be decomposed as $p=p_{1}+p_{2}$, where $p_{1},p_{2}$ are nonzero orthogonal idempotents, $p_{i}^{2}=p_{i}$ and $p_{1}p_{2}=0$. In $\mathcal{A}_{S}=\operatorname{Fun}(S,\mathbb{C})$, the idempotents are characteristic functions of subsets of $S$, and the primitive idempotents are precisely the delta functions $e_{s}$ supported at single points $s\in S$.

<sup>7</sup> This is reminiscent of the entangled state in SymTFT with multiple physical boundaries and its resulting non-factorization in \[2510.06319\].

<sup>8</sup> More precisely as a quotient stack.

<sup>9</sup> In the $c=1$ warm-up of Maloney–Witten \[2006.04855\], the Zamolodchikov metric is written as $ds^{2}=4\,dR^{2}/R^{2}$, while the measure used in the formal average is $dR/(2R)$. If one instead quotes the raw Riemannian volume form associated to that metric, one obtains $2\,dR/R$. These differ only by an overall constant. Since the $c=1$ average diverges, and since finite-volume Narain averages are usually normalized separately, this constant is a convention rather than physical data.

<sup>10</sup> Since we want the resulting absolute theories being bosonic CFTs instead of their fermionization.

<sup>11</sup> Note that this redundancy is due to this specific physical boundary, but not SymTFT itself. That is to say, given a SymTFT, different physical boundaries may require different redundancy of space of topological boundary conditions.

<sup>12</sup> We thank Patrick Jefferson for valuable discussions inspiring the content of this subsection.
