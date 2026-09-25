# Video Footage Sources for `illustration` (2026)

*Current as of 2026-09-24. A build-decision research note: which searchable sources of video footage `illustration` can use, under what terms, and what a video result needs in the schema. It is the video companion to R3, the image-source audit [1]. Not legal advice.*

---

## TL;DR

- **Video does not change `illustration`'s shape.** The good sources are plain REST `GET`s with query + page + per-page, returning per-clip metadata that maps onto the `RetrievalSource` façade. What changes is the **result** (duration, a list of renditions, poster frames, optional in/out points) and the **rights perimeter** (music in soundtracks, identifiable people, editorial-only footage, platform terms that forbid downloading even CC-licensed clips).
- **Recommended first three providers:** **Pexels Videos** (free key, constant permissive licence, per-rendition fps and resolution; same shape as the existing Pexels adapter) [2], **Wikimedia Commons video** (no key, per-file CC licence URLs, duration and transcodes; the existing Wikimedia adapter plus `filetype:video`) [3], and **Europeana video** (free key, machine-readable rights URIs, direct MP4s, and it already aggregates Open Beelden and EUscreen archival footage) [4][5].
- **Next in line:** Pixabay Videos (free, trivial on top of the existing Pixabay adapter) [6], NASA Image and Video Library (no key, public domain with conditions) [7][8], then the archival heavyweights that need moment retrieval because they serve whole reels: the US National Archives catalog (Universal Newsreel and more) [9][10], the Internet Archive [11] and the Library of Congress National Screening Room [12].
- **Not sources, only discovery:** YouTube and Vimeo. A CC-BY licence on a YouTube video grants copyright permission, but YouTube's Terms and API Developer Policies forbid downloading or storing the audiovisual content without YouTube's approval [13][14]; Vimeo only gives file links for your own account's videos [15]. SERP APIs and `yt-dlp` are likewise out: they find, they do not license [16][14][17].
- **Paid tier, later:** Vecteezy is the only self-serve pay-as-you-go video API found ($0.002/call, $1/download) [18]; Shutterstock, Getty and Adobe Stock video licensing are contract-gated [19][20][21]. Escalate only when free recall is measurably poor or indemnity is required.
- **Schema recommendation:** a shared `MediaResult` base with `ImageResult` and a sibling `VideoResult`, tagged by a `media_type` literal (a Pydantic discriminated union, which exports to JSON Schema `oneOf` and round-trips to Zod) [22][23]. Never make `VideoResult` a subclass of `ImageResult`: code typed on images (the `burns` hook) would silently accept a video.

---

## 1. Scope and method

The user's request: *"I would like illustration to also be able to find videos. Can you do some deep research on this to be able to find sources of video footage that we can search and use?"* "Search and use" sets the bar: a source counts only if it can be **queried programmatically** and its footage can be **legally downloaded and edited into a narrated video** for commercial-adjacent publication (the same bar R3 set for images [1]).

Five research passes ran in parallel on 2026-09-24: free stock video APIs; open / Creative Commons archives; public-domain government and archival footage; paid stock video; and the technical side (schema, relevance scoring, moment retrieval, transcoding). Claims were checked against live official documentation and, for no-key APIs, against live anonymous API calls on that date. Where a page could not be fetched (403s from Cloudflare, JavaScript-only pages) the claim rests on a search snippet or third-party source and is marked *unverified* or *(third-party)*.

`illustration`'s mandate is unchanged by any of this: **retrieval, not generation, and its job ends at choosing.** Downloading, trimming, transcoding and rendering belong downstream. Where this note discusses those, it is to say what the *result* must carry so a downstream consumer can do them.

---

## 2. What changes when the medium is video

These cross-cutting findings shape every provider section below.

**2.1 The content licence is not the whole perimeter.** For images, the licence on the file was nearly the whole story. For video, the *platform's* terms can forbid acquisition even when the *content* licence permits reuse. YouTube is the clean example: it offers CC BY [24], but its Terms bar downloading "unless expressly authorized by the Service" [13], and its API Developer Policies forbid downloading, caching or storing audiovisual content, or separating the audio from the video, without YouTube's prior written approval [14]. The sanctioned routes are YouTube's own editor, or getting the file directly from the creator [24]. Vimeo [25] and Dailymotion [26] are similar. So a source qualifies only if **both** the content licence and the access terms allow download.

