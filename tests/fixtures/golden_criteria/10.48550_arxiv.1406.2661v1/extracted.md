---
title: "Generative Adversarial Networks"
authors: "Ian J. Goodfellow, Jean Pouget-Abadie, Mehdi Mirza, Bing Xu, David Warde-Farley, Sherjil Ozair, Aaron Courville, Yoshua Bengio"
journal: "arXiv"
doi: "10.48550/arxiv.1406.2661v1"
published: "2014-06-10"
source: "arxiv_pdf"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 8314
---

# Generative Adversarial Networks

# **Generative Adversarial Nets** 

**Ian J. Goodfellow, Jean Pouget-Abadie**<sup>_∗_</sup> **, Mehdi Mirza, Bing Xu, David Warde-Farley, Sherjil Ozair**<sup>_†_</sup> **, Aaron Courville, Yoshua Bengio**<sup>_‡_</sup> D´epartement d’informatique et de recherche op´erationnelle Universit´e de Montr´eal Montr´eal, QC H3C 3J7 

## **Abstract** 

We propose a new framework for estimating generative models via an adversarial process, in which we simultaneously train two models: a generative model _G_ that captures the data distribution, and a discriminative model _D_ that estimates the probability that a sample came from the training data rather than _G_ . The training procedure for _G_ is to maximize the probability of _D_ making a mistake. This framework corresponds to a minimax two-player game. In the space of arbitrary functions _G_ and _D_ , a unique solution exists, with _G_ recovering the training data distribution and _D_ equal to 2<sup><u>1</u>everywhere.In the case where</sup><sup>_G_and</sup><sup>_D_are defined</sup> by multilayer perceptrons, the entire system can be trained with backpropagation. There is no need for any Markov chains or unrolled approximate inference networks during either training or generation of samples. Experiments demonstrate the potential of the framework through qualitative and quantitative evaluation of the generated samples. 

## **1 Introduction** 

The promise of deep learning is to discover rich, hierarchical models [2] that represent probability distributions over the kinds of data encountered in artificial intelligence applications, such as natural images, audio waveforms containing speech, and symbols in natural language corpora. So far, the most striking successes in deep learning have involved discriminative models, usually those that map a high-dimensional, rich sensory input to a class label [14, 22]. These striking successes have primarily been based on the backpropagation and dropout algorithms, using piecewise linear units [19, 9, 10] which have a particularly well-behaved gradient . Deep _generative_ models have had less of an impact, due to the difficulty of approximating many intractable probabilistic computations that arise in maximum likelihood estimation and related strategies, and due to difficulty of leveraging the benefits of piecewise linear units in the generative context. We propose a new generative model estimation procedure that sidesteps these difficulties.<sup>1</sup> 

In the proposed _adversarial nets_ framework, the generative model is pitted against an adversary: a discriminative model that learns to determine whether a sample is from the model distribution or the data distribution. The generative model can be thought of as analogous to a team of counterfeiters, trying to produce fake currency and use it without detection, while the discriminative model is analogous to the police, trying to detect the counterfeit currency. Competition in this game drives both teams to improve their methods until the counterfeits are indistiguishable from the genuine articles. 

> _∗_ Jean Pouget-Abadie is visiting Universit´e de Montr´eal from Ecole Polytechnique. 

> _†_ Sherjil Ozair is visiting Universit´e de Montr´eal from Indian Institute of Technology Delhi 

> _‡_ Yoshua Bengio is a CIFAR Senior Fellow. 

> 1All code and hyperparameters available at http://www.github.com/goodfeli/adversarial 

1 

This framework can yield specific training algorithms for many kinds of model and optimization algorithm. In this article, we explore the special case when the generative model generates samples by passing random noise through a multilayer perceptron, and the discriminative model is also a multilayer perceptron. We refer to this special case as _adversarial nets_ . In this case, we can train both models using only the highly successful backpropagation and dropout algorithms [17] and sample from the generative model using only forward propagation. No approximate inference or Markov chains are necessary. 

## **2 Related work** 

