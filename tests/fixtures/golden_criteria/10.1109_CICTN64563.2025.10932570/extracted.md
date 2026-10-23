---
title: "Deep Learning Based Model to Recommend Safe Route Navigation System"
authors: "Sourav Garg, Aashu Mittal, V Sathiyasuntharam"
journal: "2025 2nd International Conference on Computational Intelligence, Communication Technology and Networking (CICTN)"
doi: "10.1109/cictn64563.2025.10932570"
published: "06 February 2025"
source: "ieee_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 5452
---

# Deep Learning Based Model to Recommend Safe Route Navigation System

**Abstract.** The level of crime rates in practically every part of the world has risen to unprecedented levels. These are tough times that call for extreme methods to protect individuals, particularly those who must travel to unknown and known locations on a daily basis. Regardless of the mode of transportation used by the victim walking, driving one's own car, using a public transportation vehicle, autorickshaws, or taxis the majority of these crimes happen when the victim is traveling. This research suggests a Deep Learning Based Model To Recommend Safe Route Navigation System that shows the user a safe path shown on maps and based on the area's historical criminal history. Our approach is implemented in a hierarchical manner: a Decision Network is used to determine the user-specific attributes in the first place, and then that same Decision Network is used to activate the creation of safe routes via Geospatial Data Analysis. Users can view the navigated routes of the effective system as a colour coded map. Acknowledging that the real consequences which our research strive for should produce, we validated our model with specific data of San Francisco city for demonstrative purposes.

## Introduction

In today's society, the primary concern for most parents is sending their children to school. Walking down the street at night for ladies is fraught with danger owing to eve-teasers and ruffians. Moreover, there is a tendency for families to prefer staying indoors than going out owing to the rampant abuse of alcohol and the dangerous elements on the streets. Crime affects everybody and everything, and that is a sad reality. With an increment in crime, despair and anxiety creep in every people’s life. In most of such cases, the police simply do not reach or do not want to reach out to the problems that matter most in the specific society and remain distant, which creates insecurity.

The authorities tend to minimize the issues and appear as though they are unaware that chaos and violence are now commonplace in many areas. Anyone who has access to trustworthy crime data will be able to see the urgent need for a compact, easy-to-use solution that allows users to see the safest route for their transit while accounting for factors like age, gender, and time of day to ensure that each user's needs are met.

A system that recommends safe places employs prediction techniques and data modelling, algorithms, mathematical inference among others, to make informed assessments about a given route and or statistically prove that the route reduces the chances of becoming a victim of crime. Such a system's effectiveness is crucial as it frequently results in situations where life or death is at stake.

Given the average level of interpretive ability among users, the anticipated route visualization is equally important. After all, any safety-based program need to be widely accessible, utilized by everyone who can profit from it, and help them live better lives.

## LITERATURE REVIEW

The publication of a report measuring the path taking the lowest risk score is already out. They averaged the risk level of crime or incident occurrences across clusters and utilized openly available data on accidents and crimes from the NYC Open Data initiative. Their approach was based on artificial intelligence techniques including K Means Clustering and KNN Regressor, which were used to assign risk scores on each given path<sup>1</sup>.

In an attempt to determine the safest path, another article tried data mining using regionally sorted datasets spanning more than 12 years. The ID3 Decision Tree approach was used in identifying the user's risk based on a range of factors including the user's age and gender. The age and gender characteristics that were included in the model were only used to perform selective data extraction and were not added in the prediction model<sup>2</sup>.

Be-Safe Travel is another similar application that can be categorized under recommendation systems that developed an online platform by integrating Google APIs, PHP hypertext preprocessor and MySQL databases. Their model indicates that the path with the fewest crime points is the safest one. Data from Surabaya City is the foundation of their model. Additionally, it has the ability to rank up to three routes and assign a color to each one to indicate the degree of security<sup>3</sup>.

A different paper introduced SAFEBIKE, which suggests bike-sharing service routes based on variables including safety and distance. The system additionally displays the quantity of bikes and docking stations that are available, in line with its basic function. Take into consideration the factors of crime and safety when planning travel routes ensures that the user has a more enjoyable travel experience<sup>4</sup>.

Another study also described the development of a risk model for the urban street networks of Chicago and Philadelphia. This makes it possible to calculate the relative likelihood of criminal activity on any given route segment. The objective of their model was to produce a path that is both safe and short, but instead of attaining both at once, it produces paths that strike a compromise between the two parameters<sup>5</sup>.

