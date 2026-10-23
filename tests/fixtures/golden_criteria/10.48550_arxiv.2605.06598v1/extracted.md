---
title: "Mathematical Modeling of Early Embryonic Cell Cycles of *Drosophila melanogaster*"
authors: "Meskerem Abebaw Mebratie, Benedikt Drebes, Katja Kapp, Arno Müller, Werner M. Seiler"
journal: "arXiv"
doi: "10.48550/arxiv.2605.06598v1"
published: "2026-05-07"
source: "arxiv_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 14422
---

# Mathematical Modeling of Early Embryonic Cell Cycles of *Drosophila melanogaster*

## Abstract

In the early stages of development, Drosophila melanogaster embryos possess very fast and well-coordinated cell cycles. In the cell cycle, CDK activity is essentially regulated by binding CDK and CycB to form an active complex and by phosphorylating CDK via CDC25 and dephosphorylating it via Wee1. We develop a mathematical model for the embryonic cell cycle which is biochemically sound and which can be rigorously analysed after a model reduction. We show that there exists a region in the parameter space where the model describes oscillations. We then focus on the role of two parameters: the CycB synthesis and the activation coefficient of APC. Our main biological hypothesis is that the first one is responsible for the period lengthening over the first 14 cycles which can be experimentally observed and this hypothesis is supported by numerical simulations of our model: if the CycB synthesis is made time-dependent with a prescribed dynamics, then our simulations show qualitatively a very similar behavior to experimental data reported in the literature.

## 1 Introduction

