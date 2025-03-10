import json
import requests

import FileFilterer
import FileWriter
import TextConverterAndExtractor
import ResultGatherer
import FileGatherer


if __name__ == '__main__':
    query = "Bovine colostrum for human consumption"
    path_to_directory = "Files"
    # results = ResultGatherer.ResultGatherer().scrape_results(query, 20)
    # json.dump(results, open(f"{path_to_directory}\\results.txt", "w"))
    # results = json.load(open(f"{path_to_directory}\\results.txt"))
    # FileGatherer.FileGatherer().gather_files(results, query, path_to_directory)
    # TextConverterAndExtractor.TextConverterAndExtractor().convert_and_extract(path_to_directory)