In an application for mobile devices was employed to merge official crime statistics with crowdsourced generated information; producing a solution based on Bayes Algorithm. The published work presents a model which solves the problem of safe route mapping and crime prediction mainly based on information obtained from twitter by combining semantic processing with classification techniques, while also leveraging a collection of relevant tweets<sup>6</sup>.

SB Oh et al. suggested a methodology in which the user’s trip day and timing is considered. To estimate the risk level for the whole route, they based the crime risk levels of particular landmarks and summed up the risk levels of the landmarks along a route. The risk level index was determined for each facility on a scale of 1 to 10 based on the assessment of five distinct categories of crime<sup>7</sup>.

In<sup>8</sup>, two authors detailed their approach to safe route selection algorithms for autonomous vehicles. It is understood that the vehicles are connected to the cloud based network. In fully autonomous driving mode, a safe path gets synthesized by utilizing in-car sensors, previous real-world crash data and other traffic related big data information. In addition, the user is provided with a fully detailed itinerary which covers the length of the trip, the distance to be traversed, and the total amount of fuel that would be expended which is also determined by the traveller’s preferences.

Moreover, Nima Hoseinzadeh et al.<sup>9</sup> suggested using large data produced by cloud-connected automobiles. They use volatility as a crude concept to measure driver behaviour and road safety. To generate safety indices, real-time traffic data from the cars is supplied into the framework together with other relevant big data. The driver's five-year collision history, average speed along the route, acceleration volatility, and driver volatility are regarded as the main indices. To choose the best route, they employ a cost function called route impedance that is calculated using a mix of travel time and safety. Additionally, weights can be assigned dynamically according to user choices.

## FINDINGS AND CHALLENGES

Today’s applications will direct a user to the nearest distance from point A to B but they do not indicate the safety score of that distance thereby making one end up in desolate and dark places. Such locations predispose them to offenders and have led to various crimes such as carjackings, sexual assaults, and thefts.

A key idea in the current systems and the articles examined is that the crime rate has a direct correlation with the deterrent effect of punishment assigned to that crime. The crime-factor grows when the seriousness of the offense committed rises.

To create a safer navigation experience for the user and even alert the user of potentially troublesome areas, our application goes one step ahead of the simple route safety visualization by incorporating the past criminal records of the users' routes and crimes’ intensity level weighted by users’ specific attributes such as Longitude, Latitude, Time and Location of the Crime committed.

The majority of the work that is now available only considers women's safety and only includes information on the gender of the users. Furthermore, the methods only produce a single safe path, offering the user no other options. There isn't an alerting mechanism in any of the current systems to alert users to potentially unsafe regions while they're traveling.

## DATASET DESCRIPTION

In order to assess the risk level of a user, we make use of the FBI UCR<sup>15</sup> database, which has suitably enriched equalized records of victims for crime studies, and that jurisdictions have adopted it for more than 15 years.

We use the San Francisco dataset, which has recorded crime occurrences over a 12-year period, for the algorithm's route profiling step. We evaluate the type of crime that was reported as well as the incident's geographic location. These offenses include everything from minor moving infractions to violence and attempted murder. Every occurrence that happened in the city throughout a 12-year period is taken into account in the dataset.

## PREPROCESSING THE DATA

Dataset preprocessing is performed in order to render the datasets fit for its intended use. The FBI data was sufficiently restricted to appropriate fields and regrouped as required for our application of the algorithm.

As for the San Francisco dataset, those crimes are first counted, where each reported incident is assigned to the appropriate category and summed up to a specific crime count for a certain geographic area.

## PROPOSED WORK

### A. User Risk Calculation

Sex, age, as well as other crime related, personal information of the victim, are mostly typical elements found in most police reports. In modern times, law enforcement agencies throughout the globe have incorporated advanced technology in systems with the aim of digitizing their records and storing them. In addition, most of the materials are used by the public and are thus provided as free resources.

The FBI UCR database, which has carefully selected and well-balanced victim records pertaining to criminal acts, is used for our model. This database covers more than 15 years of data. Our approach is modeled using the statistics found in the database.

### B. Data Justification

We have limited ourselves to modelling the algorithm with only the necessary data, understanding that users must be eager to give their data with us while also protecting their privacy. This includes the user's age, gender, and desired travel time, as these details are typically included in crime reports. Three distinct datasets are employed, each including statistical information about crimes grouped according to age, gender, and date. A careful examination of the data indicates that the aforementioned characteristics have a major impact on an individual's likelihood of becoming a victim of a specific crime.

