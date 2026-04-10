# 📍 Step 1.2: Develop Multilingual Keyword Taxonomy

**Goal**: Create a comprehensive keyword matrix across English, Korean, and Italian. Extract specific variables for 5 categories: Core brand (e.g., Samsung Design, Samsung design language), Leadership (e.g., Mauro Porcini, Samsung CDO), Product, Philosophy, and Events. Translate and localize search terms accurately for Korean and Italian markets. Verification: Cross-check that the taxonomy captures terms relevant to both the pre-Porcini and post-Porcini eras to enable accurate YoY comparisons. Format this data as a structured Keyword Category table draft.

### A.1 Monitoring Framework Definition

To accurately capture and analyze the global media perception of Samsung Design, particularly following the pivotal appointment of Mauro Porcini as President and Chief Design Officer (CDO) in April 2025 [1], we have established a robust, multi-lingual monitoring infrastructure. This framework is designed to track current sentiment while enabling direct Year-over-Year (YoY) comparisons against the pre-Porcini era (2023–early 2025). 

The tracking parameters encompass global tech consumers, design professionals, business analysts, and the general public across English, Korean, and Italian markets. By capturing data across global tech media, design-specific publications, business press, and social platforms, we ensure a holistic view of Samsung's evolving design narrative, which has recently shifted toward "human-centered innovation" and four core pillars: "living longer," "living better," "living loud," and "living on" [2][3].

#### Keyword Matrix & Listening Topics

The following taxonomy dictates the boolean search logic deployed across our media listening tools. It is strictly categorized to isolate specific strategic pillars and fully localized to capture regional nuances in key markets (US/Global, South Korea, and Italy).

| Keyword Category | Keywords | Variants (Including Wildcards/Misspellings) | Language | Channel Priority |
| :--- | :--- | :--- | :--- | :--- |
| **Core Brand** | "Samsung Design", "Samsung Design Leadership", "Samsung Galaxy design", "Samsung Bespoke design", "Samsung design language", "Samsung design quality" | *SamsungDesign, Samsung-design, Samsng design, Galaxy-design, Bespoke-design | English | All Channels |
| **Core Brand** | "삼성 디자인", "삼성 디자인 리더십", "삼성 갤럭시 디자인", "삼성 비스포크 디자인", "삼성 디자인 언어", "삼성 디자인 품질" | 삼성디자인, 갤디자인, 비스포크디자인, 삼성 디자인경영 | Korean | Korean Media (조선일보, 중앙일보, 한국경제, IT조선, 디자인프레스) |
| **Core Brand** | "Samsung design", "Leadership del design Samsung", "Design Samsung Galaxy", "Design Samsung Bespoke", "Linguaggio di design Samsung", "Qualità del design Samsung" | design di Samsung, Samsung-design, estetica Samsung | Italian | Italian Media (Corriere della Sera, La Repubblica, Il Sole 24 Ore) |
| **Leadership** | "Mauro Porcini", "Mauro Porcini Samsung", "Samsung CDO", "Samsung Chief Design Officer", "Samsung design president" | M. Porcini, Porcini CDO, Mauro Porcini design, Samsung head of design | English | Business Press (Bloomberg, Forbes), Design Media, LinkedIn |
| **Leadership** | "마우로 포르치니", "마우로 포르치니 삼성", "삼성 CDO", "삼성 최고 디자인 책임자", "삼성 디자인 사장" | 마우로포르치니, 포르치니 CDO, 삼성 디자인 수장 | Korean | Korean Media, Business Press |
| **Leadership** | "Mauro Porcini", "Mauro Porcini Samsung", "Samsung CDO", "Chief Design Officer Samsung", "Presidente design Samsung" | Porcini Samsung, Mauro Porcini CDO | Italian | Italian Media, Design Media (Domus, Wallpaper*) |
| **Product Design** | "Galaxy Z Fold design", "Galaxy Z Flip design", "Galaxy S design", "Samsung foldable design", "Samsung wearable design", "Galaxy Ring design" | ZFold design, ZFlip design, Galaxy S* design, Samsung foldables, Samsung ring design | English | Global Tech Media (The Verge, Engadget, Wired, CNET), YouTube, Reddit |
| **Product Design** | "갤럭시 Z 폴드 디자인", "갤럭시 Z 플립 디자인", "갤럭시 S 디자인", "삼성 폴더블 디자인", "삼성 웨어러블 디자인", "갤럭시 링 디자인" | 갤폴드 디자인, 갤플립 디자인, 갤S 디자인, 삼성 폴더블폰 디자인, 갤링 디자인 | Korean | Korean Tech Media (IT조선), YouTube, Naver Blogs |
| **Product Design** | "Design Galaxy Z Fold", "Design Galaxy Z Flip", "Design Galaxy S", "Design pieghevoli Samsung", "Design wearable Samsung", "Design Galaxy Ring" | design Z Fold, design Z Flip, design pieghevole Samsung | Italian | Italian Tech Media, YouTube |
| **Philosophy** | "Samsung design philosophy", "Samsung Essential design", "Samsung Innovative design", "Samsung Harmonious design", "human-centered innovation", "living longer", "living better", "living loud", "living on" | Samsung design ethos, innovation as an act of love, Samsung human-centric design | English | Design Media (Dezeen, Designboom, Core77), Business Press |
| **Philosophy** | "삼성 디자인 철학", "삼성 에센셜 디자인", "삼성 혁신 디자인", "삼성 조화로운 디자인", "인간 중심 혁신", "더 오래 살기", "더 나은 삶", "더 크게 살기", "계속 살기" | 삼성 디자인 비전, 인간중심 디자인, 사랑의 행위로서의 혁신 | Korean | Korean Media, Design Press |
| **Philosophy** | "Filosofia del design Samsung", "Design essenziale Samsung", "Design innovativo Samsung", "Design armonioso Samsung", "innovazione centrata sull'uomo" | visione del design Samsung, innovazione umana Samsung | Italian | Italian Media, Design Media |
| **Events** | "Samsung Milan Design Week", "Samsung Unpacked design", "Samsung CES design", "Samsung design award" | MDW Samsung, Samsung Fuorisalone, Unpacked * design, CES * design | English | Design Media, Social Media (X/Twitter, Instagram) |
| **Events** | "삼성 밀라노 디자인 위크", "삼성 언팩 디자인", "삼성 CES 디자인", "삼성 디자인 어워드" | 밀라노디자인위크 삼성, 삼성 푸오리살로네, 언팩 디자인, CES 삼성 디자인 | Korean | Korean Media, Social Media |
| **Events** | "Samsung Milano Design Week", "Samsung Fuorisalone", "Samsung Unpacked design", "Samsung CES design", "Premio design Samsung" | MDW Samsung, Fuorisalone Samsung, Samsung Salone del Mobile | Italian | Italian Media, Design Media (Domus), Instagram |

