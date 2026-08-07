---
title: "An algorithmic multiple attribute decision-making context to model uncertainty associated with hospital site selection problem using complex sv-neutrosophic soft information"
authors: "Khuram Ali Khan, Ali Asghar, Atiqe Ur Rahman, Rostin Matendo Mabela"
doi: "10.1080/08839514.2024.2375110"
source: "tandf_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 20453
---

# An algorithmic multiple attribute decision-making context to model uncertainty associated with hospital site selection problem using complex sv-neutrosophic soft information

## ABSTRACT

Decision-making approaches are often used in uncertain environments by people who must make difficult judgments in daily life, including elements of varied qualities and costs. These methods assist decision-makers in managing ambiguity and uncertainty, allowing for more informed and risk-reduced decisions. This research introduces an advanced framework called a complex single-valued neutrosophic soft set (csvNSS) to address uncertainties inherent in decision-making. The csvNSS framework is capable of managing information periodicity by introducing two components: amplitude and phase. The first deals with fuzzy membership, while the second manages periodicity within a complex plane. Some rudiments of csvNSS like properties, set operations and aggregations, are investigated. To make these ideas practically applicable in choosing an appropriate location for the hospital, an algorithm for handling csvNSS is proposed. An enhanced strategy is validated through the use of a specific example that takes site selection for hospital into account. The outcome demonstrates the efficacy of the suggested strategy. The method can be used in other domains where selection issues arise.

## Introduction

One of the most significant regulatory considerations that governments and health regulators consider is where to locate hospitals. The goal of health services is to treat every patient fairly, in a proper environment, and with outstanding attention. Selecting the best site for a hospital is crucial for the efficiency, excellence, and fairness of medical care (Şahin, Ocak, and Top 2019). The site of a hospital is determined strategically (Pinar and Antmen 2019). The site that is chosen needs to be resilient and able to solve any issues down the road. Selecting the incorrect site might result in major cost increases along with dissatisfied customers (Chatterjee 2014). The vast majority of people around the globe are still battling the pandemic today. Hospitals around the world are experiencing an atypical need for diseased patients. This outbreak forced nations to construct hospitals, mobile hospitals, or specialized pandemic hospitals in a significant amount of time. Governments are now required, under these uncertain circumstances, to make these investments and choices based on a number of different factors. Therefore, when choosing an appropriate location, a number of factors should be taken into account. Like other hospital ranking issues, this one is dependent on a wide range of factors, including the surrounding area, population size, consumer demand, competitors, laws and regulations, and expenses (Albahri et al. 2019; Ortiz-Barrios et al. 2020; Yucesan and Gul 2020). Because of this, choosing a hospital site can be viewed as a multi-attribute decision-making (MADM) issue with associated uncertainties.

