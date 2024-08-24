from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from bs4 import BeautifulSoup as bs
from time import sleep
import re
import json
import requests


# WebDriverFactory를 인터페이스로 정의하여 확장성을 높임
class WebDriverFactory(ABC):
    @abstractmethod
    def create_driver(self) -> webdriver.Chrome:
        pass

class ChromeWebDriverFactory(WebDriverFactory):
    def __init__(self, chromedriver_path: str):
        self.chromedriver_path = chromedriver_path

    def create_driver(self) -> webdriver.Chrome:
        chrome_service = Service(self.chromedriver_path)
        chrome_options = Options()
        return webdriver.Chrome(service=chrome_service, options=chrome_options)

# WebtoonScraper 인터페이스 정의
class WebtoonScraper(ABC):
    @abstractmethod
    def get_urls(self) -> list:
        pass

    @abstractmethod
    def open_page(self, url: str):
        pass

    @abstractmethod
    def get_webtoon_elements(self) -> list:
        pass

    @abstractmethod
    def scrape_webtoon_info(self, webtoon_element) -> dict:
        pass

# NaverWebtoonScraper 구현
class NaverWebtoonScraper(WebtoonScraper):
    PLATFORM_NAME = "naver"

    NAVER_WEBTOON_URLS = [
        'https://comic.naver.com/webtoon?tab=mon',
        'https://comic.naver.com/webtoon?tab=tue',
        'https://comic.naver.com/webtoon?tab=wed',
        'https://comic.naver.com/webtoon?tab=thu',
        'https://comic.naver.com/webtoon?tab=fri',
        'https://comic.naver.com/webtoon?tab=sat',
        'https://comic.naver.com/webtoon?tab=sun',
        'https://comic.naver.com/webtoon?tab=dailyPlus',
        'https://comic.naver.com/webtoon?tab=finish'
    ]
    CONTENT_LIST_CLASS = "ContentList__content_list--q5KXY"
    ITEM_CLASS = "item"
    RATING_CLASS = "Rating__star_area--dFzsb"
    TITLE_AREA_CLASS = "ContentTitle__title_area--x24vt"

    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    def get_urls(self) -> list:
        return self.NAVER_WEBTOON_URLS

    def open_page(self, url: str):
        self.driver.get(url)
        WebDriverWait(self.driver, 3).until(lambda d: d.execute_script('return document.readyState') == 'complete')

    def get_webtoon_elements(self) -> list:
        return WebDriverWait(self.driver, 3).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, self.ITEM_CLASS))
        )

    def scrape_webtoon_info(self, webtoon_element) -> dict:
        try:

            rating = WebDriverWait(webtoon_element, 1).until(
                EC.presence_of_element_located((By.CLASS_NAME, self.RATING_CLASS))
            ).text.strip()

            title_element = webtoon_element.find_element(By.CLASS_NAME, self.TITLE_AREA_CLASS)
            title_element.click()

            WebDriverWait(self.driver, 1).until(EC.presence_of_element_located((By.CLASS_NAME, self.TITLE_AREA_CLASS)))
            soup = bs(self.driver.page_source, 'html.parser')

            title = soup.find('h2', {'class': 'EpisodeListInfo__title--mYLjC'}).text.strip()
            day_age = soup.find('div', {'class': 'ContentMetaInfo__meta_info--GbTg4'}).find('em', {'class': 'ContentMetaInfo__info_item--utGrf'}).text.strip()
            thumbnail_url = soup.find('div', {'class': 'Poster__thumbnail_area--gviWY'}).find('img')['src']
            story = soup.find('div', {'class': 'EpisodeListInfo__summary_wrap--ZWNW5'}).find('p').text.strip()

            # 작가 정보 추출
            author_elements = soup.find_all('span', {'class': 'ContentMetaInfo__category--WwrCp'})
            authors = []
            for author_element in author_elements:
                author_name = author_element.find('a').text.strip()
                author_role = author_element.find(text=True, recursive=False).strip().replace("::after", "").replace(".", "")
                author_link = author_element.find('a')['href']
                authors.append({
                    "name": author_name,
                    "role": author_role,
                    "link": author_link
                })

            # 장르 추출
            genre_elements = soup.find('div', {'class': 'TagGroup__tag_group--uUJza'}).find_all('a', {'class': 'TagGroup__tag--xu0OH'})
            genres = [genre.text.strip().replace('#', '') for genre in genre_elements]

            # 고유 ID 추출 및 int 형식으로 저장
            url = self.driver.current_url
            id_match = re.search(r'titleId=(\d+)', url)
            unique_id = int(id_match.group(1)) if id_match else None

            # 회차 수 추출
            episode_count_element = soup.find('div', {'class': 'EpisodeListView__count--fTMc5'})
            episode_count = int(re.search(r'\d+', episode_count_element.text).group()) if episode_count_element else None

            # 웹툰 1화 보기 링크 추출 및 접두사 추가
            first_episode_link = soup.find('a', {'class': 'EpisodeListUser__item--Fjp4R EpisodeListUser__view--PaVFx'})['href']
            full_first_episode_link = f"https://comic.naver.com{first_episode_link}"

            rating = re.search(r'\d+\.\d+', rating).group(0)
            day_match = re.search(r'(월|화|수|목|금|토|일)|완결', day_age)
            day = day_match.group(0) if day_match else None

            age_rating_match = re.search(r'(전체연령가|\d+세)', day_age)
            age_rating = age_rating_match.group(0) if age_rating_match else None

            return {
                "id": 0,
                "unique_id": unique_id,
                "title": title,
                "day": day,
                "rating": rating,
                "thumbnail_url": thumbnail_url,
                "story": story,
                "url": url,
                "age_rating": age_rating,
                "authors": authors,
                "genres": genres,
                "episode_count": episode_count,
                "first_episode_link": full_first_episode_link
            }
        except TimeoutException:
            print("TimeoutException: Could not load webtoon page. Skipping...")
            return None
        finally:
            self.driver.back()
            sleep(0.5)


