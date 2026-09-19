---
title: "Generative Adversarial Networks"
authors: "Ian J. Goodfellow, Jean Pouget-Abadie, Mehdi Mirza, Bing Xu, David Warde-Farley"
journal: "arXiv"
doi: "10.48550/arxiv.1406.2661v1"
published: "2014-06-10"
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
token_estimate: 6947
---

# Generative Adversarial Networks

## Abstract

We propose a new framework for estimating generative models via an adversarial process, in which we simultaneously train two models: a generative model $G$ that captures the data distribution, and a discriminative model $D$ that estimates the probability that a sample came from the training data rather than $G$. The training procedure for $G$ is to maximize the probability of $D$ making a mistake. This framework corresponds to a minimax two-player game. In the space of arbitrary functions $G$ and $D$, a unique solution exists, with $G$ recovering the training data distribution and $D$ equal to $\frac{1}{2}$ everywhere. In the case where $G$ and $D$ are defined by multilayer perceptrons, the entire system can be trained with backpropagation. There is no need for any Markov chains or unrolled approximate inference networks during either training or generation of samples. Experiments demonstrate the potential of the framework through qualitative and quantitative evaluation of the generated samples.

## 1 Introduction

The promise of deep learning is to discover rich, hierarchical models [<sup>2</sup>] that represent probability distributions over the kinds of data encountered in artificial intelligence applications, such as natural images, audio waveforms containing speech, and symbols in natural language corpora. So far, the most striking successes in deep learning have involved discriminative models, usually those that map a high-dimensional, rich sensory input to a class label [<sup>14, 22</sup>]. These striking successes have primarily been based on the backpropagation and dropout algorithms, using piecewise linear units [<sup>19, 9, 10</sup>] which have a particularly well-behaved gradient. Deep generative models have had less of an impact, due to the difficulty of approximating many intractable probabilistic computations that arise in maximum likelihood estimation and related strategies, and due to difficulty of leveraging the benefits of piecewise linear units in the generative context. We propose a new generative model estimation procedure that sidesteps these difficulties. <sup>1</sup> All code and hyperparameters available at http://www.github.com/goodfeli/adversarial

In the proposed adversarial nets framework, the generative model is pitted against an adversary: a discriminative model that learns to determine whether a sample is from the model distribution or the data distribution. The generative model can be thought of as analogous to a team of counterfeiters, trying to produce fake currency and use it without detection, while the discriminative model is analogous to the police, trying to detect the counterfeit currency. Competition in this game drives both teams to improve their methods until the counterfeits are indistiguishable from the genuine articles.

This framework can yield specific training algorithms for many kinds of model and optimization algorithm. In this article, we explore the special case when the generative model generates samples by passing random noise through a multilayer perceptron, and the discriminative model is also a multilayer perceptron. We refer to this special case as adversarial nets. In this case, we can train both models using only the highly successful backpropagation and dropout algorithms [<sup>17</sup>] and sample from the generative model using only forward propagation. No approximate inference or Markov chains are necessary.

## 2 Related work

An alternative to directed graphical models with latent variables are undirected graphical models with latent variables, such as restricted Boltzmann machines (RBMs) [<sup>27, 16</sup>], deep Boltzmann machines (DBMs) [<sup>26</sup>] and their numerous variants. The interactions within such models are represented as the product of unnormalized potential functions, normalized by a global summation/integration over all states of the random variables. This quantity (the partition function) and its gradient are intractable for all but the most trivial instances, although they can be estimated by Markov chain Monte Carlo (MCMC) methods. Mixing poses a significant problem for learning algorithms that rely on MCMC [<sup>3, 5</sup>].

Deep belief networks (DBNs) [<sup>16</sup>] are hybrid models containing a single undirected layer and several directed layers. While a fast approximate layer-wise training criterion exists, DBNs incur the computational difficulties associated with both undirected and directed models.

