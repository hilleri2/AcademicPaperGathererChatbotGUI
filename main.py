import json
import os

import FileFilterer
import FileWriter
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
    results = ResultGatherer.ResultGatherer().scrape_results(query, 100)
    os.makedirs(path_to_directory, exist_ok=True)  # Ensure the directory exists
    json.dump(results, open(os.path.join(path_to_directory, "results.txt"), 'w'))
    # results = json.load(open(os.path.join(path_to_directory, "results.txt")))
    FileGatherer.FileGatherer().gather_files(results, query, path_to_directory)
    TextConverterAndExtractor.TextConverterAndExtractor().convert_and_extract(path_to_directory)