An alternative to directed graphical models with latent variables are undirected graphical models with latent variables, such as restricted Boltzmann machines (RBMs) [27, 16], deep Boltzmann machines (DBMs) [26] and their numerous variants. The interactions within such models are represented as the product of unnormalized potential functions, normalized by a global summation/integration over all states of the random variables. This quantity (the _partition function_ ) and its gradient are intractable for all but the most trivial instances, although they can be estimated by Markov chain Monte Carlo (MCMC) methods. Mixing poses a significant problem for learning algorithms that rely on MCMC [3, 5]. 

Deep belief networks (DBNs) [16] are hybrid models containing a single undirected layer and several directed layers. While a fast approximate layer-wise training criterion exists, DBNs incur the computational difficulties associated with both undirected and directed models. 

Alternative criteria that do not approximate or bound the log-likelihood have also been proposed, such as score matching [18] and noise-contrastive estimation (NCE) [13]. Both of these require the learned probability density to be analytically specified up to a normalization constant. Note that in many interesting generative models with several layers of latent variables (such as DBNs and DBMs), it is not even possible to derive a tractable unnormalized probability density. Some models such as denoising auto-encoders [30] and contractive autoencoders have learning rules very similar to score matching applied to RBMs. In NCE, as in this work, a discriminative training criterion is employed to fit a generative model. However, rather than fitting a separate discriminative model, the generative model itself is used to discriminate generated data from samples a fixed noise distribution. Because NCE uses a fixed noise distribution, learning slows dramatically after the model has learned even an approximately correct distribution over a small subset of the observed variables. 

Finally, some techniques do not involve defining a probability distribution explicitly, but rather train a generative machine to draw samples from the desired distribution. This approach has the advantage that such machines can be designed to be trained by back-propagation. Prominent recent work in this area includes the generative stochastic network (GSN) framework [5], which extends generalized denoising auto-encoders [4]: both can be seen as defining a parameterized Markov chain, i.e., one learns the parameters of a machine that performs one step of a generative Markov chain. Compared to GSNs, the adversarial nets framework does not require a Markov chain for sampling. Because adversarial nets do not require feedback loops during generation, they are better able to leverage piecewise linear units [19, 9, 10], which improve the performance of backpropagation but have problems with unbounded activation when used ina feedback loop. More recent examples of training a generative machine by back-propagating into it include recent work on auto-encoding variational Bayes [20] and stochastic backpropagation [24]. 

## **3 Adversarial nets** 

The adversarial modeling framework is most straightforward to apply when the models are both multilayer perceptrons. To learn the generator’s distribution _pg_ over data **_x_** , we define a prior on input noise variables _p_ **_z_** ( **_z_** ), then represent a mapping to data space as _G_ ( **_z_** ; _θg_ ), where _G_ is a differentiable function represented by a multilayer perceptron with parameters _θg_ . We also define a second multilayer perceptron _D_ ( **_x_** ; _θd_ ) that outputs a single scalar. _D_ ( **_x_** ) represents the probability that **_x_** came from the data rather than _pg_ . We train _D_ to maximize the probability of assigning the correct label to both training examples and samples from _G_ . We simultaneously train _G_ to minimize log(1 _− D_ ( _G_ ( **_z_** ))): 

2 

In other words, _D_ and _G_ play the following two-player minimax game with value function _V_ ( _G, D_ ): 



<!-- Start of picture text -->
min G max D V  ( D, G ) = E x ∼p data( x )[log  D ( x )] + E z ∼p z ( z )[log(1  − D ( G ( z )))] . (1)<br><!-- End of picture text -->

In the next section, we present a theoretical analysis of adversarial nets, essentially showing that the training criterion allows one to recover the data generating distribution as _G_ and _D_ are given enough capacity, i.e., in the non-parametric limit. See Figure 1 for a less formal, more pedagogical explanation of the approach. In practice, we must implement the game using an iterative, numerical approach. Optimizing _D_ to completion in the inner loop of training is computationally prohibitive, and on finite datasets would result in overfitting. Instead, we alternate between _k_ steps of optimizing _D_ and one step of optimizing _G_ . This results in _D_ being maintained near its optimal solution, so long as _G_ changes slowly enough. This strategy is analogous to the way that SML/PCD [31, 29] training maintains samples from a Markov chain from one learning step to the next in order to avoid burning in a Markov chain as part of the inner loop of learning. The procedure is formally presented in Algorithm 1. 

