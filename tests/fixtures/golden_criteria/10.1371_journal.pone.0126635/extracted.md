---
title: "A Generalized Simplest Equation Method and Its Application to the Boussinesq-Burgers Equation"
authors: "Bilige Sudao, Xiaomin Wang"
journal: "PLOS ONE"
doi: "10.1371/journal.pone.0126635"
published: "2015"
source: "plos_xml"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 8927
---

# A Generalized Simplest Equation Method and Its Application to the Boussinesq-Burgers Equation

## Abstract

In this paper, a generalized simplest equation method is proposed to seek exact solutions of nonlinear evolution equations (NLEEs). In the method, we chose a solution expression with a variable coefficient and a variable coefficient ordinary differential auxiliary equation. This method can yield a B<em>ä</em>cklund transformation between NLEEs and a related constraint equation. By dealing with the constraint equation, we can derive infinite number of exact solutions for NLEEs. These solutions include the traveling wave solutions, non-traveling wave solutions, multi-soliton solutions, rational solutions, and other types of solutions. As applications, we obtained wide classes of exact solutions for the Boussinesq-Burgers equation by using the generalized simplest equation method.

## 1 Introduction

It is important to seek more exact solutions of nonlinear evolution equations (NLEEs) in mathematical physics. In past decades, many powerful methods have been presented such as the inverse scattering method \[1\], the Darboux transformation \[2\], the Hirota bilinear method \[3\], the Painlevé expansion method \[4\], the Bäcklund transformation method \[5, 6\], the multilinear variable separation method \[7\], the homogeneous balance method \[8\], the Jacobi elliptic function expansion method \[9\], the tanh-function method \[10, 11\], the F-expansion method \[12\], the auxiliary equation method \[13\], the sub-ODE method \[14\], the Exp-function method \[15\], the (*G*′/*G*)-expansion method \[16, 17\], the simplest equation method \[18, 19\]. Thousands of examples have shown that these methods are powerful for obtaining exact solutions of NLEEs, especially, for traveling wave solutions. Up to now, a unified method that can be used to deal with all types of NLEEs has not been discovered. Hence, developing new method and finding more general exact solutions of NLEEs have drawn a lot of interests of a diverse group of scientists.

Particularly, N.A. Kudryashov first proposed the simplest equation method and showed that it is powerful for finding analytic solutions of NLEEs \[18, 19\]. Two basic ideas are at the heart of the approach. The first idea is to apply the simplest nonlinear differential equations (the Riccati equation, the equation for the Jacobi elliptic faction, the equation for the Weierstrass ellipic function and so on) that have lesser order than the equation studied. The second idea is to use possible singularities of general solution for the equation studied. Recently, there are many applications and generalizations of the method \[20–25\].

In the present paper, based on a solution expression with a variable coefficient and variable coefficient auxiliary equation (a special simplest nonlinear differential equation), we proposed a generalized simplest equation method to seek exact solutions of NLEEs. This method can yield infinite number of exact solutions of NLEEs. For illustration, we apply this method to the Boussinesq-Burgers equation and successfully find many different types of exact solutions. These solutions include traveling wave solutions, non-traveling wave solutions, multi-soliton solutions, rational solutions and other types of solutions.

The rest of the paper is organized as follows. In Section 2, we describe the generalized simplest equation method to look for exact solutions of NLEEs. In Section 3, we firstly construct the most general form exact solutions and the exact traveling wave solutions of the Boussinesq-Burgers equation by using our method. Secondly, we obtain the Bäcklund transformation between the Boussinesq-Burgers equation and the constraint equation. Thirdly, we give some concrete new exact solutions of the Boussinesq-Burgers equation. In Section 4, we give some discussions and conclusion remarks.

## 2 Description of the generalized simplest equation method

We consider a nonlinear evolution equation (NLEE)

(1)

$$
\begin{array}{r} {P\left(u,u_{t},u_{x},u_{tx},u_{tt},u_{xx},\cdots \right) = 0,} \end{array}
$$

where *u* = *u*(*t*, *x*) is an unknown function, *t*, *x* are two independent variables, *P* is a polynomial in *u* and its various partial derivatives.

We consider a generalized simplest equation method for obtaining exact solutions to the given NLEE Eq (1), which is described in the following five steps.

**Step 1**. Suppose that the solutions for Eq (1) can be expressed in the following general form

(2)

$$
\begin{array}{r} {u(t,x) = \sum\limits_{i = 0}^{M}\alpha_{i}(t,x)\phi^{i}(\xi),} \end{array}
$$

where *α*<sub>*i*</sub>(*t*, *x*)(*i* = 0, 1, ⋯, *M*) and *ξ* = *ξ*(*t*, *x*) are all functions of *t*, *x* to be determined later, *ϕ* = *ϕ*(*ξ*) satisfies our auxiliary equation (a first order ordinary differential equation (ODE) with variable coefficients):

(3)

$$
\begin{array}{r} {\xi^{2}\left(\phi' + \phi^{2} \right) + \delta\xi\phi + \nu = 0.} \end{array}
$$

It has three types of general solution as follows

(4)

$$
\begin{array}{ccl} & & {\phi_{1}(\xi) = \varepsilon \cdot \frac{\left\lbrack(1 - \delta)c_{1} - 2\eta c_{2} \right\rbrack\sin \left(\eta\ln  \middle| \xi \middle| \right) + \left\lbrack 2\eta c_{1} + (1 - \delta)c_{2} \right\rbrack\cos \left(\eta\ln  \middle| \xi \middle| \right)}{2\xi\left\lbrack c_{1}{\sin \left(\eta\ln  \middle| \xi \right|} + c_{2}\cos \left(\eta\ln  \middle| \xi \middle| \right) \right\rbrack};\hspace{19.34766pt}\mathrm{if}\hspace{4pt}s > 1} \end{array}
$$

(5)

$$
\begin{array}{ccl} & & {\phi_{2}(\xi) = \varepsilon \cdot \frac{c_{1}(2\eta - \delta + 1)|\xi|^{2\eta} - c_{2}(2\eta + \delta - 1)}{\left. 2 \middle| \xi \right|\left(c_{1}|\xi|^{2\eta} + c_{2} \right)};\hspace{127.75302pt}\mathrm{if}\hspace{4pt}s < 1} \end{array}
$$

(6)

$$
\begin{array}{ccl} & & {\phi_{3}(\xi) = \varepsilon \cdot \frac{{(1 - \delta)(}c_{1} + c_{2}{\ln \left| \xi \middle| \right)} + 2c_{2}}{2\xi\left(c_{1} + c_{2}\ln |\xi| \right)},\hspace{166.44879pt}\mathrm{if}\hspace{4pt}s = 1} \end{array}
$$

and

(7)

$$
\begin{array}{r} {\varepsilon = \{\begin{array}{l} {\hspace{4pt}\hspace{4pt}1,\hspace{4pt}\hspace{4pt}\hspace{4pt}\hspace{4pt}\hspace{4pt}\text{if}\hspace{4pt}\hspace{4pt}\xi > 0,} \\ {- 1,\hspace{4pt}\hspace{4pt}\hspace{4pt}\hspace{4pt}\hspace{4pt}\text{if}\hspace{4pt}\hspace{4pt}\xi < 0,} \end{array}\operatorname{}} \end{array}
$$

where *c*<sub>1</sub>, *c*<sub>2</sub>, *δ*, *ν* are constants and

$$
s = 2\delta - \delta^{2} + 4\nu,\hspace{4pt}\eta = \frac{1}{2}|1 - s|^{1/2}.
$$

**Step 2**. The positive number *M* can be determined by considering the homogeneous balance between the highest order derivatives and nonlinear terms appearing in Eq (1).

**Step 3**. By substituting Eq (2) into Eq (1) and using Eq (3), collecting all terms with the same order of *ϕ* together, the left-hand side of Eq (1) is converted into another polynomial in *ϕ*. Equating each coefficient of powers of *ϕ* to zero, yields a set of over-determined partial differential equations for *α*<sub>*i*</sub>(*t*, *x*)(*i* = 0, 1, ⋯, *M*) and *ξ*(*t*, *x*).

**Step 4**. By solving the system of over-determined partial differential equations in Step 3, we obtain *α*<sub>*i*</sub>(*t*, *x*)(*i* = 0, 1, ⋯, *M*) and *ξ*(*t*, *x*).

**Step 5**. By substituting *α*<sub>*i*</sub>(*t*, *x*)(*i* = 0, 1, ⋯, *M*), *ξ*(*t*, *x*) and the general solutions Eqs (4), (5) and (6) of Eq (3) into Eq (2), we can obtain more exact solutions of the Eq (1).

**Remark 1**: The solution expression Eq (2) with functions *α*<sub>*i*</sub>(*t*, *x*)(*i* = 0, 1, ⋯, *M*) and *ξ*(*t*, *x*) can yield more general form exact solutions rather than just traveling wave solutions.

**Remark 2**: It is the first time that Eq (3) is used as an auxiliary equation for obtaining exact solutions of NLEEs.

**Remark 3**: It is emphasized that in our designs Eqs (2) and (3), the parameters *δ*, *ν* will play the role of adjusters in solving the constraint equation and in obtaining a transformation between Eq (1) and linear heat equation (see Section 3).

## 3 Application of the Method

### The exact solutions to the Boussinesq-Burgers equation

In this section, we are aimed to first give the most general form exact solutions, then we will determine the exact traveling wave and non-traveling wave solutions for the Boussinesq-Burgers equation \[26–32\]

(8)

$$
\begin{array}{r} {u_{t} + 2uu_{x} - \frac{1}{2}v_{x} = 0,} \end{array}
$$

(9)

$$
\begin{array}{r} {v_{t} + 2(uv)_{x} - \frac{1}{2}u_{xxx} = 0.} \end{array}
$$

#### The general form exact solutions

In the subsection, we solve the most general form exact solutions of Eqs (8) and (9).

**Step 1**. The solution expressions of Eqs (8) and (9) are taken as Eq (2).

**Step 2**. Considering the homogeneous balance between the highest order derivatives *v*<sub>*x*</sub>(*u*<sub>*xxx*</sub>) and nonlinear terms *uu*<sub>*x*</sub>(*uv*<sub>*x*</sub>) in Eqs (8) and (9), we get balance numbers *M* = 1 for *u* and *N* = 2 for *v*. Thus, we can denote the solutions of Eqs (8) and (9) in the form

(10)

$$
\begin{array}{r} {u(t,x) = a_{0}(t,x) + a_{1}(t,x)\phi(\xi),} \end{array}
$$

(11)

$$
\begin{array}{r} {v(t,x) = b_{0}(t,x) + b_{1}(t,x)\phi(\xi) + b_{2}(t,x)\phi^{2}(\xi),} \end{array}
$$

where functions *a*<sub>0</sub>(*t*, *x*), *a*<sub>1</sub>(*t*, *x*), *b*<sub>0</sub>(*t*, *x*), *b*<sub>1</sub>(*t*, *x*), *b*<sub>2</sub>(*t*, *x*) and *ξ* = *ξ*(*t*, *x*) are to be determined later and *ϕ* = *ϕ*(*ξ*) satisfies Eq (3).

**Step 3**. We substitute Eqs (10) and (11) along with the auxiliary Eq (3) into Eqs (8) and (9) and collect all terms with the same order of *ϕ*. As a result, the left-hand sides of Eqs (8) and (9) are converted into another polynomials in *ϕ*. Equating each coefficient of powers of *ϕ* to zero, we obtain a set of over-determined partial differential equations for *a*<sub>0</sub>(*t*, *x*), *a*<sub>1</sub>(*t*, *x*), *b*<sub>0</sub>(*t*, *x*), *b*<sub>1</sub>(*t*, *x*), *b*<sub>2</sub>(*t*, *x*) and *ξ*(*t*, *x*).

**Remark 4**: Unlike *pure* algebraic equations used in the standard auxiliary method, here we obtain differential equations for *a*<sub>*i*</sub>(*t*, *x*), *b*<sub>*j*</sub>(*t*, *x*) and *ξ*(*t*, *x*). This provides us with more general types of exact solutions to Eqs (8) and (9).

**Step 4**. Solving the differential system obtained in Step 3 by Mathematica, we obtain *a*<sub>0</sub>(*t*, *x*), *a*<sub>1</sub>(*t*, *x*), *b*<sub>0</sub>(*t*, *x*), *b*<sub>1</sub>(*t*, *x*), *b*<sub>2</sub>(*t*, *x*) expressed by *ξ*(*t*, *x*) and *δ*, *ν* as follows:

(12)

$$
\begin{array}{rcl} {a_{0}(t,x)} & = & {\frac{\xi\left(\mp \xi_{xx} - 2\xi_{t} \right) \pm \delta\xi_{x}^{2}}{4\xi\xi_{x}},\hspace{4pt}a_{1}(t,x) = \pm \frac{1}{2}\xi_{x},} \\ {b_{0}(t,x)} & = & {\frac{(\delta + 2\nu)\xi_{x}^{4} - \delta\xi\xi_{x}^{2}\xi_{xx} - \xi^{2}\xi_{xx}\left(\xi_{xx} \pm 2\xi_{t} \right) + \xi^{2}\xi_{x}\left(\xi_{xxx} \pm 2\xi_{xt} \right)}{4\xi^{2}\xi_{x}^{2}},} \\ {b_{1}(t,x)} & = & {\frac{\delta\xi_{x}^{2} - \xi\xi_{xx}}{2\xi},\hspace{4pt}b_{2}(t,x) = \frac{1}{2}\xi_{x}^{2},} \end{array}
$$

where *ξ* = *ξ*(*t*, *x*) satisfies the equation

(13)

$$
\begin{array}{ccl} & & {s\left(\xi\xi_{xx} - \xi_{x}^{2} \right)\xi_{x}^{4} + \xi^{3}\lbrack\left(\xi_{xxxx} \pm 4\xi_{txx} + 4\xi_{tt} \right)\xi_{x}^{2} + 4\left(\mp \xi_{xx} - \xi_{t} \right)\left(2\xi_{tx} \pm \xi_{xxx} \right)\xi_{x}} \\ & & {\hspace{1em} + \left(4\xi_{t}^{2} + 3\xi_{xx}^{2} \pm 8\xi_{t}\xi_{xx} \right)\xi_{xx}{\rbrack = 0.}} \end{array}
$$

Eq (13) is called **the constraint equation** of *ξ*.

Here for obtaining more general types of solutions, we consider the case of *ξ*<sub>*x*</sub> ≠ 0. Any solution of the constraint Eq (13) leads to a group of coefficients Eq (12) which together with Eqs (4)–(6) result in three classes of exact solutions Eqs (10) and (11) of Eqs (8) and (9) as follows:

(14)

$$
\begin{array}{r} {\{\begin{array}{l} {u_{i}(t,x) = a_{0}(t,x) + a_{1}(t,x)\phi_{i}(\xi),} \\ {v_{i}(t,x) = b_{0}(t,x) + b_{1}(t,x)\phi_{i}(\xi) + b_{2}(t,x)\phi_{i}^{2}(\xi),} \end{array}\operatorname{}} \end{array}
$$

in which *i* = 1 for *s* &gt; 1, *i* = 2 for *s* < 1 and *i* = 3 for *s* = 1.

Therefore, the solution expressions Eq (14) have established a Bäcklund transformation between Eqs (8) and (9) and constraint Eq (13). Because of the Bäcklund transformation, the method can give infinite number of exact solutions for the considering NLEEs immediately.

Seen from the formulae Eq (14), if *ξ*(*t*, *x*) is a solution of Eq (13) with the form *ξ* = *ξ*(*x*−*Vt*), then it yields exact traveling wave solutions of Eqs (8) and (9). While if *ξ* ≠ *ξ*(*x*−*Vt*), then it yields exact non-traveling wave solutions of Eqs (8) and (9). Hence the formulae Eq (14) provide us with abundance of general form exact solutions to Eqs (8) and (9) once the solutions of Eq (13) are given.

**Step 5**. In the following, we determine the exact traveling wave and non-traveling wave solutions of Eqs (8) and (9) through exactly solving Eq (13).

#### The exact traveling wave solutions

In this subsection, we find the exact traveling wave solutions of Eqs (8) and (9) through obtaining specific solutions of Eq (13) formed by *ξ*(*t*, *x*) = *ξ*(*x*−*Vt*). In this case, Eq (13) becomes

(15)

$$
\begin{array}{ccl} & & {s\left\lbrack \xi'(z)^{2} - \xi(z)\xi^{''}(z) \right\rbrack\xi'(z)^{4} + \left\lbrack 4\xi'(z)\xi^{''}(z)\xi^{(3)}(z) - \xi'(z)^{2}\xi^{(4)}(z) - 3\xi^{''}(z)^{3} \right\rbrack\xi(z)^{3} = 0,} \end{array}
$$

where *z* = *x*−*Vt*.

With the transformation

(16)

$$
\begin{array}{r} {\xi(t,x) = \xi(z),\xi'(z) = Y(\xi),} \end{array}
$$

Eq (15) becomes the third order linear ODE with variable coefficients

$$
\begin{array}{r} {\xi^{3}Y^{(3)}(\xi) + s\left\lbrack \xi Y'(\xi) - Y(\xi) \right\rbrack = 0,} \end{array}
$$

which has general solutions as follows:

(17)

$$
\begin{array}{r} {Y(\xi) = \{\begin{matrix} {|\xi|\left\lbrack d_{1} + d_{2}\cos \left(\delta_{0}\ln |\xi| \right) + d_{3}\sin \left(\delta_{0}\ln |\xi| \right) \right\rbrack,\hspace{39.26494pt}\mathrm{if}\hspace{4pt}\hspace{4pt}\delta_{0}^{2} = s - 1 > 0,} \\ \\ {|\xi|\left(d_{1}|\xi|^{- \delta_{0}} + d_{2}|\xi|^{\delta_{0}} + d_{3} \right),\hspace{102.43008pt}\mathrm{if}\hspace{4pt}\hspace{4pt}\delta_{0}^{2} = 1 - s > 0,} \\ \\ {|\xi|\left(d_{1} + d_{2}{\ln |\xi|} + d_{3}\ln ^{2}|\xi| \right),\hspace{0.166667em}\hspace{94.17854pt}\mathrm{if}\hspace{4pt}\hspace{4pt}\delta_{0}^{2} = 1 - s = 0,} \end{matrix}\operatorname{}} \end{array}
$$

where *d*<sub>1</sub>, *d*<sub>2</sub> and *d*<sub>3</sub> are arbitrary constants. For a nontrivial solution, these constants should not be equal to zero simultaneously. Correspondingly, from Eqs (16) and (3), we have twelve kinds of exact solutions for Eq (13) respectively, which are summarized in the following three cases and their subcases.

**Case 1**: *s* &gt; 1. In this case, there are three kinds of exact solutions of Eq (13) shown in the following subcases.

- **Subcase 1.1**: $d_{2}^{2} + d_{3}^{2} - d_{1}^{2} > 0$, $A = \sqrt{d_{2}^{2} + d_{3}^{2} - d_{1}^{2}},A_{1} = d_{2} + \exp \lbrack d_{3}(z + d_{4})\delta_{0}\rbrack$,

  (18)

  $$
  \begin{array}{r} {\xi(z) = \{\begin{array}{l} {\varepsilon\hspace{1pt}\exp \left\lbrack - \frac{2\varepsilon}{\delta_{0}}\arctan \left(\frac{A\tanh \left(\frac{A}{2}\delta_{0}\left(z + d_{4}\varepsilon \right) \right) + d_{3}\varepsilon}{d_{1} - d_{2}} \right) \right\rbrack,\hspace{57.75905pt}\text{if}\hspace{4pt}d_{1} \neq d_{2}} \\ {\varepsilon\hspace{1pt}\exp \left\lbrack \frac{2}{\delta_{0}}\arccos \left(\frac{\pm d_{3}}{\sqrt{d_{2}^{2} + d_{3}^{2} + \exp \left(d_{3}\delta_{0}\left(z + d_{4} \right) \right)\left(d_{2} + A_{1} \right)}} \right) \right\rbrack,\hspace{34.14322pt}\text{if}\hspace{4pt}d_{1} = d_{2}} \end{array}\operatorname{}} \end{array}
  $$
- **Subcase 1.2**: $d_{2}^{2} + d_{3}^{2} - d_{1}^{2} < 0$,$A^{2} = d_{1}^{2} - d_{2}^{2} - d_{3}^{2},d_{1} \neq d_{2}$,

  (19)

  $$
  \begin{array}{r} {\xi(z) = \varepsilon\exp \left\lbrack \frac{2}{\delta_{0}}\arctan \left(\frac{A\tan \left(- \frac{A}{2}\delta_{0}\varepsilon\left(z + d_{4} \right) \right) + d_{3}}{d_{2} - d_{1}} \right) \right\rbrack.} \end{array}
  $$
- **Subcase 1.3**: $d_{2}^{2} + d_{3}^{2} - d_{1}^{2} = 0$,

  (20)

  $$
  \begin{array}{r} {\xi(z) = \exp \left\lbrack - \varepsilon\hspace{2pt}\arccos \left(\frac{\pm K_{2}(z)\left(d_{1} + \varepsilon d_{2}K_{1}(z) \right) + d_{1}K_{1}^{2}(z)\left(d_{1} + d_{1}K_{1}^{2}(z) - 2\varepsilon d_{2}K_{1}(z) \right)d_{3}^{3}}{d_{3}K_{1}(z)\left(d_{1}^{4}\left(1 + K_{1}^{4}(z) \right) + 2\left(d_{3}^{4} - d_{2}^{4} \right)K_{1}^{2}(z) \right)} \right) \right\rbrack,} \end{array}
  $$

  where

  $$
  \begin{array}{ccl} {K_{1}(z)} & = & {d_{3}\delta_{0}\left(z + d_{4} \right),} \\ {K_{2}(z)} & = & {d_{1}^{2}d_{3}^{2}K_{1}^{2}{(z)\lbrack}d_{1}^{4}K_{1}^{6}(z) + 2\theta\varepsilon{|d_{1}|}^{3}d_{2}K_{1}^{5}(z) + d_{1}^{2}d_{2}^{2} + 4\varepsilon d_{1}d_{2}^{3}K_{1}^{3}(z) + 2\varepsilon d_{1}d_{2}K_{1}(z)\left(d_{3}^{2} - d_{2}^{2} \right)} \\ & & {+ \hspace{0.166667em}K_{1}^{2}(z)\left(- d_{2}^{4} - 4d_{2}^{2}d_{3}^{2} + d_{3}^{4} \right) + K_{1}^{4}(z)\left(- d_{2}^{4} + d_{2}^{2}d_{3}^{2} + 2d_{3}^{4} \right){\rbrack.}} \end{array}
  $$

  and

  $$
  \begin{array}{r} {\theta = \{\begin{array}{l} {- 1,\hspace{4pt}\hspace{4pt}\hspace{4pt}\hspace{4pt}\hspace{4pt}\text{if}\hspace{4pt}\hspace{4pt}d_{1} > 0,} \\ {\hspace{4pt}\hspace{4pt}1,\hspace{4pt}\hspace{4pt}\hspace{4pt}\hspace{4pt}\hspace{4pt}\text{if}\hspace{4pt}\hspace{4pt}d_{1} < 0.} \end{array}\operatorname{}} \end{array}
  $$

**Case 2**: *s* < 1. In this case, there are five kinds of exact solutions of Eq (13) shown in the following subcases.

- **Subcase 2.1**: $4d_{1}d_{2} - d_{3}^{2} > 0,A = \sqrt{4d_{1}d_{2} - d_{3}^{2}},$

  (21)

  $$
  \begin{array}{r} {\xi(z) = \varepsilon\left\lbrack \frac{- 2d_{1}}{\varepsilon A\tan \left(\frac{\delta_{0}}{2}\left(z + d_{4} \right)A \right) + d_{3}} \right\rbrack^{\frac{1}{\delta_{0}}}.} \end{array}
  $$
- **Subcase 2.2**: $4d_{1}d_{2} - d_{3}^{2} < 0,d_{2} \neq 0,A^{2} = d_{3}^{2} - 4d_{1}d_{2},$

  (22)

  $$
  \begin{array}{r} {\xi(z) = \varepsilon\left\lbrack - \frac{\varepsilon A\tanh \left(\frac{\delta_{0}}{2}\left(z + d_{4} \right)A \right) + d_{3}}{2d_{2}} \right\rbrack^{\frac{1}{\delta_{0}}}.} \end{array}
  $$
- **Subcase 2.3**: $4d_{1}d_{2} - d_{3}^{2} < 0,d_{2} = 0,d_{3} \neq 0,$

  (23)

  $$
  \begin{array}{r} {\xi(z) = \varepsilon{\left\lbrack \frac{\exp \left(\varepsilon d_{3}\delta_{0}\left(z + d_{4} \right) \right) - d_{1}}{d_{3}} \right\rbrack^{\frac{1}{\delta_{0}}}.}} \end{array}
  $$
- **Subcase 2.4**: $4d_{1}d_{2} - d_{3}^{2} = 0,d_{1}d_{2} \neq 0,d_{3} \neq 0,$

  (24)

  $$
  \begin{array}{r} {\xi(z) = \varepsilon\left\lbrack - \frac{2d_{1}}{d_{3}} - \frac{4\varepsilon d_{1}}{d_{3}^{2}\left(z + d_{4} \right)\delta_{0}} \right\rbrack^{\frac{1}{\delta_{0}}}.} \end{array}
  $$
- **Subcase 2.5**: $4d_{1}d_{2} - d_{3}^{2} = 0,d_{1} = 0,d_{2} \neq 0,$ i.e., *d*<sub>1</sub> = *d*<sub>3</sub> = 0,

  (25)

  $$
  \begin{array}{r} {\xi(z) = \varepsilon\left\lbrack - \frac{\varepsilon}{d_{2}\delta_{0}\left(z + d_{4} \right)} \right\rbrack^{\frac{1}{\delta_{0}}}.} \end{array}
  $$

**Case 3**: *s* = 1. In this case, there are four kinds of solutions of Eq (13) shown in the following subcases.

- **Subcase 3.1**: $4d_{1}d_{3} - d_{2}^{2} > 0,d_{3} \neq 0,$

  (26)

  $$
  \begin{array}{r} {\xi(z) = \varepsilon\exp \left\lbrack \frac{\varepsilon\sqrt{4d_{1}d_{3} - d_{2}^{2}}\tan \left(\frac{1}{2}\sqrt{4d_{1}d_{3} - d_{2}^{2}}\left(z + d_{4} \right) \right) - d_{2}}{2d_{3}} \right\rbrack.} \end{array}
  $$
- **Subcase 3.2**: $4d_{1}d_{3} - d_{2}^{2} < 0,d_{3} \neq 0,A^{2} = d_{2}^{2} - 4d_{1}d_{3},$

  (27)

  $$
  \begin{array}{r} {\xi(z) = \varepsilon\exp \left\lbrack - \frac{\varepsilon A\tanh \left(\frac{1}{2}A\left(z + d_{4} \right) \right) + d_{2}}{2d_{3}} \right\rbrack.} \end{array}
  $$
- **Subcase 3.3**: $4d_{1}d_{3} - d_{2}^{2} < 0,d_{3} = 0,d_{2} \neq 0,$

  (28)

  $$
  \begin{array}{r} {\xi(z) = \{\begin{array}{l} {\exp \left\lbrack \frac{\exp \left(d_{2}\left(z + d_{4} \right) \right) - d_{1}}{d_{2}} \right\rbrack,\hspace{48.36958pt}\text{if}\hspace{4pt}\xi(z) > 0,} \\ {- \exp \left\lbrack \frac{i\exp \left(- d_{2}\left(z + d_{4} \right) \right) - d_{1}}{d_{2}} \right\rbrack,\hspace{28.45274pt}\text{if}\hspace{4pt}\xi(z) < 0,\hspace{4pt}i^{2} = - 1.} \end{array}\operatorname{}} \end{array}
  $$
- **Subcase 3.4**: $4d_{1}d_{3} - d_{2}^{2} = 0,d_{3} = 0,$ i.e., *d*<sub>2</sub> = *d*<sub>3</sub> = 0,

  (29)

  $$
  \begin{array}{r} {\xi(z) = d_{4}\exp \left(\varepsilon d_{1}z \right).} \end{array}
  $$

In all of above cases, *d*<sub>4</sub> is an additional arbitrary constant of integration and *ɛ* is given in Eq (7).

Substituting the obtained solutions *ξ* = *ξ*(*x*−*Vt*) in all of above cases Eqs (18)–(29) into Eqs (4)–(6) and (12) and assembling them in Eq (14), we obtain twelve kinds of exact traveling wave solutions of Eqs (8) and (9). Here we omit the duplicate and long expressions of these solutions.

**Remark 5**: A feature of these solutions is that they are multi-composite solutions, i.e., they are constructed by compounding several elementary functions. For example, in the case *s* &gt; 1, the solutions Eqs (18)–(20) are the compounding of five elementary functions exp, arctan, tanh, tan, arccos etc. These solutions can not be obtained by tanh-function method, the (*G*′/*G*)-expansion method and other method given \[6\] etc. The solution Eqs (21), (22), (26) and (27) have included soliton solutions when the parameters are taken properly. The solutions Eqs (24) and (25) are rational or irrational solutions at some values of these parameters appeared in these solutions. These already significantly expand the set of exact solutions for Eqs (8) and (9).

### A transformation between Eqs (8) and (9) and a linear heat equation

It is observed that if the *t*-derivative is equal to second order *x*-derivative, then each monomial term in Eq (13) has the same sum of *x*-derivative orders. This hints a relationship between Eq (13) and a kind of heat equation. In fact, Eq (13) can be written as

(30)

$$
\begin{array}{r} {s\left(\xi\xi_{xx} - \xi_{x}^{2} \right)\xi_{x}^{4} + \xi^{3}\left\lbrack 4P\left(P \pm 2\xi_{xx} \right)\xi_{xx} - 4P_{x}\left(\xi_{xx} \pm 2P \right)\xi_{x} + 2\left(2P_{t} - 2aP_{x} \pm P_{xx} \right)\xi_{x}^{2} \right\rbrack = 0,} \end{array}
$$

where *P* = *ξ*<sub>*t*</sub>−*τξ*<sub>*xx*</sub>−*aξ*<sub>*x*</sub> for arbitrary constant *a*, and

(31)

$$
\begin{array}{r} {\tau = \{\begin{array}{l} {- 1/2,\hspace{4pt}\hspace{4pt}\hspace{4pt}\hspace{4pt}\hspace{4pt}\text{if}\hspace{4pt}\hspace{4pt}a_{1}(t,x) = \xi_{x}/2,} \\ {\hspace{4pt}\hspace{4pt}1/2,\hspace{4pt}\hspace{4pt}\hspace{4pt}\hspace{4pt}\hspace{4pt}\text{if}\hspace{4pt}\hspace{4pt}a_{1}(t,x) = - \xi_{x}/2.} \end{array}\operatorname{}} \end{array}
$$

In order to get most general form exact solutions, we consider the following two cases.

**Case I**. For $\xi\xi_{xx} - \xi_{x}^{2} = 0$ and *s* = 2<em>δ</em>−*δ*<sup>2</sup>+4<em>ν</em>.

In this case, by solving Eq (13) we have *ξ*(*t*, *x*) = *d*<sub>4</sub>exp\[(*d*<sub>2</sub> *x*+*d*<sub>3</sub>)/(*t*+*d*<sub>1</sub>)\], which results in exact solutions of Eqs (8) and (9) given by Eq (14) with Eq (12) as follows

(32)

$$
\begin{array}{rcl} {u_{i}(t,x)} & = & {\frac{2d_{3} + d_{2}\left\lbrack 2x \pm d_{2}(\delta - 1) \right\rbrack}{4d_{2}\left(d_{1} + t \right)} \pm \frac{d_{2}}{2\left(d_{1} + t \right)} \cdot \xi(t,x)\phi_{i}(\xi),} \\ {v_{i}(t,x)} & = & {\mp \frac{d_{1} + t - d_{2}^{2}\nu}{2\left(d_{1} + t \right)^{2}} + \frac{d_{2}^{2}(\delta - 1)}{2\left(d_{1} + t \right)^{2}} \cdot \xi(t,x)\phi_{i}(\xi) + \frac{d_{2}^{2}}{2\left(d_{1} + t \right)^{2}} \cdot \xi^{2}(t,x)\phi_{i}^{2}(\xi),} \end{array}
$$

in which *i* = 1 for *s* &gt; 1, *i* = 2 for *s* < 1 and *i* = 3 for *s* = 1. *ϕ*<sub>1</sub>(*ξ*), *ϕ*<sub>2</sub>(*ξ*) and *ϕ*<sub>3</sub>(*ξ*) are given in Eqs (4)–(6). *d*<sub>1</sub>, *d*<sub>2</sub>, *d*<sub>3</sub>, *d*<sub>4</sub> are arbitrary constants.

**Case II**. For *s* = 2<em>δ</em>−*δ*<sup>2</sup>+4<em>ν</em> = 0.

In this case, Eq (13) or Eq (30) admits the solutions *ξ*(*t*, *x*) of the linear heat equation

(33)

$$
\begin{array}{r} {\xi_{t} = \tau\xi_{xx} + a\xi_{x},} \end{array}
$$

with a conductive term *aξ*<sub>*x*</sub> for arbitrary constant *a*.

It is interesting that a transformation in the form of Eq (14) between Eqs (8) and (9) and the linear heat Eq (35) has been found. Using the transformation, we will obtain infinite number of exact solutions of Eqs (8) and (9). That means each solution of the heat Eq (35) (such as those given in the following Eq (34)) yields a set of exact solutions of Eqs (8) and (9). Moreover, the connection provides us with an insight into integrability of Eqs (8) and (9). For example, using the transformation, we can investigate the multi-soliton solutions, rational solutions and other types of solutions to the Boussinesq-Burgers equation.

As we know, the heat Eq (35) has infinite number of specific known exact solutions. Some representatives of them are listed as follows:

(34)

$$
\begin{array}{rcl} {\xi(t,x)} & = & {\frac{A}{\sqrt{t}}\exp \left(- \frac{(x + at)^{2}}{4\tau t} \right) + B,\hspace{4pt}\hspace{4pt}(t,x) \in R^{2},} \\ {\xi(t,x)} & = & {A\exp \left(- \tau k^{2}t \right)\cos \left(k(x + at) + B \right) + C,\hspace{4pt}\hspace{4pt}(t,x) \in R^{2},} \\ {\xi(t,x)} & = & {A\exp \left(- k(x + at) \right)\cos \left(kx + k(a - 2\tau k)t + B \right) + C,\hspace{4pt}\hspace{4pt}(t,x) \in R^{2},} \\ {\xi(t,x)} & = & {c_{0}\mathrm{erfc}\left(\frac{x + at}{2\sqrt{\tau t}} \right),\hspace{4pt}\hspace{4pt}t > 0,x + at > 0,\tau > 0,} \\ {\xi(t,x)} & = & {\sum\limits_{n = 1}^{+ \infty}c_{n}\sin \left(\frac{n\pi(x + at)}{L} \right)\exp \left(- \tau\left(\frac{n\pi}{L} \right)^{2}t \right),\hspace{4pt}\hspace{4pt}t > 0,0 \leq x + at \leq L,L > 0,} \\ {\xi(t,x)} & = & {\frac{1}{2\sqrt{\pi\tau t}}\int_{- \infty}^{+ \infty}\omega(\theta)\exp \left(- \frac{(x + at - \theta)^{2}}{4\tau t} \right)d\theta,\hspace{4pt}\hspace{4pt}t > 0,x \in R,\tau > 0,} \end{array}
$$

where *A*, *B*, *C*, *c*<sub>0</sub> and *k* are arbitrary constants, *ω*(*θ*) is any integrable function, erfc(*y*) is error function and *c*<sub>*n*</sub>, *n* = 1, 2, ⋯ are constants given by the initial or boundary conditions of Eq (35). *τ* = ±1/2 is given in Eq (31). It is noticed that the last solution in Eq (34) yields an exact solution to the Boussinesq- Burgers equation with containing an arbitrary function, which may give more freedom to solve related problems of the equations \[7\].

### Some examples of new exact solutions

#### General form exact solutions

In Case II, substituting any solution of heat Eq (35) into Eq (12) and assembling them in Eq (14) with *i* = 2, we obtain exact solutions to Eqs (8) and (9). As examples, we present four exact solutions (*u*<sub>*j*</sub>, *v*<sub>*j*</sub>)(*j* = 1,2,3,4) of Eqs (8) and (9) corresponding to the first four solutions in Eq (34). Here we have

1. $\xi(t,x) = A\exp (- {(x + at)}^{2}/4\tau t)/\sqrt{t} + B,\operatorname{}\operatorname{}(t,x) \in R^{2},\operatorname{}\tau = \pm 1/2$:

   $$
   \begin{array}{ccl} {u_{1}(t,x)} & = & {\frac{1}{4\left\lbrack Ath_{1}(t,x) + Bt^{3/2} \right\rbrack}\left\lbrack at\left(- 2B\sqrt{t} + A(\delta - 2)h_{1}(t,x) \right) + A\delta xh_{1}(t,x) \right\rbrack} \\ & & {+ \frac{A(at + x)}{2t^{3/2}}h_{1}(t,x)\phi_{2}(\xi),} \\ {v_{1}(t,x)} & = & {\frac{Ah_{1}(t,x)}{4\left\lbrack Ath_{1}(t,x) + Bt^{3/2} \right\rbrack^{2}}\left\lbrack - B\delta \right.\sqrt{t}\left(\pm t + a^{2}t^{2} + 2atx + x^{2} \right)} \\ & & {+ Ah_{1}(t,x)\left(\mp \delta t + 2\nu a^{2}t^{2} + 4a\nu tx + 2\nu x^{2} \right)\rbrack} \\ & & {\pm \frac{Ah_{1}(t,x)}{2\left\lbrack Ah_{1}(t,x) + B\sqrt{t} \right\rbrack t^{5/2}}\left\lbrack \mp B\sqrt{t}\left(\pm t + a^{2}t^{2} + 2atx + x^{2} \right) \pm Ah_{1}(t,x)(\right.t\left(2a(\delta - 1)x \mp 1 \right)} \\ & & {+ (\delta - 1)\left(a^{2}t^{2} + x^{2} \right)\rbrack\phi_{2}(\xi) + \frac{A^{2}(at + x)^{2}2}{2t^{3}}h_{1}^{2}(t,x)\phi_{2}^{2}(\xi),} \end{array}
   $$

   where *A*, *B* are arbitrary constants, and *h*<sub>1</sub>(*t*, *x*) = exp\[−(*x*+*at*)<sup>2</sup>/4*τt*\].
2. *ξ*(*t*, *x*) = *A*exp(−*τk*<sup>2</sup> *t*)cos(*k*(*x*+*at*)+*B*)+*C*, (*t*, *x*) ∈ *R*<sup>2</sup>, *τ* = ±1/2:

   $$
   \begin{array}{ccl} {u_{2}(t,x)} & = & {- \frac{1}{4\xi(t,x)}\left\lbrack 2aC + 2aA\cos \left(\xi_{0} \right)h_{2}(t,x) \pm Ak\delta\sin \left(\xi_{0} \right)h_{2}(t,x) \right\rbrack \mp \frac{1}{2}Ak\sin \left(\xi_{0} \right)h_{2}(t,x)\phi_{2}(\xi),} \\ {v_{2}(t,x)} & = & {\frac{1}{4\xi^{2}(t,x)}\left\lbrack Ak^{2}h_{2}(t,x)(\right.C\delta\cos \left(\xi_{0} \right) + A\left(\delta + \nu - \nu\cos \left(2\xi_{0} \right)h_{2}(t,x) \right\rbrack} \\ & & {+ \frac{1}{2}Ak^{2}h_{2}(t,x)\left\lbrack \cos \left(\xi_{0} \right) + \frac{A\delta\sin ^{2}\left(\xi_{0} \right)h_{2}(t,x)}{\xi(t,x)} \right\rbrack\phi_{2}(\xi) + \frac{1}{2}Ak^{2}h_{2}^{2}(t,x)\sin ^{2}\left(\xi_{0} \right)\phi_{2}^{2}(\xi),} \end{array}
   $$

   where *A*, *B*, *C* are arbitrary constants, and *ξ*<sub>0</sub> = *B*+*k*(*x*+*at*), *h*<sub>2</sub>(*t*, *x*) = exp(−*τk*<sup>2</sup> *t*).
3. *ξ*(*t*, *x*) = *A*exp(−*k*(*x*+*at*))cos(*kx*+*k*(*a*−2*τk*)*t*+*B*)+*C*, (*t*, *x*) ∈ *R*<sup>2</sup>, *τ* = ±1/2:

   $$
   \begin{array}{ccl} {u_{3}(t,x)} & = & {\frac{- 2a\left\lbrack C + A\cos \left(\xi_{0} \right)h_{3}(t,x) \right\rbrack \mp Ak\delta h_{3}(t,x)h_{4}(t,x)}{4\xi(t,x)} \mp \frac{1}{2}Akh_{3}(t,x)h_{4}(t,x)\phi_{2}(\xi),} \\ {v_{3}(t,x)} & = & {\frac{Ak^{2}h_{3}(t,x)}{4\xi^{2}(t,x)}\left\lbrack - 2C\delta\sin \left(\xi_{0} \right) + A\left(\delta + 2\nu + 2\nu\sin \left(2\xi_{0} \right) \right)h_{3}(t,x) \right\rbrack} \\ & & {+ \hspace{0.166667em}\frac{Ak^{2}h_{3}(t,x)}{2\xi(t,x)}\left\lbrack - 2C\sin \left(\xi_{0} \right) + A\left(\delta + (\delta - 1)\sin \left(2\xi_{0} \right) \right)h_{3}(t,x) \right\rbrack\phi_{2}(\xi) + \frac{1}{2}A^{2}k^{2}h_{3}^{2}(t,x)h_{4}^{2}(t,x)\phi_{2}^{2}(\xi),} \end{array}
   $$

   where *A*, *B*, *C* are arbitrary constants, and *ξ*<sub>0</sub> = *B*+*kx*+*kt*(*a*−2*kτ*), *h*<sub>3</sub>(*t*, *x*) = exp\[−*k*(*x*+*at*)\], *h*<sub>4</sub>(*t*, *x*) = cos*ξ*<sub>0</sub>+sin*ξ*<sub>0</sub>.
4. $\xi(t,x) = c_{0}\text{erfc}(\frac{x + at}{2\sqrt{\tau t}}),\operatorname{}\operatorname{}t > 0,x + at > 0,\tau = 1/2:$

   $$
   \begin{array}{ccl} {u_{4}(t,x)} & = & {- \frac{a}{2} + \frac{\delta h_{1}(t,x)}{2\sqrt{2\pi t}\mathrm{erfc}\left(\xi_{0} \right)} + \frac{c_{0}}{\sqrt{2\pi t}}h_{1}(t,x)\phi_{2}(\xi),} \\ {v_{4}(t,x)} & = & {\frac{h_{1}^{2}(t,x)}{4\pi t^{3/2}\mathrm{erfc}^{2}\left(\xi_{0} \right)}\left\lbrack 2\sqrt{t}(\delta + 2\nu) - \sqrt{2\pi}\delta h_{1}^{- 1}(t,x)(x + at)\mathrm{erfc}\left(\xi_{0} \right) \right\rbrack} \\ & & {+ \hspace{0.166667em}\left\lbrack \frac{c_{0}\delta h_{1}^{2}(t,x)}{\pi t\mathrm{erfc}\left(\xi_{0} \right)} - \frac{c_{0}\sqrt{2}(x + at)h_{1}(t,x)}{2\sqrt{\pi}t^{3/2}} \right\rbrack\phi_{2}(\xi) + \frac{c_{0}^{2}h_{1}^{2}(t,x)}{\pi t}\phi_{2}^{2}(\xi),} \end{array}
   $$

   where *c*<sub>0</sub> is an arbitrary constant, and $\xi_{0} = \frac{x + at}{2\sqrt{\tau t}}.$

In all of above cases, *ϕ*<sub>2</sub>(*ξ*) is given in Eq (5).

By the same manner, from the rest two solutions in Eq (34), we should obtain additional exact solutions in different styles to the Boussinesq-Burgers. Due to the lack of space, we omit the reasoning and the solution expressions.

**Remark 6**: In author’s knowledge, this is the first time showing these kinds of exact solutions to Eqs (8) and (9). These solutions can not be obtained by other simplest equation methods \[18–25\].

#### The multi-soliton solutions

Using the connection between solutions of Eqs (8), (9) and (35), we can get the multi-soliton solutions of Eqs (8) and (9). It is easy to check that Eq (35) admits solutions

$$
\begin{array}{r} {\xi(t,x) = A_{0} + \sum\limits_{i = 1}^{n}A_{i}\exp \left\lbrack k_{i}x + \left(\tau k_{i}^{2} + ak_{i} \right)t + B_{i} \right\rbrack,\hspace{4pt}\hspace{4pt}\tau = \pm 1/2,} \end{array}
$$

for arbitrary constants *k*<sub>*i*</sub>, *A*<sub>*i*</sub>, *B*<sub>*i*</sub>(*i* = 0, 1, ⋯, *n*) and positive integer *n*, which yield multi-soliton solutions of Eqs (8) and (9) given by Eqs (12) and (14) with *i* = 2.

#### The rational solutions

Suppose that Eq (35) has a solution in the form

(35)

$$
\begin{array}{r} {\xi(t,x) = \sum\limits_{i = 0}^{n}k_{i}(X)t^{i},X = x + at,} \end{array}
$$

for arbitrary positive integer *n*. Substituting Eq (35) into Eq (35) and setting the coefficients of *t*<sup>*i*</sup>(*i* = 0, 1, ⋯, *n*) to be zero, we obtain the ODEs for *k*<sub>*i*</sub>(*X*) as $k_{n}^{''} = 0$ and $\alpha k_{j - 1}^{''} = k_{j},j = n,\cdots,1$, which yield the solutions

$$
\begin{array}{r} {k_{i}(X) = \sum\limits_{j = 1}^{2(n + 1 - i)}\alpha_{j}\frac{X^{2(n + 1 - i) - j}}{\left\lbrack 2(n + 1 - i) - j \right\rbrack!},i = 0,1,2,\cdots,n,} \end{array}
$$

for arbitrary constants *α*<sub>*j*</sub>. Substituting the solutions into Eq (35), we obtain the polynomial solutions of Eq (35), which yield rational solutions of Eqs (8) and (9) given by Eq (12) and (14) with *i* = 2.

## 4 Conclusions

In this paper, we proposed a new auxiliary equation method to look for exact solutions of NLEEs. There are two features of the discussed method which are different from other simplest equation methods \[18\]–\[25\]. Firstly, a solution expression with a variable coefficient is chosen and a special simplest nonlinear differential equations (a special ODE with variable coefficients) is taken as auxiliary equation. Secondly, the method can yield a Bäcklund transformation between the given NLEEs and the related constraint equation. By dealing with the constraint equation, we can derive infinite number of exact solutions for NLEEs. These solutions include the traveling wave solutions, non-traveling wave solutions, multi-soliton solutions, rational solutions and other types of solutions for NLEEs. According to the auxiliary equation and above two features of our method, we call the method as the generalized simplest equation method.

As application of our method, a great number of new exact solutions of the Boussinesq-Burgers equation are obtained. Essentially, the constraint equation is related to linear heat equation which result in new exact solutions of the Boussinesq-Burgers equation. These solutions are different from those solutins given in literatures \[26–32\]. It shows that our method is more flexible in finding more general form exact solutions and the method can be used for many other NLEEs in mathematical physics. As a result, our method effectively enhances the existing auxiliary equation methods, such as those given in \[10, 16\], which demonstrates that the proposed method is effective and prospective.

We have also tested other several commonly used auxiliary equations, such as Riccati equation \[10, 11\], the auxiliary equation of F-expansion method \[12\], to get exact solutions of the Boussinesq-Burgers equation in the frame of our method. Unfortunately, we can not get the results presented in the paper. What’s more, the relationship between the Boussinesq-Burgers equation and the linear heat equation can not be found. Hence the auxiliary Eq (3) has its own advantages which are not admitted by other auxiliary equations.

In addition, the true idea of our method makes one further consider finding more general exact solutions of other NLEEs by developing the existing methods, such as Tanh-method, the simplest equation method, etc, or designing new method, in which a connection between the constraint equation and other easily solved equation may be set up. It is an excellent topic for further research.

This work is supported by Natural Science Foundation of Inner Mongolia Autonomous Region of China (2014MS0114, 2014BS0105), High Education Science Research Program of Inner Mongolia of China (NJZY12056).

## References (32 total, showing 32)

1. Ablowitz MJ, Clarkson PA. Solitons, nonlinear evolution equations and inverse scattering. Cambridge: Cambridge University Press; 1991.

2. Matveev VB, Salle MA. Darboux transformation and solitons. Berlin: Springer Press; 1991.

3. Hirota R. The Direct Method in Soliton Theory. Cambridge: Cambridge University Press; 2004.

4. Weiss J, Tabor M, Carnevale G. The Painleve property for partial differential equations. J. Math. Phys. 1983; 24: 522–526. doi: [10.1063/1.525875](http://dx.doi.org/10.1063/1.525875)

5. Miura RM. Bäcklund Transformation. Berlin: Springer Press; 1978.

6. Weiss J. Bäcklund Tradsformation and Linearizations of the Henon-Heiles System. Phys. Lett. A. 1984; 102(8): 329–331. doi: [10.1016/0375-9601(84)90289-5](http://dx.doi.org/10.1016/0375-9601(84)90289-5)

7. Lou SY, Tang XY. Nonlinear mathematical physics methods. Beijing: Science Press; 2006.

8. Wang ML, Zhou YB, Li ZB. Applications of a homogeneous balance method to exact solutions of nonlinear equations in mathematical physics. Phys. Lett. A. 1996; 216: 67–75. doi: [10.1016/0375-9601(96)00283-6](http://dx.doi.org/10.1016/0375-9601(96)00283-6)

9. Liu SK, Fu ZT, Liu SD, Zhao Q. Jacobi elliptic function expansion method and periodic wave solutions of nonlinear wave equations. Phys. Lett. A. 2001; 289: 69–74. doi: [10.1016/S0375-9601(01)00580-1](http://dx.doi.org/10.1016/S0375-9601(01)00580-1)

10. Fan EG. Extended tanh-function method and its applications to nonlinear equations. Phys. Lett. A. 2000; 277: 212–218. doi: [10.1016/S0375-9601(00)00725-8](http://dx.doi.org/10.1016/S0375-9601(00)00725-8)

11. Fan EG, Hon YC. Applications of extended tanh method to special types of nonlinear equations. Appl. Math. Comput. 2003; 141: 351–358. doi: [10.1016/S0096-3003(02)00260-6](http://dx.doi.org/10.1016/S0096-3003(02)00260-6)

12. Zhou YB, Wang ML, Wang YM. Periodic Wave Solutions to a Coupled KdV Equations with Variable Coefficients. Phys. Lett. A. 2003; 308: 31–36. doi: [10.1016/S0375-9601(02)01775-9](http://dx.doi.org/10.1016/S0375-9601(02)01775-9)

13. Sirendaoreji, Sun J. Auxiliary equation method for solving nonlinear partial differential equations. Phys. Lett. A. 2003; 309: 387–396. doi: [10.1016/S0375-9601(03)00196-8](http://dx.doi.org/10.1016/S0375-9601(03)00196-8)

14. Li XZ, Wang ML. A sub-ODE method for finding exact solutions of a generalized KdV-mKdV equation with higher order nonlinear terms. Phys. Lett. A. 2007; 361: 115–118. doi: [10.1016/j.physleta.2006.09.022](http://dx.doi.org/10.1016/j.physleta.2006.09.022)

15. He JH, Wu XH. Exp-function method for nonlinear wave equations. Chaos, Soliton. Fract. 2006; 34: 700–708. doi: [10.1016/j.chaos.2006.03.020](http://dx.doi.org/10.1016/j.chaos.2006.03.020)

16. Wang ML, Li XZ, Zhang JL. The (*G*′/*G*)-expansion method and travelling wave solutions of nonlinear evolution equations in mathematical physics. Phys. Lett. A. 2008; 372: 417–423. doi: [10.1016/j.physleta.2007.07.051](http://dx.doi.org/10.1016/j.physleta.2007.07.051)

17. Naher H, Abdullah FA, Akbar MA. Generalized and improved (*G*′/*G*)-expansion method for (3+1)-dimensional modified KdV-Zakharov-Kuznetsev equation. PLoS ONE. 2013; 8(5): e64618. doi: [10.1371/journal.pone.0064618](http://dx.doi.org/10.1371/journal.pone.0064618) 23741355

18. Kudryashov NA. Simplest equation method to look for exact solutions of nonlinear differential equations. Chaos, Solitons Fract. 2005; 24: 1217–1231. doi: [10.1016/j.chaos.2004.09.109](http://dx.doi.org/10.1016/j.chaos.2004.09.109)

19. Kudryashov NA. Exact solitary waves of the fisher equation. Phys. Lett. A. 2005; 342: 99–106. doi: [10.1016/j.physleta.2005.05.025](http://dx.doi.org/10.1016/j.physleta.2005.05.025)

20. Kudryashov NA. One method for finding exact solutions of nonlinear differential equations. Commun. Nonlinear Sci. Numer. Simulat. 2012; 17: 2248–2253. doi: [10.1016/j.cnsns.2011.10.016](http://dx.doi.org/10.1016/j.cnsns.2011.10.016)

21. Jafari H, Kadkhoda N, Khalique CM. Travelling wave solutions of nonlinear evolution equations using the simplest equation method. Comput. Math. Appl. 2012; 64: 2084–2088.

22. Vitanov NK, Dimitrova ZI, Kantz H. Application of the method of simplest equation for obtaining exact traveling-wave solutions for the extended Korteweg-de Vries equation and generalized Camassa-Holm equation. Appl. Math. Comput. 2013; 219: 7480–7492. doi: [10.1016/j.amc.2013.01.035](http://dx.doi.org/10.1016/j.amc.2013.01.035)

23. Sudao B, Temuer C. An extended simplest equation method and its application to several forms of the fifth-order KdV equation. Appl. Math. Comput. 2010; 216: 3146–3153. doi: [10.1016/j.amc.2010.04.029](http://dx.doi.org/10.1016/j.amc.2010.04.029)

24. Sudao B, Temuer C, Wang XM. Application of the extended simplest equation method to the coupled Schrödinger-Boussinesq equation. Appl. Math. Comput. 2013; 224: 517–523. doi: [10.1016/j.amc.2013.08.083](http://dx.doi.org/10.1016/j.amc.2013.08.083)

25. Antonova AO, Kudryashov NA. Generalization of the simplest equation method for nonlinear non-autonomous different eqations. Commun. Nonlinear Sci. Numer. Simulat. 2014; 19: 4037–4041. doi: [10.1016/j.cnsns.2014.03.035](http://dx.doi.org/10.1016/j.cnsns.2014.03.035)

26. Abdel Rady AS, Khalfallah M. On soliton solutions for Boussinesq-Burgers equations. Commun. Nonlinear Sci. Numer. Simulat. 2010; 15: 886–894. doi: [10.1016/j.cnsns.2009.05.053](http://dx.doi.org/10.1016/j.cnsns.2009.05.053)

27. Zhang L, Zhang LF, Li CY. Some new exact solutions of Jacobian elliptic function about the generalized Boussinesq equation and Boussinesq-Burgers equation. Chinese Phys. B. 2008; 17: 403–410. doi: [10.1088/1674-1056/17/2/009](http://dx.doi.org/10.1088/1674-1056/17/2/009)

28. Gao L, Xu W, Tang YN, Meng GF. New families of travelling wave solutions for Boussinesq-Burgers equation and (3+1)-dimensional Kadomtsev-Petviashvili equation. Phys. Lett. A. 2007; 366: 411–421. doi: [10.1016/j.physleta.2007.02.040](http://dx.doi.org/10.1016/j.physleta.2007.02.040)

29. Wang ZY, Chen AH. Explicit solutions of Boussinesq-Burgers equation. Chinese Phys. 2007; 16: 1233–1238. doi: [10.1088/1009-1963/16/5/011](http://dx.doi.org/10.1088/1009-1963/16/5/011)

30. Khalfallah M. Exact traveling wave solutions of the Boussinesq-Burgers equation. Math. Comput. Model. 2009; 49: 666–671. doi: [10.1016/j.mcm.2008.08.004](http://dx.doi.org/10.1016/j.mcm.2008.08.004)

31. Li XM, Chen AH. Darboux transformation and multi-soliton solutions of Boussinesq-Burgers equation. Phys. Lett. A. 2005; 342: 413–420. doi: [10.1016/j.physleta.2005.02.056](http://dx.doi.org/10.1016/j.physleta.2005.02.056)

32. Chen AH, Li XM. Darboux transformation and soliton solutions for Boussinesq-Burgers equation. Chaos, Soliton. Fract. 2006; 27: 43–49. doi: [10.1016/j.chaos.2004.09.116](http://dx.doi.org/10.1016/j.chaos.2004.09.116)