Alternative criteria that do not approximate or bound the log-likelihood have also been proposed, such as score matching [<sup>18</sup>] and noise-contrastive estimation (NCE) [<sup>13</sup>]. Both of these require the learned probability density to be analytically specified up to a normalization constant. Note that in many interesting generative models with several layers of latent variables (such as DBNs and DBMs), it is not even possible to derive a tractable unnormalized probability density. Some models such as denoising auto-encoders [<sup>30</sup>] and contractive autoencoders have learning rules very similar to score matching applied to RBMs. In NCE, as in this work, a discriminative training criterion is employed to fit a generative model. However, rather than fitting a separate discriminative model, the generative model itself is used to discriminate generated data from samples a fixed noise distribution. Because NCE uses a fixed noise distribution, learning slows dramatically after the model has learned even an approximately correct distribution over a small subset of the observed variables.

Finally, some techniques do not involve defining a probability distribution explicitly, but rather train a generative machine to draw samples from the desired distribution. This approach has the advantage that such machines can be designed to be trained by back-propagation. Prominent recent work in this area includes the generative stochastic network (GSN) framework [<sup>5</sup>], which extends generalized denoising auto-encoders [<sup>4</sup>]: both can be seen as defining a parameterized Markov chain, i.e., one learns the parameters of a machine that performs one step of a generative Markov chain. Compared to GSNs, the adversarial nets framework does not require a Markov chain for sampling. Because adversarial nets do not require feedback loops during generation, they are better able to leverage piecewise linear units [<sup>19, 9, 10</sup>], which improve the performance of backpropagation but have problems with unbounded activation when used ina feedback loop. More recent examples of training a generative machine by back-propagating into it include recent work on auto-encoding variational Bayes [<sup>20</sup>] and stochastic backpropagation [<sup>24</sup>].

## 3 Adversarial nets

The adversarial modeling framework is most straightforward to apply when the models are both multilayer perceptrons. To learn the generator’s distribution $p_{g}$ over data $\bm{x}$, we define a prior on input noise variables $p_{\bm{z}}(\bm{z})$, then represent a mapping to data space as $G(\bm{z};\theta_{g})$, where $G$ is a differentiable function represented by a multilayer perceptron with parameters $\theta_{g}$. We also define a second multilayer perceptron $D(\bm{x};\theta_{d})$ that outputs a single scalar. $D(\bm{x})$ represents the probability that $\bm{x}$ came from the data rather than $p_{g}$. We train $D$ to maximize the probability of assigning the correct label to both training examples and samples from $G$. We simultaneously train $G$ to minimize $\log(1-D(G(\bm{z})))$:

In other words, $D$ and $G$ play the following two-player minimax game with value function $V(G,D)$:

$$ \min_{G}\max_{D}V(D,G)=\mathbb{E}_{\bm{x}\sim p_{\text{data}}(\bm{x})}[\log D(\bm{x})]+\mathbb{E}_{\bm{z}\sim p_{\bm{z}}(\bm{z})}[\log(1-D(G(\bm{z})))]. $$
(1)

In the next section, we present a theoretical analysis of adversarial nets, essentially showing that the training criterion allows one to recover the data generating distribution as $G$ and $D$ are given enough capacity, i.e., in the non-parametric limit. See Figure 1 for a less formal, more pedagogical explanation of the approach. In practice, we must implement the game using an iterative, numerical approach. Optimizing $D$ to completion in the inner loop of training is computationally prohibitive, and on finite datasets would result in overfitting. Instead, we alternate between $k$ steps of optimizing $D$ and one step of optimizing $G$. This results in $D$ being maintained near its optimal solution, so long as $G$ changes slowly enough. This strategy is analogous to the way that SML/PCD [<sup>31, 29</sup>] training maintains samples from a Markov chain from one learning step to the next in order to avoid burning in a Markov chain as part of the inner loop of learning. The procedure is formally presented in Algorithm 1.

In practice, equation 1 may not provide sufficient gradient for $G$ to learn well. Early in learning, when $G$ is poor, $D$ can reject samples with high confidence because they are clearly different from the training data. In this case, $\log(1-D(G(\bm{z})))$ saturates. Rather than training $G$ to minimize $\log(1-D(G(\bm{z})))$ we can train $G$ to maximize $\log D(G(\bm{z}))$. This objective function results in the same fixed point of the dynamics of $G$ and $D$ but provides much stronger gradients early in learning.

|                                                          |                                                          |                                                          |     |                                                          |
| -------------------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------- | --- | -------------------------------------------------------- |
|