In practice, equation 1 may not provide sufficient gradient for _G_ to learn well. Early in learning, when _G_ is poor, _D_ can reject samples with high confidence because they are clearly different from the training data. In this case, log(1 _− D_ ( _G_ ( **_z_** ))) saturates. Rather than training _G_ to minimize log(1 _− D_ ( _G_ ( **_z_** ))) we can train _G_ to maximize log _D_ ( _G_ ( **_z_** )). This objective function results in the same fixed point of the dynamics of _G_ and _D_ but provides much stronger gradients early in learning. 



<!-- Start of picture text -->
...<br>x<br>z<br>(a) (b) (c) (d)<br><!-- End of picture text -->

Figure 1: Generative adversarial nets are trained by simultaneously updating the **d** iscriminative distribution ( _D_ , blue, dashed line) so that it discriminates between samples from the data generating distribution (black, dotted line) _p_ **_x_** from those of the **g** enerative distribution _pg_ (G) (green, solid line). The lower horizontal line is the domain from which **_z_** is sampled, in this case uniformly. The horizontal line above is part of the domain of **_x_** . The upward arrows show how the mapping **_x_** = _G_ ( **_z_** ) imposes the non-uniform distribution _pg_ on transformed samples. _G_ contracts in regions of high density and expands in regions of low density of _pg_ . (a) Consider an adversarial pair near convergence: _pg_ is similar to _p_ data and _D_ is a partially accurate classifier. (b) In the inner loop of the algorithm _D_ is trained to discriminate samples from data, converging to _D_<sup>_∗_</sup> ( **_x_** ) = _p_ data _<u>p</u>_ ( **_x_** <u>data)+(</u> **_x_** _p_ <u>)</u> _g_ ( **_x_** )<sup>.(c) After an update to</sup><sup>_G_, gradient of</sup><sup>_D_has guided</sup><sup>_G_(</sup><sup>**_z_**) to flow to regions that are more likely</sup> to be classified as data. (d) After several steps of training, if _G_ and _D_ have enough capacity, they will reach a point at which both cannot improve because _pg_ = _p_ data. The discriminator is unable to differentiate between the two distributions, i.e. _D_ ( **_x_** ) = 2<sup><u>1</u>.</sup> 

## **4 Theoretical Results** 

The generator _G_ implicitly defines a probability distribution _pg_ as the distribution of the samples _G_ ( **_z_** ) obtained when **_z_** _∼ p_ **_z_** . Therefore, we would like Algorithm 1 to converge to a good estimator of _p_ data, if given enough capacity and training time. The results of this section are done in a nonparametric setting, e.g. we represent a model with infinite capacity by studying convergence in the space of probability density functions. 

We will show in section 4.1 that this minimax game has a global optimum for _pg_ = _p_ data. We will then show in section 4.2 that Algorithm 1 optimizes Eq 1, thus obtaining the desired result. 

3 

**Algorithm 1** Minibatch stochastic gradient descent training of generative adversarial nets. The number of steps to apply to the discriminator, _k_ , is a hyperparameter. We used _k_ = 1, the least expensive option, in our experiments. 

- **for** number of training iterations **do for** _k_ steps **do** 

   - Sample minibatch of _m_ noise samples _{_ **_z_**<sup>(1)</sup> _, . . . ,_ **_z_**<sup>(</sup><sup>_m_)</sup> _}_ from noise prior _pg_ ( **_z_** ). 

   - Sample minibatch of _m_ examples _{_ **_x_**<sup>(1)</sup> _, . . . ,_ **_x_**<sup>(</sup><sup>_m_)</sup> _}_ from data generating distribution 

   - _p_ data( **_x_** ). 

   - Update the discriminator by ascending its stochastic gradient: 



<!-- Start of picture text -->
1 m<br>∇θd m � �log  D � x ( i )� + log �1  − D � G � z ( i )���� .<br>i =1<br><!-- End of picture text -->

### **end for** 

