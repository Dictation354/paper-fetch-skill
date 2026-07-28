---
title: "Hepatitis C virus modelled as an indirectly transmitted infection highlights the centrality of injection drug equipment in disease dynamics"
authors: "Miller-Dickson, Miles D., Meszaros, Victor A., Almagro-Moreno, Salvador, Brandon Ogbunugafor, C."
journal: "Journal of The Royal Society Interface"
doi: "10.1098/rsif.2019.0334"
published: "2019/09/01"
source: "royalsocietypublishing_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 8375
---

# Hepatitis C virus modelled as an indirectly transmitted infection highlights the centrality of injection drug equipment in disease dynamics

## Abstract

The hepatitis C virus (HCV) epidemic often occurs through the persistence of injection drug use. Mathematical models have been useful in understanding various aspects of the HCV epidemic, and especially, the importance of new treatment measures. Until now, however, few models have attempted to understand HCV in terms of an interaction between the various actors in an HCV outbreak—hosts, viruses and the needle injection equipment. In this study, we apply perspectives from the ecology of infectious diseases to model the transmission of HCV among a population of injection drug users. The products of our model suggest that modelling HCV as an indirectly transmitted infection—where the injection equipment serves as an environmental reservoir for infection—facilitates a more nuanced understanding of disease dynamics, by animating the underappreciated actors and interactions that frame disease. This lens may allow us to understand how certain public health interventions (e.g. needle exchange programmes) influence HCV epidemics. Lastly, we argue that this model is of particular importance in the light of the modern opioid epidemic, which has already been associated with outbreaks of viral diseases.

## 1 Introduction

While the ecology of infectious disease is a rich field with decades worth of empirical evidence and theory, there are aspects that remain relatively under-explored. One example is the importance of the free-living survival stage of certain pathogens, where diseases are transmitted indirectly between hosts through an environmental reservoir intermediate. These include infections transmitted indirectly between hosts via a surface or reservoir intermediate—often abiotic—where the pathogen lives freely and independently of a host [1–18], sometimes described as ‘sit and wait’ infections [19]. Other studies have focused on systems where pathogens are growing in the environment [9], or have explored indirectly transmitted infections in theoretical terms [12,15]. While frameworks already exist for studying indirect environmental transmission, most are engineered with constraints that render their application necessarily narrow [6], limiting their relevance for a wider number of indirectly transmitted infections.

One class of diseases where the indirect transmission paradigm has been scarcely applied are those spread through injection drug use in urban settings, such as the human immunodeficiency virus (HIV) and hepatitis C virus (HCV). HIV has been the object of many important mathematical models [20,21], some of which have implemented injection drug use effectively, even focusing on the specific dynamics of injection equipment [22–25]. HCV has also been studied using modelling methods, many focusing on treatment [26–28] and others on the particulars of transmission in injection drug-user communities [29–35]. Importantly, none of these existing dynamical models consider the peculiar ecology of HCV transmission, where transmission events occur through an environmental reservoir (injection equipment) that resembles a disease vector [36,37]. Unlike an insect vector, however, injection equipment is not an organism and is more realistically considered an abiotic reservoir for infection, similar to the role that the water supply serves in an outbreak of cholera or other waterborne diseases [38]. As HCV continues to pose a serious public health challenge in many communities, there is a need to understand how the dynamics of injection equipment influence HCV transmission. This is especially important for informing the utility of harm reduction programmes, such as needle exchange, which have been effective in decreasing transmission of HIV and HCV [39,40]. Lastly, but perhaps most importantly, the urgency for understanding these dynamics has increased dramatically in recent years with the growth of the modern opioid epidemic, much of it involving injection drug use [41,42]. The lack of models of HCV that specifically consider injection equipment, and increased social urgency related to the modern opioid epidemic implore more adaptable mathematical models of injection-drug use that could facilitate a better understanding of and predictions for the trajectory of modern HCV infections.