#### Adjective-Based Perception Capture Method

Because design quality is frequently discussed using descriptive language rather than explicit brand keywords, we have implemented a proximity-based natural language processing (NLP) rule. The system tracks the frequency and context of specific adjectives when they appear within five words (NEAR/5) of core brand identifiers (e.g., "Samsung", "Galaxy", "Bespoke").

*   **Positive Descriptors Tracked:** "premium", "elegant", "refined", "minimalist", "innovative", "bold", "sophisticated", "sleek", "beautiful", "iconic".
*   **Negative Descriptors Tracked:** "cheap", "plastic", "copycat", "generic", "boring", "cluttered", "dated", "uninspired".

This methodology allows us to quantify the qualitative reception of Samsung's hardware and software aesthetics, providing a measurable baseline to track how Mauro Porcini's new design direction impacts consumer and critical perception over time.

#### Filtering Themes

To organize the raw data collected via the keyword matrix into actionable, analytical clusters, all mentions are automatically and manually tagged into the following thematic filters:
1.  Samsung Design Identity & Philosophy
2.  Product Design Reviews & Reception
3.  Design Leadership (Mauro Porcini)
4.  Design Awards & Recognition
5.  Event Coverage (Milan Design Week, Unpacked, etc.)
6.  Competitive Design Comparisons
7.  Consumer Design Perception

---

## References

[1] Samsung Newsroom. (2025). *Samsung Electronics Appoints Mauro Porcini as President and Chief Design Officer*. Retrieved from https://news.samsung.com/global/samsung-electronics-appoints-mauro-porcini-as-president-and-chief-design-officer
[2] Porcini, M. (2025). *Design Vision*. LinkedIn. Retrieved from https://www.linkedin.com/posts/mauroporcini_samsung-samsungdesign-designthinking-activity-7427931001311621120-Z0HL
[3] Wired. (2025). *The Pepsi Man is Coming to Save Samsung from Boring Design*. Retrieved from https://www.wired.com/story/the-pepsi-man-is-coming-to-save-samsung-from-boring-design/

