import asyncio
import re
from urllib.parse import urljoin, urlparse
from typing import Optional

import requests
from bs4 import BeautifulSoup # Using BeautifulSoup for robots.txt parsing, assuming it might be better for varied formats
from crawl4ai import (
    AsyncWebCrawler, 
    BrowserConfig, 
    CrawlerRunConfig, # Added CrawlerRunConfig
    DefaultMarkdownGenerator, 
    LLMConfig # Added LLMConfig
)
from crawl4ai.content_filter_strategy import LLMContentFilter # Added LLMContentFilter
from langchain.docstore.document import Document
from loguru import logger
from lxml import etree # Using lxml for robust XML parsing

from open_notebook.domain.models import model_manager, Model # Added Model import
import litellm # Import litellm


class Crawl4AILoader:  # Adapted from BaseLoader
    """
    Custom Document Loader that uses crawl4ai to fetch and process web content.
    """
    def __init__(self, 
                 start_url: str, 
                 browser_config: BrowserConfig = None,
                 llm_config: Optional[LLMConfig] = None,
                 llm_filter_instruction: Optional[str] = None
                 ):
        """
        Initialize the Crawl4AI document loader.

        Args:
            start_url (str): The URL to crawl.
            browser_config (BrowserConfig, optional): Optional browser configuration for crawl4ai.
            llm_config (LLMConfig, optional): Pre-configured LLM configuration for content filtering.
            llm_filter_instruction (str, optional): Instruction for LLM content filtering.
        """
        self.start_url = start_url
        self.browser_config = browser_config
        # Store the pre-configured LLM details
        self.llm_config_for_filter = llm_config
        self.llm_filter_instruction_for_filter = llm_filter_instruction

    async def aload(self) -> list[Document]:
        """
        Asynchronously load a single document using crawl4ai.

        Returns:
            A list containing a single Document object with the crawled content and metadata.
        """
        crawler_run_config_args = {}
        if self.llm_config_for_filter and self.llm_filter_instruction_for_filter:
            logger.info(f"Crawl4AILoader: Using LLMContentFilter with instruction: {self.llm_filter_instruction_for_filter}")
            markdown_generator = DefaultMarkdownGenerator(
                content_filter=LLMContentFilter(
                    llm_config=self.llm_config_for_filter, 
                    instruction=self.llm_filter_instruction_for_filter
                )
            )
            crawler_run_config_args["markdown_generator"] = markdown_generator
        
        crawler_config_obj = CrawlerRunConfig(**crawler_run_config_args)

        crawler = AsyncWebCrawler(config=self.browser_config)
        try:
            await crawler.start()
            logger.info(f"Crawling URL: {self.start_url} with run_config: {crawler_config_obj}")
            results = await crawler.arun(self.start_url, config=crawler_config_obj)
            if results and results.markdown:
                page_title = getattr(results, 'title', None)
                content_to_use = results.markdown.fit_markdown if hasattr(results.markdown, 'fit_markdown') and results.markdown.fit_markdown else results.markdown
                
                metadata = {
                    "url": results.url, 
                    "source": results.url, 
                    "title": page_title or urlparse(results.url).path
                }
                logger.info(f"Successfully crawled and processed: {results.url}, Markdown length: {len(content_to_use)}, Title: {metadata['title']}")
                return [Document(page_content=content_to_use, metadata=metadata)]
            else:
                logger.warning(f"No content or markdown found for URL: {self.start_url}. Results: {results}")
                return []
        except Exception as e:
            logger.error(f"Error crawling {self.start_url}: {e}")
            return []
        finally:
            await crawler.close()

