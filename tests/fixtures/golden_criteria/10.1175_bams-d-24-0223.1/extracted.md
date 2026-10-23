---
title: "What Makes a Successful Community Model for Research and Operations? Lessons Learned from WAVEWATCH III®"
authors: "Hendrik L. Tolman"
doi: "10.1175/bams-d-24-0223.1"
source: "ams_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 12417
---

# What Makes a Successful Community Model for Research and Operations? Lessons Learned from WAVEWATCH III®

## Abstract

Physics-based numerical models form the foundation of both scientific research and operational prediction of our environment, including the atmosphere, sea ice, oceans, and more. With the increasing availability of compute resources for researchers and the general public, many such modeling efforts have been or are moving to an open-source and open-science development approach. Some examples of such models and modeling systems in the United States are the National Center for Atmospheric Research’s (NCAR) Weather Research and Forecasting (WRF) and Community Earth System Model (CESM). Similarly, the National Oceanic and Atmospheric Administration (NOAA) is moving to a community Unified Forecast System (UFS) approach for both research and operations. One of the early open-source and open-science environmental models is the WAVEWATCH III<sup>®</sup> (WW3) wind-wave model as originally developed at NOAA. This essay provides a history of this model while extracting lessons learned for community modeling. It presents 16 such lessons, ranging from coding principles to code management to community building and governance. It is expected that most lessons learned are generally applicable to community modeling, with the caveat that the WW3 community is relatively small and that some lessons, as discussed, might not “scale up” to much larger modeling systems and communities.

## 1. Introduction

Physics-based numerical modeling has been the foundation of weather and environmental prediction for almost seven decades. With the rise of high-performance computing (HPC; or “supercomputers”) in the mid- to late 1980s, weather modeling was one of the top applications for HPC. For instance, in 2000 and 2001, the supercomputer used for operations at the Environmental Modeling Center (EMC; then known as NMC) of the National Centers for Environmental Prediction (NCEP) of the National Weather Service (NWS) of the National Oceanographic and Atmospheric Administration (NOAA) was in the top 10 of the top 500 list of the most powerful supercomputers.<sup>[1](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN1)</sup> With access to such resources, and with the difficulty to provide external collaborators with access to these resources due to IT security requirements,<sup>[2](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN2)</sup> it became natural for operational models to be developed internally at operational centers with their internal research partners only.

Since then, operational supercomputers at NOAA have moved down the top 500 list so much that in 2008, they fell out of the top 100. Moreover, with the rapid rise of HPC capability in the Cloud, virtually anyone now has access to HPC resources. With that, potential collaborators outside of NOAA have gained access to the HPC resources needed to collaborate on operational model development. At the same time, external reviews of operations at NOAA started advocating for NOAA to use a broader community to develop its operational modeling systems.

NOAA started looking into a more open development approach by standing up a Unified Modeling Working Group as part of the NOAA Research Council (NRC) in 2016. The report of this group (summarized in [Link et al. 2017](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib16)) advocated for the unification of modeling efforts in NOAA, including the use of community modeling and community models shared by NOAA research and operations. Since then, a series of papers in BAMS have advocated for community modeling in general ([Jacobs 2021](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib13)), have described NOAA’s Earth Prediction Innovation Center (EPIC) to support such a community approach ([Uccellini et al. 2022](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib40)), and have documented early benefits of this approach for accelerating the transition of research to operations ([Alves et al. 2023](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib2)).

Such a community approach is closely linked to a “Unified Modeling” approach across scales and applications as pioneered by the Met Office (e.g., [Brown et al. 2012](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib4)) and as adopted by the World Meteorological Organization (WMO; [Mariotti et al. 2018](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib18)). It is at the core of NOAA’s Unified Forecast System (UFS) strategy as originally documented in [Tolman and Cortinas (2020a](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib36),[b](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib37)), and it is a key element of NOAA’s recently published modeling strategy ([Morgan et al. 2024](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib20)).

Community and open-source modeling has a long history. Successful community coding arguably started with Linus Torvalds’ development of the Linux operating system as well as his initial development of Git to enable team-based open-source software development. Within the NWS, community modeling was greatly influenced by the efforts of the late Paul van Delst and his leadership in managing and developing the Community Radiative Transfer Model (CRTM; e.g., [Van Delst 2008](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib41)). His efforts were crucial for later development of community modeling efforts around the WAVEWATCH III<sup>®</sup> (WW3) wind-wave model and the Hurricane Weather Research and Forecasting (WRF) (HWRF<sup>®</sup>) hurricane model ([Tallapragada 2016](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib25)) as well as its NOAA-funded development projects (e.g., [Hurricane Forecast Improvement Program 2017](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib12)). Other examples of successful community models are NOAA’s MOM6 ocean model (e.g., [Adcroft et al. 2019](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib1)), the Department of Energy’s CICE sea ice model ([Hunke et al. 2020](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib11); [Duvivier and Hunke 2018](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib7)), the well-known National Center for Atmospheric Research (NCAR) WRF ([Skamarock et al. 2021a](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib23)), Model for Prediction Across Scales (MPAS) (e.g., [Skamarock et al. 2012](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib22), [2021b](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib24)), and Community Earth System Model (CESM) models (e.g., [Kay et al. 2015](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib14)).

NOAA used a close collaboration with NCAR through a formal Memorandum of Agreement (MoA) to jointly develop coupled infrastructure for the CESM and the UFS,<sup>[3](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN3)</sup>,<sup>[4](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN4)</sup> and NOAA used the CESM community governance as a starting point for a fledgling UFS governance. Note that the list of community efforts is intended to be illustrative and does not claim to be complete.

