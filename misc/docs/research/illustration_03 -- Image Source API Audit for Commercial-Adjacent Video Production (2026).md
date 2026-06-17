# Image Source API Audit for Commercial-Adjacent Video Production (2026)
**Author: Thor Whalen | Current as of June 17, 2026**

> A practical, build-decision-oriented audit of image-retrieval APIs for a screenplay-to-animation production system, optimized for free / cheap pay-as-you-go billing, with a prototype-to-production path. Delivered as a downloadable Markdown (.md) document.

---

## TL;DR
- For a free-default prototype that may scale, **Pexels is the best primary provider** (free, 200 req/hr & 20,000 req/month default, unlimited free on approval, rich metadata, caching encouraged), with **Pixabay as the cacheable companion** (100 req/60s, mandatory 24h caching, download-to-server model) and **Openverse + Wikimedia Commons** for breadth/historical/editorial — but those last two carry "free but you assume all legal risk" traps because license accuracy is explicitly disclaimed per-file.
- The "open-web image breadth" era via official APIs is over: **Google Custom Search JSON API is closed to new customers and shuts down January 1, 2027**, and **Bing Search APIs (incl. Image Search) were retired August 11, 2025**. Realistic replacements are paid third-party SERP/scraper APIs (DataForSEO ~$0.0006–$0.002/query is cheapest pay-as-you-go; SerpApi richest but ~$25/1k) — but these carry live legal risk after **Google sued SerpApi on December 19, 2025**.
- The premium tier (Shutterstock, Adobe Stock, Getty/iStock) is **not realistically self-serve pay-as-you-go for an API-licensing prototype**: Adobe Stock API licensing requires a Stock-for-Enterprise contract, Getty requires a Connect partner/account agreement, and only Shutterstock offers self-serve API subscriptions. Escalate here only at production scale when indemnification matters.

---

## Key Findings

1. **Three genuinely free, API-key-only providers** (Pexels, Pixabay, Unsplash) cover the bulk of generic stock needs at zero cost. Pexels and Pixabay are the most prototype-friendly; Unsplash is the most legally constrained for a metadata-search/caching architecture because it requires hotlinking and forbids building a competing index.
2. **Aggregators (Openverse, Wikimedia Commons, Flickr, Europeana) give breadth, historical, and editorial coverage** but shift all license-verification burden to you. Every one of them disclaims license accuracy.
3. **Government/GLAM sources (Smithsonian Open Access, NASA, Europeana)** are the safest legally — mostly CC0/public domain — and ideal for historical/scientific reference imagery.
4. **Open-web breadth now costs money and carries legal risk.** With Google CSE and Bing retired/retiring, you must pay a SERP/scraper vendor, and the legal posture on scraping Google/Bing Images is actively contested.
5. **Premium stock APIs are gated behind contracts** except Shutterstock's self-serve tier; they are an escalation path for indemnified, model-released commercial imagery, not a prototype default.

---

## Details

### A. Free, API-key-only providers

**Pexels** — Free, no credit card [1][3]. Default rate limit **200 requests/hour and 20,000 requests/month**; unlimited requests available free on approval (email api@pexels.com showing attribution) [2][3]. Returns up to 80 results/page. Search filters: `orientation` (landscape/portrait/square), `size` (large 24MP / medium 12MP / small 4MP), `color` (named or hex), `locale` [1]. Metadata includes id, width/height, photographer + photographer_url + photographer_id, `avg_color`, `alt` text, and multiple pre-sized `src` URLs [1]. Caching: explicitly **encouraged** ("Implement your own cache… 24 hours is a good amount of time") [1]. License: Pexels License, free commercial use, no attribution required (attribution to Pexels appreciated/required for unlimited tier) [2]. Trap clause: **"you may not copy our core functionality with the API"** — no wallpaper apps, no re-promoting as a free stock platform, no selling unaltered copies [2]. No per-file model/property releases; recognizable people/trademarks are your responsibility.

