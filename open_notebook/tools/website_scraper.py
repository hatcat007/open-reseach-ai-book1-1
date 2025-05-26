import asyncio
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup # Using BeautifulSoup for robots.txt parsing, assuming it might be better for varied formats
from crawl4ai import AsyncWebCrawler, BrowserConfig
from langchain.docstore.document import Document
from loguru import logger
from lxml import etree # Using lxml for robust XML parsing


class Crawl4AILoader:  # Adapted from BaseLoader
    """
    Custom Document Loader that uses crawl4ai to fetch and process web content.
    """
    def __init__(self, start_url: str, browser_config: BrowserConfig = None):
        """
        Initialize the Crawl4AI document loader.

        Args:
            start_url (str): The URL to crawl.
            browser_config (BrowserConfig, optional): Optional browser configuration for crawl4ai.
        """
        self.start_url = start_url
        self.browser_config = browser_config
        # Initialize crawler here if it can be reused across calls, or in aload if not.
        # For simplicity, let's assume it's better to init fresh for each call in this context
        # to avoid state issues if this loader instance is reused unexpectedly.

    async def aload(self) -> list[Document]:
        """
        Asynchronously load a single document using crawl4ai.

        Returns:
            A list containing a single Document object with the crawled content and metadata.
        """
        crawler = AsyncWebCrawler(config=self.browser_config)
        try:
            await crawler.start()
            logger.info(f"Crawling URL: {self.start_url}")
            results = await crawler.arun(self.start_url)
            if results and results.markdown:
                page_title = getattr(results, 'title', None) # Safely get title
                metadata = {
                    "url": results.url, 
                    "source": results.url, 
                    "title": page_title or urlparse(results.url).path # Use getattr result
                }
                logger.info(f"Successfully crawled and processed: {results.url}, Markdown length: {len(results.markdown)}, Title: {metadata['title']}")
                return [Document(page_content=results.markdown, metadata=metadata)]
            else:
                logger.warning(f"No content or markdown found for URL: {self.start_url}. Results: {results}")
                return []
        except Exception as e:
            logger.error(f"Error crawling {self.start_url}: {e}")
            return []
        finally:
            await crawler.close()

async def get_content_from_url(url: str, browser_config: BrowserConfig = None) -> str:
    """Fetches content from a single URL using Crawl4AILoader and returns its markdown.
    
    Args:
        url (str): The URL to fetch content from.
        browser_config (BrowserConfig, optional): Optional browser configuration.

    Returns:
        str: The markdown content of the page, or an empty string if an error occurs or no content.
    """
    parsed_url = urlparse(url)
    if not parsed_url.scheme:
        url = f"https://{url}"
        logger.info(f"get_content_from_url: No scheme in URL, defaulting to HTTPS: {url}")

    loader = Crawl4AILoader(url, browser_config=browser_config)
    documents = await loader.aload() # aload returns a list of Documents
    if documents and documents[0].page_content:
        return documents[0].page_content
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

    loader = Crawl4AILoader(url, browser_config=browser_config)
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
        
        # Using lxml for parsing
        root = etree.fromstring(response.content)
        
        # XML sitemaps can have different namespaces, try to find loc tags
        # Common namespaces
        namespaces = {
            'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9',
            'image': 'http://www.google.com/schemas/sitemap-image/1.1' 
            # Add other common namespaces if needed
        }
        
        # Try to find <loc> tags, common in sitemaps
        # The xpath expression tries to find <loc> elements regardless of their namespace prefix
        # or if they are in the default namespace.
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
        
        # More robust regex to find Sitemap directives, case-insensitive for "sitemap:"
        sitemap_match = re.search(r"^Sitemap:\s*(.*)", content, re.IGNORECASE | re.MULTILINE)
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


async def scrape_website(base_url: str, max_pages: int = 0) -> list[Document]:
    """
    Scrapes a website based on its sitemap.xml or sitemap found in robots.txt.
    
    Args:
        base_url (str): The base URL of the website to scrape (e.g., https://www.example.com).
        max_pages (int): Maximum number of pages to scrape. 0 for no limit.

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
        # Ensure the sitemap URL is absolute
        robots_sitemap_url = urljoin(base_url, robots_sitemap_path) if robots_sitemap_path.startswith('/') else robots_sitemap_path
        sitemap_urls_to_try.append(robots_sitemap_url)

    all_page_urls = set()

    for sitemap_url in sitemap_urls_to_try:
        page_urls = await _fetch_xml_sitemap_urls(sitemap_url)
        for url in page_urls:
            all_page_urls.add(url)
            # If sitemap URL is itself a sitemap index, recursively fetch
            if url.endswith(".xml"): # Basic check for sitemap index
                logger.info(f"Found potential sitemap index: {url}, fetching...")
                nested_urls = await _fetch_xml_sitemap_urls(url)
                for nested_url in nested_urls:
                    all_page_urls.add(nested_url)
    
    # Filter out non-HTML links if possible (e.g. .xml, .txt, image extensions)
    # This is a basic filter, more robust filtering might be needed.
    filtered_page_urls = [
        url for url in all_page_urls 
        if not url.endswith((".xml", ".txt", ".jpg", ".png", ".pdf")) # Add more if needed
    ]

    logger.info(f"Total unique page URLs found: {len(filtered_page_urls)}")

    if max_pages > 0 and len(filtered_page_urls) > max_pages:
        logger.info(f"Limiting scrape to {max_pages} pages from {len(filtered_page_urls)} found URLs.")
        urls_to_scrape = list(filtered_page_urls)[:max_pages]
    else:
        urls_to_scrape = list(filtered_page_urls)

    all_documents: list[Document] = []
    
    # Consider browser_config if needed, e.g., for playwright
    # browser_conf = BrowserConfig(
    #    provider="playwright",  # or "selenium"
    #    headless=True,
    # )
    browser_conf = None # Using default (likely HTTPX) for now

    # Using asyncio.gather to run loaders concurrently
    # Creating a loader for each URL
    tasks = [Crawl4AILoader(url, browser_config=browser_conf).aload() for url in urls_to_scrape]
    
    results_list = await asyncio.gather(*tasks, return_exceptions=True) # Gather results, including exceptions

    for result in results_list:
        if isinstance(result, Exception):
            logger.error(f"A crawl task failed: {result}")
        elif result: # aload returns a list of Documents
            all_documents.extend(result)
            
    logger.info(f"Successfully scraped {len(all_documents)} pages from {base_url}.")
    return all_documents

# Example Usage (for testing purposes)
async def main_test():
    # Test with a known sitemap.xml or a website with robots.txt pointing to one
    # test_url = "https://www.langchain.com" # Has robots.txt with sitemap
    test_url = "https://streamlit.io" # Has robots.txt with sitemap
    # test_url = "https://surrealdb.com/" # Check if it has sitemap or robots.txt for sitemap
    
    logger.info(f"Testing website scraper for {test_url}")
    documents = await scrape_website(test_url, max_pages=5) # Limit for testing
    if documents:
        for doc in documents:
            print(f"URL: {doc.metadata['source']}")
            print(f"Title: {doc.metadata.get('title', 'N/A')}")
            print(f"Content snippet: {doc.page_content[:200]}...\n")
    else:
        print(f"No documents were scraped from {test_url}.")

if __name__ == "__main__":
    # Setup basic logging for testing
    import sys
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    async def run_main_test(): # Changed to be a valid async def
        await main_test()

    asyncio.run(run_main_test()) # Correctly run the async main_test