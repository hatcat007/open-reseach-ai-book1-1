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
        "Extract only the main textual content of the article or page. "
        "Exclude all website navigation elements (menus, sidebars, breadcrumbs), "
        "headers, footers, lists of related links, advertisements, and cookie consent pop-ups. "
        "Remove any isolated URLs or links that are not part of a sentence in the main content. "
        "Focus on providing a clean, readable version of the core information presented."
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

async def get_title_from_url(url: str, browser_config: BrowserConfig = None) -> str:
    """Fetches title from a single URL using Crawl4AILoader.
    
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

    loader = Crawl4AILoader(url, browser_config=browser_config, llm_config=None, llm_filter_instruction=None)
    documents = await loader.aload()
    if documents and documents[0].metadata and documents[0].metadata.get("title"):
        return documents[0].metadata["title"]
    logger.warning(f"get_title_from_url: No title found for {url}")
    return ""

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


async def scrape_website(base_url: str, max_pages: int = 0, bypass_llm_filter: bool = False) -> list[Document]:
    """
    Scrapes a website based on its sitemap.xml or sitemap found in robots.txt.
    
    Args:
        base_url (str): The base URL of the website to scrape (e.g., https://www.example.com).
        max_pages (int): Maximum number of pages to scrape. 0 for no limit.
        bypass_llm_filter (bool): If True, LLM content filtering will be skipped for all pages.

    Returns:
        A list of Document objects, each containing the markdown content of a page.
    """
    parsed_url = urlparse(base_url)
    if not parsed_url.scheme:
        base_url = f"https://{base_url}"
        logger.info(f"No scheme in base_url, defaulting to HTTPS: {base_url}")

    logger.info(f"Starting website scrape for: {base_url}")
    sitemap_urls_to_try = [urljoin(base_url, "/sitemap.xml")]
    
    robots_sitemap_path = await _fetch_sitemap_url_from_robots(base_url)
    if robots_sitemap_path:
        robots_sitemap_url = urljoin(base_url, robots_sitemap_path) if robots_sitemap_path.startswith('/') else robots_sitemap_path
        sitemap_urls_to_try.append(robots_sitemap_url)

    all_page_urls = set()

    for sitemap_url in sitemap_urls_to_try:
        page_urls = await _fetch_xml_sitemap_urls(sitemap_url)
        for url in page_urls:
            all_page_urls.add(url)
            if url.endswith(".xml"):
                logger.info(f"Found potential sitemap index: {url}, fetching...")
                nested_urls = await _fetch_xml_sitemap_urls(url)
                for nested_url in nested_urls:
                    all_page_urls.add(nested_url)
    
    filtered_page_urls = [
        url for url in all_page_urls 
        if not url.endswith((".xml", ".txt", ".jpg", ".png", ".pdf"))
    ]

    logger.info(f"Total unique page URLs found: {len(filtered_page_urls)}")

    if max_pages > 0 and len(filtered_page_urls) > max_pages:
        logger.info(f"Limiting scrape to {max_pages} pages from {len(filtered_page_urls)} found URLs.")
        urls_to_scrape = list(filtered_page_urls)[:max_pages]
    else:
        urls_to_scrape = list(filtered_page_urls)

    all_documents: list[Document] = []
    
    llm_config_for_scrape = None
    filter_instruction_for_scrape = None

    if not bypass_llm_filter:
        llm_config_for_scrape, filter_instruction_for_scrape = _prepare_llm_config_for_crawl4ai()
    else:
        logger.info(f"scrape_website: Bypassing LLM content filter for all pages from {base_url}.")
    
    browser_conf = None 

    tasks = [
        Crawl4AILoader(
            url, 
            browser_config=browser_conf, 
            llm_config=llm_config_for_scrape, 
            llm_filter_instruction=filter_instruction_for_scrape
        ).aload() for url in urls_to_scrape
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
    documents_with_filter = await scrape_website(test_url, max_pages=1, bypass_llm_filter=False)
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
    documents_without_filter = await scrape_website(test_url, max_pages=1, bypass_llm_filter=True)
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