![Figure 1](1406.2661v1_assets/fig1.svg)

|

![Figure 1](1406.2661v1_assets/fig2.svg)

|

![Figure 1](1406.2661v1_assets/fig3.svg)

| …   |

![Figure 1](1406.2661v1_assets/fig4.svg)

|
| (a)                                                      | (b)                                                      | (c)                                                      |     | (d)                                                      |

**Figure 1.** Generative adversarial nets are trained by simultaneously updating the d iscriminative distribution ($D$, blue, dashed line) so that it discriminates between samples from the data generating distribution (black, dotted line) $p_{\bm{x}}$ from those of the g enerative distribution $p_{g}$ (G) (green, solid line). The lower horizontal line is the domain from which $\bm{z}$ is sampled, in this case uniformly. The horizontal line above is part of the domain of $\bm{x}$. The upward arrows show how the mapping $\bm{x}=G(\bm{z})$ imposes the non-uniform distribution $p_{g}$ on transformed samples. $G$ contracts in regions of high density and expands in regions of low density of $p_{g}$. (a) Consider an adversarial pair near convergence: $p_{g}$ is similar to $p_{\text{data}}$ and $D$ is a partially accurate classifier. (b) In the inner loop of the algorithm $D$ is trained to discriminate samples from data, converging to $D^{*}(\bm{x})=\frac{p_{\text{data}}(\bm{x})}{p_{\text{data}}(\bm{x})+p_{g}(\bm{x})}$. (c) After an update to $G$, gradient of $D$ has guided $G(\bm{z})$ to flow to regions that are more likely to be classified as data. (d) After several steps of training, if $G$ and $D$ have enough capacity, they will reach a point at which both cannot improve because $p_{g}=p_{\text{data}}$. The discriminator is unable to differentiate between the two distributions, i.e. $D(\bm{x})=\frac{1}{2}$.

**Algorithm 1.** Minibatch stochastic gradient descent training of generative adversarial nets. The number of steps to apply to the discriminator, $k$, is a hyperparameter. We used $k=1$, the least expensive option, in our experiments.

```text
for number of training iterations do
for $k$ steps do
$\bullet$ Sample minibatch of $m$ noise samples $\{\bm{z}^{(1)},\dots,\bm{z}^{(m)}\}$ from noise prior $p_{g}(\bm{z})$.
$\bullet$ Sample minibatch of $m$ examples $\{\bm{x}^{(1)},\dots,\bm{x}^{(m)}\}$ from data generating distribution $p_{\text{data}}(\bm{x})$.
$\bullet$ Update the discriminator by ascending its stochastic gradient: $$ \nabla_{\theta_{d}}\frac{1}{m}\sum\limits_{i=1}^{m}\left[\log D\left(\bm{x}^{(i)}\right)+\log\left(1-D\left(G\left(\bm{z}^{(i)}\right)\right)\right)\right]. $$
end for
$\bullet$ Sample minibatch of $m$ noise samples $\{\bm{z}^{(1)},\dots,\bm{z}^{(m)}\}$ from noise prior $p_{g}(\bm{z})$.
$\bullet$ Update the generator by descending its stochastic gradient: $$ \nabla_{\theta_{g}}\frac{1}{m}\sum\limits_{i=1}^{m}\log\left(1-D\left(G\left(\bm{z}^{(i)}\right)\right)\right). $$
end for The gradient-based updates can use any standard gradient-based learning rule. We used momentum in our experiments.
```

## 4 Theoretical Results

The generator $G$ implicitly defines a probability distribution $p_{g}$ as the distribution of the samples $G(\bm{z})$ obtained when $\bm{z}\sim p_{\bm{z}}$. Therefore, we would like Algorithm 1 to converge to a good estimator of $p_{\text{data}}$, if given enough capacity and training time. The results of this section are done in a non-parametric setting, e.g. we represent a model with infinite capacity by studying convergence in the space of probability density functions.

We will show in section 4.1 that this minimax game has a global optimum for $p_{g}=p_{\text{data}}$. We will then show in section 4.2 that Algorithm 1 optimizes Eq 1, thus obtaining the desired result.