**Pixabay** — Free [4]. Rate limit **100 requests per 60 seconds** by default (raised on request) [4]. **Mandatory 24-hour caching of responses** [4]. Critical architectural rule: **permanent hotlinking of Pixabay CDN URLs is prohibited — you must download images to your own server** [4]. Filters: image_type (photo/illustration/vector), orientation, category, colors, safesearch, min dimensions, language [4]. Metadata: tags (comma string), user, type, views/downloads/likes/comments, dimensions, multiple sized URLs; full-resolution/vector URLs require approved full API access [4]. Corpus: 5.7M+ images and videos [4]. License: Pixabay Content License, free commercial use without attribution; CC0 for content dated before Jan 9, 2019 [5]. Trap: ToS expressly **disclaims any warranty that consents/licenses were obtained** — recognizable people, brands, logos, trademarks are your responsibility; no standalone redistribution [5].

**Unsplash** — Free [6]. **Demo tier = 50 requests/hour; Production tier = 5,000 requests/hour** after approval (submit screenshots showing proper attribution/use; approval reportedly ~5 business days) [6][7]. Only JSON requests to api.unsplash.com count; image file requests to images.unsplash.com do not [6]. Filters: orientation, color, content_filter, order_by; rich dynamic image URLs (resize/crop/format via query params) [6]. Metadata is the richest of the free three: id, dimensions, color, blur_hash, full EXIF (make, model, exposure, aperture, focal length, ISO) on individual photo fetch, location, tags, photographer profile, download_location [6]. **Three serious traps for this use case:** (1) **API Guidelines require hotlinking** the returned URLs and triggering the download endpoint — this conflicts with a cache-to-own-server model [6]; (2) the Unsplash License **"does not include the right to compile images from Unsplash to replicate a similar or competing service"** — directly relevant to building a searchable index [10]; (3) the free Unsplash License gives **$0 indemnification** (max aggregate liability $100 per their terms) and no model-release verification. AI/ML: the **free Unsplash License does not explicitly prohibit AI/ML training, but the Terms & Conditions prohibit using Images "in connection with any machine learning and/or artificial intelligence datasets"** and direct you to unsplash.com/data; Unsplash+ content explicitly bans ML/AI use [8][9]. Note: Unsplash was acquired by Getty Images in March 2021.

### B. Aggregators / open-media corpora

**Openverse** (WordPress Foundation) — Free. Aggregates **over 800 million openly-licensed and public-domain images and audio tracks** from 50+ sources (Flickr, Wikimedia, museums, etc.) [13]. **Anonymous rate limit: 20 requests/minute and 200 requests/day** (confirmed via live `X-RateLimit-Limit-anon_burst: 20/min` / `anon_sustained: 200/day` headers). Authenticated "standard" tier (register OAuth2 app) is higher but the exact numbers are not published in docs [12]; "enhanced" tier is selectively granted [12]. Filters: license type, license version, source, creator, tags, category, extension, aspect_ratio, size. Metadata: title, creator, license + license_version + license_url, source, foreign_landing_url, thumbnail, tags, attribution string. **Major trap:** ToS states **"Openverse does not own or control the content… and does not verify its licensing status or make any representations or warranties about the content or data whatsoever. You are responsible for independently verifying whether you have the right to use the content"** [11]. Also: **must not scrape the Openverse catalog**, must display "made using the Openverse API but is not endorsed/certified," and Openverse reserves the right to charge for commercial/heavy use [11].

**Wikimedia Commons** (MediaWiki Action API, `prop=imageinfo&iiprop=extmetadata`) — Free; rate limit etiquette-bound (set a descriptive User-Agent; no rate fee). Corpus: **143,153,289 free-to-use media files (including 120,651,430 images), or around 924 TB, per Wikipedia:Statistics (2026)**. Metadata via extmetadata: LicenseShortName, License URL, Artist, Credit, AttributionRequired, UsageTerms, DateTime, Categories, plus camera EXIF where present [14]. **Major trap:** licenses **vary file-by-file** (CC0, CC BY, CC BY-SA, PD, sometimes with non-copyright restrictions like personality/trademark/freedom-of-panorama). The Foundation **"does not provide any warranty regarding the copyright status or correctness of licensing terms… you should verify the copyright status of each image"** [14][15]. CC BY-SA imposes share-alike; attribution almost always required.