In this ecosystem of community models, WW3 has one of the longest histories of community modeling. This model has effectively been a community model since 1999, with its history going back to the start of its development in 1986 and its first publication in 1989 ([Tolman 1989](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib26)). Together with the Simulating Waves Nearshore (SWAN) model ([Booij et al. 1999](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib3); [Ris et al. 1999](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib21)), they are the most widely used wind-wave models, with SWAN focusing more on high-resolution coastal modeling and WW3 more on large-scale applications. Being an internally developed NOAA model, experience gained with WW3 was also material in the decision of NOAA to move toward community modeling based on the UFS, and WW3 is a component model in the UFS.

This essay aims to document how WW3 became a successful community model, both to document its history and to provide lessons learned that can be used as NOAA, the UFS, and many other communities move or have moved to community modeling approaches. Section 2 provides a history of WW3, describing the evolution of the general model, the compute environment in which this happened, and the software architecture and principles developed for it. Section 3 describes how WW3 evolved from being open-source (the code is available to the community) to becoming open science (the community contributes to the code).<sup>[5](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN5)</sup> Effective open science requires a robust intellectual property (IP) protection approach. This is described in section 4. The issues addressed in these sections create the environment to build a community model but do not build the actual community. The building of the community is described in section 5. Finally, the lessons learned are summarized in section 6.

## 2. The history of WAVEWATCH III

### a. The model

WW3 is the third incarnation of the WAVEWATCH model, which started as part of the doctoral research of [Tolman (1990](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib27), [1991a](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib28)). The model was first published in a report in [Tolman (1989)](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib26) and in a journal article in [Tolman (1991b)](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib29). This model was used by Anne Karin Magnuson for her doctoral study ([Magnusson 1993](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib17)) but was otherwise not distributed.

The second incarnation of the model known as WAVEWATCH II was developed at NASA Goddard Space Flight Center (GSFC) in support of the Surface Wave Dynamics Experiment (SWADE; [Weller et al. 1991](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib42)) and is described in [Tolman (1992)](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib30). This incarnation of the model was used by Il-Yu Moon for his doctoral study ([Moon 2005](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib19)) but was otherwise not distributed.

WAVEWATCH III was developed at NOAA as part of a project to overhaul all operational wave modeling at NCEP. NCEP intended to move to third-generation wave models and considered to either use the WAM model (The Wamdi [Group 1988](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib10); [Komen et al. 1994](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib15)) or to build a new model based on the first two WAVEWATCH incarnations. NCEP adopted the latter approach, mainly based on the need for a more flexible software architecture than the one that was at the core of the WAM model at that time. WW3 was shared with the U.S. Navy as model version 1.15 in 1997. Model version 1.18 was released in 1999 as freeware to the general public ([Tolman 1999](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib31)) and was first implemented in NCEP operations a year later ([Tolman et al. 2002](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib38)). WW3 has been under community development ever since, with five more public releases.

### b. The compute environment

The compute environment imposes limitations on computer models and their applications. As the available compute resources dominated the design features of earlier versions of WW3, they will be discussed here.

The first incarnation of the model ([Tolman 1989](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib26), [1991a](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib28)) was developed at Delft University of Technology (DUT) on an International Business Machines (IBM) 3083 mainframe computer. This computer had two computational cores with six MWords of memory, where optionally all memory could be used by a single core.

The second incarnation of the model ([Tolman 1992](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib30)) was developed at GSFC on a Cray X-MP computer. Compared to the computer used at DUT, this removed most of the practical limitations on computer memory but introduced the need to enable vector processing to produce efficient code.

WW3 was initially developed at NOAA on Cray X-MP, Y-MP, C90, and J90 computers. In 1999, NCEP switched to a massively parallel IBM SP machine, which represented NCEP’s first experience with parallel computing. The first release of WW3 ([Tolman 1999](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib31)) included a code that could run either on scalar (vector) hardware or parallel hardware. Around 2008, community input to WW3 accelerated (see section 3). Since then, WW3 has been run using a plethora of hardware and compiler options.

### c. Software architecture

Developing a model like WW3 starts with the selection of its governing equations. Wind waves are described statistically using a deterministic energy or action density spectrum. A spectral component is described with three parameters; typically a wavenumber, a direction (possibly combined in a wavenumber vector), and a frequency. As wind-wave dispersion in such models is described with linear theory, only two of these three are independent, and the wave spectrum becomes two-dimensional, with four ways to define spectral space. This results in four possible versions of the spectral balance equation describing wind-wave evolution (see, for instance, [Tolman and Booij 1998](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib35)).

With the wave spectrum varying in space and time, the wave modeling problem becomes five-dimensional. Efficient algorithms to solve such equations generally use a so-called fractional step method ([Yanenko 1971](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib43)), where the solution in time in each dimension of the model is addressed individually and sequentially. This, in principle, allows for highly modular software architectures and is often more accurate than considering the numerical advance of the solution in multiple dimensions at once (e.g., [Fletcher 1988a](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib8),[b](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib9)).

The first instantiation of the code developed at DUT used a version of the governing equations selected specifically for the intended study ([Tolman 1991a](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib28)). Code design choices were dominated by the need for efficient memory use. The code layout was therefore designed around an algorithm where the solution was obtained by incrementally updating the solution sweeping through physical space ([Tolman 1989](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib26), [1991b](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib29)). Whereas the numerical solution followed the most efficient fractional step approach available, the software architecture did not. This code was written in FORTRAN 77 using COMMON data structures, consistent with best practices of the time.

The second instantiation of the code developed at GSFC used the same governing equations as used in the DUT version. Due to the switch to the Cray hardware, memory use no longer was the main factor driving the basic code design. This allowed for a software architecture strictly based on a fractional step implementation of the governing equations, with a clean separation between model physics and dynamics and between numerical approaches in fractional steps.

