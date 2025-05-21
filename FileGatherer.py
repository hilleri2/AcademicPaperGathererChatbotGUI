import os
import requests
from bs4 import BeautifulSoup
import random
import time
import io
from urllib.parse import urljoin

import FileFilterer
import FileWriter
import DuplicateFilter
import Headers
import HeadlessBrowser


class FileGatherer:

    # Method that attempts to fetch content from a URL and will retry if failed, with a longer delay each time
    # @param url : The URl to fetch from
    # @param print_index : The index used for printing status
    # @param max_tries : The maximum number of times to try a request
    def fetch(self, url, print_index, max_tries=2):
        for _ in range(max_tries):
            try:
                headers_to_use = Headers.Headers().get_rand_header_modern()
                response = requests.get(url, headers=headers_to_use, timeout=10)
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    print(f"\rProcessing files at index {print_index}... Request blocked")
            except requests.exceptions.RequestException as e:
                print(f"\rProcessing files at index {print_index}... Request failed on attempt: {e}")
                delay = random.uniform(2, 5)
                time.sleep(delay)
        return None

    def gather_files_headless(self, results: list, query: str, path_to_directory: str):
        result_index = 1
        print_index = 0
        browser = HeadlessBrowser.HeadlessBrowser()

        for result in results:
            print_index += 1
            print(f"\rProcessing index {print_index}...", end="")
            time.sleep(random.uniform(3, 7))

            url = result.get('file_link') or result.get('link')
            if not url:
                print(f"\nNo link for index {print_index}")
                continue

            try:
                html = browser.fetch_page_headless(url)
            except Exception as e:
                print(f"\nFailed to fetch page {url} due to: {e}")
                continue

            soup = BeautifulSoup(html, 'html.parser')

            # Heuristic: check for direct PDF download
            if url.lower().endswith(".pdf"):
                try:
                    response = requests.get(url)
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "pdf" in content_type:
                        pdf_file_obj = io.BytesIO(response.content)
                        filter_result = FileFilterer.FileFilterer().filter(pdf_file_obj, query)
                        result_index = self.handle_file_result(response, filter_result, result_index, path_to_directory)
                        continue
                except Exception as e:
                    print(f"\nFailed to download PDF from {url}: {e}")
                    continue

            # Otherwise, find all <a href="...pdf">
            links = soup.find_all('a')
            for link in links:
                file_url = link.get('href')
                if not file_url or not file_url.lower().endswith(".pdf"):
                    continue

                if file_url.startswith('/'):
                    # handle relative URLs
                    print("\n\tFound relative URL.")
                    file_url = urljoin(url, file_url)

                try:
                    response = requests.get(file_url)
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "pdf" not in content_type:
                        print(f"\nSkipping {file_url} (not a valid PDF)")
                        continue

                    pdf_file_obj = io.BytesIO(response.content)
                    filter_result = FileFilterer.FileFilterer().filter(pdf_file_obj, query)
                    result_index = self.handle_file_result(response, filter_result, result_index, path_to_directory)

                except Exception as e:
                    print(f"\nFailed to download or process PDF from {file_url}: {e}")
                    continue

        print("\nAll results scraped.")


    # Gather files from each result, including ones that are referenced on each web page
        # @param results : List of scraped results from Google Scholar
        # @param query : The Google Scholar search query
        # @param path_to_directory : The path to the directory where all files will be saved
        # @param meta_can_be_missing : Boolean toggle that determines if absent title and author is acceptable
    def gather_files(self, results: list, query: str, path_to_directory: str, meta_can_be_missing: bool):
        result_index = 1
        print_index = 0
        for result in results:  # Iterate over results
            print_index += 1
            print(f"\rProcessing files at index {print_index}...", end="")
            # Sleep for 3 to 7 seconds to avoid angering any anti-bot policies
            delay = random.uniform(3, 7)
            time.sleep(delay)
            # Some results have a file_link, which may be different from the regular link, but not all have this
            #   so, if this value is None, then just use the regular file link, which all results have
            url = result['file_link']
            if url is None:
                url = result['link']
            if url is None:
                # No link for this index
                print(f"\nNo link for index {print_index}")
                continue
            response = self.fetch(url, print_index)
            if not response:
                print(f"\nFailed to fetch {url}")
                continue

            content_type = response.headers.get("Content-Type", "").lower()
            if "pdf" in content_type:
                pdf_file_obj = io.BytesIO(response.content)
                filter_result = FileFilterer.FileFilterer().filter(pdf_file_obj, query, meta_can_be_missing)
                result_index = self.handle_file_result(response, filter_result, result_index, path_to_directory)
                continue

            soup = BeautifulSoup(response.text, 'html.parser')  # Use BeautifulSoup to parse the returned results
            links = soup.find_all('a')  # Find all hyperlinks present on webpage
            i = 0  # Used for numbering the PDFs

            # Check all links for PDFs and grab the ones that are found
            #   this is the step that introduces problems, as some links report to be PDFs
            #   but are not or are just empty -- handled by checking response type
            for link in links:
                file_url = link.get('href')
                if file_url and file_url.lower().endswith(".pdf"):
                    response = self.fetch(file_url, print_index)
                    if not response:
                        continue

                    content_type = response.headers.get("Content-Type", "").lower()
                    if "pdf" not in content_type:
                        print(f"\nSkipping {file_url} (not a valid PDF)")
                        continue

                    pdf_file_obj = io.BytesIO(response.content)
                    filter_result = FileFilterer.FileFilterer().filter(pdf_file_obj, query, meta_can_be_missing)
                    result_index = self.handle_file_result(response, filter_result, result_index, path_to_directory)
        print("\nAll results scraped.")

    # Checks returned file result from filtering and saves the appropriate data
        # @param response : The GET response of the file
        # @param filter_result : The returned filtering result
        # @result_index : The current numbering index
        # @path_to_directory : The path to the directory where files are to be saved
    def handle_file_result(self, response: requests.Response, filter_result: tuple, result_index: int,
                           path_to_directory: str):
        if filter_result[0]:
            if DuplicateFilter.DuplicateFilter().add_paper(filter_result[1], filter_result[2],
                                                           filter_result[3], filter_result[4]):
                writer = FileWriter.FileWriter()
                file_path = os.path.join(path_to_directory, "Articles", f"{result_index}.pdf")
                writer.write_file(file_path, response.content, 'wb')
                writer.write_file(os.path.join(path_to_directory, "Titles", f"{result_index}.txt"),
                                  filter_result[1], 'w', "utf-8")
                writer.write_file(os.path.join(path_to_directory, "Keywords", f"{result_index}.txt"),
                                  filter_result[2], 'w', "utf-8")
                writer.write_file(os.path.join(path_to_directory, "Authors", f"{result_index}.txt"),
                                  filter_result[3], 'w', "utf-8")
                writer.write_file(os.path.join(path_to_directory, "ModDate", f"{result_index}.txt"),
                                  filter_result[4], 'w', "utf-8")
                # print(f"File '{file_path}' downloaded.")
                result_index += 1
        else:
            # print(f"File filtered out.")
            if filter_result[1] is not None:
                writer = FileWriter.FileWriter()
                os.path.join(path_to_directory, "Bad", "Keywords", f"{result_index}.txt")
                writer.write_file(os.path.join(path_to_directory, "Bad", "Titles", f"{result_index}.txt"),
                                  filter_result[1], 'w', "utf-8")
                writer.write_file(os.path.join(path_to_directory, "Bad", "Keywords", f"{result_index}.txt"),
                                  filter_result[2], 'w', "utf-8")
                result_index += 1
        return result_index


