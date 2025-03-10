from pathlib import Path
import pymupdf

import FileWriter


class PlainTextConverter:

    # Method that converts the PDF articles into simple plain text representations
        # @param path_to_directory : The path to the directory where all files will be saved
    def convert(self, path_to_directory):
        path_list = Path(f"{path_to_directory}\\Articles\\").glob('**/*.pdf')

        for p in path_list:
            writer = FileWriter.FileWriter()
            index = p.stem
            doc = pymupdf.open(p)  # Open the file

            # Convert the PDF to plain text
            content = ""  # String to store the text
            # Extract the text and store in content
            for _ in range(doc.page_count):
                content += doc.load_page(_).get_text() + "\n"
            # Write the text as a file
            writer.write_file(f"{path_to_directory}\\Articles-Text\\{index}.txt", content, 'w', "utf-8")

            # Extract images
            image_list = []
            i = 0
            end = doc.xref_length()
            for xref in range(1, end):
                try:
                    if doc.xref_is_image(xref) is False:
                        continue
                    img = doc.extract_image(xref)
                except Exception as e:
                    print(f"Article: {index} - Encountered error with xref: {xref}\tError: ", e)
                    continue
                image_list.append((img['image'], img['ext'], i))
                i += 1
            for image in image_list:
                writer.write_file(
                    f"{path_to_directory}\\Images\\{index}\\image{image[2]}.{image[1]}", image[0], 'wb')

            # Close the file and move to next
            doc.close()

