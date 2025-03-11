import os
import requests
from bs4 import BeautifulSoup
import random
import time
import io

import FileFilterer
import FileWriter
import DuplicateFilter


class FileGatherer:

    # Gather files from each result, including ones that are referenced on each web page
        # @param results : List of scraped results from Google Scholar
        # @param query : The Google Scholar search query
        # @param path_to_directory : The path to the directory where all files will be saved
    def gather_files(self, results: list, query: str, path_to_directory: str):
        result_index = 1
        print_index = 0
        for result in results:  # Iterate over results
            print_index += 1
            print(f"\rProcessing index {print_index}...", end="")
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
            try:
                response = requests.get(url)  # Use GET request on URL
            except Exception as e:
                print("\nError on index " + str(print_index) + "\n\tException: ", e)
                continue
            if url[-3:] == "pdf":
                content_type = response.headers.get("Content-Type", "")
                if "pdf" not in content_type.lower():
                    print(f"\nWarning: pdf{print_index} might not be a valid PDF (Content-Type: {content_type})")
                else:
                    pdf_file_obj = io.BytesIO(response.content)  # Save file in memory
                    filter_result = FileFilterer.FileFilterer().filter(pdf_file_obj, query)
                    result_index = self.handle_file_result(response, filter_result, result_index, path_to_directory)
                    # if filter_result[0]:
                    #     print(f"Saved PDF directly from index {result_index-1}.")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')  # Use BeautifulSoup to parse the returned results
            links = soup.find_all('a')  # Find all hyperlinks present on webpage
            i = 0  # Used for numbering the PDFs

            # Check all links for PDFs and grab the ones that are found
            #   this is the step that introduces problems, as some links report to be PDFs
            #   but are not or are just empty -- handled in post-processing
            for link in links:
                if ('.pdf' in link.get('href', [])):
                    # i += 1
                    # print(f"Checking file {i} from current index...")

                    # Try to get a response object for this link -- sometimes fails due to broken links or 403 errors
                    try:
                        response = requests.get(link.get('href'))
                    except Exception as e:
                        print("\nUnable to download results from index " + str(print_index))
                        print("\tException: ", e)
                        continue

                    pdf_file_obj = io.BytesIO(response.content)  # Save file in memory
                    filter_result = FileFilterer.FileFilterer().filter(pdf_file_obj, query)
                    result_index = self.handle_file_result(response, filter_result, result_index, path_to_directory)
            # if i == 0:
            #     print("No files from index " + str(result_index))
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