Life is characterized by several properties, including growth, metabolism, and the ability to reproduce. The ability to reproduce is essential for complex organisms as well as individual cells. At a cellular level, this attribute is enabled by the cell cycle. The cell cycle controls cell growth, the duplication of genetic information, and cell division. The cell cycle is divided into two phases: interphase and mitosis. The interphase is further subdivided into two gap phases (G phases) and the synthesis phase (S phase) in between. G1 is the gap phase during which cells grow and prepare for DNA synthesis. During the S phase, the centrosomes duplicate and the DNA is replicated. G2 is the second gap phase, during which the cell continues to grow and prepares for cell division. After the G2 phase, the cell enters mitosis. During mitosis, the replicated chromosomes are distributed into two daughter cells. This process can be subdivided into five phases: prophase, metaphase, anaphase, telophase, and cytokinesis (Matthews et al., [2022](https://arxiv.org/html/2605.06598v1#bib.bib290)).

The embryo of the fruit fly *Drosophila melanogaster* has been used extensively to study various cell biological aspects of the cell cycle. This model offers several advantages, such as the ability to use a range of genetic tools to investigate the function of individual proteins. The first 13 cell cycles in *D. melanogaster* are characterized by the absence of G1 and G2 phases, and by the absence of cytokinesis and thus provides a simplified model for the regulation of M and S phase cycling (Yuan et al., [2016](https://arxiv.org/html/2605.06598v1#bib.bib223)). Since the cell cycle consists only of the S phase and mitosis, this cycle can be used to study the regulation of these two phases (see Figure ([1(a)](https://arxiv.org/html/2605.06598v1#S1.F1.sf1))).

The choice of this family of regulatory networks was motivated by the investigation of early embryonic cell cycles in the model organism *D. melanogaster*, which has been widely used in developmental biology (Wilson et al., [1995](https://arxiv.org/html/2605.06598v1#bib.bib244)). In the early stages of development, *D. melanogaster* embryos display very fast and well-coordinated cell cycles. Precise temporal controls and other intrinsic molecular mechanisms govern these cycles. Numerous developmental biology laboratories have studied these mechanisms, and many biologists have contributed to this effort (Deneke et al., [2016](https://arxiv.org/html/2605.06598v1#bib.bib224)), (Farrell and O’Farrell, [2014](https://arxiv.org/html/2605.06598v1#bib.bib235)), (Shindo and Amodeo, [2021a](https://arxiv.org/html/2605.06598v1#bib.bib234)), (Shindo and Amodeo, [2021b](https://arxiv.org/html/2605.06598v1#bib.bib227)), (Yuan et al., [2016](https://arxiv.org/html/2605.06598v1#bib.bib223)).

![Figure 1](https://arxiv.org/html/2605.06598v1/Images/gbn3.png)

(a) The timing of the cell cycles and the first 13 cell cycles of *D. melanogaster* along with nuclei position, modified according to (Farrell and O’Farrell, [2014](https://arxiv.org/html/2605.06598v1#bib.bib235)).

![Figure 1](https://arxiv.org/html/2605.06598v1/Images/Mathdroso_inactivewee1.png)

(b) Regulatory processes impinging on $CDK1$ kinase activity.

Figure 1: Timing and regulation of the early embryonic *D. melanogaster*.

In this work, we develop a biochemically sound model of CDK activation in the form of a parametric system of ordinary differential equations and analyze it mathematically. One of the main questions in the analysis is the existence of a region of positive parameter values for which the system possesses limit cycles, i.e. shows oscillatory behavior. For systems in more than two dimensions, a direct proof of the existence of a limit cycle is known to be a challenging problem, in particular for a larger number of parameters. We therefore instead identify parameter values at which a Hopf bifurcation (Marsden and McCracken, [2012](https://arxiv.org/html/2605.06598v1#bib.bib184)), (Rionero, [2019](https://arxiv.org/html/2605.06598v1#bib.bib185)) occurs, as limit cycles in parametric systems typically stem from such a bifurcation. In experiments (Deneke et al., [2016](https://arxiv.org/html/2605.06598v1#bib.bib224)), one observes that the length of the early embryonic cell cycles increases from cycle to cycle and our biological hypothesis is that this effect is controlled by the parameter representing the cyclin synthesis. We show that our model can reproduce such a behavior, if one assumes that the cyclin synthesis is slowly decreasing and thus provide mathematical support for the biological hypothesis.

The paper is organized as follows: In Section [2](https://arxiv.org/html/2605.06598v1#S2), we develop our mathematical model for the early embryonic cell cycles of *D. melanogaster*. In Section [3](https://arxiv.org/html/2605.06598v1#S3), we apply several reduction techniques to obtain a smaller model that can be better analyzed mathematically. The analysis is the topic of Section [4](https://arxiv.org/html/2605.06598v1#S4): we first search for biologically relevant steady states of the reduced system and then perform a bifurcation analysis for two key parameters. In Section [5](https://arxiv.org/html/2605.06598v1#S5), we compare numerical simulations of our model with experimental results. Finally, some conclusions are given.

## 2 Model Development

For the cell cycle to proceed correctly, cells require precise temporal control. All the molecules that control M and S phases are present in the fly embryo as mRNA or proteins within a common cytoplasm. Cell cycle progression depends on the synthesis and destruction of Cyclins and the transition from the S phase to M phase is controlled by the complex of Cyclin B (CycB) and Cyclin-dependent kinase 1 (Cdk1) (Pluta et al., [2024](https://arxiv.org/html/2605.06598v1#bib.bib281)). The kinase activity of the CycB/Cdk1 complex is both activated and inactivated via phosphorylation (Blank et al., [2025](https://arxiv.org/html/2605.06598v1#bib.bib282)). The inactivating phosphorylations are carried out by the Wee1 kinase (Wee1) at the Threonine 14 (T14) and Tyrosine 15 (Y15) (Stumpff et al., [2004](https://arxiv.org/html/2605.06598v1#bib.bib283)). These inhibitory phosphorylations can be removed by the phosphatase Cell Division Cycle 25 (Cdc25), thereby activating the complex (Lew and Kornbluth, [1996](https://arxiv.org/html/2605.06598v1#bib.bib284)). The activated CycB/Cdk1 complex in turn activates Cdc25 and thus triggers a positive feedback loop (Lu et al., [2012](https://arxiv.org/html/2605.06598v1#bib.bib285)). When a certain amount of the CycB/Cdk1 complex is activated, the cell can enter mitosis. The transition to mitosis inactivates Wee1. During mitosis, the CycB/Cdk1 complex activates the anaphase-promoting complex (APC) via phosphorylation of Cdc20, which eventually results in the activation of APC (Kataria and Yamano, [2019](https://arxiv.org/html/2605.06598v1#bib.bib286)). The activation of APC allows the cell to proceed from metaphase to anaphase. The activated APC degrades CycB via ubiquitylation and thereby destroys the CycB/Cdk1 complex (Acquaviva and Pines, [2006](https://arxiv.org/html/2605.06598v1#bib.bib287)). At the onset of the next cell cycle, CycB is translated again from maternally provided CycB mRNA and will form a novel complex with Cdk1; therefore the translation and destruction of CycB represent the temporal regulation of this simple cell cycle (see Figure ([1(b)](https://arxiv.org/html/2605.06598v1#S1.F1.sf2))).

The simplification of the syncytial cell cycles in the fly embryo to only S and M phases provides the basis for very rapid cell cycles with a duration of about 9 minutes. From the 10th cell cycle onwards, the cell cycle durations increase gradually to a length of eventually 21 minutes for the 13th cell cycle (Foe and Alberts, [1983](https://arxiv.org/html/2605.06598v1#bib.bib288)). Coincindently with the extension of the cell cycle length, a decrease in the amount of maternal CycB mRNA can be observed at the beginning of the cell cycle (Edgar et al., [1994b](https://arxiv.org/html/2605.06598v1#bib.bib289)). The decrease in CycB concentration and the regulation of CycB/Cdk1 by Wee1, Cdc25 and APC are used to create a model that explains the change in the cell cycle length. All of these signals exhibit significant time delays in their functioning, which seem to have important biological implications. Moreover, the CDK network is susceptible to external checkpoint controls (Murray, [1992](https://arxiv.org/html/2605.06598v1#bib.bib233)).

The regulatory system, as depicted in Figure [1](https://arxiv.org/html/2605.06598v1#S1.F1), will be transformed into a system of ordinary differential equations. As illustrated in Figure [1](https://arxiv.org/html/2605.06598v1#S1.F1), we assume that the substrates (CDC25, Wee1) play a major role over the proteins (phosphatases and kinases) and that other proteins have indirect effects on CDK activity. If not, the substrates competing for the same kinase would interfere in intricate ways. These assumptions make the model much simpler. We use Hill functions to model activating and inhibiting effect in a standard way. As a result, the Hill functions we apply to describe the dynamics of CDC25, Wee1, and APC depend on their roles in the CDK activity.

Hence, the equation for the protein CDC25 is $\frac{d[CDC25]}{dt}=\theta_{5}\frac{[CDK]^{n_{2}}}{k_{2}^{n_{2}}+[CDK]^{n_{2}}}-\alpha_{3}[CDC25]$ with the activation coefficient $k_{2}$, the maximal expression level of the promoter $\theta_{5}$, the degradation rate $\alpha_{3}$, and the Hill coefficient $n_{2}$. For the protein Wee1, that the CDK-cyclin active complex inhibits, we use $\frac{d[Wee1]}{dt}=\theta_{6}\frac{k_{1}^{n_{1}}}{k_{1}^{n_{1}}+[CDK]^{n_{1}}}-\alpha_{4}[Wee1]$ where the inhibition rate is $\theta_{6}$, the inhibition coefficient $k_{1}$, the degradation rate $\alpha_{4}$, and the Hill coefficient $n_{1}$, which measures the process switch-like nature. The protein $APC$ is activated by the active complex $CDK$ and its dynamic is modelled as $\frac{d[APC]}{dt}=\theta_{4}\frac{[CDK]^{n_{3}}}{k_{3}^{n_{3}}+[CDK]^{n_{3}}}-\alpha_{4}[APC]$ where $k_{3}$ is the activation coefficient, $\theta_{4}$ the maximal level of the promoter, $\alpha_{2}$ the degradation rate and $n_{3}$ the Hill coefficient. The difference between the rates of synthesis and degradation of cyclin determines the rate at which its concentration changes over time. When APC is present, cyclin is degraded; this relationship can be explained by the following equation, $\frac{d[\text{CycB}]}{dt}=b_{1}-b_{7}[\text{CycB}][\text{APC}]$ where the rates of cyclin synthesis and degradation in the presence of APC are $b_{1}$ and $b_{7}$, respectively.

Considering all the above, the mathematical model for the central CDK–cyclin system is then described by the following differential system

$$
\begin{aligned}
\displaystyle\begin{split}\frac{d[CycB]}{dt}&=b_{1}-b_{7}[CycB][APC]\,,\\
\frac{d[CDK]}{dt}&=b_{2}[CycB][CDK_{I}]+\theta_{2}[CDC25][CDK_{I}]\\
&-\Bigl(\theta_{3}[Wee1]+\alpha_{1}[APC]\Bigr)[CDK]=-\frac{d[CDK_{I}]}{dt}\,,\\
\frac{d[APC]}{dt}&=\theta_{4}\frac{[CDK]^{n_{3}}}{[CDK]^{n_{3}}+k_{3}^{n_{3}}}-\alpha_{2}[APC]\,,\\
\frac{d[CDC25]}{dt}&=\theta_{5}\frac{[CDK]^{n_{2}}}{[CDK]^{n_{2}}+k_{2}^{n_{2}}}-\alpha_{3}[CDC25]\,,\\
\frac{d[Wee1]}{dt}&=\theta_{6}\frac{k_{1}^{n_{1}}}{k_{1}^{n_{1}}+[CDK]^{n_{1}}}-\alpha_{4}[Wee1]\,,\end{split}
\end{aligned}\tag{1}
$$

where $CDK$ denotes the active $CDK$ and $CDK_{I}$ the inactive $CDK$. It is a system of six differential equations depending on fifteen parameters and three Hill coefficients.

## 3 Model Reductions

In the form ([1](https://arxiv.org/html/2605.06598v1#S2.E1)), the system is still too large for a rigorous mathematical analysis. We therefore apply various methods for a model reduction to obtain a better analysable model. We first note that $CDC25$ appears outside of its own equation only in the equations for $CDK/CDK_{I}$. As explained above, its effect on the $CDK$ activity is described by the Hill function $\frac{[CDK]^{n_{2}}}{[CDK]^{n_{2}}+k_{2}^{n_{2}}}$ and hence we can replace the second term of the second equation of ([1](https://arxiv.org/html/2605.06598v1#S2.E1)) by $\theta_{2}\frac{[CDK]^{n_{2}}}{[CDK]^{n_{2}}+k_{2}^{n_{2}}}[CDK_{I}]$ effectively eliminating $CDC25$. The equation for $CDK$ now becomes

$$
\begin{aligned}
\frac{d[CDK]}{dt}=b_{2}[CycB][CDK_{I}]+\theta_{2}\frac{[CDK]^{n_{2}}}{[CDK]^{n_{2}}+k_{2}^{n_{2}}}[CDK_{I}]-{}\\
\Bigl(\theta_{3}[Wee1]+\alpha_{1}[APC]\Bigr)[CDK]=-\frac{d[CDK_{I}]}{dt}
\end{aligned}
$$

and there is no need to keep a differential equation for $CDC25$.

Next we note that the equality $\frac{d[CDK]}{dt}=-\frac{d[CDK]}{dt}$ implies that the overall concentration $[CDK_{total}]=[CDK]+[CDK_{I}]$ is a conserved quantity. Writing $[CDK_{I}]$ as $[CDK_{I}]=[CDK_{total}]-[CDK]$ and dividing both sides by $[CDK_{total}]$, we can eliminate the differential equation for $[CDK_{I}]$, leading to the system

$$
\begin{aligned}
\displaystyle\begin{split}\frac{d[CycB]}{dt}&=b_{1}-b_{7}[CycB][APC]\,,\\
\frac{d[\overline{CDK}]}{dt}&=b_{2}[CycB]\Bigl(1-[\overline{CDK}]\Bigr)+\theta_{2}\frac{[\overline{CDK}]^{n_{2}}}{[\overline{CDK}]^{n_{2}}+k_{2}^{n_{2}}}\Bigl(1-[\overline{CDK}]\Bigr)\\
&-\Bigl(\theta_{3}[Wee1]+\alpha_{1}[APC]\Bigr)[\overline{CDK}]\,,\\
\frac{d[APC]}{dt}&=\theta_{4}\frac{[\overline{CDK}]^{n_{3}}}{[\overline{CDK}]^{n_{3}}+k_{3}^{n_{3}}}-\alpha_{2}[APC]\,,\\
\frac{d[Wee1]}{dt}&=\theta_{6}\frac{k_{1}^{n_{1}}}{k_{1}^{n_{1}}+[\overline{CDK}]^{n_{1}}}-\alpha_{4}[Wee1]\,,\end{split}
\end{aligned}\tag{2}
$$

where $[\overline{CDK}]=\frac{[CDK_{I}]}{[CDK_{total}]}$. While it does not explicitly depend on the new parameter $[CDK_{total}]$, reconstruction of the values of $[CDK]$ and $[CDK_{I}]$ requires it.

In a further step, we apply scaling symmetries for reducing the number of parameters (i. e., we rewrite the system using dimensionless quantities). We used the Maple programme described in (Hubert and Labahn, [2013](https://arxiv.org/html/2605.06598v1#bib.bib237)) for an automated reduction. As the programme cannot work with symbolic exponents, we set all Hill coefficients $n_{k}$ equal to $2$ and afterwards checked that the obtained scaling symmetries are correct also for other values of the $n_{k}$. In fact, this was rather obvious, as the reduction does not affect the Hill functions because neither $[\overline{CDK}]$ nor any parameter $k_{i}$ is rescaled.

For biological reasons, which we will address later, we also constrain our reduction so that the parameters $b_{1}$ and $k_{3}$ remain unchanged in the reduced system. Then, after the rescaling, there are only $10$ parameters left, a reduction in the number of parameters by almost one-fourth. The new parameters are denoted by $c_{i}$, where $i=1,2,\ldots,10$, and to simplify the notation, we abbreviate from now the concentrations by $x_{1}=[CycB]$, $x_{2}=[\overline{CDK}]$, $x_{3}=[APC]$, and $x_{4}=[Wee1]$ and denote the rescaled concentrations by $y_{i}$. The new parameters and variables are defined as $c_{1}=b_{1},\ c_{2}=\frac{b_{2}}{\theta_{2}^{2}},\ c_{3}=\frac{b_{7}\theta_{4}}{b_{2}},\ c_{4}=\frac{\theta_{3}\theta_{6}}{b_{2}},\ c_{5}=k_{1},\ c_{6}=k_{2},\ c_{7}=k_{3},\ c_{8}=\frac{b_{2}\alpha_{1}}{\theta_{2}^{2}b_{7}},\ c_{9}=\frac{\alpha_{2}}{\theta_{2}},\ c_{10}=\frac{\alpha_{4}}{\theta_{2}},\ \tau=\theta_{2}t,\ \ y_{1}=\theta_{2}x_{1},\ \ y_{2}=x_{2},\ y_{3}=\frac{b_{7}\theta_{2}}{b_{2}}x_{3},\ \ y_{4}=\frac{\theta_{2}\theta_{3}}{b_{2}}x_{4}\,$. We arrive now at the rescaled system:

$$
\begin{aligned}
\displaystyle\begin{split}\frac{dy_{1}}{d\tau}&=c_{1}-c_{2}y_{1}y_{3}\,,\\
\frac{dy_{2}}{d\tau}&=c_{2}y_{1}+\frac{y_{2}^{n_{2}}}{y_{2}^{n_{2}}+c_{6}^{n_{2}}}\\
&-\left(c_{2}y_{1}+\frac{y_{2}^{n_{2}}}{y_{2}^{n_{2}}+c_{6}^{n_{2}}}+c_{2}y_{4}+c_{8}y_{3}\right)y_{2}\,,\end{split} & \displaystyle\begin{split}\frac{dy_{3}}{d\tau}&=c_{3}\frac{y_{2}^{n_{3}}}{y_{2}^{n_{3}}+c_{7}^{n_{3}}}-c_{9}y_{3}\,,\\
\frac{dy_{4}}{d\tau}&=c_{4}\frac{c_{5}^{n_{1}}}{c_{5}^{n_{1}}+y_{2}^{n_{1}}}-c_{10}y_{4}\,.\end{split}
\end{aligned}\tag{3}
$$

All reductions performed so far are of an exact nature. In a last step, we exploit that the evolution of the cell cycle of *D. melanogaster* embryogenesis involves both slow and fast time scales which allows for the use of approximate reduction techniques like the quasi-steady state approximation, see e. g. (Bertram and Rubin, [2017](https://arxiv.org/html/2605.06598v1#bib.bib173)) or (Kuehn, [2015](https://arxiv.org/html/2605.06598v1#bib.bib225)). According to (Alon, [2019](https://arxiv.org/html/2605.06598v1#bib.bib226), Sect. 1.3.1), there is a time response separation among transcription networks: input signals typically influence transcription factor activities on a subsecond period of time, and it frequently takes a few seconds for the active transcription factor’s binding to its DNA sites to reach equilibrium. The translation and transcription of the target gene take minutes, and the accumulation of the protein product can take several minutes to many hours. This leads to a large variation in the time response between the signal and the accumulation of protein products. On the slow timescale, transcription networks can be thought of as being in a steady state, whereas signaling transduction networks composed of interacting proteins function at a far slower pace. In our case the cyclin time response is faster than the other ones, so that we may assume that $[CycB]$ is in a quasi-steady state.

To make the time scale separation better visible, we perform a further rescaling of the variables $y_{1},y_{3}$, and $y_{4}$ to

$$
\begin{aligned}
\displaystyle z_{1}=\frac{c_{2}}{c_{1}}y_{1},\quad z_{3}=\frac{c_{9}}{c_{3}}y_{3},\quad z_{4}=\frac{c_{10}}{c_{4}}y_{4}\,.
\end{aligned}
$$

This transforms ([3](https://arxiv.org/html/2605.06598v1#S3.E3)) to the system

$$
\begin{aligned}
\displaystyle\begin{split}\frac{dz_{1}}{d\tau}=&c_{2}(1-\beta_{1}z_{1}z_{3})\,,\\
\frac{dz_{2}}{d\tau}=&c_{1}z_{1}+\frac{z_{2}^{n_{2}}}{z_{2}^{n_{2}}+c_{6}^{n_{2}}}\\
&-\left(c_{1}z_{1}+\frac{z_{2}^{n_{2}}}{z_{2}^{n_{2}}+c_{6}^{n_{2}}}+\beta_{2}z_{4}+\beta_{3}z_{3}\right)z_{2}\,,\\
\end{split} & \displaystyle\begin{split}\frac{dz_{3}}{d\tau}=&c_{9}\left(\frac{z_{2}^{n_{3}}}{z_{2}^{n_{3}}+c_{7}^{n_{3}}}-z_{3}\right)\,,\\
\frac{dz_{4}}{d\tau}=&c_{10}\left(\frac{c_{5}^{n_{1}}}{c_{5}^{n_{1}}+z_{2}^{n_{1}}}-z_{4}\right)\,,\end{split}
\end{aligned}\tag{4}
$$

where $\beta_{1}=\frac{c_{3}}{c_{9}},\ \ \beta_{2}=\frac{c_{2}c_{4}}{c_{10}},\ \ \beta_{3}=\frac{c_{3}c_{8}}{c_{9}}$. In this formulation, $\epsilon=\frac{1}{c_{2}}=\frac{\theta_{2}^{2}}{b_{2}}$ is the parameter leading to the time scale separation, i. e. it should be small enough so that the variable corresponding to cyclin ($z_{1}$) is in a quasi-steady state. Now the differential equation for cyclin is given by $\epsilon\frac{dz_{1}}{d\tau}=(1-\beta_{1}z_{1}z_{3})$ and in the limit $\epsilon\to 0$, corresponding to the quasi-steady state approximation, we get $z_{1}=1/(\beta_{1}z_{3})\,.$ This result agrees with the biological assumption that $z_{1}$ is degraded by $z_{3}$. Entering it into system ([4](https://arxiv.org/html/2605.06598v1#S3.E4)), we obtain our final reduced model

$$
\begin{aligned}
\displaystyle\begin{split}\frac{dz_{2}}{d\tau}=&\frac{c_{1}}{\beta_{1}z_{3}}+\frac{z_{2}^{n_{2}}}{z_{2}^{n_{2}}+c_{6}^{n_{2}}}\\
&-\left(\frac{c_{1}}{\beta_{1}z_{3}}+\frac{z_{2}^{n_{2}}}{z_{2}^{n_{2}}+c_{6}^{n_{2}}}+\beta_{2}z_{4}+\beta_{3}z_{3}\right)z_{2}\,,\end{split} & \displaystyle\begin{split}\frac{dz_{3}}{d\tau}=&c_{9}\left(\frac{z_{2}^{n_{3}}}{z_{2}^{n_{3}}+c_{7}^{n_{3}}}-z_{3}\right)\,,\\
\frac{dz_{4}}{d\tau}=&c_{10}\left(\frac{c_{5}^{n_{1}}}{c_{5}^{n_{1}}+z_{2}^{n_{1}}}-z_{4}\right)\,,\end{split}
\end{aligned}\tag{5}
$$

a system of three differential equations depending on nine parameters. In fact, the two parameters $c_{1}$ and $\beta_{1}$ appear only as the fraction $\frac{c_{1}}{\beta_{1}}$. Hence, the final model could be described with only $8$ parameters, if this fraction was treated as a single parameter. However, we will later perform a bifurcation analysis with $c_{1}$ as bifurcation parameter, as $c_{1}$ is the key parameter for our biological hypothesis about the role of the cyclin synthesis, and therefore we leave the combination $\frac{c_{1}}{\beta_{1}}$ as it is.

## 4 Bifurcation Analysis of the Reduced Model

As our reduced model ([5](https://arxiv.org/html/2605.06598v1#S3.E5)) still depends on nine parameters, a complete bifurcation analysis is not possible. Instead, in view of our biological question, we will concentrate on two parameters, namely on $c_{1}=b_{1}$ and $c_{7}=k_{3}$, i. e. on the cyclin synthesis and on the activation coefficient for APC. Below, we will perform for each of these two parameters an individual bifurcation analysis.

### 4.1 Biologically Relevant Steady States and Their Stability

We begin the mathematical analysis of the final reduced system ([5](https://arxiv.org/html/2605.06598v1#S3.E5)) by searching for biologically relevant steady states.

#### Proposition 1.

For any parameter vector $\theta\in\mathbbm{R}^{9}$ and for any integer values of the Hill coefficients $n_{1},n_{2},n_{3}\in\mathbbm{N}$, the reduced system ([5](https://arxiv.org/html/2605.06598v1#S3.E5)) possesses at least one positive steady state $\left(\hat{z}_{2},\hat{z}_{3},\hat{z}_{4}\right)\in\mathbbm{R}_{+}^{3}$.

#### Proof.

The steady states are given by the common zeros of the right-hand sides of ([5](https://arxiv.org/html/2605.06598v1#S3.E5)) which we denote by $(f_{1},f_{2},f_{3})$. Since $f_{2}$ and $f_{3}$ are linear in $\hat{z}_{3}$ and $\hat{z}_{4}$, respectively, we can express these two coordinates by $\hat{z}_{2}$:

$$
\begin{aligned}
\hat{z}_{3}=\frac{\hat{z}_{2}^{n_{3}}}{\hat{z}_{2}^{n_{3}}+c_{7}^{n_{3}}}\,,\qquad\hat{z}_{4}=\frac{c_{5}^{n_{1}}}{c_{5}^{n_{1}}+\hat{z}_{2}^{n_{1}}}\,.
\end{aligned}\tag{6}
$$

Obviously, these expressions yield positive values whenever $\hat{z}_{2}$ is positive. Entering them into the first equation yields a rational equation for $\hat{z}_{2}$ alone which after multiplication by the common denominator leads to the following polynomial equation for $\hat{z}_{2}$ where the degrees of the different terms depend on the Hill coefficients:

$$
\begin{aligned}
\left(-\beta_{1}\beta_{3}-\beta_{1}-c_{1}\right)\hat{z}_{2}^{n_{1}+n_{2}+2n_{3}+1}+\left(\beta_{1}+c_{1}\right)\hat{z}_{2}^{n_{1}+n_{2}+2n_{3}}\\
{}+\left(-\beta_{1}\beta_{2}c_{5}^{n_{1}}-\beta_{1}\beta_{3}c_{5}^{n_{1}}-\beta_{1}c_{5}^{n_{1}}-c_{1}c_{5}^{n_{1}}\right)\hat{z}_{2}^{n_{2}+2n_{3}+1}\\
{}+\left(-\beta_{1}\beta_{3}c_{6}^{n_{2}}-c_{1}c_{6}^{n_{2}}\right)\hat{z}_{2}^{n_{1}+2n_{3}+1}+\left(-\beta_{1}c_{7}^{n_{3}}-2c_{1}c_{7}^{n_{3}}\right)\hat{z}_{2}^{n_{1}+n_{2}+n_{3}+1}\\
{}+\left(\beta_{1}c_{7}^{n_{3}}+2c_{1}c_{7}^{n_{3}}\right)\hat{z}_{2}^{n_{1}+n_{2}+n_{3}}+\left(\beta_{1}c_{5}^{n_{1}}+c_{1}c_{5}^{n_{1}}\right)\hat{z}_{2}^{n_{2}+2n_{3}}+c_{1}c_{6}^{n_{2}}\hat{z}_{2}^{n_{1}+2n_{3}}\\
{}+\left(-\beta_{1}\beta_{2}c_{5}^{n_{1}}c_{7}^{n_{3}}-\beta_{1}c_{5}^{n_{1}}c_{7}^{n_{3}}-2c_{1}c_{5}^{n_{1}}c_{7}^{n_{3}}\right)\hat{z}_{2}^{n_{2}+n_{3}+1}-2c_{1}c_{6}^{n_{2}}c_{7}^{n_{3}}\hat{z}_{2}^{n_{1}+n_{3}+1}\\
{}+\left(-\beta_{1}\beta_{2}c_{5}^{n_{1}}c_{6}^{n_{2}}-\beta_{1}\beta_{3}c_{5}^{n_{1}}c_{6}^{n_{2}}-c_{1}c_{5}^{n_{1}}c_{6}^{n_{2}}\right)\hat{z}_{2}^{2n_{3}+1}-c_{1}c_{7}^{2n_{3}}\hat{z}_{2}^{n_{1}+n_{2}+1}+2c_{1}c_{6}^{n_{2}}c_{7}^{n_{3}}\hat{z}_{2}^{n_{1}+n_{3}}\\
{}+c_{1}c_{7}^{2n_{3}}\hat{z}_{2}^{n_{1}+n_{2}}+\left(\beta_{1}c_{5}^{n_{1}}c_{7}^{n_{3}}+2c_{1}c_{5}^{n_{1}}c_{7}^{n_{3}}\right)\hat{z}_{2}^{n_{2}+n_{3}}+c_{1}c_{5}^{n_{1}}c_{6}^{n_{2}}\hat{z}_{2}^{2n_{3}}-c_{1}c_{6}^{n_{2}}c_{7}^{2n_{3}}\hat{z}_{2}^{n_{1}+1}\\
{}-c_{1}c_{5}^{n_{1}}c_{7}^{2n_{3}}\hat{z}_{2}^{n_{2}+1}+\left(-\beta_{1}\beta_{2}c_{5}^{n_{1}}c_{6}^{n_{2}}c_{7}^{n_{3}}-2c_{1}c_{5}^{n_{1}}c_{6}^{n_{2}}c_{7}^{n_{3}}\right)\hat{z}_{2}^{n_{3}+1}+2c_{1}c_{5}^{n_{1}}c_{6}^{n_{2}}c_{7}^{n_{3}}\hat{z}_{2}^{n_{3}}+c_{1}c_{5}^{n_{1}}c_{7}^{2n_{3}}\hat{z}_{2}^{n_{2}}\\
{}+c_{1}c_{6}^{n_{2}}c_{7}^{2n_{3}}\hat{z}_{2}^{n_{1}}-c_{1}c_{5}^{n_{1}}c_{6}^{n_{2}}c_{7}^{2n_{3}}\hat{z}_{2}+c_{1}c_{5}^{n_{1}}c_{6}^{n_{2}}c_{7}^{2n_{3}}=0\,.
\end{aligned}\tag{7}
$$

Our claim is true, if and only if this polynomial has at least one real positive root. Independent of the chosen Hill coefficients, the term of highest degree is $\hat{z}_{2}^{n_{1}+n_{2}+2n_{3}+1}$ and it appears with a negative coefficient so that the polynomial becomes negative for sufficiently large $\hat{z}_{2}$. As the constant term $c_{1}c_{5}^{n_{1}}c_{6}^{n_{2}}c_{7}^{2n_{3}}$ – and thus the value of the polynomial for $\hat{z}_{2}=0$ – is positive, there must be at least one real positive root. ∎

A more delicate question is whether this steady state is unique. Furthermore, since the variable $z_{2}$ corresponds to a percentage, its biologically meaningful values are confined to the interval $[0,1]$ and thus we have to prove that the polynomial in ([7](https://arxiv.org/html/2605.06598v1#S4.E7)) has a root in this interval. We will now prove the existence of a parameter region $\Theta\subseteq\mathbbm{R}^{9}$ where this is the case. We cannot rigorously describe this region. Instead, we will show that for a certain parameter vector $\hat{\theta}$ and for certain Hill coefficients, the polynomial in ([7](https://arxiv.org/html/2605.06598v1#S4.E7)) possess only one real root in the interval $(0,1)$. Considering also the Hill coefficients as continuous quantities, this implies the existence of an open domain in $\mathbbm{R}^{12}$ where the positive steady state is unique and biologically meaningful.

The literature does not contain results on the direct measurement of the parameters in our model, but one can find some numerical estimates stemming from experimental data. We considered values published in (Deneke et al., [2016](https://arxiv.org/html/2605.06598v1#bib.bib224)), (Shindo and Amodeo, [2021b](https://arxiv.org/html/2605.06598v1#bib.bib227)) and (Pomerening et al., [2005](https://arxiv.org/html/2605.06598v1#bib.bib280)) where the effects of different proteins – including CDC25, Wee1, and APC – on the CDK dynamics were studied. We did not use the exact values from these references, but used them as starting points for adapting them to our biological context. The finally used values were also chosen with the numerical simulations in mind which we will discuss later so that our values lead to results similar to the experimentally observed cell cycle regulation for early embryogenesis of *D. melanogaster*. In the cited literature, all Hill coefficients $n_{k}$ were set to $5$. For this value the polynomial in ([7](https://arxiv.org/html/2605.06598v1#S4.E7)) has degree $21$ and consequently all subsequent analysis becomes very involved. We therefore used instead $2$ as common value for all Hill coefficients $n_{k}$ leading to a degree $9$ polynomial. Our complete parameter set can be found in Table [1](https://arxiv.org/html/2605.06598v1#S4.T1).

**Table 1.** Parameter values used for analysis and simulations.

|                  |                      |                      |
| ---------------- | -------------------- | -------------------- |
| $c_{1}=0.002$    | $c_{5}=0.02$         | $c_{6}=0.25$         |
| $c_{7}=0.25$     | $c_{9}=0.42857$      | $c_{10}=0.135857$    |
| $\beta_{1}=1.75$ | $\beta_{2}=0.150217$ | $\beta_{3}=7.142857$ |
| $n_{1}=2$        | $n_{2}=2$            | $n_{3}=2$            |

We claim now that for the parameter values given in Table [1](https://arxiv.org/html/2605.06598v1#S4.T1), there exists only one real steady state and it is biologically relevant. Entering the chosen parameter values into ([7](https://arxiv.org/html/2605.06598v1#S4.E7)), one obtains the following polynomial equation of degree nine (for the printing the coefficients have been truncated to six digits):

$$
\begin{aligned}
-14.252\hat{z}_{2}^{9}+1.752\hat{z}_{2}^{8}-0.896805\hat{z}_{2}^{7}\\
{}+0.110450\hat{z}_{2}^{6}-0.000392\hat{z}_{2}^{5}+6.73375\cdot 10^{-5}\hat{z}_{2}^{4}-9.08408\cdot 10^{-7}\hat{z}_{2}^{3}\\
{}+4.97656\cdot 10^{-7}\hat{z}_{2}^{2}-1.95312\cdot 10^{-10}\hat{z}_{2}+1.95312\cdot 10^{-10}\,.
\end{aligned}\tag{8}
$$

With standard numerical techniques (we used the roots method from NumPy which estimates the roots as the eigenvalues of the companion matrix), one can compute its nine roots which are all isolated and simple. Only one root is real and it also lies in the interval $[0,1]$. It leads to the unique steady state

$$
\begin{aligned}
\hat{z}_{2}=0.12555\,,\quad\hat{z}_{3}=0.20140\,,\quad\hat{z}_{4}=0.024748\,.
\end{aligned}\tag{9}
$$

Thus we can conclude that for the chosen parameter values, our model has only one real steady state which is also biologically relevant.

Given that the last two coefficients of the polynomial ([8](https://arxiv.org/html/2605.06598v1#S4.E8)) are very small (indicating the presence of two roots close to zero), one may wonder whether numerical errors may have lead here to wrong results. Since Python always computes in double precision, the two coefficients are well distinguishable from zero. We checked the residuals of all nine roots and they are all smaller than $10^{-20}$. In addition, we also computed a Sturm sequence (McNamee, [2007](https://arxiv.org/html/2605.06598v1#bib.bib27), Chapt. 2) for the polynomial ([8](https://arxiv.org/html/2605.06598v1#S4.E8)) which also confirmed that there is exactly one real root in the interval $(0,1]$. The computation of such a sequence is sometimes ill-conditioned, but as two different approaches lead to the same conclusion about the existence of exactly one biologically relevant steady state, we are very confident that it is correct.

We computed the roots of the polynomial ([7](https://arxiv.org/html/2605.06598v1#S4.E7)) also for three other sets of parameter values. Compared to Table [1](https://arxiv.org/html/2605.06598v1#S4.T1), we always only changed either the value of $c_{1}$ or the value of $c_{7}$ (the choice of the values will become apparent below). In each case, the polynomial ([7](https://arxiv.org/html/2605.06598v1#S4.E7)) has only one real root and it always lies in the interval $(0,1)$. Table [2](https://arxiv.org/html/2605.06598v1#S4.T2) contains the corresponding locations of the steady state.

**Table 2.** Steady states for different parameter values

| $c_{1}$ | $c_{7}$ | $\hat{z}_{2}$ | $\hat{z}_{3}$ | $\hat{z}_{4}$ |
| ------- | ------- | ------------- | ------------- | ------------- |
| $0.002$ | $0.250$ | $0.12555$     | $0.20140$     | $0.024748$    |
| $0.040$ | $0.250$ | $0.15401$     | $0.27511$     | $0.01658$     |
| $0.002$ | $0.040$ | $0.014352$    | $0.11405$     | $0.6601$      |
| $0.002$ | $0.500$ | $0.25766$     | $0.20983$     | $0.005989$    |

#### Remark 2.

Using advanced algorithms from real algebraic geometry (Basu et al., [2006](https://arxiv.org/html/2605.06598v1#bib.bib4)) like cylindrical algebraic decompositions, one can in principle determine for fixed Hill coefficients a semi-algebraic description of the parameter region $\Theta\subseteq\mathbbm{R}^{9}$ in which the polynomial equation ([7](https://arxiv.org/html/2605.06598v1#S4.E7)) possesses exactly one real root in the interval $(0,1)$. However, given the rather large number of parameters and the potentially high degree of the polynomial, this appears unfeasible in practice.

We now look at the stability of a steady state $\left(\hat{z}_{2},\hat{z}_{3},\hat{z}_{4}\right)$ using the Jacobian of the reduced system ([5](https://arxiv.org/html/2605.06598v1#S3.E5)). In a tedious, but straightforward computation, one obtains the characteristic polynomial $\lambda^{3}+\gamma_{2}\lambda^{2}+\gamma_{1}\lambda+\gamma_{0}=0$ where the coefficients are given by

$$
\begin{aligned}
\gamma_{2}=c_{9}+c_{10}-\delta_{1}\,,\quad\gamma_{1}=(c_{9}-\delta_{1})c_{10}-\delta_{2}\delta_{3}-\delta_{1}c_{9}\,,\quad\gamma_{0}=-(\delta_{1}c_{9}-\delta_{2}\delta_{3})c_{10}\,,
\end{aligned}
$$

with the shorthands

$$
\begin{aligned}
\displaystyle\delta_{1}=-\frac{c_{1}}{\beta_{1}\hat{z}_{3}}+\frac{k_{2}^{n_{2}}n_{2}\hat{z}_{2}^{n_{2}-1}(1-\hat{z}_{2})}{\left(\hat{z}_{2}^{n_{2}}+k_{2}^{n_{2}}\right)^{2}}-\frac{\hat{z}_{2}^{n_{2}}}{\hat{z}_{2}^{n_{2}}+k_{2}^{n_{2}}}-\beta_{2}\hat{z}_{4}-\beta_{3}\hat{z}_{3}
\end{aligned}
$$

$$
\begin{aligned}
\displaystyle\delta_{2}=-\frac{c_{1}}{\beta_{1}}\frac{1-\hat{z}_{2}}{\hat{z}_{3}^{2}}-\beta_{3}\hat{z}_{2}\,,\qquad\delta_{3}=\frac{c_{9}n_{3}k_{3}^{n_{3}}\hat{z}_{2}^{n_{3}-1}}{\left(\hat{z}_{2}^{n_{3}}+k_{3}^{n_{3}}\right)^{2}}\,.
\end{aligned}
$$

For the same parameter values as in Table [2](https://arxiv.org/html/2605.06598v1#S4.T2), we obtained at the corresponding unique steady states the eigenvalues shown in Table [3](https://arxiv.org/html/2605.06598v1#S4.T3). We always found one real and two conjugate complex eigenvalues. While the real eigenvalue is always negative, the real part of the complex eigenvalues is positive for our basic parameter set given in Table [1](https://arxiv.org/html/2605.06598v1#S4.T1) and negative for all other studied parameter sets. Hence, in the first case the steady state is unstable and one can expect an expanding oscillation nearby, whereas in the second case the steady state is stable with a damped oscillation nearby. This observation indicates the appearence of bifurcations, if we change either $c_{1}$ or $c_{7}$ around our basic parameter set. We will now show that indeed in both cases Hopf bifurcations exist leading to stable limit cycles.

**Table 3.** Eigenvalues of the Jacobian at the steady state for different parameter values

| $c_{1}$ | $c_{7}$ | $\lambda_{1}$ | $\lambda_{2/3}$          |
| ------- | ------- | ------------- | ------------------------ |
| $0.002$ | $0.250$ | $-0.135439$   | $0.081083\pm 0.866471i$  |
| $0.040$ | $0.250$ | $-0.135671$   | $-0.282007\pm 1.217285i$ |
| $0.002$ | $0.040$ | $-0.134$      | $-0.45392\pm 1.063i$     |
| $0.002$ | $0.500$ | $-0.135$      | $-0.5054\pm 1.0097i$     |

### 4.2 Bifurcation Analysis for the Parameter $c_{1}$

There exists a simple geometric explanation of the difference in the behavior for the two values of $c_{1}$ considered above. Our reduced model ([5](https://arxiv.org/html/2605.06598v1#S3.E5)) is three-dimensional so that nullclines define surfaces in $\mathbbm{R}^{3}$ making their geometry more difficult to analyze. We therefore follow an idea from (Marrone et al., [2023](https://arxiv.org/html/2605.06598v1#bib.bib26)) based on (Angeli et al., [2004](https://arxiv.org/html/2605.06598v1#bib.bib2)) using “pseudo-nullclines” which are plane curves: we decompose ([5](https://arxiv.org/html/2605.06598v1#S3.E5)) into two interconnected modules – one consisting of $z_{2}$, $z_{4}$, the other one of $z_{3}$:

$$
\begin{aligned}
\begin{aligned} \frac{dz_{2}}{d\tau}&=f_{2}(z_{2},z_{4};z_{3})\,,\\
\frac{dz_{4}}{d\tau}&=f_{4}(z_{2},z_{4})\,,\end{aligned}\qquad\qquad\frac{dz_{3}}{d\tau}=f_{3}(z_{3};z_{2})\,.
\end{aligned}\tag{10}
$$

Here, one should consider $z_{3}$ as a constant parameter in the left column and $z_{2}$ as a constant parameter in the right column. In the decomposition, we could have swapped the role of $z_{3}$ and $z_{4}$. However, in the above form we will obtain a $z_{2}$ pseudo-nullcline relating $z_{2}$ and $z_{3}$, i. e. the biologically most relevant quantities: CDK $(z_{2})$ and APC $(z_{3})$ which is equivalent to the input signal CycB ($z_{1}=1/(\beta_{1}z_{3})$).

Searching for a steady state of the left module leads to equations

$$
\begin{aligned}
z_{4}=h(z_{2})\,,\qquad f_{2}\bigl(z_{2},h(z_{2});z_{3}\bigr)=0\,,
\end{aligned}
$$

where $h$ is given by the right equation in ([6](https://arxiv.org/html/2605.06598v1#S4.E6)). In the $z_{2}$-$z_{3}$-plane, the $z_{2}$-pseudo-nullcline is now the curve implicitly described by the second equation, i. e. by

$$
\begin{aligned}
\frac{c_{1}}{\beta_{1}z_{3}}+\frac{z_{2}^{n_{2}}}{z_{2}^{n_{2}}+c_{6}^{n_{2}}}-\left(\frac{c_{1}}{\beta_{1}z_{3}}+\frac{z_{2}^{n_{2}}}{z_{2}^{n_{2}}+c_{6}^{n_{2}}}+\beta_{2}\frac{c_{5}^{n_{1}}}{c_{5}^{n_{1}}+z_{2}^{n_{1}}}+\beta_{3}z_{3}\right)z_{2}=0\,.
\end{aligned}\tag{11}
$$

Clearing the common denominator shows that it is a plane algebraic curve of degree seven. Because of the simple structure of our system, the $z_{3}$-pseudo-nullcline is defined by the vanishing of $f_{3}$, i. e. by the left equation in ([6](https://arxiv.org/html/2605.06598v1#S4.E6)).

Above the $z_{2}$-pseudo-nullcline, CDK becomes inactive ($\dot{z}_{2}<0$) and below it CDK is activated ($\dot{z}_{2}>0$). Analogously, to the left of the $z_{3}$-pseudo-nullcline, APC is degraded ($\dot{z}_{3}<0$) and to the right of it synthesized ($\dot{z}_{3}>0$). The $z_{3}$-pseudo-nullcline is a monotonically increasing curve approaching a saturation value for large $z_{3}$. It is affected only by changes in the parameter $c_{7}$ and even then only changes its steepness, but not its basic shape. By contrast, the $z_{2}$-pseudo-nullcline depends on six parameters – including $c_{1}$ – and its shape is strongly affected by changes in the parameter values.

![Figure 2.1](https://arxiv.org/html/2605.06598v1/Images/nsm4.png)

![Figure 2.2](https://arxiv.org/html/2605.06598v1/Images/gc0oo4.png)

![Figure 2.3](https://arxiv.org/html/2605.06598v1/Images/mc6.png)

![Figure 2.4](https://arxiv.org/html/2605.06598v1/Images/gc0oo7.png)

Figure 2: Phase portraits projected to $z_{2}$-$z_{3}$ plane and CDK evolution for two different values of $c_{1}$: top row $c_{1}=0.002$, bottom row $c_{1}=0.04$. The left column shows a typical trajectory together with the pseudo-nullclines (solid – $z_{2}$, dashed – $z_{3}$). In the right column a time plot of $z_{2}$ is depicted showing that in the first case a sustained and in the second case a strongly damped oscillation occurs.

In the left column of Figure [2](https://arxiv.org/html/2605.06598v1#S4.F2), one can see the pseudo-nullclines for the two considered values of $c_{1}$ with their intersection defining the steady state. While the dashed $z_{3}$-pseudo-nullcline is the same in both plots, the shape of the $z_{2}$-pseudo-nullcline changes drastically. For the smaller value, it has an S-shape with a local minimum at $(0.025,0.10518)$ and a local maximum at $(0.193,0.2214)$, whereas for the larger value it is a monotonically decreasing curve.

Such an S-shaped curve is reminiscent of relaxation oscillators like the FitzHugh–Nagumo model and indeed the phase portrait indicates the existence of a limit cycle. However, there are some differences probably due to the fact that here the pseudo-nullcline is described by a septic and not by cubic polynomial. In the considered parameter domain, we always have only one steady state and its stability is not simply determined from whether it lies on an increasing or decreasing branch of the $z_{3}$-pseudo-nullcline. One can identify three critical values of the cyclin synthesis $c_{1}$: above $c_{1}^{(s)}$ the S-shape of the $z_{2}$-pseudo-nullcline disappears and it becomes a monotonically decreasing curve; above $c_{1}^{(m)}$ the steady state lies to the right of the maximum of the $z_{2}$-pseudo-nullcline and at $c_{1}^{(h)}$ a Hopf bifurcation occurs and the stability of the steady state changes from unstable to stable for higher values.

Numerically, all three critical values are readily determined. The septic polynomial describing the $z_{2}$-pseudo-nullcline is quadratic in $z_{3}$ and hence can easily be solved in the form $z_{3}=g(z_{2};c_{1})$. The two roots have different signs and biologically only the positive sign is relevant; hence $g$ denotes from now on the positive solution. The critical value $c_{1}^{(s)}$ can be determined by solving the bivariate system

$$
\begin{aligned}
\frac{\partial g}{\partial z_{2}}(z_{2};c_{1})=\frac{\partial^{2}g}{\partial z_{2}^{2}}(z_{2};c_{1})=0
\end{aligned}\tag{12}
$$

leading to the value $c_{1}^{(s)}=0.039337$ (the $z_{2}$-value is not interesting). For determining the critical value $c_{1}^{(m)}$, we must solve the bivariate system

$$
\begin{aligned}
\frac{\partial g}{\partial z_{2}}(z_{2};c_{1})=g(z_{2};c_{1})-h(z_{2})=0
\end{aligned}\tag{13}
$$

where again $h$ is given by the right equation in ([6](https://arxiv.org/html/2605.06598v1#S4.E6)). One then finds $c_{1}^{(m)}=0.031080$. The Hopf point is as usually obtained by monitoring the complex eigenvalues of the Jacobian of ([5](https://arxiv.org/html/2605.06598v1#S3.E5)) at the steady state and is given by $c_{1}^{(h)}=0.0079967$. One also verifies easily that one deals with a supercritical Hopf bifurcation.

![Figure 3](https://arxiv.org/html/2605.06598v1/Images/bc1.png)

**Figure 3.** Bifurcation diagram for $c_{1}$. Green dots indicate the size of the limit cycle; the black line shows unstable steady states, the red line stable ones.

A bifurcation diagram in shown in Figure [3](https://arxiv.org/html/2605.06598v1#S4.F3). For lower $c_{1}$-values, a stable limit cycle (its size is indicated by green dots) around an unstable steady state (shown in black) exists. For higher $c_{1}$-values, we have a stable steady state (shown in red). Note that the situation changes completely for the border case $c_{1}=0$, as now $z_{2}=0$ becomes a multiple real root of the polynomial ([7](https://arxiv.org/html/2605.06598v1#S4.E7)). As this case is biologically irrelevant, we ignore it. The appearance of a Hopf bifurcation is not very surprising, as the eigenvalues shown above for two different $c_{1}$-values clearly indicate that between them a conjugate pair of complex eigenvalues crosses the imaginary axis. The left part of Figure [4](https://arxiv.org/html/2605.06598v1#S4.F4) shows for the lower value of $c_{1}$ a trajectory approaching the limit cycle. One can see that the approach concerns mainly the $z_{4}$-coordinate, i. e. the Wee1 concentration. Indeed, in the projection to the $z_{2}$-$z_{3}$-plane shown in the upper left part of Figure [2](https://arxiv.org/html/2605.06598v1#S4.F2), it looks like the trajectory would almost immediately reach the limit cycle, but in the 3D plot one can see that this is not really the case. Of course, this is mainly due to our choice of the initial value for the trajectory.

In the oscillatory regime, the phase portrait shown in the upper left part of Figure [2](https://arxiv.org/html/2605.06598v1#S4.F2) agrees well with the biological understanding of the cell cycle. Recall that by our quasi-steady state approximation the cyclin concentration is the reciprocal of the APC concentration ($z_{1}=1/\beta_{1}z_{3}$). If the system is in a state above both pseudo-nullclines, then changes in the APC (or cyclin) concentration have only a relative small effect on the CDK concentration. If the APC concentration crosses the $z_{2}$-pseudo-nullcline (which happens at a low value and thus at a high cyclin level), then CDK activation starts and its concentration increases rapidly. But then the APC concentration is also increasing and if it crosses again the $z_{2}$-pseudo-nullcline, then CDK becomes inactivated and after some time the cycle starts again. The S-phase roughly corresponds to the part of the limit cycle around the left crossing of the pseudo-nullcline (i. e. the troughs in the time evolution) and the M-phase to the part around the right crossing (i. e. the crests in the time evolution).

The right part of Figure [4](https://arxiv.org/html/2605.06598v1#S4.F4) shows the period length of the limit cycle as a function of the cyclin synthesis $c_{1}$ in a log-log plot. One can see that it can be very well described by a power law of the form $T=bc_{1}^{\alpha}$ with $b=0.43598$ and $\alpha=-0.186004$, i. e. roughly with the inverse of a fifth root. Thus for low cyclin synthesis the period length strongly growth. This agrees well with our biological hypothesis that a decrease in the cyclin synthesis is responsible for the increase in the cycle length in embryogensis.

![Figure 4.1](https://arxiv.org/html/2605.06598v1/Images/n3d5.png)

![Figure 4.2](https://arxiv.org/html/2605.06598v1/Images/pc1w.png)

Figure 4: Left: a trajectory approaching the limit cycle in 3D for the parameter values of Table [1](https://arxiv.org/html/2605.06598v1#S4.T1). Right: the period length $T$ of the limit cycle in dependence of the cyclin synthesis $c_{1}$.

### 4.3 Bifurcation Analysis for the Parameter $c_{7}$

From a biological perspective, cyclin begins to degrade when APC ($z_{3}$) is activated, so the activation coefficient $c_{7}$ for APC is another parameter of interest for us. We continue to use the parameter values from Table [1](https://arxiv.org/html/2605.06598v1#S4.T1), but now consider changes of the value of $c_{7}$. Figure [5](https://arxiv.org/html/2605.06598v1#S4.F5) shows phase portraits and the CDK evolution for the three different values of $c_{7}$ for which we computed above the eigenvalues. As already discussed, the $z_{2}$-pseudo-nullcline is independent of $c_{7}$ and hence is the same in all three phase portraits. The shape of the $z_{3}$-pseudo-nullcline does not strongly change with $c_{7}$; it remains a monotonically increasing curve, but the increase gets smaller for larger values of $c_{7}$.

![Figure 5.1](https://arxiv.org/html/2605.06598v1/Images/nsm3.png)

![Figure 5.2](https://arxiv.org/html/2605.06598v1/Images/fc0oo8.png)

![Figure 5.3](https://arxiv.org/html/2605.06598v1/Images/nsm1.png)

![Figure 5.4](https://arxiv.org/html/2605.06598v1/Images/fc0oo9.png)

![Figure 5.5](https://arxiv.org/html/2605.06598v1/Images/nsm2.png)

![Figure 5.6](https://arxiv.org/html/2605.06598v1/Images/fc0oo10.png)

Figure 5: Phase portraits projected to $z_{2}$-$z_{3}$ plane and CDK evolution for three different values of $c_{7}$: top row $c_{7}=0.04$, middle row $c_{7}=0.25$, bottom row $c_{1}=0.5$. The left column shows a typical trajectory together with the pseudo-nullclines (solid – $z_{2}$, dashed – $z_{3}$). In the right column a time plot of $z_{2}$ is depicted showing that in the middle row a sustained and in the two other rows a strongly damped oscillation occurs.

The middle row corresponds to the values of Table [1](https://arxiv.org/html/2605.06598v1#S4.T1) and shows again the limit cycle we discussed already in the previous section. But one can see that for both smaller and larger values of $c_{7}$, the limit cycle disappears and is replaced by damped oscillations. Together with the above presented eigenvalues, this observation indicates that there is a “Hopf bubble”, i. e. two subsequent Hopf bifurcations – one creating a limit cycle and one destroying it. The bifurcation diagram in Figure [6](https://arxiv.org/html/2605.06598v1#S4.F6) confirms this expectation.

Again one can determine several critical values of $c_{7}$. At $c_{7}^{(m)}$ the steady state lies at the minimum of the $z_{2}$-pseudo-nullcline and at $c_{7}^{(M)}$ at the maximum, so that only for values $c_{7}^{(m)}<c_{7}<c_{7}^{(M)}$ the steady state lies in the ascending part of the $z_{2}$-pseudo-nullcline. These two values are easily computed. As the $z_{2}$-pseudo-nullcline does not depend on $c_{7}$, it is given as the graph of $z_{3}=g(z_{2})$ with the same notation as in the previous section and we can directly determine the locations $z_{2}^{(m/M)}$ of the two extrema as the zeros of $g^{\prime}$. Then we solve the equations $g(z_{2}^{(m/M)})-h(z_{2}^{(m/M)};c_{7})=0$ to obtain $c_{7}^{(m)}=0.072379$ and $c_{7}^{(M)}=0.36160$. The two Hopf points $c_{7}^{(h)}$, $c_{7}^{(H)}$ are again computed by monitoring the real parts of the complex eigenvalues and are found to be $c_{7}^{(h)}=0.12997$ and $c_{7}^{(H)}=0.28328$. It follows from these critical values that in the oscillatory regime, the unstable steady state is always in the ascending part of the $z_{2}$-pseudo-nullcline. However, as we have $c_{7}^{(m)}<c_{7}^{(h)}<c_{7}^{(H)}<c_{7}^{(M)}$, we can also find stable steady states on this ascending part.

![Figure 6](https://arxiv.org/html/2605.06598v1/Images/bc7.png)

**Figure 6.** Bifurcation diagram for $c_{7}$. Green dots indicate the size of the limit cycle; the black line shows unstable steady states, the red line stable ones.

## 5 Comparison with Experimental Results

As frequently discussed in the literature – see e. g. (Deneke et al., [2016](https://arxiv.org/html/2605.06598v1#bib.bib224)), (Farrell and O’Farrell, [2014](https://arxiv.org/html/2605.06598v1#bib.bib235)), (Shindo and Amodeo, [2021a](https://arxiv.org/html/2605.06598v1#bib.bib234)) or (Shindo and Amodeo, [2021b](https://arxiv.org/html/2605.06598v1#bib.bib227)) – the period length in the early embryogenesis of *D. melanogaster* gets longer and longer after cycle $10$, and this can be seen by decreasing the synthesis of cyclin slightly in each cycle (see (Shindo and Amodeo, [2021a](https://arxiv.org/html/2605.06598v1#bib.bib234))). The early embryonic cell cycles of *D. melanogaster* only consist of S and M phases, which causes very quick divisions. However, at some point, the gap phases G2 are introduced to the cell cycle, which lengthens the duration of the cycle. For instance, the appearance of G2 in cell cycle 14 is accompanied by the inhibitory phosphorylation of almost all CDK. The downregulation of CDK, which results from the destruction of cyclin, causes this G2 phase, and such extensive inhibitory phosphorylation does not happen in the early cycles. The other reason is that after the first 10 cycles, which take place in the inner part of the embryo, the nuclei migrates into the periphery of the embryo; this might lead to the lengthening of the cell cycle after cycle $10$.

In our mathematical model, we have so far always treated the cyclin synthesis, i. e. the parameter $c_{1}$, as a constant and then obtained for suitable parameters a sustained oscillation implying in particular that the period length remains constant in contrast to the experimental findings. We now treat $c_{1}$ as a function of time; one may consider this as a kind of heuristic reduction of a more complicated model involving also a differential equation for $c_{1}$. We assume that cyclin is created in some process and then degraded in another process and that both process operate on roughly the same time scale. It is well-known – e. g. from the kinetics of the ABC reaction – that in such a situation the concentration of the intermediate product, in our case cyclin, can be approximately described by the dynamics

$$
\begin{aligned}
c_{1}(\tau)=c_{1}^{(0)}\tau e^{-\gamma\tau}\,.
\end{aligned}\tag{14}
$$

Here the factor $\tau$ describes that cyclin has first to be produced and then degrades exponentially according to the second factor with a constant rate $\gamma$. This functions increases from zero until it reaches at $\tau=1/\gamma$ a maximum value of $e^{-1}c_{1}^{(0)}/\gamma$; then it declines monotonically towards zero. By our results above, this means that we can expect after some transient phase a lengthening of the period of the oscillation.

![Figure 7](https://arxiv.org/html/2605.06598v1/Images/c10.png)

(a) Numerical simulation starting after cycle 10 with $c_{1}^{(0)}=0.0001$ and $\gamma=0.055$.

![Figure 7](https://arxiv.org/html/2605.06598v1/Images/modified_cycle1_14.png)

(b) Numerical simulation of first 14 cycles with $c_{1}^{(0)}=0.0001$ and $\gamma=0.048$.

![Figure 7](https://arxiv.org/html/2605.06598v1/Images/cx11.png)

(c) Experimental results from Deneke et al. ([2016](https://arxiv.org/html/2605.06598v1#bib.bib224)).

![Figure 7](https://arxiv.org/html/2605.06598v1/Images/modified_cycle1_14_z2.png)

(d) Enlarged bottom part of above plot.

Figure 7: Top row: Time evolution of CDK concentration (i. e. $z_{2}$) for an exponentially decreasing cyclin synthesis $c_{1}$. Left: cycles 11 to 14; right: first 14 cycles. Bottom row: Left: experimental results for cell cycles 10 to 14 taken from Deneke et al. ([2016](https://arxiv.org/html/2605.06598v1#bib.bib224)). Right: Zoom into bottom part of ([7(b)](https://arxiv.org/html/2605.06598v1#S5.F7.sf2)).

Figures [7(a)](https://arxiv.org/html/2605.06598v1#S5.F7.sf1) and [7(b)](https://arxiv.org/html/2605.06598v1#S5.F7.sf2) show the results of numerical simulations with such a variable cyclin synthesis. In a first simulation, we started from cycle $1$ using the parameter values $c_{1}^{(0)}=0.0001$ and $\gamma=0.048$ (Figure [7(b)](https://arxiv.org/html/2605.06598v1#S5.F7.sf2)). Here one can see that in the first 10 cycles, the period length grows only very moderately, whereas in the last four cycles a significant increase occurs. Figure [7(d)](https://arxiv.org/html/2605.06598v1#S5.F7.sf4) zooms into the bottom part of the plot and shows that from cycle 2 on, the troughs are getting deeper and deeper. This represents exactly the behavior observed in experiments (Deneke et al., [2016](https://arxiv.org/html/2605.06598v1#bib.bib224)). In (Edgar et al., [1994a](https://arxiv.org/html/2605.06598v1#bib.bib292)), a similar behavior was reported for CycB, but as CycB is activating CDK, this is equivalent to our finding. If one plots the projection of the trajectory to the $z_{2}$-$z_{3}$-plane, it seems, as if the 14 cycles are almost identical. But in a 3D plot (not shown here) one can see that over the 14 cycles the Wee1 level has significantly increased. We are not aware of any experimental evidence for such a behavior so that it is unclear whether this represents an artifact of our model or the chosen parameter values.

Since many studies concentrate on cycles $10$ to $14$, we performed a second simulation with the parameter values $c_{1}^{(0)}=0.0001$ and $\gamma=0.048$ to capture the behaviors of these cycles (Figure [7(a)](https://arxiv.org/html/2605.06598v1#S5.F7.sf1)). For simplicity, we used here actually a simple exponential decline of $c_{1}$, i. e. we omitted the factor $\tau$, as it is mainly relevant at the beginning of embryogenesis. One can clearly observe a significant increase in the period length from cycle to cycle. In both simulations, no oscillations occur after cycle 14.

Our results align qualitatively quite well with the experimental results of (Deneke et al., [2016](https://arxiv.org/html/2605.06598v1#bib.bib224)) shown in Figure [7(c)](https://arxiv.org/html/2605.06598v1#S5.F7.sf3). In this article, they demonstrated how the CDK signal shows clear oscillations corresponding to cell-cycle progression. While the shape of the oscillation is different in our simulations compared to the experiment, the periodic behavior is well reproduced and also the fact that the oscillations stop after cycle 14. Furthermore, one can in both simulation and experiment clearly distinguish the S and the M phases: the S phases are characterised by low CDK levels and the M phases by high CDK levels. In our model, the S phases are much longer than the M phases which is in contrast to the experimental findings. Perhaps this could be corrected by changing some of the other parameters.

## 6 Conclusion

We presented a mathematical model for the cell cycle dynamics in *D. melanogaster* during early embryogenesis by reviewing experimental findings and translating them into a biochemically sound model of CDK regulation with positive and negative feedback loops. The raw model consists of six ordinary differential equations depending on fifteen parameters and three Hill coefficients. Using exact reduction methods like conservation laws and dimensional analysis and approximate methods like a quasi-steady state assumption, we reduced to a model consisting of three differential equations depending on nine parameters and three Hill coefficients. We then performed a bifurcation analysis with respect to two key parameters, the cyclin synthesis and the activation coefficient for APC, for proving the existence of regions in the parameter space where the solutions exhibit limit cycle oscillations as observed in experiments. We found a single Hopf bifurcation when changing the cyclin synthesis entailing that oscillations occur only when its concentration drops below a certain threshold. When changing the activation coefficient for APC, a Hopf bubble appears, indicating that it must take its values in a certain finite interval for oscillations.

In numerical simulations, we investigated in particular the dependence of the period length on the cyclin synthesis. The results support our biological hypothesis that the period length increases with decreasing cyclin synthesis by showing a simple inverse power law dependency. For a comparison with experimental results, we prescribed a concrete dynamics for the cyclin synthesis by considering it as a time dependent function. Qualitatively, the simulation results agreed fairly well with experimental data reported in the literature. We could observe for suitable parameter values the same increase of the period length over the first 14 cycles and the oscillations stopped after cycle 14. We could also observe that the CDK minima got lower in each cycle. Not so well represented was the shape of the oscillations. In particular, the M phases were much shorter than the S phases. One can hope that this could be changed by modifications of other model parameters.

According to (Novak and Tyson, [1993](https://arxiv.org/html/2605.06598v1#bib.bib236)), (Pomerening et al., [2003](https://arxiv.org/html/2605.06598v1#bib.bib231)) and references therein, the embryogenesis of *Xenopus laevis* exhibits a similar type of oscillations. In yeast, Swe1 regulates Cdc28 in a manner analogous to the Wee1-mediated Cdk inhibition in *Drosophila melanogaster* (Causton et al., [2015](https://arxiv.org/html/2605.06598v1#bib.bib291)). Our numerical simulations for Wee1 qualitatively agrees with the experimental results reported for Swe1 of the yeast cell cycle in (Causton et al., [2015](https://arxiv.org/html/2605.06598v1#bib.bib291)). With small modifications, our model should thus also work well for the early cell cycles of certain other organisms.

## References (32 total, showing 32)

- C. Acquaviva and J. Pines (2006) The anaphase-promoting complex/cyclosome: APC/C. Journal of cell science 119 (12), pp. 2401–2404.

- U. Alon (2019) An introduction to systems biology: design principles of biological circuits. 2nd edition, Chapman and Hall/CRC, Boca Raton, FL.

- D. Angeli, J.E. Ferrell, and E.D. Sontag (2004) Detection of multistability, bifurcations, and hysteresis in a large class of biological positive-feedback systems. Proc. Natl. Acad. Sci. USA 101, pp. 1822–1827.

- S. Basu, R. Pollack, and M.F. Roy (2006) Algorithms in real algebraic geometry. $2^{nd}$ edition, Springer-Verlag, Berlin.

- R. Bertram and J.E. Rubin (2017) Multi-timescale systems and fast-slow analysis. Mathematical biosciences 287, pp. 105–121.

- H. Blank, E. No, and M. Polymenis (2025) Cdk activation by phosphorylation: linking growth signals to cell cycle control. Biochemical Society Transactions 53 (02), pp. BST20253004.

- H. C. Causton, K. A. Feeney, C. A. Ziegler, and J. S. O’Neill (2015) Metabolic cycles in yeast share features conserved among circadian rhythms. Current Biology 25 (8), pp. 1056–1062.

- V.E. Deneke, A. Melbinger, M. Vergassola, and S. Di Talia (2016) Waves of Cdk1 activity in S phase synchronize the cell cycle in drosophila embryos. Developmental cell 38 (4), pp. 399–412.

- B. A. Edgar, F. Sprenger, R. J. Duronio, P. Leopold, and P. H. O’Farrell (1994a) Distinct molecular mechanism regulate cell cycle timing at successive stages of drosophila embryogenesis.. Genes & development 8 (4), pp. 440–452.

- L. G. Edgar, N. Wolf, and W. B. Wood (1994b) Early transcription in caenorhabditis elegans embryos. Development 120 (2), pp. 443–451.

- J.A. Farrell and P.H. O’Farrell (2014) From egg to gastrula: how the cell cycle is remodeled during the drosophila mid-blastula transition. Annual review of genetics 48 (1), pp. 269–294.

- V. E. Foe and B. M. Alberts (1983) Studies of nuclear and cytoplasmic behaviour during the five mitotic cycles that precede gastrulation in drosophila embryogenesis. Journal of cell science 61 (1), pp. 31–70.

- E. Hubert and G. Labahn (2013) Scaling invariants and symmetry reduction of dynamical systems. Foundations of Computational Mathematics 13, pp. 479–516.

- M. Kataria and H. Yamano (2019) Interplay between phosphatases and the anaphase-promoting complex/cyclosome in mitosis. Cells 8 (8), pp. 814.

- C. Kuehn (2015) Multiple time scale dynamics. Applied Mathematical Sciences, Vol. 191, Springer, Cham, Switzerland.

- D. Lew and S. Kornbluth (1996) Regulatory roles of cyclin dependent kinase phosphorylation in cell cycle control. Current opinion in cell biology 8 (6), pp. 795–804.

- L. Lu, M. R. Domingo-Sananes, M. Huzarska, B. Novak, and K. Gould (2012) Multisite phosphoregulation of Cdc25 activity refines the mitotic entrance and exit switches. Proceedings of the National Academy of Sciences 109 (25), pp. 9899–9904.

- J.I. Marrone, J.A. Sepulchre, and A.C. Ventura (2023) Pseudo-nullclines enable the analysis and prediction of signaling model dynamics. Front. Cell Dev. Biol. 11, pp. 1209589.

- J. E. Marsden and M. McCracken (2012) The hopf bifurcation and its applications. Vol. 19, Springer Science & Business Media, New York.

- H. K. Matthews, C. Bertoli, and R. A. De Bruin (2022) Cell cycle control in cancer. Nature reviews Molecular cell biology 23 (1), pp. 74–88.

- J.M. McNamee (2007) Numerical methods for roots of polynomials. Vol. 2, Elsevier, Amsterdam.

- A.W. Murray (1992) Creative blocks: cell-cycle checkpoints and feedback controls. Nature 359 (6396), pp. 599–601.

- B. Novak and J.J. Tyson (1993) Numerical analysis of a comprehensive model of m-phase control in xenopus oocyte extracts and intact embryos. Journal of cell science 106 (4), pp. 1153–1168.

- A. J. Pluta, C. Studniarek, S. Murphy, and C. Norbury (2024) Cyclin-dependent kinases: masters of the eukaryotic universe. Wiley Interdisciplinary Reviews: RNA 15 (1), pp. e1816.

- J.R. Pomerening, S.Y. Kim, and J.E. Ferrell (2005) Systems-level dissection of the cell-cycle oscillator: bypassing positive feedback produces damped oscillations. Cell 122 (4), pp. 565–578.

- J.R. Pomerening, E.D. Sontag, and J.E. Ferrell Jr. (2003) Building a cell cycle oscillator: hysteresis and bistability in the activation of cdc2. Nature cell biology 5 (4), pp. 346–351.

- S. Rionero (2019) Hopf bifurcations in dynamical systems. Ricerche di Matematica 68, pp. 811–840.

- Y. Shindo and A.A. Amodeo (2021a) Excess histone H3 is a competitive chk1 inhibitor that controls cell-cycle remodeling in the early drosophila embryo. Current Biology 31 (12), pp. 2633–2642.

- Y. Shindo and A.A. Amodeo (2021b) Modeling the role for nuclear import dynamics in the early embryonic cell cycle. Biophysical journal 120 (19), pp. 4277–4286.

- J. Stumpff, T. Duncan, E. Homola, S. Campbell, and T. Su (2004) Drosophila wee1 kinase regulates cdk1 and mitotic entry during embryogenesis. Current Biology 14 (23), pp. 2143–2148.

- L. Wilson, P.T. Matsudaira, L.S.B. Goldstein, and E.A. Fyrberg (1995) Drosophila melanogaster: practical uses in cell and molecular biology. Academic Press, San Diego.

- K. Yuan, C.A. Seller, A.W. Shermoen, and P.H. O’Farrell (2016) Timing the Drosophila mid-blastula transition: a cell cycle-centered view. Trends in Genetics 32 (8), pp. 496–507.