![Figure](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932329/10932331/10932570/garg.t1-p6-garg-large.gif)

**TABLE I.** Comparison of the Current and Planned Work.

To illustrate this, we have included the graphics below. The graphs in Figures 1, 2, and 3 show the correlation between the crime rate and the age group, gender, and time, respectively.

![Figure 1](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932329/10932331/10932570/garg1-p6-garg-large.gif)

**Figure 1.** Crime rate vs Gender/Sex

![Figure 2](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932329/10932331/10932570/garg2-p6-garg-large.gif)

**Figure 2.** Crime rate vs Time

![Figure 3](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932329/10932331/10932570/garg3-p6-garg-large.gif)

**Figure 3.** Crime rate vs Age Group

The relationships among crime, age, sex, and the travel time, where all reflect victim data, were presented by the above charts. As noted from the example stolen property related offenses, most of the offenses were mainly committed against teenage male victims that were traveling between noon and three in the afternoon. This attribute suggests that people based on these specific qualities are more likely to fall victim to the crime than others. It also helps to establish the basis of our model, in that we present the use of a Decision Network to compute a single Risk Index score that quantitatively combines risk based on all the three factors.

### C. Algorithm

#### 1) Decision Network

Our suggestion is to employ a Bayesian network to determine the risk particular to each user by analyzing their profile. Understanding inter-event dependence effectively is made possible by a Bayesian network. In addition, it gives that event a probabilistic value that represents the likelihood of it occurring given the occurrence of another event. Using a variety of criteria, these correlations can then be utilized to derive certain conclusions from the random variables in the graphs.

With the datasets as our basis, we calculated three different kinds of conditional probabilities: the likelihood that a victim of a certain crime will fall into a given age group, gender, or time range.

![Figure 4](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932329/10932331/10932570/garg4-p6-garg-large.gif)

**Figure 4.** Proposed Decision Network

Above Figure 4 depicts the complete decision network used in this work.

The age, gender, and travel duration are the uncorrelated parent nodes in the previously described network. The product of the parent nodes' probabilities determines the final event, or the danger the user confronts in connection with a particular offense. We model the joint probability distribution in terms of the accompanying local conditional probabilities as prescribed by the network and following the Local Markov Independence Assumptions.

The decision network provides information on the probability that a person will become a victim of a specific type of criminal activity. Additionally, it is calculated using the formula -
$$
\begin{equation*}{\text{P}}({\text{Risk}}) = {\text{P}}({\text{Age}})*{\text{P}}({\text{Sex}})*{\text{P}}({\text{Time}})\tag{1}\end{equation*}
$$

#### 2) Crime Score and Risk Index Calculation

*A* quantitative assessment of the offense committed is then determined by creating a crime score. A serious crime has to be dealt with more seriously than a simple crime and therefore the degree of the crime must be taken into consideration in evaluating the level of threat an individual poses.

An offender's sentence and the kind of crime they committed are taken into account when assigning a crime score<sup>5</sup>.

The decision network-derived risk probability and the crime score are multiplied to obtain the final risk index. The risk index can be described as a metric that expresses quantitatively the relative likelihood of a crime occurring and the level of its impact, which is computed into one singular measure that is utilized in the subsequent steps of the algorithm.
$$
\begin{equation*}{\text{Risk Index}} = {\text{P}}({\text{Risk}})*{\text{Crime Score}}\tag{2}\end{equation*}
$$

Accordingly, the algorithm's first phase comprises evaluating the risks related to the traveller, who is linked to a certain profile. It then generates a risk index, which serves as an input for subsequent procedures.

![Figure](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932329/10932331/10932570/garg.t2-p6-garg-large.gif)

**TABLE II.** Crime Score.

#### 3) Reduced Geo-Spatial Information

The system must identify the set of coordinate points that fall between a user-specified origin and destination before proceeding with any more processing. This could take a while, thus probably affecting the overall performance of the system. We employ clustering techniques to reduce the workload and the amount of coordinates the system needs to examine for each newly produced use case. We observed various clustering schemes which were applicable to similar situations. Spatial clustering by density works best for geospatial data; however, this is immune to outliers.

Clusters were designed in seeking to find points which could inherently portray many different locations from smaller sub-regions as one single point. It does not modify or edit the geospatial information that the system already possesses. Most of the time, accurate forecasting applies to all individual coordinate values, even to those which lie beyond the rest and are termed outliers. Hence, we may form the coordinate cluster based on the K- nearest centroid algorithm. The cluster crime count is then stored in a database using the K-means clustering cluster’s index attribute corresponding to the appropriate cluster’s centroid.

