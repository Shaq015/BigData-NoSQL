from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime
from sqlalchemy import func
import bcrypt

Base = declarative_base()


class User(Base):
    __tablename__ = "Users"
    id = Column(String(255), primary_key=True)
    password = Column(LargeBinary, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    date_of_birth = Column(DateTime, nullable=False)
    registration_date = Column(DateTime, default=datetime.datetime.now, nullable=False)
    histories = relationship("History", back_populates="user")

    def __init__(
        self,
        username,
        password,
        first_name,
        last_name,
        date_of_birth,
        registration_date,
    ):
        self.id = username
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        self.first_name = first_name
        self.last_name = last_name
        self.date_of_birth = date_of_birth
        self.registration_date = registration_date

    def add_history(self, media_item_id):
        new_history = History(user_id=self.id, media_item_id=media_item_id, viewtime=datetime.datetime.now())
        self.histories.append(new_history)

    def sum_title_length(self):
        return sum(history.mediaitem.title_length for history in self.histories if history.mediaitem)


class MediaItem(Base):
    __tablename__ = "MediaItems"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    prod_year = Column(Integer, nullable=False)
    title_length = Column(Integer, nullable=False)

    def __init__(self, title, prod_year, title_length):
        self.title = title
        self.prod_year = prod_year
        self.title_length = title_length


class History(Base):
    __tablename__ = "History"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), ForeignKey('Users.id'), nullable=False)
    media_item_id = Column(Integer, ForeignKey('MediaItems.id'), nullable=False)
    viewtime = Column(DateTime, default=datetime.datetime.now, nullable=False)
    user = relationship("User", back_populates="histories")
    mediaitem = relationship("MediaItem")

    def __init__(self, user_id, media_item_id, viewtime):
        self.user_id = user_id
        self.media_item_id = media_item_id
        self.viewtime = viewtime


class Repository:
    def __init__(self, model_class):
        self.model_class=model_class

    def get_by_id(self, session, entity_id):
        return session.query(self.model_class).filter(self.model_class.id == entity_id).first()
    
    def get_all(self,session):
        return session.query(self.model_class).all()
    
    def delete(self,session, entity):
        session.delete(entity)

    def add(self, session, entity):
        session.add(entity)

class UserRepository(Repository):
    def __init__(self):
        super().__init__(User)
   
    def validateUser(self,session, username: str, password: str) -> bool:
        user_to_check = session.query(User).filter_by(id=username).first()  # Query the User table to find a user with the given username
        if not user_to_check:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), user_to_check.password)
    
    def getNumberOfRegistredUsers(self,session, n: int) -> int:
        start_date = datetime.datetime.now() - datetime.timedelta(days=n)
        return session.query(User).filter(User.registration_date >= start_date).count()    # Query the User table to find the number of registered users in the past n days
    
class ItemRepository(Repository):
    def __init__(self):
        super().__init__(MediaItem)

    def getTopNItems(self, session, top_n: int) -> list:
        return session.query(MediaItem).order_by(MediaItem.id.asc()).limit(top_n).all()

class UserService:
    def __init__(self, session, user_repo: UserRepository):
        self.user_repo = user_repo
        self.session = session

    def create_user(self, username, password, first_name, last_name, date_of_birth):
        curr_date = datetime.datetime.now()
        new_user = User(username, password, first_name, last_name, date_of_birth, curr_date)
        self.user_repo.add(self.session, new_user)
        self.session.commit()

    def add_history_to_user(self, username, media_item_id):
        relevant_user = self.session.query(User).filter_by(id=username).first()
        if not relevant_user:
            raise ValueError("User not found")
        relevant_user.add_history(media_item_id)
        self.session.commit()
    
    def validateUser(self, username: str, password: str) -> bool:
        return self.user_repo.validateUser(self.session, username, password)

    def getNumberOfRegistredUsers(self, n: int) -> int:
        return self.user_repo.getNumberOfRegistredUsers(self.session, n)
    
    def sum_title_length_to_user(self, username):
        relevant_user = self.session.query(User).filter_by(id=username).first()
        if not relevant_user:
            raise ValueError("User not found")
        return relevant_user.sum_title_length()

    def get_all_users(self):
        return self.user_repo.get_all(self.session)
    

class ItemService:
    def __init__(self, session, item_repo:ItemRepository):
        self.item_repo = item_repo
        self.session = session

    def create_item(self, title, prod_year):
        media_item = MediaItem(title, prod_year, len(title))
        self.item_repo.add(self.session, media_item)
        self.session.commit()


# username=''
# password=''
# connection_string = f"mssql+pyodbc://{username}:{password}@132.72.64.124/{username}?driver=ODBC+Driver+17+for+SQL+Server"
# engine = create_engine(connection_string)
# Base.metadata.create_all(engine)
# session = sessionmaker(bind=engine)()