**2.2 Machine-learning clauses touch reranking.** Several stock terms now forbid ML use of their content: Magnific (formerly Freepik) forbids use for "any machine learning and/or artificial intelligence purposes" [27]; Coverr bans "training AI algorithms, creating AI models, or as a dataset" [28]; Vecteezy bans "data training" [29]; Adobe's API FAQ says API downloads for machine learning are not permitted [21]; Envato bans AI/ML training [30]. `illustration`'s Layer 2 embeds candidate thumbnails with SigLIP-2 at query time. That is not training, but the broadest of these clauses (Magnific's) plausibly covers it. The Pexels and Pixabay licence pages carry no such clause [31][32]. This is a reason to prefer Pexels, Pixabay and the open archives first, and a question to put to counsel before shipping the others.

**2.3 Soundtracks carry separate rights.** A public-domain film can still carry a copyrighted score [33]. Archive holders cannot license the likenesses of the people in their clips, and music needs both sync and master-use rights [34]. Prelinger material is mostly public domain, but music inside it is a known grey area [35]. ESO and ESA/Hubble videos are CC BY 4.0 **except the music** [36][37]; the European Commission's CC BY 4.0 footage likewise excludes third-party works and music rights [38]. Pixabay warns that "audio or video samples" may need third-party consent [39]. Since a narrated video replaces the soundtrack anyway, the safe default downstream is to **strip audio**; a result should say whether audio exists so that default can be applied knowingly.

**2.4 People, endorsement and editorial use.** Pexels forbids showing identifiable people in a bad light or implying endorsement [31]. NASA material is generally not copyrighted, but identifiable people need permission for commercial use and the NASA insignia is protected [8]. Paid libraries mark clips **editorial-only** and carry model/property-release flags (Shutterstock's `is_editorial`, `has_model_release`, `has_property_release` [40]; Getty's `license_model` / `allowed_use` and separate editorial endpoints [41]). Those flags are rights-bearing and must survive persistence exactly like `license` does today.

**2.5 The US federal public-domain rule has edges.** 17 U.S.C. §105 denies copyright to works of the US Government, but not to works the government holds by assignment, not to contractors' works, and not to state or local government works [42][43]. Federal sites may carry third-party material, agency logos need permission, identifiable people may have publicity rights, and protection abroad may differ [43]. So a federal source should set a *default* public-domain code that any per-item restriction overrides.

**2.6 Rendition URLs expire; identity must not.** Pexels video file links have been reported to be signed Vimeo URLs [44]; Vimeo's own API download links last 24 hours [15]; Shutterstock's licensed download links last 8 hours [45]; Getty's under 24 hours [20]. A rendition URL is therefore **never** an identity. Persist `(provider, id)` (plus in/out points) and re-resolve URLs when needed.

**2.7 Files are large, and archival sources serve whole reels.** A NASA original sampled at 720×480 was 1.45 GB [7]; a National Archives sample was a 1.49 GB MP4 covering eight reels [9]. Archival sources return *films*, not *clips*, which makes **moment retrieval** (finding the six seconds inside ten minutes) part of retrieval for those sources (§7).

**2.8 Codecs vary.** Wikimedia Commons serves only WebM (VP9/AV1/VP8) for video, no H.264 MP4 [46]; its 360p MPEG-4 derivative is MPEG-4 Part 2 in QuickTime, not H.264 [3]. Stock providers serve H.264 MP4. A result should expose each rendition's container and codec so a consumer can pick an editing-friendly one or transcode.

---

## 3. Free stock video APIs

### 3.1 Pexels Videos — *recommended, #1*

- **Search.** `GET https://api.pexels.com/v1/videos/search`, key in an `Authorization: <key>` header (no `Bearer`). Parameters: `query`, `orientation` (landscape/portrait/square), `size` (large = 4K, medium = Full HD, small = HD), `locale`, `page`, `per_page` (default 15, max 80) [2].
- **No duration filter on search.** `min_duration` / `max_duration` / `min_width` / `min_height` exist only on the Popular Videos endpoint [2]; duration must be filtered client-side (every hit carries it).
- **Per clip.** `id`, `width`, `height`, `duration` (seconds), `url` (the Pexels page), `image` (poster frame), `user{id,name,url}`, `video_files[]` (`quality` hd/sd, `file_type`, `width`, `height`, `fps`, `link`) and `video_pictures[]` (preview frames) [2]. No tags field is documented, and no file size.
- **Licence.** Constant across the corpus: commercial use allowed, attribution not required; banned are showing identifiable people in a bad light, selling unaltered copies, implying endorsement, redistribution on other stock platforms, and use as a trademark [31]. The API rules require a prominent link to Pexels, ask you to credit creators when possible, and forbid replicating Pexels' core functionality [2]; the terms ban compiling content to replicate a competing service and bulk systematic copying [47].
- **Download.** Direct links SD → 4K [2]; reportedly signed Vimeo URLs [44], so treat them as expiring.
- **Rate / cost.** Free; 200 requests/hour and 20,000/month, reported in `X-Ratelimit-*` headers; unlimited on request [2].
- **Fit.** Excellent. Same host, auth and pagination as the existing `pexels` image adapter; only `_items` (`videos`) and `_normalize` differ. `PEXELS_API_KEY` is already wired in `credentials`.

### 3.2 Pixabay Videos — *next in line*

- **Search.** `GET https://pixabay.com/api/videos/?key=…` (key as a query parameter). Parameters: `q` (≤100 chars), `lang`, `video_type` (all/film/animation), `category`, `min_width`, `min_height`, `editors_choice`, `safesearch`, `order`, `page`, `per_page` (3–200) [6]. No orientation or duration filter.
- **Per hit.** `id`, `pageURL`, `tags` (comma string), `duration`, `user`, `user_id`, `userImageURL`, and four fixed renditions `videos.{large,medium,small,tiny}` each with `url`, `width`, `height`, `size`, `thumbnail`; `large` (≈3840×2160) is sometimes empty [6]. No fps.
- **Licence.** Constant: commercial use, no attribution; banned are standalone redistribution of unaltered content, trademarked content on merchandise, and immoral or misleading use of recognisable people [32]. The terms warn that identifiable people, logos and "audio or video samples" may need third-party consent [39].
- **API terms.** Show users where the media is from; cache search requests for 24 hours; no systematic mass downloads. Unlike images, videos "may be embedded directly in your applications" [6].
- **Rate / cost.** Free; 100 requests per 60 seconds, with `X-RateLimit-*` headers and HTTP 429 [6].
- **Fit.** Excellent and nearly free to build on the existing `pixabay` adapter (`_auth_params`, `min_per_page = 3`). Ranked after Pexels only because it overlaps it (generic b-roll) and adds no new capability.

### 3.3 Coverr

- **Search.** `GET https://api.coverr.co/videos` with `Authorization: Bearer <key>` or `?api_key=`; keys by email to the Coverr team [48]. Parameters: `query`, `page` (0-based), `page_size` (default 20), `urls=true` (needed to get links), `sort` [49].
- **Per clip.** `id`, `title`, `description`, `duration`, `max_width`, `max_height`, `thumbnail`, `poster`, `tags`, `is_vertical`, `aspect_ratio`, and `urls{mp4, mp4_preview, mp4_download}`; pinging a download stats endpoint is mandatory [49].
- **Licence.** Site licence: commercial use, no attribution; bans redistribution, competing services and AI training; no model releases [28]. The API page requires a clickable Coverr logo and, contradictorily, says access is free "as long as you don't… use the videos for commercial use" [50]. **Get a written answer on that contradiction before building.**
- **Fit.** Moderate: gated key, 0-based pages, logo and download-ping duties, the ML clause.

### 3.4 Magnific (formerly Freepik; Videvo's library now lives here)

- Freepik rebranded as Magnific in 2026 [51]; Videvo was acquired by Freepik [52] and its site now redirects there.
- **Search.** `GET https://api.magnific.com/v1/videos` with an `x-magnific-api-key` header; `term`, `page`, `order`, and deepObject filters `aspect_ratio`, `category` (footage/motion_graphics), `duration{from,to}`, `orientation`, `license{free,premium}`, `resolution{720,1080,2k,4k}`, `fps`, `ai-generated{excluded,only}`, `author` [53]. The richest filter set of any free-tier provider, including an **AI-generated exclusion**.
- **Per clip.** `id`, `name`, `url`, `quality`, `duration` as `"HH:MM:SS"`, `aspect_ratio`, `premium` (0/1), `is_ai_generated`, `author`, `thumbnails[]`, `previews[]`; the MP4 comes from a separate `GET /v1/videos/{id}/download` [53][54].
- **Licence.** Per clip (free vs premium). Free content requires attribution to the site and the contributor; resale and sublicensing are banned; and the broad ML clause of §2.2 applies [27].
- **Rate / cost.** Per-key 30,000 requests/minute; per-IP 50/s burst, 10/s sustained [55]. On Premium-class plans stock downloads through the API cost no credits but are capped at 100 a day [56].
- **Fit.** Good API, heavier integration (two-step download, duration parsing, attribution duty) and the ML-clause risk. A strong *cheap subscription* candidate later.

### 3.5 Vecteezy

- **API.** `GET /v2/{account_id}/resources?term=&content_type=video`, with `license_type` (commercial/editorial), `ai_generated`, `duration` buckets, `sort_by`; page×per_page capped at 10k; tags, dimensions and `ai_generated` "only available for paid customers" [57].
- **Cost.** Free plan: unlimited calls, 500 downloads/month, watermarked previews. Pay-as-you-go: $0.002 per call and $1.00 per download [18].
- **Licence.** The free licence requires attribution and caps use (print runs, project budgets under $1,000, no products for resale); editorial-only content is a separate class; data training and directly competitive use are banned [29].
- **Fit.** Poor as a free source (budget cap, attribution), but the **best self-serve pay-as-you-go paid path** (§6).

### 3.6 Storyblocks

`GET /api/v2/videos/search`, HMAC-signed (`APIKEY`, `EXPIRES`, `HMAC`) with `project_id` and `user_id`; filters include `min_duration`/`max_duration`, `quality`, `frame_rates`, `has_talent_released`, `has_property_released`, `is_editorial`; `results_per_page` ≤250 [58]. Free test keys are for internal testing only; production is an enterprise contract, roughly $6k–$12k+/year *(third-party)* [58][59]. A paid-tier option, not a v1 source.

### 3.7 No API

Mixkit (Envato) has free and restricted licences but no API [60]. Unsplash's API has no video [61]. Dareful is CC BY 4.0 4K footage with no API [62]. Videezy (Vecteezy's sister), Mazwai and Life of Vids had no API found, and the last two were unreachable on the research date *(unverified)*. Openverse does **not** index video: `/v1/video/` returns 404 and the project covers images and audio only [63][64].