The first version of WW3 developed at NOAA moved to a more general version of the governing equations to avoid singularities in the model solutions for the equations used in the previous versions of the model ([Tolman and Booij 1998](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib35)). The highly modular architecture introduced at GSFC was retained. This allowed for a full separation of computations and communications when the model was adapted for parallel compute environments (e.g., [Tolman 2002](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib32)). This feature simplifies scientific development as a developer effectively can ignore parallel communications, as well as associated code optimization. This version of the code also started exploring asynchronous I/O and I/O on dedicated processors.

A key model design feature used in the first version of WW3 developed at NOAA is that the modular code enables the introduction of many options for numerics and physics. Such options are selected when compiling the code rather than at run time. This allows for a compiled code with minimal complexity, which is a preferred feature for obtaining operational reliability and efficiency. It also generally has a positive impact on portability, and it tends to minimize the introduction of bugs and unintended modeling consequences across model options. Note that, in contrast, academic developers may prefer a code with option selection at run time, reducing the need for recompiling the code when changing model options or when performing regression testing.

As of the writing of this essay, the last major rewrite of WW3 occurred for model version 3.14, released in 2009. For this model version, the code was rewritten in free-format FORTRAN 90, and the COMMON data structure was replaced by USE-associated data structures. The new data structure was introduced (i) as a part of general software modernization, (ii) to allow for multiple wave model grids to exist and interact in core, and (iii) to prepare the code for Earth System Modeling Framework (ESMF) style coupling to other environmental models ([Collins et al. 2005](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib5)). This style of coupling exchanges data through a wrapper around existing component models, allowing coupling with minimal impact on the component models themselves.

Since the public release of model version 3.14, the WW3 community has delivered three more public releases. The most recent release is version 6.07 from 2019. A seventh release is being prepared as this essay was going through the review process. Note that the releases are snapshots of a continuous development process of the core code. In releases since version 3.14, the custom code preprocessor that allows for option selection when compiling the code has been replaced by the community *cmake* tool. Apart from that, these more recent upgrades focus on new model options rather than structural code changes.

Note that we are now in a transition period to new hardware architectures moving from CPUs to a CPU–graphics processing unit (GPU) hybrid environment. The WW3 community realizes that this requires a major code modernization. Discussions are ongoing on how to enact this modernization, both with respect to improved efficiency of WW3 by itself and with respect to enabling a move away from a “loose” coupling approach based on ESMF to a “close” coupling approach with more integrated coupled models. Similarly, as models become more accurate and of higher resolution, the level of granularity in fractional stepping is revisited, for instance, in adopting more closely integrated propagation and source terms in WW3. In atmospheric models, similar discussions are ongoing regarding the numerical separation of dynamics and physics.

## 3. From open source to open science

WW3 has been freely available and therefore effectively open-source since 1999. The formal transition to it becoming open-source will be discussed in the following section. The first “freeware” release of model version 1.18 included a mature manual and system documentation ([Tolman 1999](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib31)). Whereas the documentation was intended first and foremost for use by the developer “for his own sanity,” it proved sufficiently complete to result in a large group of users without the need for significant additional support from NOAA/NCEP/EMC. The first 100 requests for code were received within a year after its initial availability.<sup>[6](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN6)</sup>

Whereas this resulted in a large group of users, it did not result in a significant group of contributors because there was no easy way to submit contributions back to EMC. In other words, the model could be considered open-source but not open science. As a first step toward creating an open-science capability, NWS adopted Subversion (svn; [Collins-Sussmann et al. 2004](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib6)) as a software development tool in 2006, using a repository behind the NOAA firewalls. For practical reasons, WW3 adopted svn in 2009 directly after the release of model version 3.14. In 2019, the WW3 code management was moved from svn to Git,<sup>[7](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN7)</sup> and the repositories were moved to GitHub (footnote 8) as part of a systematic transition to GitHub for all operational codes used by the NWS.

The next step in developing open-source tools, techniques, and experience occurred in a National Oceanographic Partnership Program (NOPP) project that focused on transitioning new science into operational wind-wave models ([Tolman et al. 2013](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib39)) which started in 2009. The project included nine funded teams, most of which chose to make their new science available to operations by integrating them as options in WW3. NOAA contributed to this project with EMC providing the collaboration environment (svn) and dedicated WW3 code managers for the duration of the project. Note that the collaboration with a preselected group in this NOPP project did not constitute true open science. It nevertheless provided critical experience enabling true open science.

Apart from the already mentioned benefits of WW3 associated with code modularity, compile-level option selection, and documentation, lessons learned from this project can be divided into three categories: technical approaches, cultural issues, and other (including communications, governance, and funding). The following technical aspects were found to be critical for successful team-based open-science development of WW3 in the NOPP project.

### a. Define and enforce coding standards

A first set of coding standards for WW3 was published in [Tolman (2010)](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib34) as part of the NOPP project. Note that the code at the start of the project was fully compliant with these standards. This enticed contributors to follow these standards naturally for smaller additions to the code. When large and mature packages were added to WW3, coding standards were applied only to subroutines used to interface such packages to WW3.

### b. Automate and enforce regression testing

Historically, WW3 has used functional regression testing instead of more fundamental unit testing. For the NOPP project, the testing was automated and made hierarchical to find a balance between continuous (at least daily) testing and limiting the computation overhead introduced by testing (test what is worked on often, test everything else less frequently). Contributors are responsible for their codes to pass these tests in their test branches before code managers accept such code for integration in the official code. Note that this official code version is in continuous development, whereas formal releases are only done sporadically.

### c. Define and enforce code management

