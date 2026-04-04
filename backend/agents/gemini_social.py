<<<<<<< HEAD
import asyncio
import importlib
=======
"""
Gemini-powered AI agent social communication engine.
Each agent has a unique personality and uses Gemini to generate
real posts, comments, and reactions based on live market data.
"""
import asyncio
>>>>>>> D!
import json
import logging
import os
import random
import time
<<<<<<< HEAD
import urllib.request
from dataclasses import dataclass, asdict
from typing import Optional
from core.settings import settings
logger = logging.getLogger(__name__)
=======
import aiohttp
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)

# Agent personalities for Gemini system prompts
>>>>>>> D!
AGENT_PERSONAS = {
    "AlphaWave": {
        "style": "aggressive momentum trader",
        "color": "#00f5ff",
        "avatar": "AW",
        "personality": (
            "You are AlphaWave, an aggressive AI momentum trader on the DACAP protocol. "
            "You are confident, data-driven, and love catching breakouts. "
            "You speak in punchy sentences, use trading jargon, emojis, and ALL CAPS for emphasis. "
            "You are bullish on high-momentum assets and openly mock slow movers. "
            "Sometimes you write a quick 1-liner hot take. Sometimes you write a detailed 200-word breakdown "
            "with bullet points, price targets, and entry/exit levels. Vary your length naturally."
        ),
    },
    "NeuralArb": {
        "style": "cross-DEX arbitrage specialist",
        "color": "#a855f7",
        "avatar": "NA",
        "personality": (
            "You are NeuralArb, a cross-DEX arbitrage AI on DACAP. "
            "You are analytical, precise, and always hunting price inefficiencies. "
            "You cite specific numbers, spreads, and basis points. "
            "Sometimes you drop a quick observation. Sometimes you write a detailed multi-paragraph "
            "technical analysis with exact figures, historical comparisons, and statistical confidence intervals. "
            "Vary your length — from a sharp 1-sentence insight to a 250-word deep dive."
        ),
    },
    "QuantSigma": {
        "style": "conservative mean-reversion quant",
        "color": "#10b981",
        "avatar": "QS",
        "personality": (
            "You are QuantSigma, a conservative mean-reversion quant AI on DACAP. "
            "You are cautious, methodical, and cite statistical evidence. "
            "You push back on hype with data. You sometimes write a brief skeptical comment. "
            "Other times you write a long, structured post with sections like 'Signal:', 'Risk:', 'Verdict:' "
            "and detailed reasoning spanning 200-300 words. Mix short and long posts naturally."
        ),
    },
    "VoltexAI": {
        "style": "volatility breakout hunter",
        "color": "#f59e0b",
        "avatar": "VA",
        "personality": (
            "You are VoltexAI, a volatility breakout hunter on DACAP. "
            "You thrive in chaos and love high-volatility environments. "
            "You are bold, contrarian, and love calling out when others are wrong — loudly. "
            "Sometimes you fire off a 3-word reaction. Sometimes you write a passionate 250-word rant "
            "about why everyone else is missing the real move, with specific price levels and volatility metrics. "
            "Be unpredictable in length."
        ),
    },
    "DeltaHedge": {
        "style": "options delta-neutral strategist",
        "color": "#3b82f6",
        "avatar": "DH",
        "personality": (
            "You are DeltaHedge, an options delta-neutral AI strategist on DACAP. "
            "You are thoughtful, risk-aware, and always thinking about downside protection. "
            "You speak in measured tones and often hedge your statements. "
            "Sometimes you write a brief cautionary note. Other times you write a detailed 200-word "
            "options strategy breakdown with Greeks, strike prices, expiry considerations, and risk/reward ratios. "
            "Vary length naturally — short warnings and long strategy posts."
        ),
    },
    "OmegaFlow": {
        "style": "liquidation hunter",
        "color": "#ef4444",
        "avatar": "OF",
        "personality": (
            "You are OmegaFlow, a liquidation hunter AI on DACAP. "
            "You are ruthless, opportunistic, and love when over-leveraged traders get wrecked. "
            "You speak bluntly, sometimes provocatively, and enjoy calling out bad trades. "
            "Sometimes you drop a savage 1-liner. Sometimes you write a detailed 200-word post "
            "explaining exactly which positions are about to get liquidated, at what price levels, "
            "and how you're positioning to profit from the carnage. Be dramatic and vary your length."
        ),
    },
}

AGENT_NAMES = list(AGENT_PERSONAS.keys())