class KaKaoWebtoonScraper(WebtoonScraper):
    PLATFORM_NAME = "kakao"
    
    KAKAO_WEBTOON_URLS = [
        #'https://webtoon.kakao.com/?tab=mon',
        #'https://webtoon.kakao.com/?tab=tue',
        #'https://webtoon.kakao.com/?tab=wed',
        #'https://webtoon.kakao.com/?tab=thu',
        #'https://webtoon.kakao.com/?tab=fri',
        #'https://webtoon.kakao.com/?tab=sat',
        'https://webtoon.kakao.com/?tab=sun',
        #'https://webtoon.kakao.com/?tab=complete'
    ]

    # 웹툰 목록 관련 상수
    WEBTOON_LINK_CLASS = ".w-full.h-full.relative.overflow-hidden.rounded-8.before\\:absolute.before\\:inset-0.before\\:bg-grey-01.before\\:-z-1"
    CONTAINER_DIV_SELECTOR = ".w-fit.flex.overflow-x-scroll.no-scrollbar.scrolling-touch.space-x-6"
    WEBTOON_CONTAINER_SELECTOR = ".flex.flex-wrap.gap-4.content-start"
    WEBTOON_ELEMENT_SELECTOR = ".flex-grow-0.overflow-hidden.flex-\\[calc\\(\\(100\\%\\-12px\\)\\/4\\)\\]"
    TITLE_SELECTOR_X = '.whitespace-pre-wrap.break-all.break-words.support-break-word.overflow-hidden.text-ellipsis.s22-semibold-white.text-center.leading-26'

    TITLE_SELECTOR = 'whitespace-pre-wrap break-all break-words support-break-word overflow-hidden text-ellipsis !whitespace-nowrap s22-semibold-white text-center leading-26'
    STORY_SELECTOR = 'whitespace-pre-wrap break-all break-words support-break-word s13-regular-white leading-20 overflow-hidden'
    DAY_SELECTOR = 'whitespace-pre-wrap break-all break-words support-break-word font-badge !whitespace-nowrap rounded-5 s10-bold-black bg-white px-5 !text-[11px]'

    GENRE_SELECTOR = 'whitespace-pre-wrap break-all break-words support-break-word overflow-hidden text-ellipsis !whitespace-nowrap s14-medium-white'
    EPISODE_COUNT_SELECTOR = 'whitespace-pre-wrap break-all break-words support-break-word overflow-hidden text-ellipsis !whitespace-nowrap leading-14 s12-regular-white'
    FIRST_EPISODE_LINK_SELECTOR = 'relative px-10 py-0 w-full h-44 rounded-6 bg-white/10 mb-8'
    AUTHORS_SELECTOR = 'div.rounded-12.p-18.bg-white\\10.mb-8 > dl > div.flex.mb-8'

    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    def get_urls(self) -> list:
        return self.KAKAO_WEBTOON_URLS

    def open_page(self, url: str):
        self.driver.get(url)
        WebDriverWait(self.driver, 3).until(lambda d: d.execute_script('return document.readyState') == 'complete')

    def get_webtoon_elements(self) -> list:
        """웹툰 목록을 클릭 후, 웹툰 요소를 추출합니다."""
        try:
            # 전체 버튼 클릭
            container_div = WebDriverWait(self.driver, 1).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.CONTAINER_DIV_SELECTOR))
            )
            button = container_div.find_element(By.TAG_NAME, "button")
            self.driver.execute_script("arguments[0].click();", button)

            # 웹툰 목록 컨테이너 확인 후, 웹툰 요소 추출
            container = WebDriverWait(self.driver, 1).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.WEBTOON_CONTAINER_SELECTOR))
            )
            return container.find_elements(By.CSS_SELECTOR, self.WEBTOON_ELEMENT_SELECTOR)
        
        except TimeoutException:
            print("TimeoutException: Could not find or click button. Skipping...")
            return []

    def scrape_webtoon_info(self, webtoon_element) -> dict:
        try:
            link_element = webtoon_element.find_element(By.CSS_SELECTOR, self.WEBTOON_LINK_CLASS)
            url = link_element.get_attribute("href")
            deapth_count = 0
            
            if url:
                self.driver.get(url)
                deapth_count = 1
                WebDriverWait(self.driver, 1).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.TITLE_SELECTOR_X))
                )
                soup = bs(self.driver.page_source, 'html.parser')

                title = soup.find('p', {'class': self.TITLE_SELECTOR}).text.strip()

                episode_count = soup.find('p', {'class': self.EPISODE_COUNT_SELECTOR}).text.strip()

                id_match = re.search(r'titleId=(\d+)', url)
                unique_id = int(id_match.group(1)) if id_match else None

                # 정보탭에서 데이터 추출
                info_url = url + "?tab=profile"
                self.driver.get(info_url)
                deapth_count = 2
                soup = bs(self.driver.page_source, 'html.parser')
                WebDriverWait(self.driver, 1).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.TITLE_SELECTOR_X))
                )

                story = soup.find('p', {'class': self.STORY_SELECTOR}).text.strip()
                day = soup.find('p', {'class': self.DAY_SELECTOR}).text.strip()

                # 장르 추출
                genre_elements = soup.find_all('p', {'class': self.GENRE_SELECTOR})
                genres = [genre.text.strip().replace('#', '') for genre in genre_elements]

                # 작가 정보 추출
                author_elements = soup.select('div.flex.mb-8')
                authors = []
                for element in author_elements:
                    role = element.find('dt').text.strip()
                    names = element.find('dd').text.strip().split(',')
                    for name in names:
                        authors.append({
                            "name": name.strip(),
                            "role": role,
                            "link": "/author_link"  # 링크 정보가 없다면 기본값 사용
                        })

                return {
                    "unique_id": unique_id,
                    "title": title,
                    "day": day,
                    "rating": 0,
                    "thumbnail_url": "http://example.com/thumbnail.jpg",
                    "thumbnail_url2": "http://example.com/thumbnail.jpg",
                    "story": story,
                    "url": url,
                    "age_rating": "전체연령가",
                    "authors": authors,
                    "genres": genres,
                    "episode_count": episode_count,
                    "first_episode_link": ""
                }

        except TimeoutException:
            print("TimeoutException: Could not load webtoon page. Skipping...")
            return None
        finally:
            for i in range(deapth_count):
                self.driver.back()
            sleep(0.5)


