import requests
from bs4 import BeautifulSoup
import random
from collections import OrderedDict
import time


class ResultGatherer:

    # A list of possible headers to use, which simulate manual web use to avoid simple bot blockers
    headers_list = [
        # Firefox 77 Mac
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        },
        # Firefox 77 Windows
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.google.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        },
        # Chrome 83 Mac
        {
            "Connection": "keep-alive",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document",
            "Referer": "https://www.google.com/",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8"
        },
        # Chrome 83 Windows
        {
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Referer": "https://www.google.com/",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9"
        }
    ]
    # Create ordered dict from headers_list to allow for random selection
    ordered_headers_list = []
    for headers in headers_list:
        h = OrderedDict()
        for header, value in headers.items():
            h[header] = value
        ordered_headers_list.append(h)

    ###################################################################

    # Grab all available results on a specified page
        # @param soup_object : A BeautifulSoup response object
        # @param page_max : The maximum number of results on this page
    def __get_results_from_page(self, soup_object, page_max):
        scholar_results = []
        index = 1
        for element in soup_object.select(".gs_r"):
            if index > page_max:
                break
            # Get title, URL, direct file URL, authors, Google Scholar identifier, and abstract excerpt for each result
            # Each correlate to specific, nested elements on the page
            title = element.select_one(".gs_rt")
            link = element.select_one(".gs_rt a")
            file_link = element.select_one('.gs_or_ggsm a')
            authors = element.select_one(".gs_a")
            scholar_id = element.select_one(".gs_rt a")
            snippet = element.select_one(".gs_rs")
            # Then append them to a dictionary
            scholar_results.append({
                "title": title.text if title else "No title",
                "link": link["href"] if link else "No result link",
                "file_link": file_link["href"] if file_link else "No file link",
                "authors": authors.text.split('\xa0') if authors else "No authors",
                "scholar_id": scholar_id["id"] if scholar_id else "No ID",
                "snippet": snippet.text.replace("\n", "") if snippet else "No snippet"
                # "title": element.select_one(".gs_rt").text,
                # "link": element.select_one(".gs_rt a")["href"],
                # "file_link": element.select_one('.gs_or_ggsm a')["href"],
                # "authors": element.select_one(".gs_a").text.split('\xa0'),
                # "scholar_id": element.select_one(".gs_rt a")["id"],
                # "snippet": element.select_one(".gs_rs").text.replace("\n", "")
            })
            index += 1
        return scholar_results

    # Craft a URL for the desired query, specifying the starting result and number to grab
    # This allows for an iterative approach to result gathering
        # @param query : The Google Scholar search query
        # @param start : The starting index for results on the page
        # @param num : The number of results to include on this page
        # @param language : The language to use for the page - default is english
    def __build_url(self, query, start, num, language="en"):
        base = "https://scholar.google.com/scholar?"
        query = query.replace(" ", "+")
        return f"{base}hl={language}&num={num}&start={start}&q={query}"

    # Iteratively gather a set number of results for the desired query
        # @param query : The Google Scholar search query
        # @param total_results : The total number of results to gather
        # @param num : The number of results on each page - default is 10
    def scrape_results(self, query, total_results, num=10):
        scholar_results = []
        start = 0
        while start < total_results:
            print(f"\rGetting results {start}-{start+num-1}", end="")
            url = self.__build_url(query, start, num)
            session = requests.Session()
            headers_to_use = random.choice(self.ordered_headers_list)
            session.headers = headers_to_use
            response = session.get(url)
            soup = BeautifulSoup(response.text, "html.parser")
            page_results = self.__get_results_from_page(soup, num)
            scholar_results.extend(page_results)
            start += num
            # Google Scholar has strict anti-bot policies, so scraping slowly is a must
            delay = random.uniform(3, 7)
            time.sleep(delay)
        print("\nScraping complete")
        return scholar_results