In order to cope with uncertainties associated with information, Zedah (1965) introduced a fuzzy set (FS) which extended the classical set. The classical set theory was the foundational framework for understanding collections of elements without considering uncertainty or vagueness. It did not involve the notion of membership functions. In FS, each element is associated with a membership function that allows for degrees of belongingness. Building upon Zadeh’s work, Atanassov (Atanassov 1986) introduced the concept of intuitionistic fuzzy sets, enriching the field by incorporating both membership and non-membership functions for elements. Taking the theory further, Cuong and Kreinovich (2013) contributed by introducing picture fuzzy sets, a more generalized version of both fuzzy and intuitionistic fuzzy sets. In picture fuzzy sets, elements are characterized by three distinct functions: degree of membership, degree of non-membership, and degree of neutrality. These functions collectively sum up to a value within the closed unit interval, expanding the versatility of the framework. In parallel, Smarandache (2006) extended the concept of neutrosophic sets, which serves as a comprehensive generalization of fuzzy sets and intuitionistic fuzzy sets. Within the neutrosophic set theory, elements are described by three functions: degree of truth membership, degree of false membership, and degree of indeterminacy membership. Notably, the sum of these three functions is not constrained to be within the unit interval, allowing for a broader representation of uncertainty and ambiguity. In the realm of set theories, Wang et al. (2010) introduced the concept of single-valued neutrosophic sets, wherein elements are characterized by three key attributes: the degree of membership, the degree of non-membership, and the degree of indeterminacy. Notably, in single-valued neutrosophic sets, the sum of these three functions is constrained to fall within the interval [0, 3], reflecting the inherent uncertainty in the system. Arshad, Rahman, and Saeed (2023) and Rahman, Arshad, and Saeed (2021) discussed the traditional notions of convexity in refined neutrosophic and refined intuitionistic fuzzy environments. Kandasamy et al. (2020) and Ulucay (2021) investigated the several basic operational properties of refined neutrosophic sets and interval valued refined neutrosophic sets. Molodtsov (Molodtsov 1999) proposed the innovative concept of soft set theory, aimed at addressing uncertainties in parametric representations. This theory represents a generalization of fuzzy set theory, providing a versatile framework for handling imprecise information. Expanding upon Molodtsov’s work (Çagman, Enginoglu, and Citak (2011) introduced the fuzzy soft set theory, a significant extension that finds practical utility in decision-making problems. This theory blends the characteristics of fuzzy sets and soft sets, offering a more comprehensive approach to uncertainty management. Further advancements in this field led to the development of the “intuitionistic fuzzy soft set” theory by Maji, Biswas, and Roy (2001), which extends the principles of intuitionistic fuzzy sets into the soft set framework, enriching the toolbox for handling imprecise information. Vimala et al. (2023) employed an abstract approach to discuss the lattice-based ideals using multi-fuzzy soft sets. Vimala et al. (2023) ranked airlines during the COVID pandemic using the integrated context of q-rung orthopair multi-fuzzy soft set and modified TOPSIS. Cuong (2014) contributed by introducing the theory of picture fuzzy soft sets, expanding upon the principles of both picture fuzzy sets and soft sets. This novel concept provides a broader and more expressive representation for handling uncertainty in various applications. Rahman et al. (2023) modeled parametric uncertainty in a supply chain system using picture fuzzy soft information. Maji (2013) extended the structural framework of soft sets and neutrosophic sets to create neutrosophic soft sets, further enhancing the ability to model and manage imprecision and uncertainty within complex systems. These advancements in set theories have significantly broadened our capacity to handle imprecise and uncertain information, offering valuable tools for decision-making and problem-solving across diverse domains. Ali and Smarandache (2017) characterized complex neutrosophic set by combining the idea of neutrosophic set with complex settings. Al-Sharqi, Ahmad, and Al-Quran (2023) discussed decision mechanism by modeling parametric uncertainty with interval complex neutrosophic soft settings. Ramot et al. (2002) gave the theory of a complex fuzzy set in which each element has a complex-valued membership function instead of a real-valued function. Alkouri and Salleh (2012) extended the concept of an intuitionistic fuzzy set to the complex intuitionistic fuzzy set by setting all functions in a complex plane. After that, they presented an example based on the distance measure of a complex intuitionistic fuzzy set. The theory of complex fuzzy sets and picture fuzzy sets was used by Qu et al. (2022) to develop the theory of complex picture fuzzy sets. The idea of complex fuzzy soft sets was formally introduced by Thirunavukarasu, Suresh, and Ashokkumar (2017) as an extension of fuzzy sets and soft sets to address the shortcomings of existing models. The goal was to create a unified framework that could accommodate uncertain and complex data in a more comprehensive manner. The complex intuitionistic fuzzy soft sets were introduced by Kumar and Bajaj (2014), as an advanced extension of intuitionistic fuzzy sets and soft sets, enriched by the inclusion of complex numbers. This framework aims to handle uncertainty, vagueness, and complex relationships in a more comprehensive manner (Akram et al. 2023; Akram, Wasim, and Al-Kenani 2021; Al-Qudah and Hassan 2018; Mahmood et al. 2022; Mahmood, Rehman, and Ali 2021; Selvachandran and Singh 2018) and Khan et al. (2020) initiated novel hybrid set structures using the ideas of complex fuzzy set and soft set. Asghar et al. (2023) introduced the complex picture fuzzy soft sets as an extension of picture fuzzy sets and soft sets. The scholars like (Broumi et al. 2023; Chakraborty and Saha 2022; Naseem et al. 2023), and (Rasinojehdehi and Valami 2023) made rich efforts regarding modeling uncertainties and indeterminacy in decision-making.

### Research Gap and Motivation

Various erratic and ambiguous elements, such as potential population expansion, shifting healthcare demands, and changing surroundings, contribute to uncertainty and vagueness in hospital site selection problem (HSSP). The decision-making process is further complicated by qualitative considerations including connectivity, regional inclinations, and prospective socioeconomic effects. Because of these uncertainties, reliable analytical techniques are required to handle inaccurate data and offer flexible, adaptive solutions to guarantee the best possible site selection in the face of dynamic and unpredictable circumstances. Several scholars studied HSSP using various analytical frameworks for handling related uncertainties. However, the efforts of researchers like (Al Mohamed, Al Mohamed, and Zino 2023; Alamoodi et al. 2023; Alkan and Kahraman 2022; Boyac and Şişman 2022; Chen, Wan, and Dong 2022) and Serrano-Guerrero et al. (2023) are noteworthy in the context of uncertainty handling in HSSP. After a thorough analysis of the literature, it is determined that they are inadequate and constrained for properly addressing the uncertainties associated with HSSP due to the following issues:

To provide a degree of confirmation or belief in the membership, it occasionally becomes necessary to quantify strong membership function in contrast to the traditional membership function of fuzzy set in certain important circumstances.

It becomes imperative to add another dimension to the membership function that can record information to handle the periodicity of data. This can express distinct qualitative components of the data, such as temporal or spatial features, and aids in differentiating between contextual refinements or uncertainty of various types that are not represented by conventional membership functions.

Membership function representation in three dimensions is helpful because it enables more complex modeling of uncertainty, taking into account situations in which the available data is not just ambiguous but also conflicting or incomplete. The parameterization tool is also important because it may be used for a variety of scenarios where exact data is challenging to get and does not require knowledge of the underlying uncertainties beforehand.

This study aims to introduce the notions of complex single-valued neutrosophic soft set (csvNSS) to address the above issues in a single model. The first two problems are handled by the complex plane settings of csvNSS employing amplitude and phase terms, while the last challenge is handled by the single-valued neutrosophic soft settings of csvNSS. Thus, when compared to the literature previously cited, the proposed model is more reliable and adaptable. By incorporating the concept of single-valued neutrosophic sets within the framework of soft sets, the csvNSS empowers decision-makers with a versatile tool to make more precise and well-informed decisions, bridging the gap in the decision-making process between macro- and micro-level considerations. Because of its unique characteristics, the csvNSS is particularly well-suited for tackling the issues related to ambiguity, indeterminacy, and uncertainty in particular contexts, such as HSSP, even though other generalizations of FS and SS are more significant and frequently utilized in a variety of applications. The salient contributions of the study are outlined as:

The study presents a novel framework, csvNSS, intended to control decision-making uncertainty. This paradigm allows for the more efficient handling of unclear and confusing data by combining complex numbers with single-valued neutrosophic ideas.

Amplitude and phase terms are introduced in the context of the csvNSS framework. The phase term handles periodicity within a complex plane, allowing a more sophisticated depiction of recurring details, and the amplitude term encompasses membership grades, indicating single-valued neutrosophic components.

The paper investigates the fundamental ideas of csvNSS and its set operations. It also explores the properties and results of csvNSS. This theoretical investigation gives the framework a strong mathematical foundation and is crucial to comprehending the practical applications of the framework.

A cognitive approach and methodology are designed for deploying the csvNSS framework.To verify the efficacy of the approach and show its practicality in a real-world setting, the framework is implemented to address the challenge of choosing an appropriate location for a hospital.

The other portions of the work are structured as follows: Section 2 provides an overview of some fundamental terminology in order to bolster the primary findings. The primary methodology of the paper is presented in Section 3. The two subsections 3.1 and 3.2, make up the majority of it. The concepts, operations, and properties of csvNSS are presented in subsection 3.1 with the aid of examples, while the purpose of subsection 3.2 is to offer a decisive support system by proposing an algorithm that helps managers find a suitable site for the construction of a hospital. The study concludes with a summary of its key points in Section 4 and an emphasis on potential future directions.

## Preliminaries

To recall the fundamental concepts and some definitions, let’s introduce some key symbols:

G˜: This symbol represents the initial collection of objects.

K˜: This symbol denotes the set comprising closed-unit intervals within the range [0, 1].

⊎: This symbol refers to the set that includes open unit intervals within the range (0,1).

C G˜: This symbol represents the collection of all subsets of the set G˜.

These definitions are crucial for understanding the core concept.

Definition 2.1.

(Smarandache 2006) For the set G˜, the neutrosophic set ℕ˜ is defined as

$$
\widetilde{\mathbb{N}} = \left\{{\left({\widetilde{\hslash},\langle{\widetilde{Q}}_{\widetilde{P}}(\widetilde{\hslash}),{\widetilde{Q}}_{\widetilde{N}\mathit{e}}(\widetilde{\hslash}),{\widetilde{Q}}_{\widetilde{N}}(\widetilde{\hslash})\rangle} \right):\widetilde{\hslash} \in \widetilde{G}} \right\}
$$

Here, the functions denoted as Q˜ P˜(ℏ˜), Q˜ N˜ e(ℏ˜), and Q˜ N˜(ℏ˜), quantify the degrees of positivity, neutrality, and negativity associated with an element ℏ˜ such that Q˜ P˜, Q˜ N˜ e, Q˜ N˜: G˜→⊎ and the sum of these three functions lie in the interval [0, 3].

Definition 2.2.

(Wang et al. 2010) The single-valued neutrosophic set ℕ˜ over the set G˜, is defined as

$$
\widetilde{\mathbb{N}} = \left\{{\left({\widetilde{\hslash},{\langle{{\widetilde{Q}}_{\widetilde{P}}(\widetilde{\hslash}),{\widetilde{Q}}_{\widetilde{N}\mathit{e}}(\widetilde{\hslash}),{\widetilde{Q}}_{\widetilde{N}}(\widetilde{\hslash})}\rangle}} \right):\widetilde{\hslash} \in \widetilde{G}} \right\}
$$

Here, functions, denoted as Q˜ P˜(ℏ˜), Q˜ N˜ e(ℏ˜), and Q˜ N˜(ℏ˜), quantify the degrees of positivity, neutrality, and negativity associated with an element ℏ˜ such that Q˜ P˜, Q˜ N˜ e, Q˜ N˜: G˜→ I˜[0, 1] with 0≤ Q˜ P˜(ℏ˜)+Q˜ N˜ e(ℏ˜)+Q˜ N˜(ℏ˜)≤ 3.

Definition 2.3.

(Molodtsov 1999) The soft set over the set G˜ is defined as the pair (Q˜, ℋ˜), where Q˜: ℋ˜→ ℙ(G˜) and ℋ˜ be a subset of a set of attributes D˜.

Definition 2.4.

(Maji, Biswas, and Roy 2001) Consider the set G˜ and the subset ℋ˜ of the set of parameters D˜. Then the neutrosophic soft set over G˜ is defined as an order pair (Q˜, ℋ˜) such that Q˜: ℋ˜→ NS(G˜), where the collection of all neutrosophic subsets of G˜ is represented by NS(G˜).

Definition 2.5.

(Smarandache et al. 2017) In the context where ℋ˜ represents a subset of attributes within a set D˜ and for three functions Q˜ u ˇ(ℏ˜), Q˜ d ˇ(ℏ˜), and Q˜ l ˇ(ℏ˜) that represent the degrees of truth, indeterminacy, and falsity, respectively, for each element ℏ˜ within the set ℋ˜, the definition of a complex neutrosophic soft set is as follows.

$$
\widetilde{N} = \left\{{\left({\widetilde{\hslash},\widetilde{\Theta}(\widetilde{\hslash})} \right) = \left({\widetilde{\hslash},{\langle{{\widetilde{Q}}_{\check{u}}(\widetilde{\hslash}),{\widetilde{Q}}_{\check{d}}(\widetilde{\hslash}),{\widetilde{Q}}_{\check{l}}(\widetilde{\hslash})}\rangle}} \right):\widetilde{\hslash} \in \widetilde{\mathcal{H}}} \right\},
$$

where Q˜ u ˇ, Q˜ d ˇ, Q˜ l ˇ: ℋ˜→ cNSS(G˜) are complex fuzzy approximate mappings such that Q˜ u ˇ(ℏ˜)= ℒ˜ u ˇ(ℏ˜) expj Ψ˜ u ˇ(ℏ˜), Q˜ d ˇ(ℏ˜)= ℒ˜ d ˇ(ℏ˜) expj Ψ˜ d ˇ(ℏ˜) and Q˜ l ˇ(ℏ˜)= ℒ˜ l ˇ(ℏ˜) expj Ψ˜ l ˇ(ℏ˜) provided that 0≤ ℒ˜ u ˇ(ℏ˜)+ℒ˜ d ˇ(ℏ˜)+ℒ˜ l ˇ(ℏ˜)≤ 3 and 0 < Ψ˜ u ˇ(ℏ˜)+Ψ˜ d ˇ(ℏ˜)+Ψ˜ l ˇ(ℏ˜)≤ 2 π. The ℒ˜ u ˇ(ℏ˜), ℒ˜ d ˇ(ℏ˜), ℒ˜ l ˇ(ℏ˜) are called the amplitude terms and Ψ˜ u ˇ(ℏ˜), Ψ˜ d ˇ(ℏ˜), and Ψ˜ l ˇ(ℏ˜) are known as phase terms. The refusal membership grade

Q˜ R˜(ℏ˜)=[1−ℒ˜ u ˇ(ℏ˜)−ℒ˜ d ˇ(ℏ˜)−ℒ˜ l ˇ(ℏ˜)] ex p j[2 π−Ψ˜ u ˇ(ℏ˜)−Ψ˜ d ˇ(ℏ˜)−Ψ˜ l ˇ(ℏ˜)] within C[0, 1].

## Methodology

The presented framework consists of two phases: phase one is meant to characterize the basic notions of complex single-valued neutrosophic soft sets (csvNSS) and the phase two is to present a decision support framework for the selection of hospital site. The pictorial outlet of the methodology is presented in Figure 1.

![Figure 1](https://www.tandfonline.com/cms/asset/70302d6f-7cb0-4bc5-be76-b05983b2f749/uaai_a_2375110_f0001_oc.jpg)

**Figure 1.** Phases of proposed framework.

### Complex Single-Valued Neutrosophic Soft Set (csvNSS)

The purpose of this section is to explore basic concepts and actions related to complex single-valued neutrosophic soft sets (csvNSS).

Definition 3.1.

In the context where ℋ represents a subset of attributes within a set E˜ and for three functions “ Q˜ u ˇ(ℏ˜), Q˜ l ˇ(ℏ˜), and Q˜ l ˇ(ℏ˜)” that represent the degrees of truth, indeterminacy, and falsity, respectively, for each element ℏ˜ within the set ℋ˜, then the csvNSS is defined as

$$
\widetilde{N} = \left\{{\left({\widetilde{\hslash},\widetilde{\Theta}(\widetilde{\hslash})} \right) = \left({\widetilde{\hslash},{\langle{{\widetilde{Q}}_{\check{u}}(\widetilde{\hslash}),{\widetilde{Q}}_{\check{d}}(\widetilde{\hslash}),{\widetilde{Q}}_{\check{l}}(\widetilde{\hslash})}\rangle}} \right):\widetilde{\hslash} \in \widetilde{\mathcal{H}}} \right\}
$$

where, we have complex fuzzy approximate mappings denoted as Q˜ u ˇ, Q˜ d ˇ, Q˜ l ˇ: ℋ˜→ csvNSS(G˜). These mappings are characterized by the equations Q˜ u ˇ(ℏ˜)= ℒ˜ u ˇ(ℏ˜) expj Ψ˜ u ˇ(ℏ˜), Q˜ d ˇ(ℏ˜)= ℒ˜ d ˇ(ℏ˜) expj Ψ˜ d ˇ(ℏ˜), and Q˜ l ˇ(ℏ˜)= ℒ˜ l ˇ(ℏ˜) expj Ψ˜ l ˇ(ℏ˜), with the conditions that 0≤ ℒ˜ u ˇ(ℏ˜)+ℒ˜ d ˇ(ℏ˜)+ℒ˜ l ˇ(ℏ˜)≤ 3 and 0≤ Ψ˜ u ˇ(ℏ˜)+Ψ˜ d ˇ(ℏ˜)+Ψ˜ l ˇ(ℏ˜)≤ 2 π. Here, the terms ℒ˜ u ˇ(ℏ˜), ℒ˜ d ˇ(ℏ˜), and ℒ˜ l ˇ(ℏ˜) are referred to as the amplitude components, while Ψ˜ u ˇ(ℏ˜), Ψ˜ d ˇ(ℏ˜), and Ψ˜ l ˇ(ℏ˜) are known as the phase components. Additionally, the refusal membership grade Q˜ R˜(ℏ˜) is defined as

Q˜ R˜(ℏ˜)=[1−ℒ˜ u ˇ(ℏ˜)−ℒ˜ d ˇ(ℏ˜)−ℒ˜ l ˇ(ℏ˜)] ex p j[2 π−Ψ˜ u ˇ(ℏ˜)−Ψ˜ d ˇ(ℏ˜)−Ψ˜ l ˇ(ℏ˜)]. This expression is defined within the complex number space C[0, 1]. For ease of reference, the combination

$$
\langle{\widetilde{\mathcal{L}}}_{\check{u}}(\widetilde{\hslash})\mathit{expj}{\widetilde{\Psi}}_{\check{u}}(\widetilde{\hslash}),{\widetilde{\mathcal{L}}}_{\check{d}}(\widetilde{\hslash})\mathit{expj}{\widetilde{\Psi}}_{\check{d}}(\widetilde{\hslash}),{\widetilde{\mathcal{L}}}_{\check{l}}(\widetilde{\hslash})\mathit{expj}{\widetilde{\Psi}}_{\check{l}}(\widetilde{\hslash})\rangle
$$

is termed a complex single-value neutrosophic soft number (csvNSS). The entire collection of csvNSS over G˜ is represented as csvNSS(G˜).

Example 3.2.

Let for an initial space G˜={n˜ 1, n˜ 2, n˜ 3, n˜ 4} of elements and

E˜={ℏ˜ 1, ℏ˜ 2, ℏ˜ 3, ℏ˜ 4, ℏ˜ 5, ℏ˜ 6} be a collection of attributes with ℋ˜={ℏ˜ 1, ℏ˜ 2, ℏ˜ 5, ℏ˜ 6}⊆ E˜ then approximate elements of CSSNSS N˜ 1 are computed as

$$
\widetilde{\Theta}({\widetilde{\hslash}}_{1}) = \begin{Bmatrix} {\left({{\widetilde{n}}_{1},\left\langle \begin{matrix} {0.51\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.22)},0.65\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.31)},0.92\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.15)}} \end{matrix} \right\rangle} \right),} \\ {\left({{\widetilde{n}}_{2},\left\langle \begin{matrix} {0.93\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.18)},0.45\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.21)},0.59\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.22)}} \end{matrix} \right\rangle} \right),} \\ {\left({{\widetilde{n}}_{3},\left\langle \begin{matrix} {0.99\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.25)},0.75\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.30)},0.40\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.45)}} \end{matrix} \right\rangle} \right),} \\ \left({{\widetilde{n}}_{4},\left\langle \begin{matrix} {0.95\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.30)},0.91\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.45)},0.43\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.60)}} \end{matrix} \right\rangle} \right) \end{Bmatrix},
$$

$$
\widetilde{\Theta}({\widetilde{\hslash}}_{2}) = \begin{Bmatrix} {\left({{\widetilde{n}}_{1},\left\langle \begin{matrix} {0.82\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.24)},0.76\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.30)},0.85\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.40)}} \end{matrix} \right\rangle} \right),} \\ {\left({{\widetilde{n}}_{2},\left\langle \begin{matrix} {0.92\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.31)},0.85\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.34)},0.78\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.37)}} \end{matrix} \right\rangle} \right),} \\ {\left({{\widetilde{n}}_{3},\left\langle \begin{matrix} {0.63\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.32)},0.96\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.35)},0.79\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.38)}} \end{matrix} \right\rangle} \right),} \\ \left({{\widetilde{n}}_{4},\left\langle \begin{matrix} {0.94\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.33)},0.77\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.36)},0.56\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.39)}} \end{matrix} \right\rangle} \right) \end{Bmatrix},
$$