- Sample minibatch of _m_ noise samples _{_ **_z_**<sup>(1)</sup> _, . . . ,_ **_z_**<sup>(</sup><sup>_m_)</sup> _}_ from noise prior _pg_ ( **_z_** ). 

- Update the generator by descending its stochastic gradient: 



<!-- Start of picture text -->
1 m<br>∇θg m � log �1  − D � G � z ( i )��� .<br>i =1<br><!-- End of picture text -->

### **end for** 

The gradient-based updates can use any standard gradient-based learning rule. We used momentum in our experiments. 

### **4.1 Global Optimality of** _pg_ = _p_ **data** 

We first consider the optimal discriminator _D_ for any given generator _G_ . **Proposition 1.** _For G fixed, the optimal discriminator D is_ 



<!-- Start of picture text -->
pdata ( x )<br>DG ∗ ( x ) = (2)<br>pdata ( x ) +  pg ( x )<br><!-- End of picture text -->

_Proof._ The training criterion for the discriminator D, given any generator _G_ , is to maximize the quantity _V_ ( _G, D_ ) 



<!-- Start of picture text -->
V  ( G, D ) = p data( x ) log( D ( x )) dx  + p z ( z ) log(1  − D ( g ( z ))) dz<br>� x � z<br>=<br>p data( x ) log( D ( x )) +  pg ( x ) log(1  − D ( x )) dx (3)<br>� x<br><!-- End of picture text -->

For any ( _a, b_ ) _∈_ R<sup>2</sup> _\ {_ 0 _,_ 0 _}_ , the function _y → a_ log( _y_ ) + _b_ log(1 _− y_ ) achieves its maximum in [0 _,_ 1] at _a_ + _<u>a</u> b_<sup>.Thediscriminatordoesnotneedtobedefinedoutsideof</sup><sup>_Supp_(</sup><sup>_p_data)</sup><sup>_∪Supp_(</sup><sup>_pg_),</sup> concluding the proof. 

Note that the training objective for _D_ can be interpreted as maximizing the log-likelihood for estimating the conditional probability _P_ ( _Y_ = _y|_ **_x_** ), where _Y_ indicates whether **_x_** comes from _p_ data (with _y_ = 1) or from _pg_ (with _y_ = 0). The minimax game in Eq. 1 can now be reformulated as: 



<!-- Start of picture text -->
C ( G ) = max D V  ( G, D )<br>=E x ∼p data[log  DG ∗ ( x )] + E z ∼p z [log(1  − D G ∗ ( G ( z )))] (4)<br>=E x ∼p data[log  DG ∗ ( x )] + E x ∼p g [log(1  − D G ∗ ( x ))]<br>p data( x ) pg ( x )<br>=E x ∼p data log + E x ∼pg log<br>� P data( x ) +  pg ( x ) � � p data( x ) +  pg ( x ) �<br><!-- End of picture text -->

4 

**Theorem 1.** _The global minimum of the virtual training criterion C_ ( _G_ ) _is achieved if and only if pg_ = _pdata. At that point, C_ ( _G_ ) _achieves the value −_ log 4 _._ 

_Proof._ For _pg_ = _p_ data, _DG_<sup>_∗_(</sup><sup>**_x_**) =</sup><sup><u>1</u></sup> 2<sup>, (consider Eq. 2).Hence, by inspecting Eq. 4 at</sup><sup>_D_</sup> _G_<sup>_∗_(</sup><sup>**_x_**) =</sup><sup><u>1</u></sup> 2<sup>, we</sup> find _C_ ( _G_ ) = log<sup><u>1</u></sup> 2<sup>+ log</sup> 2<sup><u>1</u>=</sup><sup>_−_log 4.To see that this is the best possible value of</sup><sup>_C_(</sup><sup>_G_), reached</sup> only for _pg_ = _p_ data, observe that 



<!-- Start of picture text -->
E x ∼p data [ − log 2] + E x ∼pg  [ − log 2] =  − log 4<br><!-- End of picture text -->

and that by subtracting this expression from _C_ ( _G_ ) = _V_ ( _DG_<sup>_∗, G_), we obtain:</sup> 



