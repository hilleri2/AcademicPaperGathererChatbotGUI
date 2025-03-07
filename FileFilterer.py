import PyPDF2
from fuzzywuzzy import fuzz


class FileFilterer:

    # Determines the Jaccard Similarity for a query and a paper's title
    # Useful for substring matching
        # @param query : The Google Scholar search query
        # @param title : The paper title
    def jaccard_similarity(self, query, title):
        set1, set2 = set(query), set(title)
        return len(set1 & set2) / len(set1 | set2)

    # Determines the Fuzzy Partial Matching score for a query and a paper's title and keywords
    # Useful for word order integrity and typo handling
        # @param query : The Google Scholar search query
        # @param title : The paper title
        # @param keywords : The paper keywords
    def fuzzy_partial(self, query, title, keywords):
        title_score = fuzz.partial_ratio(query, title)
        keyword_score = max([fuzz.partial_ratio(query, kw) for kw in keywords], default=0)
        return max(title_score, keyword_score)

    # Combines Jaccard Similarity and Fuzzy Partial Matching for a hybrid approach
    # This allows for typo handling, order integrity, and substring matching to all be considered
        # @param query : The Google Scholar search query
        # @param title : The paper title
        # @param keywords : The paper keywords
    def hybrid_match(self, query, title, keywords):
        query = query.lower()
        title = title.lower()
        keywords = [kw.lower() for kw in keywords]
        jaccard = self.jaccard_similarity(query, title)
        fuzzy = self.fuzzy_partial(query, title, keywords)
        return (jaccard * 100 + fuzzy) / 2  # Normalize Jaccard and blend scores

    # Determines if a file is good and relevant to the query or not
        # @param file : The file to check
        # @param query : The Google Scholar search query
    def filter(self, file, query):
        is_good_file = (False, None, None, None, None)
        try:
            #pdf_file_obj = open(file, 'rb')
            pdf_reader = PyPDF2.PdfReader(file)
            meta = pdf_reader.metadata
        except Exception as e:
            print("File could not be opened.")
            # Bad file
            return is_good_file
        else:
            if meta is None:
                print("File read as NoneType")
                # Unknown file
                return is_good_file
            # in_title = False
            # in_keywords = False
            # term = 'bovine colostrum'
            if '/Title' not in meta.keys() or '/Keywords' not in meta.keys() \
                    or '/Author' not in meta.keys() or '/ModDate' not in meta.keys():
                print(f"Not enough data in PDF to know")
                # Unknown file
            else:
                title = meta['/Title']
                keywords = meta['/Keywords']
                score = self.hybrid_match(query, title, keywords)
                if score >= 60:
                    is_good_file = (True, title, keywords, meta['/Author'], meta['/ModDate'])
                else:  # TEST CODE
                    is_good_file = (False, title, keywords, None, None)
            return is_good_file

            #     if term in meta['/Title'].lower():
            #         in_title = True
            #     for keyword in meta['/Keywords']:
            #         if term in keyword.lower():
            #             in_keywords = True
            #     if in_title or in_keywords:
            #         print("Good file.")
            #         is_good_file = True  # Must get here to return true
            #     else:
            #         print("Non-relevant paper.")
            # return is_good_file