Following experience gained with the CRTM and the NOPP project, WW3 now uses a GitFlow<sup>[8](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN8)</sup> style workflow to develop and collaborate on code. Development branches are created for each development topic (i.e., not for individuals or integrated projects) and are continually synchronized with the baseline code. Code managers do not accept contributions to the trunk of the repository unless the contributors followed this established code management workflow.

### d. Assign an authoritative code manager

The code manager is responsible for merging innovations back into the official code but has the authority to refer any issues encountered in the process back to the associated developer. Having this as a dedicated (funded) position may be the strongest driver for successful community modeling.<sup>[9](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN9)</sup>,<sup>[10](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN10)</sup> The NOPP project used a single repository and a single code manager. Presently, there are several repositories with their own code managers, with the NOAA repository being the authoritative one to which the others are regularly synced by the formal code managers.

### e. Do no harm

If new options are added to the WW3 framework, it is the responsibility of the developer of the new code to “do no harm,” that is, new code is not allowed to break or change<sup>[11](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN11)</sup> the outcome of preexisting model options. Any code upgrade that does not follow this principle needs to be agreed upon by the community. So far, the WW3 community has not had to address issues with “harm” done to the code. The envisioned procedure to deal with such issues is similar to the procedure used when structural changes are proposed at the architecture level of the code. In such cases, consensus has always been reached between the main developers and funders of the code. Note that this do no harm principle becomes important in more complex coupled community modeling efforts like the UFS, as it minimizes the need for changes in one component model to require changes in other component models of such a system.

These experiences gained in the NOPP project have been used by the WW3 community ever since. In our experience, these technical issues have driven the success or failure of a community jointly working on a code more than anything else. However, implementing has been made difficult by cultural issues that the community encountered.

### f. (Perceived) code management overhead

All code managers assigned in the NOPP project, including the present author, feared that the effort in managing the code would take time away from model development work. Contrary to this expectation, all later found that less time spent on debugging and porting WW3 often allowed for more time to do development. This time saving may not be achieved for larger projects, where code management is likely to be more complex and hence more labor intensive. Another real overhead is the need for continuous regression testing, which for WW3 was mitigated by option selection at the compile level of the code and by having a hierarchical regression testing approach as mentioned above.

### g. Resistance to implementing code management workflow principles

Whereas most collaborators in the NOPP project had previous experience with formal code management, most resisted the transition to a GitFlow-based workflow. In particular, all initially resisted having separate branches for each development topic. All collaborators voiced that they should have used this principle earlier once they adopted it, making cultural issues the main roadblock to implement GitFlow in this community.

### h. Taking ownership

A strong point from the start of the NOPP projects was that all groups took full ownership of the options they implemented in the code, including development costs, maintenance, and porting to new releases. This implies, for instance, that grid options used by the U.K. Met Office are fully resourced by them, with minimal direct costs for groups like NOAA who do not use these options. Developing and maintaining shared infrastructure occurs organically and tends to be spread over the community naturally, minimizing effort and maximizing benefits for all in the long run, sometimes with formal agreements as discussed above.

### i. “but it is my code”

For each modeler, it is natural to feel ownership of what they create. This may lead to an unwillingness to share code, for instance, to protect work until credit for it has been established or to protect ideas for future work. This is a potential cultural issue that can prevent modelers from joining a community effort. For the NOPP project, all collaborators already had bought into working in an open-source environment as an effective way of leveraging efforts and making their work available to a broader community.

With the above technical issues driving the success, and the cultural issues potentially derailing an open-science effort, the following topics complete the observations for effective open-science gained with WW3.

### j. Change control meetings

The group of developers of WW3 typically meets monthly to coordinate code mergers and releases. For WW3, these meetings tend to be somewhat informal. Other community models or tools have more formal Change Control Boards. Regular meetings are essential to keep code mergers on track and hence to make this type of community modeling efficient.

### k. Governance

In the experience gained with WW3, the modular design and capability of the model to include many options side by side make the need for governance beyond a potentially informal Change Control Board unnecessary. In contrast, more formal governance is needed for specific applications of a model, e.g., the global wave model at NCEP, or for codes that are not designed as frameworks but as a single “best possible” model such as the Unified Model (UM) of the U.K. Met Office or the IFS of ECMWF.

### l. Funding

The funding mostly provided by the Office of Naval Research of the U.S. Navy for the NOPP project was essential in building the community, as this directly funded collaboration. NOAA now uses a “carrot and stick” approach by directing those who seek NOAA funding for projects to work with community codes, in particular the UFS, where possible. Note that this approach is critically dependent on having a community code that is suitable for research to begin with, and that it requires a properly resourced code manager.

The above open-source and open-science issues are discussed in the context of the experience gained with WW3. In a broader context, the LEGEND<sup>[12](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN12)</sup> Act (15 U.S.C. Section 8512a) of December 2022 directs the NWS to treat their operational software as open-source in general and develop it following open-science principles where possible. Furthermore, in 2024, NOAA published its first-ever modeling strategy ([Morgan et al. 2024](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib20)) and NOAA Administrative Order (NAO) 201-118 “Software Governance and Public Release Policy,”<sup>[13](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN13)</sup> with both NOAA documents being consistent with the LEGEND Act.

## 4. IP protection