**Flickr** (SmugMug) — Free API key; **3,600 queries/hour per key** (aggregate across all users) [17]. Commercial use requires a **commercial API key** (separate application; SmugMug "may grant… subject to your payment of fees") [16]. Filters: text, tags, license (CC filter), geo, date, sort, content type. Metadata: very rich — tags, description, owner, dates, geo, camera EXIF (separate call), license code, multiple sizes. **Major trap:** per-photo licenses vary wildly (All Rights Reserved is the default for most photos; only CC-licensed or PD photos are reusable). "You are solely responsible for making use of Flickr photos in compliance with the photo owners' requirements"; must honor privacy changes within 24h and removal requests [16]. Required attribution notice: "This product uses the Flickr API but is not endorsed or certified by SmugMug" [16].

**Europeana** — Free; API key now requested via a Europeana account (since 28 May 2025); a higher-rate "project key" is available on request [18]. Aggregates ~50M+ European cultural-heritage records. EDM (Europeana Data Model) metadata: dcType, dcCreator, rights (per-record rights statement URL), dataProvider, edmIsShownBy/At [18]. **Trap:** rights vary per record (CC0, PD, CC BY, CC BY-SA, plus rightsstatements.org "In Copyright" items where only metadata is open); verify per item.

### C. Government / GLAM (cleanest licensing)

**Smithsonian Open Access** — Free API key via api.data.gov (rate limit governed by api.data.gov defaults, typically 1,000 req/hour) [19]. **2.8M+ CC0 (public domain) 2D/3D images** out of 11M+ metadata records (bulk metadata also on AWS Open Data and GitHub, refreshed weekly) [19]. Metadata: title, accession number, owning unit, media (thumbnail, IDS image URL, usage.access=CC0), topic/notes [19]. Trap: items marked **"usage conditions apply"** are NOT CC0 and may not be used commercially — filter on CC0.

**NASA** — Free; api.nasa.gov key (default DEMO_KEY = 30 req/hour, 50/day; registered key = 1,000 req/hour) [20]. NASA Image and Video Library (images.nasa.gov API) and APOD, GIBS satellite imagery [20]. Metadata: title, description, keywords, date_created, center, NASA ID, media_type. License: most NASA media is **public domain** (not copyrighted), but some contain copyrighted third-party material or identifiable people/NASA logo restrictions — verify; NASA logo use is restricted.

### D. Open-web breadth: the post-2025 reality

**Google Custom Search JSON API** — **Closed to new customers; discontinued January 1, 2027** (returns HTTP 410 thereafter) [21]. For existing customers only: 100 queries/day free, then $5 per 1,000 queries up to 10,000/day [21]. The "Search entire web" mode was announced for discontinuation Jan 9, 2026. Google's recommended replacement, Vertex AI Search, is an enterprise semantic-search-over-your-own-corpus product (~$2/1,000 basic) — **not a public-web image replacement.** The Site Restricted JSON API already shut down Jan 8, 2025.

**Bing Search APIs (Web + Image Search)** — **Retired August 11, 2025**; endpoints return HTTP 410 Gone; no new signups [22]. Microsoft's only first-party replacement is "Grounding with Bing Search" inside Azure AI Agents/Foundry — agent-only, returns grounded chunks not raw SERP/image JSON, and **40–483% more expensive than the old API, per PPC Land's pricing analysis of Grounding with Bing Search vs. the retired API tiers**.

**Realistic replacements for open-web image breadth (all third-party, all paid):**

| Provider | Pricing (2026) | Free tier | Image search? | Legal posture |
|---|---|---|---|---|
| **DataForSEO** | Google Images SERP: Standard queue **$0.0006/page**, Priority $0.0012, Live $0.002; pay-as-you-go, **$50 min deposit, no monthly fee**, $1 trial credit [23][24] | $1 credit + sandbox | Yes — dedicated Google Images endpoint (alt/title tags, ranking, source) + reverse image [23] | Scrapes public SERPs; claims legality; you assume risk |
| **SerpApi** | ~**$25/1,000** at entry ($75/mo Developer = 5k); richest structured output; subscription not PAYG [25] | 250/mo free | Yes — Google/Bing Images engines | **Sued by Google Dec 19, 2025; motion to dismiss filed Feb 20, 2026** [26] |
| **Serper** | From **$0.30–$1.00/1,000**; PAYG | 2,500 free | Yes (Google Images) | Google-scraping; same category risk |
| **Brave Search API** | **$5/1,000** ($5 monthly credit ≈ 1,000 free searches; free perpetual tier retired Feb 2026) [27][28] | $5 credit/mo | Yes — independent 30B+ page index incl. image results [27] | **Lowest legal risk — owns its own index, not scraping;** storage/LLM-training requires a plan that grants storage rights [27] |
| **Oxylabs** | SERP Scraper API ~$0.95–$2/1,000+, contact sales | Trial | Yes | Named in Reddit scraping suit (Oct 22, 2025) |
| **Tavily / Exa / Firecrawl** | Tavily ~$0.008/query; Exa from $0.001/result; Firecrawl 1,000 free credits/mo | 1,000/mo each | AI-search/extraction oriented, not image-first | Mixed (own index vs scraping) |