<!-- Start of picture text -->
p data + pg p data + pg<br>C ( G ) =  − log(4) +  KL p data +  KL pg (5)<br>� ���� 2 � � ���� 2 �<br><!-- End of picture text -->

where KL is the Kullback–Leibler divergence. We recognize in the previous expression the Jensen– Shannon divergence between the model’s distribution and the data generating process: 



<!-- Start of picture text -->
C ( G ) =  − log(4) + 2  · JSD  ( p data  ∥pg  ) (6)<br><!-- End of picture text -->

Since the Jensen–Shannon divergence between two distributions is always non-negative and zero only when they are equal, we have shown that _C_<sup>_∗_</sup> = _−_ log(4) is the global minimum of _C_ ( _G_ ) and that the only solution is _pg_ = _p_ data, i.e., the generative model perfectly replicating the data generating process. 

### **4.2 Convergence of Algorithm 1** 

**Proposition 2.** _If G and D have enough capacity, and at each step of Algorithm 1, the discriminator is allowed to reach its optimum given G, and pg is updated so as to improve the criterion_ 



<!-- Start of picture text -->
E x ∼pdata [log  DG ∗ ( x )] + E x ∼p g [log(1  − D G ∗ ( x ))]<br><!-- End of picture text -->

_then pg converges to pdata_ 

_Proof._ Consider _V_ ( _G, D_ ) = _U_ ( _pg, D_ ) as a function of _pg_ as done in the above criterion. Note that _U_ ( _pg, D_ ) is convex in _pg_ . The subderivatives of a supremum of convex functions include the derivative of the function at the point where the maximum is attained. In other words, if _f_ ( _x_ ) = sup _α∈A fα_ ( _x_ ) and _fα_ ( _x_ ) is convex in _x_ for every _α_ , then _∂fβ_ ( _x_ ) _∈ ∂f_ if _β_ = arg sup _α∈A fα_ ( _x_ ). This is equivalent to computing a gradient descent update for _pg_ at the optimal _D_ given the corresponding _G_ . sup _D U_ ( _pg, D_ ) is convex in _pg_ with a unique global optima as proven in Thm 1, therefore with sufficiently small updates of _pg_ , _pg_ converges to _px_ , concluding the proof. 

In practice, adversarial nets represent a limited family of _pg_ distributions via the function _G_ ( **_z_** ; _θg_ ), and we optimize _θg_ rather than _pg_ itself. Using a multilayer perceptron to define _G_ introduces multiple critical points in parameter space. However, the excellent performance of multilayer perceptrons in practice suggests that they are a reasonable model to use despite their lack of theoretical guarantees. 

## **5 Experiments** 

We trained adversarial nets an a range of datasets including MNIST[23], the Toronto Face Database (TFD) [28], and CIFAR-10 [21]. The generator nets used a mixture of rectifier linear activations [19, 9] and sigmoid activations, while the discriminator net used maxout [10] activations. Dropout [17] was applied in training the discriminator net. While our theoretical framework permits the use of dropout and other noise at intermediate layers of the generator, we used noise as the input to only the bottommost layer of the generator network. 

We estimate probability of the test set data under _pg_ by fitting a Gaussian Parzen window to the samples generated with _G_ and reporting the log-likelihood under this distribution. The _σ_ parameter 

5 

|Model|MNIST|TFD|
|---|---|---|
|DBN [3]|138_±_2|1909_±_66|
|Stacked CAE [3]|121_±_1_._6|**2110**_±_**50**|
|Deep GSN [6]|214_±_1_._1|1890_±_29|
|Adversarial nets|**225**_±_**2**|**2057**_±_**26**|



Table 1: Parzen window-based log-likelihood estimates. The reported numbers on MNIST are the mean loglikelihood of samples on test set, with the standard error of the mean computed across examples. On TFD, we computed the standard error across folds of the dataset, with a different _σ_ chosen using the validation set of each fold. On TFD, _σ_ was cross validated on each fold and mean log-likelihood on each fold were computed. For MNIST we compare against other models of the real-valued (rather than binary) version of dataset. 