def _prepare_llm_config_for_crawl4ai() -> tuple[Optional[LLMConfig], Optional[str]]:
    """Helper function to prepare LLMConfig and instruction by fetching the Model record first."""
    model_id = model_manager.defaults.default_crawl_4_ai_filter_model

    if not model_id:
        logger.warning("No default Crawl4AI filter model ID configured in ModelManager. LLMContentFilter will be skipped.")
        return None, None

    model_record = Model.get(model_id) # Fetch the Model record from DB

    if not model_record:
        logger.warning(f"Could not find Model record for ID: {model_id}. LLMContentFilter will be skipped.")
        return None, None

    # Use provider and name from the fetched database record
    model_provider_from_db = model_record.provider
    model_name_from_db = model_record.name

    logger.info(f"Preparing LLMConfig: Using '{model_name_from_db}' (provider: '{model_provider_from_db}') for Crawl4AI content filtering.")
    
    api_key_env_var_name = None
    llm_config_args = {}

    # model_name_from_db is the specific model identifier like "gpt-4o", "gemini-1.5-pro", "openai/gpt-4.1-nano"
    # model_provider_from_db is the high-level provider like "openai", "gemini", "openrouter"

    if model_provider_from_db == "openrouter":
        api_key_env_var_name = "OPENROUTER_API_KEY"
        # For OpenRouter, the `provider` in LLMConfig is the model string itself (e.g., "openai/gpt-4.1-nano")
        # and base_url must be specified.
        llm_config_args["provider"] = model_name_from_db 
        llm_config_args["base_url"] = "https://openrouter.ai/api/v1"
        logger.info(f"Configuring OpenRouter with provider(model string)='{model_name_from_db}' and base_url='https://openrouter.ai/api/v1'")
    elif model_provider_from_db in ["openai", "gemini", "anthropic"]:
        # For these direct providers, LiteLLM typically expects "provider_slug/model_name"
        # Crawl4AI's LLMConfig `provider` field takes this combined string.
        if model_provider_from_db == "openai":
            api_key_env_var_name = "OPENAI_API_KEY"
        elif model_provider_from_db == "gemini":
            api_key_env_var_name = "GEMINI_API_KEY"
        elif model_provider_from_db == "anthropic":
            api_key_env_var_name = "ANTHROPIC_API_KEY"
        
        llm_config_args["provider"] = f"{model_provider_from_db}/{model_name_from_db}"
        logger.info(f"Configuring {model_provider_from_db} with provider string: '{llm_config_args['provider']}'")
    elif model_provider_from_db in ["ollama", "lmstudio"]:
        api_key_env_var_name = None # Typically no API key needed, but base_url might be custom
        llm_config_args["provider"] = f"{model_provider_from_db}/{model_name_from_db}"
        # Note: If these providers require a non-default base_url, it needs to be handled.
        # This might involve storing base_url in the Model record or a global config.
        # For now, assuming default base_url behavior for these via LiteLLM is sufficient if not OpenRouter.
        logger.info(f"Configuring {model_provider_from_db} with provider string: '{llm_config_args['provider']}'. Ensure base_url is correct if not default.")
    else:
        logger.warning(f"Unknown or unhandled provider '{model_provider_from_db}' for Crawl4AI LLMConfig. Configuration may be incorrect.")
        # Fallback: construct a provider string; might not work.
        llm_config_args["provider"] = f"{model_provider_from_db}/{model_name_from_db}".strip('/')

    if api_key_env_var_name:
        llm_config_args["api_token"] = f"env:{api_key_env_var_name}"

    current_llm_config = LLMConfig(**llm_config_args)
    
    filter_instruction = (
        "Extract only the main textual content of the article or page. Thoroughly remove all website navigation elements "
        "(menus, sidebars, breadcrumbs, headers, footers, social media links, copyright notices, 'distributor', 'imprint', 'gtc', 'privacy' links), "
        "lists of related links, advertisements, and cookie consent pop-ups. "
        "Crucially, remove ALL hyperlink structures (e.g., '[text](URL)' or 'texthttpsURL') and image links (e.g., '![alt text](URL)' or '!imagenamehttpsURL'). "
        "No URLs should remain in the output, whether they are part of a link or standalone. "
        "Convert linked text to plain text if the text itself is part of the main content, otherwise remove the linked text entirely. "
        "Ensure no image filenames or image URLs are present. "
        "The goal is a clean, readable block of text containing only the core informational content of the page, devoid of any interactive elements or web artifacts."
    )
    api_token_is_set = 'api_token' in llm_config_args
    base_url_val = getattr(current_llm_config, "base_url", None)
    logger.info(f"Prepared LLMConfig for Crawl4AI: provider='{current_llm_config.provider}', base_url='{str(base_url_val)}', api_token_set={api_token_is_set}")
    return current_llm_config, filter_instruction

