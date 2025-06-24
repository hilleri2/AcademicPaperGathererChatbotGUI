import argparse
import os
import json

import FileGatherer
import ResultGatherer
import TextConverterAndExtractor


# Method that validates a CLI parameter is a positive integer
    # @param value : The value to validate
def valid_positive_int(value):
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError("Must be a positive integer.")
    return ivalue


# Method that validates a CLI parameter is a valid year
    # @param value : The value to validate
def valid_year(value):
    ivalue = int(value)
    if ivalue < 1900 or ivalue > 2100:
        raise argparse.ArgumentTypeError("Year must be between 1900 and 2100.")
    return ivalue


# Method that runs the result gathering portion of the tool
    # @param query : The Google Scholar search query
    # @param directory : The directory to save files to
    # @param total_results : The total number of results to gather
    # @param year_start : The starting year of a date range - use None if no filtering is desired
    # @param year_end : The ending year of a date range - use None if no filtering is desired
def run_result_gatherer(query, directory, total_results, year_start, year_end):
    results = ResultGatherer.ResultGatherer().scrape_results(query, total_results, year_start, year_end)
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "results.txt"), 'w') as f:
        json.dump(results, f)
    return results


# Method that runs the file gathering portion of the tool
    # @param query : The Google Scholar search query
    # @param directory : The directory to save files to
    # @param year_start : The starting year of a date range - use None if no filtering is desired
    # @param year_end : The ending year of a date range - use None if no filtering is desired
    # @param meta_can_be_missing : Boolean toggle that determines if absent title and author is acceptable
def run_file_gatherer(query, directory, year_start, year_end, meta_can_be_missing):
    results_path = os.path.join(directory, "results.txt")
    if not os.path.exists(results_path):
        raise FileNotFoundError(f"Cannot find results file: {results_path}")
    with open(results_path, 'r') as f:
        results = json.load(f)
    FileGatherer.FileGatherer().gather_files(results, query, directory, meta_can_be_missing, year_start, year_end)


# Method that runs the text converting and extracting portion of the tool
    # @param directory : The directory to save files to
def run_text_converter(directory):
    TextConverterAndExtractor.TextConverterAndExtractor().convert_and_extract(directory)


# Method that parses CLI arguments
def parse_args():
    # Create a parser for CLI
    parser = argparse.ArgumentParser(description="Run the data gathering and processing pipeline.")
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Add a subparser for running all portions of the tool
    all_parser = subparsers.add_parser('all', help='Run the full pipeline')
    all_parser.add_argument('--query', required=True)
    all_parser.add_argument('--directory', required=True)
    all_parser.add_argument('--total_results', type=valid_positive_int, default=100)
    all_parser.add_argument('--year_start', type=valid_year, default=None)
    all_parser.add_argument('--year_end', type=valid_year, default=None)
    all_parser.add_argument('--meta_can_be_missing', action='store_true')

    # Add a subparser for running just the result gathering portion of the tool
    res_parser = subparsers.add_parser('results', help='Run only result gathering')
    res_parser.add_argument('--query', required=True)
    res_parser.add_argument('--directory', required=True)
    res_parser.add_argument('--total_results', type=valid_positive_int, default=100)
    res_parser.add_argument('--year_start', type=valid_year, default=None)
    res_parser.add_argument('--year_end', type=valid_year, default=None)

    # Add a subparser for running just the file gathering portion of the tool
    files_parser = subparsers.add_parser('files', help='Run only file gathering')
    files_parser.add_argument('--query', required=True)
    files_parser.add_argument('--directory', required=True)
    files_parser.add_argument('--year_start', type=valid_year, default=None)
    files_parser.add_argument('--year_end', type=valid_year, default=None)
    files_parser.add_argument('--meta_can_be_missing', action='store_true')

    # Add a subparser for running just the text converting and extracting portion of the tool
    conv_parser = subparsers.add_parser('convert', help='Run only text conversion and extraction')
    conv_parser.add_argument('--directory', required=True)

    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()  # Get the args

    # Run only the portion(s) of the tool that is appropriate
    if args.command == 'all':
        run_result_gatherer(args.query, args.directory, args.total_results, args.year_start, args.year_end)
        run_file_gatherer(args.query, args.directory, args.year_start, args.year_end, args.meta_can_be_missing)
        run_text_converter(args.directory)

    elif args.command == 'results':
        run_result_gatherer(args.query, args.directory, args.total_results, args.year_start, args.year_end)

    elif args.command == 'files':
        run_file_gatherer(args.query, args.directory, args.year_start, args.year_end, args.meta_can_be_missing)

    elif args.command == 'convert':
        run_text_converter(args.directory)