$$
\widetilde{\Theta}({\widetilde{\hslash}}_{5}) = \begin{Bmatrix} {\left({{\widetilde{n}}_{1},\left\langle \begin{matrix} {0.90\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.41)},0.72\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.31)},0.70\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.51)}} \end{matrix} \right\rangle} \right),} \\ {\left({{\widetilde{n}}_{2},\left\langle \begin{matrix} {0.99\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.30)},0.91\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.33)},0.67\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.36)}} \end{matrix} \right\rangle} \right),} \\ {\left({{\widetilde{n}}_{3},\left\langle \begin{matrix} {0.83\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.31)},0.65\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.34)},0.98\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.37)}} \end{matrix} \right\rangle} \right),} \\ \left({{\widetilde{n}}_{4},\left\langle \begin{matrix} {0.93\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.32)},0.96\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.35)},0.69\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.38)}} \end{matrix} \right\rangle} \right) \end{Bmatrix},
$$

$$
\widetilde{\Theta}({\widetilde{\hslash}}_{6}) = \begin{Bmatrix} {\left({{\widetilde{n}}_{1},\left\langle \begin{matrix} {0.86\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.44)},0.94\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.55)},0.89\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.66)}} \end{matrix} \right\rangle} \right),} \\ {\left({{\widetilde{n}}_{2},\left\langle \begin{matrix} {0.78\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.18)},0.88\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.21)},0.91\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.24)}} \end{matrix} \right\rangle} \right),} \\ {\left({{\widetilde{n}}_{3},\left\langle \begin{matrix} {0.96\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.19)},0.69\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.22)},0.82\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.25)}} \end{matrix} \right\rangle} \right),} \\ \left({{\widetilde{n}}_{4},\left\langle \begin{matrix} {0.77\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.20)},0.90\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.23)},0.53\mathit{ex}p^{\mathit{i}2\mathit{\pi}(0.26)}} \end{matrix} \right\rangle} \right) \end{Bmatrix}.
$$

The csvNSS N˜ 1 is constructed as

$$
{\widetilde{\mathcal{N}}}_{1} = \begin{Bmatrix} {({\widetilde{\hslash}}_{1},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{1})),({\widetilde{\hslash}}_{2},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{2})),({\widetilde{\hslash}}_{5},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{5})),({\widetilde{\hslash}}_{6},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{6}))} \end{Bmatrix}
$$

It can be represented in matrix notation as

$$
{\widetilde{\mathcal{N}}}_{1} = \begin{pmatrix} \left\langle \begin{matrix} {0.51^{0.22},} \\ {0.65^{0.31},} \\ 0.92^{0.15} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.18},} \\ {0.45^{0.21},} \\ 0.59^{0.22} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.99^{0.25},} \\ {0.75^{0.30},} \\ 0.40^{0.45} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.95^{0.30},} \\ {0.91^{0.45},} \\ 0.43^{0.60} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.12^{0.82},} \\ {0.76^{0.30},} \\ 0.85^{0.40} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.31},} \\ {0.85^{0.34},} \\ 0.78^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.63^{0.32},} \\ {0.96^{0.35},} \\ 0.79^{0.38} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.94^{0.33},} \\ {0.77^{0.36},} \\ 0.56^{0.39} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.90^{0.41},} \\ {0.72^{0.31},} \\ 0.70^{0.51} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.99^{0.30},} \\ {0.91^{0.33},} \\ 0.67^{0.36} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.83^{0.31},} \\ {0.65^{0.34},} \\ 0.98^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {.93^{0.32},} \\ {0.96^{0.35},} \\ 0.69^{0.38} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.86^{0.44},} \\ {0.94^{0.55},} \\ 0.89^{0.66} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.78^{0.18},} \\ {0.88^{0.21},} \\ 0.91^{0.24} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.96^{0.19},} \\ {0.69^{0.22},} \\ 0.82^{0.25} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.77^{0.20},} \\ {0.90^{0.23},} \\ 0.53^{0.26} \end{matrix} \right\rangle \end{pmatrix}
$$

In a similar way, another example of csvNSS is constructed as

$$
{\widetilde{\mathcal{N}}}_{2} = \begin{Bmatrix} {({\widetilde{\hslash}}_{1},{\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{1})),({\widetilde{\hslash}}_{3},{\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{3})),({\widetilde{\hslash}}_{4},{\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{4})),({\widetilde{\hslash}}_{6},{\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{6}))} \end{Bmatrix},
$$

which is given as

$$
{\widetilde{\mathcal{N}}}_{2} = \begin{pmatrix} \left\langle \begin{matrix} {0.62^{0.12},} \\ {0.76^{0.21},} \\ 0.90^{0.35} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.12},} \\ {0.65^{0.25},} \\ 0.89^{0.21} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.90^{0.14},} \\ {0.78^{0.31},} \\ 0.51^{0.42} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.91^{0.28},} \\ {0.51^{0.13},} \\ 0.44^{0.19} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.72^{0.32},} \\ {0.71^{0.25},} \\ 0.85^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.11},} \\ {0.55^{0.24},} \\ 0.88^{0.47} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.43^{0.22},} \\ {0.99^{0.15},} \\ 0.69^{0.41} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.98^{0.14},} \\ {0.87^{0.26},} \\ 0.67^{0.52} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.93^{0.21},} \\ {0.62^{0.32},} \\ 0.65^{0.46} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.89^{0.32},} \\ {0.90^{0.41},} \\ 0.64^{0.26} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.11},} \\ {0.85^{0.24},} \\ 0.94^{0.47} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.19},} \\ {0.96^{0.45},} \\ 0.73^{0.29} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.96^{0.35},} \\ {0.94^{0.35},} \\ 0.49^{0.36} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.88^{0.24},} \\ {0.69^{0.32},} \\ 0.56^{0.13} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.96^{0.22},} \\ {0.49^{0.32},} \\ 0.25^{0.36} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.90^{0.20},} \\ {0.68^{0.33},} \\ 0.43^{0.32} \end{matrix} \right\rangle \end{pmatrix}.
$$

Definition 3.3.

Consider two complex single-valued neutrosophic soft sets (csvNSSs) defined over a universe G˜. We establish the following:

N˜ 1 is characterized as an empty csvNSS, denoted as N˜ 1∅, if, for all x˜∈ G˜, N˜ 1(x˜) is an empty set.

N˜ 1 is identified as an absolute csvNSS, denoted as N˜ 1 ℏ˜, if, for all x˜∈ G˜, N˜ 1(x˜) equals the entire universe ℏ˜.

N˜ 1 is considered a CSVNS-subset of N˜ 2, represented as N˜ 1⊆ N˜ 2, if, for every x˜∈ G˜, the set Θ˜ 1(v˜) is a subset of Θ˜ 2(v˜). In other words, the following conditions hold:

$$
{\widetilde{\mathcal{L}}}_{{\check{u}}_{1}}(\widetilde{v}) \leq {\widetilde{\mathcal{L}}}_{{\check{u}}_{2}}(\widetilde{v}),{\widetilde{\mathcal{L}}}_{{\check{d}}_{1}}(\widetilde{v}) \leq {\widetilde{\mathcal{L}}}_{{\check{d}}_{2}}(\widetilde{v}),{\widetilde{\mathcal{L}}}_{{\check{l}}_{1}}(\widetilde{v}) \leq {\widetilde{\mathcal{L}}}_{{\check{l}}_{2}}(\widetilde{v}),
$$

and,

$$
{\widetilde{\Psi}}_{{\check{u}}_{1}}(\widetilde{v}) \leq {\widetilde{\Psi}}_{{\check{u}}_{2}}(\widetilde{v}),{\widetilde{\Psi}}_{{\check{d}}_{1}}(\widetilde{v}) \leq {\widetilde{\Psi}}_{{\check{d}}_{2}}(\widetilde{v}),{\widetilde{\Psi}}_{{\check{l}}_{1}}(\widetilde{v}) \leq {\widetilde{\Psi}}_{{\check{l}}_{2}}(\widetilde{v}).
$$

(4) N˜ 1 is said to be equal to N˜ 2, denoted by N˜ 1= N˜ 2, if for all x˜∈ ℏ˜, the following conditions are satisfied:

$$
{\widetilde{\mathcal{L}}}_{{\check{u}}_{1}}(\widetilde{v}) = {\widetilde{\mathcal{L}}}_{{\check{u}}_{2}}(\widetilde{v}),{\widetilde{\mathcal{L}}}_{{\check{d}}_{1}}(\widetilde{v}) = {\widetilde{\mathcal{L}}}_{{\check{d}}_{2}}(\widetilde{v}),{\widetilde{\mathcal{L}}}_{{\check{l}}_{1}}(\widetilde{v}) = {\widetilde{\mathcal{L}}}_{{\check{l}}_{2}}(\widetilde{v}),
$$

and,

$$
{\widetilde{\Psi}}_{{\check{u}}_{1}}(\widetilde{v}) = {\widetilde{\Psi}}_{{\check{u}}_{2}}(\widetilde{v}),{\widetilde{\Psi}}_{{\check{d}}_{1}}(\widetilde{v}) = {\widetilde{\Psi}}_{{\check{d}}_{2}}(\widetilde{v}),{\widetilde{\Psi}}_{{\check{l}}_{1}}(\widetilde{v}) = {\widetilde{\Psi}}_{{\check{l}}_{2}}(\widetilde{v}).
$$

#### Some Properties of CsvNSS

The purpose of this section is to establish the fundamental set-theoretical operations that are applicable to csvNSS, specifically focusing on the operations complement, union, and intersection of the csvNSSs. For this, assume two csvNSSs N˜ 1 and N˜ 2 defined over a universal set G˜.

Definition 3.4.

The complement of N˜ 1, represented as N˜ 1 c, is a csvNSS defined as N˜ 1 c={(x˜, Θ˜ 1 c(x˜)): x˜∈ G˜}. Here, Θ˜ 1 c(x˜) stands for the complement of Θ˜ 1, which is a single-valued complex neutrosophic function.

Example 3.5

Consider Previous Example 3.2. The complement of N˜ 1, that is

$$
{{\widetilde{\mathcal{N}}}_{1}}^{\mathit{c}} = \{{\widetilde{\Theta}}_{1}^{\mathit{c}}({\widetilde{\hslash}}_{1}),{\widetilde{\Theta}}_{1}^{\mathit{c}}({\widetilde{\hslash}}_{2}),{{\widetilde{\Theta}}_{1}}^{\mathit{c}}({\widetilde{\hslash}}_{5}),{{\widetilde{\Theta}}_{1}}^{\mathit{c}}({\widetilde{\hslash}}_{6})\}
$$

$$
{{\widetilde{\mathcal{N}}}_{1}}^{\mathit{c}} = \begin{pmatrix} \left\langle \begin{matrix} {0.92^{0.15},} \\ {0.35^{0.31},} \\ 0.51^{0.22} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.59^{0.22},} \\ {0.55^{0.21},} \\ 0.93^{0.18} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.40^{0.45},} \\ {0.25^{0.30},} \\ 0.99^{0.25} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.43^{0.60},} \\ {0.09^{0.45},} \\ 0.95^{0.30} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.85^{0.40},} \\ {0.24^{0.30},} \\ 0.12^{0.82} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.78^{0.37},} \\ {0.15^{0.34},} \\ 0.92^{0.31} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.79^{0.38},} \\ {0.04^{0.35},} \\ 0.63^{0.32} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.56^{0.39},} \\ {0.33^{0.36},} \\ 0.94^{0.33} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.70^{0.51},} \\ {0.28^{0.31},} \\ 0.90^{0.41} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.67^{0.36},} \\ {0.09^{0.33},} \\ 0.99^{0.30} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.98^{0.37},} \\ {0.35^{0.34},} \\ 0.83^{0.31} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.69^{0.38},} \\ {0.04^{0.35},} \\ 0.93^{0.32} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.89^{0.66},} \\ {0.06^{0.55},} \\ 0.86^{0.44} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.91^{0.24},} \\ {0.12^{0.21},} \\ 0.78^{0.18} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.82^{0.25},} \\ {0.31^{0.22},} \\ 0.96^{0.19} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.53^{0.26},} \\ {0.10^{0.23},} \\ 0.77^{0.20} \end{matrix} \right\rangle \end{pmatrix}.
$$

Definition 3.6.

The union of two csvNSSs N˜ 1 and N˜ 2, represented by N˜ 1∪⌣ N˜ 2, is defined as

