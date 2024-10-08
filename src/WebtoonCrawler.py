from src.WebDriverFactory import ChromeWebDriverFactory
from src.WebtoonRepository import WebtoonRepository
from src.WebtoonScraper import WebtoonScraper
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import WebDriverException

# Crawler 클래스
class WebtoonCrawler:
    def __init__(self, scraper: WebtoonScraper, repository: WebtoonRepository):
        self.scraper = scraper
        self.repository = repository

    def run(self):
        for url in self.scraper.get_urls():
            self.scraper.open_page(url)
            webtoon_elements = self.scraper.get_webtoon_elements()

            if not webtoon_elements:
                print("No webtoon elements found. Exiting...")
                continue
        
            webtoon_list_len = 40 #len(webtoon_elements)
            for i in range(webtoon_list_len):
                try:
                    print(f"Processing: {i + 1} / {webtoon_list_len}")

                    webtoon_elements = self.scraper.get_webtoon_elements()
                    webtoon_data = self.scraper.scrape_webtoon_info(webtoon_elements[i])

                    if webtoon_data:
                        self.repository.save(webtoon_data)
                except StaleElementReferenceException:
                    print(f"StaleElementReferenceException encountered on element {i + 1}. Retrying...")
                    continue
                except WebDriverException as e:
                    print(f"WebDriverException encountered: {e}. Retrying...")
                    self.scraper.driver.refresh()  # 페이지 새로고침
                    continue