of the Gaussians was obtained by cross validation on the validation set. This procedure was introduced in Breuleux _et al._ [8] and used for various generative models for which the exact likelihood is not tractable [25, 3, 5]. Results are reported in Table 1. This method of estimating the likelihood has somewhat high variance and does not perform well in high dimensional spaces but it is the best method available to our knowledge. Advances in generative models that can sample but not estimate likelihood directly motivate further research into how to evaluate such models. 

In Figures 2 and 3 we show samples drawn from the generator net after training. While we make no claim that these samples are better than samples generated by existing methods, we believe that these samples are at least competitive with the better generative models in the literature and highlight the potential of the adversarial framework. 







<!-- Start of picture text -->
a) b)<br>c) d)<br><!-- End of picture text -->

Figure 2: Visualization of samples from the model. Rightmost column shows the nearest training example of the neighboring sample, in order to demonstrate that the model has not memorized the training set. Samples are fair random draws, not cherry-picked. Unlike most other visualizations of deep generative models, these images show actual samples from the model distributions, not conditional means given samples of hidden units. Moreover, these samples are uncorrelated because the sampling process does not depend on Markov chain mixing. a) MNIST b) TFD c) CIFAR-10 (fully connected model) d) CIFAR-10 (convolutional discriminator and “deconvolutional” generator) 

6 





Figure 3: Digits obtained by linearly interpolating between coordinates in **_z_** space of the full model. 

||Deep directed<br>graphical models|Deep undirected<br>graphical models|Generative<br>autoencoders|Adversarial models|
|---|---|---|---|---|
|Training|Inference needed<br>during training.|Inference needed<br>during training.<br>MCMC needed to<br>approximate<br>partition function<br>gradient.|Enforced tradeoff<br>between mixing<br>and power of<br>reconstruction<br>generation|Synchronizing the<br>discriminator with<br>the generator.<br>Helvetica.|
|Inference|Learned<br>approximate<br>inference|Variational<br>inference|MCMC-based<br>inference|Learned<br>approximate<br>inference|
|Sampling|No difficulties|Requires Markov<br>chain|Requires Markov<br>chain|No difficulties|
|Evaluating_p_(_x_)|Intractable, may be<br>approximated with<br>AIS|Intractable, may be<br>approximated with<br>AIS|Not explicitly<br>represented, may be<br>approximated with<br>Parzen density<br>estimation|Not explicitly<br>represented, may be<br>approximated with<br>Parzen density<br>estimation|
|Model design|Nearly all models<br>incur extreme<br>difficulty|Careful design<br>needed to ensure<br>multiple properties|Any differentiable<br>function is<br>theoretically<br>permitted|Any differentiable<br>function is<br>theoretically<br>permitted|



Table 2: Challenges in generative modeling: a summary of the difficulties encountered by different approaches to deep generative modeling for each of the major operations involving a model. 

## **6 Advantages and disadvantages** 

This new framework comes with advantages and disadvantages relative to previous modeling frameworks. The disadvantages are primarily that there is no explicit representation of _pg_ ( **_x_** ), and that _D_ must be synchronized well with _G_ during training (in particular, _G_ must not be trained too much without updating _D_ , in order to avoid “the Helvetica scenario” in which _G_ collapses too many values of **z** to the same value of **x** to have enough diversity to model _p_ data), much as the negative chains of a Boltzmann machine must be kept up to date between learning steps. The advantages are that Markov chains are never needed, only backprop is used to obtain gradients, no inference is needed during learning, and a wide variety of functions can be incorporated into the model. Table 2 summarizes the comparison of generative adversarial nets with other generative modeling approaches. 

The aforementioned advantages are primarily computational. Adversarial models may also gain some statistical advantage from the generator network not being updated directly with data examples, but only with gradients flowing through the discriminator. This means that components of the input are not copied directly into the generator’s parameters. Another advantage of adversarial networks is that they can represent very sharp, even degenerate distributions, while methods based on Markov chains require that the distribution be somewhat blurry in order for the chains to be able to mix between modes. 

## **7 Conclusions and future work** 

This framework admits many straightforward extensions: 

