import io

import PyPDF2
from fuzzywuzzy import fuzz


class FileFilterer:

    # Determines the Jaccard Similarity for a query and a paper's title
    # Useful for substring matching
        # @param query : The Google Scholar search query
        # @param title : The paper title
    def jaccard_similarity(self, query: str, title: str):
        set1, set2 = set(query.lower().split()), set(title.lower().split())
        return len(set1 & set2) / len(set1 | set2) if set1 | set2 else 0

    # Determines the Fuzzy Partial Matching score for a query and a paper's title and keywords
    # Useful for word order integrity and typo handling
        # @param query : The Google Scholar search query
        # @param title : The paper title
        # @param keywords : The paper keywords
    def fuzzy_partial(self, query: str, title: str, keywords: list):
        title_score = fuzz.partial_ratio(query, title)
        keyword_score = max([fuzz.partial_ratio(query, kw) for kw in keywords], default=0)
        return max(title_score, keyword_score)

    # Combines Jaccard Similarity and Fuzzy Partial Matching for a hybrid approach
    # This allows for typo handling, order integrity, and substring matching to all be considered
        # @param query : The Google Scholar search query
        # @param title : The paper title
        # @param keywords : The paper keywords
    def hybrid_match(self, query: str, title: str, keywords: list):
        query = query.lower()
        title = title.lower()
        keywords = [kw.lower() for kw in keywords]
        jaccard = self.jaccard_similarity(query, title)
        fuzzy = self.fuzzy_partial(query, title, keywords)
        return (jaccard * 100 + fuzzy) / 2  # Normalize Jaccard and blend scores

    # Determines if a file is good and relevant to the query or not
        # @param file : The file to check
        # @param query : The Google Scholar search query
    def filter(self, file: io.BytesIO, query: str):
        is_good_file = (False, None, None, None, None)
        try:
            pdf_reader = PyPDF2.PdfReader(file)
            meta = pdf_reader.metadata
        except Exception as e:
            # print("File could not be opened.")
            # Bad file
            return is_good_file
        else:
            if meta is None:
                # Unknown file
                # print("File read as NoneType")
                return is_good_file
            if '/Title' not in meta.keys() or '/Author' not in meta.keys() or '/ModDate' not in meta.keys():
                # Unknown file
                pass
                # print(f"Not enough data in PDF to know")
            else:
                title = meta['/Title']
                if '/Keywords' not in meta.keys():
                    keywords = [""]
                else:
                    keywords = meta['/Keywords']
                    if not isinstance(keywords, list):
                        keywords = [keywords]  # Convert to list, if not already
                score = self.hybrid_match(query, title, keywords)
                keywords = str(keywords)  # Convert list to string for printing ease later
                # Dynamically set threshold dependent on query length, i.e. short and long queries have lower threshold
                threshold = 50 if (len(query.split()) <= 3 or len(query.split()) >= 7) else 60
                if score >= threshold:
                    modDate = meta['/ModDate'][6:8] + '-' + meta['/ModDate'][2:6]
                    is_good_file = (True, title, keywords, meta['/Author'], modDate)
                else:  # TEST CODE
                    is_good_file = (False, title, keywords, None, None)
            return is_good_file