# Repository 인터페이스 정의
class WebtoonRepository(ABC):
    @abstractmethod
    def save(self, webtoon_data: dict):
        pass

    @abstractmethod
    def save_to_json(self, filename: str):
        pass

class JsonWebtoonRepository(WebtoonRepository):
    def __init__(self):
        self.webtoons = []
        self.webtoon_id = 0

    def save(self, webtoon_data: dict):
        if self._exists(webtoon_data["title"]):
            self._update_day(webtoon_data)
        else:
            webtoon_data["id"] = self.webtoon_id
            self.webtoons.append(webtoon_data)
            self.webtoon_id += 1

    def _exists(self, title: str) -> bool:
        return any(webtoon['title'] == title for webtoon in self.webtoons)

    def _update_day(self, webtoon_data: dict):
        for webtoon in self.webtoons:
            if webtoon['title'] == webtoon_data['title']:
                webtoon['day'] += ', ' + webtoon_data['day']
                break

    def save_to_json(self, filename: str):
        with open(f"{filename}.json", "w", encoding="utf-8") as output_file:
            json.dump(self.webtoons, output_file, ensure_ascii=False, indent=4)

# Crawler 클래스는 웹스크래퍼와 레포지토리에 의존
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
        
            webtoon_list_len = 3 #len(webtoon_elements)
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

# Factory Method를 사용하는 메인 함수
def main():
    driver_factory = ChromeWebDriverFactory('C:/chromedriver-win64/chromedriver.exe')
    driver = driver_factory.create_driver()
    repository = JsonWebtoonRepository()

    scraper_type = 'kakao'

    if scraper_type == 'naver':
        scraper = NaverWebtoonScraper(driver)
    elif scraper_type == 'kakao':
        scraper = KaKaoWebtoonScraper(driver)

    crawler = WebtoonCrawler(scraper, repository)

    try:
        crawler.run()
    finally:
        repository.save_to_json(scraper_type+"_webtoon_list")
        input("프로그램을 종료하려면 엔터를 누르세요...")
        driver.quit()

if __name__ == "__main__":
    main()