> 1. A _conditional generative_ model _p_ ( **_x_** _|_ **_c_** ) can be obtained by adding **_c_** as input to both _G_ and _D_ . 2. _Learned approximate inference_ can be performed by training an auxiliary network to predict **_z_** given **_x_** . This is similar to the inference net trained by the wake-sleep algorithm [15] but with the advantage that the inference net may be trained for a fixed generator net after the generator net has finished training. 

7 

3. One can approximately model all conditionals _p_ ( **_x_** _S |_ **_x_** _̸S_ ) where _S_ is a subset of the indices of **_x_** by training a family of conditional models that share parameters. Essentially, one can use adversarial nets to implement a stochastic extension of the deterministic MP-DBM [11]. 

4. _Semi-supervised learning_ : features from the discriminator or inference net could improve performance of classifiers when limited labeled data is available. 

5. _Efficiency improvements:_ training could be accelerated greatly by divising better methods for coordinating _G_ and _D_ or determining better distributions to sample **z** from during training. 

This paper has demonstrated the viability of the adversarial modeling framework, suggesting that these research directions could prove useful. 

### **Acknowledgments** 

We would like to acknowledge Patrice Marcotte, Olivier Delalleau, Kyunghyun Cho, Guillaume Alain and Jason Yosinski for helpful discussions. Yann Dauphin shared his Parzen window evaluation code with us. We would like to thank the developers of Pylearn2 [12] and Theano [7, 1], particularly Fr´ed´eric Bastien who rushed a Theano feature specifically to benefit this project. Arnaud Bergeron provided much-needed support with L<sup>A</sup> TEX typesetting. We would also like to thank CIFAR, and Canada Research Chairs for funding, and Compute Canada, and Calcul Qu´ebec for providing computational resources. Ian Goodfellow is supported by the 2013 Google Fellowship in Deep Learning. Finally, we would like to thank Les Trois Brasseurs for stimulating our creativity. 

## **References** 

- [1] Bastien, F., Lamblin, P., Pascanu, R., Bergstra, J., Goodfellow, I. J., Bergeron, A., Bouchard, N., and Bengio, Y. (2012). Theano: new features and speed improvements. Deep Learning and Unsupervised Feature Learning NIPS 2012 Workshop. 

- [2] Bengio, Y. (2009). _Learning deep architectures for AI_ . Now Publishers. 

- [3] Bengio, Y., Mesnil, G., Dauphin, Y., and Rifai, S. (2013a). Better mixing via deep representations. In _ICML’13_ . 

- [4] Bengio, Y., Yao, L., Alain, G., and Vincent, P. (2013b). Generalized denoising auto-encoders as generative models. In _NIPS26_ . Nips Foundation. 

- [5] Bengio, Y., Thibodeau-Laufer, E., and Yosinski, J. (2014a). Deep generative stochastic networks trainable by backprop. In _ICML’14_ . 

- [6] Bengio, Y., Thibodeau-Laufer, E., Alain, G., and Yosinski, J. (2014b). Deep generative stochastic networks trainable by backprop. In _Proceedings of the 30th International Conference on Machine Learning (ICML’14)_ . 

- [7] Bergstra, J., Breuleux, O., Bastien, F., Lamblin, P., Pascanu, R., Desjardins, G., Turian, J., Warde-Farley, D., and Bengio, Y. (2010). Theano: a CPU and GPU math expression compiler. In _Proceedings of the Python for Scientific Computing Conference (SciPy)_ . Oral Presentation. 

- [8] Breuleux, O., Bengio, Y., and Vincent, P. (2011). Quickly generating representative samples from an RBM-derived process. _Neural Computation_ , **23** (8), 2053–2073. 

- [9] Glorot, X., Bordes, A., and Bengio, Y. (2011). Deep sparse rectifier neural networks. In _AISTATS’2011_ . 

- [10] Goodfellow, I. J., Warde-Farley, D., Mirza, M., Courville, A., and Bengio, Y. (2013a). Maxout networks. In _ICML’2013_ . 

- [11] Goodfellow, I. J., Mirza, M., Courville, A., and Bengio, Y. (2013b). Multi-prediction deep Boltzmann machines. In _NIPS’2013_ . 