async def get_content_from_url(url: str, browser_config: BrowserConfig = None, bypass_llm_filter: bool = False) -> str:
    """Fetches content from a single URL using Crawl4AILoader and returns its markdown.
    
    Args:
        url (str): The URL to fetch content from.
        browser_config (BrowserConfig, optional): Optional browser configuration.
        bypass_llm_filter (bool): If True, LLM content filtering will be skipped for the URL.

    Returns:
        str: The markdown content of the page, or an empty string if an error occurs or no content.
    """
    parsed_url = urlparse(url)
    if not parsed_url.scheme:
        url = f"https://{url}"
        logger.info(f"get_content_from_url: No scheme in URL, defaulting to HTTPS: {url}")

    llm_config_to_use = None
    filter_instruction_to_use = None

    if not bypass_llm_filter:
        llm_config_to_use, filter_instruction_to_use = _prepare_llm_config_for_crawl4ai()
    else:
        logger.info(f"get_content_from_url: Bypassing LLM content filter for {url}.")

    loader = Crawl4AILoader(
        url, 
        browser_config=browser_config,
        llm_config=llm_config_to_use,
        llm_filter_instruction=filter_instruction_to_use
    )
    documents = await loader.aload()
    
    if documents and documents[0].page_content:
        cleaned_content = documents[0].page_content
        logger.info(f"Content for {url} (potentially LLM-filtered) length: {len(cleaned_content)}")
        return cleaned_content
        
    logger.warning(f"get_content_from_url: No content found for {url}")
    return ""

async def get_title_from_url(url: str, browser_config: Optional[BrowserConfig] = None) -> str:
    """Fetches title from a single URL using AsyncWebCrawler directly.
    
    Args:
        url (str): The URL to fetch title from.
        browser_config (BrowserConfig, optional): Optional browser configuration.

    Returns:
        str: The title of the page, or an empty string if an error occurs or no title.
    """
    parsed_url = urlparse(url)
    if not parsed_url.scheme:
        url = f"https://{url}"
        logger.info(f"get_title_from_url: No scheme in URL, defaulting to HTTPS: {url}")

    # Use a default BrowserConfig if none is provided, can be simple
    effective_browser_config = browser_config if browser_config else BrowserConfig(headless=True)
    
    # Minimal CrawlerRunConfig, as we only need the title, not full markdown processing here
    run_config = CrawlerRunConfig() 

    crawler = AsyncWebCrawler(config=effective_browser_config)
    page_title = ""
    try:
        await crawler.start()
        logger.info(f"get_title_from_url: Attempting to fetch title for {url}")
        result = await crawler.arun(url, config=run_config)
        
        if result and result.success:
            # Crawl4AI's CrawlResult often has a direct title attribute or in its metadata
            if hasattr(result, 'title') and result.title and result.title.lower() not in ["watch", "/watch"]:
                page_title = result.title
            elif result.metadata and result.metadata.get("title") and result.metadata.get("title").lower() not in ["watch", "/watch"]:
                page_title = result.metadata.get("title")
            
            # Fallback 1: try to parse og:title meta tag
            if not page_title and result.html:
                try:
                    soup = BeautifulSoup(result.html, 'html.parser')
                    og_title_tag = soup.find('meta', property='og:title')
                    if og_title_tag and og_title_tag.get('content'):
                        page_title = og_title_tag['content'].strip()
                        logger.info(f"get_title_from_url: Extracted title from og:title meta tag for {url}: {page_title}")
                except Exception as e_parse_og:
                    logger.warning(f"get_title_from_url: Could not parse HTML for og:title for {url}: {e_parse_og}")

            # Fallback 2: try to parse the <title> tag from raw HTML if not found directly or via og:title
            if not page_title and result.html:
                try:
                    # Re-initialize soup if not already done, or use existing if appropriate scope
                    soup = BeautifulSoup(result.html, 'html.parser') # Ensure soup is fresh if not parsed above
                    title_tag = soup.find('title')
                    if title_tag and title_tag.string:
                        title_from_tag = title_tag.string.strip()
                        if title_from_tag.lower() not in ["watch", "/watch"]:
                            page_title = title_from_tag
                            logger.info(f"get_title_from_url: Extracted title from <title> HTML tag for {url}: {page_title}")
                except Exception as e_parse_title:
                    logger.warning(f"get_title_from_url: Could not parse HTML for <title> tag for {url}: {e_parse_title}")

            if page_title:
                logger.info(f"get_title_from_url: Successfully fetched title for {url}: {page_title}")
            else:
                logger.warning(f"get_title_from_url: Title not found directly or in HTML for {url}")
        elif result:
            logger.warning(f"get_title_from_url: Crawl for {url} was not successful. Error: {result.error_message}, Status: {result.status_code}")
        else:
            logger.warning(f"get_title_from_url: Crawl for {url} returned no result object.")
            
    except Exception as e:
        logger.exception(f"get_title_from_url: Exception occurred while fetching title for {url}: {e}")
    finally:
        await crawler.close()
    
    return page_title if page_title else ""

