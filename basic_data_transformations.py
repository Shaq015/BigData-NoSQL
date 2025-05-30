import pyodbc
import csv

class DatabaseManager:
    def __init__(self, driver: str, server: str, username: str, password: str):
        self.connection_string = f"DRIVER={driver};SERVER={server};DATABASE={username};UID={username};PWD={password};TrustServerCertificate=YES"

    def _open_connection(self):
        try:
            self.__connection = pyodbc.connect(self.connection_string)
            self.__cursor = self.__connection.cursor()
        except pyodbc.Error as e:
            print(f"Connection Failed: {e}")
            raise

    def _close_connection(self):
        try:
            self.__cursor.close()
            self.__connection.close()
        except pyodbc.Error as e:
            print(f"Error closing connection: {e}")
            raise

    def file_to_database(self, path: str) -> None:
        self._open_connection()
        try:
            with open(path, 'r') as file:
                reader = csv.reader(file)
                for row in reader:
                    title, prod_year = row
                    self.__cursor.execute("INSERT INTO dbo.MediaItems (TITLE, PROD_YEAR) VALUES (?, ?)", (title, prod_year))
                    self.__connection.commit()
            print("Data successfully inserted")
        except pyodbc.Error as e:
            print(f"Error reading the file: {e}")
            self.__connection.rollback()
            raise
        finally:
            self._close_connection()

    def calculate_similarity(self) -> None:
        self._open_connection()
        try:
            self.__cursor.execute("SELECT dbo.MaximalDistance()")
            max_distance = self.__cursor.fetchone()[0]
            if max_distance == 0:
                print("Cannot calculate similarity - division by 0")
                return
            self.__cursor.execute("SELECT MID FROM MediaItems")
            mids_list = [row[0] for row in self.__cursor.fetchall()]
            for i in range(len(mids_list)):
                for j in range(i + 1, len(mids_list)):
                    mid1 = mids_list[i]
                    mid2 = mids_list[j]
                    self.__cursor.execute("SELECT dbo.SimCalculation(?, ?, ?)", mid1, mid2, max_distance)
                    similarity = self.__cursor.fetchone()[0]
                    self.__cursor.execute("INSERT INTO Similarity (MID1, MID2, SIMILARITY) VALUES (?, ?, ?)", mid1, mid2, similarity)
                    self.__connection.commit()
            print("Similarity calculation completed")
        except pyodbc.Error as e:
            print(f"Error calculating similarity: {e}")
            self.__connection.rollback()
            raise
        finally:
            self._close_connection()

    def print_similar_items(self, mid: int) -> None:
        self._open_connection()
        try:
            self.__cursor.execute("""SELECT m.TITLE, s.SIMILARITY
                                FROM Similarity s
                                Join MediaItems m on m.MID = s.MID2
                                Where s.MID1 = ? AND s.Similarity >= 0.25
                                ORDER BY s.Similarity ASC""", mid)
            results = self.__cursor.fetchall()
            if not results:
                print(f"No similarities found between {mid} and the rest of the movies")
                return
            for title, similarity in results:
                print(f"Title: {title}, Similarity: {similarity}")
        except pyodbc.Error as e:
            print(f"Error in retrieving similar items: {e}")
            self.__connection.rollback()
            raise
        finally:
            self._close_connection()

    def add_summary_items(self) -> None:
        self._open_connection()
        try:
            self.__cursor.execute("EXEC AddSummaryItems")
            self.__connection.commit()
        except pyodbc.Error as e:
            print(f"Error in AddSummaryItems execution: {e}")
            self.__connection.rollback()
            raise
        finally:
            self._close_connection()