### 4.1 Global Optimality of $p_{g}=p_{\text{data}}$

We first consider the optimal discriminator $D$ for any given generator $G$.

#### Proposition 1.

For $G$ fixed, the optimal discriminator $D$ is

$$ D^{*}_{G}(\bm{x})=\frac{p_{\text{data}}(\bm{x})}{p_{\text{data}}(\bm{x})+p_{g}(\bm{x})} $$
(2)

#### Proof.

The training criterion for the discriminator D, given any generator $G$, is to maximize the quantity $V(G,D)$

$\displaystyle V(G,D)=$
$\displaystyle\int_{\bm{x}}p_{\text{data}}(\bm{x})\log(D(\bm{x}))dx+\int_{z}p_{\bm{z}}(\bm{z})\log(1-D(g(\bm{z})))dz$
$\displaystyle=$
$\displaystyle\int_{\bm{x}}p_{\text{data}}(\bm{x})\log(D(\bm{x}))+p_{g}(\bm{x})\log(1-D(\bm{x}))dx$
(3)

For any $(a,b)\in\mathbb{R}^{2}\setminus\{0,0\}$, the function $y\rightarrow a\log(y)+b\log(1-y)$ achieves its maximum in $[0,1]$ at $\frac{a}{a+b}$. The discriminator does not need to be defined outside of $Supp(p_{\text{data}})\cup Supp(p_{g})$, concluding the proof. ∎

Note that the training objective for $D$ can be interpreted as maximizing the log-likelihood for estimating the conditional probability $P(Y=y|\bm{x})$, where $Y$ indicates whether $\bm{x}$ comes from $p_{\text{data}}$ (with $y=1$) or from $p_{g}$ (with $y=0$). The minimax game in Eq. 1 can now be reformulated as:

$\displaystyle C(G)=$
$\displaystyle\max_{D}V(G,D)$
$\displaystyle=$
$\displaystyle\mathbb{E}_{\bm{x}\sim p_{\text{data}}}[\log D^{*}_{G}(\bm{x})]+\mathbb{E}_{\bm{z}\sim p_{\bm{z}}}[\log(1-D^{*}_{G}(G(\bm{z})))]$
(4)
$\displaystyle=$
$\displaystyle\mathbb{E}_{\bm{x}\sim p_{\text{data}}}[\log D^{*}_{G}(\bm{x})]+\mathbb{E}_{\bm{x}\sim p_{g}}[\log(1-D^{*}_{G}(\bm{x}))]$
$\displaystyle=$
$\displaystyle\mathbb{E}_{\bm{x}\sim p_{\text{data}}}\left[\log\frac{p_{\text{data}}(\bm{x})}{P_{\text{data}}(\bm{x})+p_{g}(\bm{x})}\right]+\mathbb{E}_{\bm{x}\sim p_{g}}\left[\log\frac{p_{g}(\bm{x})}{p_{\text{data}}(\bm{x})+p_{g}(\bm{x})}\right]$

#### Theorem 1.

The global minimum of the virtual training criterion $C(G)$ is achieved if and only if $p_{g}=p_{\text{data}}$. At that point, $C(G)$ achieves the value $-\log 4$.

#### Proof.

For $p_{g}=p_{\text{data}}$, $D^{*}_{G}(\bm{x})=\frac{1}{2}$, (consider Eq. 2). Hence, by inspecting Eq. 4 at $D^{*}_{G}(\bm{x})=\frac{1}{2}$, we find $C(G)=\log\frac{1}{2}+\log\frac{1}{2}=-\log 4$. To see that this is the best possible value of $C(G)$, reached only for $p_{g}=p_{\text{data}}$, observe that

$$ \mathbb{E}_{\bm{x}\sim p_{\text{data}}}\left[-\log 2\right]+\mathbb{E}_{\bm{x}\sim p_{g}}\left[-\log 2\right]=-\log 4 $$

and that by subtracting this expression from $C(G)=V(D_{G}^{*},G)$, we obtain:

$$ C(G)=-\log(4)+KL\left(p_{\text{data}}\left\|\frac{p_{\text{data}}+p_{g}}{2}\right.\right)+KL\left(p_{g}\left\|\frac{p_{\text{data}}+p_{g}}{2}\right.\right) $$
(5)