$$
\chi_{C} = {\widetilde{\mathcal{N}}}_{1}\check{\cup \!\!}\;\;{\widetilde{\mathcal{N}}}_{2} = \{(\widetilde{\hslash},{\widetilde{\Theta}}_{1}(\widetilde{\hslash})\check{\cup \!\!}\;\;\!{\widetilde{\Theta}}_{2}(\widetilde{\hslash})):\widetilde{\hslash} \in \widetilde{\mathcal{G}}\},
$$

$$
\delta_{U}(\widetilde{\hslash}) = \left\{\begin{matrix} {{\!\!\!\!\!\!\!(\widetilde{\hslash},{\widetilde{\Theta}}_{1}(\widetilde{\hslash})),}\quad\quad} & {\mathit{if}\widetilde{\hslash} \in {\widetilde{\mathcal{N}}}_{1} - {\widetilde{\mathcal{N}}}_{2},} \\ {{(\widetilde{\hslash},{\widetilde{\Theta}}_{2}(\widetilde{\hslash})),}\quad\quad\quad} & {\mathit{if}\widetilde{\hslash} \in {\widetilde{\mathcal{N}}}_{2} - {\widetilde{\mathcal{N}}}_{1},} \\ {(\widetilde{\hslash},{\widetilde{\Theta}}_{1}(\widetilde{\hslash})\check{\cup \!\!}\;\;{\widetilde{\Theta}}_{2}(\widetilde{\hslash})),} & {\mathit{if}\widetilde{\hslash} \in {\widetilde{\mathcal{N}}}_{1} \cap {\widetilde{\mathcal{N}}}_{2},} \end{matrix} \right.
$$

where C= N˜ 1∪ N˜ 2, ℏ˜∈ G˜, and

$$
{\widetilde{\Theta}}_{1}(\widetilde{\hslash})\check{\cup \text{\!\!}}\text{ \!}{\widetilde{\Theta}}_{2}(\widetilde{\hslash}) = \left\{\begin{array}{l} {({\widetilde{\mathcal{L}}}_{{\widetilde{T}}_{1}}(\widetilde{\hslash}) \vee {\widetilde{\mathcal{L}}}_{T_{2}}(\widetilde{\hslash}))e^{i({\widetilde{\Psi}}_{{\widetilde{T}}_{1}}(\widetilde{\hslash}) \cup {\widetilde{\Psi}}_{{\widetilde{T}}_{2}}(\widetilde{\hslash}))},} \\ {({\widetilde{\mathcal{L}}}_{I_{1}}(\widetilde{\hslash}) \land \mathcal{L}_{{\widetilde{I}}_{2}}(\widetilde{\hslash}))e^{i({\widetilde{\Psi}}_{{\widetilde{I}}_{1}}(\widetilde{\hslash}) \cup {\widetilde{\Psi}}_{{\widetilde{I}}_{2}}(\widetilde{\hslash}))},} \\ {({\widetilde{\mathcal{L}}}_{{\widetilde{F}}_{1}}(\widetilde{\hslash}) \land {\widetilde{\mathcal{L}}}_{{\widetilde{F}}_{2}}(\widetilde{\hslash}))e^{i({\widetilde{\Psi}}_{{\widetilde{F}}_{1}}(\widetilde{\hslash}) \cup {\widetilde{\Psi}}_{{\widetilde{F}}_{2}}(\widetilde{\hslash}))}} \end{array} \right\}.
$$

In the above definition, the symbol ∨ is for the maximum and the symbol ∧ is for the minimum operators. The phase terms associated with each of the function fall within the interval (0, 2 π] and can be calculated by using any of the following operators:

(1) Sum:

$$
\mu_{{\widetilde{T}}_{1} \cup {\widetilde{T}}_{2}}(\widetilde{\hslash}) = {\widetilde{\Psi}}_{{\widetilde{T}}_{1}}(\widetilde{\hslash}) + {\widetilde{\Psi}}_{{\widetilde{T}}_{2}}(\widetilde{\hslash}),
$$

$$
\nu_{{\widetilde{I}}_{1} \cup {\widetilde{I}}_{2}}(\widetilde{\hslash}) = {\widetilde{\Psi}}_{{\widetilde{I}}_{1}}(\widetilde{\hslash}) + {\widetilde{\Psi}}_{{\widetilde{I}}_{2}}(\widetilde{\hslash}),
$$

$$
\omega_{{\widetilde{F}}_{1} \cup {\widetilde{F}}_{2}}(\widetilde{\hslash}) = {\widetilde{\Psi}}_{{\widetilde{F}}_{1}}(\widetilde{\hslash}) + {\widetilde{\Psi}}_{{\widetilde{F}}_{2}}(\widetilde{\hslash}).
$$

(2) Max:

$$
\mu_{{\widetilde{T}}_{1} \cup {\widetilde{T}}_{2}}(\widetilde{\hslash}) = \max({\widetilde{\Psi}}_{{\widetilde{T}}_{1}}(\widetilde{\hslash}),{\widetilde{\Psi}}_{{\widetilde{T}}_{2}}(\widetilde{\hslash})),
$$

$$
\nu_{{\widetilde{I}}_{1} \cup {\widetilde{I}}_{2}}(\widetilde{\hslash}) = \max({\widetilde{\Psi}}_{{\widetilde{I}}_{1}}(\widetilde{\hslash}),{\widetilde{\Psi}}_{{\widetilde{I}}_{2}}(\widetilde{\hslash})),
$$

$$
\omega_{{\widetilde{F}}_{1} \cup {\widetilde{F}}_{2}}(\widetilde{\hslash}) = \max({\widetilde{\Psi}}_{{\widetilde{F}}_{1}}(\widetilde{\hslash}),{\widetilde{\Psi}}_{{\widetilde{T}}_{2}}(\widetilde{\hslash})).
$$

(3) Min:

$$
\mu_{{\widetilde{T}}_{1} \cap {\widetilde{T}}_{2}}(\widetilde{\hslash}) = \min({\widetilde{\Psi}}_{{\widetilde{T}}_{1}}(\widetilde{\hslash}),{\widetilde{\Psi}}_{{\widetilde{T}}_{2}}(\widetilde{\hslash})),
$$

$$
\nu_{{\widetilde{I}}_{1} \cap {\widetilde{I}}_{2}}(\widetilde{\hslash}) = \min({\widetilde{\Psi}}_{{\widetilde{I}}_{1}}(\widetilde{\hslash}),{\widetilde{\Psi}}_{{\widetilde{I}}_{2}}(\widetilde{\hslash})),
$$

$$
\omega_{{\widetilde{F}}_{1} \cap {\widetilde{F}}_{2}}(\widetilde{\hslash}) = \min({\widetilde{\Psi}}_{{\widetilde{F}}_{1}}(\widetilde{\hslash}),{\widetilde{\Psi}}_{{\widetilde{T}}_{2}}(\widetilde{\hslash})).
$$

(4) The contest involving truth, indeterminacy and falsity components:

$$
\mu_{{\widetilde{N}}_{1} \cup {\widetilde{N}}_{2}}(\widetilde{\hslash}) = \left\{\begin{array}{l} {{\widetilde{\Psi}}_{{\widetilde{T}}_{1}}(\widetilde{\hslash})\mathit{if}{\widetilde{\mathcal{L}}}_{{\widetilde{T}}_{1}}(\widetilde{\hslash})\text{>}{\widetilde{\mathcal{L}}}_{{\widetilde{T}}_{2}}(\widetilde{\hslash}),} \\ {{\widetilde{\Psi}}_{{\widetilde{T}}_{2}}(\widetilde{\hslash})\mathit{if}{\widetilde{\mathcal{L}}}_{{\widetilde{T}}_{2}}(\widetilde{\hslash})\text{>}{\widetilde{\mathcal{L}}}_{{\widetilde{T}}_{1}}(\widetilde{\hslash}),} \end{array} \right.
$$

$$
\nu_{{\widetilde{N}}_{1} \cup {\widetilde{N}}_{2}}(\widetilde{\hslash}) = \left\{\begin{array}{l} {{\widetilde{\Psi}}_{{\widetilde{I}}_{1}}(\widetilde{\hslash})\text{ }\mathit{if}{\widetilde{\mathcal{L}}}_{{\widetilde{I}}_{1}}(\widetilde{\hslash})\text{<}{\widetilde{\mathcal{L}}}_{{\widetilde{I}}_{2}}(\widetilde{\hslash}),} \\ {{\widetilde{\Psi}}_{{\widetilde{I}}_{2}}(\widetilde{\hslash})\text{ }\mathit{if}{\widetilde{\mathcal{L}}}_{{\widetilde{I}}_{2}}(\widetilde{\hslash})\text{<}{\widetilde{\mathcal{L}}}_{{\widetilde{I}}_{1}}(\widetilde{\hslash}),} \end{array} \right.
$$

and

$$
\omega_{{\widetilde{N}}_{1} \cup {\widetilde{N}}_{2}}(\widetilde{\hslash}) = \left\{\begin{array}{l} {{\widetilde{\Psi}}_{{\widetilde{F}}_{1}}(\widetilde{\hslash})\text{ }\mathit{if}{\widetilde{\mathcal{L}}}_{{\widetilde{F}}_{1}}(\widetilde{\hslash})\text{<}{\widetilde{\mathcal{L}}}_{{\widetilde{F}}_{2}}(\widetilde{\hslash}),} \\ {{\widetilde{\Psi}}_{{\widetilde{F}}_{2}}(\widetilde{\hslash})\text{ }\mathit{if}{\widetilde{\mathcal{L}}}_{{\widetilde{F}}_{2}}(\widetilde{\hslash})\text{<}{\widetilde{\mathcal{L}}}_{{\widetilde{F}}_{1}}(\widetilde{\hslash}).} \end{array} \right.
$$

Note that these operators are the generalized form of the operators that are presented for complex neutrosophic soft set (cNSS) by Smarandache et al. (2017).

In a similar way, the intersection of any two csvNSSs is defined as

Definition 3.7.

The intersection of any two csvNSSs N˜ 1 and N˜ 2, is denoted by N˜ 1∩ ˇ N˜ 2, and defined as

$$
\chi_{D} = {\widetilde{\mathcal{N}}}_{1}\check{\cap \!\!}\;\;{\widetilde{\mathcal{N}}}_{2} = \{(\widetilde{\hslash},{\widetilde{\Theta}}_{1}(\widetilde{\hslash})\check{\cap \!\!}\;\;{\widetilde{\Theta}}_{2}(\widetilde{\hslash})):\widetilde{\hslash} \in \widetilde{\mathcal{G}}\},
$$

$$
\chi_{D}(\widetilde{\hslash}) = \left\{\begin{matrix} {{(\widetilde{\hslash},{\widetilde{\Theta}}_{1}(\widetilde{\hslash})),}\quad\quad\quad} & {\mathit{if}\widetilde{\hslash} \in {\widetilde{\mathcal{N}}}_{1} - {\widetilde{\mathcal{N}}}_{2},} \\ {{(\widetilde{\hslash},{\widetilde{\Theta}}_{2}(\widetilde{\hslash})),}\quad\quad\quad} & {\mathit{if}\widetilde{\hslash} \in {\widetilde{\mathcal{N}}}_{2} - {\widetilde{\mathcal{N}}}_{1},} \\ {(\widetilde{\hslash},{\widetilde{\Theta}}_{1}(\widetilde{\hslash})\check{\cap \!\!}\;\;{\widetilde{\Theta}}_{2}(\widetilde{\hslash})),} & {\mathit{if}\widetilde{\hslash} \in {\widetilde{\mathcal{N}}}_{1} \cap {\widetilde{\mathcal{N}}}_{2},} \end{matrix} \right.
$$

where D= N˜ 1∩ N˜ 2, ℏ˜∈ G˜, and

$$
{\widetilde{\Theta}}_{1}(\widetilde{\hslash})\check{\cap \text{\!\!}}\text{ \!}{\widetilde{\Theta}}_{2}(\widetilde{\hslash}) = \left\{\begin{array}{l} {({\widetilde{\mathcal{L}}}_{T_{1}}(\widetilde{\hslash}) \land {\widetilde{\mathcal{L}}}_{{\widetilde{T}}_{2}}(\widetilde{\hslash}))e^{i({\widetilde{\Psi}}_{{\widetilde{T}}_{1}}(\widetilde{\hslash}) \cup {\widetilde{\Psi}}_{{\widetilde{T}}_{2}}(\widetilde{\hslash}))},} \\ {({\widetilde{\mathcal{L}}}_{{\widetilde{I}}_{1}}(\widetilde{\hslash}) \vee {\widetilde{\mathcal{L}}}_{{\widetilde{I}}_{2}}(\widetilde{\hslash}))e^{i({\widetilde{\Psi}}_{{\widetilde{I}}_{1}}(\widetilde{\hslash}) \cup {\widetilde{\Psi}}_{{\widetilde{I}}_{2}}(\widetilde{\hslash}))},} \\ {({\widetilde{\mathcal{L}}}_{{\widetilde{F}}_{1}}(\widetilde{\hslash}) \vee {\widetilde{\mathcal{L}}}_{{\widetilde{F}}_{2}}(\widetilde{\hslash}))e^{i({\widetilde{\Psi}}_{{\widetilde{F}}_{1}}(\widetilde{\hslash}) \cup {\widetilde{\Psi}}_{{\widetilde{F}}_{2}}(\widetilde{\hslash}))}} \end{array} \right\}.
$$

In the above definition the symbol ∨ is for the maximum and the symbol ∧ is for the minimum operators. The phase terms associated with the each of the function fall within interval (0, 2 π], these phase terms can be determined with the help of any one of the operator that were explained Definition 3.6.

Example 3.8.

Recapitulating the data from Example 3.2, we have formulated the following two CSFSSs, represented in matrix form as presented below:

The csvNSS

$$
{\widetilde{\mathcal{N}}}_{1} = \begin{Bmatrix} {({\widetilde{\hslash}}_{1},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{1})),({\widetilde{\hslash}}_{2},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{2})),({\widetilde{\hslash}}_{5},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{5})),({\widetilde{\hslash}}_{6},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{6}))} \end{Bmatrix}
$$

is given as

$$
{\widetilde{\mathcal{N}}}_{1} = \begin{pmatrix} \left\langle \begin{matrix} {0.51^{0.22},} \\ {0.65^{0.31},} \\ 0.92^{0.15} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.18},} \\ {0.45^{0.21},} \\ 0.59^{0.22} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.99^{0.25},} \\ {0.75^{0.30},} \\ 0.40^{0.45} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.95^{0.30},} \\ {0.91^{0.45},} \\ 0.43^{0.60} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.12^{0.82},} \\ {0.76^{0.30},} \\ 0.85^{0.40} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.31},} \\ {0.85^{0.34},} \\ 0.78^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.63^{0.32},} \\ {0.96^{0.35},} \\ 0.79^{0.38} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.94^{0.33},} \\ {0.77^{0.36},} \\ 0.56^{0.39} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.90^{0.41},} \\ {0.72^{0.31},} \\ 0.70^{0.51} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.99^{0.30},} \\ {0.91^{0.33},} \\ 0.67^{0.36} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.83^{0.31},} \\ {0.65^{0.34},} \\ 0.98^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.32},} \\ {0.96^{0.35},} \\ 0.69^{0.38} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.86^{0.44},} \\ {0.94^{0.55},} \\ 0.89^{0.66} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.78^{0.18},} \\ {0.88^{0.21},} \\ 0.91^{0.24} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.96^{0.19},} \\ {0.69^{0.22},} \\ 0.82^{0.25} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.77^{0.20},} \\ {0.90^{0.23},} \\ 0.53^{0.26} \end{matrix} \right\rangle \end{pmatrix}.
$$

