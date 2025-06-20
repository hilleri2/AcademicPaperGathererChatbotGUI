import json
import os
import time

import TextConverterAndExtractor
import ResultGatherer
import FileGatherer


if __name__ == '__main__':
    query = "Bovine colostrum for human consumption"
    path_to_directory = "BovineCol"
    # query = "empirical software engineering"
    # path_to_directory = "EmpiricalSoftware"
    # query = "large language models"
    # path_to_directory = "LLM"
    # query = "whey protein unfolding compound binding OR coacervation"
    # path_to_directory = "wheyProtein"
    # query = "Ceramic microfiltration MF WPI purification"
    # path_to_directory = "ceramicMicro"
    meta_can_be_missing = True
    year_start = None  # Start year of a date range
    year_end = None  # End year of a date range
    start = time.perf_counter()
    results = ResultGatherer.ResultGatherer().scrape_results(query, 100, year_start, year_end)
    end = time.perf_counter()
    result_time = end - start
    os.makedirs(path_to_directory, exist_ok=True)  # Ensure the directory exists
    json.dump(results, open(os.path.join(path_to_directory, "results.txt"), 'w'))
    # results = json.load(open(os.path.join(path_to_directory, "results.txt")))
    start = time.perf_counter()
    FileGatherer.FileGatherer().gather_files(results, query, path_to_directory,
                                             meta_can_be_missing, year_start, year_end)
    # print(f"Duplicates papers found: {DuplicateFilter.DuplicateFilter().duplicateCount}")
    end = time.perf_counter()
    file_time = end - start
    start = time.perf_counter()
    TextConverterAndExtractor.TextConverterAndExtractor().convert_and_extract(path_to_directory)
    end = time.perf_counter()
    convert_time = end - start
    print(f"Result time: {result_time:.6f} seconds")
    print(f"File time: {file_time:.6f} seconds")
    print(f"Convert time: {convert_time:.6f} seconds")