where KL is the Kullback–Leibler divergence. We recognize in the previous expression the Jensen–Shannon divergence between the model’s distribution and the data generating process:

$$ C(G)=-\log(4)+2\cdot JSD\left(p_{\text{data}}\left\|p_{g}\right.\right) $$
(6)

Since the Jensen–Shannon divergence between two distributions is always non-negative and zero only when they are equal, we have shown that $C^{*}=-\log(4)$ is the global minimum of $C(G)$ and that the only solution is $p_{g}=p_{\text{data}}$, i.e., the generative model perfectly replicating the data generating process. ∎

### 4.2 Convergence of Algorithm 1

#### Proposition 2.

If $G$ and $D$ have enough capacity, and at each step of Algorithm 1, the discriminator is allowed to reach its optimum given $G$, and $p_{g}$ is updated so as to improve the criterion

$$ \mathbb{E}_{\bm{x}\sim p_{\text{data}}}[\log D^{*}_{G}(\bm{x})]+\mathbb{E}_{\bm{x}\sim p_{g}}[\log(1-D^{*}_{G}(\bm{x}))] $$

then $p_{g}$ converges to $p_{\text{data}}$

#### Proof.

Consider $V(G,D)=U(p_{g},D)$ as a function of $p_{g}$ as done in the above criterion. Note that $U(p_{g},D)$ is convex in $p_{g}$. The subderivatives of a supremum of convex functions include the derivative of the function at the point where the maximum is attained. In other words, if $f(x)=\sup_{\alpha\in\cal{A}}f_{\alpha}(x)$ and $f_{\alpha}(x)$ is convex in $x$ for every $\alpha$, then $\partial f_{\beta}(x)\in\partial f$ if $\beta=\arg\sup_{\alpha\in\cal{A}}f_{\alpha}(x)$. This is equivalent to computing a gradient descent update for $p_{g}$ at the optimal $D$ given the corresponding $G$. $\sup_{D}U(p_{g},D)$ is convex in $p_{g}$ with a unique global optima as proven in Thm 1, therefore with sufficiently small updates of $p_{g}$, $p_{g}$ converges to $p_{x}$, concluding the proof. ∎

In practice, adversarial nets represent a limited family of $p_{g}$ distributions via the function $G(\bm{z};\theta_{g})$, and we optimize $\theta_{g}$ rather than $p_{g}$ itself. Using a multilayer perceptron to define $G$ introduces multiple critical points in parameter space. However, the excellent performance of multilayer perceptrons in practice suggests that they are a reasonable model to use despite their lack of theoretical guarantees.

## 5 Experiments

We trained adversarial nets an a range of datasets including MNIST[<sup>23</sup>], the Toronto Face Database (TFD) [<sup>28</sup>], and CIFAR-10 [<sup>21</sup>]. The generator nets used a mixture of rectifier linear activations [<sup>19, 9</sup>] and sigmoid activations, while the discriminator net used maxout [<sup>10</sup>] activations. Dropout [<sup>17</sup>] was applied in training the discriminator net. While our theoretical framework permits the use of dropout and other noise at intermediate layers of the generator, we used noise as the input to only the bottommost layer of the generator network.

We estimate probability of the test set data under $p_{g}$ by fitting a Gaussian Parzen window to the samples generated with $G$ and reporting the log-likelihood under this distribution. The $\sigma$ parameter of the Gaussians was obtained by cross validation on the validation set. This procedure was introduced in Breuleux et al. [8] and used for various generative models for which the exact likelihood is not tractable [<sup>25, 3, 5</sup>]. Results are reported in Table 1. This method of estimating the likelihood has somewhat high variance and does not perform well in high dimensional spaces but it is the best method available to our knowledge. Advances in generative models that can sample but not estimate likelihood directly motivate further research into how to evaluate such models.

**Table 1.** Parzen window-based log-likelihood estimates. The reported numbers on MNIST are the mean log-likelihood of samples on test set, with the standard error of the mean computed across examples. On TFD, we computed the standard error across folds of the dataset, with a different $\sigma$ chosen using the validation set of each fold. On TFD, $\sigma$ was cross validated on each fold and mean log-likelihood on each fold were computed. For MNIST we compare against other models of the real-valued (rather than binary) version of dataset.