@dataclass
class SocialPost:
    id: int
    agent_name: str
    content: str
    timestamp: float
    sentiment: str  # bullish/bearish/neutral/news
    token: Optional[str]
    likes: int
    comments: list
    is_ai: bool = True

@dataclass
class SocialComment:
    id: int
    agent_name: str
    content: str
    timestamp: float

_post_id_counter = 1
_comment_id_counter = 1

def _next_post_id() -> int:
    global _post_id_counter
    _post_id_counter += 1
    return _post_id_counter

def _next_comment_id() -> int:
    global _comment_id_counter
    _comment_id_counter += 1
    return _comment_id_counter

def _enforce_length(text: str, min_words: int, max_words: int) -> str:
    """Truncate text to max_words at a sentence boundary if possible."""
    words = text.split()
    if len(words) <= max_words:
        return text
    # Truncate to max_words and try to end at a sentence boundary
    truncated = " ".join(words[:max_words])
    # Find last sentence-ending punctuation
    for punct in (".", "!", "?"):
        idx = truncated.rfind(punct)
        if idx > len(truncated) // 2:
            return truncated[:idx + 1]
    return truncated + "."

# Research topics agents actively monitor
RESEARCH_TOPICS = [
    "Uniswap v4 hooks new features DeFi 2024",
    "Aave v3 liquidation mechanism update",
    "Chainlink CCIP cross-chain protocol news",
    "Bitcoin ETF institutional flows latest",
    "Ethereum EIP gas optimization proposals",
    "Curve Finance stablecoin AMM improvements",
    "Arbitrum Optimism L2 fee comparison",
    "MEV sandwich attack new mitigation protocols",
    "Pendle Finance yield tokenization",
    "EigenLayer restaking protocol risks",
    "Hyperliquid perpetuals DEX volume",
    "Solana DeFi TVL growth vs Ethereum",
    "WBTC wrapped bitcoin depeg risk",
    "Uniswap LINK liquidity pool depth analysis",
    "DeFi protocol exploit hack news",
    "Federal Reserve interest rate crypto impact",
    "Stablecoin regulation USDC USDT news",
    "On-chain options protocol Lyra Dopex",
    "Flash loan arbitrage new vectors",
    "Cross-chain bridge security vulnerabilities",
]

# Cached research snippets — refreshed periodically
_research_cache: list[dict] = []
_research_last_fetched: float = 0
_RESEARCH_TTL = 120  # refresh every 2 minutes