After WW3 was initially distributed as freeware, some users appeared to modify and rename the code without proper source recognition. This led EMC to investigate the potential of licensing the model in 2008. At this time, open-source licenses were not yet mature, with effectively only the original GNU Public License available as a standardized license. Discussions with NOAA’s existing partners, in particular the U.K. Met Office, resulted in a custom license which can be found in section 1.2 of [Tolman (2009)](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#bib33). Due to the unique history of the model starting in the Netherlands, and due to the transfer of rights of a government contractor, NWS was able to copyright the code before licensing it. In 2022, the custom license was replaced by the GNU Lesser General Public License (LGPL)<sup>[14](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN14)</sup> for general convenience and as part of preparing UFS codes for formal public release.

While developing the custom license, the model name (WAVEWATCH III) and a designated operational product name (NOAA WAVEWATCH III) were trademarked, both as a general protection strategy protecting rights and NOAA’s and WW3’s “brands,” and in response to previous issues, EMC encountered when model names used by EMC were co-opted by other organizations.

The copyright, license, and trademark development for WW3 as described here are dated, as such approaches have now become mature. NOAA is developing a handbook to be published with the abovementioned NAO to provide practical IP guidance for community models used or developed by NOAA. A main takeaway from this handbook will be that IP issues should be addressed before new code is developed, as this is trivial compared to retrofitting old code with proper IP protection.

With the UFS, NOAA has chosen to address IP protection through open-source licensing. Another approach would be to file patents. Since community model development is incremental, it generally is covered by preexisting licensing regarding each incremental upgrade. Hence, using patents for IP protection in open-source licensed community models is not likely to succeed, and open-source licensing and patenting are effectively orthogonal approaches.

Finally, community modeling with WW3 encountered two “cultural” pushbacks associated with IP protection. The first is associated with researchers wanting to keep their results private until the results are published, and they then use that as an argument not to use code management tools such as svn or GitHub. However, parts of repositories can be kept private, avoiding this issue, and repositories provide verifiable time stamps on submission of code and data well before they are published, which in fact provides some IP protection.

The second issue is the belief that private companies cannot be part of an open-source community while having a viable business model. Whereas we do not claim to be able to dictate business models for private companies, we do recognize the Red Hat business model, where code is given away freely and products and support are monetized, as viable for many private companies in the fields of software development and environmental modeling.

## 5. Community building

The previous sections describe the technical aspects of what made WW3 a successful community model. However, a community model does not make a community. A community requires a critical mass of members who are committed and capable of working together. Making a code open-source may result in many users, but the large majority of such users are not interested in codeveloping the model but are interested in creating products or research by running the model.

The establishment of, in particular, a developer group benefits greatly from active training of developers. For WW3, this started with an introductory single-day short course in 2000 at the WISE meeting in Reykjavik associated with the initial release of WW3 v1.18. Since 2013, mainly to keep the momentum of the NOPP project going, regular week-long summer schools have been held by EMC at the University of Maryland and by the Institut Français de Recherche pour l’Exploitation de la Mer (IFREMER) in Brest.<sup>[15](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN15)</sup> These training opportunities were augmented by another nine one-off training events from 2010 through 2017 in South America, Africa, India, Australia, and Southeast Asia organized through, for instance, capacity-building efforts from the United Nations Educational, Scientific and Cultural Organization (UNESCO) (WMO and JCOMM) and bilateral agreements. This resulted in the training for several hundreds of potential developers of the code. For comparison, in July 2018, there were 2499 unique individuals who downloaded the WW3 code according the svn repository logs.

The broader community of both users and developers includes active researchers and the private sector. Having supported building such a broad community of users and developers has greatly reduced NOAA’s risk associated with operational Continuity of Operations. In case of turnover of NOAA personnel, NOAA can draw from a large pool of well-trained potential successors, unlike with in-house models supported only or mainly by their initial developers.

## 6. Lessons learned

This essay mostly follows the history of WW3 as a community model and is, furthermore, organized by topics. In this summary section, the lessons learned are reorganized without reproducing discussions associated with them, but pointing out where WW3 experiences might not be applicable to other, in particular larger, models or modeling systems.

The experience gained with WW3 suggests that much of the success of a community model suitable for research and operations stands or falls with the following technical issues.

- (i) Use a modular architecture allowing for separations of concern by isolating, for instance, physics, dynamics, numerics, and communication.
- (ii) Based on this architecture, create a portable framework where the corresponding options are selected at compile level, in particular for operational use.
- (iii) Provide a thorough manual and system documentation, including coding standards.
- (iv) Address IP protection ideally before developing the first code, preferably with standard, open-source licensing.<sup>[16](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#FN16)</sup>

Together with these technical issues, the success of a community model is strongly driven by code management principles, in particular with respect to the following best practices.

- Define and strictly enforce a clear development workflow/pipeline,
- an authoritative repository structure,
- extensive unit and/or functional regression testing, and
- an authoritative, dedicated, and funded code manager.
- Define ownership of code; in case of a framework code design, the community needs to jointly own the framework, whereas the ownership of optional physical and numerical approaches is naturally distributed among their developers and users.
- Ownership implies providing the resources needed to develop and maintain the associated part(s) of the model.
- Based on the above ownership principle, code without sustained ownership is removed.
- New code options should follow the “do not harm” principle, unless the broader community provides an exception to this principle.

The above lessons learned address technical principles as well as code management, with the second half of the code management principles bleeding over into governance. The following lessons learned are associated with how a community works together and is established.

- (i) Once the WW3 framework was well established, the do no harm principle for adding options allowed for a fairly informal but regular set of Change Control meetings with active developers to effectively govern general model capability development. Note that this approach may be more difficult to execute for much larger communities.
- (ii) For model applications, a more formal governance process is required, generally including improvement targets, work plans, and the systematic generation of metrics. More formal governance is also needed for models that are not designed as a framework, where capacity and application development are intertwined, or possibly for communities that are much larger than the WW3 community.
- (iii) Funding targeting the development of shared community models strongly supports the building up of its community. Explicit funding requires more formal governance, including prioritization of work. Funding a dedicated code manager may well be the single most important factor for a community to be successful.
- (iv) Finally, training opportunities support and build a community. Note that investment in training results in a bigger community that for practical purposes becomes self-supporting through mailing lists, etc.

After having addressed technical aspects, code management, and governance, this leaves the cultural roadblocks to community modeling identified in this essay.

For completeness, the first cultural roadblock is the “but it is my code” pushback to open-source and open-science modeling. Between the culture change started by Linus Torvalds, the associated “Red Hat” business model for the private sector, and the understanding that code repositories can protect IP for researchers rather than put it at risk, this cultural pushback has almost completely eroded. Nevertheless, open science remains inappropriate for some applications, for instance, for software with national security implications or for software used for regulatory purposes.

A second cultural pushback to effective community modeling that was encountered in the WW3/NOPP community was the initial unwillingness of almost all collaborators to go “all in” on the selected code management workflow. For WW3 in the NOPP project, this proved a true cultural issue; once the old culture was replaced with the new culture, there was little or no willingness to go back to the old way of doing business. It is expected that such a cultural hurdle may be common to those new to community modeling in general. Hence, it is important to address this forthwith in new communities.

A third cultural issue is the objection to the cost overhead that regression testing as part of systematic code management represents. For the relatively small WW3 model and community, this overhead proved manageable and was offset by cost savings associated with an improved code quality and by cost savings associated with the introduction of automated and hierarchical regression testing. For WW3, the cost was exacerbated by choosing options at compile time and the associated need for excessive recompilation during regression testing.

In contrast, NCEP/EMC is presently experiencing that the costs associated with regression testing of large UFS-based coupled systems are becoming prohibitive. Regression testing is expensive as it requires compilation of an entire model and as the number of regression tests tends to increase exponentially with the complexity of the code, in particular as associated with the number of options in the code. Commercial code development approaches avoid such costs by introducing so-called unit testing of small parts of the code individually. Unit testing is cheap compared to regression testing as the number of tests grows linearly with the size of code and as individual tests only consider a small subset of the full code to be compiled and run in each test. Environmental community modeling would benefit greatly from adopting the unit-testing industry standard rapidly, even if initial code refactoring costs may look to be substantial.

This third cultural issue highlights that findings presented in this essay may be well established for a relatively small community like the WW3 community, but that we do not have the data to show that (all) these findings scale up to much larger modeling systems and communities.

Last but not least, this essay highlights lessons learned, which does not mean that they are presently fully implemented in WW3. For instance, after the NOPP project, the WW3 community has struggled with resourcing code management and enforcing coding standards, and after COVID, community training has not yet been fully reestablished. This identifies a concluding cultural issue that there is a need to stay committed to these principles which inherently requires explicit dedicated resources and a “champion” for each community code.

## Footnotes

<sup>[1](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN1)</sup> [https://www.top500.org](https://www.top500.org).

<sup>[2](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN2)</sup> In particular after the 9/11 terrorist attacks, after which these computers were designated as critical national assets.

<sup>[3](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN3)</sup> [https://www.noaa.gov/media-release/noaa-and-ncar-partner-on-new-state-of-art-us-modeling-framework](https://www.noaa.gov/media-release/noaa-and-ncar-partner-on-new-state-of-art-us-modeling-framework).

<sup>[4](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN4)</sup> [https://dtcenter.org/news/2019/02/noaa-ncar-partner-new-modeling-framework](https://dtcenter.org/news/2019/02/noaa-ncar-partner-new-modeling-framework).

<sup>[5](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN5)</sup> The terms open-source and open-development are considered exchangeable in this essay.

<sup>[6](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN6)</sup> Exact numbers are no longer available due to the loss of the associated mail archive when NOAA moved its email to the Google Suite.

<sup>[7](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN7)</sup> [https://git-scm.com/docs](https://git-scm.com/docs).

<sup>[8](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN8)</sup> [https://docs.github.com/en/get-started/using-github/github-flow](https://docs.github.com/en/get-started/using-github/github-flow).

<sup>[9](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN9)</sup> This was confirmed as NOAA funding for a code manager for CICE as it transitioned to open science was generally identified as a key aspect of an effective transition.

<sup>[10](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN10)</sup> This was also confirmed when the present lack of a dedicated code manager appears to hamstring community development.

<sup>[11](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN11)</sup> Ideally, bit-by-bit reproducibility is achieved. This is only possible on identical hardware and with identical compilers that do not rewrite the code, i.e., without optimization turned on. Thus, bit-by-bit reproducibility is accepted, whereas minor differences may be acceptable upon detailed, usually statistical, analysis; see, e.g., a recent workshop on this topic at [https://ncar.github.io/correctness-workshop/](https://ncar.github.io/correctness-workshop/).

<sup>[12](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN12)</sup> Section 10601: Learning Excellence and Good Examples from New Developers.

<sup>[13](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN13)</sup> [https://www.noaa.gov/administration/nao-201-118-software-governance-and-public-release-policy](https://www.noaa.gov/administration/nao-201-118-software-governance-and-public-release-policy).

<sup>[14](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN14)</sup> [https://github.com/NOAA-EMC/WW3/blob/develop/LICENSE.md](https://github.com/NOAA-EMC/WW3/blob/develop/LICENSE.md).

<sup>[15](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN15)</sup> Both have been disrupted by COVID-19 in-person meeting restrictions.

<sup>[16](https://journals.ametsoc.org/view/journals/bams/107/5/BAMS-D-24-0223.1.xml#ref_FN16)</sup> The preference of open-source licensing over patents may not be supported by some modeling communities but is preferred by the WW3 and UFS modeling communities.

## Acknowledgments

Most of the experiences described in this essay were gained while the author worked at the Environmental Modeling Center (EMC) of NOAA/NWS, supported by NOAA Software Engineering for Novel Architectures (SENA) and EMC base funding. The author would like to thank the broad wind-wave modeling community for four decades of interaction and communication, with a special thanks to the original code managers of WW3 in the NOPP project and their successors, in particular (in alphabetic order) Jose-Henrique Alves, Arun Chawla, Jessica Meixner, and Andre van der Westhuysen, who also all reviewed drafts of this essay. Finally, the author would also like to extend a special thanks to his thesis co-advisors Leo Holthuijsen and Nico Booij for their life-long support and friendship and Klaus Hasselmann for always supporting him as “the guy with that other wave model” in the WAM group and beyond.

## Data availability statement

There are no new or unpublished data used in this essay.

## References (43 total, showing 43)

- Adcroft, A., and Coauthors, 2019: The GFDL global ocean and sea ice model OM4.0: Model description and simulation features. <em>J. Adv. Model. Earth Syst.</em>, **11**, 3167–3211, https://doi.org/10.1029/2019MS001726.

- Alves, J.-H., H. Tolman, A. Roland, A. Abdolali, F. Ardhuin, G. Mann, A. Chawla, and J. Smith, 2023: NOAA’s Great Lakes wave prediction system: A successful framework for accelerating the transition of innovations to operations. <em>Bull. Amer. Meteor. Soc.</em>, **104**, E837–E850, https://doi.org/10.1175/BAMS-D-22-0094.1.

- Booij, N., R. C. Ris, and L. H. Holthuijsen, 1999: A third‐generation wave model for coastal regions: 1. Model description and validation. <em>J. Geophys. Res.</em>, **104**, 7649–7666, https://doi.org/10.1029/98JC02622.

- Brown, A., S. Milton, M. Cullen, B. Golding, J. Mitchell, and A. Shelly, 2012: Unified modeling and prediction of weather and climate: A 25-year journey. <em>Bull. Amer. Meteor. Soc.</em>, **93**, 1865–1877, https://doi.org/10.1175/BAMS-D-12-00018.1.

- Collins, N., and Coauthors, 2005: Design and implementation of components in the Earth System Modeling Framework. <em>Int. J. High Perform. Comput. Appl.</em>, **19**, 341–350, https://doi.org/10.1177/1094342005056120.

- Collins-Sussmann, B., B. W. Fitzpatrick, and C. M. Pilato, 2004: <em>Version Control with Subversion.</em> O’Reilly, 320 pp.

- Duvivier, A., and E. Hunke, 2018: Community-driven sea ice modeling with the CICE consortium. Witness Community Highlights, Arctic Research Consortium of the United States, https://www.arcus.org/witness-the-arctic/2018/5/highlight/1.

- Fletcher, C. A. J., 1988a: <em>Computational Techniques for Fluid Dynamics, Part I.</em> Springer, 409 pp.

- Fletcher, C. A. J., 1988b: <em>Computational Techniques for Fluid Dynamics, Part II.</em> Springer, 484 pp.

- Hunke, E., and Coauthors, 2020: Should sea-ice modeling tools designed for climate research be used for short-term forecasting? <em>Curr. Climate Change Rep.</em>, **6**, 121–136, https://doi.org/10.1007/s40641-020-00162-y.

- Hurricane Forecast Improvement Program, 2017: 2016 R&D activities summary; recent results and operational implementations. HFIP Tech. Rep. HFIP2017-1, NOAA, 49 pp.

- Jacobs, N. A., 2021: Open innovation and the case for community model development. <em>Bull. Amer. Meteor. Soc.</em>, **102**, E2002–E2011, https://doi.org/10.1175/BAMS-D-21-0030.1.

- Kay, J. E., and Coauthors, 2015: The Community Earth System Model (CESM) large ensemble project: A community resource for studying climate change in the presence of internal climate variability. <em>Bull. Amer. Meteor. Soc.</em>, **96**, 1333–1349, https://doi.org/10.1175/BAMS-D-13-00255.1.

- Komen, G. J., L. Cavaleri, M. Donelan, K. Hasselmann, S. Hasselmann, and P. A. E. M. Janssen, 1994: <em>Dynamics and Modelling of Ocean Waves.</em> Cambridge University Press, 532 pp.

- Link, J., H. L. Tolman, and K. Robinson, 2017: Earth systems: NOAA’s strategy for unified modelling. <em>Nature</em>, **549**, 458, https://doi.org/10.1038/549458b.

- Magnusson, A. K., 1993: Modelling wave-current interactions. Ph.D. thesis, Geophysical Institute, University of Bergen.

- Mariotti, A., P. M. Rutti, and M. Rixen, 2018: Progress in subseasonal to seasonal prediction through a joint weather and climate community effort. <em>npj Climate Atmos. Sci.</em>, **1**, 4, https://doi.org/10.1038/s41612-018-0014-z.

- Moon, I. J., 2005: Impact of a coupled ocean wave–tide–circulation system on coastal modeling. <em>Ocean Modell.</em>, **8**, 203–236, https://doi.org/10.1016/j.ocemod.2004.02.001.

- Morgan, M., and Coauthors, 2024: NOAA Modeling Strategy: Strategic plan 2024-2033. National Oceanic and Atmospheric Administration, 22 pp., https://doi.org/10.25923/qggz-jb43.

- Ris, R. C., L. H. Holthuijsen, and N. Booij, 1999: A third-generation wave model for coastal regions, 2. Verification. <em>J. Geophys. Res.</em>, **104**, 7667–7681, https://doi.org/10.1029/1998JC900123.

- Skamarock, W. C., J. B. Klemp, M. G. Duda, L. Fowler, S.-H. Park, and T. D. Ringler, 2012: A multiscale nonhydrostatic atmospheric model using centroidal Voronoi tesselations and C-grid staggering. <em>Mon. Wea. Rev.</em>, **140**, 3090–3105, https://doi.org/10.1175/MWR-D-11-00215.1.

- Skamarock, W. C., J. B. Klemp, J. Dudhia, D. O. Gill, Z. Liu, J. Berner, and X. Y. Huang, 2021a: A description of the Advanced Research WRF version 4.3. University Corporation for Atmospheric Research Rep. NCAR/TN-556+STR, 165 pp., https://doi.org/10.5065/1dfh-6p97.

- Skamarock, W. C., H. Ong, and J. B. Klemp, 2021b: A fully compressible nonhydrostatic deep-atmosphere equations solver for MPAS. <em>Mon. Wea. Rev.</em>, **149**, 571–583, https://doi.org/10.1175/MWR-D-20-0286.1.

- Tallapragada, V., 2016: Overview of the NOAA/NCEP operational Hurricane Weather Research and Forecasting (HWRF) modeling system. <em>Advanced Numerical Modeling and Data Assimilation Techniques for Tropical Cyclone Prediction</em>, U. C. Mohanty and G. Gopolakrishnan, Eds., Springer, 51–106.

- The Wamdi Group, 1988: The WAM model—A third generation ocean wave prediction model. <em>J. Phys. Oceanogr.</em>, **18**, 1775–1810, https://doi.org/10.1175/1520-0485(1988)018<1775:TWMTGO&gt;2.0.CO;2.

- Tolman, H. L., 1989: The numerical model WAVEWATCH: A third generation model for the hindcasting of wind waves on tides in shelf seas. Communications on Hydraulic and Geotechnical Engineering 89-2, Delft University of Technology, 72 pp., https://library.metoffice.gov.uk/portal/Default/en-GB/RecordView/Index/176340.

- Tolman, H. L., 1990: Wind wave propagation in tidal seas. Ph.D. thesis, Delft University of Technology, 195 pp.

- Tolman, H. L., 1991a: Effects of tides and storm surges on North Sea wind waves. <em>J. Phys. Oceanogr.</em>, **21**, 766–781, https://doi.org/10.1175/1520-0485(1991)021<0766:EOTASS&gt;2.0.CO;2.

- Tolman, H. L., 1991b: A third-generation model for wind waves on slowly varying, unsteady, and inhomogeneous depths and currents. <em>J. Phys. Oceanogr.</em>, **21**, 782–797, https://doi.org/10.1175/1520-0485(1991)021<0782:ATGMFW&gt;2.0.CO;2.

- Tolman, H. L., 1992: Effects of numerics on the physics in a third-generation wind-wave model. <em>J. Phys. Oceanogr.</em>, **22**, 1095–1111, https://doi.org/10.1175/1520-0485(1992)022<1095:EONOTP&gt;2.0.CO;2.

- Tolman, H. L., 1999: User manual and system documentation of WAVEWATCH III version 1.18. NOAA/NWS/NCEP/OMB Tech. Note 166, 110 pp.

- Tolman, H. L., 2002: Distributed-memory concepts in the wave model WAVEWATCH III. <em>Parallel Comput.</em>, **28**, 35–52, https://doi.org/10.1016/S0167-8191(01)00130-2.

- Tolman, H. L., 2009: User manual and system documentation of WAVEWATCH III version 3.14. NOAA/NWS/NCEP/MMAB Tech. Note 276, 194 pp.

- Tolman, H. L., 2010: WAVEWATCH III <sup>®</sup> development best practices. Version 0.1. NOAA/NWS/NCEP/MMAB Tech. Note 286, 19 pp.

- Tolman, H. L., and N. Booij, 1998: Modeling wind waves using wavenumber-direction spectra and a variable wavenumber grid. <em>Global Atmos. Ocean Syst.</em>, **6**, 295–309.

- Tolman, H. L., and J. Cortinas, 2020a: 2017-2018 roadmap for the production suite at NCEP. NOAA Rep., 69 pp., https://doi.org/10.25923/kr4a-zy63.

- Tolman, H. L., and J. Cortinas, 2020b: A strategic vision for NOAA’s Physical Environmental Modeling Enterprise. NOAA Rep., 9 pp., https://doi.org/10.25923/0rac-9017.

- Tolman, H. L., B. Balasubramaniyan, L. D. Burroughs, D. V. Chalikov, Y. Y. Chao, H. S. Chen, and V. M. Gerald, 2002: Development and implementation of wind-generated ocean surface wave models NCEP. <em>Wea. Forecasting</em>, **17**, 311–333, https://doi.org/10.1175/1520-0434(2002)017<0311:DAIOWG&gt;2.0.CO;2.

- Tolman, H. L., M. L. Banner, and J. M. Kaihatu, 2013: The NOPP operational wave model improvement project. <em>Ocean Modell</em>, **70**, 2–10, https://doi.org/10.1016/j.ocemod.2012.11.011.

- Uccellini, L. W., R. W. Spinrad, D. M. Koch, C. N. McLean, and W. M. Lapenta, 2022: EPIC as a catalyst for NOAA’s future Earth prediction system. <em>Bull. Amer. Meteor. Soc.</em>, **103**, E2246–E2264, https://doi.org/10.1175/BAMS-D-21-0061.1.

- Van Delst, P., 2008: CRTM: Fortran95 coding guidelines. Joint Center for Satellite Data Assimilation Tech. Rep., 8 pp.

- Weller, R., M. Donelan, M. Briscoe, and N. Huang, 1991: Riding the crest: A tale of two wave experiments. <em>Bull. Amer. Meteor. Soc.</em>, **72**, 163–183, https://doi.org/10.1175/1520-0477(1991)072<0163:RTCATO&gt;2.0.CO;2.

- Yanenko, N. N., 1971: <em>The Method of Fractional Steps.</em> Springer, 160 pp.
