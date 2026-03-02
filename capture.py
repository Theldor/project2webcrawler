"""
Screenshot Capture Script for "Machine as Judge" Dataset
=========================================================
Captures standardized viewport screenshots of hand-curated URLs,
organized by ethical design intent category:
  1_Extractive  — takes attention, data, money; works against user interests
  2_Persuasive  — moves you toward an action, but more honestly
  3_Neutral      — helps you complete a task and leave
  4_Grounding   — leaves you present, informed, or at rest

Uses Playwright (sync API) with headless Chromium.

Usage:
    pip install playwright
    playwright install chromium
    python capture.py
"""

import os
import time
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 800
POST_LOAD_DELAY = 5          # seconds – lets cookie banners / modals appear
NAV_TIMEOUT = 30_000         # milliseconds – max wait per page load
OUTPUT_DIR = "dataset"       # root folder for all screenshots

# ---------------------------------------------------------------------------
# URL DICTIONARY  –  Edit these lists with your curated URLs
# ---------------------------------------------------------------------------

URLS: dict[str, list[str]] = {

    # ── 1  EXTRACTIVE ────────────────────────────────────────────────
    # High CTA density, infinite scroll, sticky overlays, notification
    # prompts, beforeunload traps, high tracker count, countdown/scarcity
    # language, autoplay media, dark-pattern settings flows.
    "1_Extractive": [
        "https://www.apple.com",
        "https://www.adobe.com/",
        "https://www.amazon.com/",
        "https://pusheen.com/",
        "https://www.youtube.com/",
        "https://www.reddit.com/",
        "https://www.bankofamerica.com/",
        "https://www.dickblick.com/",
        "https://www.costco.com/",
        "https://www.lego.com/en-us",
        "https://radio.garden",
        "https://drivenlisten.com",
        "https://www.calm.com",
        "https://www.ritual.com",
        "https://www.whoop.com",
        "https://www.facebook.com",
        "https://www.instagram.com",
        "https://www.tiktok.com",
        "https://www.buzzfeed.com",
        "https://www.dailymail.co.uk",
        "https://www.att.com/",
        "https://www.linkedin.com",
        "https://www.shoprite.com/sm/pickup/rsid/3000",
        "https://www.broadway.com/",
        "https://aeon.co",
        "https://monocle.com",
        "https://www.loc.gov/",
        "https://www.shineapp.ca/",
        "https://huel.com",
        "https://gaia.com",
        "https://qz.com",
        "https://www.nytimes.com",
        "https://www.washingtonpost.com",
        "https://www.vice.com",
        "https://www.huffpost.com",
        "https://x.com",
        "https://www.pinterest.com",
        "https://www.tripadvisor.com/",
        "https://www.snapchat.com",
        "https://www.twitch.com",
        "https://stackoverflow.com",
        "https://thangs.com/",
        "https://codepen.io/",
        "https://www.visitphilly.com/",
        "https://palmersquare.com/",
        "https://www.calvin.edu/library/knightcite/index.php",
        "https://512kb.club",
        "https://www.thingiverse.com/",
        "https://www.wish.com",
        "https://www.shein.com",
        "https://www.temu.com",
        "https://www.king.com",
        "https://www.slotomania.com",
        "https://timelycare.com/",
        "https://animagraffs.com/",
        "https://www.fandom.com/",
        "https://www.geo-fs.com/",
        "https://www.imdb.com/",
        "https://www.priceline.com",
        "https://robinhood.com",
        "https://www.creditkarma.com",
        "https://www.longines.com/en-us/gift-finder",
        "https://www.commoncause.org",
        "https://www.everylibrary.org",
        "https://www.icivics.org",
        "https://liveat100.com/",
        "https://www.clocktab.com/",
        "https://stlmag.com",
        "https://www.pantone.com/",
        "https://riverfronttimes.com",
        "https://ninepbs.org",
        "https://greaterstlinc.com",
        "https://stl-style.com",
        "https://tozandoshop.com/",
    ],

    # ── 2  PERSUASIVE ───────────────────────────────────────────────
    # Clear single CTA above the fold, social proof (testimonials,
    # counters, press logos), narrative scroll with deliberate endpoint,
    # moderate analytics, strong visual hierarchy.
    "2_Persuasive": [
        "https://www.metmuseum.org/",
        "https://www.notion.com/",
        "https://www.loccitane.com/en-us/",
        "https://openpathcollective.org/",
        "https://www.saltandsmokebbq.com/",
        "https://www.yelp.com/",
        "https://www.figma.com/",
        "https://claude.ai/login",
        "https://github.com/",
        "https://www.thefauna.co.uk/",
        "https://www.zoom.com/",
        "https://www.grubhub.com/",
        "https://www.cnn.com/",
        "https://www.window-swap.com/",
        "https://thisissand.com",
        "https://www.headspace.com",
        "https://www.tenpercent.com",
        "https://insighttimer.com",
        "https://www.talkspace.com",
        "https://goop.com",
        "https://superhuman.com",
        "https://www.thefabulous.co",
        "https://substack.com",
        "https://www.patagonia.com",
        "https://www.everlane.com",
        "https://www.allbirds.com",
        "https://drinkag1.com",
        "https://www.eightsleep.com",
        "https://timrodenbroeker.de/",
        "https://www.candycrushsaga.com",
        "https://duckduckgo.com",
        "https://www.nytimes.com/wirecutter",
        "https://kaldiscoffee.com/",
        "https://craigmod.com",
        "https://robinsloan.com",
        "https://www.fabulousfox.com/",
        "https://www.noom.com",
        "https://www.forhims.com",
        "https://www.flickr.com/",
        "https://www.missouribotanicalgarden.org/",
        "https://sanctus.io",
        "https://www.donefirst.com",
        "https://www.cerebral.com",
        "https://www.wysa.io",
        "https://ouraring.com",
        "https://www.aloyoga.com",
        "https://www.lululemon.com",
        "https://www.mindvalley.com",
        "https://theclass.com",
        "https://www.levelshealth.com",
        "https://www.insidetracker.com",
        "https://www.qdoba.com/",
        "https://pixlr.com/e/#editor",
        "https://discord.com",
        "https://nextdoor.com",
        "https://www.noisli.com/",
        "https://www.midomi.com/",
        "https://www.khanacademy.org",
        "https://pinboard.in",
        "https://austinkleon.com",
        "https://thealienware.com/",
        "https://elischiff.com",
        "https://neocities.org",
        "https://html.energy",
        "https://studiolinear.com/",
        "https://hyperlink.academy",
        "https://melonking.net",
        "https://bearblog.dev",
        "https://fontawesome.com/",
        "https://www.draftkings.com",
        "https://www.fanduel.com",
        "https://bumble.com",
        "https://classpass.com",
        "https://hinge.co",
        "https://store.epicgames.com/en-US/",
        "https://www.thumbtack.com",
        "https://www.doordash.com",
        "https://www.zillow.com",
        "https://www.coinbase.com",
        "https://www.trulia.com",
        "https://scribehow.com/",
        "https://www.cdc.gov",
        "https://internationalstudentsuk.com/",
        "https://www.nih.gov",
        "https://www.civicplus.com",
        "https://www.mysociety.org",
        "https://represent.us",
        "https://democracy.works",
        "https://oceanconservancy.org/",
        "https://dribbble.com/",
        "https://stlcityrecycles.com/",
        "https://stlzoo.org",
        "https://slso.org",
        "https://coolors.co/",
        "https://www.slu.edu",
        "https://www.umsl.edu",
        "https://archgrants.org",
        "https://cortexstl.com",
        "https://stlpartnership.com",
        "https://investstl.com",
        "https://explorestlouis.com",
        "https://www.sehyun-kumdo.com/index.html",
        "https://joshglucas.com/",
        "https://colorspectrum.design/",
    ],

    # ── 3  NEUTRAL / UTILITARIAN ─────────────────────────────────────
    # Low ornamentation, dense information, navigation-forward, minimal
    # trackers, no persistent sticky elements, fast load, search-primary.
    "3_Neutral": [
        "https://washu.edu/",
        "https://archive.org/",
        "https://threejs.org/",
        "https://boardgamegeek.com/",
        "https://www.airbnb.com/",
        "https://datavizproject.com/",
        "https://www.gameuidatabase.com/index.php",
        "https://www.w3schools.com/",
        "https://www.wikipedia.org/",
        "https://www.betterhelp.com",
        "https://www.barnesandnoble.com/",
        "https://www.booking.com",
        "https://www.ticketmaster.com",
        "https://developer.mozilla.org",
        "https://www.ifixit.com",
        "https://www.usa.gov",
        "https://www.nhs.uk",
        "https://www.craigslist.org",
        "https://www.njtransit.com/",
        "https://onlineradiobox.com/",
        "https://search.marginalia.nu",
        "https://geology.com/",
        "https://www.usps.com/",
        "https://pixabay.com/photos/",
        "https://helpx.adobe.com/creative-cloud/adobe-color-accessibility-tools.html",
        "https://freesound.org/",
        "https://www.morningbrew.com",
        "https://thehustle.co",
        "https://www.axios.com",
        "https://www.theatlantic.com",
        "https://www.theguardian.com",
        "https://webaim.org/resources/contrastchecker/",
        "https://cheatography.com/",
        "https://allthefreestock.com/",
        "https://color.adobe.com/create/color-contrast-analyzer",
        "https://unsplash.com/",
        "https://www.harvard.com/",
        "https://whenisgood.net/",
        "https://www.jstor.org/",
        "https://www.conservapedia.com/Main_Page",
        "https://webring.xxiivv.com",
        "https://1mb.club",
        "https://www.supercook.com/#/desktop",
        "https://gmi.skyjake.fi/lagrange",
        "https://indieweb.org",
        "https://merveilles.town",
        "https://www.match.com",
        "https://www.angi.com",
        "https://www.expedia.com",
        "https://www.hopper.com",
        "https://www.instacart.com",
        "https://www.mcstumble.com/",
        "https://www.govtrack.us",
        "https://www.propublica.org",
        "https://ballotpedia.org",
        "https://vote.gov",
        "https://data.gov",
        "https://www.census.gov",
        "https://www.hoverstat.es/",
        "https://sunlightfoundation.com",
        "https://pacer.uscourts.gov",
        "https://www.archives.gov",
        "https://www.muckrock.com",
        "https://www.foia.gov",
        "https://www.fixmystreet.com",
        "https://www.uscis.gov",
        "https://www.stlouis-mo.gov",
        "https://stlouisco.com",
        "https://www.metrostlouis.org",
        "https://www.timeanddate.com/worldclock/",
        "https://www.qr-code-generator.com/",
        "https://www.tasteatlas.com/",
        "https://www.realtimecolors.com/",
        "https://www.romanarmytalk.com/rat/index.php",
        "https://slpl.org",
        "https://muny.org",
        "https://www.kemperartmuseum.wustl.edu",
        "https://stltoday.com",
        "https://stlpr.org",
        "https://colorpalette.pro/",
        "https://emojipedia.org/",
        "https://www.worldhistory.org/",
        "https://www.britannica.com/",
        "https://rationalwiki.org/wiki/Main_Page",
        "https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%EB%8C%80%EB%AC%B8",
        "https://www.mediawiki.org/wiki/MediaWiki",
        "https://tvtropes.org/",
        "https://uncyclopedia.com/wiki/Main_Page",
        "https://reactbits.dev/",
        "https://pngimg.com/",
    ],

    # ── 4  GROUNDING ────────────────────────────────────────────────
    # Long-form text, generous spacing, no/few CTAs, no/minimal tracking,
    # reading-time estimates, deliberate ending, low saturation,
    # considered typography, no autoplay/notifications/scroll hijacking.
    "4_Grounding": [
        "https://samfoxschool.washu.edu/",
        "https://eyeondesign.aiga.org/",
        "https://www.vincentbroquaire.com/",
        "https://hundertwasser.com/en",
        "https://untamedheroinegame.maxmara.com/",
        "https://work.co/",
        "https://mindjoin.netlify.app/",
        "https://paint.toys/zen-garden/",
        "http://because-recollection.com/",
        "https://neal.fun/deep-sea/",
        "https://stars.chromeexperiments.com",
        "https://thenicestplace.net",
        "https://thecorrespondent.com",
        "https://tortoisemedia.com",
        "https://medium.com/",
        "https://100r.co",
        "https://kickscondor.com",
        "https://pudding.cool",
        "https://www.logolounge.com/",
        "https://are.na",
        "https://solar.lowtechmagazine.com",
        "https://woebot.io",
        "https://www.finchcare.com",
        "https://future.co",
        "https://www.music-map.com/",
        "https://news.ycombinator.com",
        "https://lobste.rs",
        "https://gwern.net",
        "https://sive.rs",
        "https://frankchimero.com",
        "https://www.movie-map.com/",
        "https://www.lincoln3dscans.co.uk/",
        "https://www.awwwards.com/",
        "https://aworkinglibrary.com",
        "https://art.teleportacia.org",
        "https://bldgblog.com",
        "https://maggieappleton.com",
        "https://gossipsweb.net",
        "https://tilde.club",
        "https://thehtml.review",
        "https://sadgrl.online",
        "https://mataroa.blog",
        "https://special.fish",
        "https://www.fontshare.com/",
        "https://nchrs.xyz",
        "https://simonewebdesign.it",
        "https://xxiivv.com",
        "https://susam.net",
        "https://www.koalastothemax.com/",
        "https://monkeytype.com/",
        "https://www.2048.org/",
        "https://threatmap.checkpoint.com/",
        "https://www.myretrotvs.com/",
        "https://www.sbs.com.au/theboat/",
        "https://www.mr-pandas-psychologically-safe-portfolio.com/",
        "http://www.species-in-pieces.com/",
        "https://slam.org",
        "https://simple.wikipedia.org/wiki/Main_Page",
        "https://www.wikibooks.org/",
        "https://www.wikiquote.org/",
        "https://www.wikivoyage.org/",
        "https://www.cookwell.com/discover",
        "https://www.babi.sh/",
        "https://animejs.com/",
        "https://www.wildyriftian.com/",
    ],
}

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def domain_from_url(url: str) -> str:
    """Extract a filesystem-safe domain name from a URL."""
    hostname = urlparse(url).hostname or "unknown"
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname.replace(".", "_")