| Model                       | MNIST               | TFD                   |
| --------------------------- | ------------------- | --------------------- |
| DBN [<sup>3</sup>] | $138\pm 2$ | $1909\pm 66$ |
| Stacked CAE [<sup>3</sup>] | $121\pm 1.6$ | $\mathbf{2110\pm 50}$ |
| Deep GSN [<sup>6</sup>] | $214\pm 1.1$ | $1890\pm 29$ |
| Adversarial nets            | $\mathbf{225\pm 2}$ | $\mathbf{2057\pm 26}$ |

In Figures 2 and 3 we show samples drawn from the generator net after training. While we make no claim that these samples are better than samples generated by existing methods, we believe that these samples are at least competitive with the better generative models in the literature and highlight the potential of the adversarial framework.

|                                                                        |                                                                        |
| ---------------------------------------------------------------------- | ---------------------------------------------------------------------- |
|

![Figure 2](1406.2661v1_assets/mnist_samples.png)

|

![Figure 2](1406.2661v1_assets/tfd_samples.png)

|
| a)                                                                     | b)                                                                     |
|

![Figure 2](1406.2661v1_assets/cifar_full_samples.png)

|

![Figure 2](1406.2661v1_assets/cifar_conv_samples.png)

|
| c)                                                                     | d)                                                                     |

![Figure 2](1406.2661v1_assets/mnist_samples.png)

![Figure 2](1406.2661v1_assets/tfd_samples.png)

![Figure 2](1406.2661v1_assets/cifar_full_samples.png)

![Figure 2](1406.2661v1_assets/cifar_conv_samples.png)

**Figure 2.** Visualization of samples from the model. Rightmost column shows the nearest training example of the neighboring sample, in order to demonstrate that the model has not memorized the training set. Samples are fair random draws, not cherry-picked. Unlike most other visualizations of deep generative models, these images show actual samples from the model distributions, not conditional means given samples of hidden units. Moreover, these samples are uncorrelated because the sampling process does not depend on Markov chain mixing. a) MNIST b) TFD c) CIFAR-10 (fully connected model) d) CIFAR-10 (convolutional discriminator and “deconvolutional” generator)

![Figure 3](1406.2661v1_assets/1dsubspace.png)

![Figure 3](1406.2661v1_assets/1dsubspace2.png)

![Figure 3](1406.2661v1_assets/1dsubspace.png)

![Figure 3](1406.2661v1_assets/1dsubspace2.png)

**Figure 3.** Digits obtained by linearly interpolating between coordinates in $\bm{z}$ space of the full model.

**Table 2.** Challenges in generative modeling: a summary of the difficulties encountered by different approaches to deep generative modeling for each of the major operations involving a model.

|                   | Deep directed graphical models             | Deep undirected graphical models                                                          | Generative autoencoders                                                        | Adversarial models                                                             |
| ----------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| Training          | Inference needed during training.          | Inference needed during training. MCMC needed to approximate partition function gradient. | Enforced tradeoff between mixing and power of reconstruction generation        | Synchronizing the discriminator with the generator. Helvetica.                 |
| Inference         | Learned approximate inference              | Variational inference                                                                     | MCMC-based inference                                                           | Learned approximate inference                                                  |
| Sampling          | No difficulties                            | Requires Markov chain                                                                     | Requires Markov chain                                                          | No difficulties                                                                |
| Evaluating $p(x)$ | Intractable, may be approximated with AIS  | Intractable, may be approximated with AIS                                                 | Not explicitly represented, may be approximated with Parzen density estimation | Not explicitly represented, may be approximated with Parzen density estimation |
| Model design      | Nearly all models incur extreme difficulty | Careful design needed to ensure multiple properties                                       | Any differentiable function is theoretically permitted                         | Any differentiable function is theoretically permitted                         |

## 6 Advantages and disadvantages