---

## 4. Open and Creative Commons archives

### 4.1 Wikimedia Commons (video) — *recommended, #2*

- **Search.** The existing adapter's query plus a keyword: `action=query&generator=search&gsrnamespace=6&gsrsearch=<q> filetype:video&prop=imageinfo|videoinfo`, offset pagination via `gsroffset`/`continue`; no key [3]. `filemime:video/webm`, `filew:>1000` / `fileh:>1000` also work, and CirrusSearch documents a duration keyword (untested) [65]. Live counts on the research date: 412,191 files for `filetype:video` [3].
- **Per clip.** `imageinfo` returns `width`, `height`, `duration` (seconds), `size`, `mime`, `mediatype=VIDEO`, `thumburl` (a JPG poster sized by `iiurlwidth`), `url` (the original) and `descriptionurl`; `videoinfo&viprop=derivatives` lists transcodes (240p/480p VP9 WebM, a 360p MPEG-4 Part 2 `.mov`) [3]. Originals are often Ogg Theora.
- **Licence.** Per file, via the same `extmetadata` the image adapter already reads: `LicenseShortName`, `LicenseUrl`, `Artist`, `Credit`, `AttributionRequired`, `UsageTerms` [3]. The Foundation gives no warranty; reusers must verify status, and personality and trademark rights may still apply [66]. `licensing.normalize_license` already handles the Commons dialect.
- **Rate.** 2026 global limits: 10 requests/min with no User-Agent, 200/min with a User-Agent carrying contact details [67] (compare open issue [thorwhalen/illustration#27](https://github.com/thorwhalen/illustration/issues/27) on the policy-compliant User-Agent).
- **Fit.** Excellent: no key, per-file CC URLs, duration and renditions, and most of the code already exists. The catch is format: WebM/Ogg only, so downstream transcoding is expected [46].

### 4.2 Europeana (video) — *recommended, #3*

- **Search.** `GET https://api.europeana.eu/record/v2/search.json?wskey=<key>&query=<q>&qf=TYPE:VIDEO&media=true&reusability=open&rows=&start=` (or `cursor=*`, which returns `nextCursor`) [4]. `qf=MIME_TYPE:video/mp4` narrows to MP4; `video_duration=short` had no effect in live tests [4]. A key needs a Europeana account; personal keys are for non-production use, project keys for production; there is no throttling but pauses between calls are requested [68].
- **Per clip.** `id`, `title[]`, `rights[]` (a URI), `dcCreator[]`, `dataProvider`, `edmIsShownBy` (a direct, playable MP4 in live results), `edmIsShownAt` (landing page), `edmPreview` (thumbnail), `guid`; the record endpoint's `webResources` add MIME type, `ebucoreDuration` (ms) and dimensions [4].
- **Licence.** Rights are URIs from Creative Commons (licences and PDM) or rightsstatements.org (InC, InC-EDU, NoC-NC, NoC-OKLR, CNE); `reusability=open` means CC BY, CC BY-SA, CC0 or PDM [5]. That is the cleanest machine-readable rights vocabulary among the free sources.
- **Size.** 389,151 video records, but only about 12,000 are both open and playable [4]; small, but curated and archival (European newsreels and broadcast heritage), which is exactly what the commentary genre needs.
- **Also covers** Open Beelden (Netherlands Institute for Sound & Vision; everything CC or public domain, OAI-PMH only, no keyword search) [69][70] and EUscreen [71], so neither needs its own adapter.
- **Fit.** Very good. New vocabulary work: `normalize_license` must learn CC and rightsstatements.org **URIs**, and `InC*` / `NoC-NC` must never pass the default allowlist.

### 4.3 Internet Archive (incl. Prelinger)

- **Search.** `advancedsearch.php?q=<lucene>&fl[]=identifier&fl[]=title&fl[]=licenseurl&fl[]=creator&fl[]=runtime&rows=&page=&output=json`, no key; filters `mediatype:movies`, `licenseurl:*creativecommons.org*`, `collection:prelinger` [11]. The scrape API pages with a cursor, minimum count 100 [72]. Live counts: 1,173,148 movies with a CC licence URL; 10,468 Prelinger items [11].
- **Per item.** Search gives `licenseurl` and `runtime` ("HH:MM:SS", often missing); `/metadata/{id}` adds `files[]` with `format` (h.264, Ogg Video, MPEG-2 original), dimensions, `length`, `size`, and frame thumbnails [73]. h.264 derivatives are generated with the `moov` atom at the front, so range requests work [74].
- **Licence.** `licenseurl` is uploader-entered and often absent, and copyrighted uploads surface in plain movie searches [11]. The Terms say access is "for scholarship and research purposes only" [75] (archived copy). Prelinger's music caveat applies (§2.3).
- **Fit.** Huge but noisy. Require `licenseurl` (or a PD collection) as a hard filter, and pair with moment retrieval since most items are full films. Phase 2.

### 4.4 Flickr video

`flickr.photos.search&media=videos&license=…&extras=license,owner_name,media,url_o` [76]; licence IDs map to CC URLs including CC 4.0, CC0 and PDM [77]; non-owners get renditions up to 1080p via `getSizes` [78]. Commercial use needs a commercial key, caching only "for reasonable periods", and an endorsement notice [79]. Clean licensing, awkward access. Later, if at all.

### 4.5 Discovery-only platforms

- **YouTube Data API v3**: `search.list` with `videoLicense=creativeCommon` finds CC BY videos [80], but download is forbidden (§2.1) [13][14]. Useful only to surface a clip for a human to request from the creator.
- **Vimeo**: search supports CC filters and returns short licence tokens (`by`, `by-sa`, `cc0`) [81], but file links are for your own account's videos and need a paid plan [15]; the Terms forbid downloading without the owner's consent [25].
- **Dailymotion**: no CC filter found, and the Terms forbid downloading without consent [26].
- **Pond5 Public Domain**: a web collection behind an account, free including commercially, with no public search API found [82].

---

## 5. Public-domain, government and archival footage

### 5.1 NASA Image and Video Library — *next in line*

- **Search.** `GET https://images-api.nasa.gov/search?q=&media_type=video&page=&page_size=`, **no key** (live anonymous calls worked); also `center`, `keywords`, `year_start`/`year_end`, etc.; deep paging stops at 10,000 results [83][7].
- **Per clip.** `nasa_id`, `title`, `description`, `date_created`, `center`, `keywords[]`, preview JPGs and a captions link; renditions (`~orig.mp4`, `~medium`, `~small`, `~mobile`, `~preview`) and duration require follow-up calls to `/asset/{nasa_id}` and `metadata.json` [7].
- **Licence.** Generally not copyrighted; acknowledge NASA; no implied endorsement; insignia protected; identifiable people need permission for commercial use; third-party items marked with the holder's name [8]. No per-item licence enum; set a `PD-USGov`-style default and parse the third-party markers.
- **Fit.** Excellent mechanically; narrow domain (space and aeronautics). One or two lazy follow-up calls per selected item.

### 5.2 US National Archives (NARA) Catalog API v2

- **Search.** `GET https://catalog.archives.gov/api/v2/records/search?q=` with an `x-api-key` header; keys by email; `typeOfMaterials`, `availableOnline`, `page`, `limit` [84][85]. Live: "universal newsreel" + `Moving Images` + online returned 4,054 hits [9].
- **Per record.** `naId`, `title`, `productionDates`, `shotList`, `soundType`, `subjects`, and `digitalObjects[]` (`objectUrl`, `objectType` "Audio/Visual File (MP4)", `objectFileSize`); no thumbnail in the sampled record [9].
- **Licence.** Generally public domain, but donated material may be copyrighted; each record's structured `useRestriction` (e.g. `status: "Restricted - Possibly"`, `specificUseRestrictions: ["Copyright"]`) must be read [84][9]. API users must show a not-endorsed notice [85]. Universal Newsreel (1929–67) was deeded without copyright restrictions, though individual stories may carry third-party rights [86][10].
- **Rate.** 10,000 queries/month per key by default [84].
- **Fit.** Strong for historical newsreels — the best match for music-history commentary — but whole-reel files (≈1.5 GB) and no thumbnails mean it needs moment retrieval and server-side frame grabs. Request a key early.

### 5.3 Library of Congress (loc.gov JSON)

Any search page plus `fo=json`, no key [87]; 20 requests/min with a one-hour block if exceeded, and 429s or CAPTCHA pages under load [88]. Rights fields (`rights_advisory`, `access_restricted`) vary by collection and are not comprehensive [89]. The National Screening Room offers titles the Library believes are PD as MP4 and ProRes 422 MOV; "rights assessment is your responsibility" [12]. Live calls from the research machine hit Cloudflare 403s, so the response shape is *unverified*. Richest content for film and music history; weakest operations. Harden before shipping.

### 5.4 Other government sources

- **NPS**: `GET developer.nps.gov/api/v1/multimedia/videos` with an api.data.gov key returns duration, credit, captions, transcript, an `isBRoll` flag and MP4 renditions 360p–1080p in one call [90][91]. No rights field; apply the §105 default.
- **DVIDS** (US military): a clean keyed API with MP4 and HLS renditions [92][93]; public domain unless indicated, credit requested, free for commercial use with attribution to DVIDS [94][95]. Modern military content; low relevance for commentary.
- **Smithsonian Open Access**: only 128 video records, all with `online_media: null` and rights "permission required" — metadata is CC0, video is not delivered [96]. Skip.
- **ESA** (standard licence non-commercial by default; some CC BY-SA 3.0 IGO) [97], **ESO / ESA-Hubble** (CC BY 4.0 excluding music; credit must be visible) [36][37], **European Commission AV service** (CC BY 4.0, excluding third-party works and music) [38], **USGS** (PD unless noted) [98], **NOAA** (library video lives on YouTube) [99]: no search APIs found; not adapters.

### 5.5 Commercial archives

British Pathé (per-second pricing, 60-second minimum) [100] and Periscope Film (per-second, ProRes masters by FTP) [101] have no public API. They are human-licensing escalations, never a `RetrievalSource`.

---

## 6. Paid stock video (escalation path)

| Provider | Search API | Self-serve? | Notable |
|---|---|---|---|
| **Vecteezy** | REST, `license_type` editorial filter | **Yes**, $0.002/call, $1/download [18] | the only self-serve pay-as-you-go video API found [57] |
| **Magnific** | REST, rich filters incl. AI-generated | subscription; 100 free-credit downloads/day on Premium-class plans [56] | ML clause [27] |
| **Shutterstock** | `GET /v2/videos/search`, duration/fps/resolution/editorial/model-release filters [45] | free tier is **images only**; video is Contact Sales [19] | best per-clip rights flags (`is_editorial`, release flags) [40]; licensed links expire in 8 h [45] |
| **Getty / iStock** | `/v3/search/videos/{creative,editorial}`, clip-length, frame-rate, release-status filters [41] | key tied to a licence agreement via a rep [20] | editorial split by endpoint |
| **Adobe Stock** | `Search/Files` with `content_type:video`, duration buckets, `has_releases` [102] | search keys free; licensing via API is Enterprise/affiliate only [21] | watermarked previews usable for search-then-license |
| **Storyblocks** | HMAC-signed REST [58] | enterprise contract | flat-fee unlimited model *(third-party pricing)* [59] |
| **Pond5** | partner API | unverified | owned by Shutterstock since 2022 [103] |
| Artlist, Envato, Motion Array, Filmsupply | none for footage | — | Artlist's API is music [104]; Envato has a search-only MCP server and bans bots [105][30] |

**When to escalate:** stay on free sources until recall on real narration queries is measurably poor; then Vecteezy pay-as-you-go (same GET/page shape, no contract); then a cheap subscription (Magnific, subject to the ML-clause question); and only when editorial/news footage, 4K masters or real indemnification are required, an enterprise contract with Shutterstock, Getty or Adobe. Their watermarked search can feed a human "license this" queue in the meantime.

**Not sources.** SERP APIs (SerpApi's YouTube/Google Videos engines, DataForSEO's YouTube SERP) return URLs and snippets with no grant of rights [16][106]. `yt-dlp`-style downloading breaches YouTube's Terms [13], and a German appeals court held a host liable for hosting youtube-dl under anti-circumvention rules [17]. `illustration` must neither ship nor document downloading as a retrieval backend.

---

## 7. Comparison

| Source | Key | Per-clip licence data | Commercial | Attribution | Download | Rate / cost | Fit |
|---|---|---|---|---|---|---|---|
| Pexels Videos | free | constant (Pexels License) | yes | not required (link to Pexels) | direct MP4 SD→4K, signed | 200/h, 20k/mo | ★★★ |
| Pixabay Videos | free | constant (Pixabay License) | yes | not required (show source) | direct MP4, 4 tiers | 100/min, 24 h cache | ★★★ |
| Wikimedia Commons | none | per file, CC URL | per licence | usually required | WebM/Ogg | 200/min with UA | ★★★ |
| Europeana | free (account) | per record, CC/rightsstatements URI | per licence | per licence | direct MP4 | unthrottled, pauses | ★★★ |
| NASA | none | none (PD-by-default + markers) | yes, conditions | acknowledge NASA | MP4 renditions | undocumented | ★★☆ |
| NARA | free (email) | structured `useRestriction` | mostly | not-endorsed notice | whole-reel MP4 | 10k/mo | ★★☆ |
| Internet Archive | none | uploader `licenseurl`, often missing | per licence; ToS "research" | per licence | h.264/Ogg | undocumented | ★☆☆ |
| Library of Congress | none | varies by collection | PD titles | — | MP4, ProRes | 20/min, Cloudflare | ★☆☆ |
| NPS | api.data.gov | none | PD default | credit | MP4 360p–1080p | 1,000/h | ★★☆ |
| Coverr | by email | constant | contradictory | logo | MP4 | undocumented | ★☆☆ |
| Magnific | paid plans | per clip (free/premium) | yes | free tier: required | two-step MP4 | generous | ★★☆ (ML clause) |
| Vecteezy | free/PAYG | per clip | paid: yes | free tier: required | metered | $1/download | ★★☆ (paid) |
| YouTube, Vimeo, Dailymotion | — | CC tokens | — | — | **forbidden by platform** | — | discovery only |

---

## 8. Fit with the `RetrievalSource` façade

**What maps directly.** Every recommended source is a keyed or anonymous `GET` with a query parameter and a page/per-page pair, returning a list of items: exactly the `endpoint` / `query_param` / `per_page_param` / `max_per_page` / `_items` / `_normalize` contract. Pexels Videos needs `_auth_headers` (already implemented for images); Pixabay Videos needs `_auth_params` and `min_per_page = 3` (already implemented); Commons needs `fixed_params` + `_page_params` offset pagination (already implemented); Europeana needs a key in `_auth_params` and either `start` offsets or its cursor (a `_page_params` override).

**Quirks the base class must tolerate.**

1. **Lazy follow-up calls.** NASA (asset manifest), the Internet Archive (`/metadata/{id}`), Magnific (`/download`) and Europeana (`webResources` for duration) need a second call per item for renditions or duration. The search stage should not make them for every hit; a `resolve(result)` hook, called only for shortlisted or chosen items, keeps search cheap and matches the "URLs expire, re-resolve" rule of §2.6.
2. **Client-side filters.** Duration is the canonical video filter, but only some providers filter it natively (Magnific, Vecteezy, Shutterstock, Getty, Storyblocks, Pexels' popular endpoint), and not the two recommended stock sources. Every video hit carries its duration, so `min_duration` / `max_duration` can be honoured by a façade-level post-filter where the native param is missing. That is a deliberate departure from pure `param_map` translation and should be decided explicitly (the ≥2-provider promotion rule would otherwise leave duration in the escape hatch).
3. **Media-type selection.** Pexels and Pixabay serve images and videos from different endpoints. The simplest open-closed design is **one source per (provider, media type)**, e.g. `pexels_video` alongside `pexels`, each declaring its media type in `SourceInfo`; `search(q, media="video")` then picks the registered video sources. This keeps each subclass single-endpoint and leaves the existing image sources untouched.

**Parameter mapping for video.** `orientation` maps natively on Pexels and Magnific (Commons and Europeana do not filter it); `size` maps to Pexels' `size` and to Pixabay's `min_width`; `safe` maps to Pixabay's `safesearch`. The canonical names already exist, so video adds only `min_duration` / `max_duration` as candidates.

---

## 9. What a video result needs in the schema

**Fields.** Beyond today's `ImageResult`, a video hit needs: `duration_s`; `fps`; `has_audio`; a **list of renditions** (each: `url`, `mime_type`, `video_codec`, `width`, `height`, `fps`, `size_bytes`, the provider's own `quality_label`, and `expires_at` for signed URLs); a `poster_url` and optional `preview_frames` / `preview_clip_url`; and optional **in/out points** (`moment: TimeSpan`) for a span inside a longer film. The existing providers' shapes confirm this: Pexels `video_files[]` + `video_pictures[]` [2], Pixabay's fixed tiers [6], Shutterstock's `assets` object [107]. Openverse made the same choice for audio: a sibling schema sharing the licence core, adding `duration` and an `alt_files[]` rendition list [108]. OpenTimelineIO models the span as `Clip.source_range` over an `ExternalReference.available_range` [109], schema.org as a `Clip` with `startOffset`/`endOffset` [110][111], and W3C media fragments give it a stable URI form, `#t=start,end` [112]. The `lacing` persistence and its OTIO export already speak this language.

**Rights fields.** Video adds rights-bearing facts: `editorial_only`, `has_model_release`, `has_property_release` (from Shutterstock-class providers) and an `audio_policy` (§2.3). Per the repo's licence/attribution invariant, every new field must be classified as rights-bearing or not; these four are, so they join `RIGHTS_FIELDS` and `persistence._CandidateRef` under the same names, optional with `None` meaning "not recorded" (additive, no `lacing` migration).

**Modelling.** Three options were compared:

| Option | Verdict |
|---|---|
| `VideoResult(ImageResult)` subclass | **Reject.** A video is not an image; anything typed on `ImageResult` (the `burns` render hook, `sequence`'s pHash dedupe) would silently accept one. |
| One model + `media_type` + optional video fields | Reject. Nothing enforces that a video has a duration; a pile of optionals. |
| **Shared base → `ImageResult` / `VideoResult`, tagged by a `media_type` literal** | **Adopt.** Fused result lists can mix modalities for RRF and MMR; Pydantic dispatches on the tag and emits `oneOf` with a discriminator mapping in JSON Schema [22], which Zod's `discriminatedUnion` round-trips (generate Zod at build time; runtime `fromJSONSchema` is experimental) [23]. Old payloads without a tag default to `"image"` via a callable discriminator [22]. |

```python
class Rendition(BaseModel):
    url: str
    mime_type: str | None = None  # "video/mp4", "video/webm"
    video_codec: str | None = None  # confirm with ffprobe downstream
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    size_bytes: int | None = None
    quality_label: str | None = None  # provider's own: "hd", "tiny", "_4k"
    expires_at: datetime | None = None  # signed URLs


class TimeSpan(BaseModel):  # seconds; ↔ OTIO TimeRange, schema.org Clip
    start: float
    end: float


class MediaResult(BaseModel):  # today's shared fields, rights record included
    media_type: str
    provider: str
    id: str
    ...


class ImageResult(MediaResult):
    media_type: Literal["image"] = "image"
    ...  # unchanged


class VideoResult(MediaResult):
    media_type: Literal["video"] = "video"
    duration_s: float
    fps: float | None = None
    has_audio: bool | None = None
    renditions: list[Rendition] = []
    poster_url: str | None = None
    preview_frames: list[str] = []
    moment: TimeSpan | None = None
    editorial_only: bool | None = None
    has_model_release: bool | None = None
    has_property_release: bool | None = None
```

`url` on a `VideoResult` should be the best progressive rendition at search time (so existing consumers that read `.url` keep working), with the understanding that it may expire. `to_search_hit` sets `surface_kind="video"`. `licensing.normalize_license` needs new aliases for rightsstatements.org URIs (which must never canonicalise to an open licence), CC licence **URLs** (Europeana), a US-government public-domain code, and CC BY-SA 3.0 IGO.

---

## 10. Layer 2 for video (later)

Not needed for the first providers, but it shapes the schema, so briefly:

- **Cheap-first cascade.** Tier 0: metadata text through the existing fusion (~free). Tier 1: the poster frame through the existing SigLIP-2 reranker (same cost as one image). Tier 2: sample 1–3 keyframes per shot from the smallest rendition and max-pool the image embeddings (max-pool for "any part matches", mean-pool for "the whole clip is about X"; Perception Encoder averages 8 frames for its video embedding [113]). Tier 3: a VLM judge on the top-k windows only; Gemini accepts start/end offsets and samples 1 fps by default [114][115]. One vendor benchmark put frame-pooled SigLIP 2 well below dedicated video embeddings (nDCG@10 0.325 vs ≈0.76), on 20 videos, from a vendor that sells video search, so treat it as indicative only [116]. Hosted indexing (TwelveLabs) costs about $2.50 per video hour [117]; open video-text models include VideoPrism (JAX only) [118] and InternVideo2-CLIP [119].
- **Moment retrieval** for whole-reel archival sources: split into shots (PySceneDetect's adaptive and threshold detectors, CPU-only, handle cuts and fades [120]; TransNetV2 is the stronger learned detector [121]), score shots by keyframe embeddings fused with an ASR transcript via the existing RRF, pick the best span that fits the narration beat, optionally refine with Lighthouse's moment-retrieval models [122], and persist the span as a `moment`. Partial download of just the span is cheap because ffmpeg seeks over HTTP with range requests [123] when the MP4 is faststart, which Internet Archive h.264 derivatives are [74].
- **Dedupe.** The DCT pHash in `sequence` does not carry over; vPDQ matches a clip inside a longer video [124].
- **Audio.** Default to stripping it downstream; if kept, an AudioSet tagger such as PANNs can flag music for clearance [125].

All of this stays inside the mandate: it *chooses* a clip and a span. Cutting, transcoding and rendering the span belongs to the consumer (`illustration.video`'s `burns` hook is stills-only and should stay so).

---

## 11. Recommendation

**Build order.**

1. **Schema and façade seam first** (no provider can ship without it): `MediaResult` / `ImageResult` / `VideoResult` discriminated union, `Rendition`, `TimeSpan`, the four new rights fields in `RIGHTS_FIELDS` and `_CandidateRef`, `SourceInfo` media type, `search(..., media=)`, and the duration post-filter decision.
2. **Pexels Videos** — proves the seam on the simplest, cleanest-licensed source; key already wired.
3. **Wikimedia Commons video** — no key, per-file CC licences, reuses the existing adapter; brings archival breadth.
4. **Europeana video** — the archival source with machine-readable rights; forces the licence-URI vocabulary work that NARA and others will need too.

Then, as demand appears: Pixabay Videos and NASA (cheap wins); NARA, Internet Archive and Library of Congress once moment retrieval exists; Vecteezy as the first paid source.

**Why these three.** Together they cover generic modern b-roll (Pexels) and historical/cultural footage (Commons, Europeana), exercise all three auth styles (header key, none, query key), all carry per-clip or constant licence data that populates the rights record without guessing, and none has an ML-use clause or a platform download ban.

---

## 12. Open questions

1. **ML-use clauses.** Does query-time embedding of thumbnails fall under Magnific/Coverr/Vecteezy's "machine learning" bans? Needs a human (or counsel) decision before those providers ship.
2. **Duration filter semantics.** Accept a façade-level post-filter for `min_duration` / `max_duration` (a departure from pure translation), or keep it in the escape hatch until two providers filter natively?
3. **Keys to request.** Europeana (account; project key for production) and, later, NARA (by email). Both need a human.
4. **Coverr's commercial-use contradiction** (§3.3) — only worth asking if Coverr is ever wanted.

---

## References

1. [illustration R3 — Image Source API Audit for Commercial-Adjacent Video Production (2026), this repo](illustration_03%20--%20Image%20Source%20API%20Audit%20for%20Commercial-Adjacent%20Video%20Production%20%282026%29.md)
2. [Pexels API documentation](https://www.pexels.com/api/documentation/)
3. [Wikimedia Commons Action API (live calls, 2026-09-24)](https://commons.wikimedia.org/w/api.php)
4. [Europeana Search/Record API (live calls, 2026-09-24)](https://api.europeana.eu/record/v2/search.json)
5. [Europeana — Available rights statements](https://pro.europeana.eu/page/available-rights-statements)
6. [Pixabay API docs](https://pixabay.com/api/docs/)
7. [NASA Images API (live anonymous calls, 2026-09-24)](https://images-api.nasa.gov/search?q=apollo%2011&media_type=video)
8. [NASA Images and Media Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
9. [National Archives Catalog v2 (live calls, 2026-09-24)](https://catalog.archives.gov/api/v2/records/search)
10. [National Archives — Newsreels at College Park](https://www.archives.gov/research/motion-pictures/newsreels)
11. [Internet Archive advancedsearch (live calls, 2026-09-24)](https://archive.org/advancedsearch.php)
12. [Library of Congress — National Screening Room, About this Collection](https://www.loc.gov/collections/national-screening-room/about-this-collection)
13. [YouTube Terms of Service](https://www.youtube.com/t/terms)
14. [YouTube API Services Developer Policies](https://developers.google.com/youtube/terms/developer-policies)
15. [Vimeo Help — Video file download links from the API](https://help.vimeo.com/hc/en-us/articles/12427806914577-About-video-file-download-links-from-the-API)
16. [SerpApi — YouTube Search API](https://serpapi.com/youtube-search-api)
17. [heise — OLG Hamburg: host liable for youtube-dl](https://www.heise.de/en/news/OLG-Hamburg-Uberspace-liable-for-hosting-Youtube-DL-10179284.html)
18. [Vecteezy Developer API](https://www.vecteezy.com/developers)
19. [Shutterstock API pricing](https://www.shutterstock.com/api/pricing)
20. [Getty Images API documentation](https://developer.gettyimages.com/docs/)
21. [Adobe Stock API business FAQ](https://developer.adobe.com/stock/docs/faq/stock-api-business-faq)
22. [Pydantic — Unions (discriminated unions)](https://pydantic.dev/docs/validation/latest/concepts/unions/)
23. [Zod — JSON Schema](https://zod.dev/json-schema)
24. [YouTube Help — Creative Commons](https://support.google.com/youtube/answer/2797468)
25. [Vimeo Terms of Service](https://vimeo.com/legal)
26. [Dailymotion Terms of Use](https://legal.dailymotion.com/en/terms-of-use/)
27. [Magnific Terms of Use](https://www.magnific.com/legal/terms-of-use)
28. [Coverr License](https://coverr.co/license)
29. [Vecteezy Licensing Agreement](https://www.vecteezy.com/licensing-agreement)
30. [Envato Elements — Acceptable Use Policy](https://help.elements.envato.com/hc/en-us/articles/31035788503321-Acceptable-Use-Policy)
31. [Pexels License](https://www.pexels.com/license/)
32. [Pixabay Content License](https://pixabay.com/service/license/)
33. [Stanford Copyright & Fair Use — Public domain trouble spots](https://fairuse.stanford.edu/overview/public-domain/trouble-spots)
34. [IDA — A short guide to clearing copyrighted footage](https://www.documentary.org/feature/raiding-lost-archives-wisely-and-legally-short-guide-clearing-copyrighted-footage)
35. [Internet Archive Help — Prelinger Archive](https://help.archive.org/help/prelinger-archive/)
36. [ESO — Copyright notice](https://www.eso.org/public/copyright/)
37. [ESA/Hubble — Usage of images and videos](https://esahubble.org/copyright/)
38. [European Commission Audiovisual Service — Conditions of use](https://audiovisual.ec.europa.eu/en/conditions-of-use)
39. [Pixabay Terms of Service](https://pixabay.com/service/terms/)
40. [Shutterstock SDK — Video model](https://github.com/shutterstock/public-api-javascript-sdk/blob/master/docs/Video.md)
41. [Getty Images API OpenAPI v3](https://api.gettyimages.com/swagger/v3/swagger.json)
42. [17 U.S.C. §105 (Cornell LII)](https://www.law.cornell.edu/uscode/text/17/105)
43. [USAGov — Copyright and federal government materials](https://www.usa.gov/government-copyright)
44. [pypexels issue #11 — Pexels video links are signed Vimeo URLs](https://github.com/salvoventura/pypexels/issues/11)
45. [Shutterstock SDK — VideosApi](https://github.com/shutterstock/public-api-javascript-sdk/blob/master/docs/VideosApi.md)
46. [Commons — Video](https://commons.wikimedia.org/wiki/Commons:Video)
47. [Pexels Terms of Service](https://www.pexels.com/terms-of-service/)
48. [Coverr API — Auth](https://api.coverr.co/docs/auth/)
49. [Coverr API — Videos](https://api.coverr.co/docs/videos/)
50. [Coverr API — Before you start](https://api.coverr.co/docs/)
51. [The Next Web — Freepik rebrands as Magnific](https://thenextweb.com/news/freepik-rebrands-as-magnific)
52. [EU-Startups — Freepik acquires Videvo](https://www.eu-startups.com/2022/06/malaga-based-freepik-acquires-uk-based-videvo-adding-audio-and-video-to-its-growing-content-portfolio/)
53. [Magnific — List videos](https://docs.magnific.com/api-reference/videos/get-all-videos-by-order)
54. [Magnific (formerly Freepik) Videos API overview](https://docs.magnific.com/api-reference/videos/videos-api)
55. [Magnific — Rate limits](https://docs.magnific.com/ratelimits)
56. [Magnific — Pricing](https://docs.magnific.com/pricing)
57. [Vecteezy API v2 OpenAPI spec](https://www.vecteezy.com/api-docs/api/v2/swagger.json)
58. [Storyblocks API reference](https://documentation.storyblocks.com/)
59. [CheckThat — Storyblocks pricing (third-party)](https://checkthat.ai/brands/storyblocks/pricing)
60. [Mixkit Licenses](https://mixkit.co/license/)
61. [Unsplash API documentation](https://unsplash.com/documentation)
62. [About Dareful](https://dareful.com/about-dareful-completely-free-4k-stock-video/)
63. [Openverse /v1/video/ (live 404, 2026-09-24)](https://api.openverse.org/v1/video/)
64. [Openverse — API media properties](https://docs.openverse.org/meta/media_properties/api.html)
65. [MediaWiki — Help:CirrusSearch](https://www.mediawiki.org/wiki/Help:CirrusSearch)
66. [Commons — Reusing content outside Wikimedia](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)
67. [Wikimedia APIs — Rate limits](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits)
68. [Europeana API FAQ](https://europeana.atlassian.net/wiki/spaces/EF/pages/2360508417/Europeana+API+FAQ)
69. [Open Beelden API](https://www.openbeelden.nl/api)
70. [Open Beelden OAI-PMH feed (live)](https://www.openbeelden.nl/feeds/oai/?verb=ListRecords&metadataPrefix=oai_oi)
71. [EUscreen Help](https://euscreen.eu/help/)
72. [ia_scrape reference (Internet Archive scrape API parameters)](https://hrbrmstr.github.io/wayback/reference/ia_scrape.html)
73. [Internet Archive Metadata API (live call)](https://archive.org/metadata/GreaterG1953)
74. [Internet Archive — Movies and Videos: A Basic Guide](https://archivesupport.zendesk.com/hc/en-us/articles/360017808151-Movies-and-Videos-A-Basic-Guide)
75. [Internet Archive Terms of Use (archived copy)](https://ia801705.us.archive.org/26/items/05132021/Internet%20Archive%20Terms%20of%20Use.mhtml)
76. [Flickr API — flickr.photos.search](https://www.flickr.com/services/api/flickr.photos.search.html)
77. [Flickr API — flickr.photos.licenses.getInfo](https://www.flickr.com/services/api/flickr.photos.licenses.getInfo.html)
78. [alexwlchan — Flickr video sizes via getSizes](https://alexwlchan.net/til/2025/flickr-video-sizes/)
79. [Flickr API Terms of Use](https://www.flickr.com/services/api/tos/)
80. [YouTube Data API — search.list](https://developers.google.com/youtube/v3/docs/search/list)
81. [Vimeo OpenAPI spec](https://github.com/vimeo/openapi/blob/master/api.yaml)
82. [Pond5 — Public Domain collection](https://www.pond5.com/public-domain)
83. [NASA Images API documentation (PDF)](https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf)
84. [US National Archives — Catalog-API README](https://github.com/usnationalarchives/Catalog-API)
85. [National Archives Catalog API help](https://www.archives.gov/research/catalog/help/api)
86. [The Unwritten Record — Universal Newsreels](https://unwritten-record.blogs.archives.gov/2013/12/30/universal-newsreels-national-archives/)
87. [Library of Congress — JSON/YAML for loc.gov](https://www.loc.gov/apis/json-and-yaml/)
88. [loc.gov — Working within limits](https://www.loc.gov/apis/json-and-yaml/working-within-limits/)
89. [LoC data-exploration — Accessing images for analysis (rights fields)](https://github.com/LibraryOfCongress/data-exploration/blob/master/loc.gov%20JSON%20API/Accessing%20images%20for%20analysis.ipynb)
90. [NPS API — multimedia/videos (live call, 2026-09-24)](https://developer.nps.gov/api/v1/multimedia/videos)
91. [api.data.gov Developer Manual (rate limits)](https://api.data.gov/docs/developer-manual/)
92. [DVIDS Search API](https://api.dvidshub.net/docs/search_api)
93. [DVIDS Asset API](https://api.dvidshub.net/docs/asset_api)
94. [DVIDS Content Copyright](https://api.dvidshub.net/docs/copyright)
95. [DVIDS API Terms of Use](https://api.dvidshub.net/docs/tos)
96. [Smithsonian Open Access API (live calls, 2026-09-24)](https://api.si.edu/openaccess/api/v1.0/terms/online_media_type)
97. [ESA — Terms and conditions for images and videos](https://www.esa.int/ESA_Multimedia/Terms_and_conditions_of_use_of_images_and_videos_available_on_the_esa_website)
98. [USGS Multimedia Gallery — Videos](https://www.usgs.gov/products/multimedia-gallery/videos)
99. [NOAA Central Library — Photos and videos](https://library.noaa.gov/blogs/news-research-highlights/photos-and-videos)
100. [British Pathé — Licensing](https://www.britishpathe.com/licensing/)
101. [Periscope Film — Pricing and delivery](https://stock.periscopefilm.com/pricing/)
102. [Adobe Stock Search API reference](https://developer.adobe.com/stock/docs/api/11-search-reference)
103. [Shutterstock acquires Pond5](https://investor.shutterstock.com/news-releases/news-release-details/shutterstock-acquires-pond5-worlds-largest-video-marketplace)
104. [Artlist Enterprise API](https://developer.artlist.io/welcome)
105. [Envato — MCP server](https://elements.envato.com/learn/envato-mcp-server)
106. [DataForSEO — YouTube SERP API pricing](https://dataforseo.com/pricing/serp/youtube-serp-api)
107. [Shutterstock SDK — VideoAssets](https://github.com/shutterstock/public-api-javascript-sdk/blob/master/docs/VideoAssets.md)
108. [Openverse API v1 (audio schema, live)](https://api.openverse.org/v1/)
109. [OpenTimelineIO — schema API](https://opentimelineio.readthedocs.io/en/latest/api/python/opentimelineio.schema.html)
110. [schema.org — VideoObject](https://schema.org/VideoObject)
111. [schema.org — Clip](https://schema.org/Clip)
112. [W3C — Media Fragments URI 1.0](https://www.w3.org/TR/media-frags/)
113. [Perception Encoder (arXiv 2504.13181)](https://arxiv.org/pdf/2504.13181)
114. [Gemini API — Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)
115. [Gemini API — Pricing](https://ai.google.dev/gemini-api/docs/pricing)
116. [Mixpeek — Video embedding benchmark 2026 (vendor)](https://mixpeek.com/blog/video-embedding-benchmark-2026)
117. [TwelveLabs — Pricing](https://www.twelvelabs.io/pricing)
118. [VideoPrism](https://github.com/google-deepmind/videoprism)
119. [InternVideo2-CLIP-1B](https://huggingface.co/OpenGVLab/InternVideo2-CLIP-1B-224p-f8)
120. [PySceneDetect — detectors](https://www.scenedetect.com/docs/latest/api/detectors.html)
121. [TransNetV2](https://github.com/soCzech/TransNetV2)
122. [Lighthouse (moment retrieval and highlight detection)](https://github.com/line/lighthouse)
123. [FFmpeg protocols — http](https://ffmpeg.org/ffmpeg-protocols.html)
124. [ThreatExchange — vPDQ / TMK](https://github.com/facebook/ThreatExchange/tree/main/vpdq)
125. [PANNs: Large-Scale Pretrained Audio Neural Networks (arXiv 1912.10211)](https://arxiv.org/pdf/1912.10211)