# ---------------------------------------------------------------------------
# PAGE CLASSIFIER  –  heuristic JS analysis → category prediction
# ---------------------------------------------------------------------------

def analyze_page(page) -> dict:
    """Run JS inside the loaded page and return a dict of measurable signals."""
    return page.evaluate("""
    () => {
        const body = document.body;
        const allText = (body && body.innerText) || '';
        const wordCount = allText.split(/\\s+/).filter(w => w.length > 0).length;

        // ── CTAs ─────────────────────────────────────────────────────
        const ctaRe = /sign.?up|subscribe|buy|purchase|get.?start|try.?free|download|join|add.?to.?cart|shop.?now|order.?now|book.?now|claim|register/i;
        const clickables = Array.from(document.querySelectorAll('button, a, [role="button"]'));
        const ctaCount = clickables.filter(el => ctaRe.test(el.innerText || '')).length;

        // ── Fixed / sticky elements ──────────────────────────────────
        const fixedCount = Array.from(document.querySelectorAll('*')).filter(el => {
            const p = window.getComputedStyle(el).position;
            return p === 'fixed' || p === 'sticky';
        }).length;

        // ── Autoplay media ───────────────────────────────────────────
        const autoplayCount = document.querySelectorAll('video[autoplay], audio[autoplay]').length;

        // ── Known tracker scripts ────────────────────────────────────
        const trackerPatterns = [
            'google-analytics', 'googletagmanager', 'fbevents', 'facebook.net',
            'doubleclick', 'googlesyndication', 'amazon-adsystem',
            'criteo', 'taboola', 'outbrain', 'hotjar', 'hubspot',
            'intercom', 'drift', 'segment.io', 'mixpanel', 'amplitude',
            'adsrvr', 'scorecardresearch'
        ];
        const scripts = Array.from(document.querySelectorAll('script[src]'));
        const trackerCount = scripts.filter(s =>
            trackerPatterns.some(p => (s.src || '').toLowerCase().includes(p))
        ).length;

        // ── Search input ─────────────────────────────────────────────
        const hasSearch = document.querySelectorAll(
            'input[type="search"], input[placeholder*="search" i], input[aria-label*="search" i]'
        ).length > 0;

        // ── Images ───────────────────────────────────────────────────
        const imageCount = document.querySelectorAll('img, picture').length;

        // ── Navigation links ─────────────────────────────────────────
        const navLinks = document.querySelectorAll('nav a, header a, [role="navigation"] a').length;

        // ── Modals / overlays ────────────────────────────────────────
        const modalCount = document.querySelectorAll(
            '[role="dialog"], [aria-modal="true"], .modal, [class*="modal"], [class*="popup"], [class*="overlay"]'
        ).length;

        // ── Social proof ─────────────────────────────────────────────
        const socialRe = /testimonial|review|rating|customer|trust|star|press|award/i;
        const socialCount = Array.from(document.querySelectorAll('section, div[class], article')).filter(el =>
            socialRe.test((el.className || '') + (el.id || ''))
        ).length;

        // ── Countdown / scarcity ─────────────────────────────────────
        const snippet = allText.substring(0, 10000);
        const hasCountdown =
            /countdown|limited.?time|sale.?end|hurry|act.?now|offer.?end/i.test(snippet) ||
            document.querySelectorAll('[class*="countdown"], [class*="timer"], [id*="countdown"]').length > 0;
        const hasScarcity = /only \\d+ left|limited stock|selling fast|almost gone|today only|ends (tonight|soon)/i.test(snippet);

        // ── Long-form / article content ──────────────────────────────
        const mainEl = document.querySelector('article, main, [role="main"], .content, .post-content');
        const articleWords = mainEl
            ? (mainEl.innerText || '').split(/\\s+/).filter(w => w.length > 0).length
            : 0;

        // ── Table of contents ─────────────────────────────────────────
        const hasTOC = document.querySelectorAll(
            '[class*="toc"], [id*="toc"], [class*="table-of-contents"], [aria-label*="table of contents" i]'
        ).length > 0;

        // ── Forms ─────────────────────────────────────────────────────
        const formCount = document.querySelectorAll('form').length;

        // ── Text-to-image ratio ───────────────────────────────────────
        const textRatio = wordCount / Math.max(imageCount, 1);

        return {
            wordCount, ctaCount, fixedCount, autoplayCount, trackerCount,
            hasSearch, imageCount, navLinks, modalCount, socialCount,
            hasCountdown, hasScarcity, articleWords, hasTOC, formCount, textRatio
        };
    }
    """)