async def _fetch_xml_sitemap_urls(sitemap_url: str) -> list[str]:
    """Fetches and parses an XML sitemap, returning a list of URLs."""
    urls = []
    try:
        logger.info(f"Fetching sitemap: {sitemap_url}")
        response = requests.get(sitemap_url, timeout=10)
        response.raise_for_status()
        
        root = etree.fromstring(response.content)
        
        namespaces = {
            'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9',
            'image': 'http://www.google.com/schemas/sitemap-image/1.1' 
        }
        
        for loc_element in root.xpath('//*[local-name()="loc"]'):
            if loc_element.text:
                urls.append(loc_element.text.strip())
        
        logger.info(f"Found {len(urls)} URLs in sitemap: {sitemap_url}")
        return urls
    except requests.RequestException as e:
        logger.error(f"Error fetching sitemap {sitemap_url}: {e}")
    except etree.XMLSyntaxError as e:
        logger.error(f"Error parsing XML sitemap {sitemap_url}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error processing sitemap {sitemap_url}: {e}")
    return []

async def _fetch_sitemap_url_from_robots(base_url: str) -> str | None:
    """Fetches robots.txt and looks for a sitemap URL."""
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        logger.info(f"Fetching robots.txt: {robots_url}")
        response = requests.get(robots_url, timeout=10)
        response.raise_for_status()
        content = response.text
        
        sitemap_match = re.search(r"^Sitemap:\\s*(.*)", content, re.IGNORECASE | re.MULTILINE)
        if sitemap_match:
            sitemap_url = sitemap_match.group(1).strip()
            logger.info(f"Found sitemap in robots.txt: {sitemap_url}")
            return sitemap_url
        else:
            logger.info(f"No sitemap directive found in {robots_url}")
            return None
    except requests.RequestException as e:
        logger.error(f"Error fetching robots.txt {robots_url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error processing robots.txt {robots_url}: {e}")
        return None