The csvNSS

$$
{\widetilde{\mathcal{N}}}_{2} = \begin{Bmatrix} {({\widetilde{\hslash}}_{1},{\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{1})),({\widetilde{\hslash}}_{3},{\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{3})),({\widetilde{\hslash}}_{4},{\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{4})),({\widetilde{\hslash}}_{6},{\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{6}))} \end{Bmatrix}
$$

is given as

$$
{\widetilde{\mathcal{N}}}_{2} = \begin{pmatrix} \left\langle \begin{matrix} {0.62^{0.12},} \\ {0.76^{0.21},} \\ 0.90^{0.35} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.12},} \\ {0.65^{0.25},} \\ 0.89^{0.21} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.90^{0.14},} \\ {0.78^{0.31},} \\ 0.51^{0.42} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.91^{0.28},} \\ {0.51^{0.13},} \\ 0.44^{0.19} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.72^{0.32},} \\ {0.71^{0.25},} \\ 0.85^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.11},} \\ {0.55^{0.24},} \\ 0.88^{0.47} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.43^{0.22},} \\ {0.99^{0.15},} \\ 0.69^{0.41} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.98^{0.14},} \\ {0.87^{0.26},} \\ 0.67^{0.52} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.93^{0.21},} \\ {0.62^{0.32},} \\ 0.65^{0.46} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.89^{0.32},} \\ {0.90^{0.41},} \\ 0.64^{0.26} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.11},} \\ {0.85^{0.24},} \\ 0.94^{0.47} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.19},} \\ {0.96^{0.45},} \\ 0.73^{0.29} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.96^{0.35},} \\ {0.94^{0.35},} \\ 0.49^{0.36} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.88^{0.24},} \\ {0.69^{0.32},} \\ 0.56^{0.13} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.96^{0.22},} \\ {0.49^{0.32},} \\ 0.25^{0.36} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.90^{0.20},} \\ {0.68^{0.33},} \\ 0.43^{0.32} \end{matrix} \right\rangle \end{pmatrix}.
$$

Then union

$$
{{\widetilde{\mathcal{N}}}_{1} \cup {\widetilde{\mathcal{N}}}_{2}} = \begin{Bmatrix} {({\widetilde{\hslash}}_{1},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{1}) \cup {\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{1})),({\widetilde{\hslash}}_{2},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{2})),({\widetilde{\hslash}}_{3},{\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{3})),({\widetilde{\hslash}}_{4},{\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{4})),} \\ {({\widetilde{\hslash}}_{5},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{5})),({\widetilde{\hslash}}_{6},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{6}) \cup {\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{6}))} \end{Bmatrix}
$$

is given as

$$
{\widetilde{\mathcal{N}}}_{1} \cup {\widetilde{\mathcal{N}}}_{2} = \begin{pmatrix} \left\langle \begin{matrix} {0.62^{0.22},} \\ {0.76^{0.31},} \\ 0.92^{0.35} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.18},} \\ {0.65^{0.25},} \\ 0.89^{0.22} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.99^{0.25},} \\ {0.78^{0.31},} \\ 0.51^{0.45} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.95^{0.30},} \\ {0.91^{0.45},} \\ 0.44^{0.19} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.12^{0.82},} \\ {0.76^{0.30},} \\ 0.85^{0.40} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.31},} \\ {0.85^{0.34},} \\ 0.78^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.63^{0.32},} \\ {0.96^{0.35},} \\ 0.79^{0.38} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.94^{0.33},} \\ {0.77^{0.36},} \\ 0.56^{0.39} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.72^{0.32},} \\ {0.71^{0.25},} \\ 0.85^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.11},} \\ {0.55^{0.24},} \\ 0.88^{0.47} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.43^{0.22},} \\ {0.99^{0.15},} \\ 0.69^{0.41} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.98^{0.14},} \\ {0.87^{0.26},} \\ 0.67^{0.52} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.93^{0.21},} \\ {0.62^{0.32},} \\ 0.65^{0.46} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.89^{0.32},} \\ {0.90^{0.41},} \\ 0.64^{0.26} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.11},} \\ {0.85^{0.24},} \\ 0.94^{0.47} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.19},} \\ {0.96^{0.45},} \\ 0.73^{0.29} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.90^{0.41},} \\ {0.72^{0.31},} \\ 0.70^{0.51} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.99^{0.30},} \\ {0.91^{0.33},} \\ 0.67^{0.36} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.83^{0.31},} \\ {0.65^{0.34},} \\ 0.98^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.32},} \\ {0.96^{0.35},} \\ 0.69^{0.38} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.96^{0.44},} \\ {0.94^{0.55},} \\ 0.89^{0.66} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.88^{0.24},} \\ {0.88^{0.32},} \\ 0.91^{0.24} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.96^{0.22},} \\ {0.69^{0.32},} \\ 0.82^{0.36} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.90^{0.20},} \\ {0.90^{0.33},} \\ 0.53^{0.32} \end{matrix} \right\rangle \end{pmatrix}.
$$

The intersection is

$$
{{\widetilde{\mathcal{N}}}_{1} \cap {\widetilde{\mathcal{N}}}_{2}} = \begin{Bmatrix} {({\widetilde{\hslash}}_{1},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{1}) \cap {\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{1})),({\widetilde{\hslash}}_{2},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{2})),({\widetilde{\hslash}}_{3},{\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{3})),({\widetilde{\hslash}}_{4},{\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{4})),} \\ {({\widetilde{\hslash}}_{5},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{5})),({\widetilde{\hslash}}_{6},{\widetilde{\Theta}}_{1}({\widetilde{\hslash}}_{6}) \cap {\widetilde{\Theta}}_{2}({\widetilde{\hslash}}_{6}))} \end{Bmatrix}
$$

is given as

$$
{{\widetilde{\mathcal{N}}}_{1} \cap {\widetilde{\mathcal{N}}}_{2}} = \begin{pmatrix} \left\langle \begin{matrix} {0.51^{0.22},} \\ {0.65^{0.31},} \\ 0.90^{0.35} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.18},} \\ {0.45^{0.25},} \\ 0.59^{0.22} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.90^{0.25},} \\ {0.75^{0.31},} \\ 0.40^{0.45} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.91^{0.30},} \\ {0.51^{0.45},} \\ 0.43^{0.19} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.12^{0.82},} \\ {0.76^{0.30},} \\ 0.85^{0.40} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.31},} \\ {0.85^{0.34},} \\ 0.78^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.63^{0.32},} \\ {0.96^{0.35},} \\ 0.79^{0.38} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.94^{0.33},} \\ {0.77^{0.36},} \\ 0.56^{0.39} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.72^{0.32},} \\ {0.71^{0.25},} \\ 0.85^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.11},} \\ {0.55^{0.24},} \\ 0.88^{0.47} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.43^{0.22},} \\ {0.99^{0.15},} \\ 0.69^{0.41} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.98^{0.14},} \\ {0.87^{0.26},} \\ 0.67^{0.52} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.93^{0.21},} \\ {0.62^{0.32},} \\ 0.65^{0.46} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.89^{0.32},} \\ {0.90^{0.41},} \\ 0.64^{0.26} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.11},} \\ {0.85^{0.24},} \\ 0.94^{0.47} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.19},} \\ {0.96^{0.45},} \\ 0.73^{0.29} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.90^{0.41},} \\ {0.72^{0.31},} \\ 0.70^{0.51} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.99^{0.30},} \\ {0.91^{0.33},} \\ 0.67^{0.36} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.83^{0.31},} \\ {0.65^{0.34},} \\ 0.98^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.32},} \\ {0.96^{0.35},} \\ 0.69^{0.38} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.86^{0.44},} \\ {0.94^{0.55},} \\ 0.49^{0.66} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.78^{0.24},} \\ {0.69^{0.32},} \\ 0.56^{0.24} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.96^{0.22},} \\ {0.49^{0.32},} \\ 0.25^{0.36} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.77^{0.20},} \\ {0.68^{0.33},} \\ 0.43^{0.32} \end{matrix} \right\rangle \end{pmatrix}.
$$

### The MADM Based Decisive Technique Using Aggregations of CsvNSS

An algorithm based on the score function, which is detailed in Definitions 0.14 and 0.15 is introduced in this section. These adaptations, derived from concepts originally presented in (Al-Quran and Hassan 2018) and (Smarandache et al. 2017) have been tailored to align with the structure of the csvNSS model. The decision-making process, as outlined in the context of this example, unfolds through the following steps until a final decision is ultimately determined:

Definition 3.9.

A comparison matrix is structured in such a way that its rows are populated with elements from the universal set G˜={u˜ 1, u˜ 2,…, u˜ m}, while its columns are filled with the corresponding parameters E˜={e˜ 1, e˜ 2,…, e˜ n} that pertain to the problem at hand. In this matrix, each entry is denoted as c ij and serves the following purpose:

$$
c_{\mathit{ij}} = ({\widetilde{\mathcal{L}}}_{\mathit{amp}} + {\widetilde{\Psi}}_{\mathit{amp}} - \gamma_{\mathit{amp}}) + ({\widetilde{\mathcal{L}}}_{\mathit{phase}} + {\widetilde{\Psi}}_{\mathit{phase}} - \gamma_{\mathit{phase}}),
$$