In this study, we model HCV as an indirectly (or environmentally) transmitted infection, where the drug paraphernalia serves as the environmental reservoir. As HCV epidemics are partly defined by injection drug users and injection drug equipment, we argue that this indirectly transmitted lens captures aspects that prior models have not. In §[2](#s2), we introduce a theoretical iteration of an indirectly transmitted infection using a standard epidemiological model imbued with an environmental reservoir compartment. We describe analytic equations of such a system, and derive the reproductive number (R0) using analytic methods. Then in §[3](#s3), we introduce the full HCV mathematical model, demonstrating how it allows one to examine several otherwise-overlooked features of disease dynamics. We pontificate on these results in light of the ecology of infectious diseases, and in terms of public health policies, especially as they relate to the modern opioid epidemic.

## 2 An elementary adapted SIR indirectly transmitted iteration

### 2.1 Description

While the emphasis of our examination will reside in how we analyse a HCV epidemic, for explanatory purposes we will begin by describing how an environmental reservoir modifies very basic concepts in a classic, purposefully prosaic susceptible–infected–recovered (SIR) mathematical model. We will explain the basic structure of a model of indirect transmission, after which the HCV-specific iteration will be discussed.

While there are several existing frameworks that can be used to describe infections spreading through an environmental reservoir, we have conveniently labelled ours the waterborne, abiotic and indirectly transmitted (W.A.I.T.) infection model. Many diseases can be modelled using this kind of approach, but this study applies it to HCV in a community of injection drug users, which has not been previously modelled in this manner.

We use a standard SIR framework, where dynamics are defined by changes in a population of susceptible (S), infected (I) and recovered (R) hosts. Classically, flow of infection through the system is defined by contact between susceptible and infected individuals, often driven by a β factor, or transmission coefficient. Figure 1 is a compartmental model that depicts this interaction, and adds two additional compartments, labelled with a W (for W.A.I.T.), which influence the flow of hosts from the susceptible to infected compartments—indicated by the dashed lines in the figure.

![Figure 1](https://trs.silverchair-cdn.com/trs/content_public/journal/rsif/16/158/10.1098_rsif.2019.0334/6/rsif20190334f01.png?Expires=1782305913&Signature=yGSyfPn0u~rYiwBrh1wN6MGuOgIedzJ9VoZ8x2rFf2KsMYmmeMpdzcAeBobJnCDYwZIGAj8CJcU89rf-PUcuj3pXGClP~49IIJ8IzfiIwdjt03nBBe9Z8EaApRlH3UPx-RTQCtrokc0o54qo9fS1M0-r8MTN8zjelQJOvm8K7fUbJn~7KMFIE03QHTh3kS6hv1XcLsmvYqKVRXLIbivt0C9U5KmkdURQvdY2VkrB0uEVS07XH5~4N0btC5NsjiTuq7X3hmChas~bGITJEK7gRMQOiKE3A5rq4w5YlguwJ8s8448buB9k9VCaMkd7KOSV0QYmTcKeP9NvpHjATSLTIg__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 1.** Adapted SIR compartmental diagram. This depicts a standard SIR style compartmental model with the added compartments (shaded) corresponding to the W.A.I.T. environment. Note the dynamical properties of the Wi and Wu compartments. (Online version in colour.)

### 2.2 The adapted SIR compartmental diagram

The S, I and R compartments represent the usual susceptible, infected and recovered populations of hosts, respectively. Wu and Wi represent uninfected and infected populations of environmental agents, respectively.

In traditional SIR models, the rate of new infection (arrow from the S compartment to the I) is generally proportional to the product of the susceptible and the infected populations, i.e. proportional to SI. In the W.A.I.T. framework, the environmental compartment plays a role analogous to the infected host compartment in driving the rate of infection. In this specific example, the Wi compartment contributes to the rate of infection as a fraction, Wi/(Wi + Wu), which appears as a factor in the rate terms.

The epidemic is then driven by a series of interactions: between uninfected (susceptible) hosts S and the infected (transmitting) environmental compartment Wi, and interactions between infected individuals I and the uninfected environmental compartment Wu. The epidemic is sustained through infected hosts I depositing pathogen into the environmental reservoir, creating new infections, which can then infect more susceptible hosts S (in a process resembling a feedback loop). These dynamics can be captured by the set of dynamical equations and visualized with the diagram in figure 1:
Equation 2.1: $\frac{dS}{dt} = \pi_{S} - \beta S\frac{W_{i}}{W_{u} + W_{i}} - \mu S,$
Equation 2.2: $\frac{dI}{dt} = \beta S\frac{W_{i}}{W_{u} + W_{i}} - \nu I - \mu I,$
Equation 2.3: $\frac{dR}{dt} = \nu I - \mu R,$
Equation 2.4: $\frac{dW_{u}}{dt} = \pi_{W} - \alpha I\frac{W_{u}}{W_{u} + W_{i}} - kW_{u}$
Equation 2.5: ${and}\qquad\frac{dW_{i}}{dt} = \alpha I\frac{W_{u}}{W_{u} + W_{i}} - kW_{i}.\qquad$

Equations (2.1)–(2.5) define an extension of the prosaic SIR model. πS is the birthrate of new susceptible hosts and μ is the fractional death rate of hosts. In this context, β represents the strength of the interaction between the susceptible hosts S and the environmental reservoir. This will generally be proportional to the rate of contact between the two. Similarly, α characterizes the strength of interaction between infected hosts I and the environmental reservoir, and is also generally proportional to the contact rate between the two. α and β, while both generally proportional to the contact rate between environmental agents and living hosts, are distinguished by factors that indicate the probabilities of spreading the infection either from host to environment, as in the case of α, or from the environment to host, as in the case of β. Note that α and β could be replaced with the same parameter in settings where the infection is guaranteed to spread at any encounter with an infected host or environmental agent. ν represents the fractional recovery rate, πW is the birthrate of new uninfected environmental agents and k is the fractional death or discard rate of environmental agents. Note that the discard rate k (which includes any force that removes environmental agents from the system) can be split into two discard rates, one for the infected compartment, and one for the uninfected compartment (we do, in fact make this distinction in the full HCV model). For simplicity, we will tend to set the discard rates of these two compartments equal, where there are two parameters, as we have no current mathematical grounds to distinguish them.

Also note that this model resembles vector-borne transmission models such as those used to study malaria [37]. In fact, prior studies have explored the utility of applying vector-borne transmission models to the spread of infection with needles as a proxy for vectors—although, only in the context of HIV [36]. In this paper, however, we wish to emphasize peculiarities of the spread of HCV and, further, to elaborate some features of the R0 expression in the context of these shared dynamical settings—between hosts and agents—which we believe have not been rigorously addressed in the existing literature.

### 2.3 W.A.I.T. framework influences the basic reproductive number in a standard SIR model

Next, we briefly consider how the value of the basic reproductive ratio R0 in this model compares to its SIR counterpart. While R0 can have different theoretical formulations, we rely on definitions as provided by Jones [43] and Diekmann et al. [44]. In a density-dependent SIR model with constant birth of susceptible hosts πS and death rate proportional to the host population −μS, the R0 value is given by
Equation 2.6: $R_{0}^{SIR} = \frac{\beta\pi_{S}}{\nu\mu},$
or sometimes, more simply, $R_{0}^{SIR} = \beta/\nu$, depending on the form of the SIR equations used, e.g. frequency-dependent, constant population, etc. In this equation, β is the traditional transmission coefficient. It represents the coupling strength between infected and uninfected hosts, two non-environmental agents. Whereas, in the W.A.I.T. model, what is analogous to β is a pair of parameters α and β, which govern the interaction strengths between hosts and the environment. πS, μ and ν have the same interpretation as in the W.A.I.T. model.

In the case of the W.A.I.T. iteration, the value of R0 takes the form
Equation 2.7: $R_{0}^{WAIT} = \sqrt{\frac{\alpha\beta\pi_{S}}{\mu(\mu + \nu)\pi_{W}}}.$

There are some notable differences in the R0 formulae of the SIR and W.A.I.T. models: the square root in the W.A.I.T. version arises as a consequence of implementing two infected agents (I and Wi) into the model, as opposed to just one in the SIR case. Next, one notices that the β factor in the SIR formula is augmented by the additional factor α in the W.A.I.T. formula, representing a kind of shared dependence between the couplings controlling the I-interaction (α) and the S-interaction (β) with the environment. Analogously, what was the responsibility of πS in the SIR formula now presents itself as a shared dependence, πS/πW, the ratio of the birthrate of susceptible hosts to that of uninfected environmental agents. In this case, the two appear as a ratio under the square root, as opposed to a product in the αβ case, indicating that whereas α and β contribute to R0 in the same way, πS and πW contribute in opposite ways: when πS is increased, R0 increases, but when πW is increased, R0 decreases.

It is possible to view $R_{0}^{WAIT}$ as a geometric mean of two R0 values. Namely, there is the reproductive ratio associated with the number of secondary host infections caused by a single infected environmental agent, and there is the reproductive ratio associated with the number of secondary environmental agent infections caused by a single infected host. We denote the former by $R_{0}^{H}$ and the latter by $R_{0}^{W}$ (H for hosts and W for the W.A.I.T. compartment). From equations (2.1)–(2.5), one can see that the rate of new host infection due to infected environmental agents Wi is given by βSWi/(Wi + Wu). Near the disease-free equilibrium (DFE), S ≈ πS/μ and Wi/(Wi + Wu) ≈ kWi/πW (near the DFE, Wi ≪ Wu), which implies that near the DFE, the rate of new host infection per infected environmental agent is ≈βπSk/(μπW). The average amount of time an infected environmental agent remains infected is 1/k, i.e. the reciprocal of the exit rate of the infected state. Thus, the number of new host infections caused by an infected environmental agent in the time that the agent is infected, and while the system is near the DFE, is given by βπSk/(μπW) × 1/k = βπS/(μπW). That is
Equation 2.8: $R_{0}^{H} = \frac{\beta\pi_{S}}{\mu\pi_{W}}.$

Similarly, the rate of new infection of environmental agents, caused by infected hosts, is given by αIWu/(Wi + Wu). Near the DFE, this rate, per infected host, is ≈α (since Wu/(Wi + Wu) ≈ 1), and the average time that an infected host remains infected is given by 1/(μ + ν), the reciprocal of the exit rate of the infected state. Thus, the number of new environmental agent infections caused by an infected host in the time that the host is infected (near the DFE) is given by
Equation 2.9: $R_{0}^{W} = \frac{\alpha}{\mu + \nu}.$

One can see that the value of R0 given in equation (2.7) is the geometric mean of the two R0 values calculated above:
Equation 2.10: $R_{0}^{WAIT} = \sqrt{\frac{\beta\pi_{S}}{\mu\pi_{W}}} \times \sqrt{\frac{\alpha}{\mu + \nu}} = \sqrt{R_{0}^{H}R_{0}^{W}}.$

From this perspective, one can observe how a characteristic feature of the epidemic is modified by indirect transmission.

## 3 The hepatitis C virus model

### 3.1 Description

Our HCV model represents an adaptation of the SIR W.A.I.T. model outlined in §[2](#s2), but engineered around the particulars of HCV. Our model simulates a population of approximately 170 000 individuals—based on estimates of the size of the people who inject drugs (PWID) community in New York City [45]—where infected injection drug users may migrate into the population. In this model, injection paraphernalia serve as the environmental reservoir for HCV and the sharing of this equipment will constitute the means of transmitting new infections. While the entirety of injection paraphernalia might contain other components, many parameters in this model are based on the use of needle and syringe as the instrument of injection and sharing. Consequently, we use the term ‘needle’ in this paper as a synecdoche for the entire injection apparatus. It is also important to note that HCV can be transmitted sexually [46], but in this study we restrict our attention to transmission through infected needles. This main text focuses on the main structure and dynamical properties of the model. Further model details and discussion can be found in the electronic supplementary material, appendix.

### 3.2 HCV W.A.I.T. model: compartmental diagram

We model the dynamics of needle populations and injection drug users through a series of five ordinary differential equations. The compartments labelled S, IE, IL, Nu and Ni represent the populations of susceptible individuals, early-stage infected individuals (acute HCV infection), late-stage-infected individuals (chronic HCV infection), uninfected needles and infected needles, respectively (figure 2). Here, we refer to all needles in circulation within the entire PWID community. This model is defined by several features:

![Figure 2](https://trs.silverchair-cdn.com/trs/content_public/journal/rsif/16/158/10.1098_rsif.2019.0334/6/rsif20190334f02.png?Expires=1782305913&Signature=c5DL0nbBjtoCDB2HJ3T~VpJRpRwSTjouWnFYnyf~JRCFooZugqWq-0IGf5dZtjicnDPhWsQ6rGqIVKhLUfdXgqo8osxMqOv1kshBberKheITGs4nHmLnBk3u8BWPEOAPTZqtlu3rGCDZDEDMe2kgisuUT8IGi7wezaZQkkevv09vmU4C4VnCSfzuixDnS5UqhtwMbmHOIeu4-7CPUsvUcXsiewuKMTupKW35kacmXI8vaJQYCYI8vt0TG7SUHa3ouaYSuBrnLcS-EFEN3CApupvEDZefaPWgIIuvnkbwUZZtsKwU-M0UUEcyGCECEbok4sJgBQfFwb5dsuJRcmZtww__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 2.** HCV compartmental diagram. Red arrows highlight flow of disease through the system, and where there is a colour/transparency gradient there is a flow of infection away from an infected compartment towards an uninfected one. (Online version in colour.)

- The susceptible compartment refers to individuals who are injecting drugs and who are sharing needles with other members in the PWID community.
- The needle population is divided into two compartments: infected and uninfected, and we model the dynamics of each compartment separately. This is analogous to the Wi and Wu terms discussed in the preliminary model.
- New infections (of both hosts and needles) will depend on the fraction of infected or uninfected needles in circulation.
- Newly infected individuals enter the early stage compartment IE first before either spontaneously clearing the infection or moving into the late-stage compartment IL, from which we assume no spontaneous clearance occurs—individuals may leave IL either by treatment or death only, since cases of spontaneously clearing chronic HCV are rare.
- There are various estimates for the ability of HCV to survive in needles [47,48]. We incorporate HCV free-living survival via the parameter ε, which quantifies the rate at which the virus decays on infected needles.

### 3.3 HCV W.A.I.T. model: analytic equations and parameters

The dynamics of the HCV transmission process are governed by equations (3.1)–(3.5). The population of individuals that are being treated and those who have recovered are not explicitly modelled in this iteration, as the dynamics of treatment and recovery are not central to the questions explored in this study. There are, however, several modelling studies of HCV that focus on treatment [26–28,49], and their effects are not ignored in the HCV W.A.I.T. model.

Entering treatment (and re-entering the susceptible population, as in case of drug relapse in the PWID population) are incorporated via removal terms −τIL and −τIE and the susceptible ‘birth’ term πS.
Equation 3.1: $\frac{dS}{dt} = \pi_{S} + \phi I_{E} - \beta S\frac{N_{i}}{N_{i} + N_{u}} - \mu S,$
Equation 3.2: $\frac{dI_{E}}{dt} = \beta S\frac{N_{i}}{N_{i} + N_{u}} - (\omega + \tau + \mu + \phi)I_{E},$
Equation 3.3: $\frac{dI_{L}}{dt} = \omega I_{E} - (\mu + \tau)I_{L},$
Equation 3.4: $\frac{dN_{u}}{dt} = \pi_{N} - \alpha(I_{E} + I_{L})\frac{N_{u}}{N_{i} + N_{u}} - k_{u}N_{u} + \epsilon N_{i}$
Equation 3.5: ${and}\qquad\frac{dN_{i}}{dt} = \alpha(I_{E} + I_{L})\frac{N_{u}}{N_{i} + N_{u}} - k_{i}N_{i} - \epsilon N_{i},\qquad\,$
where πS is the birthrate of new members into the PWID community either via migration, first-time use or recovery from treatment—not from spontaneous self-clearance. ϕ represents the daily fractional rate that acutely infected individuals (or early infectedIE) spontaneously clear the infection—i.e. without treatment. α represents the per capita injection rate, scaled by the fraction of injection events by infected users that render a needle infectious. β represents the per capita injection rate, scaled by the fraction of injection events with an infected needle that leave a susceptible host infectious. μ is the combined fractional death and PWID cessation rate (individuals who leave the PWID community). ω is the daily fractional rate that early stage infected individuals progress to the late stage of infection. τ is the daily fractional rate that infected individuals go into treatment. πN is the rate of introduction of uninfected needles into the PWID population. ku is the daily fractional discard rate of uninfected needles. ki is the daily fractional discard rate of infected needles. Lastly, $\epsilon$ is the daily fractional rate that infected needles clear the infection due to de-activation (or ‘death’) of virus populations on the needle. Parameter values and sources can be seen in table 1.

Table 1: HCV model parameters.

| label | value | units | description | sources |
|---|---|---|---|---|
| πS | 47 ± 10 | person/day | birthrate of susceptibles (chosen to keep πN/μ ≈ 170 000) | estimate |
| ϕ | (4.7 ± 0.5) × 10−3 | %/day | daily fractional self-clearance rate | [26,50] |
| α | 4 ± 3 | $\frac{injections}{{person} \cdot {day}}$ | injection rate times infection of needle probability | [51] |
| β | 0.072 ± 0.05 | $\frac{injections}{{person} \cdot {day}}$ | injection rate times infection of host rate | [52] |
| μ | (2.7 ± 0.5) × 10−4 | %/day | fractional rate of removal from PWID community due to cessation and death | [53] |
| ω | 0.006 ± 0.005 | %/day | fractional transfer rate into late-stage infection | [54,55] |
| τ | 0.011 ± 0.005 | %/day | fractional rate of entering treatment | [56,57] |
| πN | (3.14 ± 0.01) × 104 | needles/day | birthrate of uninfected needles (chosen to keep πN/ku ≈ 220 000) | [58,59] |
| ku | 0.143 ± 0.005 | %/day | fractional discard rate of uninfected needles | estimate |
| ki | 0.143 ± 0.005 | %/day | fractional discard rate of infected needles | estimate |
| ɛ | 1.17 ± 0.05 | %/day | fractional decay rate of HCV infection in needles | [48] |

### 3.4 HCV W.A.I.T. model parameters influence R0

Having constructed and elaborated on the details of the HCV W.A.I.T. model, we now explore how parameters related to the environmental reservoir (in this case, those framing the population of infected needles) influence R0. We directly measured the influence of parameters on R0 by considering the partial rank correlation coefficient (PRCC), discussed below. The value of R0 was calculated using established methods [43,44] and is outlined in the electronic supplementary material, appendix:
Equation 3.6: $R_{0} = \sqrt{\frac{\alpha\beta k_{u}\pi_{S}(\mu + \tau + \omega)}{\pi_{N}\mu(\epsilon + k_{i})(\mu + \tau)(\mu + \tau + \phi + \omega)}}.$

We emphasize that in a manner analogous to our example discussed in §[2](#s2), we can regard our R0 value as a geometric mean of two other R0 values:
Equation 3.7: $R_{0} = \sqrt{\frac{\alpha(\mu + \tau + \omega)}{(\mu + \tau)(\mu + \tau + \phi + \omega)}} \times \sqrt{\frac{\beta k_{u}\pi_{S}}{\mu(\epsilon + k_{i})\pi_{N}}}.$

The left-most factor (under the square root) can be interpreted as the number of secondary infections of needles in the average time that a host is infected (near the DFE), and the right-most factor can be regarded as the number of secondary infections of hosts in the average time that a needle remains infected. Further discussion of this result can be found in the electronic supplementary material, appendix. As with traditional values of R0, we find that our value is consistent with the statement that sign(R0 − 1) = sign(λ), where λ is the maximal eigenvalue of the Jacobian of the infected subsystem—composed of the infected compartments of the ODE system: IE, IL and Ni—calculated at the DFE (all eigenvalues of the Jacobian were real-valued). This shows that the DFE is unstable when R0 > 1.

We determine the sensitivities of our parameters on the value of R0 by calculating the PRCC with respect to equation (3.6)—we base our calculation of PRCC on methods used in prior studies [60]. We find that parameters related to an interaction with the environmental reservoir (the population of needles) such as α and β, the couplings between hosts and needles, are at least as central to HCV dynamics as parameters traditionally associated with an epidemic, such as πS, the birthrate of susceptibles, μ, the combined death and cessation rate of PWID, and τ, the rate of progressing to treatment (figure 3). This fortifies the notion that W.A.I.T.-specific properties dictate the spread of HCV, providing opportunities to explore more precise targeting by public health interventions.

![Figure 3](https://trs.silverchair-cdn.com/trs/content_public/journal/rsif/16/158/10.1098_rsif.2019.0334/6/rsif20190334f03.png?Expires=1782305913&Signature=zVAO5ghhFgv6wz3xRlfDx1k0W4gZi62xjRgW7-Vtu6flxCVSBAOH6tQcJ3JMAqk0PU96eTGbBIxrHoMzH8K2RZLszKuc0vA~0LTn5uw-JkxsFpa1xySLs2hR6czz24Ui1gOrjVyN5yfBG3McoWhIRrYisFXK4dOdDP-mgy2uix6ntQCyBPoAPtbnoGRcNbt2c8hv4MmExsQPkq4SNOXFIOV3LrcPWYeQ9ZLRfLvEZD952JuYVDnhRJXQGjmdz~H-PKEx0PO99-VDGL~cv5pvQD6rm5QkZFvK4nkCEagc~Br--9e~87R7u9gG4jQ64GnRDgGYioqSWmS7PD-fguUQSA__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 3.** R0 sensitivity in HCV: the partial rank correlation coefficient (PRCC). A PRCC calculation was performed for R0 using Latin hypercube sampling. Parameters were sampled from uniform distributions with widths specified by the ranges given in table 1. The PRCC calculation was repeated for 50 independent iterations. The averages of these iterations are shown here, with the standard deviations for each parameter shown as the error bars. (Online version in colour.)

### 3.5 HCV W.A.I.T. model and simulated interventions: needle exchange programmes

Having demonstrated the relevance of injection drug equipment in terms of how it influences the basic reproductive number, we can consider the utility of the model with respect to other properties, including how it offers insight into potential interventions.

In figure 4b, we demonstrate how changing ku and ki modifies the value of R0. Notice that R0 is reduced by increasing ki across fixed values of ku, and the opposite effect—increasing R0—is observed when increasing ku along fixed values of ki. That is, removing infected needles at an increased rate may decrease infection risk in a population of PWID, while removing uninfected needles can increase the risk. One can also see that increasing ku and ki simultaneously, along the dashed line—where ku = ki—will increase R0. This suggests that if a distinction between infected and uninfected needles cannot be established (as is often the case) then discarding needles indiscriminately can potentially exacerbate the spread of the infection.

![Figure 4](https://trs.silverchair-cdn.com/trs/content_public/journal/rsif/16/158/10.1098_rsif.2019.0334/6/rsif20190334f04.png?Expires=1782305913&Signature=C9Aij9LjD7Il4ytR6OU4NU5zuuUi88-H66MKqvvAnVFoqGBAwGad1NWAchzkmdrhRqTSwydkemWE0ZGOi7uGJmWHaaHIzm86bXkKpP476-YXwO5rgmPTfTsMyuNSFzcmhLUzBK-Wp442V0DMSlWS~wYLeI6ggfO5eJ9UFZrB8EEi6UfT3pKHBYdH2o7804o6BaSQRoE0e1q60BvXjH9SMIFagrI3rIQOqe-M-35r9Qypa7B2IdXHneletzMMUnPvz7NgnJfNHv4DWnbIYmWk1671HEe~xSGhJv01nCYDZsJsWf2mcJoz02YB28zfN-hILxnhjSPiQX8tpQyGmSDxYg__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 4.** HCV R0 as a function of various model features. (a) The relationship between the rate of acquisition of clean needles πN and the discard rate of infected needles ki with respect to various values of R0. The curves are contours of R0 and are labelled by the associated R0 value. The vertical and horizontal dashed lines indicate the chosen values for their respective parameters (we fix ku to the value specified in table 1). (b) The relationship between the infected and uninfected needle discard rate, with respect to R0. The diagonal line represents where ku = ki. The ‘x’ indicates the value chosen for ku and ki in the model (we set ku = ki in the model). Notice that moving upwards along this diagonal increases R0. (Online version in colour.)

This is a result of the fact that when k:= ku = ki, the expression for R0 is proportional to
Equation 3.8: $\sqrt{\frac{k}{\epsilon + k}}\,.$

We highlight this to show the explicit dependence on k in the R0 expression. Notice that this factor is monotonically increasing in k, indicating that no matter the values of other parameters in the model, as long as they are all positive, R0 will necessarily increase with k. Notice also that when $\epsilon$ = 0, the k dependence cancels out entirely. This indicates that when $\epsilon$ = 0, meaning that there is no flow of infected needles back to the uninfected compartment, then R0 is not modified by the discard rate of needles. We point the reader to the electronic supplementary material, appendix, for a more thorough discussion of this point.

Next, we considered how certain interventions can modify the transfer rate of needles from infected to uninfected states, through modifying the $\epsilon$ parameter in our study (figure 5). A high $\epsilon$ value would indicate a scenario where needles move quickly from an infected state to an uninfected state. This would apply to settings where viral decay on a needle is high, or when infected needles are directly exchanged for uninfected ones (as in certain needle exchange programmes). The model is run with all uninfected populations initialized at their DFE values (S = 170 000 and Nu = 220 000), and we initialize IE = Nu = 1, and IL = 0. In the high $\epsilon$ scenario, we observe generally slower dynamics and higher overall susceptible population sizes, along with lower infected populations (on long time scales).

![Figure 5](https://trs.silverchair-cdn.com/trs/content_public/journal/rsif/16/158/10.1098_rsif.2019.0334/6/rsif20190334f05.png?Expires=1782305913&Signature=qTAKwklFtVWQMI4Jv9HV~Vn99SmKu2Rcg7BBnGFV-l4shRX6TXaKqn5hY7~ru38wSiJp9nXCOuaQGaRz-BN5eIzvgFpN1gzNBM0TwhwVMDC73UX2Lge1~Evy3cE8kvq9Lm7jgtVL23sV4bm-tcnjHS-rkcLLCP5QWuJxDYFnX~4n2ljKkgXmcqAueqQJg6dtna9uLvlLy33tAMetMxKny1k4txN4KDC4JKGW56iGAUBqCnmRaSjRYd3TOyp5MzzAdspnyJWGiYJSVQhhHM5fHaqDYbdUZH1Ik85qKZJWZP2uhlldueM0f3vJ8lnI~qVxQlBEgBA5N1v-Q7shCrZvHg__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 5.** The dynamics of susceptible (blue), early-infected (orange) and late-infected (green) populations in two parameter regimes: high and low $\epsilon$, the conversion rate of needles from infected to uninfected. The solid lines represent the dynamics for $\epsilon = 2\,{day}^{- 1}$ (high $\epsilon$), and dashed lines are the dynamics for $\epsilon = 0.33\, d^{- 1}$ (low $\epsilon$). In the high- $\epsilon$ regime, we find that the susceptible population at equilibrium is ≈4 times that of the low-ε regime, and the infected populations are each $\approx \mkern180mu 89\text{\%}$ of their low- $\epsilon$ counterparts at equilibrium (note the log scale on the y-axis). (Online version in colour.)

## 4 Discussion

While diseases transmitted through injection drug use have been the object of prior modelling efforts, none have specifically investigated how injection equipment plays a role in the dynamics of HCV. Prior models of injection equipment have focused on HIV [24,25], and/or been so complicated that their structure is not easily translated to any other settings [23]. In this study, we model HCV as an indirectly transmitted infection, where the injection equipment is modelled as the environmental reservoir, just as a water source might be modelled in a waterborne infection [8,19]. We label our approach as the W.A.I.T. model, one that incorporates features of other approaches to studying environmentally transmitted pathogens [6,11], but grounding them in a flexible model that can be neatly applied to HCV. Our approach offers several specific insights. For example, we demonstrate that the composite R0 that defines the entire dynamical system is the geometric mean of R0 values used to describe each of two sub-components: disease flow through the hosts and flow through the injection equipment (equation (3.7)). This observation offers a practical suggestion for studying diseases like HCV: epidemiologists and modellers must understand, through empirical studies, properties of all major actors in the system (hosts and environmental injection drug equipment in the case of HCV).

The mathematical model of HCV presented in this paper (described as a W.A.I.T. model; see §§[2](#s2) and [3](#s3)) also offers nuanced findings about the dynamics of disease. Firstly, our model highlights the differing roles of uninfected and infected injection on disease dynamics. Specifically, the model speaks to the potential utility of harm reduction policies: indiscriminately removing injection equipment from a system—without an overall shift in needle populations from infected to uninfected—might increase the rate of infection. In order to attenuate an epidemic, intervention strategies should focus on steering the population of needles towards being more uninfected. Therefore, ideal intervention efforts should aim to decrease sharing events on an infected needle. This helps to explain why programmes like safe injection might be effective [61]: they do not change the number of infected needles in the system directly, but can alter the sharing rate, and consequently, the probability of sharing an infected needle.

Finally, understanding the dynamical properties of disease transmitted through injection drug use is now especially relevant as a result of the modern opioid epidemic. This epidemic is typified by recreational use of prescription and illicit opioids, with injection drug use being a major route through which drugs are consumed [42]. The relevance of viral diseases among opioid users gained national attention during a 2015 outbreak of HIV in rural Indiana that was driven by an injected opioid called oxymorphone [62,63]. This outbreak raised alarms in the public health community, and officials are increasingly aware of the potential for future outbreaks. However, it was not until relatively recently that the role of the opioid crisis in HCV transmission has been examined [64,65]. We propose, in closing, that modelling approaches (in general, and not relegated to the methods proposed in this study) are crucial for understanding, attenuating or preventing explosive outbreaks of HCV in an age when a new opioid epidemic has emerged.

## Data accessibility

Code for the mathematical models presented in this paper are available on GitHub (https://github.com/ogplexus/WAIT).

## Authors' contributions

All authors contributed to the development of the model, study design, analysis and interpretation of results. C.B.O. conceived the study, and created the original iteration of the model. M.D.M.D. and V.A.M. wrote the code, ran simulations, performed calculations and developed visualizations. All authors contributed to the writing and editing of the manuscript.

## Competing interests

We declare we have no competing interests.

## Funding

This work was supported by Brown University.

## Acknowledgements

The authors thank B. Linas, J. Andrews, I. Diakite, S. Robinson, S. Scarpino, N. Harris, B. Marshall and E. Hinton for various contributions on the topic. The authors would also like to thank three reviewers for very helpful comments on a manuscript draft.

## References (65 total, showing 65)

1. Dick EC , Jennings LC , Mink KA , Wartgow CD , Inborn SL . 1987 Aerosol transmission of rhinovirus colds . J. Infect. Dis. , 156 , 442 - 448 . ( doi:10.1093/infdis/156.3.442 )
2. Abad FX , Pinto RM , Bosch A . 1994 Survival of enteric viruses on environmental fomites . Appl. Environ. Microbiol. , 60 , 3704 - 3710 .
3. Codeço CT . 2001 Endemic and epidemic dynamics of cholera: the role of the aquatic reservoir . BMC Infect. Dis. , 1 , 1 . ( doi:10.1186/1471-2334-1-1 )
4. Boone SA , Gerba CP . 2007 Significance of fomites in the spread of respiratory and enteric viral disease . Appl. Environ. Microbiol. , 73 , 1687 - 1696 . ( doi:10.1128/AEM.02051-06 )
5. Weber TP , Stilianakis NI . 2008 Inactivation of influenza a viruses in the environment and modes of transmission: a critical review . J. Infect. , 57 , 361 - 373 . ( doi:10.1016/j.jinf.2008.08.013 )
6. Li S , Eisenberg JNS , Spicknall IH , Koopman JS . 2009 Dynamics and control of infections transmitted from person to person through the environment . Am. J. Epidemiol. , 170 , 257 - 265 . ( doi:10.1093/aje/kwp116 )
7. Tellier R . 2009 Aerosol transmission of influenza a virus: a review of new studies . J. R. Soc. Interface , 6 , S783 - S790 . ( doi:10.1098/rsif.2009.0302.focus )
8. Tien JH , Earn DJD . 2010 Multiple transmission pathways and disease dynamics in a waterborne pathogen model . Bull. Math. Biol. , 72 , 1506 - 1533 . ( doi:10.1007/s11538-010-9507-6 )
9. Bani-Yaghoub M , Gautam R , Shuai Z , Van Den Driessche P , Ivanek R . 2012 Reproduction numbers for infections with free-living pathogens growing in the environment . J. Biol. Dyn. , 6 , 923 - 940 . ( doi:10.1080/17513758.2012.693206 )
10. Zhao J , Eisenberg JE , Spicknall IH , Li S , Koopman JS . 2012 Model analysis of fomite mediated influenza transmission . PLoS ONE , 7 , e51984 . ( doi:10.1371/journal.pone.0051984 )
11. Breban R . 2013 Role of environmental persistence in pathogen transmission: a mathematical modeling approach . J. Math. Biol. , 66 , 535 - 546 . ( doi:10.1007/s00285-012-0520-2 )
12. Cortez MH , Weitz JS . 2013 Distinguishing between indirect and direct modes of transmission using epidemiological time series . Am. Nat. , 181 , E43 - E52 . ( doi:10.1086/668826 )
13. Van Doremalen N , Bushmaker T , Munster VJ . 2013 Stability of Middle East respiratory syndrome coronavirus (MERS-COV) under different environmental conditions . Eurosurveillance , 18 , 20590 . ( doi:10.2807/1560-7917.ES2013.18.38.20590 )
14. Li M , Ma J , van den Driessche P . 2015 Model for disease dynamics of a waterborne pathogen on a random network . J. Math. Biol. , 71 , 961 - 977 . ( doi:10.1007/s00285-014-0839-y )
15. Caraco T , Cizauskas CA , Wang N . 2016 Environmentally transmitted parasites: host-jumping in a heterogeneous environment . J. Theor. Biol. , 397 , 33 - 42 . ( doi:10.1016/j.jtbi.2016.02.025 )
16. Brouwer AF , Eisenberg MC , Remais JV , Collender PA , Meza R , Eisenberg JNS . 2017 Modeling biphasic environmental decay of pathogens and implications for risk analysis . Environ. Sci. Technol. , 51 , 2186 - 2196 . ( doi:10.1021/acs.est.6b04030 )
17. Brouwer AF , Weir MH , Eisenberg MC , Meza R , Eisenberg JNS . 2017 Dose-response relationships for environmentally mediated infectious disease transmission models . PLoS Comput. Biol. , 13 , e1005481 . ( doi:10.1371/journal.pcbi.1005481 )
18. Webster JP , Borlase A , Rudge JW . 2017 Who acquires infection from whom and how? Disentangling multi-host and multi-mode transmission dynamics in the ‘elimination’ era . Phil. Trans. R. Soc. B , 372 , 20160091 . ( doi:10.1098/rstb.2016.0091 )
19. Walther BA , Ewald PW . 2004 Pathogen survival in the external environment and the evolution of virulence . Biol. Rev. , 79 , 849 - 869 . ( doi:10.1017/S1464793104006475 )
20. Kaplan EH . 1990 Modeling HIV infectivity: must sex acts be counted? . J. Acquir. Immune Defic. Syndr. , 3 , 55 - 61 .
21. Phillips AN . 1996 Reduction of concentration during acute infection: independence from a specific immune response . Science , 271 , 497 - 499 . ( doi:10.1126/science.271.5248.497 )
22. Kaplan EH . 1989 Needles that kill: modeling human immunodeficiency virus transmission via shared drug injection equipment in shooting galleries . Rev. Infect. Dis. , 11 , 289 - 298 . ( doi:10.1093/clinids/11.2.289 )
23. Homer JB , St.-Clair CL . 1991 A model of HIV transmission through needle sharing . Interfaces , 21 , 26 - 49 . ( doi:10.1287/inte.21.3.26 )
24. Kaplan EH , Heimer R . 1992 A model-based estimate of HIV infectivity via needle sharing . J. Acquir. Immune Defic. Syndr. , 5 , 1116 - 1118 .
25. Kaplan EH , O’Keefe E . 1993 Let the needles do the talking! Evaluating the New Haven needle exchange . Interfaces , 23 , 7 - 26 . ( doi:10.1287/inte.23.1.7 )
26. Vickerman P , Martin N , Turner K , Hickman M . 2012 Can needle and syringe programmes and opiate substitution therapy achieve substantial reductions in hepatitis C virus prevalence? model projections for different epidemic settings . Addiction , 107 , 1984 - 1995 . ( doi:10.1111/add.2012.107.issue-11 )
27. Martin NK et al. 2013 Hepatitis C virus treatment for prevention among people who inject drugs: modeling treatment scale-up in the age of direct-acting antivirals . Hepatology , 58 , 1598 - 1609 . ( doi:10.1002/hep.26431 )
28. Fraser H et al. 2018 Model projections on the impact of HCV treatment in the prevention of HCV transmission among people who inject drugs in Europe . J. Hepatol. , 68 , 402 - 411 . ( doi:10.1016/j.jhep.2017.10.010 )
29. Rolls DA , Daraganova G , Sacks-Davis R , Hellard M , Jenkinson R , McBryde E , Pattison PE , Robins GL . 2012 Modelling hepatitis C transmission over a social network of injecting drug users . J. Theor. Biol. , 297 , 73 - 87 . ( doi:10.1016/j.jtbi.2011.12.008 )
30. Pitcher AB , Borquez A , Skaathun B , Martin NK . In press. Mathematical modeling of hepatitis C virus (HCV) prevention among people who inject drugs: a review of the literature and insights for elimination strategies . J. Theor. Biol . ( doi:10.1016/j.jtbi.2018.11.013 )
31. Cousien A , Tran VC , Deuffic-Burban S , Jauffret-Roustide M , Dhersin JS , Yazdanpanah Y . 2015 Dynamic modelling of hepatitis C virus transmission among people who inject drugs: a methodological review . J. Viral Hepat. , 22 , 213 - 229 . ( doi:10.1111/jvh.2015.22.issue-3 )
32. Esposito N , Rossi C . 2004 A nested-epidemic model for the spread of hepatitis C among injecting drug users . Math. Biosci. , 188 , 29 - 45 . ( doi:10.1016/j.mbs.2003.11.001 )
33. Corson S , Greenhalgh D , Hutchinson SJ . 2013 A time since onset of injection model for hepatitis C spread amongst injecting drug users . J. Math. Biol. , 66 , 935 - 978 . ( doi:10.1007/s00285-012-0577-y )
34. Corson S , Greenhalgh D , Hutchinson S . 2012 Mathematically modelling the spread of hepatitis C in injecting drug users . Math. Med. Biol. , 29 , 205 - 230 . ( doi:10.1093/imammb/dqr011 )
35. Echevarria D , Gutfraind A , Boodram B , Major M , Del Valle S , Cotler SJ , Dahari H . 2015 Mathematical modeling of hepatitis C prevalence reduction with antiviral treatment scale-up in persons who inject drugs in metropolitan Chicago . PLoS ONE , 10 , e0135901 . ( doi:10.1371/journal.pone.0135901 )
36. Massad E , Coutinho FA , Yang HM , De Carvalho HB , Mesquita F , Burattini MN . 1994 The basic reproduction ratio of among intravenous drug users . Math. Biosci. , 123 , 227 - 247 . ( doi:10.1016/0025-5564(94)90013-2 )
37. Mandal S , Sarkar RR , Sinha S . 2011 Mathematical models of malaria—a review . Malar. J. , 10 , 202 . ( doi:10.1186/1475-2875-10-202 )
38. Almagro-Moreno S , Taylor RK . 2013 Cholera: environmental reservoirs and impact on disease transmission . Microbiol. Spectr. , 1 , 1 - 19 . ( doi:10.1128/microbiolspec.OH-0003-2012 )
39. National Research Council et al. 1995 Preventing transmission: the role of sterile needles and bleach . Washington, DC: National Academies Press .
40. Van Den Berg C , Smit C , Van Brussel G , Coutinho R , Prins M . 2007 Full participation in harm reduction programmes is associated with decreased risk for human immunodeficiency virus and hepatitis C virus: evidence from the Amsterdam cohort studies among drug users . Addiction , 102 , 1454 - 1462 . ( doi:10.1111/add.2007.102.issue-9 )
41. Lankenau SE , Teti M , Silva K , Bloom JJ , Harocopos A , Treese M . 2012 Initiation into prescription opioid misuse amongst young injection drug users . Int. J. Drug Policy , 23 , 37 - 44 . ( doi:10.1016/j.drugpo.2011.05.014 )
42. Marshall BDL , Krieger MS , Yedinak JL , Ogera P , Banerjee P , Alexander-Scott NE , Rich JD , Green TC . 2017 Epidemiology of fentanyl-involved drug overdose deaths: a geospatial retrospective study in Rhode Island, USA . Int. J. Drug Policy , 46 , 130 - 135 . ( doi:10.1016/j.drugpo.2017.05.029 )
43. Jones JH . 2007 Notes on R 0 . Stanford, CA: Department of Anthropological Sciences, Stanford University .
44. Diekmann O , Heesterbeek JAP , Roberts MG . 2010 The construction of next-generation matrices for compartmental epidemic models . J. R. Soc. Interface , 7 , 873 - 885 . ( doi:10.1098/rsif.2009.0386 )
45. Des Jarlais DC et al. 1998 Declining seroprevalence in a very large epidemic: injecting drug users in New York City, 1991 to 1996 . Am. J. Public Health , 88 , 1801 - 1806 . ( doi:10.2105/AJPH.88.12.1801 )
46. Terrault NA et al. 2013 Sexual transmission of hepatitis C virus among monogamous heterosexual couples: the HCV partners study . Hepatology , 57 , 881 - 889 . ( doi:10.1002/hep.26164 )
47. Canadian Paediatric Society . 2008 Needle stick injuries in the community . Paediatr. Child Health , 13 , 205 - 210 .
48. Paintsil E , He H , Peters C , Lindenbach BD , Heimer R . 2010 Survival of hepatitis C virus in syringes: implication for transmission among injection drug users . J. Infect. Dis. , 202 , 984 - 990 . ( doi:10.1086/653019 )
49. Martin NK , Pitcher AB , Vickerman P , Vassall A , Hickman M . 2011 Optimal control of hepatitis C antiviral treatment programme delivery for prevention amongst a population of injecting drug users . PLoS ONE , 6 , e22309 . ( doi:10.1371/journal.pone.0022309 )
50. Micallef JM , Kaldor JM , Dore GJ . 2006 Spontaneous viral clearance following acute hepatitis C infection: a systematic review of longitudinal studies . J. Viral Hepat. , 13 , 34 - 41 . ( doi:10.1111/jvh.2006.13.issue-1 )
51. Short LJ , Bell DM . 1993 Risk of occupational infection with blood borne pathogens in operating and delivery room settings . Am. J. Infect. Control , 21 , 343 - 50 . ( doi:10.1016/0196-6553(93)90400-X )
52. Centers for Disease Control and Prevention (CDC) . 1997 Recommendations for follow-up of health-care workers after occupational exposure to hepatitis C virus . MMWR Morb. Mortal Wkly. Rep. , 46 , 603 - 606 .
53. Hickman M , Hope V , Brady T , Madden P , Jones S , Honor S , Holloway G , Ncube F , Parry J . 2007 Hepatitis C virus (HCV) prevalence, and injecting risk behaviour in multiple sites in England in 2004 . J. Viral Hepat. , 14 , 645 - 652 . ( doi:10.1111/jvh.2007.14.issue-9 )
54. Poynard T , Bedossa P , Opolon P . 1997 Natural history of liver fibrosis progression in patients with chronic hepatitis C . Lancet , 349 , 825 - 32 . ( doi:10.1016/S0140-6736(96)07642-8 )
55. Khan A , Sial S , Imran M . 2014 Transmission dynamics of hepatitis C with control strategies . J. Comput. Med. , 2014 , 18 . ( doi:10.1155/2014/654050 )
56. Grebely J , Conway B , Raffa J , Lai C , Krajden M , Tyndall M . 2006 Uptake of hepatitis C virus (HCV) treatment among injection drug users (IDUS) in Vancouver, Canada . J. Hepatol. , 44 , 214 - 215 . ( doi:10.1016/S0168-8278(06)80578-7 )
57. Seal KH , Kral A , Lorvick J , Gee L , Tsui J , Edlin B . 2005 Among injection drug users, interest is high, but access low to HCV antiviral therapy . J. Gen. Intern. Med. , 20 , 171 .
58. Gold K . 2011 Analysis: the impact of needle, syringe, and lancet disposal on the community . J. Diabetes Sci. Technol. , 5 , 848 - 850 . ( doi:10.1177/193229681100500404 )
59. Heller DI , Paone D , Siegler A , Karpati A . 2009 The syringe gap: an assessment of sterile syringe need and acquisition among syringe exchange program participants in New York City . Harm Reduct. J. , 6 , 1 . ( doi:10.1186/1477-7517-6-1 )
60. Blower SM , Dowlatabadi H . 1994 Sensitivity and uncertainty analysis of complex models of disease transmission: an model, as an example . Int. Stat. Rev. , 62 , 229 - 243 . ( doi:10.2307/1403510 )
61. Rhodes T , Kimber J , Small W , Fitzgerald J , Kerr T , Hickman M , Holloway G . 2006 Public injecting and the need for ‘safer environment interventions’ in the reduction of drug-related harm . Addiction , 101 , 1384 - 1393 . ( doi:10.1111/add.2006.101.issue-10 )
62. Conrad C et al. 2015 Community outbreak of HIV infection linked to injection drug use of oxymorphone—Indiana, 2015 . MMWR Morb. Mortal. Wkly. Rep. , 64 , 443 .
63. Peters PJ et al. 2016 infection linked to injection use of oxymorphone in Indiana, 2014–2015 . N. Engl. J. Med. , 375 , 229 - 239 . ( doi:10.1056/NEJMoa1515195 )
64. Zibbell JE et al. 2015 Increases in hepatitis C virus infection related to injection drug use among persons aged ≤30 years—Kentucky, Tennessee, Virginia, and West Virginia, 2006–2012 . MMWR Morb. Mortal. Wkly. Rep. , 64 , 453 . ( doi:10.15585/mmwr.mm6503a2 )
65. Powell D , Alpert A , Pacula RL . 2019 A transitioning epidemic: how the opioid crisis is driving the rise in hepatitis C . Health Aff. , 38 , 287 - 294 . ( doi:10.1377/hlthaff.2018.05232 )