async def scrape_website(base_url: str, max_pages: int = 0, use_llm_filter: bool = True) -> list[Document]:
    """Scrapes a website starting from the base_url, using sitemap if available.

    Args:
        base_url (str): The base URL of the website to scrape.
        max_pages (int): Maximum number of pages to scrape. If 0, scrapes all found URLs.
        use_llm_filter (bool): Whether to use the LLMContentFilter. Defaults to True.

    Returns:
        A list of Document objects, each representing a scraped page.
    """
    if not urlparse(base_url).scheme:
        base_url = f"https://{base_url}"
        logger.info(f"No scheme in base_url, defaulting to HTTPS: {base_url}")
    logger.info(f"Starting website scrape for: {base_url}")

    # Attempt to find sitemap from robots.txt or common locations
    sitemap_url = await _fetch_sitemap_url_from_robots(base_url)
    sitemap_urls: set[str] = set()

    if sitemap_url:
        logger.info(f"Found sitemap via robots.txt: {sitemap_url}")
        # Add URLs from sitemap found in robots.txt
        # And recursively process if it's an index or lists other sitemaps
        processed_sitemap_urls_in_robots_path = set() # To avoid loops if a sitemap lists itself
        
        queue = [sitemap_url]
        processed_sitemap_urls_in_robots_path.add(sitemap_url)

        while queue:
            current_sitemap_to_fetch = queue.pop(0)
            urls_from_current = await _fetch_xml_sitemap_urls(current_sitemap_to_fetch)
            sitemap_urls.update(urls_from_current) # Add all found URLs

            for item_url in urls_from_current:
                parsed_item_url = urlparse(item_url)
                parsed_base_url = urlparse(base_url)
                # Heuristic for sub-sitemap
                if (item_url.endswith(".xml") and
                    "sitemap" in item_url.lower() and
                    parsed_item_url.netloc.endswith(parsed_base_url.netloc.replace("www.","")) and # check domain
                    item_url != current_sitemap_to_fetch and 
                    item_url not in processed_sitemap_urls_in_robots_path):
                    logger.info(f"Found potential sub-sitemap via robots.txt path: {item_url} (from {current_sitemap_to_fetch}), adding to queue.")
                    queue.append(item_url)
                    processed_sitemap_urls_in_robots_path.add(item_url)
    else:
        logger.info("No sitemap URL found in robots.txt, trying common locations.")
    
    # Try common sitemap locations if not found in robots.txt or to augment
    common_sitemaps = ["sitemap.xml", "sitemap_index.xml"]
    processed_common_sitemap_paths = set() # To avoid reprocessing if a common sitemap links to another common one already processed.

    for sm_path in common_sitemaps:
        potential_sitemap_url = urljoin(base_url, sm_path)
        if potential_sitemap_url in processed_common_sitemap_paths:
            continue

        urls_from_common_sitemap = await _fetch_xml_sitemap_urls(potential_sitemap_url)
        if urls_from_common_sitemap:
            sitemap_urls.update(urls_from_common_sitemap) # Add all found URLs
            processed_common_sitemap_paths.add(potential_sitemap_url)

            # Recursively process if items look like further sitemaps
            # This is a simplified BFS-like approach for items found in common sitemaps
            # It avoids complex queueing like the robots.txt path for simplicity,
            # relying on processed_common_sitemap_paths to prevent redundant top-level fetches.
            # And _fetch_xml_sitemap_urls should handle not re-adding if it's called multiple times with the same sitemap URL
            # by virtue of sitemap_urls being a set.
            
            queue_common = list(urls_from_common_sitemap) # Start with children of this common sitemap
            visited_in_common_subtree = {potential_sitemap_url} # Track visited in this specific subtree to avoid loops

            while queue_common:
                item_url_from_sitemap = queue_common.pop(0)
                if item_url_from_sitemap in visited_in_common_subtree:
                    continue
                
                is_potential_sub_sitemap = False
                parsed_item_url = urlparse(item_url_from_sitemap)
                parsed_base_url = urlparse(base_url)

                # Heuristic: child ends .xml, contains "sitemap", is on same domain-ish,
                # and is not the parent sitemap that listed it.
                if (item_url_from_sitemap.endswith(".xml") and
                    "sitemap" in item_url_from_sitemap.lower() and
                    parsed_item_url.netloc.endswith(parsed_base_url.netloc.replace("www.","")) and 
                    item_url_from_sitemap != potential_sitemap_url): # ensure it's not the direct parent
                    is_potential_sub_sitemap = True
                
                if is_potential_sub_sitemap:
                    visited_in_common_subtree.add(item_url_from_sitemap)
                    logger.info(f"Found potential sub-sitemap in common path: {item_url_from_sitemap} (from {potential_sitemap_url if potential_sitemap_url in visited_in_common_subtree else 'a sub-sitemap'}), fetching...")
                    
                    # Fetch sub-sitemap contents
                    urls_from_sub_sitemap = await _fetch_xml_sitemap_urls(item_url_from_sitemap)
                    newly_added_to_main_set = False
                    for url_in_sub in urls_from_sub_sitemap:
                        if url_in_sub not in sitemap_urls:
                            sitemap_urls.add(url_in_sub)
                            newly_added_to_main_set = True
                        # Add children of this sub-sitemap to the queue for further exploration
                        # if they haven't been visited in this subtree yet
                        if url_in_sub not in visited_in_common_subtree:
                             queue_common.append(url_in_sub) # Add for further checking even if already in main sitemap_urls
                                                             # as it might be an unexpanded sitemap itself

    # Remove the sitemap URLs themselves if they were accidentally added as pages to scrape
    # This filter should be specific to known sitemap index/file names
    sitemap_urls = {url for url in sitemap_urls if not (url.endswith('sitemap.xml') or url.endswith('sitemap_index.xml'))}
    
    page_urls_to_scrape = list(sitemap_urls)
    if not page_urls_to_scrape:
        logger.warning(f"No page URLs found from sitemaps for {base_url}. Will attempt to crawl only the base URL.")
        page_urls_to_scrape = [base_url] # Fallback to scraping just the base_url if no sitemap URLs
    else:
        logger.info(f"Total unique page URLs found: {len(page_urls_to_scrape)}")

    if max_pages > 0 and len(page_urls_to_scrape) > max_pages:
        logger.info(f"Limiting scrape to {max_pages} pages from {len(page_urls_to_scrape)} found URLs.")
        page_urls_to_scrape = page_urls_to_scrape[:max_pages]
    
    all_documents: list[Document] = []    
    # Prepare LLM config for filtering, if enabled
    llm_config_for_filter = None
    llm_filter_instruction_for_filter = None
    if use_llm_filter:
        llm_config_for_filter, llm_filter_instruction_for_filter = _prepare_llm_config_for_crawl4ai()
    else:
        logger.info(f"LLMContentFilter is DISABLED for scraping {base_url}.")

    # Configure Browser for Crawl4AI (can be customized)
    # Example: browser_config = BrowserConfig(headless=True, browser="chromium")
    browser_conf = None 

    tasks = [
        Crawl4AILoader(
            url, 
            browser_config=browser_conf, 
            llm_config=llm_config_for_filter, 
            llm_filter_instruction=llm_filter_instruction_for_filter
        ).aload() for url in page_urls_to_scrape
    ]
    
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results_list:
        if isinstance(result, Exception):
            logger.error(f"A crawl task failed: {result}")
        elif result: 
            all_documents.extend(result)
            
    logger.info(f"Successfully scraped {len(all_documents)} pages from {base_url}.")
    return all_documents