The formula above is defined for all b κ∈ G˜, with the condition that b i≠ b κ. The components of this formula are as follows:

• ℒ˜ amp represents the number of instances where the amplitude term of Q˜ u˜(b i)(e˜ j) is greater than or equal to Q˜ u˜(b k)(e˜ j).

• Ψ˜ amp indicates the number of instances where the amplitude term of Q˜ d˜(b i)(e˜ j) is greater than or equal to Q˜ d˜(b k)(e˜ j).

• γ amp signifies the number of instances where the amplitude term of Q˜ l˜(b i)(e˜ j) is greater than or equal to Q˜ l˜(b k)(e˜ j). Furthermore:

• ℒ˜ phase represents the number of instances where the phase term of Q˜ u˜(b i)(e˜ j) is greater than or equal to Q˜ u˜(b k)(e˜ j).

• Ψ˜ phase indicates the number of instances where the phase term of Q˜ d˜(b i)(e˜ j) is greater than or equal to Q˜ d˜(b k)(e˜ j).

• γ phase signifies the number of instances where the phase term of Q˜ l˜(b i)(e˜ j) is greater than or equal to Q˜ l˜(b k)(e˜ j).

These components are used in the context of the given formula to make comparisons between various terms in the complex framework.

Definition 3.10.

The score for an element ℏ˜ i can be determined using the score function d⌣ i, which is formulated as the summation of ∑ j cij.

**Remark 3.11**. In this illustration, the phase terms serve as a representation of the time required for changes in economic indicators to exert their influence on the overall performance of the economy. The magnitude of these phase terms provides insight into which economic sectors hold the greatest sway over the economy and, by extension, which sectors the economy heavily relies upon. To elaborate, as the phase-term approaches 0, it signifies a relatively minor impact, whereas nearing 2 π indicates a more substantial influence. For example, when comparing a phase term like 3 π 4 to others such as π 3 and π 2, the 3 π 4 phase term indicates a higher level of influence. Consequently, we derived the values of ℒ˜ phase, Ψ˜ phase, and γ phase by quantifying the instances in which the phase term of element b ij surpassed that of element b κj.

#### Problem Statement

The substantial rise in population highlights the vital role that hospitals play as the cornerstones of a strong healthcare system. Growing populations inevitably result in an increase in health-related issues, such as persistent illnesses and viral ailments. Because they offer emergency treatments, laboratory services, and therapeutic services, hospitals are essential in tackling these medical problems. Hospitals are essential to maintaining the health of the public since the necessity of medical facilities rises along with the population. Hospitals support research, health awareness, and preventative care in addition to providing emergency medical attention, which helps to build a healthier and more secure community. Sufficient funding for the development and modernization of hospital facilities is necessary to guarantee that local populations have access to high-quality medical care, reducing the negative effects of expanding populations on general well-being. The task of choosing a hospital site is intricate and multidimensional, involving the evaluation of numerous factors in order to identify the optimal spot for medical services. Many variables are involved in this activity, including easy access, vicinity to crowded places, transit systems, atmospheric factors, and the availability of qualified healthcare specialists. The distinct requirements and goals of the local population and the healthcare sector are reflected in the varying weights assigned to each factor during the decision-making process. In addition, laws regarding zoning, patterns of population growth, and land prices add additional complexity to the process of making decisions. The process of selecting a hospital site is intrinsically multicriteria-based due to the complexity of these factors. To make sure that the selected location best satisfies the varied and changing needs of the target audience, a thorough analysis combining quantitative and qualitative data is necessary. Gul, Guneri, and Huang (2021) presented a systematic literature review for hospital site selection based on various methodologies and applications adopted by several researchers by considering different criteria. However, the criteria for the present study are based on the research presented by Soltani and Marandi (2011) after partial modifications. The adopted parameters are presented in Table 1, Figures 2, and 3.

![Figure 2](https://www.tandfonline.com/cms/asset/fd50f6c2-ed20-42a7-b3a4-c60939c06082/uaai_a_2375110_f0002_oc.jpg)

**Figure 2.** Categorical criteria for hospital site selection-I.

![Figure 3](https://www.tandfonline.com/cms/asset/fdfd0df7-7624-4e5b-bc6c-1da3ee60c5b6/uaai_a_2375110_f0003_oc.jpg)

**Figure 3.** Categorical criteria for hospital site selection-II.

**Table 1.** Adopted criteria (Soltani and Marandi 2011).

| Categorial Criteria    | Relevant Sub Criteria                                                                                                                             |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Technical Criteria     | Site Gradient; Ground Conditions (soil/rocks); Accessibility; Cost related to site purchase; Existing infrastructure and availability of services |
| Site Quality Criteria  | Heritage considerations; Environmental considerations; Site area; Site orientation; Site shape                                                    |
| Location Criteria      | Proximity to public transport; Traffic routs; Future population and prominence; Flexibility of land for expansion                                 |
| Miscellaneous Criteria | Pollution free; Population density; Government policies; Socio-demographics of service area                                                       |

Now, let us introduce a dependable methodology that will assist the Ministry of Health in determining which location would be best for a new hospital. This procedure consists of the subsequent steps:

**Table**

|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Algorithm: Hospital site selection using aggregations of csvNSS                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| (1) Firstly create a complex single valued neutrosophic soft set (csvNSS) tailored to the specific problem under study. This set should encompass the elements denoted as ℏ˜ i (where i= 1, 2,…, m) and the parameters represented by e˜ j (with j= 1, 2,…, n) that are pertinent to the problem at hand. In the context of this particular illustration, we will utilize the universal set denoted as ℏ˜, the set of parameters identified as ℋ˜, and reference the csvNSS labeled as N˜ 1, as outlined in example 3.2. |
| (2) For the second stage, establish a comparative matrix and calculate the values of c ij for every ℏ˜ i element and its corresponding parameter e˜ j by applying the formula specified in Definition 3.9.                                                                                                                                                                                                                                                                                                               |
| (3) In this step, calculate the scores d⌣ i for each individual element ℏ˜ i (where i= 1, 2,…, m) by applying Definition 3.10.                                                                                                                                                                                                                                                                                                                                                                                           |
| (4) In the concluding phase of the discussion, the scores derived from the score function are evaluated, and the top-scoring element is designated as the optimal selection. In the case where several elements share the same highest score, any of these elements may be picked as the preferred alternative.                                                                                                                                                                                                          |

The above complete algorithm is summarized in Figure 4.

![Figure 4](https://www.tandfonline.com/cms/asset/4b516165-20a1-4bbd-a945-9e2873718240/uaai_a_2375110_f0004_oc.jpg)

**Figure 4.** Flowchart of proposed algorithm.

Example 3.12.

The population of the province is growing exponentially; therefore, the Ministry of Health, Punjab, Pakistan, needs to construct hospitals in a number of districts. Let there be four sites, say ℋ˜={ℏ˜ 1, ℏ˜ 2, ℏ˜ 3, ℏ˜ 4} located in four different districts, that are evaluated by two real-estate experts, “ D 1 and D 2” and one expert, “ D 3” from Housing, Urban Development, and Public Health Engineering (HUD & PHED). The evaluation process is accomplished based on parameters like b˜ 1= Technical Criteria, b˜ 2= Site Quality Criteria, b˜ 3= Location Criteria, and b˜ 4= Miscellaneous Criteria. After the mutual consensus of experts, approximations of sites are determined based on their opinions, which leads to the construction of csvNSS that is presented in the form of matrix notation. The explanation of the proposed algorithm is given now.

(1) The opinion M D 1 N˜ 1 of first buyer is given as

$$
\begin{pmatrix} \left\langle \begin{matrix} {0.51^{0.22},} \\ {0.65^{0.31},} \\ 0.92^{0.15} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.18},} \\ {0.45^{0.21},} \\ 0.59^{0.22} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.99^{0.25},} \\ {0.75^{0.30},} \\ 0.40^{0.45} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.95^{0.30},} \\ {0.91^{0.45},} \\ 0.43^{0.60} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.12^{0.82},} \\ {0.76^{0.30},} \\ 0.85^{0.40} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.31},} \\ {0.85^{0.34},} \\ 0.78^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.63^{0.32},} \\ {0.96^{0.35},} \\ 0.79^{0.38} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.94^{0.33},} \\ {0.77^{0.36},} \\ 0.56^{0.39} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.90^{0.41},} \\ {0.72^{0.31},} \\ 0.70^{0.51} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.99^{0.30},} \\ {0.91^{0.33},} \\ 0.67^{0.36} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.83^{0.31},} \\ {0.65^{0.34},} \\ 0.98^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.32},} \\ {0.96^{0.35},} \\ 0.69^{0.38} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.86^{0.44},} \\ {0.94^{0.55},} \\ 0.89^{0.66} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.78^{0.18},} \\ {0.88^{0.21},} \\ 0.91^{0.24} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.96^{0.19},} \\ {0.69^{0.22},} \\ 0.82^{0.25} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.77^{0.20},} \\ {0.90^{0.23},} \\ 0.53^{0.26} \end{matrix} \right\rangle \end{pmatrix}.
$$

$$
\mathbf{A}_{\mathbb{D}_{1}}^{{\widetilde{\mathcal{N}}}_{1}} = \begin{pmatrix} 0.24^{0.38} & 0.79^{0.17} & 1.34^{0.1} & 1.43^{0.15} \\ 0.02^{0.72} & 0.99^{0.28} & 0.8^{1.05} & 1.15^{0.3} \\ 0.92^{0.21} & 1.23^{0.27} & 0.5^{0.28} & 1.2^{0.29} \\ 0.91^{0.33} & 0.75^{0.15} & 0.83^{0.16} & 1.14^{0.17} \end{pmatrix}.
$$

$$
\mathbf{B}_{\mathbb{D}_{1}}^{{\widetilde{\mathcal{N}}}_{1}} = \begin{pmatrix} 0.0912 & 0.1343 & 0.134 & 0.2145 \\ 0.0144 & 0.2772 & 0.84 & 0.345 \\ 0.1932 & 0.3321 & 0.14 & 0.348 \\ 0.3003 & 0.1125 & 0.1328 & 0.1938 \end{pmatrix}.
$$

The opinion M D 2 N˜ 2 of second buyer is given as

$$
\begin{pmatrix} \left\langle \begin{matrix} {0.62^{0.32},} \\ {0.78^{0.29},} \\ 0.52^{0.24} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.86^{0.29},} \\ {0.56^{0.32},} \\ 0.59^{0.19} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.89^{0.31},} \\ {0.77^{0.35},} \\ 0.56^{0.29} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.99^{0.29},} \\ {0.81^{0.33},} \\ 0.58^{0.40} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.78^{0.22},} \\ {0.66^{0.16},} \\ 0.67^{0.29} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.86^{0.29},} \\ {0.77^{0.27},} \\ 0.59^{0.29} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.77^{0.36},} \\ {0.86^{0.25},} \\ 0.64^{0.28} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.87^{0.23},} \\ {0.69^{0.26},} \\ 0.68^{0.41} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.88^{0.32},} \\ {0.79^{0.26},} \\ 0.65^{0.42} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.79^{0.27},} \\ {0.99^{0.27},} \\ 0.78^{0.26} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.91^{0.41},} \\ {0.82^{0.42},} \\ 0.79^{0.51} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.83^{0.42},} \\ {0.91^{0.27},} \\ 0.78^{0.29} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.99^{0.34},} \\ {0.86^{0.49},} \\ 0.78^{0.53} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.88^{0.15},} \\ {0.97^{0.51},} \\ 0.70^{0.35} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.99^{0.29},} \\ {0.78^{0.25},} \\ 0.72^{0.35} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.47^{0.45},} \\ {0.59^{0.23},} \\ 0.63^{0.16} \end{matrix} \right\rangle \end{pmatrix}.
$$

$$
\mathbf{A}_{\mathbb{D}_{2}}^{{\widetilde{\mathcal{N}}}_{2}} = \begin{pmatrix} 0.88^{0.37} & 0.82^{0.21} & 1.1^{0.37} & 1.43^{0.15} \\ 0.77^{0.09} & 1.04^{0.27} & 0.99^{0.33} & 1.02^{0.08} \\ 1.02^{0.16} & 1^{0.28} & 1.22^{0.32} & 0.96^{0.40} \\ 1.07^{0.30} & 1.15^{0.31} & 1.05^{0.19} & 0.43^{0.52} \end{pmatrix}.
$$