- [12] Goodfellow, I. J., Warde-Farley, D., Lamblin, P., Dumoulin, V., Mirza, M., Pascanu, R., Bergstra, J., Bastien, F., and Bengio, Y. (2013c). Pylearn2: a machine learning research library. _arXiv preprint arXiv:1308.4214_ . 

- [13] Gutmann, M. and Hyvarinen, A. (2010). Noise-contrastive estimation: A new estimation principle for unnormalized statistical models. In _AISTATS’2010_ . 

- [14] Hinton, G., Deng, L., Dahl, G. E., Mohamed, A., Jaitly, N., Senior, A., Vanhoucke, V., Nguyen, P., Sainath, T., and Kingsbury, B. (2012a). Deep neural networks for acoustic modeling in speech recognition. _IEEE Signal Processing Magazine_ , **29** (6), 82–97. 

- [15] Hinton, G. E., Dayan, P., Frey, B. J., and Neal, R. M. (1995). The wake-sleep algorithm for unsupervised neural networks. _Science_ , **268** , 1558–1161. 

8 

- [16] Hinton, G. E., Osindero, S., and Teh, Y. (2006). A fast learning algorithm for deep belief nets. _Neural Computation_ , **18** , 1527–1554. 

- [17] Hinton, G. E., Srivastava, N., Krizhevsky, A., Sutskever, I., and Salakhutdinov, R. (2012b). Improving neural networks by preventing co-adaptation of feature detectors. Technical report, arXiv:1207.0580. 

- [18] Hyv¨arinen, A. (2005). Estimation of non-normalized statistical models using score matching. _J. Machine Learning Res._ , **6** . 

- [19] Jarrett, K., Kavukcuoglu, K., Ranzato, M., and LeCun, Y. (2009). What is the best multi-stage architecture for object recognition? In _Proc. International Conference on Computer Vision (ICCV’09)_ , pages 2146–2153. IEEE. 

- [20] Kingma, D. P. and Welling, M. (2014). Auto-encoding variational bayes. In _Proceedings of the International Conference on Learning Representations (ICLR)_ . 

- [21] Krizhevsky, A. and Hinton, G. (2009). Learning multiple layers of features from tiny images. Technical report, University of Toronto. 

- [22] Krizhevsky, A., Sutskever, I., and Hinton, G. (2012). ImageNet classification with deep convolutional neural networks. In _NIPS’2012_ . 

- [23] LeCun, Y., Bottou, L., Bengio, Y., and Haffner, P. (1998). Gradient-based learning applied to document recognition. _Proceedings of the IEEE_ , **86** (11), 2278–2324. 

- [24] Rezende, D. J., Mohamed, S., and Wierstra, D. (2014). Stochastic backpropagation and approximate inference in deep generative models. Technical report, arXiv:1401.4082. 

- [25] Rifai, S., Bengio, Y., Dauphin, Y., and Vincent, P. (2012). A generative process for sampling contractive auto-encoders. In _ICML’12_ . 

- [26] Salakhutdinov, R. and Hinton, G. E. (2009). Deep Boltzmann machines. In _AISTATS’2009_ , pages 448– 455. 

- [27] Smolensky, P. (1986). Information processing in dynamical systems: Foundations of harmony theory. In D. E. Rumelhart and J. L. McClelland, editors, _Parallel Distributed Processing_ , volume 1, chapter 6, pages 194–281. MIT Press, Cambridge. 

- [28] Susskind, J., Anderson, A., and Hinton, G. E. (2010). The Toronto face dataset. Technical Report UTML TR 2010-001, U. Toronto. 

- [29] Tieleman, T. (2008). Training restricted Boltzmann machines using approximations to the likelihood gradient. In W. W. Cohen, A. McCallum, and S. T. Roweis, editors, _ICML 2008_ , pages 1064–1071. ACM. 

- [30] Vincent, P., Larochelle, H., Bengio, Y., and Manzagol, P.-A. (2008). Extracting and composing robust features with denoising autoencoders. In _ICML 2008_ . 

- [31] Younes, L. (1999). On the convergence of Markovian stochastic algorithms with rapidly decreasing ergodicity rates. _Stochastics and Stochastic Reports_ , **65** (3), 177–228. 

9 