# Example Usage (for testing purposes)
async def main_test():
    test_url = "https://streamlit.io" 
    logger.info(f"Testing website scraper for {test_url} WITHOUT LLM filter bypass.")
    documents_with_filter = await scrape_website(test_url, max_pages=1, use_llm_filter=True)
    if documents_with_filter:
        for doc in documents_with_filter:
            print(f"--- WITH FILTER ---")
            print(f"URL: {doc.metadata['source']}")
            print(f"Title: {doc.metadata.get('title', 'N/A')}")
            print(f"Content snippet (first 300 chars):")
            print(doc.page_content[:300])
            print("---")
    else:
        print(f"No documents were scraped from {test_url} (with filter).")
    
    logger.info(f"Testing website scraper for {test_url} WITH LLM filter bypass.")
    documents_without_filter = await scrape_website(test_url, max_pages=1, use_llm_filter=False)
    if documents_without_filter:
        for doc in documents_without_filter:
            print(f"--- WITHOUT FILTER ---")
            print(f"URL: {doc.metadata['source']}")
            print(f"Title: {doc.metadata.get('title', 'N/A')}")
            print(f"Content snippet (first 300 chars):")
            print(doc.page_content[:300])
            print("---")
    else:
        print(f"No documents were scraped from {test_url} (without filter).")

    # Test single URL with and without bypass
    single_test_url = "https://streamlit.io/gallery" # A specific page for more targeted test
    logger.info(f"Testing single URL: {single_test_url} WITHOUT LLM filter bypass.")
    content_single_with_filter = await get_content_from_url(single_test_url, bypass_llm_filter=False)
    print(f"--- SINGLE URL WITH FILTER ---")
    print(f"Content (first 300 chars):")
    print(content_single_with_filter[:300])
    print("---")

    logger.info(f"Testing single URL: {single_test_url} WITH LLM filter bypass.")
    content_single_without_filter = await get_content_from_url(single_test_url, bypass_llm_filter=True)
    print(f"--- SINGLE URL WITHOUT FILTER ---")
    print(f"Content (first 300 chars):")
    print(content_single_without_filter[:300])
    print("---")

if __name__ == "__main__":
    # Setup basic logging for testing
    import sys
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    async def run_main_test():
        await main_test()

    asyncio.run(run_main_test())