The K Means Clustering findings are shown as a chart in Figure 5.

![Figure 5](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932329/10932331/10932570/garg5-p6-garg-large.gif)

**Figure 5.** K means clustering performed on a particular region in San Francisco

#### 4) Optimal Route Profiling

For the purpose of recommending a route, the system receives the user's location as input. The next step involves using the Google Maps API to get the three shortest paths between the origin and the destination. The routes are divided into manageable segments, with each segment designated according to the assessed safety index. Based on the route's length and safety index, the system suggests the best path. The crime total of the clusters that are situated within a given radius of each component is used to determine its own crime index. The predefined distance is represented by the radius mean of each coordinate cluster.

![Figure 6](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932329/10932331/10932570/garg6-p6-garg-large.gif)

**Figure 6.** Selection of the Nearest Cluster

The cluster selection procedure that the suggested model uses is shown in Figure 6.

Street risk is expressed as the number of crime counts in the nearby groups multiplied by the risk rate determined during stage one of the process.
$$
\begin{equation*}Street{\text{ }}risk(S) = \sum\nolimits_{c = 1}^n \quad (count(c)*risk{\text{ }}factor(c))\tag{3}\end{equation*}
$$

Wherefore S stands for street risk; n for the total number of crime types; c for the type of crime; count for the number of that particular crime in a defined location, such as the most relevant clusters; and risk index for the criminal risk likelihood of the user in the context of a healthy c.

A weighted average of all the streets that are part of the route is used to estimate the route risk after the risk associated with each street has been evaluated.
$$
\begin{equation*}{\text{Route risk }}{ = ^{1/t}}\sum\nolimits_{i = 1}^{\text{t}} {({\text{Si}})} \tag{4}\end{equation*}
$$
where Si is the street risk of street i and t is the total number of streets along the route.

#### 5) Colour Coding Scheme

For ease of apprehension a simple colour code is enforced for indicating the safest option. We define the safest path as green and the rest of the generated routes, which do not exceed the SBS, in red. As an effort to make the user interface of the system as uncomplicated as possible, we do not use different colours on the smaller elongated parts of the whole route. Besides the colour coding, when the pointer is moved across the corresponding route, the system brings up a small window with descriptive information.

Following the calculation of the route risk for each street, colour coding is applied, and the routes are displayed appropriately. The whole method for the best route profiling is shown below.

A flowchart representing the route profiling algorithm is shown in Figure 7.

![Figure 7](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932329/10932331/10932570/garg7-p6-garg-large.gif)

**Figure 7.** Optimal Route Profiling

## IMPLEMENTATION

Utilizing Bayesian methodology, risk structure parameters as well as the cluster database system formulated employing K MEANS clustering have been calculated a priori.

Such a derived knowledge base is held in data storage systems and is applied when the deployment of such a project takes place in operational mode. While responding to a user, a request is made to the Routes API, certain data is sent to and retrieved from the databases, and the most appropriate route is calculated and shown on the maps and dashboard with a clear safe signal.

All data pre-processing, risk analysis, and data clustering functionalities are implemented using Python. We have expanded our model's coverage across San Francisco's Northern District in order to validate it. The user can query for routes via the web-based interface, and an interactive dashboard helps the user with any warnings or alarms.

## RESULTS AND CONCLUSION

Our system finds the safest path between two sites after being tested on San Francisco streets. Different source and destination locations, as well as a range of user data use cases, are tested for the algorithm. Figure 8 and 9 depict the user-friendly interface, which is made to adapt to the user's needs in real time.

![Figure 8](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932329/10932331/10932570/garg8-p6-garg-large.gif)

**Figure 8.** Register form for basic user attribute storage.

![Figure 9](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932329/10932331/10932570/garg9-p6-garg-large.gif)

**Figure 9.** Verify user details using the login form.

The Dashboard interface serves users with intelligent notifications targeted on the street crime in a specific area and all the route info as shown in Figure 10.

![Figure 10](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932329/10932331/10932570/garg10-p6-garg-large.gif)

**Figure 10.** Smart Alerts and Safe Route Visualization

The objective of our study is to create maps of safe pathways by using geospatial data analysis and a decision network on historical crime data.

In our work, we present an effective modelling of individual user profile risks that (i) incorporates information on the user’s age, gender and time of travel, (ii) utilizes Insights from appropriate database Moreover, And (iii) builds a decision network to assess a risk factor.

