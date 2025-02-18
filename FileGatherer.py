import requests
from bs4 import BeautifulSoup
import time

import FileFilterer
import FileWriter


class FileGatherer:

    # Gather files from each result, including ones that are referenced on each web page
        # @param results : List of scraped results from Google Scholar
        # @param q : The Google Scholar search query
    def gather_files(self, results, q):
        result_index = -1
        for result in results:  # Iterate over results
            result_index += 1
            time.sleep(3)  # Sleep for 3 seconds to avoid angering any anti-bot policies
            # Some results have a file_link, which may be different from the regular link, but not all have this
            #   so, if this value is None, then just use the regular file link, which all results have
            url = result['file_link']
            if url is None:
                url = result['link']
            if url is None:
                print(f"No link for index {result_index}.")
                continue
            try:
                response = requests.get(url)  # Use GET request on URL
            except Exception as e:
                print("Error on index " + str(result_index) + "\n\tException: ", e)
                continue
            if url[-4:] == ".pdf":
                FileWriter.FileWriter().write_file("Files\\pdf" + str(result_index) + ".pdf", response.content, 'wb')
                print(f"Saved PDF directly from index {result_index}.")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')  # Use BeautifulSoup to parse the returned results
            links = soup.find_all('a')  # Find all hyperlinks present on webpage
            i = 0  # Used for numbering the PDFs

            # Check all links for PDFs and grab the ones that are found
            #   this is the step that introduces problems, as some links report to be PDFs
            #   but are not or are just empty -- handled in post-processing
            for link in links:
                if ('.pdf' in link.get('href', [])):
                    i += 1
                    print("Downloading file: " + str(result_index) + "-" + str(i))

                    # Try to get a response object for this link -- sometimes fails due to broken links or 403 errors
                    try:
                        response = requests.get(link.get('href'))
                    except Exception as e:
                        print("Unable to download results from index " + str(result_index))
                        print("\tException: ", e)
                        continue

                    # Write content in pdf file
                    file_path = "Files\\pdf" + str(result_index) + "-" + str(i) + ".pdf"
                    FileWriter.FileWriter().write_file(file_path, response.content, 'wb')
                    if FileFilterer.FileFilterer().filter(file_path, q):
                        print(f"File '{file_path}' downloaded.")
                    else:
                        # File is bad and must be deleted
                        FileWriter.FileWriter().remove_file(file_path)
                        print(f"File '{file_path}' deleted.")
            if i == 0:
                print("No files from index " + str(result_index))
        print("All results scraped.")