This new framework comes with advantages and disadvantages relative to previous modeling frameworks. The disadvantages are primarily that there is no explicit representation of $p_{g}(\bm{x})$, and that $D$ must be synchronized well with $G$ during training (in particular, $G$ must not be trained too much without updating $D$, in order to avoid “the Helvetica scenario” in which $G$ collapses too many values of $\mathbf{z}$ to the same value of $\mathbf{x}$ to have enough diversity to model $p_{\text{data}}$), much as the negative chains of a Boltzmann machine must be kept up to date between learning steps. The advantages are that Markov chains are never needed, only backprop is used to obtain gradients, no inference is needed during learning, and a wide variety of functions can be incorporated into the model. Table 2 summarizes the comparison of generative adversarial nets with other generative modeling approaches.

The aforementioned advantages are primarily computational. Adversarial models may also gain some statistical advantage from the generator network not being updated directly with data examples, but only with gradients flowing through the discriminator. This means that components of the input are not copied directly into the generator’s parameters. Another advantage of adversarial networks is that they can represent very sharp, even degenerate distributions, while methods based on Markov chains require that the distribution be somewhat blurry in order for the chains to be able to mix between modes.

## 7 Conclusions and future work

This framework admits many straightforward extensions:

1. A conditional generative model $p(\bm{x}\mid\bm{c})$ can be obtained by adding $\bm{c}$ as input to both $G$ and $D$.
2. Learned approximate inference can be performed by training an auxiliary network to predict $\bm{z}$ given $\bm{x}$. This is similar to the inference net trained by the wake-sleep algorithm [<sup>15</sup>] but with the advantage that the inference net may be trained for a fixed generator net after the generator net has finished training.
3. One can approximately model all conditionals $p(\bm{x}_{S}\mid\bm{x}_{\not S})$ where $S$ is a subset of the indices of $\bm{x}$ by training a family of conditional models that share parameters. Essentially, one can use adversarial nets to implement a stochastic extension of the deterministic MP-DBM [<sup>11</sup>].
4. Semi-supervised learning: features from the discriminator or inference net could improve performance of classifiers when limited labeled data is available.
5. Efficiency improvements: training could be accelerated greatly by divising better methods for coordinating $G$ and $D$ or determining better distributions to sample $\mathbf{z}$ from during training.

This paper has demonstrated the viability of the adversarial modeling framework, suggesting that these research directions could prove useful.

## References (31 total, showing 31)