Street profiles are created using Google API technology and the K-means clustering algorithm, and an efficient safe-route is constructed and visualized using a variety of methods. Unlike the famous Google maps, which only addresses the time and distance boundaries, the proposed approach is fundamentally better than previous solutions. This is because it makes use of crime statistics and a user-specific risk factor. In addition, the model outperforms its peers in the quantity of pertinent user attributes taken into account when generating safe routes.

## FUTURE SCOPE

With the model's applicability in mind, further research has the potential to expand the suggested approach's sphere of influence. Future research could focus on including other elements in the calculation of route safety. By being available on several platforms, the suggested concept can be put into practice as an Android app, which would increase accessibility and broaden its audience. To improve the user experience, the UI might also have more interactive features incorporated.

## References (15 total, showing 15)

1. Soni, Shivangi, Venkatesh Gauri Shankar, and Chaurasia Sandeep. “Route-The Safe: A Secure Path Prediction Model using Crime and Accident Data.” ( 2019 ).

2. Sarang Tarlekar et al, / (IJCSIT) International Journal of Computer Science and Information Technologies , Vol. 7 ( 3 ), 2016, 1536 - 1540.

3. Utamima, Amalia, and Arif Djunaidy. “Be-safe travel, a web- based geographic application to explore safe-route in an area.” AIP conference proceedings. Vol. 1867. No. 1. AIP Publishing LLC, 2017.

4. Zhong, Weisheng, Fanglan Chen, Kaiqun Fu, and Chang-Tien Lu. “ SAFEBIKE: A highly accurate bike-sharing route recommender coupled with availability forecast and safe routing .” arXiv preprint arXiv : 1712. 01469 ( 2017 ).

5. Galbrun, Esther, Konstantinos Pelechrinis, and Evimaria Terzi. “Urban Navigation Beyond the Shortest Route: The Case of Safe Paths.” Information Systems 57 ( 2016 ): 160 - 171.

6. Mata, Félix, Miguel Torres-Ruiz, Giovanni Guzman, Rolando Quintero, Roberto Zagal-Flores, Marco Moreno-Ibarra and Eduardo Loza. “Finding safe routes: a mobile information system based on crowd-sensed and official crime data.” Mexico city: case study. Mobile Information Systems 2016 ( 2016 ).

7. Oh, Su Bin, Hyeok Ju Park, Byeong Ki Kang, Ill Chui Doo, and Mee Hwa Park. “Safe Route Recommendation Method to Prevent Crime Exposure.” Advanced Science Letters 23, no. 10 ( 2017 ): 9579 - 9583.

8. Li, Zhaojian, Ilya Kolmanovsky, Ella Atkins, Jianbo Lu, Dimitar P. Filev, and John Michelini. “Road risk modeling and cloud-aided safety-based route planning.” IEEE transactions on cybernetics 46, no. 11 ( 2015 ): 2473 - 2483.

9. Hoseinzadeh, Nima, Ramin Arvin, Asad J. Khattak, and Lee Han. “Integrating safety and mobility for pathfinding using big data generated by connected vehicles.” Journal of Intelligent Transportation Systems ( 2020 ): 1 - 17.

10. Kang, Hyeon-Woo, and Hang-Bong Kang. “Prediction of crime occurrence from multi-modal datausing deep learning.” PloS one 12. 4 ( 2017 ).

11. Fu, Kaiqun, Yen-Cheng Lu, and Chang-Tien Lu. “Treads: A safe route recommender using social media mining and text summarization.” Proceedings of the 22nd ACM SIGSPATIAL International Conference on Advances in Geographic Information Systems. 2014.

12. Al Najada, Hamzah, and Imad Mahgoub. “Autonomous vehicles safe-optimal trajectory selection based on big data analysis and predefined user preferences.” 2016 IEEE 7th Annual Ubiquitous Computing, Electronics & Mobile Communication Conference (UEMCON) . IEEE, 2016.

13. J. W. Coid et al., “Development of a Bayesian network for the risk management of violent prisoners.” Improving Risk Management for Violence inMentalHealth Services: A Multimethods Approach - NCBI Bookshelf Nov. 01, 2016.

14. J. De Zoete, Μ. Sjerps, D. Lagnado, and N. Fenton, “Modelling crime linkage with Bayesian networks.” Science & Justice , vol. 55, no. 3, pp. 209 - 217, Dec. 2014, doi: 10.1016/j.scijus.2014.11.005.

15. FBI UCR Database , Available (Online): https://www.fbi.gov/services/cjis/ucr ; Accessed on 15-Dec-2024