**Decisive point:** Brave Search API is the only independent Western web index left after Bing's shutdown, so it carries the **lowest legal exposure** for open-web breadth; the Google-scraping vendors (SerpApi, Serper, Oxylabs, DataForSEO) are cheaper/richer but expose you to the same legal theory Google is now litigating [26].

### E. Premium tier (escalation only)

**Shutterstock** — **Only premium provider with self-serve API subscriptions** (developers.shutterstock.com) [29]. Free API tier reported at ~100 requests/hour, 500 downloads/month for testing; production = custom/contact sales [29]. Pay-Per-Use and collection tiers (Starter 3M+ assets up to Full Collection 375M+) [29]. API content is licensed under the restricted **Platform License** (use only within the integrated app). Standard license carries $10,000 indemnification; Enhanced $250,000. Rich metadata: keywords, descriptions, categories, model/property release flags, contributor. AI training offered as a separate licensed product.

**Adobe Stock** — **Search API is free and open** (any Adobe ID can search + get watermarked previews), **but the licensing/download API requires Adobe Stock for Enterprise (ETLA contract)** as of November 2024; non-enterprise developers must join the Affiliate program or apply via the prerelease survey [30]. Server-to-server (no user login) is Enterprise-only [30]. Search returns up to 100 assets/page; filters by content type, premium tier, etc. So: **no self-serve pay-as-you-go API licensing for a startup prototype.**

**Getty Images / iStock** — **API access requires a Getty Connect partner/account agreement**; an api-key is issued only to customers with an existing agreement or an approved test account [31]. OAuth 2.0; throttle (QPS) set per contract [31]. Fields: summary_set vs detail_set (rich editorial metadata, captions, dates, releases). Getty explicitly offers AI-training licensing of its visuals + metadata [31]. **No self-serve pay-as-you-go.** ~50,000–80,000 new images/week (mostly editorial). Note Getty owns Unsplash.

---

## Master Comparison Table

