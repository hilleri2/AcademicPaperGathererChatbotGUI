import json
import os
import time

import FileGatherer
import ResultGatherer
import TextConverterAndExtractor

if __name__ == '__main__':
    # This file is used for running the tool manually, without CLI
    # Use cli.py for running under normal circumstances
    searches = [("Bovine colostrum for human consumption", "BovineCol"),
                ("empirical software engineering", "EmpiricalSoftware"),
                ("large language models", "LLM"),
                ("whey protein unfolding compound binding OR coacervation", "wheyProtein"),
                ("Ceramic microfiltration MF WPI purification", "ceramicMicro")]
    timings = []
    for q, p in searches:
        start = time.perf_counter()
        results = ResultGatherer.ResultGatherer().scrape_results(q, 100, year_start, year_end)
        end = time.perf_counter()
        result_time = end - start
        os.makedirs(p, exist_ok=True)  # Ensure the directory exists
        json.dump(results, open(os.path.join(p, "results.txt"), 'w'))
        # results = json.load(open(os.path.join(path_to_directory, "results.txt")))
        start = time.perf_counter()
        FileGatherer.FileGatherer().gather_files(results, q, p,
                                                 meta_can_be_missing, year_start, year_end)
        end = time.perf_counter()
        file_time = end - start
        start = time.perf_counter()
        TextConverterAndExtractor.TextConverterAndExtractor().convert_and_extract(p)
        end = time.perf_counter()
        convert_time = end - start
        timing = f"Results for {q}" \
                 f"\n\tResult time: {result_time:.6f} seconds" \
                 f"\n\tFile time: {file_time:.6f} seconds" \
                 f"\n\tConvert time: {convert_time:.6f} seconds"
        print(timing)
        timings.append(timing)
    for t in timings:
        print(t)