$$
\mathbf{B}_{\mathbb{D}_{2}}^{{\widetilde{\mathcal{N}}}_{2}} = \begin{pmatrix} 0.3256 & 0.1722 & 0.407 & 0.2145 \\ 0.0693 & 0.2808 & 0.3267 & 0.0816 \\ 0.1632 & 0.28 & 0.3904 & 0.384 \\ 0.321 & 0.3565 & 0.1995 & 0.2236 \end{pmatrix}.
$$

The opinion M D 3 N˜ 3 of third buyer is given as

$$
\begin{pmatrix} \left\langle \begin{matrix} {0.62^{0.22},} \\ {0.76^{0.21},} \\ 0.90^{0.35} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.12},} \\ {0.65^{0.25},} \\ 0.89^{0.21} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.90^{0.14},} \\ {0.78^{0.31},} \\ 0.51^{0.42} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.91^{0.28},} \\ {0.51^{0.13},} \\ 0.44^{0.19} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.72^{0.32},} \\ {0.71^{0.25},} \\ 0.85^{0.37} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.11},} \\ {0.55^{0.24},} \\ 0.88^{0.17} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.43^{0.32},} \\ {0.99^{0.25},} \\ 0.69^{0.41} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.98^{0.14},} \\ {0.87^{0.26},} \\ 0.67^{0.22} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.93^{0.21},} \\ {0.62^{0.32},} \\ 0.65^{0.46} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.89^{0.32},} \\ {0.90^{0.41},} \\ 0.64^{0.26} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.92^{0.11},} \\ {0.85^{0.24},} \\ 0.94^{0.27} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.93^{0.19},} \\ {0.96^{0.45},} \\ 0.73^{0.29} \end{matrix} \right\rangle \\ \left\langle \begin{matrix} {0.96^{0.35},} \\ {0.94^{0.35},} \\ 0.49^{0.36} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.88^{0.24},} \\ {0.69^{0.32},} \\ 0.56^{0.13} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.86^{0.22},} \\ {0.49^{0.32},} \\ 0.25^{0.36} \end{matrix} \right\rangle & \left\langle \begin{matrix} {0.90^{0.20},} \\ {0.68^{0.33},} \\ 0.43^{0.32} \end{matrix} \right\rangle \end{pmatrix}.
$$

$$
\mathbf{A}_{\mathbb{D}_{3}}^{{\widetilde{\mathcal{N}}}_{3}} = \begin{pmatrix} 0.48^{0.08} & 0.69^{0.08} & 1.17^{0.03} & 0.98^{0.22} \\ 0.58^{0.20} & 0.79^{0.18} & 0.73^{0.16} & 1.18^{0.18} \\ 1.1^{0.07} & 1.15^{0.47} & 0.83^{0.08} & 1.26^{0.35} \\ 1.41^{0.34} & 1.01^{0.43} & 1.1^{0.18} & 1.15^{0.21} \end{pmatrix}.
$$

$$
\mathbf{B}_{\mathbb{D}_{3}}^{{\widetilde{\mathcal{N}}}_{3}} = \begin{pmatrix} 0.0384 & 0.0552 & 0.0351 & 0.2156 \\ 0.116 & 0.1422 & 0.1168 & 0.2124 \\ 0.077 & 0.5405 & 0.0664 & 0.441 \\ 0.4794 & 0.4343 & 0.198 & 0.2415 \end{pmatrix}.
$$

(2) Score matrix for three decision makers are:

$$
\mathbf{S}_{\mathbb{D}_{1}}^{{\widetilde{\mathcal{N}}}_{1}} = \begin{pmatrix} 0.574 \\ 1.4766 \\ 1.0423 \\ 0.7394 \end{pmatrix},\,\mathbf{S}_{\mathbb{D}_{2}}^{{\widetilde{\mathcal{N}}}_{2}} = \begin{pmatrix} 1.1193 \\ 0.7584 \\ 1.2176 \\ 1.1006 \end{pmatrix},\,\mathbf{S}_{\mathbb{D}_{3}}^{{\widetilde{\mathcal{N}}}_{3}} = \begin{pmatrix} 0.3443 \\ 0.5874 \\ 1.1249 \\ 1.3532 \end{pmatrix}.
$$

(3) The average matrix:

$$
\mathbf{V}_{\mathbb{D}_{3}}^{{\widetilde{\mathcal{N}}}_{3}} = \begin{pmatrix} 0.6792 \\ 0.9408 \\ 1.1287 \\ 1.0644 \end{pmatrix}.
$$

(4) Note that the value of 1.1287 is the highest value that can be selected from the average matrix. Selecting the highest value from the average matrix of a csvNSS provides a straightforward and fruitful way to make decisions in scenarios characterized by uncertainty and ambiguity. By averaging the csvNSS elements and identifying the maximum value, we can arrive at a clear and robust decision. Moreover, this method accommodates situations where multiple alternatives possess the same maximum average score, offering flexibility in decision-making while ensuring optimal outcomes. The utilization of csvNSS and its associated average matrix represents a valuable tool for handling complex decision problems in real-world applications.

The ranking of sites based on computed scores is presented in Figure 5.