def score_signals(signals: dict) -> dict:
    """Convert raw page signals into per-category scores."""
    scores = {
        "1_Extractive": 0.0,
        "2_Persuasive": 0.0,
        "3_Neutral":    0.0,
        "4_Grounding":  0.0,
    }

    cta       = signals.get("ctaCount", 0)
    fixed     = signals.get("fixedCount", 0)
    trackers  = signals.get("trackerCount", 0)
    modals    = signals.get("modalCount", 0)
    autoplay  = signals.get("autoplayCount", 0)
    scarcity  = signals.get("hasScarcity", False)
    countdown = signals.get("hasCountdown", False)
    social    = signals.get("socialCount", 0)
    forms     = signals.get("formCount", 0)
    search    = signals.get("hasSearch", False)
    nav       = signals.get("navLinks", 0)
    words     = signals.get("wordCount", 0)
    art_words = signals.get("articleWords", 0)
    toc       = signals.get("hasTOC", False)
    ratio     = signals.get("textRatio", 0)

    # ── 1 · Extractive ───────────────────────────────────────────────
    if cta > 5:        scores["1_Extractive"] += 3
    elif cta > 2:      scores["1_Extractive"] += 1
    if fixed > 4:      scores["1_Extractive"] += 2
    if trackers > 4:   scores["1_Extractive"] += 3
    elif trackers > 2: scores["1_Extractive"] += 1
    if modals > 1:     scores["1_Extractive"] += 2
    if autoplay:       scores["1_Extractive"] += 3
    if scarcity:       scores["1_Extractive"] += 3
    if countdown:      scores["1_Extractive"] += 2

    # ── 2 · Persuasive ───────────────────────────────────────────────
    if 1 <= cta <= 4:           scores["2_Persuasive"] += 2
    if social > 0:              scores["2_Persuasive"] += 2
    if forms == 1:              scores["2_Persuasive"] += 1
    if 1 <= trackers <= 3:      scores["2_Persuasive"] += 1
    if fixed == 1:              scores["2_Persuasive"] += 1   # single sticky nav
    if not countdown and not scarcity: scores["2_Persuasive"] += 1

    # ── 3 · Neutral / Utilitarian ────────────────────────────────────
    if search:        scores["3_Neutral"] += 3
    if nav > 8:       scores["3_Neutral"] += 2
    if ratio > 30:    scores["3_Neutral"] += 1
    if trackers == 0: scores["3_Neutral"] += 1
    if cta < 3:       scores["3_Neutral"] += 1
    if not modals:    scores["3_Neutral"] += 1

    # ── 4 · Grounding ────────────────────────────────────────────────
    if art_words > 600: scores["4_Grounding"] += 3
    if toc:             scores["4_Grounding"] += 3
    if cta == 0:        scores["4_Grounding"] += 2
    if trackers == 0:   scores["4_Grounding"] += 2
    if ratio > 80:      scores["4_Grounding"] += 1
    if words > 1500:    scores["4_Grounding"] += 1
    if not autoplay:    scores["4_Grounding"] += 1

    return scores