[1] Bastien, F., Lamblin, P., Pascanu, R., Bergstra, J., Goodfellow, I. J.,
Bergeron, A., Bouchard, N., and Bengio, Y. (2012). Theano: new features and speed improvements. Deep Learning and Unsupervised Feature Learning NIPS 2012 Workshop.
[2] Bengio, Y. (2009). Learning deep architectures for AI. Now Publishers.
[3] Bengio, Y., Mesnil, G., Dauphin, Y., and Rifai, S. (2013a). Better mixing via deep representations. In ICML’13.
[4] Bengio, Y., Yao, L., Alain, G., and Vincent, P. (2013b). Generalized denoising auto-encoders as generative models. In NIPS26. Nips Foundation.
[5] Bengio, Y., Thibodeau-Laufer, E., and Yosinski, J. (2014a). Deep generative stochastic networks trainable by backprop. In ICML’14.
[6] Bengio, Y., Thibodeau-Laufer, E., Alain, G., and Yosinski, J. (2014b). Deep generative stochastic networks trainable by backprop. In Proceedings of the 30th International Conference on Machine
Learning (ICML’14).
[7] Bergstra, J., Breuleux, O., Bastien, F., Lamblin, P., Pascanu, R., Desjardins,
G., Turian, J., Warde-Farley, D., and Bengio, Y. (2010). Theano: a CPU and GPU math expression compiler. In Proceedings of the Python for Scientific Computing Conference
(SciPy). Oral Presentation.
[8] Breuleux, O., Bengio, Y., and Vincent, P. (2011). Quickly generating representative samples from an RBM-derived
process. Neural Computation, 23 (8), 2053–2073.
[9] Glorot, X., Bordes, A., and Bengio, Y. (2011). Deep sparse rectifier neural networks. In AISTATS’2011.
[10] Goodfellow, I. J., Warde-Farley, D., Mirza, M., Courville, A., and Bengio, Y.
(2013a). Maxout networks. In ICML’2013.
[11] Goodfellow, I. J., Mirza, M., Courville, A., and Bengio, Y. (2013b). Multi-prediction deep Boltzmann machines. In NIPS’2013.
[12] Goodfellow, I. J., Warde-Farley, D., Lamblin, P., Dumoulin, V., Mirza, M.,
Pascanu, R., Bergstra, J., Bastien, F., and Bengio, Y. (2013c). Pylearn2: a machine learning research library. arXiv preprint arXiv:1308.4214.
[13] Gutmann, M. and Hyvarinen, A. (2010). Noise-contrastive estimation: A new estimation principle for
unnormalized statistical models. In AISTATS’2010.
[14] Hinton, G., Deng, L., Dahl, G. E., Mohamed, A., Jaitly, N., Senior, A.,
Vanhoucke, V., Nguyen, P., Sainath, T., and Kingsbury, B. (2012a). Deep neural networks for acoustic modeling in speech recognition. IEEE Signal Processing Magazine, 29 (6), 82–97.
[15] Hinton, G. E., Dayan, P., Frey, B. J., and Neal, R. M. (1995). The wake-sleep algorithm for unsupervised neural networks. Science, 268, 1558–1161.
[16] Hinton, G. E., Osindero, S., and Teh, Y. (2006). A fast learning algorithm for deep belief nets. Neural Computation, 18, 1527–1554.
[17] Hinton, G. E., Srivastava, N., Krizhevsky, A., Sutskever, I., and
Salakhutdinov, R. (2012b). Improving neural networks by preventing co-adaptation of feature
detectors. Technical report, arXiv:1207.0580.
[18] Hyvärinen, A. (2005). Estimation of non-normalized statistical models using score matching. J. Machine Learning Res., 6.
[19] Jarrett, K., Kavukcuoglu, K., Ranzato, M., and LeCun, Y. (2009). What is the best multi-stage architecture for object recognition? In Proc. International Conference on Computer Vision
(ICCV’09), pages 2146–2153. IEEE.
[20] Kingma, D. P. and Welling, M. (2014). Auto-encoding variational bayes. In Proceedings of the International Conference on Learning
Representations (ICLR).
[21] Krizhevsky, A. and Hinton, G. (2009). Learning multiple layers of features from tiny images. Technical report, University of Toronto.
[22] Krizhevsky, A., Sutskever, I., and Hinton, G. (2012). ImageNet classification with deep convolutional neural networks. In NIPS’2012.
[23] LeCun, Y., Bottou, L., Bengio, Y., and Haffner, P. (1998). Gradient-based learning applied to document recognition. Proceedings of the IEEE, 86 (11), 2278–2324.
[24] Rezende, D. J., Mohamed, S., and Wierstra, D. (2014). Stochastic backpropagation and approximate inference in deep
generative models. Technical report, arXiv:1401.4082.
[25] Rifai, S., Bengio, Y., Dauphin, Y., and Vincent, P. (2012). A generative process for sampling contractive auto-encoders. In ICML’12.
[26] Salakhutdinov, R. and Hinton, G. E. (2009). Deep Boltzmann machines. In AISTATS’2009, pages 448–455.
[27] Smolensky, P. (1986). Information processing in dynamical systems: Foundations of harmony
theory. In D. E. Rumelhart and J. L. McClelland, editors, Parallel
Distributed Processing, volume 1, chapter 6, pages 194–281. MIT Press,
Cambridge.
[28] Susskind, J., Anderson, A., and Hinton, G. E. (2010). The Toronto face dataset. Technical Report UTML TR 2010-001, U. Toronto.
[29] Tieleman, T. (2008). Training restricted Boltzmann machines using approximations to the
likelihood gradient. In W. W. Cohen, A. McCallum, and S. T. Roweis, editors, ICML
2008, pages 1064–1071. ACM.
[30] Vincent, P., Larochelle, H., Bengio, Y., and Manzagol, P.-A. (2008). Extracting and composing robust features with denoising autoencoders. In ICML 2008.
[31] Younes, L. (1999). On the convergence of Markovian stochastic algorithms with rapidly
decreasing ergodicity rates. Stochastics and Stochastic Reports, 65 (3), 177–228.