| Source | Cost model | Rate limit | CC/contract | Metadata richness | License + key traps | Corpus | AI-train | Cache/hotlink |
|---|---|---|---|---|---|---|---|---|
| **Pexels** | Free | 200/hr, 20k/mo (unltd on approval) | No CC | High (avg_color, alt, photographer, sizes) | Pexels License, commercial OK, no attribution req; no "core functionality" clones | Large (M's photos+video) | No explicit ban | **Cache encouraged (24h)** |
| **Pixabay** | Free | 100/60s | No CC | Med (tags, user, dims) | Content License; **must download to own server, no hotlink**; no warranty of consents | 5.7M+ | Broad upload license | **Cache mandatory 24h** |
| **Unsplash** | Free | 50/hr demo → 5,000/hr prod | No CC | **Highest (full EXIF, location)** | **Must hotlink; no competing index; $0 indemnity; T&C bans AI dataset use** | ~5M+ | **Prohibited (T&C)** | Hotlink required |
| **Openverse** | Free | **20/min, 200/day anon**; higher authed | No CC | Med (license_url, creator, tags) | **No license-accuracy warranty; no scraping catalog** | **800M+ img+audio** | Per-source | Per-source |
| **Wikimedia Commons** | Free | ~etiquette (UA req) | No CC | High (extmetadata, EXIF, license) | **Per-file licenses vary; no warranty; CC BY-SA share-alike** | 143.2M files (120.7M images) | Generally OK (CC) | Hotlink or download OK |
| **Flickr** | Free key | 3,600/hr | No CC (fees possible for commercial key) | High (EXIF, tags, geo) | **Per-photo license varies; ARR default; commercial key required** | Billions (CC subset smaller) | Per-photo | Cache w/ removal rules |
| **Europeana** | Free | Account key; project key higher | No CC | High (EDM, rights URL) | **Per-record rights vary** | ~50M+ records | Per-record | Per-record |
| **Smithsonian OA** | Free | api.data.gov (~1k/hr) | No CC | Med (CC0 flag, unit, topic) | **Filter CC0; "usage conditions apply" = not commercial** | 2.8M+ CC0 | OK (CC0) | OK |
| **NASA** | Free | DEMO 30/hr; key 1k/hr | No CC | Med (keywords, center, date) | Mostly PD; logo/3rd-party/person caveats | Large | OK (PD) | OK |
| **Google CSE JSON** | Existing only; **EOL Jan 1 2027** | 100/day free, $5/1k to 10k/day | CC for billing | Med | **Closed to new customers** | Web | n/a | n/a |
| **Bing Search API** | **Retired Aug 11 2025** | — | — | — | **Gone (HTTP 410)** | — | — | — |
| **DataForSEO** | PAYG $0.0006–$0.002/query | Concurrency-based | $50 min deposit | Med-High (alt/title, source, reverse img) | Scrapes SERP; you assume risk | Google/Bing index | Add-on | You host |
| **SerpApi** | Subscription ~$25/1k | Plan-based | CC required | **Highest structured SERP** | **Google lawsuit Dec 2025** | Google/Bing | n/a | You host |
| **Serper** | PAYG $0.30–1/1k | QPS limits | CC | Med | Google-scraping risk | Google | n/a | You host |
| **Brave Search API** | $5/1k ($5 credit/mo) | Plan-based | CC | Med (own index) | **Lowest risk (own index)**; storage needs storage plan | 30B+ pages | Plan w/ storage rights | You host |
| **Shutterstock** | **Self-serve API subs** + PPU | ~100/hr free tier | CC (self-serve) | High (releases, keywords) | Platform License (in-app only); $10k–$250k indemnity | 375M+ | Separate product | Per license |
| **Adobe Stock** | Search API free; **license API = Enterprise contract** | per contract | Enterprise | High (releases) | **No self-serve licensing** | 300M+ | Enterprise | Per license |
| **Getty/iStock** | **Partner contract only** | per contract QPS | Contract | **Highest editorial** | **No self-serve** | 100M's; 50–80k/wk new | Licensed product | Per license |

---

## Decision Tree ("if you need X, use Y")

- **Generic stock photos/video, free, prototype-fast, cache to your own DB →** Pexels (primary). Add Pixabay for additional free volume (download-to-server).
- **Highest-quality artistic photos + richest EXIF, and you can hotlink + show attribution →** Unsplash (but NOT if you're building a searchable index you redistribute — competing-service clause).
- **Maximum breadth incl. CC/historical/long-tail, one API over many sources →** Openverse (verify licenses yourself; low rate limit anon, authenticate).
- **Historical, editorial, museum, fine-art, scientific reference →** Wikimedia Commons + Europeana + Smithsonian Open Access (CC0) + NASA (PD).
- **Specific photographer/community photos, geo-tagged →** Flickr (commercial key; filter to CC).
- **"Find me any image on the open web for a concept" (breadth fallback) →** Brave Search API first (lowest legal risk, owns index); DataForSEO if you need cheapest PAYG Google Images specifically; avoid SerpApi until its Google litigation resolves.
- **Indemnified, model-released, premium commercial imagery at production →** Shutterstock self-serve API (only realistic self-serve premium); escalate to Getty/Adobe Enterprise only with a contract and budget.

---

## Recommended Layered Source Strategy

1. **Free default provider: Pexels.** Zero cost, 20k/month default (free unlimited on approval), cache-friendly, rich-enough metadata (avg_color, alt, photographer, sizes), clean commercial license. Build your metadata index over Pexels responses; respect the no-clone clause by adding value beyond raw passthrough.
2. **Cacheable companion: Pixabay.** Download-to-own-server is mandated anyway, which fits a production pipeline that stores assets + metadata locally. Adds free volume and illustrations/vectors.
3. **Breadth + historical/editorial: Openverse + Wikimedia Commons + Smithsonian/NASA/Europeana.** Use for anything Pexels/Pixabay lack (historical, fine-art, scientific, editorial). **Build a per-file license-verification gate** — store license_url/rights statement per asset and block anything not on an allowlist (CC0, CC BY, PD; flag CC BY-SA for share-alike; reject NC/ND and "usage conditions apply"/ARR).
4. **Open-web breadth fallback: Brave Search API** (lowest legal risk) with DataForSEO as the cheap PAYG alternative for Google Images specifically. Treat scraped results as discovery/reference only; do not assume any license — re-clear each image at the source.
5. **Premium escalation: Shutterstock self-serve API** when you need guaranteed indemnification + model/property releases for commercial release. Reserve Getty/Adobe Enterprise for funded production with legal review.

**Architectural rules baked in:** (a) cache responses 24h+ and store images on your own server (required by Pixabay, smart everywhere; the one exception is Unsplash, which requires hotlinking — so either comply with Unsplash hotlinking or exclude it from the cached pipeline); (b) persist a normalized metadata record per asset including source, license, license_url, attribution string, photographer/creator, and dimensions — this is what your metadata-search prototype queries over; (c) keep Unsplash out of any "searchable redistributable index" feature to avoid its competing-service clause.

---

## Recommendations (staged, with thresholds)

**Stage 1 — Prototype (now):** Integrate Pexels + Pixabay (both free, no card). Add Smithsonian/NASA/Wikimedia for historical/scientific reference. Build the metadata index and license-allowlist gate. **Threshold to advance:** when you exceed ~20k Pexels calls/month or need open-web breadth.

**Stage 2 — Scaling free:** Apply for Pexels unlimited (free) and Unsplash Production (5,000/hr) — but only wire Unsplash in if you can hotlink + attribute and you are NOT exposing a redistributable image index. Authenticate to Openverse for higher limits. **Threshold:** when free coverage gaps force open-web search, or when clients demand indemnification.

**Stage 3 — Paid breadth:** Add Brave Search API ($5/1k, lowest legal risk) for open-web concept search; use DataForSEO ($0.0006/query) only if you specifically need Google Images structured data and accept scraping risk. **Threshold:** when a paying customer requires legally-cleared, model-released commercial imagery.

**Stage 4 — Premium/production:** Onboard Shutterstock self-serve API for indemnified commercial assets; engage Getty or Adobe Enterprise sales only with legal review and budget for contracts.

**Benchmarks that change the plan:** The Google v. SerpApi case is in the U.S. District Court for the Northern District of California (Case No. 5:25-cv-10826-YGR, Judge Yvonne Gonzalez Rogers); SerpApi filed a 31-page motion to dismiss on Feb 20, 2026 (arguing Google lacks standing as a non-copyright holder and that SearchGuard is not a copyright access-control measure), with a hearing set for May 19, 2026. If that resolves in scrapers' favor, SerpApi/Serper/Oxylabs become viable; if it goes against them, consolidate on Brave + first-party providers. If Brave raises prices further (it retired its free tier Feb 2026), re-evaluate DataForSEO. If Openverse begins charging for commercial/heavy use (a right it reserves), budget for it or self-host a Common-Crawl-based index.

---

## Caveats
- **Pricing and limits change frequently.** All figures verified against official docs/developer pages current to mid-2026; re-verify before committing.
- **The "free but you assume all legal risk" trap is real and central.** Pixabay, Wikimedia, Openverse, Flickr, and Europeana all explicitly disclaim warranty of license accuracy. For commercial-adjacent video, a per-file license-verification gate and stored provenance are mandatory, not optional. Unsplash's free tier gives only $100 max liability and no model releases.
- **Scraping-based open-web APIs carry active, unresolved legal risk.** Google's complaint (filed 12/19/25) alleges SerpApi sends "hundreds of millions" of artificial queries daily — a volume up "as much as 25,000%" over two years — and seeks DMCA §1201 statutory damages of "$200 to $2,500 for each" circumvention act; Reddit separately sued SerpApi, Perplexity AI, Oxylabs, and AWMProxy on Oct 22, 2025 in the Southern District of New York. Brave (own index) is the conservative choice.
- **Openverse standard/enhanced authenticated rate limits are not published numerically** — read the `X-RateLimit-Limit-oauth2_client_credentials_*` response headers after registering, or inspect the repo's `DEFAULT_THROTTLE_RATES`.
- **AI/ML training permissions are tightening.** If your screenplay-to-animation system trains or fine-tunes any model on retrieved images, treat AI-training rights as a separate license question per source (Unsplash and most premium providers restrict or separately license it).

---

## References
1. [Pexels API Documentation](https://www.pexels.com/api/documentation/)
2. [Pexels — How do I get unlimited requests?](https://help.pexels.com/hc/en-us/articles/900005852323-How-do-I-get-unlimited-requests)
3. [Pexels — Is the Pexels API free?](https://help.pexels.com/hc/en-us/articles/47677890260761-Is-the-Pexels-API-free-to-use)
4. [Pixabay API Documentation](https://pixabay.com/api/docs/)
5. [Pixabay Terms of Service](https://pixabay.com/service/terms/)
6. [Unsplash API Documentation](https://unsplash.com/documentation)
7. [Unsplash — When should I apply for a higher rate limit?](https://help.unsplash.com/en/articles/3887917-when-should-i-apply-for-a-higher-rate-limit)
8. [Unsplash API Terms](https://unsplash.com/api-terms)
9. [Unsplash Terms & Conditions](https://unsplash.com/terms)
10. [Unsplash — "compiling images to replicate a similar or competing service"](https://help.unsplash.com/en/articles/2612332-what-do-you-mean-by-compiling-images-to-replicate-a-similar-or-competing-service)
11. [Openverse API Terms of Service](https://docs.openverse.org/terms_of_service.html)
12. [Openverse — Authentication and Throttling](https://docs.openverse.org/api/reference/authentication_and_throttling.html)
13. [Openverse — Made with Openverse (corpus size)](https://docs.openverse.org/api/reference/made_with_ov.html)
14. [Wikimedia Commons — Reusing content outside Wikimedia](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)
15. [Wikimedia Commons — Licensing](https://commons.wikimedia.org/wiki/Commons:Licensing)
16. [Flickr APIs Terms of Use](https://www.flickr.com/help/terms/api)
17. [Flickr Developer Guide — API](https://www.flickr.com/services/developer/api/)
18. [Europeana APIs](https://pro.europeana.eu/page/apis)
19. [Smithsonian Open Access Developer Tools](https://www.si.edu/openaccess/devtools)
20. [NASA Open APIs](https://api.nasa.gov/)
21. [Google Custom Search JSON API overview (EOL notice)](https://developers.google.com/custom-search/v1/overview)
22. [Bing Search APIs Retiring on August 11, 2025 — Microsoft Learn](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement)
23. [DataForSEO Google Images SERP API](https://dataforseo.com/pricing/serp/google-images-serp-api)
24. [DataForSEO SERP API pricing](https://dataforseo.com/apis/serp-api/pricing)
25. [SerpApi Plans and Pricing](https://serpapi.com/pricing)
26. [Why we're taking legal action against SerpApi (Google)](https://blog.google/technology/safety-security/serpapi-lawsuit/)
27. [Brave Search API](https://brave.com/search/api/)
28. [Brave Kills Free Search API Tier (Implicator)](https://www.implicator.ai/brave-drops-free-search-api-tier-puts-all-developers-on-metered-billing/)
29. [Shutterstock Developer Portal — API Pricing](https://www.shutterstock.com/api/pricing)
30. [Adobe Stock API — Getting Started](https://developer.adobe.com/stock/docs/getting-started/)
31. [Getty Images API](https://www.gettyimages.com/api)
32. [PPC Land — Microsoft ends Bing Search APIs; alternative costs 40-483% more](https://ppc.land/microsoft-ends-bing-search-apis-on-august-11-alternative-costs-40-483-more/)
33. [IPWatchdog — Google Sues SerpApi (case details)](https://ipwatchdog.com/2025/12/26/google-sues-serpapi-parasitic-scraping-circumvention-protection-measures/)