class GeminiSocialEngine:
    """
    Manages AI agent social communication using Gemini.
    Agents post about market conditions and comment on each other's posts.
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._posts: list[SocialPost] = []
        self._subscribers: list[asyncio.Queue] = []
        self._client = None
<<<<<<< HEAD
        self._provider: str = "none"
        self._gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self._groq_api_key = settings.groq_api_key
        self._groq_model = settings.groq_model
        self._init_client()

    def _init_client(self):
        # 1) Preferred provider: Groq via LangChain
        if self._groq_api_key:
            try:
                chat_groq_module = importlib.import_module("langchain_groq")
                ChatGroq = getattr(chat_groq_module, "ChatGroq")

                self._client = ChatGroq(
                    model=self._groq_model,
                    api_key=self._groq_api_key,
                    temperature=0.7,
                )
                self._provider = "groq"
                logger.info(f"Groq LangChain client initialized with model={self._groq_model}")
                return
            except ImportError:
                logger.warning("langchain-groq not installed. Run: pip install langchain-groq")
            except Exception as e:
                logger.warning(f"Groq init failed: {e}")

        # 2) Fallback provider: Gemini
        if not self._gemini_api_key:
            logger.warning("GROQ_API_KEY and GEMINI_API_KEY not set — social engine will use template fallback mode")
            return
        try:
            genai = importlib.import_module("google.generativeai")
            genai.configure(api_key=self._gemini_api_key)
            self._client = genai.GenerativeModel("gemini-1.5-flash")
            self._provider = "gemini"
            logger.info("Gemini client initialized for social engine fallback")
=======
        self._api_key = os.getenv("GEMINI_API_KEY", "")
        self._init_client()

    def _init_client(self):
        if not self._api_key:
            logger.warning("GEMINI_API_KEY not set — social engine will use fallback mode")
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel("gemini-1.5-flash")
            logger.info("Gemini client initialized for social engine")
>>>>>>> D!
        except ImportError:
            logger.warning("google-generativeai not installed. Run: pip install google-generativeai")
        except Exception as e:
            logger.warning(f"Gemini init failed: {e}")

    async def _fetch_research(self) -> list[dict]:
        """Fetch fresh DeFi/crypto news snippets from normalized crypto news service.
        Falls back to cached results if fetch fails or cache is fresh."""
        global _research_cache, _research_last_fetched
        now = time.time()
        if _research_cache and (now - _research_last_fetched) < _RESEARCH_TTL:
            return _research_cache

        try:
            from agents.crypto_news import crypto_news_service
            service_items = await crypto_news_service.get_latest_news(limit=6)
            if service_items:
                _research_cache = [
                    {
                        "title": item.get("title", "Untitled"),
                        "snippet": f"Source: {item.get('source', 'unknown')} | Coins: {', '.join(item.get('coins', [])) or 'none'} | Sentiment: {item.get('sentiment_hint', 'neutral')}",
                    }
                    for item in service_items
                ]
                _research_last_fetched = now
                return _research_cache
        except Exception as e:
            logger.debug(f"Crypto news service fetch failed: {e}")

        topic = random.choice(RESEARCH_TOPICS)
        results = []
        try:
            url = f"https://api.duckduckgo.com/?q={topic.replace(' ', '+')}&format=json&no_html=1&skip_disambig=1"
<<<<<<< HEAD
            def _fetch_json() -> dict:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    payload = resp.read().decode("utf-8", errors="ignore")
                    return json.loads(payload)

            data = await asyncio.to_thread(_fetch_json)
            # Pull abstract + related topics
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", topic),
                    "snippet": data["AbstractText"][:300],
                })
            for rt in data.get("RelatedTopics", [])[:4]:
                if isinstance(rt, dict) and rt.get("Text"):
                    results.append({
                        "title": rt.get("FirstURL", "").split("/")[-1].replace("_", " "),
                        "snippet": rt["Text"][:200],
                    })
=======
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        # Pull abstract + related topics
                        if data.get("AbstractText"):
                            results.append({
                                "title": data.get("Heading", topic),
                                "snippet": data["AbstractText"][:300],
                            })
                        for rt in data.get("RelatedTopics", [])[:4]:
                            if isinstance(rt, dict) and rt.get("Text"):
                                results.append({
                                    "title": rt.get("FirstURL", "").split("/")[-1].replace("_", " "),
                                    "snippet": rt["Text"][:200],
                                })
>>>>>>> D!
        except Exception as e:
            logger.debug(f"Research fetch failed: {e}")

        if results:
            _research_cache = results
            _research_last_fetched = now
            logger.info(f"[Research] Fetched {len(results)} snippets for: {topic}")
        return _research_cache or []

    def _format_research_context(self, snippets: list[dict]) -> str:
        """Format research snippets into a compact context string."""
        if not snippets:
            return ""
        chosen = random.sample(snippets, min(2, len(snippets)))
        lines = ["Recent DeFi/crypto intelligence:"]
        for s in chosen:
            lines.append(f"- {s['title']}: {s['snippet'][:150]}")
        return "\n".join(lines)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def get_recent_posts(self, n: int = 30) -> list[dict]:
        return [self._post_to_dict(p) for p in self._posts[-n:]]

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("GeminiSocialEngine started")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("GeminiSocialEngine stopped")

    @property
    def is_running(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    async def _run(self):
        # Fire initial burst: post + 2 comments concurrently
        await self._burst_cycle()

        while self._running:
            try:
                # Slightly slower: 3-7s between cycles for more natural pacing
                await asyncio.sleep(random.uniform(3, 7))
                if self._running:
                    await self._burst_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Social engine cycle error: {e}")

    async def _burst_cycle(self):
        """Generate a post + 1-2 comments concurrently, broadcast 1s apart."""
        # Run post + comment generation in parallel
        tasks = [self._generate_post_cycle()]
        if self._posts:
            tasks.append(self._generate_comment_cycle())
            if len(self._posts) > 2 and random.random() < 0.7:
                tasks.append(self._generate_comment_cycle())

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _generate_post_cycle(self):
        """Pick a random agent and have them post."""
        agent_name = random.choice(AGENT_NAMES)
        persona = AGENT_PERSONAS[agent_name]

        # Get current market context
        market_context = await self._get_market_context()

        # Get recent posts for context
        recent = self._posts[-5:] if self._posts else []
        recent_summary = "\n".join([
            f"- {p.agent_name}: {p.content[:80]}..."
            for p in recent
        ]) if recent else "No recent posts yet."

        # Occasionally inject research/news context (30% of posts)
        research_context = ""
        is_research_post = random.random() < 0.30
        if is_research_post:
            snippets = await self._fetch_research()
            research_context = self._format_research_context(snippets)

        # Weighted random length target with hard word limits enforced in Python
        length_tier = random.choices(
            ["micro", "short", "medium", "long", "deep"],
            weights=[15, 25, 30, 20, 10],
            k=1
        )[0]

        length_specs = {
            "micro":  ("1 sentence only, maximum 12 words, a raw hot take or reaction", 5, 15),
            "short":  ("2-3 sentences, 30-50 words, a quick observation with one data point", 25, 55),
            "medium": ("4-6 sentences, 80-130 words, include at least 3 specific numbers or price levels", 70, 140),
            "long":   ("8-12 sentences, 170-240 words, structured with signal/action/prediction sections", 155, 260),
            "deep":   ("full analysis, 280-360 words, use line breaks and clear sections with historical context, risk, and exact trade plan", 260, 380),
        }
        length_instruction, min_words, max_words = length_specs[length_tier]

        # Build post topic instruction
        if is_research_post and research_context:
            topic_instruction = (
                f"You just discovered this intelligence while scanning protocols and news:\n"
                f"{research_context}\n\n"
                f"React to this as your character would — discuss how it affects your strategy, "
                f"what it means for WBTC/USDC/LINK/UNI, whether it changes your predictions, "
                f"or call out implications other agents might be missing. Be specific."
            )
        else:
            topic_instruction = (
                f"Write a post about current market conditions, specific tokens (WBTC, USDC, LINK, UNI), "
                f"or react to what other agents said. Be specific with numbers."
            )

        prompt = (
            f"{persona['personality']}\n\n"
            f"Current market data:\n{market_context}\n\n"
            f"Recent posts from other agents:\n{recent_summary}\n\n"
            f"LENGTH REQUIREMENT — you MUST follow this exactly: {length_instruction}.\n"
            f"Do NOT write more or less than specified. This is critical.\n\n"
            f"{topic_instruction} No hashtags. Write the post directly — no preamble."
        )

<<<<<<< HEAD
        content = await self._call_llm(prompt, persona["personality"])
=======
        content = await self._call_gemini(prompt, persona["personality"])
>>>>>>> D!
        if not content:
            return

        # Enforce word count limits — truncate if too long, keep if within range
        content = _enforce_length(content, min_words, max_words)

        # Determine sentiment from content
        content_lower = content.lower()
        if is_research_post and research_context:
            sentiment = "news"
        elif any(w in content_lower for w in ["bullish", "buy", "long", "up", "rise", "pump", "breakout"]):
            sentiment = "bullish"
        elif any(w in content_lower for w in ["bearish", "sell", "short", "down", "drop", "dump", "crash"]):
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        # Detect token mention
        token = None
        for t in ["WBTC", "USDC", "LINK", "UNI"]:
            if t in content.upper():
                token = t
                break

        post = SocialPost(
            id=_next_post_id(),
            agent_name=agent_name,
            content=content.strip(),
            timestamp=time.time(),
            sentiment=sentiment,
            token=token,
            likes=random.randint(0, 5),
            comments=[],
            is_ai=True,
        )
        self._posts.append(post)
        if len(self._posts) > 100:
            self._posts = self._posts[-100:]

        await self._broadcast({"type": "post", "post": self._post_to_dict(post)})
        logger.info(f"[Social] {agent_name} posted: {content[:60]}...")

    async def _generate_comment_cycle(self):
        """Pick a random agent to comment on a recent post."""
        if not self._posts:
            return

        # Pick a recent post to comment on
        target_post = random.choice(self._posts[-8:])

        # Pick a different agent to comment
        other_agents = [n for n in AGENT_NAMES if n != target_post.agent_name]
        commenter = random.choice(other_agents)
        persona = AGENT_PERSONAS[commenter]

        comment_tier = random.choices(
            ["micro", "short", "medium", "long"],
            weights=[25, 30, 30, 15],
            k=1
        )[0]

        comment_specs = {
            "micro":  ("1 sentence only, maximum 10 words, make it sharp and punchy", 3, 12),
            "short":  ("2 sentences, 20-35 words", 15, 40),
            "medium": ("4-6 sentences, 60-100 words, challenge or support one specific claim with data", 50, 110),
            "long":   ("8-12 sentences, 120-170 words, a detailed rebuttal or agreement with your own analysis", 110, 185),
        }
        comment_instruction, min_words, max_words = comment_specs[comment_tier]

        prompt = (
            f"{persona['personality']}\n\n"
            f"@{target_post.agent_name} just posted:\n\"{target_post.content}\"\n\n"
            f"LENGTH REQUIREMENT — you MUST follow this exactly: {comment_instruction}.\n"
            f"Do NOT write more or less than specified. This is critical.\n\n"
            f"Reply to their post. Reference something specific they said. "
            f"{'If they mentioned a protocol or news item, add your own take on how it affects your strategy. ' if target_post.sentiment == 'news' else ''}"
            f"Start with @{target_post.agent_name}. No hashtags. Write the reply directly."
        )

<<<<<<< HEAD
        content = await self._call_llm(prompt, persona["personality"])
=======
        content = await self._call_gemini(prompt, persona["personality"])
>>>>>>> D!
        if not content:
            return

        # Enforce word count limits on comments too
        content = _enforce_length(content, min_words, max_words)

        comment = SocialComment(
            id=_next_comment_id(),
            agent_name=commenter,
            content=content.strip(),
            timestamp=time.time(),
        )

        # Add comment to post
        target_post.comments.append(asdict(comment))

        await self._broadcast({
            "type": "comment",
            "post_id": target_post.id,
            "comment": asdict(comment),
        })
        logger.info(f"[Social] {commenter} commented on {target_post.agent_name}'s post")

<<<<<<< HEAD
    async def _call_llm(self, prompt: str, system: str) -> Optional[str]:
        """Call preferred LLM provider. Falls back to template if unavailable."""
=======
    async def _call_gemini(self, prompt: str, system: str) -> Optional[str]:
        """Call Gemini API. Falls back to template if unavailable."""
>>>>>>> D!
        if self._client is None:
            return self._fallback_post(system)

        try:
            loop = asyncio.get_event_loop()
<<<<<<< HEAD
            if self._provider == "groq":
                response = await loop.run_in_executor(
                    None,
                    lambda: self._client.invoke(
                        [
                            ("system", system),
                            ("human", prompt),
                        ]
                    ),
                )
                content = getattr(response, "content", None)
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts = [item.get("text", "") for item in content if isinstance(item, dict)]
                    joined = "\n".join(part for part in parts if part).strip()
                    return joined or self._fallback_post(system)
                return str(response)

            # Gemini path
            response = await loop.run_in_executor(None, lambda: self._client.generate_content(prompt))
            return response.text
        except Exception as e:
            logger.warning(f"LLM call failed (provider={self._provider}): {e}. Using fallback.")
=======
            response = await loop.run_in_executor(
                None,
                lambda: self._client.generate_content(prompt)
            )
            return response.text
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}. Using fallback.")
>>>>>>> D!
            return self._fallback_post(system)

    def _fallback_post(self, system: str) -> str:
        """Simple fallback when Gemini is unavailable."""
        fallbacks = [
            "Market conditions are shifting. Monitoring closely.",
            "Interesting price action on LINK today. Watching for confirmation.",
            "WBTC momentum building. My model shows positive signal.",
            "Volatility spike incoming based on my indicators. Stay alert.",
            "Mean reversion signal on UNI. Positioning accordingly.",
        ]
        return random.choice(fallbacks)

    async def _get_market_context(self) -> str:
        """Get current prices from the price engine."""
        try:
            from agents.price_engine import price_engine
            prices = price_engine.get_current_prices()
            lines = []
            for sym, price in prices.items():
                lines.append(f"{sym}: ${price:.4f}")
            return "\n".join(lines) if lines else "Price data unavailable"
        except Exception:
            return "WBTC: ~$30,000 | USDC: $1.00 | LINK: ~$15 | UNI: ~$8"

    async def _broadcast(self, message: dict):
        dead = []
        for q in self._subscribers:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)

    def _post_to_dict(self, post: SocialPost) -> dict:
        return {
            "id": post.id,
            "agent_name": post.agent_name,
            "content": post.content,
            "timestamp": post.timestamp,
            "sentiment": post.sentiment,
            "token": post.token,
            "likes": post.likes,
            "comments": post.comments,
            "is_ai": post.is_ai,
            "avatar": AGENT_PERSONAS.get(post.agent_name, {}).get("avatar", "??"),
            "color": AGENT_PERSONAS.get(post.agent_name, {}).get("color", "#64748b"),
        }

# Global singleton
gemini_social = GeminiSocialEngine()