![Figure 5](https://www.tandfonline.com/cms/asset/34463970-b907-4afe-94da-e5c66780e1f3/uaai_a_2375110_f0005_oc.jpg)

**Figure 5.** Ranking of sites.

### Discussion and Comparison

Sifting over the intricacies of uncertainty and indeterminacy-two aspects that can have an enormous influence on the effectiveness and long-term viability of health-related facilities-is necessary for efficient hospital site selection. Numerous factors, including changing healthcare demands, financial markets, legislative developments, and geographical variations, must be taken into consideration while choosing the best location for a hospital. The dynamic nature of healthcare demands and the built-in challenges in forecasting developments in the future are the main causes of uncertainty. On the other hand, indeterminacy results from the intricate relationships among many elements, which makes it difficult to accurately measure their impact on site selection criteria. A thorough strategy is necessary for efficiently handling these risks. Using sophisticated statistical analysis, scenario formulation, and threat assessment techniques, entails modeling probable results and creating adaptable plans that can change as conditions do. Engaging stakeholders-community people, local government representatives, and healthcare professionals, among others-is also essential to obtaining a variety of viewpoints and understandings that support well-informed decision-making. To guarantee that healthcare facilities are strategically positioned to meet the changing requirements of the local population while improving the holistic provision of healthcare, it is important to efficiently handle uncertainty and indeterminacy in hospital site selection. The problem of hospital site selection has been studied by numerous scholars in general, but it has been explored by some writers, such as Pinar and Antmen (Pinar and Antmen 2019), Chatterjee (Chatterjee 2014), Yucesan and Gul (Yucesan and Gul 2020), and Soltani and Marandi (Soltani and Marandi 2011), with integration of MADM approaches and uncertainty. For comparison, these studies are taken into consideration. In Table 2, we have compared our proposed strategy with these references while taking into account their limitations in the areas of uncertainty management, indeterminacy management, vagueness management, hospital site ranking, and MADM. As statistical analysis ensures the validity and dependability of results, validates hypotheses, and offers a strong platform to establish novel solutions and streamline procedures. Therefore, the validity of score values determined in previous section is assessed through statistical analysis as depicted in Table 3. This table depicts that the ranking is consistent for Pythagorean means but this is not the case for measures of dispersion. This research has certain limitations in addition to its benefits. The suggested model can be examined using any actual data because the opinions of the research specialists are regarded as hypothetical. In a similar vein, ANP or FANP techniques can also be used to establish particular weights for expert opinions. Likewise, using additional decision-making techniques such as TOPSIS, VIKOR, and so on can also improve the usefulness of the suggested model. To prevent computational complexity, the suggested framework also restricts the number of sites and parameters chosen for evaluation; yet, it can handle massive data sets by employing sophisticated machine learning and neural network techniques. This model will undoubtedly be helpful in these situations.

**Table 2.** The comparison of the suggested framework with existing ones.

| References                  | Uncertainty management | Indeterminacy management | Vagueness management | Hospital sites ranking | MADM      |
| --------------------------- | ---------------------- | ------------------------ | -------------------- | ---------------------- | --------- |
| Şahin, Ocak, and Top (2019) | Deficient              | Deficient                | Deficient            | Ample                  | Deficient |
| Pinar and Antmen (2019)     | Ample                  | Deficient                | Deficient            | Ample                  | Deficient |
| Chatterjee (2014)           | Ample                  | Deficient                | Deficient            | Ample                  | Deficient |
| Yucesan and Gul (2020)      | Ample                  | Deficient                | Deficient            | Ample                  | Deficient |
| Gul and Guneri, (2021)      | Deficient              | Deficient                | Deficient            | Ample                  | Deficient |
| Soltani and Marandi (2011)  | Ample                  | Deficient                | Deficient            | Ample                  | Ample     |
| Presented Approach          | Ample                  | Ample                    | Ample                | Ample                  | Ample     |

**Table 3.** Statistical analysis of scores.

| Statistical Tool   | ℏ˜ 1   | ℏ˜ 2   | ℏ˜ 3   | ℏ˜ 4   | Ranking                |
| ------------------ | ------ | ------ | ------ | ------ | ---------------------- |
| Arithmetic Mean    | 0.6792 | 0.9408 | 1.1287 | 1.0644 | ℏ˜ 3> ℏ˜ 4> ℏ˜ 2> ℏ˜ 1 |
| Geometric Mean     | 0.6048 | 0.8697 | 1.1260 | 1.0327 | ℏ˜ 3> ℏ˜ 4> ℏ˜ 2> ℏ˜ 1 |
| Harmonic Mean      | 0.5415 | 0.8112 | 1.1237 | 1.0000 | ℏ˜ 3> ℏ˜ 4> ℏ˜ 2> ℏ˜ 1 |
| Standard Deviation | 0.3250 | 0.3852 | 0.0716 | 0.2519 | ℏ˜ 2> ℏ˜ 1> ℏ˜ 4> ℏ˜ 3 |

## Conclusion

The present research has constructed an innovative theoretical framework, called csvNSS, which captures the constraints of both SS and svNS. To allow readers to visualize the concept, explanation of its properties, and certain set operations have been covered. Additionally, the idea has been addressed and applied to the MADM problem using its aggregations, such as the comparison matrix and score function. An algorithm is provided that aims to select a suitable location for a hospital building using recommended aggregations. A fictitious case study has been provided to evaluate the algorithm’s validity. Through structural comparison, the framework’s adaptability has been demonstrated. The integration of csvNSS with machine learning models is one of its future developments, as it may pave the way for new applications of predictive analytic in unpredictable settings. Machine learning models have the potential to yield more precise and dependable predictions by utilizing the advantages of csvNSS in handling ambiguity and uncertainty, particularly in intricate and dynamic systems. The versatility and usefulness of csvNSS can also be demonstrated by extending its application to a range of domains outside hospital site selection. Healthcare, finance, supply chain management, environmental management, and other fields are examples of potential domains. It can also be easier for practitioners to use csvNSS if user-friendly software tools and platforms are developed. To assist users in applying csvNSS in their decision-making processes, these tools should have accessible interfaces, the ability to visualize data, and extensive documentation.

## Ethical Approval

This article does not contain any studies with human participants or animals performed by any of the authors.

## Informed Consent

Informed consent was obtained from all individual participants included in the study.

## Disclosure Statement

No potential conflict of interest was reported by the author(s).

## Data Availability Statement

This study has no associated data.

## Supplemental material

Supplemental data for this article can be accessed online at https://doi.org/10.1080/08839514.2024.2375110

## References (52 total, showing 52)

1. Ak’ram, M., U. Amjad, J. C. R. Alcantud, and G. Santos-García. 2023. Complex fermatean fuzzy N-soft sets: A new hybrid model with applications. Journal of Ambient Intelligence and Humanized Computing 14 (7):8765–28. doi:10.1007/s12652-021-03629-4.
2. Akram, M., F. Wasim, and A. N. Al-Kenani. 2021. A hybrid decision-making approach under complex Pythagorean fuzzy N-soft sets. International Journal of Computational Intelligence Systems 14 (1):1263–91. doi:10.2991/ijcis.d.210331.002.
3. Alamoodi, A. H., O. S. Albahri, A. A. Zaidan, H. A. Alsattar, B. B. Zaidan, and A. S. Albahri. 2023. Hospital selection framework for remote MCD patients based on fuzzy q-rung orthopair environment. Neural Computing and Applications 35 (8):6185–96. doi:10.1007/s00521-022-07998-5.
4. Albahri, A. S., O. S. Albahri, A. A. Zaidan, B. B. Zaidan, M. Ashim, M. A. Alsalem, A. H. Mohsin, K. I. Mohammed, A. H. Alamoodi, O. Enaizan, et al. 2019. Based multiple heterogeneous wearable sensors: A smart real-time health monitoring structured for hospitals distributor. Institute of Electrical and Electronics Engineers Access 7:37269–323. doi:10.1109/ACCESS.2019.2898214.
5. Ali, M., and F. Smarandache. 2017. Complex neutrosophic set. Neural Computing and Applications 28 (7):1817–34. doi:10.1007/s00521-015-2154-y.
6. Alkan, N., and C. Kahraman. 2022. Circular intuitionistic fuzzy TOPSIS method: Pandemic hospital location selection. Journal of Intelligent & Fuzzy Systems 42 (1):295–316. doi:10.3233/JIFS-219193.
7. Alkouri, A., and A. Salleh. 2012. Complex intuitionistic fuzzy sets. AIP Conference Proceedings 1482 (1):464–70. doi:10.1063/1.4757515.
8. Al Mohamed, A. A., S. Al Mohamed, and M. Zino. 2023. Application of fuzzy multicriteria decision-making model in selecting pandemic hospital site. Future Business Journal 9 (1):14. doi:10.1186/s43093-023-00185-5.
9. Al-Qudah, Y., and N. Hassan. 2018. Complex multi-fuzzy soft set: Its entropy and similarity measure. Institute of Electrical and Electronics Engineers Access 6:65002–17. doi:10.1109/ACCESS.2018.2877921.
10. Al-Quran, A., and N. Hassan. 2018. The complex neutrosophic soft expert set and its application in decision making. Journal of Intelligent & Fuzzy Systems 34 (1):569–82. doi:10.3233/JIFS-17806.
11. Al-Sharqi, F., A. G. Ahmad, and A. Al-Quran. 2023. Fuzzy parameterized-interval complex neutrosophic soft sets and their applications under uncertainty. Journal of Intelligent & Fuzzy Systems 44 (1):1453–77. doi:10.3233/JIFS-221579.
12. Arshad, M., A. U. Rahman, and M. Saeed. 2023. An abstract approach to convex and concave sets under refined neutrosophic set environment. Neutrosophic Sets and Systems 53:274–96. doi:10.5281/zenodo.7536029.
13. Asghar, A., K. A. Khan, M. A. Albahar, and A. Alammari. 2023. An optimized multi-attribute decision-making approach to construction supply chain management by using complex picture fuzzy soft set. Peer J Computer Science 9:e1540. doi:10.7717/peerj-cs.1540.
14. Atanassov, K. T. 1986. Intuitionistic fuzzy sets. Fuzzy Sets and Systems 20 (1):87–96. doi:10.1016/S0165-0114(86)80034-3.
15. Boyac, A. Ç., and A. Şişman. 2022. Pandemic hospital site selection: A GIS-based MCDM approach employing Pythagorean fuzzy sets. Environmental Science and Pollution Research 29 (2):1985–97. doi:10.1007/s11356-021-15703-7.
16. Broumi, S., S. Mohanaselvi, T. Witczak, M. Talea, A. Bakali, and F. Smarandache. 2023. Complex fermatean neutrosophic graph and application to decision making. Decision Making: Applications in Management and Engineering 6 (1):474–501. doi:10.31181/dmame24022023b.
17. Çagman, N., S. Enginoglu, and F. Citak. 2011. Fuzzy soft set theory and its applications. Iranian Journal of Fuzzy Systems 8 (3):137–47. doi:10.1016/10.22111/IJFS.2011.292.
18. Chakraborty, S., and A. K. Saha. 2022. Selection of Forklift unit for transport handling using integrated MCDM under neutrosophic environment. Facta Universitatis, Series: Mechanical Engineering. doi:10.22190/FUME220620039C.
19. Chatterjee, D. 2014. Can fuzzy extension of Delphi-analytical hierarchy process improve hospital site selection? International Journal of Intercultural Information Management 4 (2–3):113–28. doi:10.1504/IJIIM.2014.067428.
20. Chen, Z. H., S. P. Wan, and J. Y. Dong. 2022. An efficiency-based interval type-2 fuzzy multi-criteria group decision making for makeshift hospital selection. Applied Soft Computing 115:108243. doi:10.1016/j.asoc.2021.108243.
21. Cuong, B. C. 2014. Picture fuzzy sets. Journal of Computer Science and Cybernetics 30 (4):409–20. doi:10.15625/1813-9663/30/4/5032.
22. Cuong, B. C., and V. Kreinovich. 2013. Picture fuzzy sets-a new concept for computational intelligence problems. 2013 third world congress on information and communication technologies (WICT 2013), 1–6, IEEE, December. doi:10.1109/WICT.2013.7113099.
23. Gul, M., A. F. Guneri, and G. Huang. 2021. Hospital location selection: A systematic literature review on methodologies and applications. Mathematical Problems in Engineering 2021:1–14. doi:10.1155/2021/6682958.
24. Kandasamy, I., W. B. Vasantha, J. M. Obbineni, and F. Smarandache. 2020. Sentiment analysis of tweets using refined neutrosophic sets. Computers in Industry 115:103180. doi:10.1016/j.compind.2019.103180.
25. Khan, W., A. N. İ. S. Saima, S. Z. Song, and J. U. N. Youngbae. 2020. Complex fuzzy soft matrices with applications. Hacettepe Journal of Mathematics and Statistics 49 (2):676–83. doi:10.15672/hujms.588700.
26. Kumar, T., and R. K. Bajaj. 2014. On complex intuitionistic fuzzy soft sets with distance measures and entropies. Journal of Mathematics 2014:1–12. doi:10.1155/2014/972198.
27. Mahmood, T., U. U. Rehman, and Z. Ali. 2021. A novel complex fuzzy N-soft sets and their decision-making algorithm. Complex & Intelligent Systems 7 (5):2255–80. doi:10.1007/s40747-021-00373-2.
28. Mahmood, T., U. U. Rehman, A. Jaleel, J. Ahmmad, and R. Chinram. 2022. Bipolar complex fuzzy soft sets and their applications in decision-making. Mathematics 10 (7):1048. doi:10.3390/math10071048.
29. Maji, P. K. 2013. Neutrosophic soft set. Annals of Fuzzy Mathematics and Informatics 5 (1):157–68.
30. Maji, P. K., R. Biswas, and A. R. Roy. 2001. Intuitionistic fuzzy soft sets. The Journal of Fuzzy Mathematics 9 (3):677–92.
31. Molodtsov, D. 1999. Soft set theory—First results. Computers and Mathematics with Applications 37 (4–5):19–31. doi:10.1016/S0898-1221(99)00056-5.
32. Naseem, A., M. Akram, K. Ullah, and Z. Ali. 2023. Aczel-alsina aggregation operators based on complex single-valued neutrosophic information and their application in decision-making problems. Decision Making Advances 1 (1):86–114. doi:10.31181/dma11202312.
33. Ortiz-Barrios, M., M. Gul, P. López-Meza, M. Yucesan, and E. Navarro-Jiménez. 2020. Evaluation of hospital disaster preparedness by a multi-criteria decision making approach: The case of Turkish hospitals. International Journal of Disaster Risk Reduction 49:101748. doi:10.1016/j.ijdrr.2020.101748.
34. Pinar, M. İ. Ç., and Z. F. Antmen. 2019. A healthcare facility location selection problem with fuzzy TOPSIS method for a regional hospital. Avrupa Bilim ve Teknoloji Dergisi 16:750–57. doi:10.31590/ejosat.584217.
35. Qu, J., A. Nasir, S. U. Khan, K. Nonlaopon, G. Rahman, and R. Aliev. 2022. An innovative decision-making approach based on correlation coefficients of complex picture fuzzy sets and their applications in Cluster Analysis. Computational Intelligence and Neuroscience 2022:1–16. doi:10.1155/2022/7389882.
36. Rahman, A. U., T. Alballa, H. Alqahtani, and H. A. E. W. Khalifa. 2023. A fuzzy parameterized multiattribute decision-making framework for supplier chain management based on picture fuzzy soft information. Symmetry 15 (10):1872. doi:10.3390/sym15101872.
37. Rahman, A. U., M. Arshad, and M. Saeed. 2021. A conceptual framework of convex and concave sets under refined intuitionistic fuzzy set environment. Journal of Prime Research in Mathematics 17 (2):122–37. doi:10.5281/zenodo.6656141.
38. Ramot, D., R. Milo, M. Friedman, and A. Kandel. 2002. Complex fuzzy sets. IEEE Transactions on Fuzzy Systems 10 (2):171–86. doi:10.1109/91.995119.
39. Rasinojehdehi, R., and H. B. Valami. 2023. A comprehensive neutrosophic model for evaluating the efficiency of airlines based on SBM model of network DEA. Decision Making: Applications in Management and Engineering 6 (2):880–906. doi:10.31181/dma622023729.
40. Şahin, T., S. Ocak, and M. Top. 2019. Analytic hierarchy process for hospital site selection. Health Policy and Technology 8 (1):42–50. doi:10.1016/j.hlpt.2019.02.005.
41. Selvachandran, G., and P. K. Singh. 2018. Interval-valued complex fuzzy soft set and its application. International Journal for Uncertainty Quantification 8 (2):101–17. doi:10.1615/Int.J.UncertaintyQuantification.2018020362.
42. Serrano-Guerrero, J., M. Bani-Doumi, F. P. Romero, and J. A. Olivas. 2023. Selecting the best health care systems: An approach based on opinion mining and simplified neutrosophic sets. International Journal on Artificial Intelligence Tools 32 (2):2340007. doi:10.1142/S0218213023400079.
43. Smarandache, F. 2006. Neutrosophic set-a generalization of the intuitionistic fuzzy set. 2006 IEEE international conference on granular computing, Atlanta, GA, USA, 38–42, IEEE. doi:10.1109/GRC.2006.1635754.
44. Smarandache, F., S. Broumi, A. Bakali, M. Talea, M. Ali, and G. Selvachandran. 2017. Complex neutrosophic soft set. 2017 FUZZ-IEEE Conference on Fuzzy Systems, 1, Naples, Italy. July 9–12, 2017. doi:10.5281/zenodo.888849.
45. Soltani, A., and E. Z. Marandi. 2011. Hospital site selection using two-stage fuzzy multi-criteria decision making process. Journal of Urban and Environmental Engineering 5 (1):32–43. doi:10.4090/juee.2011.v5n1.032043.
46. Thirunavukarasu, P., R. Suresh, and V. Ashokkumar. 2017. Theory of complex fuzzy soft set and its applications. International Journal for Innovative Research in Science and Technology 3 (10):13–18.
47. Ulucay, V. 2021. Some concepts on interval-valued refined neutrosophic sets and their applications. Journal of Ambient Intelligence and Humanized Computing 12 (7):7857–72. doi:10.1007/s12652-020-02512-y.
48. Vimala, J., S. S. Begam, M. Saeed, K. A. Khan, and A. U. Rahman. 2023. An abstract context to lattice-based ideals (filters) with multi-fuzzy soft settings. New Mathematics and Natural Computation 1–15. in press. doi:10.1142/S1793005725500024.
49. Vimala, J., P. Mahalakshmi, A. U. Rahman, and M. Saeed. 2023. A customized TOPSIS method to rank the best airlines to fly during COVID-19 pandemic with q-rung orthopair multi-fuzzy soft information. Soft Computing 27 (20):14571–84. doi:10.1007/s00500-023-08976-2.
50. Wang, H., F. Smarandache, Y. Zhang, and R. Sunderraman. 2010. Single valued neutrosophic sets. Review of the Air Force Academy 2010 (1):10–14.
51. Yucesan, M., and M. Gul. 2020. Hospital service quality evaluation: An integrated model based on Pythagorean fuzzy AHP and fuzzy TOPSIS. Soft Computing 24 (5):3237–55. doi:10.1007/s00500-019-04084-2.
52. Zadeh, L. A. 1965. Fuzzy sets. Information & Control 8 (3):338–53. doi:10.1016/S0019-9958(65)90241-X.
