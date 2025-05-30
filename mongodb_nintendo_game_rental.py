import pymongo
import bcrypt
import ast
import pandas as pd
import random
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class LoginManager:

    def __init__(self) -> None:
        # MongoDB connection
        self.client = pymongo.MongoClient("mongodb://localhost:27017/")
        self.db = self.client["hw3"]
        self.collection = self.db["users"]
        self.salt = b"$2b$12$ezgTynDsK3pzF8SStLuAPO"  # TODO: if not working, generate a new salt

    def register_user(self, username: str, password: str) -> None:
        if not username or not password:
            raise ValueError("Username and password are required.")
        if len(username) < 3 or len(password) < 3:
            raise ValueError("Username and password must be at least 3 characters.")
        if self.collection.find_one({"username": username}):
            raise ValueError(f"User already exists: {username}.")
        encrypted_password = bcrypt.hashpw(password.encode('utf-8'), self.salt)
        self.collection.insert_one({"username": username, "password": encrypted_password, "rented_games": []})

    def login_user(self, username: str, password: str) -> object:
        encrypted_password = bcrypt.hashpw(password.encode('utf-8'), self.salt)
        user = self.collection.find_one({"username": username, "password": encrypted_password})
        if user:
            print(f"Logged in successfully as: {username}")
            return user
        raise ValueError("Invalid username or password")


class DBManager:

    def __init__(self) -> None:
        # MongoDB connection
        self.client = pymongo.MongoClient("mongodb://localhost:27017/")
        self.db = self.client["hw3"]
        self.user_collection = self.db["users"]
        self.game_collection = self.db["games"]

    def load_csv(self) -> None:
        games_df = pd.read_csv("NintendoGames.csv")
        for index, row in games_df.iterrows():
            # Convert genres field to a list and add is_rented field
            row["genres"] = ast.literal_eval(row["genres"])
            row["is_rented"] = False
            if not self.game_collection.find_one({"title": row["title"]}):
                self.game_collection.insert_one(row.to_dict())

    def rent_game(self, user: dict, game_title: str) -> str:
        # Fetch the current state of the user from the database
        current_user = self.user_collection.find_one({"username": user["username"]})
        game = self.game_collection.find_one({"title": game_title})
        if game:
            if not game["is_rented"]:
                # Mark the game as rented and update the user's rented games list
                self.game_collection.update_one({"_id": game["_id"]}, {"$set": {"is_rented": True}})
                self.user_collection.update_one({"_id": current_user["_id"]}, {"$push": {"rented_games": game["_id"]}})
                return f"{game_title} rented successfully"
            return f"{game_title} is already rented"
        return f"{game_title} not found"

    def return_game(self, user: dict, game_title: str) -> str:
        # Fetch the current state of the user from the database
        current_user = self.user_collection.find_one({"username": user["username"]})
        game = self.game_collection.find_one({"title": game_title})
        if game and game["_id"] in current_user["rented_games"]:
            # Remove the game from the user's rented games list and mark it as not rented
            self.user_collection.update_one({"_id": current_user["_id"]}, {"$pull": {"rented_games": game["_id"]}})
            self.game_collection.update_one({"_id": game["_id"]}, {"$set": {"is_rented": False}})
            return f"{game_title} returned successfully"
        return f"{game_title} was not rented by you"

    def recommend_games_by_genre(self, user: dict) -> list:
        # Fetch the current state of the user from the database
        current_user = self.user_collection.find_one({"username": user["username"]})
        rented_games_by_user = current_user.get("rented_games", [])
        if not rented_games_by_user:
            return ["No games rented"]
        rented_games = self.game_collection.find({"_id": {"$in": rented_games_by_user}})
        genres = [genre for game in rented_games for genre in game["genres"]]
        # Calculate the genre distribution and select a random genre based on weights
        genre_distribution = {genre: genres.count(genre) for genre in set(genres)}
        random_genre = random.choices(list(genre_distribution.keys()), weights=list(genre_distribution.values()), k=1)[0]
        # Find and return up to 5 games of the selected genre that the user has not rented
        recommended_games = self.game_collection.aggregate([{"$match": {"genres": random_genre, "_id": {"$nin": rented_games_by_user}}}, {"$sample": {"size": 5}}])
        return [game["title"] for game in recommended_games]

    def recommend_games_by_name(self, user: dict) -> list:
        # Fetch the current state of the user from the database
        current_user = self.user_collection.find_one({"username": user["username"]})
        rented_games_by_user = current_user.get("rented_games", [])
        if not rented_games_by_user:
            return ["No games rented"]
        rented_games = list(self.game_collection.find({"_id": {"$in": rented_games_by_user}}))
        random_game = random.choice(rented_games)
        # Use TF-IDF to find similar game titles
        not_rented_games = list(self.game_collection.find({"_id": {"$nin": rented_games_by_user}}))
        titles = [game["title"] for game in not_rented_games]
        # Include the random game title temporarily to compute TF-IDF similarity
        all_titles = titles + [random_game["title"]]
        tfidf = TfidfVectorizer().fit_transform(all_titles)
        cosine_sim = cosine_similarity(tfidf)
        random_game_index = len(all_titles) - 1
        similar_indices = cosine_sim[random_game_index][:-1].argsort()[-5:][::-1]
        # Get the top 5 recommendations excluding rented games
        recommendations = [titles[i] for i in similar_indices if i < len(titles)]
        return recommendations

    def find_top_rated_games(self, min_score) -> list:
        games = self.game_collection.find({"user_score": {"$gte": min_score}}, {"title": 1, "user_score": 1})
        return [{"title": game["title"], "user_score": game["user_score"]} for game in games]

    def decrement_scores(self, platform_name) -> None:
        self.game_collection.update_many({"platform": platform_name}, {"$inc": {"user_score": -1}})

    def get_average_score_per_platform(self) -> dict:
        pipeline = [{"$group": {"_id": "$platform", "average_score": {"$avg": "$user_score"}}}, {"$project": {"_id": 1,"average_score": {"$round": ["$average_score", 3]}}}]
        results = self.game_collection.aggregate(pipeline)
        return {result["_id"]: result["average_score"] for result in results}

    def get_genres_distribution(self) -> dict:
        pipeline = [{"$unwind": "$genres"}, {"$group": {"_id": "$genres", "count": {"$sum": 1}}}]
        results = self.game_collection.aggregate(pipeline)
        return {result["_id"]: result["count"] for result in results}
