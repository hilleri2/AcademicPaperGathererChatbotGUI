import os


class FileWriter:

    # CHeck if a path is valid and create any needed directories
        # @param path : The path to check, including the file name
    def __check_path(self, path):
        value = 0
        parent = path.rsplit("\\")[0]
        try:
            os.mkdir(parent)
        except FileExistsError:
            print(f"Directory '{parent}' already exists.")
            pass
        except PermissionError:
            print(f"Can not create directory '{parent}' due to permission error.")
            value = -1
        except Exception as e:
            print(f"Error encountered: {e}")
            value = -1
        return value

    # Write a file to a specified path, after verifying the path
        # @param path : The path to write the file to, including file name
        # @param content : The contents of the file
        # @param write_type : The writing mode to use for this file
    def write_file(self, path, content, write_type):
        value = self.__check_path(path)
        if value == 0:
            file = open(path, write_type)
            file.write(content)
            file.close()

    # Remove a file, if it exists
        # @param path : The file's path
    def remove_file(self, path):
        if os.path.exists(path):
            os.remove(path)
        else:
            print(f"Path '{path}' does not exist.")