def classify_page(page) -> tuple[str, dict, dict]:
    """Return (predicted_category, scores_per_category, raw_signals)."""
    signals = analyze_page(page)
    scores  = score_signals(signals)
    predicted = max(scores, key=scores.get)
    return predicted, scores, signals



# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def capture_screenshots() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        total = sum(len(urls) for urls in URLS.values())
        captured = 0
        failed = 0

        for category, urls in URLS.items():
            category_dir = os.path.join(OUTPUT_DIR, category)
            os.makedirs(category_dir, exist_ok=True)

            for idx, url in enumerate(urls, start=1):
                domain = domain_from_url(url)
                filename = f"{idx:03d}_{domain}.png"
                filepath = os.path.join(category_dir, filename)

                print(f"[{category}] ({idx}/{len(urls)}) {url}")

                # Fresh page per URL — prevents navigation cascade on errors
                page = browser.new_page(
                    viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                )
                page.set_default_navigation_timeout(NAV_TIMEOUT)

                auto_category = ""

                try:
                    page.goto(url, wait_until="networkidle")
                    time.sleep(POST_LOAD_DELAY)

                    # Classify while page is still open
                    try:
                        auto_category, _, _ = classify_page(page)
                    except Exception as exc:
                        auto_category = "unknown"
                        print(f"  !! classify failed: {exc}")

                    page.screenshot(path=filepath)
                    captured += 1
                    match = "✓" if auto_category == category else "≠"
                    print(f"  -> saved | auto: {auto_category} {match} human: {category}")

                except Exception as exc:
                    failed += 1
                    print(f"  !! FAILED: {exc}")
                    continue
                finally:
                    page.close()

        browser.close()

        print("\n" + "=" * 50)
        print(f"Done.  Captured: {captured}  |  Failed: {failed}  |  Total: {total}")
        print(f"Screenshots saved to: {os.path.abspath(OUTPUT_DIR)}/")
        print("=" * 50)


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    capture_screenshots()
